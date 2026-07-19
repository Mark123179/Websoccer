"""Verbandsabgabe (Spec Kap. 12.5) — Geldvernichtungs-Senke, HART DEAKTIVIERT.

Reichensteuer gegen Geldhortung: Übersteigt der Kontostand eines Vereins
das FAKTOR-fache seines Jahresumsatzes (positive Ledger-Summe der laufenden
Saison), wird auf den Überschuss eine Abgabe von SATZ erhoben und als
Pflichtbuchung (Typ VERBANDSABGABE, Geld verlässt das System) gebucht.

    abgabe = SATZ × (kontostand − FAKTOR × jahresumsatz)   [nur wenn > 0]

Alle Werte leben im EconomyParameter VERBANDSABGABE (Seed: enabled=False,
faktor=2.0, satz=0.10). Der Runner verweigert die Ausführung HART, solange
enabled nicht explizit auf True gesetzt wurde — die Senke ist Phase-5-
Infrastruktur und wird erst nach Balancing-Freigabe scharfgeschaltet.
"""
from decimal import Decimal

from django.db.models import Sum

from .booking import book
from .params import get_param


class VerbandsabgabeDisabled(Exception):
    """Die Verbandsabgabe ist per EconomyParameter deaktiviert."""


def _config(saison=None):
    cfg = get_param('VERBANDSABGABE', saison)
    if not isinstance(cfg, dict):
        raise ValueError('EconomyParameter VERBANDSABGABE muss ein Dict sein.')
    return cfg


def is_enabled(saison=None) -> bool:
    return bool(_config(saison).get('enabled', False))


def jahresumsatz(club, saison) -> Decimal:
    """Jahresumsatz = Summe aller positiven Buchungen der Saison."""
    from game.models import FinanceTransaction

    total = (
        FinanceTransaction.objects
        .filter(club=club, saison=str(saison), betrag__gt=0)
        .aggregate(s=Sum('betrag'))['s']
    )
    return total or Decimal('0.00')


def berechne_abgabe(kontostand, umsatz, *, faktor, satz) -> Decimal:
    """Abgabe = satz × (kontostand − faktor × umsatz), gekappt bei 0."""
    kontostand = Decimal(str(kontostand or 0))
    umsatz = Decimal(str(umsatz or 0))
    ueberschuss = kontostand - Decimal(str(faktor)) * umsatz
    if ueberschuss <= 0:
        return Decimal('0.00')
    return (Decimal(str(satz)) * ueberschuss).quantize(Decimal('0.01'))


def run_verbandsabgabe(saison, *, dry_run=False):
    """Erhebt die Verbandsabgabe für alle Vereine — verweigert hart bei disabled.

    Gibt eine Liste von Dicts (club, umsatz, abgabe) für alle Vereine mit
    Abgabe > 0 zurück. Buchung als Pflichtbuchung (kann ins Minus führen —
    dann greift das Zahlungsunfähigkeits-Verfahren, Spec Kap. 12.3).
    """
    from game.models import Club

    saison = str(saison)
    cfg = _config(saison)
    if not cfg.get('enabled', False):
        raise VerbandsabgabeDisabled(
            'Die Verbandsabgabe ist deaktiviert (EconomyParameter '
            'VERBANDSABGABE.enabled=False). Aktivierung nur nach '
            'expliziter Balancing-Freigabe.'
        )
    faktor = cfg.get('faktor', 2.0)
    satz = cfg.get('satz', 0.10)

    ergebnisse = []
    for club in Club.objects.filter(budget__isnull=False).order_by('pk'):
        umsatz = jahresumsatz(club, saison)
        abgabe = berechne_abgabe(club.budget, umsatz, faktor=faktor, satz=satz)
        if abgabe <= 0:
            continue
        ergebnisse.append({'club': club, 'umsatz': umsatz, 'abgabe': abgabe})
        if not dry_run:
            book(
                club, 'VERBANDSABGABE', -abgabe,
                beschreibung=(
                    f'Verbandsabgabe Saison {saison}: {satz:.0%} auf '
                    f'Überschuss über {faktor}× Jahresumsatz'
                ),
                saison=saison,
                pflicht=True,
            )
    return ergebnisse
