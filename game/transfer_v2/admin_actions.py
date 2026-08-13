"""Creator-Transferaufsicht — Admin-Aktionen (Task #824, Spec §8).

Locking-/Buchungs-Muster exakt wie execution.py:
- Clubs sortiert nach pk mit select_for_update sperren.
- Buchungen NUR via game.economy.booking.book_many.
- Rückzahlungen des Empfängers als Pflichtbuchung ('pflicht': True).
- Pushes NUR nach Commit via transaction.on_commit.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from game.economy.booking import book_many

from .models import (
    CreatorActionLog, Loan, PendingTransfer, SquadLimitNote,
    TransferLock, TransferRecord, TransferRecordPlayer, YouthLevyPayment,
)

logger = logging.getLogger(__name__)

CENT = Decimal('0.01')
ZERO = Decimal('0.00')


class TransferActionError(Exception):
    """Fachlicher Fehler bei Admin-Aktionen (deutsche Meldung für die UI)."""


def _q(v):
    return Decimal(str(v)).quantize(CENT)


def log_creator_action(actor, action, target, **details):
    """Protokolliert eine Creator-Aktion in CreatorActionLog."""
    try:
        CreatorActionLog.objects.create(
            actor=actor,
            action=action,
            target=str(target)[:200],
            details=details,
        )
    except Exception:
        logger.exception('CreatorActionLog konnte nicht geschrieben werden')


def admin_cancel_record(record, *, grund='', actor=None, saison=None):
    """Vollständige Rückabwicklung eines TransferRecords (Spec §8).

    Atomic; record select_for_update; wenn record.is_cancelled -> Fehler.
    Pending-Transfers -> CANCELLED_ADMIN; vollzogene Transfers -> Spieler zurück.
    Geldflüsse spiegeln, Jugendabgaben rückbuchen, TransferLocks löschen.
    """
    from game.models import Club, Player

    with transaction.atomic():
        rec = TransferRecord.objects.select_for_update().get(pk=record.pk)
        if rec.is_cancelled:
            raise TransferActionError('bereits storniert')

        # ── Spieler-Bewegungen bestimmen ──────────────────────────────────
        # Alle beteiligten Vereine sammeln (für Locks)
        club_ids = set()
        if rec.club_a_id:
            club_ids.add(rec.club_a_id)
        if rec.club_b_id:
            club_ids.add(rec.club_b_id)

        # Jugendabgaben laden
        levies = list(YouthLevyPayment.objects.filter(record=rec))
        for lev in levies:
            if lev.payer_club_id:
                club_ids.add(lev.payer_club_id)
            if lev.receiver_club_id:
                club_ids.add(lev.receiver_club_id)

        # Spieler aus Record-Playern
        record_players = list(rec.players.select_related('player').all())

        # PendingTransfers für diesen Record
        pendings = list(PendingTransfer.objects.filter(
            record=rec, status=PendingTransfer.STATUS_PENDING,
        ).select_related('player', 'from_club', 'to_club'))

        # Clubs für Pendings
        for p in pendings:
            if p.from_club_id:
                club_ids.add(p.from_club_id)
            if p.to_club_id:
                club_ids.add(p.to_club_id)

        # Alle Clubs sperren (stabile PK-Ordnung)
        locked = {
            c.pk: c
            for c in Club.objects.select_for_update()
            .filter(pk__in=sorted(club_ids)).order_by('pk')
        }

        # ── Für vollzogene Transfers: Spieler prüfen & zurückbewegen ─────
        # Pendings (noch nicht vollzogen) -> nur Status setzen
        for p in pendings:
            p.status = PendingTransfer.STATUS_CANCELLED_ADMIN
            p.executed_at = timezone.now()
            p.save(update_fields=['status', 'executed_at'])

        # Vollzogene Spielerwechsel: zurück bewegen
        # SIDE_A: Spieler ging von club_a -> club_b; zurück = club_b -> club_a
        # SIDE_B: Spieler ging von club_b -> club_a; zurück = club_a -> club_b
        is_loan_start = (rec.kind == TransferRecord.KIND_LOAN
                         and rec.loan_event == TransferRecord.LOAN_EVENT_START)
        is_loan_return = (rec.kind == TransferRecord.KIND_LOAN
                          and rec.loan_event == TransferRecord.LOAN_EVENT_RETURN)

        if is_loan_return:
            raise TransferActionError(
                'Storno eines RETURN-Records (Leih-Rückkehr) ist nicht möglich.'
            )

        # Spieler, die wirklich bewegt wurden (nicht nur Pending)
        # = record_players die KEIN laufendes Pending haben
        pending_player_ids = {p.player_id for p in pendings}

        players_to_move = []
        for rp in record_players:
            if rp.player_id is None:
                continue
            if rp.player_id in pending_player_ids:
                # War noch Pending -> Spieler hat nicht gewechselt, kein Rück-Move
                continue
            # Spieler hat gewechselt: prüfen ob er beim aufnehmenden Verein ist
            player_obj = Player.objects.select_for_update().get(pk=rp.player_id)
            if rp.side == TransferRecordPlayer.SIDE_A:
                # Spieler ging von club_a nach club_b
                expected_current = rec.club_b_id
                return_to = rec.club_a_id
            else:
                # SIDE_B: Spieler ging von club_b nach club_a
                expected_current = rec.club_a_id
                return_to = rec.club_b_id

            if expected_current and player_obj.club_id != expected_current:
                raise TransferActionError(
                    f'Spieler {player_obj.full_name} ist nicht mehr beim '
                    f'aufnehmenden Verein — kein Teil-Storno möglich.'
                )
            players_to_move.append((player_obj, return_to))

        # Leihen behandeln: aktive Loan-Zeile JE SPIELER des Records sperren.
        # Nie über das Vereinspaar suchen — zwischen denselben zwei Vereinen
        # können mehrere Leihen gleichzeitig aktiv sein (Leih-Limits erlauben
        # das); ein Paar-Lookup würde die falsche Leihe beenden.
        loans_by_player = {}
        if is_loan_start:
            for rp in record_players:
                if not rp.player_id:
                    continue
                loan = Loan.objects.select_for_update().filter(
                    player_id=rp.player_id, ended_at__isnull=True,
                ).first()
                if loan is None:
                    raise TransferActionError(
                        'Keine aktive Leihe zu diesem Record gefunden — '
                        'kein Storno möglich.'
                    )
                # Defensiv: Leihe muss zu den Record-Vereinen passen.
                if (loan.owner_club_id != rec.club_a_id
                        or loan.loan_club_id != rec.club_b_id):
                    raise TransferActionError(
                        'Aktive Leihe des Spielers gehört nicht zu diesem '
                        'Record — kein Storno möglich.'
                    )
                loans_by_player[rp.player_id] = loan

        # ── Geldflüsse spiegeln ────────────────────────────────────────────
        entries = []
        ref_typ = 'transfer_v2_admin_storno'
        text = f'Admin-Storno Record #{rec.pk}'
        if grund:
            text += f' ({grund})'

        is_free = rec.kind == TransferRecord.KIND_FREE

        if is_free:
            # KIND_FREE (Vereinsloser Kauf): nur Käufer bekommt cash_b zurück
            # (Verbands-Senke, keine Gegenbuchung)
            if rec.cash_b and _q(rec.cash_b) > ZERO and rec.club_b_id:
                entries.append({
                    'club': locked[rec.club_b_id], 'typ': 'TRANSFER_EIN',
                    'betrag': _q(rec.cash_b), 'beschreibung': text,
                    'saison': saison, 'referenz_typ': ref_typ,
                    'referenz_id': rec.pk,
                })
        else:
            # cash_b: B zahlte an A -> B erhält cash_b zurück (TRANSFER_EIN),
            #          A zahlt zurück (TRANSFER_AUS, pflicht=True)
            if rec.cash_b and _q(rec.cash_b) > ZERO:
                if rec.club_b_id:
                    entries.append({
                        'club': locked[rec.club_b_id], 'typ': 'TRANSFER_EIN',
                        'betrag': _q(rec.cash_b), 'beschreibung': text,
                        'saison': saison, 'referenz_typ': ref_typ,
                        'referenz_id': rec.pk,
                    })
                if rec.club_a_id:
                    entries.append({
                        'club': locked[rec.club_a_id], 'typ': 'TRANSFER_AUS',
                        'betrag': -_q(rec.cash_b), 'beschreibung': text,
                        'saison': saison, 'referenz_typ': ref_typ,
                        'referenz_id': rec.pk, 'pflicht': True,
                    })
            # cash_a: A zahlte an B -> A erhält cash_a zurück (TRANSFER_EIN),
            #          B zahlt zurück (TRANSFER_AUS, pflicht=True)
            if rec.cash_a and _q(rec.cash_a) > ZERO:
                if rec.club_a_id:
                    entries.append({
                        'club': locked[rec.club_a_id], 'typ': 'TRANSFER_EIN',
                        'betrag': _q(rec.cash_a), 'beschreibung': text,
                        'saison': saison, 'referenz_typ': ref_typ,
                        'referenz_id': rec.pk,
                    })
                if rec.club_b_id:
                    entries.append({
                        'club': locked[rec.club_b_id], 'typ': 'TRANSFER_AUS',
                        'betrag': -_q(rec.cash_a), 'beschreibung': text,
                        'saison': saison, 'referenz_typ': ref_typ,
                        'referenz_id': rec.pk, 'pflicht': True,
                    })

        # Jugendabgaben rückbuchen
        for lev in levies:
            if lev.receiver_club_id and lev.payer_club_id:
                entries += [
                    {
                        'club': locked[lev.receiver_club_id],
                        'typ': 'AUSBILDUNG_AUS',
                        'betrag': -_q(lev.amount), 'beschreibung': text,
                        'saison': saison, 'referenz_typ': ref_typ,
                        'referenz_id': rec.pk, 'pflicht': True,
                    },
                    {
                        'club': locked[lev.payer_club_id],
                        'typ': 'AUSBILDUNG_EIN',
                        'betrag': _q(lev.amount), 'beschreibung': text,
                        'saison': saison, 'referenz_typ': ref_typ,
                        'referenz_id': rec.pk,
                    },
                ]

        if entries:
            book_many(entries, saison=saison)

        if levies:
            YouthLevyPayment.objects.filter(
                pk__in=[lev.pk for lev in levies]).delete()

        # ── Spieler zurückbewegen ─────────────────────────────────────────
        for player_obj, return_to_id in players_to_move:
            loan = loans_by_player.get(player_obj.pk)
            if is_loan_start and loan is not None:
                # Leihe dieses Spielers beenden
                loan.ended_at = timezone.now()
                loan.save(update_fields=['ended_at'])
                player_obj.loan_status = ''
                player_obj.loan_partner_club = None
                player_obj.save(update_fields=['loan_status', 'loan_partner_club'])
            # Spieler zurück zum abgebenden Verein
            return_club = locked.get(return_to_id) if return_to_id else None
            player_obj.club = return_club
            player_obj.is_on_transfer_list = False
            player_obj.is_on_loan_list = False
            player_obj.sale_category = 'UVK'
            player_obj.sale_visible_to_ai = False
            player_obj.save(update_fields=[
                'club', 'is_on_transfer_list', 'is_on_loan_list',
                'sale_category', 'sale_visible_to_ai',
            ])

        # ── TransferLocks löschen ─────────────────────────────────────────
        locks = TransferLock.objects.filter(source_record=rec).select_related('player')
        for lock in locks:
            try:
                player_obj = Player.objects.get(pk=lock.player_id)
                if player_obj.transfer_locked_until == lock.locked_until:
                    player_obj.transfer_locked_until = None
                    player_obj.save(update_fields=['transfer_locked_until'])
            except Player.DoesNotExist:
                pass
        locks.delete()

        # ── Record als storniert markieren ────────────────────────────────
        rec.is_cancelled = True
        rec.save(update_fields=['is_cancelled'])

    # ── Pushes nach Commit ────────────────────────────────────────────────
    from . import push

    def _do_pushes():
        try:
            if rec.club_a_id:
                from game.models import Club as _Club
                club_a = _Club.objects.get(pk=rec.club_a_id)
                push.admin_cancelled(rec, club_a, grund)
        except Exception:
            logger.exception('admin_cancel push (club_a) fehlgeschlagen')
        try:
            if rec.club_b_id:
                from game.models import Club as _Club
                club_b = _Club.objects.get(pk=rec.club_b_id)
                push.admin_cancelled(rec, club_b, grund)
        except Exception:
            logger.exception('admin_cancel push (club_b) fehlgeschlagen')

    transaction.on_commit(_do_pushes)
    transaction.on_commit(
        lambda: log_creator_action(
            actor, 'admin_cancel_record',
            f'Record #{rec.pk}',
            grund=grund, record_id=rec.pk,
        )
    )


def admin_transfer(player, to_club, *, actor=None, saison=None, grund=''):
    """Direkt-Transfer ohne Ablöse und ohne Jugendabgabe (Aufsichtsakt).

    KIND_ADMIN, is_admin=True. Keine Wechselsperre, keine Buchungen.
    """
    from game.models import Club, Player
    from game.economy.kader import effective_squad_limit, min_squad_size, squad_count

    with transaction.atomic():
        player_obj = Player.objects.select_for_update().get(pk=player.pk)
        old_club = player_obj.club

        # Alle beteiligten Club-Zeilen sperren (stabile PK-Ordnung)
        club_ids = [to_club.pk]
        if old_club is not None:
            club_ids.append(old_club.pk)
        locked = {
            c.pk: c
            for c in Club.objects.select_for_update()
            .filter(pk__in=sorted(set(club_ids))).order_by('pk')
        }

        to_club_locked = locked[to_club.pk]
        old_club_locked = locked.get(old_club.pk) if old_club else None

        # Kadergrenzen prüfen
        if squad_count(to_club_locked) + 1 > effective_squad_limit(to_club_locked, saison):
            raise TransferActionError(
                f'{to_club.name} hat keinen freien Kaderplatz '
                f'(Limit {effective_squad_limit(to_club_locked, saison)}).'
            )
        if old_club_locked is not None:
            if squad_count(old_club_locked) - 1 < min_squad_size(saison):
                raise TransferActionError(
                    f'{old_club.name} würde unter den Mindestkader von '
                    f'{min_squad_size(saison)} Spielern fallen.'
                )

        # Marktwert-Snapshot
        mw = _q(player_obj.market_value) if player_obj.market_value else None

        # TransferRecord erzeugen
        from .models import TransferListing as _TL
        rec = TransferRecord.objects.create(
            kind=TransferRecord.KIND_ADMIN,
            timing=_TL.TIMING_SOFORT,
            club_a=old_club,
            club_b=to_club,
            cash_a=ZERO,
            cash_b=ZERO,
            is_admin=True,
        )
        TransferRecordPlayer.objects.create(
            record=rec, player=player_obj,
            side=TransferRecordPlayer.SIDE_A,
            market_value_at_transfer=mw,
        )

        # Spieler bewegen (keine Wechselsperre)
        player_obj.club = to_club_locked
        player_obj.is_on_transfer_list = False
        player_obj.is_on_loan_list = False
        player_obj.sale_category = 'UVK'
        player_obj.sale_visible_to_ai = False
        player_obj.save(update_fields=[
            'club', 'is_on_transfer_list', 'is_on_loan_list',
            'sale_category', 'sale_visible_to_ai',
        ])

    # Pushes nach Commit
    from . import push

    def _do_pushes():
        try:
            msg = (f'Admin-Transfer: {player_obj.full_name} → {to_club.name}.'
                   + (f' Grund: {grund}' if grund else ''))
            push.admin_transfer(to_club, msg)
            if old_club:
                push.admin_transfer(old_club, msg)
        except Exception:
            logger.exception('admin_transfer push fehlgeschlagen')

    transaction.on_commit(_do_pushes)
    transaction.on_commit(
        lambda: log_creator_action(
            actor, 'admin_transfer',
            f'{player_obj.full_name} → {to_club.name}',
            grund=grund, player_id=player_obj.pk, to_club_id=to_club.pk,
        )
    )
    return rec


def admin_cancel_listing(listing, *, grund='', actor=None):
    """Vorzeitiges Auktions-Ende ohne Zuschlag (CANCELLED).

    Gibt alle Gebots-Reservierungen frei, Benachrichtigung an Verkäufer + Bieter.
    """
    from . import escrow as _escrow
    from .models import TransferListing
    from .services import (
        TransferActionError as ServiceError,
        _finish_listing, _release_all_bidder_reservations,
    )

    with transaction.atomic():
        lst = TransferListing.objects.select_for_update().get(pk=listing.pk)
        if lst.status != TransferListing.STATUS_ACTIVE:
            raise TransferActionError('Listing ist nicht aktiv.')
        _finish_listing(lst, TransferListing.STATUS_CANCELLED)
        bidder_ids = set(lst.bids.values_list('club_id', flat=True))
        _release_all_bidder_reservations(lst)

    # Pushes nach Commit
    def _notify():
        try:
            from game.models import Club
            from game.notifications import notify_club
            msg = (f'Die Auktion für {lst.player.full_name} wurde von der '
                   f'Transferaufsicht beendet (kein Zuschlag).'
                   + (f' Grund: {grund}' if grund else ''))
            if lst.seller_id:
                seller = Club.objects.get(pk=lst.seller_id)
                notify_club(seller, 'Auktion beendet (Admin)', msg)
            for cid in bidder_ids:
                notify_club(Club.objects.get(pk=cid),
                            'Auktion beendet (Admin)', msg)
        except Exception:
            logger.exception('admin_cancel_listing push fehlgeschlagen')

    transaction.on_commit(_notify)
    transaction.on_commit(
        lambda: log_creator_action(
            actor, 'admin_cancel_listing',
            f'Listing #{lst.pk} ({lst.player})',
            grund=grund, listing_id=lst.pk,
        )
    )


def admin_close_listing_now(listing, *, saison=None, actor=None):
    """Vorzeitiger Zuschlag = services.close_listing(force=True) + log."""
    from .services import close_listing

    result = close_listing(listing, force=True, saison=saison)
    transaction.on_commit(
        lambda: log_creator_action(
            actor, 'admin_close_listing_now',
            f'Listing #{listing.pk} ({listing.player})',
            listing_id=listing.pk,
        )
    )
    return result
