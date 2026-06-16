"""Tests für den FMInside-Adapter — strikt FM-ID-basiert, keine 404-Suche.

Stellt sicher, dass der Importer ohne bekannte FM-ID **nicht** mehr zu der nicht
existierenden Such-URL (``/search?q=`` → 404) navigiert, sondern den Fall sauber
als prüfbedürftig meldet. Referenzfall ohne FM-ID: HSV / „Daniel Heuer
Fernandes".
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cfm_importer.adapters.fminside import FMInsideAdapter  # noqa: E402


class _RecordingPage:
    """Minimaler Page-Doppelgänger, der jede Navigation protokolliert."""

    def __init__(self):
        self.goto_calls = []
        self.url = ''

    def goto(self, url, **kwargs):
        self.goto_calls.append(url)

        class _Resp:
            status = 200

        self.url = url
        return _Resp()

    def wait_for_timeout(self, _ms):
        pass

    def title(self):
        return ''

    def locator(self, _selector):
        return _EmptyLocator()


class _EmptyLocator:
    """Leerer Locator — liefert keine Treffer, wirft nie."""

    def count(self):
        return 0

    def nth(self, _i):
        return self

    @property
    def first(self):
        return self

    def inner_text(self):
        return ''

    def get_attribute(self, _name):
        return ''


class _Config:
    nav_retries = 0
    request_timeout = 5
    backoff_base = 0.0
    challenge_wait_seconds = 0
    manual_unblock = False
    headless = True

    def pause(self, _key, default=0):
        return default


class _Log:
    def warning(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass

    def exception(self, *a, **k):
        pass


class FMInsideLookupTests(unittest.TestCase):
    def _adapter(self):
        self.page = _RecordingPage()
        return FMInsideAdapter(self.page, _Config(), _Log())

    def test_no_fmi_id_does_not_navigate_and_warns(self):
        """Ohne FM-ID: keine Navigation (kein 404), klare Warnung."""
        adapter = self._adapter()
        warnings = []
        result = adapter.lookup(
            display_name='Daniel Heuer Fernandes',
            date_of_birth='13.11.1992',
            nationality='Deutschland',
            warnings=warnings,
        )
        self.assertIsNone(result)
        self.assertEqual(self.page.goto_calls, [])  # nie zu /search?q= navigiert
        self.assertEqual(len(warnings), 1)
        self.assertIn('FM-ID manuell setzen', warnings[0])

    def test_no_fmi_id_without_dob_also_safe(self):
        """Auch ohne Geburtsdatum darf keine Navigation erfolgen."""
        adapter = self._adapter()
        warnings = []
        result = adapter.lookup(
            display_name='Irgendwer',
            date_of_birth='',
            nationality='',
            warnings=warnings,
        )
        self.assertIsNone(result)
        self.assertEqual(self.page.goto_calls, [])

    def test_known_fmi_id_navigates_to_canonical_page(self):
        """Mit FM-ID: direkter Aufruf der einsegmentigen Spielerseite."""
        adapter = self._adapter()
        # finale (umgeleitete) URL trägt dieselbe ID → Treffer gilt als gültig.
        self.page.url = 'https://fminside.net/players/7-fm262/28049320-harry-kane'
        warnings = []
        adapter.lookup(
            display_name='Harry Kane',
            date_of_birth='28.07.1993',
            nationality='England',
            warnings=warnings,
            fmi_id=28049320,
        )
        self.assertTrue(self.page.goto_calls)
        self.assertIn('/players/28049320-', self.page.goto_calls[0])


if __name__ == '__main__':
    unittest.main()
