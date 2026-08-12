"""WP/SE-Stichtage und Leih-Deadline (Master-Spec §5.4).

Die Spielplan-Generierung fixiert bei Saisonstart feste Winterpausen- (WP)
und Saisonende- (SE) Daten. Bis diese in einem Kalendermodell abgelegt sind,
liefert dieses Modul deterministische Näherungen über die vorhandenen
Liga-Fixture-Daten (SimulatedMatch/Fixture scheduled_date). So bleiben alle
WP/SE-abhängigen Jobs (execute_pending_transfers, loan_deadline_guard)
funktionsfähig und die Näherung ist an EINER Stelle austauschbar.
"""
from django.utils import timezone


def _fixture_date_bounds():
    """(erstes, letztes) geplantes Fixture-Datum über alle Ligen — oder None."""
    from game.models import SeasonFixture  # scheduled_date liegt auf SeasonFixture.
    qs = SeasonFixture.objects.exclude(scheduled_date__isnull=True)
    first = qs.order_by('scheduled_date').values_list('scheduled_date', flat=True).first()
    last = qs.order_by('-scheduled_date').values_list('scheduled_date', flat=True).first()
    return first, last


def winter_break_date():
    """Fixes WP-Datum (Näherung: Mitte des Spielplan-Zeitraums)."""
    first, last = _fixture_date_bounds()
    if first and last:
        return first + (last - first) / 2
    return timezone.localdate() + timezone.timedelta(days=60)


def season_end_date():
    """Fixes SE-Datum (Näherung: letztes Fixture-Datum)."""
    _, last = _fixture_date_bounds()
    if last:
        return last
    return timezone.localdate() + timezone.timedelta(days=180)


def next_execution_date(timing):
    """WP- bzw. SE-Vollzugsdatum für einen PendingTransfer."""
    if timing == 'WP':
        return winter_break_date()
    if timing == 'SE':
        return season_end_date()
    # SOFORT dürfte hier nie ankommen; sicherheitshalber heute.
    return timezone.localdate()


def loan_deadline_date(timing, saison=None):
    """Leih-Deadline = 5 Spieltage vor WP bzw. SE (Näherung: N Tage vor Stichtag)."""
    from game.economy.params import get_param
    spieltage = int(get_param('LEIHE_DEADLINE_SPIELTAGE', saison))
    # Näherung: ein Spieltag ≈ 7 Tage. Austauschbar, sobald ein echter
    # Spielplan-Kalender die Deadline-Daten direkt liefert.
    ziel = winter_break_date() if timing == 'WP' else season_end_date()
    return ziel - timezone.timedelta(days=spieltage * 7)


def loan_market_paused(timing=None, saison=None):
    """True, wenn ab der Leih-Deadline keine neuen Leihen mehr erlaubt sind."""
    today = timezone.localdate()
    if timing:
        return today >= loan_deadline_date(timing, saison)
    # Ohne Angabe: pausiert, sobald die frühere (WP-)Deadline erreicht ist.
    return today >= loan_deadline_date('WP', saison)
