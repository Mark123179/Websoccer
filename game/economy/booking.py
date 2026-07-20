"""Zentrale Buchungsfunktion des Finanz-Ledgers (Spec Kap. 12).

Jede Kontobewegung eines Vereins läuft über book():
  - sperrt die Vereinszeile (SELECT … FOR UPDATE),
  - schreibt die FinanceTransaction-Zeile,
  - aktualisiert den Konto-Cache Club.budget
in EINER Datenbank-Transaktion. Ledger und Cache laufen so nie auseinander.

Grundregel 2 (Spec Kap. 1): Aktive Ausgaben (pflicht=False) schlagen fehl,
wenn die Deckung fehlt (InsufficientFunds). Pflichtbuchungen (Gehälter,
Betriebskosten, Unterhalt) dürfen das Konto ins Minus buchen.

Nebenläufigkeit (Spec Kap. 12.4): Bei Buchungen über mehrere Vereine
(book_many) werden die Vereinszeilen immer in fester Reihenfolge gesperrt —
kleinere Club-ID zuerst (Deadlock-Lehre aus Scouting V1).
"""
from decimal import Decimal

from django.db import transaction


class InsufficientFunds(Exception):
    """Aktive Ausgabe ohne Deckung (Grundregel 2) — Buchung abgelehnt."""

    def __init__(self, club, benoetigt, verfuegbar):
        self.club = club
        self.benoetigt = benoetigt
        self.verfuegbar = verfuegbar
        super().__init__(
            f'Deckung fehlt für {club}: benötigt {abs(benoetigt):,.2f} €, '
            f'verfügbar {verfuegbar:,.2f} €.'
        )


def _current_saison(saison):
    if saison is not None:
        return str(saison)
    from game.finance import current_sim_season
    return current_sim_season() or '0'


def _create_booking(locked, typ, betrag, *, saison, spieltag, beschreibung,
                    referenz_typ, referenz_id, datum, pflicht, referenz_mw=None):
    """Buchung gegen eine bereits gesperrte Club-Zeile schreiben."""
    from django.utils import timezone
    from game.models import FinanceTransaction

    betrag = Decimal(str(betrag)).quantize(Decimal('0.01'))
    kontostand = locked.budget if locked.budget is not None else Decimal('0.00')

    if betrag < 0 and not pflicht and kontostand + betrag < 0:
        raise InsufficientFunds(locked, betrag, kontostand)

    tx = FinanceTransaction.objects.create(
        club=locked,
        saison=saison,
        spieltag=spieltag,
        typ=typ,
        betrag=betrag,
        referenz_typ=referenz_typ or '',
        referenz_id=referenz_id,
        referenz_mw=referenz_mw,
        beschreibung=(beschreibung or '')[:200],
        datum=datum or timezone.localdate(),
    )
    locked.budget = kontostand + betrag
    locked.save(update_fields=['budget'])

    # Zahlungsunfähigkeit (Spec Kap. 12.3): Nur der Vorzeichen-Übergang
    # löst Queries aus — der heiße Buchungspfad bleibt reine Arithmetik.
    # Läuft in derselben Transaktion wie die Buchung (Club-Zeile gesperrt);
    # rollt die Buchung zurück, verschwindet auch der Vermerk.
    from game.economy import insolvency
    if pflicht and betrag < 0 and kontostand >= 0 and locked.budget < 0:
        insolvency.open_case(locked, tx)
    elif betrag > 0 and kontostand < 0 and locked.budget >= 0:
        insolvency.resolve_cases(locked)

    return tx


def book(club, typ, betrag, *, beschreibung='', saison=None, spieltag=None,
         referenz_typ='', referenz_id=None, referenz_mw=None, datum=None, pflicht=False):
    """Bucht einen Betrag auf das Vereinskonto (Ledger + Cache atomar).

    Args:
        club: Club-Instanz (wird intern per SELECT FOR UPDATE gesperrt).
        typ: Buchungstyp aus FinanceTransaction.TYP_CHOICES.
        betrag: positiv = Einnahme, negativ = Ausgabe.
        beschreibung: Verwendungszweck (Kontoauszug), max. 200 Zeichen.
        saison: Saison-String (Default: aktuelle Sim-Saison).
        spieltag: Spieltag-Nummer oder None.
        referenz_typ/referenz_id: fachlicher Verweis (z. B. "match", 4711).
        datum: Buchungsdatum (Default: heute).
        pflicht: True = Pflichtbuchung, darf ins Minus (Gehälter etc.);
                 False = aktive Ausgabe, wirft InsufficientFunds ohne Deckung.

    Returns:
        FinanceTransaction-Zeile.

    Die übergebene club-Instanz wird nach der Buchung mit dem neuen
    Kontostand aktualisiert (club.budget).
    """
    from game.models import Club

    saison = _current_saison(saison)

    with transaction.atomic():
        locked = Club.objects.select_for_update().get(pk=club.pk)
        tx = _create_booking(
            locked, typ, betrag,
            saison=saison, spieltag=spieltag, beschreibung=beschreibung,
            referenz_typ=referenz_typ, referenz_id=referenz_id,
            referenz_mw=referenz_mw, datum=datum, pflicht=pflicht,
        )
        club.budget = locked.budget
    return tx


def book_many(entries, *, saison=None):
    """Bucht mehrere Positionen (ggf. mehrere Vereine) atomar.

    entries: Liste von dicts mit denselben Keys wie book()
             (club, typ, betrag, optional beschreibung/spieltag/…).

    Sperrt alle beteiligten Vereinszeilen in fester Reihenfolge
    (kleinere Club-ID zuerst, Spec Kap. 12.4) und schreibt danach die
    Buchungen in Eingabereihenfolge. Wirft eine Buchung InsufficientFunds,
    wird die gesamte Transaktion zurückgerollt.
    """
    from game.models import Club

    saison = _current_saison(saison)
    club_ids = sorted({e['club'].pk for e in entries})

    with transaction.atomic():
        locked_map = {
            c.pk: c
            for c in Club.objects.select_for_update()
                                 .filter(pk__in=club_ids)
                                 .order_by('pk')
        }
        txs = []
        for e in entries:
            locked = locked_map[e['club'].pk]
            txs.append(_create_booking(
                locked,
                e['typ'],
                e['betrag'],
                saison=str(e.get('saison', saison)),
                spieltag=e.get('spieltag'),
                beschreibung=e.get('beschreibung', ''),
                referenz_typ=e.get('referenz_typ', ''),
                referenz_id=e.get('referenz_id'),
                referenz_mw=e.get('referenz_mw'),
                datum=e.get('datum'),
                pflicht=e.get('pflicht', False),
            ))
        for e in entries:
            e['club'].budget = locked_map[e['club'].pk].budget
    return txs
