"""Startbudgets & Genesis (Spec Kap. 13).

Startbudget = STARTBUDGET_QUOTE × projizierter Jahresumsatz (min. STARTBUDGET_MIN)
proj. Umsatz = TV-Sockel (Saisonanteil) + erwartetes Platzgeld
               (Präsidenten-Erwartung, linear degressiv) + Sponsorwert
               + Ticketschätzung (Nachfrageformel, Ø-Gegner)

Bewusst NICHT Kader-MW-basiert — sonst bekämen strukturelle
Defizitvereine die dicksten Polster.

Genesis: Beim Erst-Launch erhält jeder Bestandsverein sein Startbudget;
der Alt-Kontostand wird ERSETZT (eine KORREKTUR_ADMIN-Differenzbuchung
als erster Ledger-Eintrag). Idempotent je Verein (referenz_typ='genesis').
Vereinsübernahmen im laufenden Betrieb erhalten KEIN Startbudget.
"""
import logging
from decimal import Decimal

from .params import get_decimal, get_param

logger = logging.getLogger(__name__)


def _erwartetes_platzgeld(club, saison: str) -> Decimal:
    """Platzanteil (30 %) am erwarteten Rang der Präsidenten-Erwartung."""
    from game.season_goals import project_goal_for_club
    from .tv import liga_topf

    p = project_goal_for_club(club)
    n = max(p['league_size'], 1)
    rang = min(max(p['rank_in_league'], 1), n)

    topf = liga_topf(club.league, saison)
    platz_summe = topf * Decimal(str(get_param('TV_VERTEILUNG', saison)['platz']))
    gewicht_summe = n * (n + 1) // 2
    return (platz_summe * (n - rang + 1) / gewicht_summe).quantize(Decimal('0.01'))


def _ticketschaetzung(club, saison: str) -> Decimal:
    """Erwartete Saison-Ticketeinnahmen der Liga-Heimspiele.

    Projektion mit der vollen Nachfrageformel (Kap. 5.1) bei neutralem
    Gegnerfaktor (kein konkreter Gegner bekannt).
    """
    from .sponsors import _liga_spieltage
    from .stadium import compute_demand

    try:
        stadium = club.stadium
    except Exception:
        return Decimal('0.00')

    demand = compute_demand(club, stadium, saison=saison)
    _, heimspiele = _liga_spieltage(club, saison)
    return (demand['einnahmen_gesamt'] * heimspiele).quantize(Decimal('0.01'))


def projizierter_jahresumsatz(club, saison: str) -> Decimal:
    """Projizierter Jahresumsatz laut Startbudget-Formel (Spec Kap. 13)."""
    from .sponsors import sponsorwert, _liga_spieltage
    from .tv import tv_sockel_rate

    saison = str(saison)
    spieltage, _ = _liga_spieltage(club, saison)
    tv_sockel = tv_sockel_rate(club.league, saison) * spieltage
    return (
        tv_sockel
        + _erwartetes_platzgeld(club, saison)
        + sponsorwert(club, saison)
        + _ticketschaetzung(club, saison)
    ).quantize(Decimal('0.01'))


def startbudget(club, saison: str) -> Decimal:
    """Startbudget = Quote × proj. Umsatz, Untergrenze STARTBUDGET_MIN."""
    quote = get_decimal('STARTBUDGET_QUOTE', saison)
    minimum = get_decimal('STARTBUDGET_MIN', saison)
    wert = (quote * projizierter_jahresumsatz(club, saison)).quantize(Decimal('0.01'))
    return max(wert, minimum)


def apply_genesis(saison: str, dry_run: bool = False) -> dict:
    """Genesis-Lauf: Alt-Kontostände aller Ligavereine ersetzen.

    Je Verein: Differenzbuchung KORREKTUR_ADMIN, sodass der Kontostand
    exakt dem Startbudget entspricht. Idempotent je Verein über
    referenz_typ='genesis' — ein zweiter Lauf ist ein No-op.
    """
    from game.models import Club, FinanceTransaction
    from .booking import book

    saison = str(saison)
    report = {'saison': saison, 'clubs': [], 'skipped': [], 'errors': []}

    schon_genesis = set(
        FinanceTransaction.objects.filter(
            typ='KORREKTUR_ADMIN', referenz_typ='genesis',
        ).values_list('club_id', flat=True)
    )

    clubs = (
        Club.objects.filter(league__isnull=False)
        .select_related('league').order_by('pk')
    )
    for club in clubs:
        if club.pk in schon_genesis:
            report['skipped'].append(club.name)
            continue
        try:
            ziel = startbudget(club, saison)
            aktuell = club.budget if club.budget is not None else Decimal('0.00')
            diff = (ziel - aktuell).quantize(Decimal('0.01'))
            eintrag = {
                'club': club.name,
                'startbudget': str(ziel),
                'vorher': str(aktuell),
                'korrektur': str(diff),
            }
            if not dry_run and diff != 0:
                book(
                    club, 'KORREKTUR_ADMIN', diff,
                    beschreibung=f'Genesis-Startbudget (Kap. 13): {ziel:,.0f} €',
                    saison=saison,
                    referenz_typ='genesis', referenz_id=club.pk,
                    pflicht=True,
                )
            elif not dry_run and diff == 0:
                # Marker-Buchung, damit der Lauf idempotent bleibt.
                book(
                    club, 'KORREKTUR_ADMIN', Decimal('0.00'),
                    beschreibung=f'Genesis-Startbudget (Kap. 13): {ziel:,.0f} € (unverändert)',
                    saison=saison,
                    referenz_typ='genesis', referenz_id=club.pk,
                    pflicht=True,
                )
            report['clubs'].append(eintrag)
        except Exception as exc:
            report['errors'].append(f'{club.name}: {exc}')
            logger.exception('Genesis für %s fehlgeschlagen', club)

    return report
