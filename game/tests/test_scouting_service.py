"""Service-Tests für das Scouting-System (Task #594).

Deckt ab: Auftragsstart (Kosten + Sperre), Fund-Erzeugung (genau 3, idempotent),
Gebot (Budget-Reservierung, Watchlist, Auftragsabschluss), Rückzug (Freigabe),
Zuschlags-Auflösung (höchstes Gebot, Gleichstand), Verpflichtungslimit + Coin
sowie Community-Einreichungen.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from game.club_import.season import get_current_tm_season_id
from game.models import (
    League, Club, Player, PlayerStrengthProfile, ManagerProfile, HoenessCoin,
    ScoutingAssignment, ScoutingFind, ScoutingBid, WatchlistEntry,
    CountryNetwork, CommunitySubmission, FinanceTransaction, ClubNewsItem,
)
from game.scouting import service, coverage, department, constants


def _pool_player(nat='Türkei', strength=70, potential=75, age=22, pos='ST',
                 market_value='4000000', last='Spieler',
                 pool_status=Player.POOL_STATUS_SCOUTABLE, scouting_category=''):
    player = Player.objects.create(
        first_name='Pool', last_name=last, age=age,
        position='Sturm', main_position_1=pos, nationalities=nat,
        market_value=(Decimal(market_value) if market_value is not None else None),
        potential=potential, pool_status=pool_status, scouting_category=scouting_category,
    )
    PlayerStrengthProfile.objects.create(player=player, base_strength=Decimal(strength))
    return player


class ScoutingServiceBase(TestCase):
    def setUp(self):
        self.today = date(2026, 6, 23)
        self.season_id = get_current_tm_season_id(self.today)
        self.league = League.objects.create(name='Testliga', country='Deutschland')
        self.club = Club.objects.create(
            name='Bayern', short_name='FCB', founded_year=1900,
            budget=Decimal('200000000.00'), league=self.league,
        )
        self.manager = ManagerProfile.objects.create(name='Test-Manager')
        # Threshold künstlich klein, damit wenige Poolspieler scoutbar machen.
        patcher = mock.patch.object(coverage, 'COUNTRY_THRESHOLD', 2)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Genug TR-Poolspieler für Scoutbarkeit + Auswahl.
        self.pool = [_pool_player(last=f'P{i}', strength=68 + (i % 6)) for i in range(6)]

    def _active_assignment_with_find(self, player, club=None, manager=None):
        """Erzeugt direkt einen aktiven Auftrag + Fund (ORM) für volle Kontrolle."""
        club = club or self.club
        manager = manager if manager is not None else self.manager
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


class StartAssignmentTests(ScoutingServiceBase):
    def test_start_debits_cost_and_logs_transaction(self):
        before = self.club.budget
        a = service.start_assignment(self.club, self.manager, 'country', 'TR',
                                     'ergaenzung', 'ST', today=self.today)
        self.club.refresh_from_db()
        cost = Decimal(department.order_cost(0))
        self.assertEqual(self.club.budget, before - cost)
        self.assertEqual(a.status, ScoutingAssignment.STATUS_ACTIVE)
        self.assertTrue(FinanceTransaction.objects.filter(
            club=self.club, typ='SCOUTING').exists())

    def test_only_one_active_assignment(self):
        service.start_assignment(self.club, self.manager, 'country', 'TR',
                                 'ergaenzung', 'ST', today=self.today)
        with self.assertRaises(service.ScoutingError):
            service.start_assignment(self.club, self.manager, 'country', 'TR',
                                     'ergaenzung', 'ST', today=self.today)

    def test_non_scoutable_scope_rejected(self):
        with self.assertRaises(service.ScoutingError):
            service.start_assignment(self.club, self.manager, 'country', 'BR',
                                     'ergaenzung', 'ST', today=self.today)


class FindsTests(ScoutingServiceBase):
    def test_generate_finds_requires_completion(self):
        a = service.start_assignment(self.club, self.manager, 'country', 'TR',
                                     'ergaenzung', 'ST', today=self.today)
        with self.assertRaises(service.ScoutingError):
            service.generate_finds(a, today=self.today)

    def test_generate_exactly_three_idempotent(self):
        a = service.start_assignment(self.club, self.manager, 'country', 'TR',
                                     'ergaenzung', 'ST', today=self.today)
        done = a.completes_on
        finds = service.generate_finds(a, today=done)
        self.assertEqual(len(finds), 3)
        for f in finds:
            self.assertGreater(f.min_bid, Decimal('0'))
        again = service.generate_finds(a, today=done)
        self.assertEqual([f.player_id for f in finds], [f.player_id for f in again])

    def test_top_star_never_found(self):
        star = _pool_player(last='Star', strength=constants.TOP_STAR_STRENGTH + 3)
        a = service.start_assignment(self.club, self.manager, 'country', 'TR',
                                     'ergaenzung', 'ST', today=self.today)
        finds = service.generate_finds(a, today=a.completes_on)
        self.assertNotIn(star.id, [f.player_id for f in finds])


class BidTests(ScoutingServiceBase):
    def test_place_bid_reserves_budget_and_completes_assignment(self):
        player = self.pool[0]
        a, find = self._active_assignment_with_find(player)
        # zweiter Fund, der danach verfallen muss
        other = ScoutingFind.objects.create(assignment=a, player=self.pool[1],
                                            order=1, min_bid=Decimal('5000000'),
                                            status=ScoutingFind.STATUS_OFFERED)
        budget_before = self.club.budget
        bid = service.place_bid(self.club, self.manager, find,
                                Decimal('6000000'), today=self.today)
        self.club.refresh_from_db()
        # Budget noch NICHT belastet, aber reserviert
        self.assertEqual(self.club.budget, budget_before)
        self.assertEqual(service.reserved_budget(self.club), Decimal('6000000'))
        self.assertEqual(service.available_budget(self.club),
                         budget_before - Decimal('6000000'))
        find.refresh_from_db(); other.refresh_from_db(); a.refresh_from_db()
        self.assertEqual(find.status, ScoutingFind.STATUS_CHOSEN)
        self.assertEqual(other.status, ScoutingFind.STATUS_EXPIRED)
        self.assertEqual(a.status, ScoutingAssignment.STATUS_COMPLETED)
        self.assertTrue(WatchlistEntry.objects.filter(
            manager=self.manager, player=player, status='bid').exists())
        self.assertEqual(bid.window_date, date(2026, 7, 3))

    def test_bid_below_min_rejected(self):
        player = self.pool[0]
        _, find = self._active_assignment_with_find(player)
        with self.assertRaises(service.ScoutingError):
            service.place_bid(self.club, self.manager, find,
                              Decimal('1000000'), today=self.today)

    def test_withdraw_releases_reservation(self):
        player = self.pool[0]
        _, find = self._active_assignment_with_find(player)
        bid = service.place_bid(self.club, self.manager, find,
                                Decimal('6000000'), today=self.today)
        self.assertEqual(service.reserved_budget(self.club), Decimal('6000000'))
        service.withdraw_bid(bid)
        self.assertEqual(service.reserved_budget(self.club), Decimal('0.00'))
        self.assertTrue(WatchlistEntry.objects.filter(
            manager=self.manager, player=player, status='watched').exists())

    def test_watch_find_rejects_foreign_club(self):
        """Ein fremder Fund darf nicht beobachtet werden (kein Cross-Club-Leak)."""
        player = self.pool[0]
        club2 = Club.objects.create(name='BVB', short_name='BVB', founded_year=1909,
                                    budget=Decimal('200000000'), league=self.league)
        mgr2 = ManagerProfile.objects.create(name='Manager 2')
        _, foreign_find = self._active_assignment_with_find(player, club=club2, manager=mgr2)
        with self.assertRaises(service.ScoutingError):
            service.watch_find(self.club, self.manager, foreign_find)
        self.assertFalse(WatchlistEntry.objects.filter(
            manager=self.manager, player=player).exists())


class ResolutionTests(ScoutingServiceBase):
    def _make_bid(self, club, manager, player, amount, window_date,
                  coin_earmarked=False):
        return ScoutingBid.objects.create(
            club=club, manager=manager, player=player, amount=Decimal(amount),
            min_bid=Decimal('5000000'), window_date=window_date,
            season_id=self.season_id, coin_earmarked=coin_earmarked,
            status=ScoutingBid.STATUS_ACTIVE,
        )

    def test_highest_bid_wins_and_charges(self):
        player = self.pool[0]
        club2 = Club.objects.create(name='BVB', short_name='BVB', founded_year=1909,
                                    budget=Decimal('200000000'), league=self.league)
        mgr2 = ManagerProfile.objects.create(name='Manager 2')
        wd = date(2026, 7, 3)
        self._make_bid(self.club, self.manager, player, '6000000', wd)
        self._make_bid(club2, mgr2, player, '8000000', wd)

        summary = service.resolve_due_windows(today=wd)
        self.assertEqual(summary['won'], 1)
        self.assertEqual(summary['lost'], 1)
        player.refresh_from_db()
        self.assertEqual(player.club_id, club2.id)
        self.assertEqual(player.pool_status, Player.POOL_STATUS_NONE)
        club2.refresh_from_db()
        self.assertEqual(club2.budget, Decimal('192000000'))
        self.assertTrue(FinanceTransaction.objects.filter(
            club=club2, typ='AUKTION').exists())

    def test_tie_breaks_to_earlier_bid(self):
        player = self.pool[0]
        club2 = Club.objects.create(name='BVB', short_name='BVB', founded_year=1909,
                                    budget=Decimal('200000000'), league=self.league)
        mgr2 = ManagerProfile.objects.create(name='Manager 2')
        wd = date(2026, 7, 3)
        first = self._make_bid(self.club, self.manager, player, '7000000', wd)
        self._make_bid(club2, mgr2, player, '7000000', wd)
        service.resolve_due_windows(today=wd)
        player.refresh_from_db()
        self.assertEqual(player.club_id, first.club_id)

    def test_future_window_not_resolved(self):
        player = self.pool[0]
        self._make_bid(self.club, self.manager, player, '6000000', date(2027, 1, 15))
        summary = service.resolve_due_windows(today=date(2026, 7, 3))
        self.assertEqual(summary['won'], 0)
        player.refresh_from_db()
        self.assertIsNone(player.club_id)

    def test_settlement_emits_news_for_winner_and_loser(self):
        player = self.pool[0]
        club2 = Club.objects.create(name='BVB', short_name='BVB', founded_year=1909,
                                    budget=Decimal('200000000'), league=self.league)
        mgr2 = ManagerProfile.objects.create(name='Manager 2')
        wd = date(2026, 7, 3)
        self._make_bid(self.club, self.manager, player, '6000000', wd)
        self._make_bid(club2, mgr2, player, '8000000', wd)

        service.resolve_due_windows(today=wd)

        win_news = ClubNewsItem.objects.filter(club=club2)
        loss_news = ClubNewsItem.objects.filter(club=self.club)
        self.assertEqual(win_news.count(), 1)
        self.assertEqual(loss_news.count(), 1)
        self.assertIn('verpflichtet', win_news.first().title)
        self.assertIn('nicht erfolgreich', loss_news.first().title)
        self.assertEqual(win_news.first().published_at, wd)


class CommitmentCoinTests(ScoutingServiceBase):
    def _seed_active_bids(self, n):
        wd = date(2026, 7, 3)
        for i in range(n):
            ScoutingBid.objects.create(
                club=self.club, manager=self.manager, player=self.pool[i],
                amount=Decimal('5000000'), min_bid=Decimal('5000000'),
                window_date=wd, season_id=self.season_id,
                status=ScoutingBid.STATUS_ACTIVE,
            )

    def test_third_bid_requires_coin(self):
        self._seed_active_bids(constants.BASE_COMMITMENT_SLOTS)
        target = self.pool[constants.BASE_COMMITMENT_SLOTS]
        _, find = self._active_assignment_with_find(target)
        # ohne Coin → Fehler
        with self.assertRaises(service.ScoutingError):
            service.place_bid(self.club, self.manager, find,
                              Decimal('6000000'), today=self.today)
        # mit Coin → erlaubt + earmarked
        HoenessCoin.objects.create(manager=self.manager, amount=1)
        bid = service.place_bid(self.club, self.manager, find,
                                Decimal('6000000'), today=self.today)
        self.assertTrue(bid.coin_earmarked)

    def test_coin_consumed_on_win(self):
        HoenessCoin.objects.create(manager=self.manager, amount=1)
        self._seed_active_bids(constants.BASE_COMMITMENT_SLOTS)
        target = self.pool[constants.BASE_COMMITMENT_SLOTS]
        _, find = self._active_assignment_with_find(target)
        bid = service.place_bid(self.club, self.manager, find,
                                Decimal('6000000'), today=self.today)
        service.resolve_due_windows(today=bid.window_date)
        bid.refresh_from_db()
        coin = HoenessCoin.objects.get(manager=self.manager)
        self.assertEqual(bid.status, ScoutingBid.STATUS_WON)
        self.assertTrue(bid.coin_used)
        self.assertEqual(coin.amount, 0)

    def test_coin_released_on_loss(self):
        HoenessCoin.objects.create(manager=self.manager, amount=1)
        self._seed_active_bids(constants.BASE_COMMITMENT_SLOTS)
        target = self.pool[constants.BASE_COMMITMENT_SLOTS]
        _, find = self._active_assignment_with_find(target)
        bid = service.place_bid(self.club, self.manager, find,
                                Decimal('6000000'), today=self.today)
        # Konkurrenzgebot gewinnt
        club2 = Club.objects.create(name='BVB', short_name='BVB', founded_year=1909,
                                    budget=Decimal('200000000'), league=self.league)
        ScoutingBid.objects.create(
            club=club2, manager=ManagerProfile.objects.create(name='M2'),
            player=target, amount=Decimal('9000000'), min_bid=Decimal('5000000'),
            window_date=bid.window_date, season_id=self.season_id,
            status=ScoutingBid.STATUS_ACTIVE,
        )
        service.resolve_due_windows(today=bid.window_date)
        bid.refresh_from_db()
        coin = HoenessCoin.objects.get(manager=self.manager)
        self.assertEqual(bid.status, ScoutingBid.STATUS_LOST)
        self.assertFalse(bid.coin_used)
        self.assertEqual(coin.amount, 1)

    def test_earmarked_bid_loses_without_coin_at_settlement(self):
        """Coin-belegtes Gebot gewinnt NICHT, wenn beim Zuschlag kein Coin da ist."""
        coin = HoenessCoin.objects.create(manager=self.manager, amount=1)
        self._seed_active_bids(constants.BASE_COMMITMENT_SLOTS)
        target = self.pool[constants.BASE_COMMITMENT_SLOTS]
        _, find = self._active_assignment_with_find(target)
        bid = service.place_bid(self.club, self.manager, find,
                                Decimal('6000000'), today=self.today)
        self.assertTrue(bid.coin_earmarked)
        # Coin wird zwischenzeitlich anderweitig aufgebraucht.
        coin.amount = 0
        coin.save(update_fields=['amount'])
        service.resolve_due_windows(today=bid.window_date)
        bid.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(bid.status, ScoutingBid.STATUS_LOST)
        self.assertFalse(bid.coin_used)
        # Spieler wurde NICHT verpflichtet (kein Gratis-Transfer am Limit).
        self.assertIsNone(target.club_id)
        self.assertEqual(target.pool_status, Player.POOL_STATUS_SCOUTABLE)


class AutoResolveOnMatchdayTests(ScoutingServiceBase):
    """close_matchday muss fällige Zuschlagstermine automatisch auflösen."""

    def test_close_matchday_resolves_due_window(self):
        from game.models import LeagueSeasonState
        from game.season_service import close_matchday

        player = self.pool[0]
        wd = date(2026, 7, 3)
        bid = ScoutingBid.objects.create(
            club=self.club, manager=self.manager, player=player,
            amount=Decimal('6000000'), min_bid=Decimal('5000000'),
            window_date=wd, season_id=self.season_id,
            status=ScoutingBid.STATUS_ACTIVE,
        )
        # Spieltag-Zustand: simuliert, bereit zum Abschluss.
        LeagueSeasonState.objects.create(
            league=self.league, season='0',
            current_matchday=1, is_simulated=True,
        )

        # Heute liegt am/nach dem Zuschlagstermin → Fenster ist fällig.
        with mock.patch('game.scouting.service.timezone') as tz:
            tz.localdate.return_value = wd
            close_matchday(self.league, '0')

        bid.refresh_from_db()
        player.refresh_from_db()
        self.assertEqual(bid.status, ScoutingBid.STATUS_WON)
        self.assertEqual(player.club_id, self.club.id)

    def test_close_matchday_leaves_future_window_untouched(self):
        from game.models import LeagueSeasonState
        from game.season_service import close_matchday

        player = self.pool[0]
        bid = ScoutingBid.objects.create(
            club=self.club, manager=self.manager, player=player,
            amount=Decimal('6000000'), min_bid=Decimal('5000000'),
            window_date=date(2027, 1, 15), season_id=self.season_id,
            status=ScoutingBid.STATUS_ACTIVE,
        )
        LeagueSeasonState.objects.create(
            league=self.league, season='0',
            current_matchday=1, is_simulated=True,
        )

        with mock.patch('game.scouting.service.timezone') as tz:
            tz.localdate.return_value = date(2026, 7, 3)
            close_matchday(self.league, '0')

        bid.refresh_from_db()
        player.refresh_from_db()
        self.assertEqual(bid.status, ScoutingBid.STATUS_ACTIVE)
        self.assertIsNone(player.club_id)


class AutoResolveOnSeasonTransitionTests(ScoutingServiceBase):
    """GameSeasonState muss fällige Zuschlagstermine beim Saisonwechsel/-start
    auflösen — schließt die Lücke in der Sommerpause, wenn kein Spieltag mehr
    geschlossen wird."""

    def _make_due_bid(self, wd):
        player = self.pool[0]
        bid = ScoutingBid.objects.create(
            club=self.club, manager=self.manager, player=player,
            amount=Decimal('6000000'), min_bid=Decimal('5000000'),
            window_date=wd, season_id=self.season_id,
            status=ScoutingBid.STATUS_ACTIVE,
        )
        return bid, player

    def test_season_advance_resolves_due_window(self):
        from game.models import GameSeasonState

        wd = date(2026, 7, 3)
        bid, player = self._make_due_bid(wd)
        state = GameSeasonState.objects.create(current_season=0, is_started=True)

        with mock.patch('game.scouting.service.timezone') as tz:
            tz.localdate.return_value = wd
            state.current_season = 1
            state.save()

        bid.refresh_from_db()
        player.refresh_from_db()
        self.assertEqual(bid.status, ScoutingBid.STATUS_WON)
        self.assertEqual(player.club_id, self.club.id)

    def test_season_start_resolves_due_window(self):
        from game.models import GameSeasonState

        wd = date(2026, 7, 3)
        bid, player = self._make_due_bid(wd)
        state = GameSeasonState.objects.create(current_season=0, is_started=False)

        with mock.patch('game.scouting.service.timezone') as tz:
            tz.localdate.return_value = wd
            state.is_started = True
            state.save()

        bid.refresh_from_db()
        player.refresh_from_db()
        self.assertEqual(bid.status, ScoutingBid.STATUS_WON)
        self.assertEqual(player.club_id, self.club.id)

    def test_season_advance_leaves_future_window_untouched(self):
        from game.models import GameSeasonState

        bid, player = self._make_due_bid(date(2027, 1, 15))
        state = GameSeasonState.objects.create(current_season=0, is_started=True)

        with mock.patch('game.scouting.service.timezone') as tz:
            tz.localdate.return_value = date(2026, 7, 3)
            state.current_season = 1
            state.save()

        bid.refresh_from_db()
        player.refresh_from_db()
        self.assertEqual(bid.status, ScoutingBid.STATUS_ACTIVE)
        self.assertIsNone(player.club_id)

    def test_unchanged_save_does_not_resolve(self):
        from game.models import GameSeasonState

        wd = date(2026, 7, 3)
        bid, player = self._make_due_bid(wd)
        state = GameSeasonState.objects.create(current_season=1, is_started=True)

        with mock.patch('game.scouting.service.timezone') as tz:
            tz.localdate.return_value = wd
            # Kein Saisonwechsel/-start → kein Auflösen.
            state.save()

        bid.refresh_from_db()
        player.refresh_from_db()
        self.assertEqual(bid.status, ScoutingBid.STATUS_ACTIVE)
        self.assertIsNone(player.club_id)


class CommunityTests(ScoutingServiceBase):
    def test_submission_raises_activity_and_enforces_limits(self):
        for i in range(constants.COMMUNITY_COUNTRY_WEEK_CAP):
            service.submit_community_profile(self.manager, 'TR',
                                             f'https://www.transfermarkt.de/x/{i}',
                                             today=self.today)
        net = CountryNetwork.objects.get(iso2='TR')
        self.assertEqual(net.activity_points,
                         constants.COMMUNITY_COUNTRY_WEEK_CAP * constants.COMMUNITY_ACTIVITY_POINTS)
        # Länder-Wochenlimit erreicht
        with self.assertRaises(service.ScoutingError):
            service.submit_community_profile(self.manager, 'TR',
                                             'https://www.transfermarkt.de/x/over',
                                             today=self.today)

    def test_moderation_approve_adds_community_points(self):
        sub = service.submit_community_profile(self.manager, 'TR',
                                               'https://www.transfermarkt.de/x/1',
                                               today=self.today)
        before = coverage.coverage_percent(CountryNetwork.objects.get(iso2='TR'))
        service.moderate_submission(sub, approve=True)
        after = coverage.coverage_percent(CountryNetwork.objects.get(iso2='TR'))
        self.assertGreaterEqual(after, before)
        sub.refresh_from_db()
        self.assertEqual(sub.status, CommunitySubmission.STATUS_APPROVED)


class DepartmentUpgradeTests(ScoutingServiceBase):
    def test_upgrade_charges_levels_up_and_logs(self):
        before = self.club.budget
        dept = service.upgrade_department(self.club, today=self.today)
        self.club.refresh_from_db()
        cost = Decimal(department.upgrade_cost(0))
        self.assertEqual(dept.level, 1)
        self.assertEqual(self.club.budget, before - cost)
        self.assertTrue(FinanceTransaction.objects.filter(
            club=self.club, typ='SCOUTING',
            beschreibung__icontains='Scoutingbüro').exists())

    def test_upgrade_blocked_without_budget(self):
        self.club.budget = Decimal('0.00')
        self.club.save(update_fields=['budget'])
        with self.assertRaises(service.ScoutingError):
            service.upgrade_department(self.club, today=self.today)

    def test_upgrade_blocked_at_max_level(self):
        from game.scouting.constants import MAX_DEPARTMENT_LEVEL
        dept = department.get_or_create_department(self.club)
        dept.level = MAX_DEPARTMENT_LEVEL
        dept.save(update_fields=['level'])
        with self.assertRaises(service.ScoutingError):
            service.upgrade_department(self.club, today=self.today)


class RejectAllFindsTests(ScoutingServiceBase):
    def test_reject_completes_assignment_and_marks_finds(self):
        a, find = self._active_assignment_with_find(self.pool[0])
        other = ScoutingFind.objects.create(
            assignment=a, player=self.pool[1], order=1,
            min_bid=Decimal('5000000'), status=ScoutingFind.STATUS_OFFERED)
        service.reject_all_finds(a)
        a.refresh_from_db(); find.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(a.status, ScoutingAssignment.STATUS_COMPLETED)
        self.assertEqual(find.status, ScoutingFind.STATUS_REJECTED)
        self.assertEqual(other.status, ScoutingFind.STATUS_REJECTED)

    def test_reject_inactive_assignment_raises(self):
        a, _ = self._active_assignment_with_find(self.pool[0])
        a.status = ScoutingAssignment.STATUS_COMPLETED
        a.save(update_fields=['status'])
        with self.assertRaises(service.ScoutingError):
            service.reject_all_finds(a)


class EligiblePlayersFilledTests(ScoutingServiceBase):
    def test_backfill_guarantees_minimum_from_wider_levels(self):
        from game.scouting import draw
        # Land mit nur einem eigenen Kandidaten, aber Region/Kontinent liefern mehr.
        only = _pool_player(nat='Portugal', last='PTone')
        narrow = draw.eligible_players('country', 'PT')
        self.assertIn(only.id, [p.id for p in narrow])
        self.assertLess(len(narrow), 3)
        filled = draw.eligible_players_filled('country', 'PT', 3)
        self.assertGreaterEqual(len(filled), 3)
        # Der eigene Landeskandidat steht weiterhin an erster Stelle (Vorrang).
        self.assertEqual(filled[0].id, only.id)

    def test_no_widening_when_scope_already_sufficient(self):
        from game.scouting import draw
        base = draw.eligible_players('country', 'TR')
        filled = draw.eligible_players_filled('country', 'TR', 3)
        self.assertGreaterEqual(len(base), 3)
        self.assertEqual([p.id for p in base], [p.id for p in filled])


class WatchlistAddRemoveTests(ScoutingServiceBase):
    """Manuelles Hinzufügen/Entfernen auf der managergebundenen Beobachtungsliste."""

    def test_add_to_watchlist_creates_watched(self):
        player = self.pool[0]
        entry = service.add_to_watchlist(self.manager, player)
        self.assertEqual(entry.status, 'watched')
        self.assertTrue(
            WatchlistEntry.objects.filter(
                manager=self.manager, player=player).exists())

    def test_add_to_watchlist_keeps_existing_status(self):
        player = self.pool[0]
        WatchlistEntry.objects.create(
            manager=self.manager, player=player, status='bid')
        service.add_to_watchlist(self.manager, player)
        entry = WatchlistEntry.objects.get(manager=self.manager, player=player)
        self.assertEqual(entry.status, 'bid')

    def test_remove_from_watchlist_deletes(self):
        player = self.pool[0]
        WatchlistEntry.objects.create(
            manager=self.manager, player=player, status='watched')
        service.remove_from_watchlist(self.manager, player)
        self.assertFalse(
            WatchlistEntry.objects.filter(
                manager=self.manager, player=player).exists())

    def test_add_to_watchlist_requires_manager(self):
        with self.assertRaises(service.ScoutingError):
            service.add_to_watchlist(None, self.pool[0])
