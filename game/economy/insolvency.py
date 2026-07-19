"""Zahlungsunfähigkeits-Verfahren (Spec Kap. 12.3).

Die Grenze ist für jeden Verein dieselbe: die 0. Bucht eine Pflichtbuchung
das Konto ins Minus, wird automatisch ein Sportgericht-Vermerk
(InsolvencyCase) geöffnet. Der Manager hat 7 ECHTE Tage, den Kontostand zu
bereinigen — kehrt das Konto auf ≥ 0 zurück, schließt der Vermerk
automatisch. Andernfalls kann der Admin eine Zwangsversteigerung
ausgewählter Spieler ansetzen (game.economy.forced_auction).

Die Hooks laufen INNERHALB der Buchungstransaktion (Club-Zeile bereits
gesperrt, keine neue Lock-Reihenfolge). Reine Arithmetik-Guards halten den
heißen Buchungspfad frei von Zusatz-Queries: Nur der Vorzeichen-Übergang
(≥ 0 → < 0 bzw. < 0 → ≥ 0) löst Datenbankzugriffe aus.
"""
import datetime

from django.utils import timezone

#: Frist zur Bereinigung des Kontostands (echte Zeit, Spec Kap. 12.3).
FRIST_TAGE = 7


def open_case(locked_club, tx):
    """Öffnet einen Vermerk für den (bereits gesperrten) Verein — idempotent.

    Wird von booking._create_booking aufgerufen, wenn eine Pflichtbuchung
    den Kontostand von ≥ 0 auf < 0 gebucht hat. Existiert bereits ein
    offener Vermerk (z. B. nach Admin-Korrekturen), passiert nichts.
    """
    from game.models import InsolvencyCase

    if InsolvencyCase.objects.filter(
        club_id=locked_club.pk, status=InsolvencyCase.STATUS_OPEN,
    ).exists():
        return None

    now = timezone.now()
    return InsolvencyCase.objects.create(
        club_id=locked_club.pk,
        deadline_at=now + datetime.timedelta(days=FRIST_TAGE),
        trigger_tx=tx,
        betrag_bei_eroeffnung=locked_club.budget,
        status=InsolvencyCase.STATUS_OPEN,
    )


def resolve_cases(locked_club):
    """Schließt offene Vermerke des Vereins (Konto ist zurück auf ≥ 0).

    Auch 'enforced'-Fälle werden geschlossen — die Bereinigung (z. B. durch
    den Zwangsversteigerungs-Erlös selbst) beendet das Verfahren.
    """
    from game.models import InsolvencyCase

    return InsolvencyCase.objects.filter(
        club_id=locked_club.pk,
        status__in=[InsolvencyCase.STATUS_OPEN, InsolvencyCase.STATUS_ENFORCED],
    ).update(status=InsolvencyCase.STATUS_RESOLVED, resolved_at=timezone.now())


def offene_faelle(club):
    """Offene(r) Vermerk(e) eines Vereins für Manager-/Admin-Ansichten."""
    from game.models import InsolvencyCase

    return InsolvencyCase.objects.filter(
        club=club,
        status__in=[InsolvencyCase.STATUS_OPEN, InsolvencyCase.STATUS_ENFORCED],
    )
