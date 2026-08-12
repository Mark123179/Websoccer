"""Zustandsautomaten & Aktionen des Transfersystems v2 (Master-Spec §4.2/§4.3/§5).

Service-Schicht über den Modellen. Jede geldbewegende Aktion läuft in EINER
DB-Transaktion mit select_for_update() auf Listing/Deal UND den beteiligten
Club-Zeilen (Race-Safety, Master-Spec §6). Kein Auto-Bieten.

Öffentliche Aktionen:
    create_listing / place_bid / buy_now / hammer / withdraw_listing
    close_listing (Auktionsabschluss-Task, idempotent)
    create_deal_request / accept_deal / decline_deal / withdraw_deal
    create_loan_listing / request_loan / accept_loan_request
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from game.economy.booking import InsufficientFunds
from game.economy.params import get_decimal, get_param

from . import escrow, execution
from .calendar_dates import loan_market_paused
from .models import (
    ClubPartnership, DealRequest, DealRequestPlayer, Loan, LoanListing,
    PendingTransfer, TransferBid, TransferListing, TransferRecord,
)

CENT = Decimal('0.01')
ZERO = Decimal('0.00')


class TransferActionError(Exception):
    """Fachlicher Fehler (deutsche Meldung für die UI)."""


def _q(v):
    return Decimal(str(v)).quantize(CENT)


# ── Gebots-Arithmetik ─────────────────────────────────────────────────────

def min_increment(highest, saison=None):
    """Mindesterhöhung = max(100.000 €, 5 %), gerundet auf 50.000 €."""
    abs_min = get_decimal('TRANSFER_MIN_ERHOEHUNG_ABS', saison)
    pct = get_decimal('TRANSFER_MIN_ERHOEHUNG_PCT', saison)
    step = get_decimal('TRANSFER_ERHOEHUNG_RUNDUNG', saison)
    roh = max(abs_min, _q(Decimal(str(highest)) * pct))
    # Aufrunden auf das nächste step-Vielfache.
    gerundet = (roh / step).to_integral_value(rounding=ROUND_HALF_UP) * step
    if gerundet < roh:
        gerundet += step
    return _q(gerundet)


def min_next_bid(listing, saison=None):
    """Kleinstes zulässiges nächstes Gebot auf ein Listing."""
    leading = listing.bids.filter(is_leading=True).first()
    if leading is None:
        return _q(listing.min_bid)
    return _q(leading.amount + min_increment(leading.amount, saison))


# ── Listing anlegen ───────────────────────────────────────────────────────

def create_listing(player, seller, *, min_bid, buy_now=None, timing='SOFORT',
                   duration_days=None, saison=None):
    """Erstellt ein Listing; erzwingt das 500.000-€-Systemminimum.

    Vereinslos: seller=None → min_bid = aktueller MW, duration_days=None,
    ends_at bleibt NULL bis zum ersten Gebot.
    """
    from game.models import Player

    min_system = get_decimal('TRANSFER_MIN_GEBOT', saison)
    is_free_agent = seller is None

    with transaction.atomic():
        # Eigentums-Validierung unter Zeilen-Lock: Vereins-Listings nur für
        # eigene Spieler, Vereinslosen-Listings nur für tatsächlich
        # vereinslose Spieler (sonst würde execute_purchase den
        # Eigentums-Check des "Free-Agent"-Pfads umgehen).
        player = Player.objects.select_for_update().get(pk=player.pk)
        if is_free_agent:
            if player.club_id is not None:
                raise TransferActionError(
                    'Vereinslosen-Listing nur für vereinslose Spieler.')
        elif player.club_id != seller.pk:
            raise TransferActionError(
                f'{player.full_name} gehört nicht {seller.name}.')
        if player.is_transfer_locked:
            raise TransferActionError('Spieler ist wechselgesperrt.')
        # Leihspieler dürfen NICHT gelistet werden — der aufnehmende Verein
        # ist zwar player.club, aber nicht Eigentümer.
        if player.loan_status in ('loaned_in', 'loaned_out') or (
                Loan.objects.filter(
                    player=player, ended_at__isnull=True).exists()):
            raise TransferActionError(
                f'{player.full_name} ist verliehen und kann nicht '
                'gelistet werden.')
        if TransferListing.objects.filter(
                player=player,
                status=TransferListing.STATUS_ACTIVE).exists():
            raise TransferActionError('Spieler ist bereits gelistet.')
        if PendingTransfer.objects.filter(
                player=player,
                status=PendingTransfer.STATUS_PENDING).exists():
            raise TransferActionError(
                'Spieler hat bereits einen ausstehenden Transfer.')
        if not is_free_agent:
            # Mindestkader: Abgabe darf den Verkäufer nicht darunter drücken.
            _check_squad_bounds(seller, raus=1, saison=saison)

        if timing not in (TransferListing.TIMING_SOFORT,
                          TransferListing.TIMING_WP,
                          TransferListing.TIMING_SE):
            raise TransferActionError('Ungültiges Timing (SOFORT/WP/SE).')

        if is_free_agent:
            mw = Decimal(str(player.market_value or 0))
            min_bid = mw if mw > 0 else min_system
            ends_at = None
            duration_days = None
        else:
            min_bid = _q(min_bid)
            if min_bid < min_system:
                raise TransferActionError(
                    f'Mindestgebot muss mindestens {min_system:,.0f} € betragen.'
                )
            if duration_days not in (1, 2, 3, 5, 7):
                raise TransferActionError('Ungültige Laufzeit (1/2/3/5/7 Tage).')
            ends_at = timezone.now() + timezone.timedelta(days=duration_days)

        # Sofortkauf-Preis hart validieren: er wird bei buy_now() direkt
        # gebucht — 0/negativ wäre ein Gratis- bzw. Umkehr-Transfer.
        if buy_now is not None:
            buy_now = _q(buy_now)
            if buy_now <= 0:
                raise TransferActionError(
                    'Sofortkauf-Preis muss positiv sein.')
            if buy_now < _q(min_bid):
                raise TransferActionError(
                    'Sofortkauf-Preis darf das Mindestgebot nicht '
                    'unterschreiten.')

        listing = TransferListing.objects.create(
            player=player, seller=seller, min_bid=_q(min_bid),
            buy_now=buy_now,
            timing=timing, duration_days=duration_days,
            listed_at=timezone.now(), ends_at=ends_at,
            status=TransferListing.STATUS_ACTIVE,
        )
    return listing


# ── Gebot ─────────────────────────────────────────────────────────────────

def place_bid(listing, club, amount, *, saison=None):
    """Gibt ein bindendes Gebot ab (Escrow + Anti-Sniping + Race-Safety)."""
    from game.models import Club

    amount = _q(amount)
    with transaction.atomic():
        listing = (TransferListing.objects.select_for_update()
                   .get(pk=listing.pk))
        if listing.status != TransferListing.STATUS_ACTIVE:
            raise TransferActionError('Auktion soeben beendet.')
        if listing.seller_id == club.pk:
            raise TransferActionError('Auf eigene Listings kann nicht geboten werden.')

        now = timezone.now()
        # Vereinslose: ends_at beim 1. Gebot setzen.
        first_bid = listing.ends_at is None
        if listing.ends_at is not None and listing.ends_at <= now:
            raise TransferActionError('Auktion soeben beendet.')

        mindest = min_next_bid(listing, saison)
        if amount < mindest:
            raise TransferActionError(
                f'Gebot zu niedrig — mindestens {mindest:,.0f} €.'
            )

        bidder = Club.objects.select_for_update().get(pk=club.pk)
        # Eigene bestehende Reservierung auf DIESES Listing (Selbst-Überbieten
        # des Führenden) darf nicht doppelt gegen die Deckung zählen.
        if escrow.available(
                bidder,
                exclude_referenz=escrow.bid_ref(listing.pk, bidder.pk),
        ) < amount:
            raise TransferActionError('Nicht genügend verfügbares Budget.')

        # Vorheriges führendes Gebot entthronen + dessen Reservierung freigeben.
        prev = listing.bids.filter(is_leading=True).select_related('club').first()
        prev_club = None
        if prev is not None:
            prev.is_leading = False
            prev.save(update_fields=['is_leading'])
            prev_club = Club.objects.select_for_update().get(pk=prev.club_id)

        bid = TransferBid.objects.create(
            listing=listing, club=bidder, amount=amount, is_leading=True,
        )
        # Escrow: neuen Bieter reservieren, Vor-Bieter freigeben.
        # (Überbietet sich der Führende selbst, aktualisiert reserve die Zeile.)
        escrow.reserve_money(bidder, escrow.bid_ref(listing.pk, bidder.pk), amount)
        if prev_club is not None and prev_club.pk != bidder.pk:
            escrow.release_money(prev_club, escrow.bid_ref(listing.pk, prev_club.pk))

        # Anti-Sniping: Gebot < 60 min vor Ende → +24 h.
        if first_bid:
            hours = int(get_param('TRANSFER_FREE_AGENT_STUNDEN', saison))
            listing.ends_at = now + timezone.timedelta(hours=hours)
        else:
            fenster = int(get_param('TRANSFER_ANTISNIPING_FENSTER_MIN', saison))
            verl = int(get_param('TRANSFER_ANTISNIPING_VERLAENGERUNG_H', saison))
            if (listing.ends_at - now) < timezone.timedelta(minutes=fenster):
                listing.ends_at = listing.ends_at + timezone.timedelta(hours=verl)
                listing.extensions += 1
        listing.save(update_fields=['ends_at', 'extensions'])

        # Sofortkauf ersetzt: Höchstgebot ≥ Sofortkaufpreis.
        if listing.buy_now is not None and amount >= listing.buy_now:
            listing.buy_now = None
            listing.save(update_fields=['buy_now'])
    return bid


def _release_all_bidder_reservations(listing, *, skip_club_id=None):
    """Gibt die Gebots-Reservierungen aller Bieter des Listings frei.

    skip_club_id: Gewinner überspringen (dessen Reservierung wurde bereits
    per consume in die Buchung überführt). release() ist auf bereits
    freigegebene/verbrauchte Referenzen no-op → idempotent.
    """
    from game.models import Club
    bidder_ids = set(listing.bids.values_list('club_id', flat=True))
    for cid in sorted(bidder_ids):
        if cid == skip_club_id:
            continue
        c = Club.objects.select_for_update().get(pk=cid)
        escrow.release_money(c, escrow.bid_ref(listing.pk, cid))


# ── Sofortkauf ────────────────────────────────────────────────────────────

def buy_now(listing, buyer, *, saison=None, spieltag=None):
    """Sofortkauf (Master-Spec §3): Direktabbuchung, Auktion sofort SOLD."""
    from game.models import Club

    with transaction.atomic():
        listing = TransferListing.objects.select_for_update().get(pk=listing.pk)
        if listing.status != TransferListing.STATUS_ACTIVE:
            raise TransferActionError('Auktion soeben beendet.')
        if listing.ends_at is not None and timezone.now() >= listing.ends_at:
            # Abgelaufen, aber vom Minuten-Job noch nicht geschlossen —
            # Sofortkauf darf das Fenster nicht ausnutzen (wie place_bid).
            raise TransferActionError('Auktion ist bereits abgelaufen.')
        if listing.buy_now is None:
            raise TransferActionError('Kein Sofortkauf verfügbar.')
        if listing.seller_id == buyer.pk:
            raise TransferActionError('Eigenes Listing.')

        amount = _q(listing.buy_now)
        buyer_locked = Club.objects.select_for_update().get(pk=buyer.pk)
        # Deckungsprüfung gegen Verfügbar (Kontostand − Reserviert), KEINE
        # eigene Reservierungsphase (§3). Führt der Käufer selbst das
        # Höchstgebot auf DIESEM Listing, zählt dessen Reservierung nicht
        # doppelt — sie wird vor der Buchung freigegeben.
        eigene_ref = escrow.bid_ref(listing.pk, buyer_locked.pk)
        if escrow.available(
                buyer_locked, exclude_referenz=eigene_ref) < amount:
            raise TransferActionError('Nicht genügend verfügbares Budget.')
        if escrow.reserved_for(eigene_ref) > 0:
            escrow.release_money(buyer_locked, eigene_ref)

        record = execution.execute_purchase(
            listing, buyer_locked, amount, timing=listing.timing,
            saison=saison, spieltag=spieltag,
        )
        _finish_listing(listing, TransferListing.STATUS_SOLD)
        _release_all_bidder_reservations(listing)
    return record


# ── Hammer (Verkäufer nimmt Höchstgebot an) ───────────────────────────────

def hammer(listing, *, saison=None, spieltag=None):
    """Verkäufer-Hammer: schließt jederzeit auf das Höchstgebot ab."""
    return close_listing(listing, saison=saison, spieltag=spieltag, force=True)


# ── Rückzug (nur bei 0 Geboten) ───────────────────────────────────────────

def withdraw_listing(listing):
    with transaction.atomic():
        listing = TransferListing.objects.select_for_update().get(pk=listing.pk)
        if listing.status != TransferListing.STATUS_ACTIVE:
            raise TransferActionError('Listing ist nicht mehr aktiv.')
        if listing.bids.exists():
            raise TransferActionError('Rückzug nur ohne Gebote möglich.')
        _finish_listing(listing, TransferListing.STATUS_CANCELLED)
    return listing


# ── Auktionsabschluss (idempotent, Task-Pfad) ─────────────────────────────

def close_listing(listing, *, saison=None, spieltag=None, force=False):
    """Schließt ein Listing idempotent ab.

    force=True (Hammer): jederzeit auf das aktuelle Höchstgebot.
    force=False (Task): nur wenn status=ACTIVE UND ends_at <= now.

    Settlement-Konflikt-Policy (deterministisch): Kann der Zuschlag am
    Abschlusszeitpunkt fachlich nicht vollzogen werden (z. B. Kaderlimit
    des Bieters voll, Verkäufer unter Mindestkader, Spieler inzwischen
    verliehen/weg), wird die Auktion EXPIRED, ALLE Gebots-Reservierungen
    werden freigegeben und beide Seiten benachrichtigt. Eine Auktion bleibt
    nie mit gebundenem Escrow hängen.
    """
    from game.models import Club

    with transaction.atomic():
        listing = TransferListing.objects.select_for_update().get(pk=listing.pk)
        if listing.status != TransferListing.STATUS_ACTIVE:
            return listing  # idempotent — schon abgeschlossen.

        now = timezone.now()
        if not force:
            if listing.ends_at is None or listing.ends_at > now:
                return listing  # noch nicht fällig.

        leading = (listing.bids.filter(is_leading=True)
                   .select_related('club').first())
        if leading is None:
            _finish_listing(listing, TransferListing.STATUS_EXPIRED)
            return listing

        buyer = Club.objects.select_for_update().get(pk=leading.club_id)
        amount = _q(leading.amount)
        try:
            # Settlement in eigenem Savepoint: schlägt der Vollzug fehl,
            # wird NUR er zurückgerollt — der Konflikt-Abschluss darunter
            # (EXPIRED + Freigabe) bleibt bestehen.
            with transaction.atomic():
                # Reservierung des Gewinners in Buchung überführen.
                escrow.consume_money(buyer, escrow.bid_ref(listing.pk, buyer.pk))
                record = execution.execute_purchase(
                    listing, buyer, amount, timing=listing.timing,
                    saison=saison, spieltag=spieltag,
                )
                _finish_listing(listing, TransferListing.STATUS_SOLD)
                # Alle anderen Bieter freigeben.
                _release_all_bidder_reservations(listing)
            return record
        except (execution.ExecutionError, TransferActionError,
                InsufficientFunds) as exc:
            # Auch Deckungsausfälle (fremde Reservierungen/Buchungen können
            # die Deckung zwischenzeitlich ändern) enden deterministisch:
            # EXPIRED + vollständige Escrow-Freigabe, nie hängendes Escrow.
            _expire_listing_on_conflict(listing, str(exc))
    return listing


def _expire_listing_on_conflict(listing, grund):
    """Konflikt-Abschluss: Auktion EXPIRED, gesamtes Escrow frei, Pushes."""
    from game.notifications import notify_club

    _finish_listing(listing, TransferListing.STATUS_EXPIRED)
    _release_all_bidder_reservations(listing)
    msg = (f'Die Auktion für {listing.player.full_name} konnte nicht '
           f'vollzogen werden und wurde ohne Zuschlag beendet: {grund} '
           f'Alle Gebots-Reservierungen wurden freigegeben.')
    if listing.seller_id:
        notify_club(listing.seller, 'Auktion ohne Zuschlag beendet', msg)
    for cid in set(listing.bids.values_list('club_id', flat=True)):
        from game.models import Club
        notify_club(Club.objects.get(pk=cid),
                    'Auktion ohne Zuschlag beendet', msg)


def _finish_listing(listing, status):
    listing.status = status
    listing.save(update_fields=['status', 'updated_at'])


# ── Deal-Anfragen (Master-Spec §4.3) ──────────────────────────────────────

def _validate_deal_player(player, expected_club, *, allow_loaned=False):
    """Prüft eine (gesperrte) Spielerzeile für eine Deal-Seite.

    Sicherheitskritisch: Ein Deal darf NUR Spieler bewegen, die der
    jeweiligen Seite tatsächlich gehören. Zusätzlich blockieren
    Wechselsperre, aktives Leihverhältnis und offener PendingTransfer.
    """
    if expected_club is None or player.club_id != expected_club.pk:
        raise TransferActionError(
            f'{player.full_name} gehört nicht {expected_club.name if expected_club else "—"}.'
        )
    if player.is_transfer_locked:
        raise TransferActionError(f'{player.full_name} ist wechselgesperrt.')
    if not allow_loaned and player.loan_status in ('loaned_in', 'loaned_out'):
        raise TransferActionError(f'{player.full_name} ist verliehen.')
    if Loan.objects.filter(player=player, ended_at__isnull=True).exists():
        raise TransferActionError(f'{player.full_name} ist verliehen.')
    if PendingTransfer.objects.filter(
            player=player, status=PendingTransfer.STATUS_PENDING).exists():
        raise TransferActionError(
            f'{player.full_name} hat bereits einen ausstehenden Transfer.')


def _lock_and_validate_deal_players(from_ids, to_ids, from_club, to_club):
    """Sperrt alle Deal-Spielerzeilen und validiert Eigentum + Zustand.

    Gibt (from_players, to_players) als gesperrte, frische Instanzen zurück.
    """
    from game.models import Player

    alle_ids = sorted(set(from_ids) | set(to_ids))
    if len(alle_ids) < len(from_ids) + len(to_ids):
        raise TransferActionError('Ein Spieler kann nur auf einer Seite stehen.')
    locked = {
        p.pk: p for p in Player.objects.select_for_update()
        .filter(pk__in=alle_ids).order_by('pk')
    }
    if len(locked) != len(alle_ids):
        raise TransferActionError('Spieler nicht gefunden.')
    from_players = [locked[i] for i in from_ids]
    to_players = [locked[i] for i in to_ids]
    for p in from_players:
        _validate_deal_player(p, from_club)
    for p in to_players:
        _validate_deal_player(p, to_club)
    return from_players, to_players


_DEAL_TYPES = (DealRequest.TYP_CASH, DealRequest.TYP_SWAP,
               DealRequest.TYP_SWAP_CASH, DealRequest.TYP_LOAN)
_DEAL_TIMINGS = ('SOFORT', 'WP', 'SE')
_LOAN_UNTILS = (LoanListing.UNTIL_WP, LoanListing.UNTIL_SE)


def _nonneg(value, feldname):
    """Normalisiert einen Geldwert und lehnt negative Beträge hart ab."""
    betrag = _q(value or 0)
    if betrag < 0:
        raise TransferActionError(f'{feldname} darf nicht negativ sein.')
    return betrag


def _check_squad_bounds(club, *, raus=0, rein=0, saison=None):
    """Kadergrenzen-Prüfung (Spec Kap. 9.1) für einen Netto-Effekt.

    raus/rein = Anzahl abgehender/ankommender Spieler dieses Vorgangs.
    Mindestkader blockiert Abgaben, Kaderlimit blockiert Zugänge.
    """
    from game.economy.kader import (effective_squad_limit, min_squad_size,
                                    squad_count)
    aktuell = squad_count(club)
    danach = aktuell - int(raus) + int(rein)
    if raus and danach < min_squad_size(saison):
        raise TransferActionError(
            f'{club.name} würde unter den Mindestkader von '
            f'{min_squad_size(saison)} Spielern fallen.')
    if rein and danach > effective_squad_limit(club, saison):
        raise TransferActionError(
            f'{club.name} hat keinen freien Kaderplatz '
            f'(Limit {effective_squad_limit(club, saison)}).')


def create_deal_request(from_club, to_club, *, typ, timing='SOFORT',
                        cash_from=Decimal('0'), cash_to=Decimal('0'),
                        from_players=None, to_players=None, message='',
                        loan_until='', loan_fee=None, loan_buy_option=None,
                        saison=None):
    """Erstellt eine Deal-/Leihanfrage; reserviert den eigenen Geldanteil.

    Eigentums-Validierung: FROM-Spieler müssen dem Initiator, TO-Spieler
    dem Empfänger gehören (gesperrt geprüft, erneut bei Annahme).

    Typ-Schemata (hart erzwungen, unabhängig von Formular-Validierung):
    - CASH (Kauf): Geld des Initiators gegen ≥1 Empfänger-Spieler; keine
      eigenen Spieler, kein Gegen-Geld, keine Leihfelder.
    - CASH (Verkauf): ≥1 eigener Spieler gegen Geld des Empfängers; keine
      Empfänger-Spieler, kein eigenes Geld. Deckung des Empfängers wird bei
      Annahme geprüft (accept_deal), nicht bei Erstellung.
    - SWAP: ≥1 Spieler auf BEIDEN Seiten; optional einseitiger Geldausgleich;
      keine Leihfelder.
    - LOAN: genau EIN Empfänger-Spieler, keine eigenen Spieler, kein
      cash_from/cash_to; Leihende WP/SE; Gebühr/Kaufoption ≥ 0.
    """
    from game.models import Club

    from_players = list(from_players or [])
    to_players = list(to_players or [])
    if typ not in _DEAL_TYPES:
        raise TransferActionError('Ungültiger Anfrage-Typ.')
    if timing not in _DEAL_TIMINGS:
        raise TransferActionError('Ungültiges Timing (SOFORT/WP/SE).')
    cash_from = _nonneg(cash_from, 'Geldanteil')
    cash_to = _nonneg(cash_to, 'Gegen-Geldanteil')
    loan_fee = _nonneg(loan_fee, 'Leihgebühr') if loan_fee is not None else None
    loan_buy_option = (_nonneg(loan_buy_option, 'Kaufoption')
                       if loan_buy_option is not None else None)

    if typ == DealRequest.TYP_LOAN:
        if len(to_players) != 1 or from_players:
            raise TransferActionError(
                'Leihanfrage: genau ein Spieler des Stammvereins.')
        if cash_from or cash_to:
            raise TransferActionError(
                'Leihanfrage: Geldanteile nur über die Leihgebühr.')
        if loan_until not in _LOAN_UNTILS:
            raise TransferActionError('Ungültiges Leihende (WP/SE).')
    else:
        if loan_until or loan_fee is not None or loan_buy_option is not None:
            raise TransferActionError(
                'Leihfelder nur bei Leihanfragen erlaubt.')
        if typ == DealRequest.TYP_CASH:
            # Zwei Richtungen: Kauf (Empfänger-Spieler gegen eigenes Geld)
            # oder Verkauf (eigene Spieler gegen Empfänger-Geld).
            kauf = bool(to_players) and not from_players
            verkauf = bool(from_players) and not to_players
            if not (kauf or verkauf):
                raise TransferActionError(
                    'Geld-Deal: Spieler nur auf EINER Seite (Kauf oder '
                    'Verkauf).')
            if kauf and (cash_from <= 0 or cash_to):
                raise TransferActionError(
                    'Geld-Deal (Kauf): positiver Geldanteil des Initiators '
                    'nötig, kein Gegen-Geld.')
            if verkauf and (cash_to <= 0 or cash_from):
                raise TransferActionError(
                    'Geld-Deal (Verkauf): positiver Geldanteil des '
                    'Empfängers nötig, kein eigenes Geld.')
        else:  # SWAP / SWAP_CASH
            if not (from_players and to_players):
                raise TransferActionError(
                    'Tausch: Spieler auf beiden Seiten nötig.')
            if cash_from and cash_to:
                raise TransferActionError(
                    'Tausch: Geldausgleich nur einseitig.')
            if typ == DealRequest.TYP_SWAP_CASH and not (cash_from or cash_to):
                raise TransferActionError(
                    'Tausch/Geld: ein Geldausgleich ist erforderlich.')
            # Persistenz konsistent halten: Tausch MIT Geld = SWAP_CASH,
            # reiner Tausch = SWAP (unabhängig von der Aufrufer-Schreibweise).
            typ = (DealRequest.TYP_SWAP_CASH if (cash_from or cash_to)
                   else DealRequest.TYP_SWAP)

    max_paket = int(get_param('TRANSFER_MAX_PAKET', saison))
    if len(from_players) > max_paket or len(to_players) > max_paket:
        raise TransferActionError(f'Maximal {max_paket} Spieler je Seite.')
    if from_club.pk == to_club.pk:
        raise TransferActionError('Anfrage an den eigenen Verein nicht möglich.')

    reserve_betrag = cash_from
    if typ == DealRequest.TYP_LOAN:
        reserve_betrag = loan_fee or ZERO

    with transaction.atomic():
        initiator = Club.objects.select_for_update().get(pk=from_club.pk)
        if escrow.available(initiator) < reserve_betrag:
            raise TransferActionError('Nicht genügend verfügbares Budget.')

        # Eigentum + Zustand aller Spieler gesperrt validieren.
        from_players, to_players = _lock_and_validate_deal_players(
            [p.pk for p in from_players], [p.pk for p in to_players],
            initiator, to_club)

        # Kadergrenzen bereits bei Erstellung (Netto-Effekt; erneut bei
        # Annahme geprüft, da sich Kader bis dahin ändern können).
        if typ == DealRequest.TYP_LOAN:
            _check_squad_bounds(initiator, rein=1, saison=saison)
            _check_squad_bounds(to_club, raus=1, saison=saison)
        else:
            _check_squad_bounds(
                initiator, raus=len(from_players), rein=len(to_players),
                saison=saison)
            _check_squad_bounds(
                to_club, raus=len(to_players), rein=len(from_players),
                saison=saison)

        expires = timezone.now() + timezone.timedelta(
            days=int(get_param('TRANSFER_ANFRAGE_LAUFZEIT_TAGE', saison))
        )
        deal = DealRequest.objects.create(
            from_club=initiator, to_club=to_club, typ=typ, timing=timing,
            cash_from=_q(cash_from), cash_to=_q(cash_to), message=message[:280],
            loan_until=loan_until, loan_fee=_q(loan_fee) if loan_fee else None,
            loan_buy_option=_q(loan_buy_option) if loan_buy_option else None,
            expires_at=expires,
        )
        for p in from_players:
            DealRequestPlayer.objects.create(
                request=deal, player=p, side=DealRequestPlayer.SIDE_FROM)
        for p in to_players:
            DealRequestPlayer.objects.create(
                request=deal, player=p, side=DealRequestPlayer.SIDE_TO)

        if reserve_betrag > 0:
            escrow.reserve_money(initiator, escrow.deal_ref(deal.pk), reserve_betrag)
    return deal


def withdraw_deal(deal):
    """Initiator zieht zurück → Reservierung sofort frei."""
    return _resolve_deal(deal, DealRequest.STATUS_WITHDRAWN)


def decline_deal(deal):
    """Empfänger lehnt ab → Reservierung sofort frei."""
    return _resolve_deal(deal, DealRequest.STATUS_DECLINED)


def expire_deal(deal):
    """7-Tage-Ablauf → Reservierung frei."""
    return _resolve_deal(deal, DealRequest.STATUS_EXPIRED)


def _resolve_deal(deal, status):
    from game.models import Club
    with transaction.atomic():
        deal = DealRequest.objects.select_for_update().get(pk=deal.pk)
        if deal.status != DealRequest.STATUS_OPEN:
            return deal
        deal.status = status
        deal.resolved_at = timezone.now()
        deal.save(update_fields=['status', 'resolved_at'])
        initiator = Club.objects.select_for_update().get(pk=deal.from_club_id)
        escrow.release_money(initiator, escrow.deal_ref(deal.pk))
    return deal


def accept_deal(deal, *, saison=None, spieltag=None):
    """Empfänger nimmt an: Re-Validierung + sofortiger Vollzug (§4.3/§4.4).

    Reihenfolge (alles in EINER Transaktion, Rollback stellt Escrow wieder her):
    1. Deal + beide Clubs sperren, Zustand prüfen.
    2. Eigentum/Zustand ALLER Deal-Spieler gesperrt re-validieren.
    3. Initiator-Escrow VOR der Buchung konsumieren — book_many rechnet
       aktive Reservierungen in die Deckung ein; die eigene Reservierung
       für genau diese Zahlung darf nicht doppelt zählen.
    4. Vollzug (Buchungen, Jugendabgabe, Spielerbewegung/Pending).
    """
    from game.models import Club

    with transaction.atomic():
        deal = DealRequest.objects.select_for_update().get(pk=deal.pk)
        if deal.status != DealRequest.STATUS_OPEN:
            raise TransferActionError('Anfrage ist nicht mehr offen.')
        if timezone.now() >= deal.expires_at:
            raise TransferActionError('Anfrage ist bereits abgelaufen.')

        locked_clubs = {
            c.pk: c for c in Club.objects.select_for_update()
            .filter(pk__in=sorted({deal.from_club_id, deal.to_club_id}))
            .order_by('pk')
        }
        initiator = locked_clubs[deal.from_club_id]
        recipient = locked_clubs[deal.to_club_id]
        # Deckungsprüfung Empfänger-Geldanteil.
        if escrow.available(recipient) < _q(deal.cash_to):
            raise TransferActionError('Empfänger kann seinen Geldanteil nicht decken.')

        # Re-Validierung: Eigentum + Zustand aller Spieler, gesperrt.
        entries = list(deal.players.all())
        from_ids = [e.player_id for e in entries
                    if e.side == DealRequestPlayer.SIDE_FROM]
        to_ids = [e.player_id for e in entries
                  if e.side == DealRequestPlayer.SIDE_TO]
        from_players, to_players = _lock_and_validate_deal_players(
            from_ids, to_ids, initiator, recipient)

        # Kadergrenzen (Netto-Effekt beider Seiten, Spec Kap. 9.1):
        # Initiator gibt from_players ab und erhält to_players — Empfänger
        # umgekehrt. Leihe = 1 Spieler vom Empfänger zum Initiator.
        if deal.typ == DealRequest.TYP_LOAN:
            _check_squad_bounds(initiator, rein=1, saison=saison)
            _check_squad_bounds(recipient, raus=1, saison=saison)
        else:
            _check_squad_bounds(
                initiator, raus=len(from_players), rein=len(to_players),
                saison=saison)
            _check_squad_bounds(
                recipient, raus=len(to_players), rein=len(from_players),
                saison=saison)

        # Escrow des Initiators VOR der Buchung konsumieren (Schritt 3).
        escrow.consume_money(initiator, escrow.deal_ref(deal.pk))

        if deal.typ == DealRequest.TYP_LOAN:
            record = _execute_loan_from_deal(deal, saison=saison)
        else:
            record = _execute_deal_swap(
                deal, from_players, to_players, saison=saison, spieltag=spieltag)

        deal.status = DealRequest.STATUS_ACCEPTED
        deal.resolved_at = timezone.now()
        deal.save(update_fields=['status', 'resolved_at'])
    return record


def _execute_deal_swap(deal, from_players, to_players, *, saison=None,
                       spieltag=None):
    """Vollzieht einen Deal (Tausch/Geld) über die Buchungs-/Levy-Schicht.

    from_players/to_players sind bereits gesperrte, eigentums-validierte
    Instanzen aus _lock_and_validate_deal_players (accept_deal Schritt 2).
    """
    from game.economy.booking import book_many
    from game.models import Player
    from .execution import (_levy_entries_and_payments, _move_player,
                            _set_transfer_lock, _create_pending)
    from .models import TransferRecordPlayer, YouthLevyPayment
    from . import youth_levy

    club_a = deal.from_club  # abgebend (Initiator gibt from_players)
    club_b = deal.to_club

    cash_from = _q(deal.cash_from)
    cash_to = _q(deal.cash_to)

    from game.models import Club
    club_ids = {club_a.pk, club_b.pk}
    # Jugendabgabe je abgegebenem Spieler. Bemessung:
    # - Tausch (Spieler auf BEIDEN Seiten, §5.6): Marktwert + anteiliges
    #   Gegenseiten-Geld (swap_bemessung).
    # - Reiner Geld-Deal (Spieler nur auf EINER Seite): NUR der gezahlte
    #   Preis (anteilig je Spieler) — nie der Marktwert obendrauf.
    is_swap = bool(from_players and to_players)

    def _basis(p, gegenseite_geld, n):
        if is_swap:
            return youth_levy.swap_bemessung(p, gegenseite_geld, n)
        geld = Decimal(str(gegenseite_geld or 0))
        return _q(geld / max(int(n or 1), 1))

    levy_from = []
    for p in from_players:
        basis = _basis(p, cash_to, len(from_players))
        v = youth_levy.calc_youth_levy(p, basis, zahler_club=club_a, saison=saison)
        levy_from.append((p, v))
        club_ids.update(v['betraege_je_ausbildungsverein'])
    levy_to = []
    for p in to_players:
        basis = _basis(p, cash_from, len(to_players))
        v = youth_levy.calc_youth_levy(p, basis, zahler_club=club_b, saison=saison)
        levy_to.append((p, v))
        club_ids.update(v['betraege_je_ausbildungsverein'])

    locked = {c.pk: c for c in Club.objects.select_for_update()
              .filter(pk__in=sorted(club_ids)).order_by('pk')}

    kind = (TransferRecord.KIND_SWAP if (from_players and to_players)
            else TransferRecord.KIND_CASH)
    record = TransferRecord.objects.create(
        kind=kind, timing=deal.timing, club_a=club_a, club_b=club_b,
        cash_a=cash_from, cash_b=cash_to,
    )

    entries_book = []
    # Geldflüsse (Netto beidseitig möglich).
    if cash_from > 0:
        entries_book += [
            {'club': locked[club_a.pk], 'typ': 'TRANSFER_AUS', 'betrag': -cash_from,
             'beschreibung': f'Deal #{deal.pk}', 'saison': saison, 'spieltag': spieltag,
             'referenz_typ': 'transfer_v2', 'referenz_id': deal.pk},
            {'club': locked[club_b.pk], 'typ': 'TRANSFER_EIN', 'betrag': cash_from,
             'beschreibung': f'Deal #{deal.pk}', 'saison': saison, 'spieltag': spieltag,
             'referenz_typ': 'transfer_v2', 'referenz_id': deal.pk},
        ]
    if cash_to > 0:
        entries_book += [
            {'club': locked[club_b.pk], 'typ': 'TRANSFER_AUS', 'betrag': -cash_to,
             'beschreibung': f'Deal #{deal.pk}', 'saison': saison, 'spieltag': spieltag,
             'referenz_typ': 'transfer_v2', 'referenz_id': deal.pk},
            {'club': locked[club_a.pk], 'typ': 'TRANSFER_EIN', 'betrag': cash_to,
             'beschreibung': f'Deal #{deal.pk}', 'saison': saison, 'spieltag': spieltag,
             'referenz_typ': 'transfer_v2', 'referenz_id': deal.pk},
        ]
    payments = []
    for p, v in levy_from:
        le, pay = _levy_entries_and_payments(record, p, club_a, v, locked,
                                             saison=saison, spieltag=spieltag)
        entries_book += le
        payments += pay
    for p, v in levy_to:
        le, pay = _levy_entries_and_payments(record, p, club_b, v, locked,
                                             saison=saison, spieltag=spieltag)
        entries_book += le
        payments += pay

    if entries_book:
        book_many(entries_book, saison=saison)
    for pay in payments:
        YouthLevyPayment.objects.create(**pay)

    immediate = deal.timing == TransferListing.TIMING_SOFORT
    for p in from_players:
        cur = Player.objects.select_for_update().get(pk=p.pk)
        mw = _q(cur.market_value) if cur.market_value is not None else None
        TransferRecordPlayer.objects.create(
            record=record, player=cur, side=TransferRecordPlayer.SIDE_A,
            market_value_at_transfer=mw)
        if immediate:
            _move_player(cur, club_b)
            _set_transfer_lock(cur, record, saison)
        else:
            from .models import PendingTransfer
            _create_pending(cur, club_a, club_b, deal.timing, record,
                            PendingTransfer.SOURCE_DEAL, saison)
    for p in to_players:
        cur = Player.objects.select_for_update().get(pk=p.pk)
        mw = _q(cur.market_value) if cur.market_value is not None else None
        TransferRecordPlayer.objects.create(
            record=record, player=cur, side=TransferRecordPlayer.SIDE_B,
            market_value_at_transfer=mw)
        if immediate:
            _move_player(cur, club_a)
            _set_transfer_lock(cur, record, saison)
        else:
            from .models import PendingTransfer
            _create_pending(cur, club_b, club_a, deal.timing, record,
                            PendingTransfer.SOURCE_DEAL, saison)
    return record


# ── Leihen (Master-Spec §5.3/§5.4) ────────────────────────────────────────

def _validate_loan_fee(owner_club, loan_club, fee, saison=None):
    min_fee = get_decimal('LEIHE_MIN_GEBUEHR', saison)
    fee = _q(fee or 0)
    if fee == 0 and not ClubPartnership.are_partners(owner_club, loan_club):
        raise TransferActionError('0-€-Leihgebühr nur zwischen Partnervereinen.')
    if fee > 0 and fee < min_fee:
        raise TransferActionError(f'Leihgebühr muss mindestens {min_fee:,.0f} € betragen.')
    return fee


def _check_loan_limits(owner_club, loan_club, saison=None):
    rein = int(get_param('LEIHE_LIMIT_REIN', saison))
    raus = int(get_param('LEIHE_LIMIT_RAUS', saison))
    paar = int(get_param('LEIHE_LIMIT_JE_PAAR', saison))
    if Loan.objects.filter(loan_club=loan_club, ended_at__isnull=True).count() >= rein:
        raise TransferActionError('Leih-Limit (rein) erreicht.')
    if Loan.objects.filter(owner_club=owner_club, ended_at__isnull=True).count() >= raus:
        raise TransferActionError('Leih-Limit (raus) erreicht.')
    if Loan.objects.filter(owner_club=owner_club, loan_club=loan_club,
                           ended_at__isnull=True).count() >= paar:
        raise TransferActionError('Leih-Limit je Vereinspaar erreicht.')


def create_loan_listing(player, owner_club, *, fee_asking, until,
                        buy_option_price=None, saison=None):
    """Erstellt ein Leih-Listing (unter Spieler-Lock voll validiert).

    0-€-Gebühr ist beim LISTEN erlaubt (der künftige Leihverein steht noch
    nicht fest) — die Partnervereins-Prüfung erfolgt erst bei der konkreten
    Anfrage/Annahme (_validate_loan_fee mit echtem Leihverein). Eine Gebühr
    > 0 muss das Minimum einhalten.
    """
    from game.models import Player

    if until not in _LOAN_UNTILS:
        raise TransferActionError('Ungültiges Leihende (WP/SE).')
    fee = _nonneg(fee_asking, 'Leihgebühr')
    buy_option = (_nonneg(buy_option_price, 'Kaufoption')
                  if buy_option_price is not None else None)
    min_fee = get_decimal('LEIHE_MIN_GEBUEHR', saison)
    if fee > 0 and fee < min_fee:
        raise TransferActionError(
            f'Leihgebühr muss mindestens {min_fee:,.0f} € betragen.')

    with transaction.atomic():
        player = Player.objects.select_for_update().get(pk=player.pk)
        # Volle Zustandsprüfung (Eigentum, Sperre, aktive Leihe, Pending).
        _validate_deal_player(player, owner_club)
        if LoanListing.objects.filter(
                player=player, status=LoanListing.STATUS_ACTIVE).exists():
            raise TransferActionError(
                f'{player.full_name} ist bereits auf dem Leihmarkt.')
        if TransferListing.objects.filter(
                player=player,
                status=TransferListing.STATUS_ACTIVE).exists():
            raise TransferActionError(
                f'{player.full_name} ist bereits auf dem Transfermarkt.')
        return LoanListing.objects.create(
            player=player, owner_club=owner_club, fee_asking=fee,
            until=until, buy_option_price=buy_option,
        )


def request_loan(loan_listing, loan_club, *, saison=None):
    """Leihanfrage aus dem Leihmarkt → DealRequest(typ=LOAN) unter Meine Deals."""
    if loan_listing.status != LoanListing.STATUS_ACTIVE:
        raise TransferActionError('Leih-Listing ist nicht mehr aktiv.')
    if loan_listing.owner_club_id == loan_club.pk:
        raise TransferActionError('Eigenes Leih-Listing.')
    if loan_market_paused(loan_listing.until, saison):
        raise TransferActionError('Leihmarkt pausiert (Leih-Deadline erreicht).')
    _check_loan_limits(loan_listing.owner_club, loan_club, saison)
    fee = _validate_loan_fee(loan_listing.owner_club, loan_club,
                             loan_listing.fee_asking, saison)
    return create_deal_request(
        loan_club, loan_listing.owner_club, typ=DealRequest.TYP_LOAN,
        loan_until=loan_listing.until, loan_fee=fee,
        loan_buy_option=loan_listing.buy_option_price,
        from_players=[], to_players=[loan_listing.player], saison=saison,
    )


def _execute_loan_from_deal(deal, *, saison=None):
    """Vollzieht eine angenommene Leihanfrage (Gebühr sofort an Stammverein)."""
    from game.economy.booking import book_many
    from game.models import Club, Player

    to_entries = list(deal.players.filter(side=DealRequestPlayer.SIDE_TO))
    if len(to_entries) != 1 or deal.players.filter(
            side=DealRequestPlayer.SIDE_FROM).exists():
        raise TransferActionError(
            'Leihanfrage: genau ein Spieler des Stammvereins.')
    player = Player.objects.select_for_update().get(pk=to_entries[0].player_id)
    owner_club = deal.to_club       # Empfänger = Stammverein (besitzt Spieler)
    loan_club = deal.from_club      # Initiator = aufnehmender Verein

    if loan_market_paused(deal.loan_until or 'WP', saison):
        raise TransferActionError('Leihmarkt pausiert (Leih-Deadline erreicht).')
    _check_loan_limits(owner_club, loan_club, saison)
    fee = _validate_loan_fee(owner_club, loan_club, deal.loan_fee, saison)

    locked = {c.pk: c for c in Club.objects.select_for_update()
              .filter(pk__in=sorted({owner_club.pk, loan_club.pk})).order_by('pk')}
    if fee > 0:
        book_many([
            {'club': locked[loan_club.pk], 'typ': 'TRANSFER_AUS', 'betrag': -fee,
             'beschreibung': f'Leihgebühr {player.full_name}', 'saison': saison,
             'referenz_typ': 'transfer_v2_loan', 'referenz_id': deal.pk},
            {'club': locked[owner_club.pk], 'typ': 'TRANSFER_EIN', 'betrag': fee,
             'beschreibung': f'Leihgebühr {player.full_name}', 'saison': saison,
             'referenz_typ': 'transfer_v2_loan', 'referenz_id': deal.pk},
        ], saison=saison)

    loan = Loan.objects.create(
        player=player, owner_club=owner_club, loan_club=loan_club,
        fee=fee, until=deal.loan_until or 'WP', buy_option=deal.loan_buy_option,
        started_via=Loan.STARTED_VIA_DEAL,
    )
    # Aktive Leih-Listings dieses Spielers schließen — sie dürfen nach dem
    # Leihstart nicht weiter anfragbar bleiben.
    LoanListing.objects.filter(
        player=player, status=LoanListing.STATUS_ACTIVE,
    ).update(status=LoanListing.STATUS_LOANED)
    # Spieler zieht zum aufnehmenden Verein (zählt dort auf die Kadergrenze);
    # Leihstart erzeugt KEINE Wechselsperre wie ein Kauf, aber einen Record.
    player.club = loan_club
    player.loan_status = 'loaned_in'
    player.loan_partner_club = owner_club
    player.save(update_fields=['club', 'loan_status', 'loan_partner_club'])

    record = TransferRecord.objects.create(
        kind=TransferRecord.KIND_LOAN, timing='SOFORT',
        club_a=owner_club, club_b=loan_club, cash_a=Decimal('0'), cash_b=fee,
        loan_event=TransferRecord.LOAN_EVENT_START, loan_until=deal.loan_until or 'WP',
    )
    from .models import TransferRecordPlayer
    TransferRecordPlayer.objects.create(
        record=record, player=player, side=TransferRecordPlayer.SIDE_A,
        market_value_at_transfer=_q(player.market_value) if player.market_value else None,
    )
    return record


accept_loan_request = accept_deal  # Leihanfrage ist ein DealRequest(typ=LOAN).


def exercise_buy_option(loan, buyer_club, *, saison=None, spieltag=None):
    """Leihverein zieht die vereinbarte Kaufoption (Vollkauf sofort).

    Delegiert an execution.execute_option_purchase (atomar, escrow-bewusst,
    Jugendabgabe, Leih-Ende, Wechselsperre, OPTION-Record).
    """
    try:
        return execution.execute_option_purchase(
            loan, buyer_club=buyer_club, saison=saison, spieltag=spieltag)
    except execution.ExecutionError as e:
        raise TransferActionError(str(e))


# ── Kader anbieten: Statusboard (Task #821) ──────────────────────────────

def set_squad_offer_status(player, club, status):
    """Setzt/aktualisiert den „Kader anbieten"-Status eines eigenen Spielers.

    Reines Kommunikations-Statusboard (kein Zwang, keine Geldbewegung).
    Eigentum wird hart geprüft — nur der besitzende Verein darf den Status
    seiner Spieler setzen.
    """
    from game.models import SquadOffer

    if club is None or player.club_id != club.pk:
        raise TransferActionError(
            f'{player.full_name} gehört nicht {club.name if club else "—"}.')
    valid = {c[0] for c in SquadOffer.STATUS_CHOICES}
    if status not in valid:
        raise TransferActionError('Ungültiger Angebots-Status.')
    obj, _ = SquadOffer.objects.update_or_create(
        player=player, defaults={'status': status})
    return obj


def build_forum_post(club):
    """Erzeugt den BB-Code-Forum-Post aller Spieler mit Status ≠ UVK.

    Reine Text-Erzeugung aus dem gespeicherten Statusboard — keine
    Push-Auslösung, kein Nebenwirkung.
    """
    from game.models import Player, SquadOffer

    stmap = dict(SquadOffer.STATUS_CHOICES)
    offers = {
        o.player_id: o.status
        for o in SquadOffer.objects.filter(player__club=club)
        .exclude(status=SquadOffer.STATUS_UVK)
    }
    if not offers:
        return ''
    players = {
        p.pk: p for p in Player.objects.filter(pk__in=offers)
    }
    lines = []
    for pid, status in offers.items():
        p = players.get(pid)
        if not p:
            continue
        hp = ','.join(p.main_positions[:3]) or '—'
        mw = int(p.market_value or 0)
        mw_fmt = f'{mw:,}'.replace(',', '.') + ' €'
        lines.append(
            f'{hp} | {p.full_name} | {p.age} | {mw_fmt} | '
            f'Status: {stmap.get(status, status)}')
    if not lines:
        return ''
    from django.utils import timezone as _tz
    stamp = _tz.localdate().strftime('%d.%m.%Y')
    header = f'[b]{club.name} — Kaderangebote (Stand {stamp})[/b]'
    footer = ('Anfragen gern ingame über den Deal-Builder oder hier '
              'im Thread.')
    return header + '\n' + '\n'.join(lines) + '\n\n' + footer


def price_guidance(player, *, saison=None):
    """Preisfindungs-Hilfe (§6.1): Spanne + bis zu 3 Referenzen.

    Datengrundlage sind reale, vollzogene Geld-Transfers (TransferRecord
    KIND_CASH mit genau EINEM Spieler) vergleichbarer Spieler derselben
    Hauptposition. Bei < 3 vergleichbaren Treffern gibt es KEINE Anzeige
    (bewusst „keine schlechten Daten"). Das Positionsbarometer gewichtet
    die Spanne nach oben/unten (keine eigene UI).

    Rückgabe:
        {'show': bool, 'lo': int, 'hi': int, 'refs': [{...}]}  oder
        {'show': False} wenn < 3 Vergleiche.
    """
    from game.models import PlayerMarketValueSnapshot
    from .models import PositionBarometer, TransferRecordPlayer

    hp = (player.main_position_1 or '').strip()
    if not hp:
        return {'show': False}

    # Vergleichbare vollzogene Geld-Transfers: 1 Spieler, gleiche HP,
    # tatsächlich Geld geflossen. market_value_at_transfer als Vergleichspreis.
    entries = (
        TransferRecordPlayer.objects
        .filter(
            record__kind=TransferRecord.KIND_CASH,
            record__is_cancelled=False,
            player__main_position_1=hp,
            market_value_at_transfer__isnull=False,
        )
        .exclude(player_id=player.pk)
        .select_related('record', 'player')
        .order_by('-record__date', '-record__id')
    )
    refs_raw = []
    prices = []
    for e in entries:
        preis = e.record.cash_b or e.record.cash_a
        if not preis or preis <= 0:
            continue
        prices.append(Decimal(str(preis)))
        if len(refs_raw) < 3:
            refs_raw.append((e.player, preis, e.record.date))
        if len(prices) >= 12:
            break

    if len(prices) < 3:
        return {'show': False}

    prices.sort()
    lo = prices[0]
    hi = prices[-1]

    # Positionsbarometer-Gewicht (Nachfrageüberhang → teurer).
    baro = PositionBarometer.objects.filter(position=hp).first()
    weight = Decimal(str(baro.weight)) if baro else Decimal('1.000')
    lo = _q(lo * weight)
    hi = _q(hi * weight)
    # Auf 100.000 € runden (wie Prototyp).
    step = Decimal('100000')
    lo = (lo / step).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * step
    hi = (hi / step).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * step

    refs = []
    for rp, preis, datum in refs_raw:
        rphp = ','.join(rp.main_positions[:1]) or hp
        refs.append({
            'name': rp.full_name,
            'age': rp.age,
            'hp': rphp,
            'price': int(preis),
            'date': datum.strftime('%d.%m.') if datum else '',
        })
    return {'show': True, 'lo': int(lo), 'hi': int(hi), 'refs': refs}
