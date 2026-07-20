"""Zwangsversteigerung (Spec Kap. 12.3) — Admin-Ventil bei Zahlungsunfähigkeit.

Nach Fristablauf eines offenen Zahlungsunfähigkeits-Vermerks kann der Admin
ausgewählte Spieler des Schuldnervereins versteigern. Anders als reguläre
Auktionen (Scouting-Pool, Erlös vernichtet — Typ AUKTION) geht der Erlös
hier an den Verein: Das Settlement läuft über execute_money_transfer
(TRANSFER_AUS Käufer / TRANSFER_EIN Verein, Ausbildungsabgabe inklusive).

Gebote sind verdeckt (wie Scouting): höchstes Gebot gewinnt, bei Gleichstand
das früher abgegebene. Keine Budget-Reservierung beim Bieten — die Deckung
wird beim Zuschlag geprüft (aktive Ausgabe, Grundregel 2); scheitert der
Höchstbietende, rückt das nächsthöhere Gebot nach.

Phase 6 — KI-Vereine bieten mit (Spec Kap. 11):
  run_ki_zwangsversteigerungen() lässt KI-Vereine (managed_by IS NULL,
  ai_buyer_paused=False) plausible Gebote auf offene Auktionen abgeben.
  Kein Transferfenster-Gate (Zwangsversteigerungen sind Notverfahren).
  KI_KAEUFER.dry_run muss False sein — sonst keine Gebote.
"""
import datetime
import hashlib
import logging
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .booking import InsufficientFunds
from .kader import min_squad_size, squad_count
from .transfers import TransferError, execute_money_transfer

logger = logging.getLogger(__name__)

#: Laufzeit einer Zwangsversteigerung ab Ansetzung (echte Tage).
AUKTIONS_LAUFZEIT_TAGE = 7


class ForcedAuctionError(Exception):
    """Regelverstoß rund um Zwangsversteigerungen (deutsche Meldung)."""


def _today(today=None):
    return today or timezone.localdate()


def start_auction(case, player, min_bid, *, ends_on=None, today=None):
    """Setzt eine Zwangsversteigerung für einen Spieler des Schuldnervereins an.

    Voraussetzungen (Admin-Flow):
      - Vermerk offen/enforced, Frist abgelaufen, Konto weiterhin < 0
      - Spieler gehört dem Verein des Vermerks
      - Mindestkader bleibt gewahrt (laufende Auktionen eingerechnet)
    """
    from game.models import ForcedAuction, InsolvencyCase

    today = _today(today)
    min_bid = Decimal(str(min_bid)).quantize(Decimal('0.01'))
    if min_bid <= 0:
        raise ForcedAuctionError('Das Mindestgebot muss größer als 0 sein.')

    with transaction.atomic():
        case = InsolvencyCase.objects.select_for_update().get(pk=case.pk)
        if case.status not in (InsolvencyCase.STATUS_OPEN,
                               InsolvencyCase.STATUS_ENFORCED):
            raise ForcedAuctionError('Der Vermerk ist bereits bereinigt.')
        if timezone.now() < case.deadline_at:
            raise ForcedAuctionError(
                'Die 7-Tage-Frist läuft noch — Zwangsversteigerung erst '
                'nach Fristablauf möglich.'
            )

        club = case.club
        club.refresh_from_db(fields=['budget'])
        if club.budget is not None and club.budget >= 0:
            raise ForcedAuctionError(
                'Das Konto ist nicht mehr im Minus — keine '
                'Zwangsversteigerung nötig.'
            )
        if player.club_id != case.club_id:
            raise ForcedAuctionError(
                'Der Spieler gehört nicht dem Verein des Vermerks.'
            )
        offene = ForcedAuction.objects.filter(
            seller_club_id=case.club_id, status=ForcedAuction.STATUS_OPEN,
        ).count()
        if squad_count(club) - offene - 1 < min_squad_size():
            raise ForcedAuctionError(
                'Mindestkader würde unterschritten — dieser Spieler kann '
                'nicht zusätzlich versteigert werden.'
            )
        if ForcedAuction.objects.filter(
            player=player, status=ForcedAuction.STATUS_OPEN,
        ).exists():
            raise ForcedAuctionError(
                'Für diesen Spieler läuft bereits eine Zwangsversteigerung.'
            )

        auction = ForcedAuction.objects.create(
            case=case,
            player=player,
            seller_club_id=case.club_id,
            min_bid=min_bid,
            ends_on=ends_on or (today + datetime.timedelta(
                days=AUKTIONS_LAUFZEIT_TAGE)),
        )
        if case.status != InsolvencyCase.STATUS_ENFORCED:
            case.status = InsolvencyCase.STATUS_ENFORCED
            case.enforced_at = timezone.now()
            case.save(update_fields=['status', 'enforced_at'])
    return auction


def place_bid(auction, club, manager, amount, *, today=None):
    """Verdecktes Gebot eines Vereins (Erhöhen = Update des eigenen Gebots).

    Beim Bieten wird der aktuelle Kontostand als Plausibilitätsprüfung
    herangezogen (Grundregel: keine aktiven Ausgaben ohne Deckung) — es
    wird aber NICHTS reserviert. Maßgeblich ist die erneute Deckungs-
    prüfung beim Zuschlag; scheitert sie dort, rückt das nächsthöhere
    Gebot nach (Kaskade in resolve_due_auctions).
    """
    from game.models import ForcedAuction, ForcedAuctionBid

    today = _today(today)
    amount = Decimal(str(amount)).quantize(Decimal('0.01'))

    with transaction.atomic():
        auction = ForcedAuction.objects.select_for_update().get(pk=auction.pk)
        if auction.status != ForcedAuction.STATUS_OPEN:
            raise ForcedAuctionError('Diese Zwangsversteigerung läuft nicht mehr.')
        if today > auction.ends_on:
            raise ForcedAuctionError('Der Zuschlagstermin ist bereits erreicht.')
        if club.pk == auction.seller_club_id:
            raise ForcedAuctionError('Der Schuldnerverein darf nicht mitbieten.')
        if amount < auction.min_bid:
            raise ForcedAuctionError(
                f'Das Gebot liegt unter dem Mindestgebot '
                f'({auction.min_bid:,.0f} €).'
            )
        club.refresh_from_db(fields=['budget'])
        verfuegbar = club.budget if club.budget is not None else Decimal('0.00')
        if amount > verfuegbar:
            raise ForcedAuctionError(
                'Dein Kontostand deckt dieses Gebot nicht (Grundregel: '
                'keine aktiven Ausgaben ohne Deckung).'
            )

        bid, created = ForcedAuctionBid.objects.update_or_create(
            auction=auction, club=club,
            defaults={'manager': manager, 'amount': amount},
        )
    return bid


def _ki_gebot_betrag(auction, wertung, club_budget, params):
    """KI-Gebot für eine Zwangsversteigerung: Schmerzgrenzen-Maximum,
    deterministisch variiert (±streuung), quantisiert, geclampt.

    Returns das Gebot als Decimal oder None wenn Gebot < min_bid.
    """
    from .ai_buyer.offers import max_gebot_fuer
    from .negotiation import _quantisiere

    max_ki = max_gebot_fuer('bedarf', wertung, params)
    if max_ki <= 0:
        return None

    schritt = Decimal(str(params.get('gebot_quantisierung', 10000)))
    streuung = Decimal(str(params.get('streuung', 0.05)))

    noise_seed = f'{club_budget}:{auction.pk}'
    digest = hashlib.sha256(noise_seed.encode()).hexdigest()
    anteil = Decimal(int(digest[:8], 16)) / Decimal('4294967295')
    faktor = Decimal('1') - streuung + anteil * 2 * streuung

    verfuegbar = Decimal(str(club_budget))
    gebot_raw = min(max_ki, verfuegbar) * faktor
    gebot = _quantisiere(gebot_raw, schritt)
    gebot = min(gebot, verfuegbar)

    if gebot < auction.min_bid:
        if schritt > 0:
            gebot_aufgerundet = (
                (auction.min_bid / schritt).to_integral_value(
                    rounding='ROUND_CEILING',
                ) * schritt
            )
        else:
            gebot_aufgerundet = auction.min_bid
        gebot = min(gebot_aufgerundet, verfuegbar)

    if gebot < auction.min_bid:
        return None

    return gebot


def run_ki_zwangsversteigerungen(today=None, saison=None):
    """KI-Vereine geben Gebote auf offene Zwangsversteigerungen ab (Phase 6).

    Aufruf täglich vom resolve_forced_auctions-Command — VOR der Auflösung,
    damit KI-Gebote beim Zuschlag berücksichtigt werden. Läuft unabhängig
    davon, ob heute Auktionen fällig sind (offene Auktionen erhalten Gebote).

    Kein Transferfenster-Gate: Zwangsversteigerungen sind admin-initiierte
    Notverfahren, die außerhalb des regulären Marktzyklus stattfinden.
    KI_KAEUFER.dry_run=True → keine Gebote (Sicherheitsnetz).

    Bedarfs-Gate: KI-Vereine bieten nur, wenn sie einen akuten Kader-Bedarf
    haben (bedarfs_analyse.akut ≠ ∅ oder Kader zu klein für Beste-11).
    Positions-Check: Spieler muss eine der akuten Positionen abdecken können
    (Spieler ohne Positions-Codes = unvollständige Daten, keine Restriction).

    Returns dict: {'auktionen': int, 'gebote': int, 'uebersprungen': int,
                   'dry_run': bool}
    """
    from game.models import Club, ForcedAuction

    from .ai_buyer.bedarf import bedarfs_analyse, liga_soll
    from .ai_buyer.offers import max_gebot_fuer
    from .kader import effective_squad_limit
    from .params import get_param
    from .schmerzgrenze import bewertung
    from .snapshot import ensure_season_snapshot

    today = _today(today)
    if saison is None:
        from game.finance import current_sim_season
        saison = current_sim_season() or '0'

    params = get_param('KI_KAEUFER', saison)
    dry_run = bool(params.get('dry_run', True))

    summary = {
        'auktionen': 0, 'gebote': 0, 'uebersprungen': 0, 'dry_run': dry_run,
    }
    if dry_run:
        logger.info('KI-Zwangsversteigerung: dry_run=True — keine Gebote.')
        summary['letzter_lauf'] = timezone.now().isoformat()
        cache.set('ki_zv_last_summary', summary, timeout=60 * 60 * 24 * 7)
        return summary

    snapshot = ensure_season_snapshot(saison)

    offene_auktionen = list(
        ForcedAuction.objects
        .filter(status=ForcedAuction.STATUS_OPEN, ends_on__gte=today)
        .select_related(
            'player', 'seller_club',
            'player__strength_profile',
        )
        .prefetch_related('player__source_ratings')
    )

    ki_clubs = list(
        Club.objects
        .filter(managed_by__isnull=True, ai_buyer_paused=False)
        .select_related('stadium', 'league')
    )

    # Bedarfsanalyse je KI-Verein einmal vorberechnen (liga_soll je Liga cachen).
    # klub_bedarf[pk] = None   → Kader zu klein für Beste-11 (dringendster Bedarf)
    # klub_bedarf[pk] = set()  → kein akuter Bedarf (kein Gebot)
    # klub_bedarf[pk] = {codes} → akute Positions-Lücken
    liga_soll_cache: dict = {}
    klub_bedarf: dict = {}
    for club in ki_clubs:
        if club.league_id is None:
            klub_bedarf[club.pk] = set()
            continue
        if club.league_id not in liga_soll_cache:
            liga_soll_cache[club.league_id] = liga_soll(club.league)
        soll = liga_soll_cache[club.league_id]
        analyse = bedarfs_analyse(club, soll, params)
        if analyse['elf'] is None:
            klub_bedarf[club.pk] = None
        elif analyse['akut']:
            klub_bedarf[club.pk] = {p['position'] for p in analyse['akut']}
        else:
            klub_bedarf[club.pk] = set()

    for auction in offene_auktionen:
        summary['auktionen'] += 1
        player = auction.player

        wert = bewertung(player, saison=saison, snapshot=snapshot)
        if wert is None:
            logger.debug(
                'KI-ZV: Spieler %s (%d) ohne Bewertung — übersprungen.',
                player.full_name, player.pk,
            )
            summary['uebersprungen'] += 1
            continue

        if max_gebot_fuer('bedarf', wert, params) < auction.min_bid:
            logger.debug(
                'KI-ZV: Max-Gebot für %s unterschreitet Mindestgebot %s — '
                'übersprungen.', player.full_name, auction.min_bid,
            )
            summary['uebersprungen'] += 1
            continue

        player_codes = frozenset(player.all_position_codes)

        for club in ki_clubs:
            if club.pk == auction.seller_club_id:
                continue

            if squad_count(club) >= effective_squad_limit(club, saison):
                continue

            akut = klub_bedarf.get(club.pk)
            if akut is not None and not akut:
                continue
            if akut is not None and player_codes and not (akut & player_codes):
                continue

            club.refresh_from_db(fields=['budget'])
            verfuegbar = club.budget if club.budget is not None else Decimal('0')
            if verfuegbar <= 0:
                continue

            gebot = _ki_gebot_betrag(auction, wert, verfuegbar, params)
            if gebot is None:
                continue

            try:
                place_bid(auction, club, None, gebot, today=today)
                summary['gebote'] += 1
                logger.info(
                    'KI-ZV: %s bietet %s € auf %s.',
                    club.name, gebot, player.full_name,
                )
            except ForcedAuctionError as exc:
                logger.debug(
                    'KI-ZV: Gebot von %s auf %s abgelehnt: %s',
                    club.name, player.full_name, exc,
                )

    from django.utils import timezone as _tz
    summary['letzter_lauf'] = _tz.now().isoformat()
    cache.set('ki_zv_last_summary', summary, timeout=60 * 60 * 24 * 7)
    return summary


def resolve_due_auctions(today=None):
    """Wertet alle fälligen Zwangsversteigerungen aus.

    Wurde der Vermerk zwischenzeitlich bereinigt (Konto zurück auf ≥ 0),
    wird die Auktion ABGEBROCHEN statt zugeschlagen — die Zwangsvollstreckung
    ist der Hebel gegen anhaltende Zahlungsunfähigkeit, nicht gegen bereits
    bereinigte Fälle (Spec 12.3: Verkäufe sind der vorgesehene Weg zurück
    ins Plus). Sonst: höchstes Gebot gewinnt (Gleichstand: früher
    abgegeben); scheitert der Zuschlag an Deckung/Kaderplatz, rückt das
    nächsthöhere Gebot nach. Ohne wertbares Gebot endet die Auktion als
    'unsold'.
    """
    from game.models import ClubNewsItem, ForcedAuction, InsolvencyCase

    today = _today(today)
    summary = {'auctions': 0, 'settled': 0, 'unsold': 0, 'cancelled': 0}

    due_ids = list(
        ForcedAuction.objects
        .filter(status=ForcedAuction.STATUS_OPEN, ends_on__lte=today)
        .values_list('pk', flat=True)
    )
    for auction_id in due_ids:
        summary['auctions'] += 1
        with transaction.atomic():
            auction = (
                ForcedAuction.objects
                .select_for_update()
                .select_related('player', 'seller_club', 'case')
                .get(pk=auction_id)
            )
            if auction.status != ForcedAuction.STATUS_OPEN:
                continue

            player = auction.player

            # Vermerk bereinigt oder Konto wieder ≥ 0 → Abbruch statt Zuschlag.
            seller = auction.seller_club
            seller.refresh_from_db(fields=['budget'])
            case_bereinigt = (
                auction.case_id is not None
                and auction.case.status == InsolvencyCase.STATUS_RESOLVED
            )
            if case_bereinigt or (seller.budget is not None
                                  and seller.budget >= 0):
                auction.status = ForcedAuction.STATUS_CANCELLED
                auction.settled_on = today
                auction.save(update_fields=['status', 'settled_on'])
                summary['cancelled'] += 1
                ClubNewsItem.objects.create(
                    club_id=auction.seller_club_id,
                    title=(f'Zwangsversteigerung abgebrochen: Konto '
                           f'bereinigt — {player.full_name} bleibt im '
                           f'Kader')[:160],
                    published_at=today,
                )
                continue
            winner_bid = None
            if player.club_id == auction.seller_club_id:
                bids = list(
                    auction.bids.select_related('club')
                    .order_by('-amount', 'created_at')
                )
                for bid in bids:
                    try:
                        execute_money_transfer(
                            player, bid.club, bid.amount,
                        )
                    except (TransferError, InsufficientFunds):
                        continue
                    winner_bid = bid
                    break

            if winner_bid is not None:
                auction.status = ForcedAuction.STATUS_SETTLED
                auction.winning_bid = winner_bid
                auction.settled_on = today
                auction.save(update_fields=['status', 'winning_bid', 'settled_on'])
                summary['settled'] += 1
                betrag = f'{winner_bid.amount:,.0f}'.replace(',', '.')
                ClubNewsItem.objects.create(
                    club_id=auction.seller_club_id,
                    title=(f'Zwangsversteigerung: {player.full_name} für '
                           f'{betrag} € an {winner_bid.club.name}')[:160],
                    published_at=today,
                )
                ClubNewsItem.objects.create(
                    club_id=winner_bid.club_id,
                    title=(f'Zuschlag: {player.full_name} für {betrag} € '
                           f'aus Zwangsversteigerung verpflichtet')[:160],
                    published_at=today,
                )
            else:
                auction.status = ForcedAuction.STATUS_UNSOLD
                auction.settled_on = today
                auction.save(update_fields=['status', 'settled_on'])
                summary['unsold'] += 1
                if player.club_id == auction.seller_club_id:
                    titel = (f'Zwangsversteigerung ohne Zuschlag: '
                             f'{player.full_name} bleibt im Kader')
                else:
                    titel = (f'Zwangsversteigerung aufgehoben: '
                             f'{player.full_name} hat den Verein bereits '
                             f'verlassen')
                ClubNewsItem.objects.create(
                    club_id=auction.seller_club_id,
                    title=titel[:160],
                    published_at=today,
                )
    return summary
