"""Vollzug von Transfers/Leihen (Master-Spec §4.4, §5) — atomare Geldflüsse.

Jeder Vollzug:
- bucht Geldflüsse SOFORT über die Finanz-Buchungsschicht (book_many),
- verteilt die Jugendabgabe (youth_levy als Single Source of Truth),
- erzeugt genau einen TransferRecord,
- setzt für alle wechselnden Spieler die 21-Tage-Wechselsperre,
- bewegt den Spieler sofort (SOFORT) oder legt einen PendingTransfer an (WP/SE).

Race-Safety: Aufrufer (services.py) hält bereits die Listing-/Deal- und
Club-Locks; hier werden zusätzlich die Spielerzeilen re-validiert.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from game.economy.booking import book_many
from game.economy.params import get_param

from . import youth_levy
from .models import (
    Loan, PendingTransfer, TransferListing, TransferLock,
    TransferRecord, TransferRecordPlayer, YouthLevyPayment,
)

CENT = Decimal('0.01')


class ExecutionError(Exception):
    """Fachlicher Vollzugsfehler (deutsche Meldung für die UI)."""


def _q(v):
    return Decimal(str(v)).quantize(CENT)


def _lock_days(saison=None):
    return int(get_param('TRANSFER_WECHSELSPERRE_TAGE', saison))


def _set_transfer_lock(player, record, saison=None):
    """Setzt die 21-Tage-Wechselsperre (Feld + persistente TransferLock-Zeile)."""
    until = timezone.localdate() + timezone.timedelta(days=_lock_days(saison))
    player.transfer_locked_until = until
    player.save(update_fields=['transfer_locked_until'])
    TransferLock.objects.create(
        player=player, locked_until=until, source_record=record,
    )
    return until


def _move_player(player, new_club):
    """Setzt den Spieler sofort um und räumt Verkaufsmarkierungen ab."""
    player.club = new_club
    player.is_on_transfer_list = False
    player.is_on_loan_list = False
    player.sale_category = 'UVK'
    player.sale_visible_to_ai = False
    player.save(update_fields=[
        'club', 'is_on_transfer_list', 'is_on_loan_list',
        'sale_category', 'sale_visible_to_ai',
    ])


def _levy_entries_and_payments(record, player, zahler_club, verteilung,
                               locked, *, saison, spieltag):
    """Buchungszeilen (AUS/EIN) + YouthLevyPayment-Zeilen der Abgabe."""
    entries = []
    payments = []
    betraege = verteilung['betraege_je_ausbildungsverein']
    if not betraege:
        return entries, payments
    gesamt = verteilung['summe']
    entries.append({
        'club': locked[zahler_club.pk], 'typ': 'AUSBILDUNG_AUS',
        'betrag': -gesamt, 'beschreibung': f'Jugendabgabe {player.full_name}',
        'saison': saison, 'spieltag': spieltag,
        'referenz_typ': 'transfer_v2', 'referenz_id': player.pk,
        'pflicht': True,  # Folge des Transfers, durch Ablöse gedeckt.
    })
    for club_id, betrag in sorted(betraege.items()):
        entries.append({
            'club': locked[club_id], 'typ': 'AUSBILDUNG_EIN',
            'betrag': betrag, 'beschreibung': f'Jugendabgabe {player.full_name}',
            'saison': saison, 'spieltag': spieltag,
            'referenz_typ': 'transfer_v2', 'referenz_id': player.pk,
        })
        payments.append({
            'record': record, 'player': player,
            'payer_club_id': zahler_club.pk, 'receiver_club_id': club_id,
            'percent': verteilung['gesamt_pct'], 'amount': betrag,
        })
    return entries, payments


def execute_purchase(listing, buyer, amount, *, timing, saison=None,
                     spieltag=None, kind=TransferRecord.KIND_CASH):
    """Vollzieht einen (Sofort-)Kauf eines Listings.

    Geld fließt IMMER sofort. Bei timing=WP/SE wird der Spielerwechsel als
    PendingTransfer aufgeschoben; der TransferRecord entsteht dennoch sofort
    (Historie-Eintrag). Erwartet einen bereits gehaltenen Listing-Lock.

    Vereinslos (listing.seller is None): Erlös an den Verband (Systemsenke),
    keine Jugendabgabe, Wechsel immer sofort.
    """
    from game.models import Club, Player

    player = listing.player
    amount = _q(amount)
    is_free_agent = listing.seller_id is None
    seller = None if is_free_agent else listing.seller

    with transaction.atomic():
        aktuell = Player.objects.select_for_update().get(pk=player.pk)
        if not is_free_agent and aktuell.club_id != seller.pk:
            raise ExecutionError('Der Spieler hat den Verein bereits verlassen.')
        if is_free_agent and aktuell.club_id is not None:
            raise ExecutionError('Der Spieler ist nicht mehr vereinslos.')
        # Re-Validierung unter Spieler-Lock: Leihspieler dürfen nicht
        # verkauft werden (player.club ist beim Leihen der aufnehmende
        # Verein, nicht der Eigentümer).
        from .models import Loan
        if aktuell.loan_status in ('loaned_in', 'loaned_out') or (
                Loan.objects.filter(
                    player=aktuell, ended_at__isnull=True).exists()):
            raise ExecutionError('Der Spieler ist verliehen.')
        # Wechselsperre/Pending können NACH Listing-Erstellung entstanden
        # sein (z. B. parallel angenommener Deal) — zum Settlement erneut
        # unter Spieler-Lock prüfen.
        if aktuell.is_transfer_locked:
            raise ExecutionError('Der Spieler ist wechselgesperrt.')
        if PendingTransfer.objects.filter(
                player=aktuell,
                status=PendingTransfer.STATUS_PENDING).exists():
            raise ExecutionError(
                'Der Spieler hat bereits einen ausstehenden Transfer.')

        if is_free_agent:
            verteilung = youth_levy.calc_youth_levy(
                player, 0, zahler_club=None, saison=saison,
            )  # → leer, keine Abgabe.
        else:
            verteilung = youth_levy.calc_youth_levy(
                player, amount, zahler_club=seller, saison=saison,
            )

        # ALLE beteiligten Vereinszeilen ZUERST sperren (stabile PK-Ordnung),
        # DANACH erst Kadergrenzen zählen: die Club-Zeilensperre serialisiert
        # konkurrierende Settlements desselben Vereins, sonst könnten zwei
        # parallele Käufe denselben letzten Kaderplatz doppelt vergeben bzw.
        # zwei parallele Verkäufe den Mindestkader gemeinsam unterschreiten.
        club_ids = [buyer.pk]
        if seller is not None:
            club_ids.append(seller.pk)
        club_ids += list(verteilung['betraege_je_ausbildungsverein'])
        locked = {
            c.pk: c for c in Club.objects.select_for_update()
            .filter(pk__in=sorted(set(club_ids))).order_by('pk')
        }

        # Kadergrenzen zum Settlement (Spec Kap. 9.1) — unter Club-Lock:
        # Käufer braucht Platz, Verkäufer darf nicht unter den Mindestkader
        # fallen. (WP/SE-Vollzug via execute_pending prüft am Stichtag.)
        from game.economy.kader import (effective_squad_limit,
                                        min_squad_size, squad_count)
        buyer_locked = locked[buyer.pk]
        if squad_count(buyer_locked) + 1 > effective_squad_limit(
                buyer_locked, saison):
            raise ExecutionError(
                f'{buyer.name} hat keinen freien Kaderplatz '
                f'(Limit {effective_squad_limit(buyer_locked, saison)}).')
        if seller is not None and (
                squad_count(locked[seller.pk]) - 1 < min_squad_size(saison)):
            raise ExecutionError(
                f'{seller.name} würde unter den Mindestkader von '
                f'{min_squad_size(saison)} Spielern fallen.')

        mw = _q(aktuell.market_value) if aktuell.market_value is not None else None
        text = f'Transfer {player.full_name}'
        entries = [{
            'club': locked[buyer.pk], 'typ': 'TRANSFER_AUS',
            'betrag': -amount, 'beschreibung': text,
            'saison': saison, 'spieltag': spieltag,
            'referenz_typ': 'transfer_v2', 'referenz_id': player.pk,
            'referenz_mw': mw,
        }]
        if is_free_agent:
            # Erlös an den Verband: Geldvernichtungs-Senke (kein Empfänger-Konto).
            entries.append({
                'club': locked[buyer.pk], 'typ': 'VERBANDSABGABE',
                'betrag': Decimal('0.00'),  # reine Kennzeichnung, Betrag oben.
                'beschreibung': f'Vereinsloser-Erlös an Verband {player.full_name}',
                'saison': saison, 'spieltag': spieltag,
                'referenz_typ': 'transfer_v2', 'referenz_id': player.pk,
            })
        else:
            entries.append({
                'club': locked[seller.pk], 'typ': 'TRANSFER_EIN',
                'betrag': amount, 'beschreibung': text,
                'saison': saison, 'spieltag': spieltag,
                'referenz_typ': 'transfer_v2', 'referenz_id': player.pk,
                'referenz_mw': mw,
            })

        record = TransferRecord.objects.create(
            kind=(TransferRecord.KIND_FREE if is_free_agent else kind),
            timing=timing, club_a=seller, club_b=buyer,
            cash_a=Decimal('0'), cash_b=amount,
        )
        levy_entries, payments = _levy_entries_and_payments(
            record, player, seller, verteilung, locked,
            saison=saison, spieltag=spieltag,
        ) if seller is not None else ([], [])
        book_many(entries + levy_entries, saison=saison)
        for p in payments:
            YouthLevyPayment.objects.create(**p)
        TransferRecordPlayer.objects.create(
            record=record, player=player,
            side=TransferRecordPlayer.SIDE_A, market_value_at_transfer=mw,
        )

        immediate = is_free_agent or timing == TransferListing.TIMING_SOFORT
        if immediate:
            _move_player(aktuell, buyer)
            _set_transfer_lock(aktuell, record, saison)
        else:
            _create_pending(aktuell, seller, buyer, timing, record,
                            PendingTransfer.SOURCE_LISTING, saison)

        if seller is not None:
            buyer.budget = locked[buyer.pk].budget
    return record


def execute_option_purchase(loan, *, buyer_club=None, saison=None,
                            spieltag=None):
    """Zieht die Kaufoption einer aktiven Leihe (Vollkauf durch Leihverein).

    Validiert unter Locks: Leihe aktiv, Option vereinbart, Aufrufer ist der
    Leihverein, Spieler noch beim Leihverein, Deckung (escrow-bewusst).
    Bucht Ablöse + Jugendabgabe, beendet die Leihe, macht den Spieler zum
    festen Vereinsspieler, setzt die Wechselsperre und schreibt einen
    OPTION-TransferRecord.
    """
    from game.models import Club, Player

    from . import escrow

    with transaction.atomic():
        l = Loan.objects.select_for_update().get(pk=loan.pk)
        if l.ended_at is not None:
            raise ExecutionError('Die Leihe ist bereits beendet.')
        if l.buy_option is None:
            raise ExecutionError('Diese Leihe hat keine Kaufoption.')
        if buyer_club is not None and buyer_club.pk != l.loan_club_id:
            raise ExecutionError(
                'Nur der Leihverein kann die Kaufoption ziehen.')
        price = _q(l.buy_option)

        player = Player.objects.select_for_update().get(pk=l.player_id)
        if player.club_id != l.loan_club_id:
            raise ExecutionError('Der Spieler ist nicht mehr beim Leihverein.')
        if PendingTransfer.objects.filter(
                player=player,
                status=PendingTransfer.STATUS_PENDING).exists():
            raise ExecutionError(
                'Der Spieler hat bereits einen ausstehenden Transfer.')

        # Jugendabgabe: Zahler = abgebender Stammverein, Basis = Optionspreis.
        verteilung = youth_levy.calc_youth_levy(
            player, price, zahler_club=l.owner_club, saison=saison,
        )
        club_ids = sorted({l.owner_club_id, l.loan_club_id}
                          | set(verteilung['betraege_je_ausbildungsverein']))
        locked = {
            c.pk: c for c in Club.objects.select_for_update()
            .filter(pk__in=club_ids).order_by('pk')
        }
        buyer = locked[l.loan_club_id]
        owner = locked[l.owner_club_id]
        if escrow.available(buyer) < price:
            raise ExecutionError(
                'Nicht genügend verfügbares Budget für die Kaufoption.')

        mw = _q(player.market_value) if player.market_value is not None else None
        text = f'Kaufoption gezogen {player.full_name}'
        record = TransferRecord.objects.create(
            kind=TransferRecord.KIND_OPTION, timing='SOFORT',
            club_a=owner, club_b=buyer,
            cash_a=Decimal('0'), cash_b=price,
        )
        entries = [
            {'club': buyer, 'typ': 'TRANSFER_AUS', 'betrag': -price,
             'beschreibung': text, 'saison': saison, 'spieltag': spieltag,
             'referenz_typ': 'transfer_v2', 'referenz_id': player.pk,
             'referenz_mw': mw},
            {'club': owner, 'typ': 'TRANSFER_EIN', 'betrag': price,
             'beschreibung': text, 'saison': saison, 'spieltag': spieltag,
             'referenz_typ': 'transfer_v2', 'referenz_id': player.pk,
             'referenz_mw': mw},
        ]
        levy_entries, payments = _levy_entries_and_payments(
            record, player, owner, verteilung, locked,
            saison=saison, spieltag=spieltag,
        )
        book_many(entries + levy_entries, saison=saison)
        for p in payments:
            YouthLevyPayment.objects.create(**p)
        TransferRecordPlayer.objects.create(
            record=record, player=player,
            side=TransferRecordPlayer.SIDE_A, market_value_at_transfer=mw,
        )

        # Leihe beenden, Spieler wird fester Vereinsspieler des Käufers.
        l.ended_at = timezone.now()
        l.save(update_fields=['ended_at'])
        player.loan_status = ''
        player.loan_partner_club = None
        player.save(update_fields=['loan_status', 'loan_partner_club'])
        _move_player(player, buyer)
        _set_transfer_lock(player, record, saison)
    return record


def _wp_se_date(timing):
    """Fixes WP-/SE-Vollzugsdatum aus dem Spielplan (Näherung: heute + Puffer).

    Bis die Spielplan-Generierung feste WP-/SE-Daten liefert, wird ein
    deterministisches Platzhalterdatum genutzt; der Job execute_pending_transfers
    zieht ausschließlich Zeilen mit execute_at <= heute.
    """
    from .calendar_dates import next_execution_date
    return next_execution_date(timing)


def _create_pending(player, from_club, to_club, timing, record, source, saison):
    PendingTransfer.objects.create(
        player=player, from_club=from_club, to_club=to_club,
        execute_at=_wp_se_date(timing), source=source, record=record,
    )
    # Bis zum Stichtag kein erneutes Listen/Verkaufen/Verleihen.
    player.is_on_transfer_list = False
    player.is_on_loan_list = False
    player.save(update_fields=['is_on_transfer_list', 'is_on_loan_list'])


def execute_pending(pending, *, saison=None):
    """Vollzieht einen fälligen PendingTransfer (WP/SE-Stichtag) als
    SETTLEMENT-EINHEIT: Alle PENDING-Geschwister desselben TransferRecords
    (Mehrspieler-Deal) werden gemeinsam gesperrt, gemeinsam geprüft und
    entweder ALLE vollzogen oder ALLE storniert — nie einseitig.

    Kadergrenzen sind am Stichtag HART und werden über den NETTO-Effekt
    aller Beine je Verein geprüft. Bei Verstoß wird die gesamte Einheit
    deterministisch storniert (STATUS_CANCELLED_LIMIT): alle Geldflüsse
    werden je Bein zurückerstattet (Pflichtbuchung), Jugendabgaben
    rückabgewickelt, die Spieler bleiben bei ihren abgebenden Vereinen und
    beide Vereine werden benachrichtigt. Ein Wechsel wird NIE über das
    Limit vollzogen.
    """
    from game.economy.kader import (effective_squad_limit, min_squad_size,
                                    squad_count)
    from game.models import Player

    with transaction.atomic():
        p = PendingTransfer.objects.select_for_update().get(pk=pending.pk)
        if p.status != PendingTransfer.STATUS_PENDING:
            return p

        # Settlement-Einheit: alle PENDING-Beine desselben Records.
        if p.record_id:
            gruppe = list(
                PendingTransfer.objects.select_for_update()
                .filter(record_id=p.record_id,
                        status=PendingTransfer.STATUS_PENDING)
                .order_by('pk')
            )
        else:
            gruppe = [p]

        # Alle Spielerzeilen der Einheit sperren (feste Reihenfolge).
        spieler = {
            pl.pk: pl for pl in Player.objects.select_for_update()
            .filter(pk__in=sorted({g.player_id for g in gruppe}))
            .order_by('pk')
        }

        # ALLE beteiligten Vereinszeilen sperren (stabile PK-Ordnung),
        # BEVOR Kaderstände gezählt werden: die Club-Zeilensperre
        # serialisiert konkurrierende Settlements desselben Vereins —
        # sonst könnten zwei fällige Einheiten denselben letzten
        # Kaderplatz doppelt vergeben.
        from game.models import Club
        beteiligte_ids = set()
        for g in gruppe:
            beteiligte_ids.add(g.to_club_id)
            if g.from_club_id:
                beteiligte_ids.add(g.from_club_id)
        club_locked = {
            c.pk: c for c in Club.objects.select_for_update()
            .filter(pk__in=sorted(beteiligte_ids)).order_by('pk')
        }

        # Spielerzustand ALLER Beine unter Lock re-validieren: Der Spieler
        # muss noch beim abgebenden Verein sein, darf nicht (anderweitig)
        # wechselgesperrt oder verliehen sein. Ein zwischenzeitlicher
        # legitimer Zustandswechsel darf am Stichtag NIE überschrieben
        # werden — stattdessen wird die gesamte Einheit storniert.
        konflikt = None
        for g in gruppe:
            pl = spieler[g.player_id]
            if g.from_club_id is not None and pl.club_id != g.from_club_id:
                konflikt = f'{pl.full_name} ist nicht mehr beim abgebenden Verein.'
                break
            if pl.is_transfer_locked:
                konflikt = f'{pl.full_name} ist wechselgesperrt.'
                break
            if pl.loan_status in ('loaned_in', 'loaned_out') or (
                    Loan.objects.filter(
                        player=pl, ended_at__isnull=True).exists()):
                konflikt = f'{pl.full_name} ist verliehen.'
                break

        # Netto-Kadereffekt je Verein über ALLE Beine — gezählt wird
        # ausschließlich gegen die GESPERRTEN Club-Zeilen.
        if konflikt is None:
            delta = {}
            for g in gruppe:
                delta[g.to_club_id] = delta.get(g.to_club_id, 0) + 1
                if g.from_club_id:
                    delta[g.from_club_id] = delta.get(g.from_club_id, 0) - 1

            for cid, d in delta.items():
                club = club_locked[cid]
                danach = squad_count(club) + d
                if d > 0 and danach > effective_squad_limit(club, saison):
                    konflikt = f'{club.name}: Kaderlimit überschritten.'
                    break
                if d < 0 and danach < min_squad_size(saison):
                    konflikt = f'{club.name}: Mindestkader unterschritten.'
                    break

        if konflikt is not None:
            for g in gruppe:
                _cancel_pending_over_limit(g, saison=saison, grund=konflikt)
            return p

        for g in gruppe:
            player = spieler[g.player_id]
            _move_player(player, g.to_club)
            _set_transfer_lock(player, g.record, saison)
            g.status = PendingTransfer.STATUS_EXECUTED
            g.executed_at = timezone.now()
            g.save(update_fields=['status', 'executed_at'])
    return p


def _cancel_pending_over_limit(p, *, saison=None, grund=''):
    """Storniert einen Pending am Stichtag (Kadergrenzen-/Zustandskonflikt).

    Rückerstattung: Der Käufer erhält den auf diesen Spieler entfallenden
    Kaufpreis zurück (Listing = voller Betrag; Deal = Anteil je Side-A/B-
    Spieler), der Verkäufer zahlt ihn zurück (Pflichtbuchung — darf ins
    Minus, Insolvenzpfad greift regulär). Bereits gebuchte Jugendabgaben
    dieses Spielers werden rückabgewickelt.
    """
    from game.models import Club

    record = p.record
    refund = Decimal('0.00')
    if record is not None and p.from_club is not None:
        # Anteil dieses Spielers am Geldfluss seiner Richtung: Spieler lief
        # von from_club → to_club. SIDE_A-Spieler gehen A→B (B zahlte
        # cash_b), SIDE_B-Spieler gehen B→A (A zahlte cash_a).
        if record.club_b_id == p.to_club_id:
            gesamt = _q(record.cash_b)
            seite = TransferRecordPlayer.SIDE_A
        else:
            gesamt = _q(record.cash_a)
            seite = TransferRecordPlayer.SIDE_B
        side_players = record.players.filter(side=seite).count() or 1
        refund = _q(gesamt / side_players)

    entries = []
    club_ids = {p.to_club_id}
    if p.from_club_id:
        club_ids.add(p.from_club_id)
    levies = list(YouthLevyPayment.objects.filter(
        record=record, player=p.player)) if record else []
    for lev in levies:
        club_ids.add(lev.payer_club_id)
        club_ids.add(lev.receiver_club_id)
    locked = {
        c.pk: c for c in Club.objects.select_for_update()
        .filter(pk__in=sorted(club_ids)).order_by('pk')
    }

    text = f'Storno WP/SE-Transfer {p.player.full_name} (Kadergrenze)'
    if refund > 0 and p.from_club_id:
        entries += [
            {'club': locked[p.from_club_id], 'typ': 'TRANSFER_AUS',
             'betrag': -refund, 'beschreibung': text, 'saison': saison,
             'referenz_typ': 'transfer_v2_storno', 'referenz_id': p.pk,
             'pflicht': True},
            {'club': locked[p.to_club_id], 'typ': 'TRANSFER_EIN',
             'betrag': refund, 'beschreibung': text, 'saison': saison,
             'referenz_typ': 'transfer_v2_storno', 'referenz_id': p.pk},
        ]
    for lev in levies:
        entries += [
            {'club': locked[lev.receiver_club_id], 'typ': 'AUSBILDUNG_AUS',
             'betrag': -_q(lev.amount), 'beschreibung': text,
             'saison': saison, 'referenz_typ': 'transfer_v2_storno',
             'referenz_id': p.pk, 'pflicht': True},
            {'club': locked[lev.payer_club_id], 'typ': 'AUSBILDUNG_EIN',
             'betrag': _q(lev.amount), 'beschreibung': text,
             'saison': saison, 'referenz_typ': 'transfer_v2_storno',
             'referenz_id': p.pk},
        ]
    if entries:
        book_many(entries, saison=saison)
    if levies:
        YouthLevyPayment.objects.filter(
            pk__in=[lev.pk for lev in levies]).delete()

    p.status = PendingTransfer.STATUS_CANCELLED_LIMIT
    p.executed_at = timezone.now()
    p.save(update_fields=['status', 'executed_at'])

    # Kadergrenzen-Vermerk je betroffenem Verein anlegen (additiv).
    from .models import SquadLimitNote
    note_text = (f'WP/SE-Transfer {p.player.full_name} storniert: '
                 f'{grund or "Kadergrenzen am Stichtag verletzt."} '
                 f'Erstattung: {refund:,.2f} €.')
    SquadLimitNote.objects.create(
        club=p.to_club, player=p.player, text=note_text,
    )
    if p.from_club:
        SquadLimitNote.objects.create(
            club=p.from_club, player=p.player, text=note_text,
        )

    # Pushes über den zentralen Nach-Commit-Dispatch des Push-Katalogs —
    # ein Benachrichtigungs-Fehler darf Storno + Erstattung NIE zurückrollen.
    from . import push
    msg = (f'Der WP/SE-Wechsel von {p.player.full_name} wurde storniert: '
           f'{grund or "Kadergrenzen am Stichtag verletzt."} '
           f'Erstattung: {refund:,.2f} €.')
    push.pending_cancelled_limit(p.to_club, msg)
    if p.from_club:
        push.pending_cancelled_limit(p.from_club, msg)
