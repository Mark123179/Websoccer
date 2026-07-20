"""Transferabwicklung + Ausbildungsabgabe (Spec Kap. 9.1).

Drei Abwicklungspfade, jeweils atomar in EINER DB-Transaktion:
  - execute_money_transfer: Geldtransfer (TRANSFER_AUS/EIN + Abgabe)
  - execute_free_transfer:  ablösefreier Wechsel (Abgabe auf MW, zahlt Aufnehmer)
  - execute_swap:           Manager-zu-Manager-Tausch (Abgabe je Spieler)

Ausbildungsabgabe (AUSBILDUNGSABGABE, 5 %): Verteilrechnung aus
PlayerClubHistory. Ausbildungszeitraum = Saisons ab Sim-Eintritt bis
einschließlich der Saison des 21. Geburtstags (Näherung über das
gespeicherte Alter: cutoff = saison + (21 − age)). Pro angefangener Saison
je Verein ein gleicher Anteil. Es wird kein Geld vernichtet: Nur
auszahlbare Fremdanteile werden erhoben — Anteile des Zahlers selbst und
Anteile ohne Empfänger entfallen ersatzlos (Spec-Beispiele Koloto).

Nebenläufigkeit: Alle beteiligten Vereinszeilen werden VOR den Prüfungen
in fester Reihenfolge gesperrt (kleinere Club-ID zuerst, Spec Kap. 12.4 —
identisch zur book_many-Sperrreihenfolge, Deadlock-Lehre Scouting V1).
"""
from decimal import Decimal

from django.db import transaction

from .booking import book_many
from .params import get_decimal


class TransferError(Exception):
    """Fachlicher Transferfehler (deutsche Meldung für die UI)."""


class KaderVoll(TransferError):
    pass


class MindestkaderUnterschritten(TransferError):
    pass


def _saison_int(saison):
    from game.finance import current_sim_season
    s = str(saison) if saison is not None else (current_sim_season() or '0')
    try:
        return int(s), s
    except (TypeError, ValueError):
        return 0, s


def mw_basis(player, saison=None):
    """Abgabe-Basis bei ablösefrei/Tausch: aktueller MW, geclampt auf MW_MINIMUM."""
    minimum = get_decimal('MW_MINIMUM', saison)
    mw = player.market_value
    if mw is None:
        return minimum
    return max(Decimal(str(mw)), minimum)


def compute_ausbildungsabgabe(player, zahler_club, basis, saison=None):
    """Verteilrechnung der Ausbildungsabgabe (reine Leserechnung).

    Returns:
        dict mit
          'empfaenger': {club_id: Decimal-Betrag} — nur Fremdempfänger,
          'gesamt': Decimal — Summe der tatsächlich erhobenen Anteile,
          'anteile_gesamt': int, 'anteile_fremd': int.
    """
    from game.models import PlayerClubHistory

    leer = {'empfaenger': {}, 'gesamt': Decimal('0.00'),
            'anteile_gesamt': 0, 'anteile_fremd': 0}

    basis = Decimal(str(basis))
    if basis <= 0:
        return leer

    saison_num, saison_str = _saison_int(saison)
    rate = get_decimal('AUSBILDUNGSABGABE', saison_str)
    cutoff = saison_num + (21 - int(player.age))

    stationen = list(
        PlayerClubHistory.objects
        .filter(player=player, season__lte=cutoff)
        .values_list('club_id', flat=True)
    )
    n = len(stationen)
    if n == 0:
        return leer  # Keine Sim-Ausbildungshistorie → keine Abgabe.

    abgabe_gesamt = rate * basis
    anteil = abgabe_gesamt / n

    zahler_id = zahler_club.pk if zahler_club is not None else None
    counts = {}
    for club_id in stationen:
        if club_id == zahler_id:
            continue  # Eigenanteil des Zahlers wird nie erhoben.
        counts[club_id] = counts.get(club_id, 0) + 1

    empfaenger = {
        club_id: (anteil * cnt).quantize(Decimal('0.01'))
        for club_id, cnt in counts.items()
    }
    gesamt = sum(empfaenger.values(), Decimal('0.00'))
    return {
        'empfaenger': empfaenger,
        'gesamt': gesamt,
        'anteile_gesamt': n,
        'anteile_fremd': sum(counts.values()),
    }


def _lock_clubs(club_ids):
    """Sperrt Vereinszeilen in fester Reihenfolge (kleinere ID zuerst)."""
    from game.models import Club
    ids = sorted(set(club_ids))
    return {
        c.pk: c
        for c in Club.objects.select_for_update().filter(pk__in=ids).order_by('pk')
    }


def _check_kaderplatz(club, saison=None):
    from .kader import effective_squad_limit, squad_count
    limit = effective_squad_limit(club, saison)
    if squad_count(club) >= limit:
        raise KaderVoll(
            f'{club.name} hat keinen freien Kaderplatz (Limit {limit}).'
        )


def _check_mindestkader(club, saison=None):
    from .kader import min_squad_size, squad_count
    minimum = min_squad_size(saison)
    if squad_count(club) - 1 < minimum:
        raise MindestkaderUnterschritten(
            f'{club.name} würde unter den Mindestkader von {minimum} Spielern fallen.'
        )


def _abgabe_entries(zahler_club, verteilung, locked, *, player, saison,
                    spieltag, pflicht, beschreibung):
    """Buchungszeilen der Abgabe (AUS beim Zahler, EIN je Empfänger)."""
    entries = []
    if verteilung['gesamt'] <= 0:
        return entries
    entries.append({
        'club': locked[zahler_club.pk], 'typ': 'AUSBILDUNG_AUS',
        'betrag': -verteilung['gesamt'], 'beschreibung': beschreibung,
        'saison': saison, 'spieltag': spieltag,
        'referenz_typ': 'transfer', 'referenz_id': player.pk,
        'pflicht': pflicht,
    })
    for club_id, betrag in sorted(verteilung['empfaenger'].items()):
        entries.append({
            'club': locked[club_id], 'typ': 'AUSBILDUNG_EIN',
            'betrag': betrag, 'beschreibung': beschreibung,
            'saison': saison, 'spieltag': spieltag,
            'referenz_typ': 'transfer', 'referenz_id': player.pk,
        })
    return entries


def _complete_move(player, new_club):
    """Spieler umsetzen; Verkaufsmarkierungen zurücksetzen.

    club_history-Tracking läuft automatisch über das save-Signal
    (kein _suppress_club_history — der Wechsel SOLL eine Station erzeugen).
    Offene KI-Kaufangebote auf den Spieler werden storniert — sie galten
    dem Ex-Verein (Phase 6, Spec Kap. 9.3).
    """
    player.club = new_club
    player.is_on_transfer_list = False
    player.is_on_loan_list = False
    player.sale_category = 'UVK'
    player.sale_visible_to_ai = False
    player.save(update_fields=[
        'club', 'is_on_transfer_list', 'is_on_loan_list',
        'sale_category', 'sale_visible_to_ai',
    ])
    from .ai_buyer.offers import storniere_offene_fuer_spieler
    storniere_offene_fuer_spieler(player)


def execute_money_transfer(player, kaeufer, abloese, *, saison=None,
                           spieltag=None):
    """Geldtransfer: Käufer zahlt voll, Verkäufer erhält Ablöse − Abgabe.

    Buchungsreihenfolge: TRANSFER_EIN vor AUSBILDUNG_AUS, damit der
    Verkäufer die Abgabe aus der frischen Ablöse decken kann; die Abgabe
    selbst ist Pflichtfolge des Transfers (pflicht=True — sie ist durch
    die Ablöse stets gedeckt, darf aber ein Minus-Konto nicht blockieren).
    """
    verkaeufer = player.club
    if verkaeufer is None:
        raise TransferError('Spieler hat keinen Verein — ablösefreier Pfad nutzen.')
    if kaeufer.pk == verkaeufer.pk:
        raise TransferError('Käufer und Verkäufer sind identisch.')
    abloese = Decimal(str(abloese)).quantize(Decimal('0.01'))
    if abloese < 0:
        raise TransferError('Ablöse darf nicht negativ sein.')

    _, saison_str = _saison_int(saison)

    with transaction.atomic():
        verteilung = compute_ausbildungsabgabe(
            player, verkaeufer, abloese, saison_str,
        )
        locked = _lock_clubs(
            [kaeufer.pk, verkaeufer.pk] + list(verteilung['empfaenger'])
        )
        # Doppelkauf-Schutz: Spielerzeile NACH den Club-Locks sperren und
        # die Vereinszugehörigkeit re-validieren (ein paralleler Transfer
        # eines anderen Bieters kann den Spieler bereits bewegt haben).
        from game.models import Player
        aktuell = Player.objects.select_for_update().get(pk=player.pk)
        if aktuell.club_id != verkaeufer.pk:
            raise TransferError('Der Spieler hat den Verein bereits verlassen.')
        _check_kaderplatz(locked[kaeufer.pk], saison_str)
        _check_mindestkader(locked[verkaeufer.pk], saison_str)

        mw_snapshot = (
            Decimal(str(aktuell.market_value)).quantize(Decimal('0.01'))
            if aktuell.market_value is not None else None
        )
        text = f'Transfer {player.full_name}'
        entries = [
            {'club': locked[kaeufer.pk], 'typ': 'TRANSFER_AUS',
             'betrag': -abloese, 'beschreibung': text,
             'saison': saison_str, 'spieltag': spieltag,
             'referenz_typ': 'transfer', 'referenz_id': player.pk,
             'referenz_mw': mw_snapshot},
            {'club': locked[verkaeufer.pk], 'typ': 'TRANSFER_EIN',
             'betrag': abloese, 'beschreibung': text,
             'saison': saison_str, 'spieltag': spieltag,
             'referenz_typ': 'transfer', 'referenz_id': player.pk,
             'referenz_mw': mw_snapshot},
        ] + _abgabe_entries(
            verkaeufer, verteilung, locked, player=player,
            saison=saison_str, spieltag=spieltag, pflicht=True,
            beschreibung=f'Ausbildungsabgabe {player.full_name}',
        )
        txs = book_many(entries, saison=saison_str)
        _complete_move(player, kaeufer)
        kaeufer.budget = locked[kaeufer.pk].budget
        verkaeufer.budget = locked[verkaeufer.pk].budget
    return {'transactions': txs, 'abgabe': verteilung}


def execute_free_transfer(player, aufnehmender, *, saison=None, spieltag=None):
    """Ablösefreier Wechsel: Abgabe auf den aktuellen MW, zahlt der Aufnehmer."""
    ex_club = player.club
    if ex_club is not None and ex_club.pk == aufnehmender.pk:
        raise TransferError('Spieler ist bereits bei diesem Verein.')

    _, saison_str = _saison_int(saison)

    with transaction.atomic():
        basis = mw_basis(player, saison_str)
        verteilung = compute_ausbildungsabgabe(
            player, aufnehmender, basis, saison_str,
        )
        club_ids = [aufnehmender.pk] + list(verteilung['empfaenger'])
        if ex_club is not None:
            club_ids.append(ex_club.pk)
        locked = _lock_clubs(club_ids)
        # Doppelwechsel-Schutz (analog Geldtransfer): Spielerzeile nach den
        # Club-Locks sperren und Vereinszugehörigkeit re-validieren.
        from game.models import Player
        aktuell = Player.objects.select_for_update().get(pk=player.pk)
        if aktuell.club_id != (ex_club.pk if ex_club is not None else None):
            raise TransferError('Der Spieler hat den Verein bereits gewechselt.')
        _check_kaderplatz(locked[aufnehmender.pk], saison_str)
        if ex_club is not None:
            _check_mindestkader(locked[ex_club.pk], saison_str)

        entries = _abgabe_entries(
            aufnehmender, verteilung, locked, player=player,
            saison=saison_str, spieltag=spieltag, pflicht=False,
            beschreibung=f'Ausbildungsabgabe (ablösefrei) {player.full_name}',
        )
        txs = book_many(entries, saison=saison_str) if entries else []
        _complete_move(player, aufnehmender)
        aufnehmender.budget = locked[aufnehmender.pk].budget
    return {'transactions': txs, 'abgabe': verteilung}


def execute_swap(player_a, player_b, *, saison=None, spieltag=None):
    """Manager-zu-Manager-Tausch: Abgabe (5 % auf MW) je Spieler.

    Zahler ist jeweils der ABGEBENDE Verein (Spec-Beispiel Koloto:
    ManUtd zahlt die Abgabe auf den MW des abgegebenen Koloto an Basel).
    """
    club_a, club_b = player_a.club, player_b.club
    if club_a is None or club_b is None:
        raise TransferError('Beide Spieler brauchen einen Verein.')
    if club_a.pk == club_b.pk:
        raise TransferError('Tausch innerhalb desselben Vereins ist nicht möglich.')
    if club_a.managed_by_id is None or club_b.managed_by_id is None:
        raise TransferError('Spielertausch gibt es nur zwischen Manager-Vereinen.')

    _, saison_str = _saison_int(saison)

    with transaction.atomic():
        vert_a = compute_ausbildungsabgabe(
            player_a, club_a, mw_basis(player_a, saison_str), saison_str,
        )
        vert_b = compute_ausbildungsabgabe(
            player_b, club_b, mw_basis(player_b, saison_str), saison_str,
        )
        locked = _lock_clubs(
            [club_a.pk, club_b.pk]
            + list(vert_a['empfaenger']) + list(vert_b['empfaenger'])
        )
        # Doppelwechsel-Schutz (analog Geldtransfer): beide Spielerzeilen
        # nach den Club-Locks sperren (PK-Reihenfolge) und re-validieren.
        from game.models import Player
        aktuelle = {
            p.pk: p for p in Player.objects.select_for_update()
            .filter(pk__in=[player_a.pk, player_b.pk]).order_by('pk')
        }
        if (aktuelle[player_a.pk].club_id != club_a.pk
                or aktuelle[player_b.pk].club_id != club_b.pk):
            raise TransferError('Ein Spieler hat den Verein bereits gewechselt.')
        # Kadergrößen bleiben beim Tausch konstant — keine Limit-Checks nötig.
        entries = _abgabe_entries(
            club_a, vert_a, locked, player=player_a,
            saison=saison_str, spieltag=spieltag, pflicht=False,
            beschreibung=f'Ausbildungsabgabe (Tausch) {player_a.full_name}',
        ) + _abgabe_entries(
            club_b, vert_b, locked, player=player_b,
            saison=saison_str, spieltag=spieltag, pflicht=False,
            beschreibung=f'Ausbildungsabgabe (Tausch) {player_b.full_name}',
        )
        txs = book_many(entries, saison=saison_str) if entries else []
        _complete_move(player_a, club_b)
        _complete_move(player_b, club_a)
        club_a.budget = locked[club_a.pk].budget
        club_b.budget = locked[club_b.pk].budget
    return {'transactions': txs, 'abgabe_a': vert_a, 'abgabe_b': vert_b}
