"""Tests für das SoFIFA-Matching — toleranter Namensfilter + Geburtsdatum.

Deckt den dokumentierten Wurzelfall ab: SoFIFA zeigt in der Trefferliste oft
Kurz-/Abkürzungsnamen (z. B. „L. Messi"), wodurch ein reiner Gleichheitsabgleich
scheitert und das Profil nie geöffnet wird. Die endgültige Eindeutigkeit stellt
das Geburtsdatum her; ohne lesbares Geburtsdatum wird ein eindeutiger
Namenstreffer mit Hinweis übernommen (SoFIFA ist optional).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cfm_importer.adapters import sofifa  # noqa: E402
from cfm_importer.adapters.sofifa import SoFIFAAdapter, _first_dob, _name_matches  # noqa: E402


class NameMatchTests(unittest.TestCase):
    def test_abbreviated_first_name_matches(self):
        self.assertTrue(_name_matches('L. Messi', 'Lionel Messi'))

    def test_full_name_matches_abbreviated_target(self):
        self.assertTrue(_name_matches('Lionel Messi', 'L. Messi'))

    def test_exact_match(self):
        self.assertTrue(_name_matches('Cristiano Ronaldo', 'Cristiano Ronaldo'))

    def test_accents_ignored(self):
        self.assertTrue(_name_matches('Á. García', 'Alvaro Garcia'))

    def test_different_surname_no_match(self):
        self.assertFalse(_name_matches('L. Suárez', 'Lionel Messi'))

    def test_different_initial_no_match(self):
        self.assertFalse(_name_matches('C. Messi', 'Lionel Messi'))

    def test_single_token_surname_match(self):
        self.assertTrue(_name_matches('Vinicius', 'Vinicius Junior'))


class FirstDobTests(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(_first_dob('geboren 2002-12-28'), '2002-12-28')

    def test_german(self):
        self.assertEqual(_first_dob('28.12.2002'), '2002-12-28')

    def test_english_month_first(self):
        self.assertEqual(_first_dob('Dec 28, 2002 (age 23)'), '2002-12-28')

    def test_english_day_first(self):
        self.assertEqual(_first_dob('28 Dec 2002'), '2002-12-28')

    def test_nothing(self):
        self.assertEqual(_first_dob('keine Angabe'), '')


# ── Page-Doppelgänger zum Steuern von Suche/Profil ──────────────────────────
class _Locator:
    def __init__(self, text='', href=''):
        self._text = text
        self._href = href

    def count(self):
        return 1 if (self._text or self._href) else 0

    def nth(self, _i):
        return self

    @property
    def first(self):
        return self

    def inner_text(self):
        return self._text

    def get_attribute(self, name):
        if name == 'href':
            return self._href
        return ''


class _LinkList:
    """Mehrere Treffer-Links als Locator-Liste."""

    def __init__(self, links):
        self._links = links

    def count(self):
        return len(self._links)

    def nth(self, i):
        return self._links[i]


class _FakePage:
    """Liefert je nach aktueller URL Such-Links oder ein Profil-DOM."""

    def __init__(self, results, profiles):
        self._results = results        # Liste von (name, href)
        self._profiles = profiles      # {url: {'dob':..., 'overall':...}}
        self.url = ''
        self.goto_calls = []

    def goto(self, url, **kwargs):
        self.goto_calls.append(url)
        self.url = url

        class _Resp:
            status = 200

        return _Resp()

    def wait_for_timeout(self, _ms):
        pass

    def title(self):
        return ''

    def locator(self, selector):
        if '/player/' in selector:
            links = [_Locator(text=n, href=h) for n, h in self._results]
            return _LinkList(links)
        prof = self._profiles.get(self.url, {})
        if 'overall' in selector:
            return _Locator(text=str(prof.get('overall', '')))
        if 'potential' in selector:
            return _Locator(text=str(prof.get('potential', '')))
        if selector == 'body':
            return _Locator(text=prof.get('body', ''))
        # DOB-Selektoren
        return _Locator(text=prof.get('dob_text', ''))


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


class LookupTests(unittest.TestCase):
    def _adapter(self, page):
        return SoFIFAAdapter(page, _Config(), _Log())

    def test_abbreviated_name_opens_profile_and_confirms_dob(self):
        """Kurzname in der Liste + passendes Geburtsdatum → Treffer übernommen."""
        page = _FakePage(
            results=[('L. Messi', '/player/158023/')],
            profiles={'https://sofifa.com/player/158023/':
                      {'overall': 90, 'potential': 90,
                       'dob_text': 'Jun 24, 1987'}},
        )
        warnings = []
        result = self._adapter(page).lookup(
            display_name='Lionel Messi', date_of_birth='24.06.1987',
            nationality='Argentinien', warnings=warnings)
        self.assertIsNotNone(result)
        self.assertEqual(result['dob'], '1987-06-24')
        self.assertEqual(result['rating'], 90)
        # Profil wurde tatsächlich geöffnet (über die Suche hinaus).
        self.assertIn('https://sofifa.com/player/158023/', page.goto_calls)

    def test_dob_mismatch_rejected(self):
        """Lesbares, aber abweichendes Geburtsdatum → kein Treffer (kein Raten)."""
        page = _FakePage(
            results=[('L. Messi', '/player/158023/')],
            profiles={'https://sofifa.com/player/158023/':
                      {'overall': 90, 'dob_text': 'Jan 1, 1990'}},
        )
        warnings = []
        result = self._adapter(page).lookup(
            display_name='Lionel Messi', date_of_birth='24.06.1987',
            nationality='Argentinien', warnings=warnings)
        self.assertIsNone(result)
        self.assertTrue(any('weicht ab' in w for w in warnings))

    def test_dob_unreadable_single_hit_accepted_with_warning(self):
        """Geburtsdatum nicht lesbar, aber eindeutiger Name → übernommen + Hinweis."""
        page = _FakePage(
            results=[('Lionel Messi', '/player/158023/')],
            profiles={'https://sofifa.com/player/158023/':
                      {'overall': 90, 'dob_text': ''}},
        )
        warnings = []
        result = self._adapter(page).lookup(
            display_name='Lionel Messi', date_of_birth='24.06.1987',
            nationality='Argentinien', warnings=warnings)
        self.assertIsNotNone(result)
        self.assertTrue(any('bitte prüfen' in w for w in warnings))

    def test_ambiguous_two_names_no_dob_target(self):
        """Zwei Namenstreffer ohne Ziel-Geburtsdatum → uneindeutig, None."""
        page = _FakePage(
            results=[('L. Messi', '/player/1/'), ('L. Messi', '/player/2/')],
            profiles={'https://sofifa.com/player/1/': {'overall': 80},
                      'https://sofifa.com/player/2/': {'overall': 70}},
        )
        warnings = []
        result = self._adapter(page).lookup(
            display_name='Lionel Messi', date_of_birth='',
            nationality='', warnings=warnings)
        self.assertIsNone(result)

    def test_no_name_hit(self):
        page = _FakePage(
            results=[('Andrés Iniesta', '/player/41/')],
            profiles={},
        )
        warnings = []
        result = self._adapter(page).lookup(
            display_name='Lionel Messi', date_of_birth='24.06.1987',
            nationality='', warnings=warnings)
        self.assertIsNone(result)
        self.assertTrue(any('kein Namenstreffer' in w for w in warnings))


if __name__ == '__main__':
    unittest.main()
