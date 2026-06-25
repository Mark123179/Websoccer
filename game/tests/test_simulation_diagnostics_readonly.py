"""Read-only-Garantie: weder Report-Aufbau noch View verändern Daten/UI."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse


def _slice_diag_content(html):
    """Nur den Diagnose-Inhalt (ohne globale App-Shell) zwischen den Markern."""
    start = html.find('<!-- sim-diag-start -->')
    end = html.find('<!-- sim-diag-end -->')
    if start == -1 or end == -1:
        return ''
    return html[start:end].lower()


def _counts():
    from game.models import (
        SimulatedMatch, SeasonFixture, PlayerFormSnapshot, PlayerSeasonStat,
    )
    return (
        SimulatedMatch.objects.count(),
        SeasonFixture.objects.count(),
        PlayerFormSnapshot.objects.count(),
        PlayerSeasonStat.objects.count(),
    )


class SimulationDiagnosticsReadOnlyTests(TestCase):
    def test_report_build_does_not_write(self):
        from game.simulation_diagnostics.report import (
            build_simulation_diagnostics_report,
        )
        before = _counts()
        build_simulation_diagnostics_report()
        self.assertEqual(before, _counts())

    def test_view_is_readonly_and_has_no_write_ui(self):
        User = get_user_model()
        staff = User.objects.create_user(
            'ro_staff', 'ro@example.de', 'pw12345', is_staff=True,
        )
        self.client.force_login(staff)
        before = _counts()
        resp = self.client.get(reverse('creator_simulation_diagnostics'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(before, _counts())

        content = _slice_diag_content(resp.content.decode())
        self.assertTrue(content, 'Diagnose-Marker nicht gefunden')
        # Keine Schreib-UI im Diagnose-Inhalt.
        self.assertNotIn('<form', content)
        self.assertNotIn('<button', content)
        self.assertNotIn('method="post"', content)
        self.assertNotIn("method='post'", content)
