"""Show-Auktion — Kernservice (Spec §7–§12).

Nebenläufigkeit: Jeder schreibende Pfad sperrt ZUERST die Auktionszeile
(select_for_update), danach die Vereinszeile — konsistente Reihenfolge
auf allen Pfaden (Gebot, Kauf, Abwicklung, Abbruch), damit Beat- und
Lazy-Abwicklung nie verklemmen. Geld bewegt sich ausschließlich über
book() (Senke AUKTION mit Idempotenz-Referenz showauction:{id}:settle,
strukturell abgesichert per UniqueConstraint auf FinanceTransaction).
"""
import logging
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Avg
from django.urls import reverse
from django.utils import timezone

from game.economy import reservations
from game.economy.booking import InsufficientFunds, book
from game.economy.kader import effective_squad_limit, squad_count
from game.models import (
    Club,
    CoinTransaction,
    HoenessCoin,
    Player,
    PlayerTransferHistory,
)
from game.notifications import notify_club

from . import pricing
from .models import ShowAuction, ShowAuctionBid, ShowAuctionWatch
from .validator import validate_config

logger = logging.getLogger(__name__)

_rng = secrets.SystemRandom()

WECHSELSPERRE_TAGE = 21
RESERVIERUNGS_ZWECK = 'showauction'


class AuctionError(Exception):
    """Fachlicher Fehler mit deutscher, nutzerlesbarer Meldung."""


def fmt_eur(value):
    ganze = int(Decimal(str(value)))
    return f'{ganze:,}'.replace(',', '.') + ' €'


def _detail_url(auction):
    return reverse('showauction_detail', args=[auction.pk])


def _bid_ref(bid):
    return f'showauction:bid:{bid.pk}'


# ── Anlage & Lebenszyklus (Creator) ──────────────────────────────────────────

def _needs_market_value(config):
    sp = config.get('startpreis')
    if isinstance(sp, dict) and 'prozent_mw' in sp:
        return True
    if config.get('preisverfall', 'aus') != 'aus':
        return True
    if 'korridor' in config:
        return True
    return False


def create_auction(*, player, preset, created_by=None, config_overrides=None,
                   conditions=None, color_hex=None, rules_text=None):
    """Auktion anlegen — Spieler betritt den Raum bereits als Entwurf (E33)."""
    config = dict(preset.config or {})
    for key, value in (config_overrides or {}).items():
        config[key] = value
    if conditions is not None:
        # Bedingungs-Overrides laufen durch DIESELBE Schema-Prüfung wie die
        # Preset-Config (Achse 12) — nie ungeprüft in den Snapshot.
        config['teilnahmebedingungen'] = conditions
    config = validate_config(config)

    with transaction.atomic():
        p = Player.objects.select_for_update().get(pk=player.pk)
        if p.club_id is not None:
            raise AuctionError('Nur vereinslose Spieler können in die Show-Auktion.')
        if p.pool_status == Player.POOL_STATUS_SHOW_AUCTION:
            raise AuctionError('Der Spieler steht bereits in einer Show-Auktion.')
        mw = Decimal(str(p.market_value)) if p.market_value is not None else None
        if mw is None and _needs_market_value(config):
            raise AuctionError(
                'Der Spieler hat keinen Marktwert — Startpreis/Verfall/Korridor '
                'lassen sich nicht berechnen.'
            )
        start_price = pricing.resolve_start_price(config, mw)
        auction = ShowAuction.objects.create(
            preset=preset,
            config_snapshot=config,
            type_name=preset.name,
            color_hex=(color_hex or preset.color_hex),
            rules_text=(rules_text if rules_text is not None else preset.rules_text),
            player=p,
            player_prev_pool_status=p.pool_status,
            status=ShowAuction.STATUS_DRAFT,
            start_price=start_price,
            market_value_snapshot=mw,
            conditions=list(config.get('teilnahmebedingungen') or []),
            created_by=created_by,
        )
        if config.get('gewinnerermittlung') == 'naechstliegend_verborgenes_ziel':
            _draw_corridor(auction, config, mw)
        p.pool_status = Player.POOL_STATUS_SHOW_AUCTION
        p.save(update_fields=['pool_status'])
    return auction


def _draw_corridor(auction, config, market_value):
    """Bereichsauktion: Korridor-Mitte und -Breite ziehen (Spec §4.4).

    Die Mitte wird gleichverteilt aus [spanne_min, spanne_max]·MW gezogen
    (SystemRandom), die Breite ist breite_prozent·MW. Beides bleibt für
    immer verborgen — auch nach Auktionsende (E22).
    """
    kor = config['korridor']
    lo = float(kor['spanne_min_prozent'])
    hi = float(kor['spanne_max_prozent'])
    mitte_prozent = _rng.uniform(lo, hi)
    mitte = Decimal(str(market_value)) * Decimal(str(mitte_prozent)) / 100
    breite = Decimal(str(market_value)) * Decimal(str(kor['breite_prozent'])) / 100
    auction.hidden_target = mitte.quantize(Decimal('1'))
    auction.hidden_width = breite.quantize(Decimal('1'))
    auction.save(update_fields=['hidden_target', 'hidden_width', 'updated_at'])


def schedule_auction(auction, starts_at):
    """Entwurf terminieren (oder geplanten Termin verschieben)."""
    with transaction.atomic():
        a = ShowAuction.objects.select_for_update().get(pk=auction.pk)
        if a.status not in (ShowAuction.STATUS_DRAFT, ShowAuction.STATUS_SCHEDULED):
            raise AuctionError('Nur Entwürfe oder geplante Auktionen lassen sich terminieren.')
        if starts_at is None:
            raise AuctionError('Startzeitpunkt fehlt.')
        a.status = ShowAuction.STATUS_SCHEDULED
        a.starts_at = starts_at
        a.save(update_fields=['status', 'starts_at', 'updated_at'])
    return a


def start_auction_now(auction, now=None):
    """Creator-Aktion: sofort live schalten."""
    now = now or timezone.now()
    with transaction.atomic():
        a = ShowAuction.objects.select_for_update().select_related('player').get(pk=auction.pk)
        if a.status not in (ShowAuction.STATUS_DRAFT, ShowAuction.STATUS_SCHEDULED):
            raise AuctionError('Diese Auktion kann nicht mehr gestartet werden.')
        a.starts_at = now
        _start(a, now)
    return a


def cancel_auction(auction, grund='Vom Creator abgebrochen.'):
    """Abbruch aus draft/scheduled/running — wie geplatzt (Spec §6.2)."""
    now = timezone.now()
    with transaction.atomic():
        a = ShowAuction.objects.select_for_update().select_related('player').get(pk=auction.pk)
        if a.status not in ShowAuction.ACTIVE_STATUSES:
            raise AuctionError('Nur aktive Auktionen lassen sich abbrechen.')
        for b in a.bids.exclude(reservation_ref=''):
            reservations.release(b.reservation_ref)
        p = Player.objects.select_for_update().get(pk=a.player_id)
        if p.pool_status == Player.POOL_STATUS_SHOW_AUCTION:
            p.pool_status = a.player_prev_pool_status or Player.POOL_STATUS_NONE
            p.save(update_fields=['pool_status'])
        a.status = ShowAuction.STATUS_CANCELLED
        a.fail_reason = grund[:200]
        if not a.ends_at or a.ends_at > now:
            a.ends_at = now
        a.save(update_fields=['status', 'fail_reason', 'ends_at', 'updated_at'])
        _notify_watchers(
            a, f'Auktion abgebrochen: {a.player.full_name}',
            body=grund, url=_detail_url(a),
        )
    return a


# ── Zeitsteuerung ────────────────────────────────────────────────────────────

def _cap_by_max(config, starts_at, candidate):
    ml = config.get('maximallaufzeit', 'aus')
    if ml == 'aus' or starts_at is None:
        return candidate
    cap = starts_at + timedelta(days=int(ml['tage']))
    if candidate is None:
        return cap
    return min(candidate, cap)


def _initial_ends_at(auction, config, now):
    starts = auction.starts_at or now
    ende = config['endebedingung']
    if ende == 'deadline':
        ends = starts + timedelta(minutes=int(config['laufzeit_minuten']))
    elif ende == 'haltezeit':
        ends = starts + timedelta(hours=pricing.hold_duration_hours(config, 0))
    elif config['gebotsrichtung'] == 'fallend':
        steps = pricing.dutch_steps_to_floor(
            config, auction.start_price, auction.market_value_snapshot,
        )
        intervall = int(config['preisverfall']['intervall_minuten'])
        ends = starts + timedelta(minutes=steps * intervall)
    else:  # fest: läuft bis Zuschlag bzw. Maximallaufzeit
        ends = None
    return _cap_by_max(config, starts, ends)


def _start(auction, now):
    """Innerhalb der gehaltenen Sperre: scheduled/draft → running."""
    config = auction.cfg
    if not auction.starts_at:
        auction.starts_at = now
    auction.status = ShowAuction.STATUS_RUNNING
    auction.ends_at = _initial_ends_at(auction, config, now)
    auction.save(update_fields=['status', 'starts_at', 'ends_at', 'updated_at'])
    _notify_watchers(
        auction, f'Auktionsstart: {auction.player.full_name}',
        body=f'{auction.type_name} — jetzt live in der Transfershow.',
        url=_detail_url(auction),
    )


def _finish_due(auction, now):
    """Fällige laufende Auktion abschließen (Zuschlag oder Platzen)."""
    config = auction.cfg
    richtung = config['gebotsrichtung']
    if richtung == 'fallend':
        return _fail(auction, now, 'Preisboden erreicht — kein Zuschlag.')
    if richtung == 'fest':
        return _fail(auction, now, 'Maximallaufzeit erreicht — kein Zuschlag.')
    return _settle(auction, now)


def _lazy_transition(auction, now):
    """Unter der Auktions-Sperre: überfällige Übergänge nachholen (E26)."""
    if (auction.status == ShowAuction.STATUS_SCHEDULED
            and auction.starts_at and auction.starts_at <= now):
        _start(auction, now)
    if (auction.status == ShowAuction.STATUS_RUNNING
            and auction.ends_at and now >= auction.ends_at):
        _finish_due(auction, now)


# ── Teilnahmebedingungen (Achse 12, E20: konkreter Grund) ────────────────────

def _coin_condition_amount(auction):
    for cond in (auction.conditions or []):
        if cond.get('art') == 'coins':
            return int(cond.get('anzahl') or 1)
    return 0


def _coin_ticket_paid(auction, club):
    return ShowAuctionBid.objects.filter(
        auction=auction, club=club, coin_charged=True,
    ).exists()


def _freie_kaderplaetze(club, exclude_ref=None):
    from game.scouting.service import reserved_slots as scouting_reserved_slots
    limit = effective_squad_limit(club)
    return (limit - squad_count(club)
            - reservations.reserved_slots(club, exclude_referenz=exclude_ref)
            - scouting_reserved_slots(club))


def _verfuegbares_budget(club, exclude_ref=None):
    from game.scouting.service import reserved_budget as scouting_reserved_budget
    return ((club.budget or Decimal('0.00'))
            - scouting_reserved_budget(club)
            - reservations.reserved_money(club, exclude_referenz=exclude_ref))


def check_participation(auction, club, manager):
    """Erste verletzte Teilnahmebedingung als deutschen Grund liefern, sonst None."""
    if club is None:
        return 'Du brauchst einen Verein, um an Auktionen teilzunehmen.'
    for cond in (auction.conditions or []):
        art = cond.get('art')
        if art == 'max_mw_schnitt':
            grenze = Decimal(str(cond['betrag']))
            schnitt = Player.objects.filter(club=club).aggregate(
                avg=Avg('market_value'),
            )['avg']
            if schnitt is not None and Decimal(schnitt) > grenze:
                return (f'Nur für Vereine mit MW-Schnitt bis {fmt_eur(grenze)} '
                        f'(dein Kader: {fmt_eur(schnitt)}).')
        elif art == 'coins':
            n = int(cond.get('anzahl') or 1)
            if not _coin_ticket_paid(auction, club):
                if manager is None:
                    return 'Kein Managerprofil — Eintritt kann nicht bezahlt werden.'
                verfuegbar = _coins_available(manager)
                if verfuegbar < n:
                    return (f'Eintritt kostet {n} Hoeneß-Coin — '
                            f'verfügbar: {verfuegbar}.')
        elif art == 'freie_kaderplaetze':
            n = int(cond.get('anzahl') or 1)
            frei = _freie_kaderplaetze(club)
            if frei < n:
                return (f'Mindestens {n} freie Kaderplätze nötig — '
                        f'du hast {max(frei, 0)}.')
        elif art == 'mindestkontostand':
            grenze = Decimal(str(cond['betrag']))
            stand = club.budget or Decimal('0.00')
            if stand < grenze:
                return (f'Mindestkontostand {fmt_eur(grenze)} nötig — '
                        f'dein Konto: {fmt_eur(stand)}.')
        elif art == 'liga':
            ligen = cond.get('ligen') or []
            if club.league_id not in ligen:
                try:
                    from game.models import League
                    namen = list(
                        League.objects.filter(pk__in=ligen)
                        .values_list('name', flat=True)
                    )
                    if namen:
                        return 'Nur für Vereine aus: ' + ', '.join(namen) + '.'
                except Exception:  # Anzeige-Fallback, Bedingung greift trotzdem
                    pass
                return 'Diese Auktion ist auf bestimmte Ligen beschränkt.'
    return None


def _coins_available(manager):
    """Coin-Guthaben minus Scouting-Earmarks (gemeinsame Sicht)."""
    from game.scouting.service import coin_earmarked_count, get_current_tm_season_id
    coin = HoenessCoin.objects.filter(manager=manager).first()
    have = coin.amount if coin else 0
    season_id = get_current_tm_season_id(timezone.localdate())
    return have - coin_earmarked_count(manager, season_id)


def _charge_coin_ticket(auction, club, manager):
    """Coin = Eintrittsticket: 1× pro Auktion+Manager, atomar mit dem ersten
    Gebot, KEIN Refund bei Überbietung oder Platzen (Nutzer-Entscheid)."""
    n = _coin_condition_amount(auction)
    if n <= 0 or _coin_ticket_paid(auction, club):
        return False
    if manager is None:
        raise AuctionError('Kein Managerprofil — Eintritt kann nicht bezahlt werden.')
    coin, _ = HoenessCoin.objects.select_for_update().get_or_create(manager=manager)
    from game.scouting.service import coin_earmarked_count, get_current_tm_season_id
    season_id = get_current_tm_season_id(timezone.localdate())
    verfuegbar = coin.amount - coin_earmarked_count(manager, season_id)
    if verfuegbar < n:
        raise AuctionError(
            f'Eintritt kostet {n} Hoeneß-Coin — verfügbar: {verfuegbar}.'
        )
    coin.amount -= n
    coin.save(update_fields=['amount', 'updated_at'])
    CoinTransaction.objects.create(
        manager=manager,
        amount=-n,
        reason=CoinTransaction.REASON_SHOW_AUCTION,
        description=f'Eintritt Show-Auktion #{auction.pk} ({auction.player.full_name})',
    )
    return True


# ── Gebote (Spec §8.1 — eine Transaktion, feste Prüfreihenfolge) ─────────────

def place_bid(auction_id, club, manager, amount, now=None):
    now = now or timezone.now()
    try:
        amount = Decimal(str(amount)).quantize(Decimal('1'))
    except Exception:
        raise AuctionError('Ungültiger Gebotsbetrag.')
    if amount <= 0:
        raise AuctionError('Das Gebot muss größer als 0 € sein.')

    with transaction.atomic():
        try:
            a = (ShowAuction.objects.select_for_update()
                 .select_related('player').get(pk=auction_id))
        except ShowAuction.DoesNotExist:
            raise AuctionError('Diese Auktion existiert nicht (mehr).')
        _lazy_transition(a, now)
        if a.status != ShowAuction.STATUS_RUNNING:
            raise AuctionError('Diese Auktion läuft nicht (mehr).')
        config = a.cfg
        richtung = config['gebotsrichtung']
        if richtung in ('fallend', 'fest'):
            raise AuctionError('Diese Auktion hat keinen Gebotsmodus — nutze den Sofort-Zuschlag.')

        club = Club.objects.select_for_update().get(pk=club.pk)

        # 1) Teilnahmebedingungen (konkreter Grund, E20)
        grund = check_participation(a, club, manager)
        if grund:
            raise AuctionError(grund)

        # 2) Gebotslimit / Änderbarkeit (Achsen 6+7)
        meine = list(a.bids.filter(club=club).order_by('created_at'))
        meine_aktiven = [b for b in meine if b.is_active]
        limit_cfg = config['gebote_pro_manager']
        aenderbar = config.get('gebot_aenderbar', 'nein') == 'ja'
        is_change = False
        if richtung == 'verdeckt':
            if meine_aktiven:
                if not aenderbar:
                    raise AuctionError('Du hast bereits geboten — Gebote sind hier nicht änderbar.')
                is_change = True
            elif limit_cfg == 'genau_1' and meine and not meine_aktiven:
                raise AuctionError('Hier gilt: genau ein Gebot pro Manager.')
        else:
            if limit_cfg == 'genau_1' and meine:
                raise AuctionError('Hier gilt: genau ein Gebot pro Manager.')
            if isinstance(limit_cfg, dict) and len(meine) >= int(limit_cfg['max']):
                raise AuctionError(f'Maximal {int(limit_cfg["max"])} Gebote pro Manager.')

        # 3) Betrag (Achse 1/8/9)
        if richtung == 'aufsteigend':
            top = (a.bids.filter(is_active=True)
                   .order_by('-amount', 'created_at').first())
            if top is None:
                min_required = a.start_price or Decimal('1')
            else:
                min_required = top.amount + pricing.min_increment(config, top.amount)
                if a.start_price:
                    min_required = max(min_required, a.start_price)
            if amount < min_required:
                raise AuctionError(f'Gebot zu niedrig — mindestens {fmt_eur(min_required)}.')
        else:  # verdeckt
            if a.start_price and amount < a.start_price:
                raise AuctionError(f'Das Mindestgebot beträgt {fmt_eur(a.start_price)}.')

        # 4) Kaderplatz inkl. Reservierungen (Spec §8.1 Schritt 5)
        own_ref = (meine_aktiven[0].reservation_ref
                   if (is_change and meine_aktiven and meine_aktiven[0].reservation_ref)
                   else None)
        if _freie_kaderplaetze(club, exclude_ref=own_ref) < 1:
            raise AuctionError('Kein freier Kaderplatz — Limit erreicht (inkl. Reservierungen).')

        # 5) Deckung inkl. Reservierungen (Spec §8.1 Schritt 6)
        verfuegbar = _verfuegbares_budget(club, exclude_ref=own_ref)
        if amount > verfuegbar:
            raise AuctionError(
                f'Dein verfügbares Budget reicht nicht — frei: {fmt_eur(verfuegbar)}.'
            )

        # 6) Coin-Ticket (atomar mit dem ersten Gebot)
        coin_flag = _charge_coin_ticket(a, club, manager)

        # 7) Gebot schreiben + Reservierung
        freigabe = config['reservierungsfreigabe']
        if is_change:
            bid = meine_aktiven[0]
            bid.amount = amount
            if coin_flag:
                bid.coin_charged = True
            bid.save(update_fields=['amount', 'coin_charged', 'updated_at'])
            if bid.reservation_ref:
                reservations.adjust(bid.reservation_ref, betrag=amount)
            else:
                bid.reservation_ref = _bid_ref(bid)
                bid.save(update_fields=['reservation_ref', 'updated_at'])
                reservations.reserve(
                    club, referenz=bid.reservation_ref,
                    zweck=RESERVIERUNGS_ZWECK, betrag=amount, slots=1,
                )
        else:
            bid = ShowAuctionBid.objects.create(
                auction=a, club=club, manager=manager, amount=amount,
                is_active=True, coin_charged=coin_flag,
            )
            bid.reservation_ref = _bid_ref(bid)
            bid.save(update_fields=['reservation_ref', 'updated_at'])
            reservations.reserve(
                club, referenz=bid.reservation_ref,
                zweck=RESERVIERUNGS_ZWECK, betrag=amount, slots=1,
            )

        # 8) Überbietung: alten Leader freigeben + benachrichtigen (aufsteigend)
        if richtung == 'aufsteigend':
            prev = (a.bids.filter(is_leading=True).exclude(pk=bid.pk)
                    .select_related('club').first())
            if prev is not None:
                prev.is_leading = False
                prev.save(update_fields=['is_leading', 'updated_at'])
                if freigabe == 'bei_ueberbietung' and prev.reservation_ref:
                    reservations.release(prev.reservation_ref)
                zeig_betrag = config['sichtbarkeit'] in (
                    'hoechstgebot_und_bieter', 'nur_hoechstgebot',
                )
                notify_club(
                    prev.club,
                    f'Überboten: {a.player.full_name}',
                    body=(f'Neues Höchstgebot: {fmt_eur(amount)}.'
                          if zeig_betrag else 'Es gibt ein neues Höchstgebot.'),
                    url=_detail_url(a),
                )
            bid.is_leading = True
            bid.save(update_fields=['is_leading', 'updated_at'])

        # 9) Beobachtung (Quelle: Gebot)
        ShowAuctionWatch.objects.get_or_create(
            auction=a, club=club,
            defaults={'source': ShowAuctionWatch.SOURCE_BID},
        )

        # 10) Zeitsteuerung: Haltezeit-Treppe bzw. Deadline-Verlängerung
        if config['endebedingung'] == 'haltezeit':
            total = a.bids.filter(is_active=True).count()
            stunden = pricing.hold_duration_hours(config, total)
            a.hold_step_index = pricing.hold_step_number(config, total)
            a.ends_at = _cap_by_max(config, a.starts_at, now + timedelta(hours=stunden))
            a.save(update_fields=['hold_step_index', 'ends_at', 'updated_at'])
        elif (config['endebedingung'] == 'deadline'
              and config.get('verlaengerung', 'aus') != 'aus' and a.ends_at):
            v = config['verlaengerung']
            if (a.ends_at - now) <= timedelta(minutes=int(v['fenster'])):
                a.ends_at = _cap_by_max(
                    config, a.starts_at,
                    a.ends_at + timedelta(minutes=int(v['minuten'])),
                )
                a.extension_count += 1
                a.save(update_fields=['ends_at', 'extension_count', 'updated_at'])

    return bid


def buy_now(auction_id, club, manager, now=None):
    """Sofort-Zuschlag (fallend/fest): Preis ist SERVERSEITIG berechnet."""
    now = now or timezone.now()
    with transaction.atomic():
        try:
            a = (ShowAuction.objects.select_for_update()
                 .select_related('player').get(pk=auction_id))
        except ShowAuction.DoesNotExist:
            raise AuctionError('Diese Auktion existiert nicht (mehr).')
        _lazy_transition(a, now)
        if a.status != ShowAuction.STATUS_RUNNING:
            raise AuctionError('Diese Auktion läuft nicht (mehr).')
        config = a.cfg
        if config['gebotsrichtung'] not in ('fallend', 'fest'):
            raise AuctionError('Diese Auktion hat keinen Sofort-Zuschlag.')

        club = Club.objects.select_for_update().get(pk=club.pk)
        grund = check_participation(a, club, manager)
        if grund:
            raise AuctionError(grund)
        if _freie_kaderplaetze(club) < 1:
            raise AuctionError('Kein freier Kaderplatz — Limit erreicht (inkl. Reservierungen).')

        if config['gebotsrichtung'] == 'fallend':
            preis = pricing.dutch_price(
                config, a.start_price, a.market_value_snapshot, a.starts_at, now,
            )
        else:
            if a.start_price is None:
                raise AuctionError('Kein Festpreis hinterlegt.')
            preis = a.start_price

        verfuegbar = _verfuegbares_budget(club)
        if preis > verfuegbar:
            raise AuctionError(
                f'Dein verfügbares Budget deckt den Preis nicht — frei: {fmt_eur(verfuegbar)}.'
            )

        coin_flag = _charge_coin_ticket(a, club, manager)
        bid = ShowAuctionBid.objects.create(
            auction=a, club=club, manager=manager, amount=preis,
            is_active=True, is_leading=True, coin_charged=coin_flag,
        )
        ShowAuctionWatch.objects.get_or_create(
            auction=a, club=club,
            defaults={'source': ShowAuctionWatch.SOURCE_BID},
        )
        return _settle(a, now, winner_bid=bid, price=preis)


# ── Abwicklung (Spec §7.1/§7.2 — Zuschlag, Platzen) ──────────────────────────

def _vickrey_price(auction, config, bids, winner):
    andere = [b.amount for b in bids if b.pk != winner.pk]
    basis = max(andere) if andere else (auction.start_price or winner.amount)
    preis = basis + pricing.min_increment(config, basis)
    return min(preis, winner.amount)


def _settle(auction, now, winner_bid=None, price=None):
    """Zuschlag: Gewinner → Preis → Buchung → Transfer → Aufräumen.

    Läuft IMMER unter der Auktions-Sperre des Aufrufers. Idempotenz:
    Status-Guard (Zeile gesperrt) + UniqueConstraint auf der Buchung.

    Lock-Reihenfolge (Konvention der Transfer-Engine): Auktion (Aufrufer)
    → Gewinner-Club (in book()) → Spielerzeile. Kein Deadlock-Zyklus:
    alle Gebots-/Abwicklungspfade serialisieren an der Auktionszeile, und
    der Spieler ist im Raum (pool_status=show_auction) für Transfer- und
    Scouting-Pfade unsichtbar. Kaderplatz braucht hier keinen Re-Check:
    die Slot+Geld-Reservierung des Führenden bleibt bis consume() aktiv
    und zählt in _check_kaderplatz aller Normaltransfers mit.
    """
    from game.finance import current_sim_season

    config = auction.cfg
    bids = list(auction.bids.filter(is_active=True).select_related('club'))

    if winner_bid is None:
        if not bids:
            return _fail(auction, now, 'Kein Gebot eingegangen.')
        gw = config['gewinnerermittlung']
        if gw == 'naechstliegend_verborgenes_ziel':
            target = auction.hidden_target
            width = auction.hidden_width or Decimal('0')
            lo, hi = target - width / 2, target + width / 2
            kandidaten = [b for b in bids if lo <= b.amount <= hi]
            if not kandidaten:
                return _fail(auction, now, 'Kein Gebot traf den verborgenen Zielbereich.')
            best = min(abs(b.amount - target) for b in kandidaten)
            pool = [b for b in kandidaten if abs(b.amount - target) == best]
            winner_bid = _rng.choice(pool)  # Gleichstand → Los (Spec §7.2)
            price = winner_bid.amount
        else:
            top = max(b.amount for b in bids)
            pool = [b for b in bids if b.amount == top]
            winner_bid = _rng.choice(pool)  # Gleichstand → Los
            if config['zuschlagspreis'] == 'zweithoechstes_plus_erhoehung':
                price = _vickrey_price(auction, config, bids, winner_bid)
            else:
                price = winner_bid.amount

    price = Decimal(str(price)).quantize(Decimal('0.01'))
    winner_club = winner_bid.club
    sofort = config['reservierungsfreigabe'] == 'sofortige_buchung'

    # Buchung — Senke AUKTION (Geld wird vernichtet, Spec §7.1).
    # Reservierte Pfade buchen als Pflicht (Deckung war reserviert und darf
    # durch zwischenzeitliche Pflichtausgaben nicht mehr scheitern);
    # Sofortkauf prüft die Deckung live.
    try:
        book(
            winner_club, 'AUKTION', -price,
            beschreibung=f'Show-Auktion Zuschlag: {auction.player.full_name}',
            referenz_typ='showauction_settle', referenz_id=auction.pk,
            referenz_mw=auction.market_value_snapshot,
            pflicht=not sofort,
        )
    except InsufficientFunds:
        raise AuctionError('Dein Konto deckt den Preis nicht mehr.')
    except IntegrityError:
        raise AuctionError('Diese Auktion wurde bereits abgewickelt.')

    # Reservierungen: Gewinner verbrauchen, alle übrigen freigeben (E21)
    for b in auction.bids.exclude(reservation_ref=''):
        if b.pk == winner_bid.pk:
            reservations.consume(b.reservation_ref)
        else:
            reservations.release(b.reservation_ref)

    # Spieler → Gewinnerverein: regulärer Wechsel, Vereinsstation über das
    # save-Signal, KEINE Ausbildungsabgabe, 21 Tage Wechselsperre (§7.1).
    p = Player.objects.select_for_update().get(pk=auction.player_id)
    p.club = winner_club
    p.pool_status = Player.POOL_STATUS_NONE
    p.transfer_locked_until = timezone.localdate() + timedelta(days=WECHSELSPERRE_TAGE)
    update_fields = ['club', 'pool_status', 'transfer_locked_until']
    if p.market_value:
        p.salary_per_match = (
            Decimal(str(p.market_value)) / Decimal('1000000')
        ) * Decimal('5000')
        update_fields.append('salary_per_match')
    p.save(update_fields=update_fields)

    PlayerTransferHistory.objects.create(
        player=p,
        transfer_date=timezone.localdate(),
        season=str(current_sim_season() or ''),
        from_club=None,
        to_club=winner_club,
        fee_eur=price,
        notes=f'Show-Auktion ({auction.type_name})',
    )

    auction.status = ShowAuction.STATUS_SETTLED
    auction.winner_club = winner_club
    auction.winning_amount = price
    auction.settled_at = now
    if not auction.ends_at or auction.ends_at > now:
        auction.ends_at = now
    auction.save(update_fields=[
        'status', 'winner_club', 'winning_amount', 'settled_at', 'ends_at',
        'updated_at',
    ])

    url = _detail_url(auction)
    notify_club(
        winner_club, f'Zuschlag: {p.full_name} gehört dir!',
        body=f'Zuschlagspreis {fmt_eur(price)} — {auction.type_name}.',
        url=url,
    )
    _notify_watchers(
        auction, f'Auktion beendet: {p.full_name}',
        body=f'Zuschlag für {fmt_eur(price)} an {winner_club.name}.',
        url=url, exclude_club_ids={winner_club.pk},
    )
    return auction


def _fail(auction, now, grund):
    """Platzen: Reservierungen freigeben, Spieler zurück, Beobachter informieren."""
    for b in auction.bids.exclude(reservation_ref=''):
        reservations.release(b.reservation_ref)
    p = Player.objects.select_for_update().get(pk=auction.player_id)
    if p.pool_status == Player.POOL_STATUS_SHOW_AUCTION:
        p.pool_status = auction.player_prev_pool_status or Player.POOL_STATUS_NONE
        p.save(update_fields=['pool_status'])
    auction.status = ShowAuction.STATUS_FAILED
    auction.fail_reason = grund[:200]
    if not auction.ends_at or auction.ends_at > now:
        auction.ends_at = now
    auction.save(update_fields=['status', 'fail_reason', 'ends_at', 'updated_at'])
    _notify_watchers(
        auction, f'Auktion geplatzt: {auction.player.full_name}',
        body=grund, url=_detail_url(auction),
    )
    return auction


# ── Beat + Lazy (E26): fällige Auktionen abwickeln ───────────────────────────

def resolve_due(now=None):
    """Für Beat (showauction_tick) UND Lazy-Aufruf aus den Views.

    Jede Auktion läuft in ihrer eigenen Transaktion — eine defekte Auktion
    blockiert nie den Rest des Laufs.
    """
    now = now or timezone.now()
    stats = {'gestartet': 0, 'zugeschlagen': 0, 'geplatzt': 0,
             'endspurt': 0, 'fehler': 0}

    start_ids = list(
        ShowAuction.objects
        .filter(status=ShowAuction.STATUS_SCHEDULED, starts_at__lte=now)
        .values_list('pk', flat=True)
    )
    for pk in start_ids:
        try:
            with transaction.atomic():
                a = (ShowAuction.objects.select_for_update()
                     .select_related('player').get(pk=pk))
                if (a.status == ShowAuction.STATUS_SCHEDULED
                        and a.starts_at and a.starts_at <= now):
                    _start(a, now)
                    stats['gestartet'] += 1
        except Exception:
            logger.exception('Show-Auktion %s: Start fehlgeschlagen', pk)
            stats['fehler'] += 1

    endspurt_ids = list(
        ShowAuction.objects
        .filter(status=ShowAuction.STATUS_RUNNING, endspurt_notified=False,
                ends_at__gt=now, ends_at__lte=now + timedelta(hours=1))
        .values_list('pk', flat=True)
    )
    for pk in endspurt_ids:
        try:
            with transaction.atomic():
                a = (ShowAuction.objects.select_for_update()
                     .select_related('player').get(pk=pk))
                if (a.status == ShowAuction.STATUS_RUNNING
                        and not a.endspurt_notified and a.ends_at
                        and now < a.ends_at <= now + timedelta(hours=1)):
                    a.endspurt_notified = True
                    a.save(update_fields=['endspurt_notified', 'updated_at'])
                    _notify_watchers(
                        a, f'Endspurt: {a.player.full_name}',
                        body='Weniger als eine Stunde Restzeit!',
                        url=_detail_url(a),
                    )
                    stats['endspurt'] += 1
        except Exception:
            logger.exception('Show-Auktion %s: Endspurt-Meldung fehlgeschlagen', pk)
            stats['fehler'] += 1

    due_ids = list(
        ShowAuction.objects
        .filter(status=ShowAuction.STATUS_RUNNING, ends_at__lte=now)
        .values_list('pk', flat=True)
    )
    for pk in due_ids:
        try:
            with transaction.atomic():
                a = (ShowAuction.objects.select_for_update()
                     .select_related('player').get(pk=pk))
                if (a.status == ShowAuction.STATUS_RUNNING
                        and a.ends_at and a.ends_at <= now):
                    _finish_due(a, now)
                    if a.status == ShowAuction.STATUS_SETTLED:
                        stats['zugeschlagen'] += 1
                    elif a.status == ShowAuction.STATUS_FAILED:
                        stats['geplatzt'] += 1
        except Exception:
            logger.exception('Show-Auktion %s: Abwicklung fehlgeschlagen', pk)
            stats['fehler'] += 1

    return stats


# ── Beobachten & Benachrichtigen ─────────────────────────────────────────────

def toggle_watch(auction, club):
    """Beobachtung an/aus — liefert neuen Zustand (True = beobachtet)."""
    if club is None:
        raise AuctionError('Du brauchst einen Verein, um Auktionen zu beobachten.')
    existing = ShowAuctionWatch.objects.filter(auction=auction, club=club).first()
    if existing is not None:
        existing.delete()
        return False
    ShowAuctionWatch.objects.create(
        auction=auction, club=club, source=ShowAuctionWatch.SOURCE_MANUAL,
    )
    return True


def _notify_watchers(auction, title, body='', url='', exclude_club_ids=()):
    for watch in auction.watches.select_related('club'):
        if watch.club_id in exclude_club_ids:
            continue
        notify_club(watch.club, title, body=body, url=url)
