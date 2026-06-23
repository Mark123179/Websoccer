"""Unit-Tests für die reinen Scouting-Kernfunktionen (Task #594).

Deckt ab: Schwellen + Karten-Datenvertrag (kein pool_count), Fenster-/Saison-
Berechnung, Preisformel, Kandidatenfilter/-gewichtung und Top-Star-Ausschluss.
"""

from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from game.models import League, Club, Player, PlayerStrengthProfile, CountryNetwork
from game.scouting import constants, windows, pricing, coverage, draw


def make_pool_player(nat='Türkei', strength=70, potential=75, age=22,
                     pos='ST', market_value='4000000', club=None,
                     pool_status=Player.POOL_STATUS_SCOUTABLE,
                     scouting_category='', first='Pool', last='Spieler'):
    player = Player.objects.create(
        first_name=first, last_name=last, age=age,
        position='Sturm', main_position_1=pos,
        nationalities=nat,
        market_value=(Decimal(market_value) if market_value is not None else None),
        potential=potential, club=club, pool_status=pool_status,
        scouting_category=scouting_category,
    )
    PlayerStrengthProfile.objects.create(player=player, base_strength=Decimal(strength))
    return player


class WindowAndSeasonTests(TestCase):
    def test_next_window_after_summer(self):
        self.assertEqual(windows.next_window_after(date(2026, 6, 23)), date(2026, 7, 3))

    def test_next_window_after_late_summer_rolls_to_winter(self):
        self.assertEqual(windows.next_window_after(date(2026, 7, 10)), date(2027, 1, 15))

    def test_window_for_bid_respects_seven_day_lead(self):
        # 10 Tage vor dem Termin → zählt für 03.07.
        self.assertEqual(windows.window_for_bid(date(2026, 6, 23)), date(2026, 7, 3))
        # 4 Tage vor dem Termin → rollt auf den nächsten Termin (15.01.).
        self.assertEqual(windows.window_for_bid(date(2026, 6, 29)), date(2027, 1, 15))

    def test_all_window_dates_in_range(self):
        out = windows.all_window_dates_in_range(date(2026, 1, 1), date(2027, 1, 31))
        self.assertIn(date(2026, 1, 15), out)
        self.assertIn(date(2026, 7, 3), out)
        self.assertIn(date(2027, 1, 15), out)


class CoverageThresholdTests(TestCase):
    def test_country_scoutable_at_threshold(self):
        # 49 < 50 → nicht scoutbar
        Player.objects.bulk_create([
            Player(first_name='A', last_name=str(i), age=22, position='Sturm',
                   main_position_1='ST', nationalities='Türkei',
                   pool_status=Player.POOL_STATUS_SCOUTABLE)
            for i in range(constants.COUNTRY_THRESHOLD - 1)
        ])
        self.assertFalse(coverage.is_country_scoutable('TR'))
        # genau 50 → scoutbar
        Player.objects.create(first_name='A', last_name='last', age=22,
                              position='Sturm', main_position_1='ST',
                              nationalities='Türkei',
                              pool_status=Player.POOL_STATUS_SCOUTABLE)
        self.assertTrue(coverage.is_country_scoutable('TR'))

    def test_paused_network_is_not_scoutable(self):
        net = CountryNetwork.objects.create(iso2='TR', name='Türkei', is_paused=True)
        for i in range(constants.COUNTRY_THRESHOLD + 5):
            Player.objects.create(first_name='A', last_name=str(i), age=22,
                                  position='Sturm', main_position_1='ST',
                                  nationalities='Türkei',
                                  pool_status=Player.POOL_STATUS_SCOUTABLE)
        self.assertFalse(coverage.is_country_scoutable('TR', network=net))

    def test_unsupported_country_unavailable(self):
        self.assertEqual(coverage.country_status('ZZ'), coverage.STATUS_UNAVAILABLE)


class MapContractTests(TestCase):
    def test_contract_never_leaks_pool_count(self):
        for i in range(60):
            Player.objects.create(first_name='A', last_name=str(i), age=22,
                                  position='Sturm', main_position_1='ST',
                                  nationalities='Türkei',
                                  pool_status=Player.POOL_STATUS_SCOUTABLE)
        data = coverage.map_data()
        self.assertIn('countries', data)
        for country in data['countries']:
            self.assertEqual(set(country.keys()), coverage.ALLOWED_CONTRACT_KEYS)
            self.assertNotIn('pool_count', country)

    def test_coverage_percent_from_points_only(self):
        # Großer Pool, aber keine Community-Punkte → 0 % Abdeckung (kein Leak).
        for i in range(60):
            Player.objects.create(first_name='A', last_name=str(i), age=22,
                                  position='Sturm', main_position_1='ST',
                                  nationalities='Türkei',
                                  pool_status=Player.POOL_STATUS_SCOUTABLE)
        net = CountryNetwork.objects.create(iso2='TR', name='Türkei')
        self.assertEqual(coverage.coverage_percent(net), 0)
        net.community_points = 40
        net.save()
        self.assertEqual(coverage.coverage_percent(net), 50)


class PricingTests(TestCase):
    def test_min_bid_is_premium_over_market_value(self):
        p = make_pool_player(market_value='4500000', age=22, strength=76, potential=80)
        bid = pricing.min_bid_for_player(p)
        self.assertGreater(bid, Decimal('4500000'))
        # gerundet auf 100k
        self.assertEqual(bid % Decimal(constants.BID_ROUND_TO), Decimal('0'))

    def test_min_bid_deterministic(self):
        p = make_pool_player(market_value='3200000', age=20, strength=72, potential=78)
        self.assertEqual(pricing.min_bid_for_player(p), pricing.min_bid_for_player(p))

    def test_min_bid_floor_for_missing_market_value(self):
        p = make_pool_player(market_value=None, age=24, strength=60, potential=62)
        self.assertGreaterEqual(pricing.min_bid_for_player(p), Decimal(constants.BID_MIN_FLOOR))


class DrawTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Testliga', country='Deutschland')

    def test_eligible_excludes_top_stars_bound_and_reserved(self):
        ok = make_pool_player(last='OK', strength=72)
        make_pool_player(last='TopStar', strength=constants.TOP_STAR_STRENGTH + 2)
        make_pool_player(last='Reserved', strength=70,
                         pool_status=Player.POOL_STATUS_AUCTION_RESERVED)
        bound_club = Club.objects.create(name='Bound', short_name='BND',
                                         founded_year=1900,
                                         budget=Decimal('0'), league=self.league)
        make_pool_player(last='Bound', strength=70, club=bound_club)

        eligible = draw.eligible_players('country', 'TR')
        ids = {p.id for p in eligible}
        self.assertIn(ok.id, ids)
        self.assertEqual(len(eligible), 1)

    def test_draw_returns_exactly_k(self):
        for i in range(8):
            make_pool_player(last=f'P{i}', strength=68 + i % 5)
        cands = draw.eligible_players('country', 'TR')
        chosen = draw.draw_candidates(cands, team_avg=70, profile='ergaenzung',
                                      position='ST', precision=0.8, seed=123, k=3)
        self.assertEqual(len(chosen), 3)
        # deterministisch
        chosen2 = draw.draw_candidates(cands, team_avg=70, profile='ergaenzung',
                                       position='ST', precision=0.8, seed=123, k=3)
        self.assertEqual([p.id for p in chosen], [p.id for p in chosen2])

    def test_find_model_has_no_strength_or_potential_fields(self):
        from game.models import ScoutingFind
        field_names = {f.name for f in ScoutingFind._meta.get_fields()}
        self.assertNotIn('base_strength', field_names)
        self.assertNotIn('potential', field_names)
