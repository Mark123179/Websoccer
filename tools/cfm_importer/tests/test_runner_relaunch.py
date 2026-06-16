"""Tests für die Browser-Wiederaufnahme im Runner.

Stellt sicher, dass ein verlorener Browser (Page/Kontext/Browser geschlossen)
**nicht** als „Spieler überspringen" gewertet wird — auch dann nicht, wenn der
Fehler von ``safe_goto`` als ``PageError`` verpackt ankommt — sondern den Edge
neu startet und den Lauf über den lokalen State fortsetzt. Nach erschöpften
Neustarts bricht der Lauf sauber ab (Rückgabe 1 + ``fail``).
"""

import os
import sys
import time
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Playwright ist nur auf dem Windows-PC installiert, nicht in der CI/Serverumgebung.
# Da der Test ``Browser`` ohnehin durch eine Attrappe ersetzt, genügt ein Stub,
# damit der Import von ``browser.py`` (``from playwright.sync_api import ...``)
# nicht scheitert.
if 'playwright' not in sys.modules:
    _pw = types.ModuleType('playwright')
    _sync = types.ModuleType('playwright.sync_api')
    _sync.sync_playwright = lambda: None
    _pw.sync_api = _sync
    sys.modules['playwright'] = _pw
    sys.modules['playwright.sync_api'] = _sync

import cfm_importer.runner as runner_mod  # noqa: E402
from cfm_importer.runner import Runner  # noqa: E402
from cfm_importer.adapters.base import PageError  # noqa: E402

CLOSED_MSG = 'Navigationsfehler: Target page, context or browser has been closed'


class _FakeBrowser:
    def __init__(self, *_a, **_k):
        self.page = object()
        self.restart_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def restart(self):
        self.restart_calls += 1
        self.page = object()
        return self


class _FakeTM:
    squad_club_name = 'Testverein'

    def __init__(self, *_a, **_k):
        pass

    def collect_squad(self, *_a, **_k):
        return [{'tm_player_id': 1, 'display_name': 'A'},
                {'tm_player_id': 2, 'display_name': 'B'}]


class _FakeAdapter:
    def __init__(self, *_a, **_k):
        pass


class _FakeApi:
    def __init__(self):
        self.sent = []
        self.completed = 0
        self.failed = []

    def progress(self, *_a, **_k):
        pass

    def heartbeat(self, *_a, **_k):
        pass

    def send_candidate(self, _job_id, candidate):
        self.sent.append(candidate['tm_player_id'])

    def complete(self, *_a, **_k):
        self.completed += 1

    def fail(self, _job_id, message):
        self.failed.append(message)


class _FakeState:
    def __init__(self):
        self._sent = set()
        self.total = None
        self.cleared = False

    def is_sent(self, pid):
        return int(pid) in self._sent

    def mark_sent(self, pid):
        self._sent.add(int(pid))

    def set_total(self, total):
        self.total = total

    def clear(self):
        self.cleared = True


class _Config:
    heartbeat_seconds = 9999

    def pause(self, _key, default=0):
        return 0


class _Log:
    def warning(self, *_a, **_k):
        pass

    def info(self, *_a, **_k):
        pass

    def error(self, *_a, **_k):
        pass

    def exception(self, *_a, **_k):
        pass


def _make_runner(build_candidate):
    runner = Runner.__new__(Runner)
    runner.config = _Config()
    runner.log = _Log()
    runner.api = _FakeApi()
    runner._roster_matcher = None
    runner._last_heartbeat = time.time()
    runner._build_candidate = build_candidate  # bind override
    return runner


class RelaunchTests(unittest.TestCase):
    def setUp(self):
        self._orig = (runner_mod.Browser, runner_mod.TransfermarktAdapter,
                      runner_mod.FMInsideAdapter, runner_mod.SoFIFAAdapter)
        self.browser = _FakeBrowser()
        runner_mod.Browser = lambda *_a, **_k: self.browser
        runner_mod.TransfermarktAdapter = _FakeTM
        runner_mod.FMInsideAdapter = _FakeAdapter
        runner_mod.SoFIFAAdapter = _FakeAdapter

    def tearDown(self):
        (runner_mod.Browser, runner_mod.TransfermarktAdapter,
         runner_mod.FMInsideAdapter, runner_mod.SoFIFAAdapter) = self._orig

    def test_closed_pageerror_relaunches_and_resumes(self):
        """Geschlossener Browser (als PageError) → Neustart + Wiederaufnahme."""
        raised = {'done': False}

        def build_candidate(_tm, _fmi, _sofifa, entry):
            if entry['tm_player_id'] == 2 and not raised['done']:
                raised['done'] = True
                raise PageError(CLOSED_MSG)
            return {'tm_player_id': entry['tm_player_id'], 'tm': {}}

        runner = _make_runner(build_candidate)
        state = _FakeState()
        rc = runner._run_job(1, {'tm_club_id': 'c', 'tm_season_id': 's'}, state)

        self.assertEqual(rc, 0)
        self.assertEqual(self.browser.restart_calls, 1)  # genau einmal neu
        # Spieler 1 wurde nur einmal gesendet (Resume überspringt ihn danach).
        self.assertEqual(runner.api.sent, [1, 2])
        self.assertEqual(runner.api.completed, 1)
        self.assertEqual(runner.api.failed, [])
        self.assertTrue(state.cleared)

    def test_repeated_browser_loss_aborts(self):
        """Wiederholter Verlust → Abbruch nach MAX_BROWSER_RELAUNCH (Rückgabe 1)."""
        def build_candidate(_tm, _fmi, _sofifa, _entry):
            raise PageError(CLOSED_MSG)

        runner = _make_runner(build_candidate)
        state = _FakeState()
        rc = runner._run_job(1, {'tm_club_id': 'c', 'tm_season_id': 's'}, state)

        self.assertEqual(rc, 1)
        self.assertEqual(self.browser.restart_calls, Runner.MAX_BROWSER_RELAUNCH)
        self.assertEqual(runner.api.sent, [])
        self.assertTrue(runner.api.failed)


if __name__ == '__main__':
    unittest.main()
