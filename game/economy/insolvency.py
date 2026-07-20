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

#: Erinnerung versenden, wenn noch ≤ diese Anzahl Tage verbleiben.
ERINNERUNG_TAGE = 2


def _frist_label(deadline_at):
    """Gibt das Fristdatum als lesbaren deutschen String zurück."""
    local = timezone.localtime(deadline_at)
    return local.strftime('%-d. %B %Y')


def open_case(locked_club, tx):
    """Öffnet einen Vermerk für den (bereits gesperrten) Verein — idempotent.

    Wird von booking._create_booking aufgerufen, wenn eine Pflichtbuchung
    den Kontostand von ≥ 0 auf < 0 gebucht hat. Existiert bereits ein
    offener Vermerk (z. B. nach Admin-Korrekturen), passiert nichts.
    Erzeugt bei Eröffnung eine ClubNewsItem-Meldung für den Manager.
    """
    from game.models import ClubNewsItem, InsolvencyCase

    if InsolvencyCase.objects.filter(
        club_id=locked_club.pk, status=InsolvencyCase.STATUS_OPEN,
    ).exists():
        return None

    now = timezone.now()
    deadline = now + datetime.timedelta(days=FRIST_TAGE)
    case = InsolvencyCase.objects.create(
        club_id=locked_club.pk,
        deadline_at=deadline,
        trigger_tx=tx,
        betrag_bei_eroeffnung=locked_club.budget,
        status=InsolvencyCase.STATUS_OPEN,
    )

    frist_str = _frist_label(deadline)
    ClubNewsItem.objects.create(
        club_id=locked_club.pk,
        title=f'Zahlungsunfähigkeit festgestellt — Frist bis {frist_str}',
        subtitle=(
            f'Der Kontostand ist unter 0 gefallen. Das Sportgericht hat einen '
            f'Vermerk eröffnet. Der Verein hat bis zum {frist_str}, den '
            f'Kontostand zu bereinigen (≥ 0 €). Andernfalls kann der Admin '
            f'eine Zwangsversteigerung ansetzen.'
        ),
        category='Sportgericht',
        outlet='Sportgericht',
        published_at=timezone.localdate(),
        is_new=True,
    )

    return case


def resolve_cases(locked_club):
    """Schließt offene Vermerke des Vereins (Konto ist zurück auf ≥ 0).

    Auch 'enforced'-Fälle werden geschlossen — die Bereinigung (z. B. durch
    den Zwangsversteigerungs-Erlös selbst) beendet das Verfahren.
    Erzeugt eine positive Bestätigungs-News, wenn mindestens ein Fall
    geschlossen wird.
    """
    from game.models import ClubNewsItem, InsolvencyCase

    updated = InsolvencyCase.objects.filter(
        club_id=locked_club.pk,
        status__in=[InsolvencyCase.STATUS_OPEN, InsolvencyCase.STATUS_ENFORCED],
    ).update(status=InsolvencyCase.STATUS_RESOLVED, resolved_at=timezone.now())

    if updated:
        ClubNewsItem.objects.create(
            club_id=locked_club.pk,
            title='Zahlungsunfähigkeits-Verfahren abgeschlossen — Konto bereinigt',
            subtitle=(
                'Der Kontostand ist wieder auf ≥ 0 € gestiegen. '
                'Das Sportgericht hat den Vermerk geschlossen. '
                'Das Verfahren ist damit beendet.'
            ),
            category='Sportgericht',
            outlet='Sportgericht',
            published_at=timezone.localdate(),
            is_new=True,
        )

    return updated


def offene_faelle(club):
    """Offene(r) Vermerk(e) eines Vereins für Manager-/Admin-Ansichten."""
    from game.models import InsolvencyCase

    return InsolvencyCase.objects.filter(
        club=club,
        status__in=[InsolvencyCase.STATUS_OPEN, InsolvencyCase.STATUS_ENFORCED],
    )
