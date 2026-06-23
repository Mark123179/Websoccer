"""HTTP-/View-Tests für das Scouting-System (Task #597).

Während ``test_scouting_service.py`` die Geld-/Status-Logik abdeckt, sichert
diese Datei die HTTP-Ebene über den Django-Testclient ab:

* Login-Schutz (nicht eingeloggt → Redirect auf /auth/login/),
* POST-Pflicht (``require_POST`` → GET liefert 405),
* CSRF-Schutz (POST ohne Token → 403),
* Vereins-Eigentum (Gebot/Beobachtung auf einen fremden Fund schlägt fehl,
  ohne dass ein Cross-Club-Datensatz entsteht),
* Creator-Endpunkte verhalten sich wie der restliche ``/creator/``-Bereich
  (Login-Pflicht + POST-Pflicht auf den Moderations-Endpunkt).
"""

from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from game.club_import.season import get_current_tm_season_id
from game.models import (
    Club, League, ManagerProfile, Player, PlayerStrengthProfile,
    ScoutingAssignment, ScoutingBid, ScoutingFind, WatchlistEntry,
    CommunitySubmission, CountryNetwork,
)
from game.scouting import coverage


def _pool_player(nat='Türkei', strength=70, potential=75, age=22, pos='ST',
                 market_value='4000000', last='Spieler'):
    player = Player.objects.create(
        first_name='Pool', last_name=last, age=age,
        position='Sturm', main_position_1=pos, nationalities=nat,
        market_value=Decimal(market_value),
        potential=potential, pool_status=Player.POOL_STATUS_SCOUTABLE,
    )
    PlayerStrengthProfile.objects.create(player=player, base_strength=Decimal(strength))
    return player


class ScoutingViewsBase(TestCase):
    def setUp(self):
        self.today = date(2026, 6, 23)
        self.season_id = get_current_tm_season_id(self.today)
        self.league = League.objects.create(name='Testliga', country='Deutschland')

        # Eigener Verein + eingeloggter Manager. Das ManagerProfile wird per
        # post_save-Signal automatisch angelegt; hier nur den Namen setzen.
        self.user = User.objects.create_user(username='manager1', password='pw12345')
        self.manager = self.user.manager_profile
        self.manager.name = 'Test-Manager'
        self.manager.save(update_fields=['name'])
        self.club = Club.objects.create(
            name='Bayern', short_name='FCB', founded_year=1900,
            budget=Decimal('200000000.00'), league=self.league,
            managed_by=self.manager,
        )

        # Fremder Verein + fremder Manager (ohne User-Login).
        self.other_manager = ManagerProfile.objects.create(name='Fremd-Manager')
        self.other_club = Club.objects.create(
            name='BVB', short_name='BVB', founded_year=1909,
            budget=Decimal('200000000.00'), league=self.league,
            managed_by=self.other_manager,
        )

        # Threshold künstlich klein für Scoutbarkeit (analog Service-Tests).
        patcher = mock.patch.object(coverage, 'COUNTRY_THRESHOLD', 2)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pool = [_pool_player(last=f'P{i}', strength=68 + (i % 6)) for i in range(6)]

        self.client = Client()
        self.client.force_login(self.user)

    def _assignment_with_find(self, player, club, manager):
        assignment = ScoutingAssignment.objects.create(
            club=club, manager=manager, scope_type='country', scope_key='TR',
            position='ST', profile='ergaenzung', department_level=0,
            cost=Decimal('250000'), duration_days=18,
            started_on=self.today, completes_on=self.today,
            season_id=self.season_id, status=ScoutingAssignment.STATUS_ACTIVE,
            finds_generated=True,
        )
        find = ScoutingFind.objects.create(
            assignment=assignment, player=player, order=0,
            observer_count=10, min_bid=Decimal('5000000'),
            status=ScoutingFind.STATUS_OFFERED,
        )
        return assignment, find


# ── Login-Schutz ──────────────────────────────────────────────────────────────
class LoginProtectionTests(ScoutingViewsBase):
    def test_scouting_screen_redirects_anonymous(self):
        self.client.logout()
        resp = self.client.get(reverse('transfer_scouting'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp.url)

    def test_watchlist_redirects_anonymous(self):
        self.client.logout()
        resp = self.client.get(reverse('transfer_watchlist'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp.url)

    def test_scouting_screen_ok_when_logged_in(self):
        resp = self.client.get(reverse('transfer_scouting'))
        self.assertEqual(resp.status_code, 200)

    def test_action_endpoints_redirect_anonymous(self):
        """Auch die POST-Aktionen sind login-geschützt (Redirect statt 405)."""
        self.client.logout()
        for name in ('scouting_start', 'scouting_bid', 'scouting_watch',
                     'scouting_withdraw', 'scouting_upgrade', 'scouting_reject',
                     'scouting_community_submit'):
            resp = self.client.post(reverse(name))
            self.assertEqual(resp.status_code, 302, name)
            self.assertIn('/auth/login/', resp.url, name)


# ── POST-Pflicht (require_POST) ───────────────────────────────────────────────
class RequirePostTests(ScoutingViewsBase):
    def test_get_on_post_only_endpoints_returns_405(self):
        for name in ('scouting_start', 'scouting_bid', 'scouting_watch',
                     'scouting_withdraw', 'scouting_upgrade', 'scouting_reject',
                     'scouting_community_submit'):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 405, name)


# ── CSRF-Schutz ───────────────────────────────────────────────────────────────
class CsrfProtectionTests(ScoutingViewsBase):
    def setUp(self):
        super().setUp()
        # Eigener Client mit CSRF-Prüfung; force_login behält die Session.
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.user)

    def test_bid_without_csrf_is_forbidden(self):
        _, find = self._assignment_with_find(self.pool[0], self.club, self.manager)
        resp = self.csrf_client.post(
            reverse('scouting_bid'),
            {'find_id': find.id, 'amount': '6000000'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_watch_without_csrf_is_forbidden(self):
        _, find = self._assignment_with_find(self.pool[0], self.club, self.manager)
        resp = self.csrf_client.post(
            reverse('scouting_watch'), {'find_id': find.id})
        self.assertEqual(resp.status_code, 403)

    def test_withdraw_without_csrf_is_forbidden(self):
        bid = ScoutingBid.objects.create(
            club=self.club, manager=self.manager, player=self.pool[0],
            amount=Decimal('6000000'), min_bid=Decimal('5000000'),
            window_date=date(2026, 7, 3), season_id=self.season_id,
            status=ScoutingBid.STATUS_ACTIVE,
        )
        resp = self.csrf_client.post(
            reverse('scouting_withdraw'), {'bid_id': bid.id})
        self.assertEqual(resp.status_code, 403)


# ── Vereins-Eigentum (kein Cross-Club-Zugriff) ────────────────────────────────
class CrossClubProtectionTests(ScoutingViewsBase):
    def test_bid_on_foreign_find_creates_no_bid(self):
        """Gebot auf einen fremden Fund schlägt fehl (kein Cross-Club-Zugriff)."""
        _, foreign = self._assignment_with_find(
            self.pool[0], self.other_club, self.other_manager)
        resp = self.client.post(
            reverse('scouting_bid'),
            {'find_id': foreign.id, 'amount': '6000000'},
        )
        # Service-Fehler wird abgefangen → Redirect, kein 500.
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ScoutingBid.objects.filter(
            club=self.club, player=self.pool[0]).exists())
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, ScoutingFind.STATUS_OFFERED)

    def test_watch_on_foreign_find_creates_no_entry(self):
        """Beobachten eines fremden Fundes schlägt fehl, ohne Eintrag anzulegen."""
        _, foreign = self._assignment_with_find(
            self.pool[1], self.other_club, self.other_manager)
        resp = self.client.post(
            reverse('scouting_watch'), {'find_id': foreign.id})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(WatchlistEntry.objects.filter(
            manager=self.manager, player=self.pool[1]).exists())

    def test_withdraw_foreign_bid_is_404(self):
        """Ein fremdes Gebot lässt sich nicht zurückziehen (get_object_or_404 club=)."""
        foreign_bid = ScoutingBid.objects.create(
            club=self.other_club, manager=self.other_manager, player=self.pool[2],
            amount=Decimal('6000000'), min_bid=Decimal('5000000'),
            window_date=date(2026, 7, 3), season_id=self.season_id,
            status=ScoutingBid.STATUS_ACTIVE,
        )
        resp = self.client.post(
            reverse('scouting_withdraw'), {'bid_id': foreign_bid.id})
        self.assertEqual(resp.status_code, 404)
        foreign_bid.refresh_from_db()
        self.assertEqual(foreign_bid.status, ScoutingBid.STATUS_ACTIVE)

    def test_own_bid_succeeds(self):
        """Gegenprobe: das Gebot auf den eigenen Fund wird angenommen."""
        _, find = self._assignment_with_find(self.pool[3], self.club, self.manager)
        resp = self.client.post(
            reverse('scouting_bid'),
            {'find_id': find.id, 'amount': '6000000'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(ScoutingBid.objects.filter(
            club=self.club, player=self.pool[3],
            status=ScoutingBid.STATUS_ACTIVE).exists())


# ── Creator-Endpunkte ─────────────────────────────────────────────────────────
class CreatorScoutingEndpointTests(ScoutingViewsBase):
    def test_overview_redirects_anonymous(self):
        self.client.logout()
        resp = self.client.get(reverse('creator_scouting_overview'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp.url)

    def test_overview_ok_when_logged_in(self):
        resp = self.client.get(reverse('creator_scouting_overview'))
        self.assertEqual(resp.status_code, 200)

    def test_moderate_redirects_anonymous(self):
        sub = CommunitySubmission.objects.create(
            manager=self.manager, iso2='TR',
            status=CommunitySubmission.STATUS_PENDING,
        )
        self.client.logout()
        resp = self.client.post(
            reverse('creator_moderate_submission', args=[sub.id]),
            {'action': 'approve'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp.url)
        sub.refresh_from_db()
        self.assertEqual(sub.status, CommunitySubmission.STATUS_PENDING)

    def test_moderate_requires_post(self):
        sub = CommunitySubmission.objects.create(
            manager=self.manager, iso2='TR',
            status=CommunitySubmission.STATUS_PENDING,
        )
        resp = self.client.get(
            reverse('creator_moderate_submission', args=[sub.id]))
        self.assertEqual(resp.status_code, 405)
