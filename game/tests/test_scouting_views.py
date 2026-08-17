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


# ── Öffentliche Sicht leakt keine Stärke/Potential/Pool (Task #600) ───────────
class FindCardConfidentialityTests(ScoutingViewsBase):
    """Das zentrale Design-Versprechen: Fund-Karten verraten weder
    base_strength/potential noch observer-Pool/pool_count.

    Der Test setzt bewusst unverwechselbare Sentinel-Werte für Stärke und
    Potential, damit ein versehentliches Durchsickern ins Template oder den
    Context sofort auffällt.
    """

    # Sentinel-Werte, die sonst nirgends auf dem Screen vorkommen dürfen.
    # Domain-invalid (>100) und vierstellig → kein Substring-Kollision mit kleinen PKs.
    SENTINEL_STRENGTH = 9873
    SENTINEL_POTENTIAL = 9937

    # Schlüssel, die im finds-Context niemals auftauchen dürfen.
    FORBIDDEN_KEYS = (
        'strength', 'base_strength', 'potential',
        'pool_count', 'pool_status', 'attributes',
    )

    # Genau diese Schlüssel darf eine öffentliche Fund-Karte enthalten.
    ALLOWED_KEYS = {
        'find_id', 'player_id', 'name', 'age', 'flag', 'nat', 'hp', 'np',
        'rl_club', 'rl_club_crest', 'rl_liga', 'market_value_fmt', 'min_bid', 'min_bid_fmt',
        'observer_count', 'portrait', 'watched',
    }

    def _sentinel_find(self):
        player = _pool_player(
            last='Geheim', strength=self.SENTINEL_STRENGTH,
            potential=self.SENTINEL_POTENTIAL, age=24,
            market_value='4000000',
        )
        return self._assignment_with_find(player, self.club, self.manager)

    def test_finds_context_has_no_strength_or_potential_keys(self):
        self._sentinel_find()
        resp = self.client.get(reverse('transfer_scouting'))
        self.assertEqual(resp.status_code, 200)
        finds = resp.context['finds']
        self.assertEqual(len(finds), 1)
        card = finds[0]
        # Keine verbotenen Schlüssel.
        for key in self.FORBIDDEN_KEYS:
            self.assertNotIn(key, card, f'Fund-Karte verrät {key!r}')
        # Whitelist: ausschließlich erlaubte Schlüssel.
        self.assertEqual(set(card), self.ALLOWED_KEYS)

    def test_finds_context_values_do_not_contain_sentinels(self):
        """Auch die Werte (nicht nur Schlüssel) dürfen Stärke/Potential nicht
        durchreichen — z. B. als String oder in einer verschachtelten Struktur."""
        self._sentinel_find()
        resp = self.client.get(reverse('transfer_scouting'))
        card = resp.context['finds'][0]
        for value in card.values():
            self.assertNotIn(self.SENTINEL_STRENGTH, (value,))
            self.assertNotIn(self.SENTINEL_POTENTIAL, (value,))

    def test_rendered_html_hides_strength_and_potential(self):
        self._sentinel_find()
        resp = self.client.get(reverse('transfer_scouting'))
        html = resp.content.decode('utf-8')
        # Die Fund-Karte wird gerendert (Name als Anker).
        self.assertIn('Pool Geheim', html)

        # Auf dem Gesamtscreen kommen Zahlen wie Sentinels zufällig in Karten-
        # Daten/Prozenten vor; deshalb wird nur das Ergebnis-Panel geprüft, das
        # ausschließlich die öffentlichen Fund-Karten enthält.
        start = html.index('<aside class="sc-panel sc-results-panel">')
        end = html.index('</aside>', start)
        panel = html[start:end]
        self.assertIn('Pool Geheim', panel)

        # Sentinel-Werte tauchen im Fund-Panel nicht auf.
        self.assertNotIn(str(self.SENTINEL_STRENGTH), panel)
        self.assertNotIn(str(self.SENTINEL_POTENTIAL), panel)
        # Und keine verräterischen Attribut-Labels (gesamter Screen).
        for label in ('base_strength', 'pool_count', 'Stärke', 'Potential', 'Potenzial'):
            self.assertNotIn(label, html)


# ── Vereinslose Beobachtungsliste (managergebunden) ───────────────────────────
class ClublessWatchlistTests(ScoutingViewsBase):
    def setUp(self):
        super().setUp()
        # Eingeloggter Manager OHNE Verein – die Liste muss trotzdem nutzbar sein.
        self.clubless_user = User.objects.create_user(
            username='vereinslos', password='pw12345')
        self.clubless_manager = self.clubless_user.manager_profile
        self.cl_client = Client()
        self.cl_client.force_login(self.clubless_user)

    def test_clubless_can_view_watchlist(self):
        resp = self.cl_client.get(reverse('transfer_watchlist'))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context['club'])

    def test_clubless_can_add_player(self):
        player = self.pool[0]
        resp = self.cl_client.post(
            reverse('scouting_watchlist_add'), {'player_id': player.id})
        self.assertEqual(resp.status_code, 302)
        entry = WatchlistEntry.objects.get(
            manager=self.clubless_manager, player=player)
        self.assertEqual(entry.status, 'watched')

    def test_clubless_can_remove_player(self):
        player = self.pool[1]
        WatchlistEntry.objects.create(
            manager=self.clubless_manager, player=player, status='watched')
        resp = self.cl_client.post(
            reverse('scouting_watchlist_remove'), {'player_id': player.id})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(
            WatchlistEntry.objects.filter(
                manager=self.clubless_manager, player=player).exists())

    def test_add_does_not_downgrade_existing_status(self):
        player = self.pool[2]
        WatchlistEntry.objects.create(
            manager=self.clubless_manager, player=player, status='bid')
        self.cl_client.post(
            reverse('scouting_watchlist_add'), {'player_id': player.id})
        entry = WatchlistEntry.objects.get(
            manager=self.clubless_manager, player=player)
        self.assertEqual(entry.status, 'bid')

    def test_add_remove_require_post(self):
        for name in ('scouting_watchlist_add', 'scouting_watchlist_remove'):
            resp = self.cl_client.get(reverse(name))
            self.assertEqual(resp.status_code, 405, name)

    def test_add_remove_require_login(self):
        self.cl_client.logout()
        for name in ('scouting_watchlist_add', 'scouting_watchlist_remove'):
            resp = self.cl_client.post(
                reverse(name), {'player_id': self.pool[0].id})
            self.assertEqual(resp.status_code, 302, name)
            self.assertIn('/auth/login/', resp.url, name)

    def test_search_filters_by_name(self):
        resp = self.cl_client.get(reverse('transfer_watchlist'), {'q': 'P0'})
        ids = [r['player_id'] for r in resp.context['search_results']]
        self.assertIn(self.pool[0].id, ids)
        self.assertNotIn(self.pool[1].id, ids)

    def test_search_filters_by_position(self):
        resp = self.cl_client.get(reverse('transfer_watchlist'), {'pos': 'ST'})
        ids = [r['player_id'] for r in resp.context['search_results']]
        self.assertIn(self.pool[0].id, ids)
        resp2 = self.cl_client.get(reverse('transfer_watchlist'), {'pos': 'IV'})
        ids2 = [r['player_id'] for r in resp2.context['search_results']]
        self.assertNotIn(self.pool[0].id, ids2)

    def test_search_excludes_already_watched(self):
        player = self.pool[0]
        WatchlistEntry.objects.create(
            manager=self.clubless_manager, player=player, status='watched')
        resp = self.cl_client.get(reverse('transfer_watchlist'), {'q': 'P0'})
        ids = [r['player_id'] for r in resp.context['search_results']]
        self.assertNotIn(player.id, ids)

    def test_search_results_never_leak_strength_or_potential(self):
        resp = self.cl_client.get(reverse('transfer_watchlist'), {'q': 'Pool'})
        # Nur öffentliche Felder (Identität/Optik/MW) — NIE Stärke/Potential.
        allowed = {
            'player_id', 'name', 'age', 'flag', 'flag_img', 'portrait',
            'hp', 'np', 'club_name', 'club_crest', 'player_url',
            'market_value_fmt',
        }
        forbidden = {'base_strength', 'potential', 'strength', 'pool_count'}
        self.assertTrue(resp.context['search_results'])
        for r in resp.context['search_results']:
            self.assertEqual(set(r.keys()), allowed)
            self.assertFalse(set(r.keys()) & forbidden)

    def test_add_with_invalid_player_id_does_not_crash(self):
        for bad in ('abc', '', '999999'):
            resp = self.cl_client.post(
                reverse('scouting_watchlist_add'), {'player_id': bad})
            self.assertEqual(resp.status_code, 302, bad)
        self.assertFalse(
            WatchlistEntry.objects.filter(manager=self.clubless_manager).exists())

    def test_remove_with_invalid_player_id_does_not_crash(self):
        resp = self.cl_client.post(
            reverse('scouting_watchlist_remove'), {'player_id': 'not-a-number'})
        self.assertEqual(resp.status_code, 302)
