"""Tests für das Wettersystem (Modell, Service, Engine-Integration, Anzeige)."""

from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase

from game.models import DayWeather
from game.weather_service import (
    PHASES,
    PHASE_PROBABILITIES,
    PHASE_TEMPERATURES,
    SEASON_DAY1,
    SEASON_LENGTH_DAYS,
    WEATHER_TYPES,
    day_in_season,
    ensure_weather_for_day,
    ensure_weather_window,
    get_weather_for_date,
    phase_for_date,
    roll_weather,
    temperature_css_class,
    weather_context,
    weather_context_from_parts,
    weather_for_match,
)


class PhaseCalendarTests(TestCase):
    def test_phases_cover_all_90_days_exactly_once(self):
        covered = []
        for start, end, _key in PHASES:
            covered.extend(range(start, end + 1))
        self.assertEqual(sorted(covered), list(range(1, SEASON_LENGTH_DAYS + 1)))

    def test_probabilities_sum_to_100_per_phase(self):
        for phase, probs in PHASE_PROBABILITIES.items():
            self.assertEqual(sum(probs.values()), 100, phase)

    def test_day_in_season_anchor_and_wraparound(self):
        self.assertEqual(day_in_season(SEASON_DAY1), 1)
        self.assertEqual(day_in_season(SEASON_DAY1 + timedelta(days=89)), 90)
        self.assertEqual(day_in_season(SEASON_DAY1 + timedelta(days=90)), 1)

    def test_phase_for_date_matches_table(self):
        self.assertEqual(phase_for_date(SEASON_DAY1), 'spaetsommer')
        self.assertEqual(phase_for_date(SEASON_DAY1 + timedelta(days=19)), 'herbst')
        self.assertEqual(phase_for_date(SEASON_DAY1 + timedelta(days=41)), 'winter')
        self.assertEqual(phase_for_date(SEASON_DAY1 + timedelta(days=60)), 'fruehling')
        self.assertEqual(phase_for_date(SEASON_DAY1 + timedelta(days=82)), 'fruehsommer')


class RollWeatherTests(TestCase):
    def test_roll_respects_phase_type_and_temp_ranges(self):
        for offset in (0, 25, 50, 70, 85):  # eine Stichprobe je Phase
            sim_day = SEASON_DAY1 + timedelta(days=offset)
            phase = phase_for_date(sim_day)
            for _ in range(50):
                wtype, temp = roll_weather(sim_day)
                self.assertIn(wtype, WEATHER_TYPES)
                self.assertGreater(PHASE_PROBABILITIES[phase][wtype], 0)
                lo, hi = PHASE_TEMPERATURES[phase][wtype]
                self.assertGreaterEqual(temp, lo)
                self.assertLessEqual(temp, hi)

    def test_impossible_types_never_rolled(self):
        # Spätsommer: kein Schnee; Herbst: weder Hitze noch Schnee
        for _ in range(200):
            wtype, _ = roll_weather(SEASON_DAY1)
            self.assertNotEqual(wtype, 'schnee')
        herbst_day = SEASON_DAY1 + timedelta(days=25)
        for _ in range(200):
            wtype, _ = roll_weather(herbst_day)
            self.assertNotIn(wtype, ('hitze', 'schnee'))


class PersistenceTests(TestCase):
    def test_ensure_weather_for_day_is_immutable(self):
        d = date(2030, 1, 15)
        dw1, created1 = ensure_weather_for_day(d)
        dw2, created2 = ensure_weather_for_day(d)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(dw1.weather_type, dw2.weather_type)
        self.assertEqual(dw1.temperature, dw2.temperature)

    def test_ensure_weather_window_backfills_today_plus_7(self):
        created = ensure_weather_window()
        self.assertEqual(created, 8)
        today = date.today()
        for i in range(8):
            self.assertIsNotNone(get_weather_for_date(today + timedelta(days=i)))
        # Idempotent
        self.assertEqual(ensure_weather_window(), 0)

    def test_get_weather_for_date_never_rolls(self):
        d = date(2031, 6, 1)
        self.assertIsNone(get_weather_for_date(d))
        self.assertEqual(DayWeather.objects.filter(sim_day=d).count(), 0)

    def test_weather_for_match_rolls_on_demand(self):
        d = date(2031, 7, 1)
        dw = weather_for_match(d)
        self.assertIsNotNone(dw)
        self.assertEqual(get_weather_for_date(d).weather_type, dw.weather_type)

    def test_roll_daily_weather_command_idempotent(self):
        call_command('roll_daily_weather', verbosity=0)
        count_after_first = DayWeather.objects.count()
        call_command('roll_daily_weather', verbosity=0)
        self.assertEqual(DayWeather.objects.count(), count_after_first)


class DisplayHelperTests(TestCase):
    def test_temperature_css_class_boundaries(self):
        self.assertEqual(temperature_css_class(28), 'wx-temp--heat')
        self.assertEqual(temperature_css_class(27), 'wx-temp--normal')
        self.assertEqual(temperature_css_class(10), 'wx-temp--normal')
        self.assertEqual(temperature_css_class(9), 'wx-temp--cold')
        self.assertEqual(temperature_css_class(1), 'wx-temp--cold')
        self.assertEqual(temperature_css_class(0), 'wx-temp--frost')
        self.assertEqual(temperature_css_class(-8), 'wx-temp--frost')

    def test_weather_context_from_parts(self):
        ctx = weather_context_from_parts('regen', 12)
        self.assertEqual(ctx['label'], 'Regen')
        self.assertEqual(ctx['temp_class'], 'wx-temp--normal')
        self.assertTrue(ctx['flavor'])
        self.assertIsNone(weather_context_from_parts('unbekannt', 12))
        self.assertIsNone(weather_context_from_parts('regen', None))

    def test_weather_context_from_instance(self):
        dw, _ = ensure_weather_for_day(date(2030, 3, 3))
        ctx = weather_context(dw)
        self.assertEqual(ctx['type'], dw.weather_type)
        self.assertIsNone(weather_context(None))


class EngineModifierTests(TestCase):
    """_apply_weather_to_compiled: None/normal = No-Op, Typen greifen multiplikativ."""

    def _base_comp(self):
        return {
            'xg_for': 1.0,
            'foul_multiplier': 1.0,
            'fatigue_cost': 1.0,
            'pressing_index': 0.5,
            'shot_volume': 1.0,
            'directness': 1.0,
            'tempo': 1.0,
        }

    def _base_tactic(self):
        return {
            'attack_focus': 'fluegelspiel',
            'buildup': {'tempo': 'hoch', 'defense': 'normal', 'midfield': 'normal', 'attack': 'normal'},
            'defending': {'zweikampf': 'hart'},
            'pressing': {'defense': 'intensiv', 'midfield': 'intensiv', 'attack': 'hoch'},
        }

    def test_none_and_normal_are_noop(self):
        from game.match_engine import _apply_weather_to_compiled
        for wx in (None, 'normal'):
            comp = self._base_comp()
            before = dict(comp)
            _apply_weather_to_compiled(comp, wx, self._base_tactic(), 10, None)
            self.assertEqual(comp, before, f'weather={wx} muss No-Op sein')

    def test_regen_increases_fouls(self):
        from game.match_engine import _apply_weather_to_compiled
        comp = self._base_comp()
        _apply_weather_to_compiled(comp, 'regen', self._base_tactic(), 10, None)
        self.assertGreater(comp['foul_multiplier'], 1.0)

    def test_hitze_raises_fatigue_and_caps_late_pressing(self):
        from game.match_engine import _apply_weather_to_compiled
        comp_early = self._base_comp()
        _apply_weather_to_compiled(comp_early, 'hitze', self._base_tactic(), 10, None)
        self.assertGreater(comp_early['fatigue_cost'], 1.0)
        comp_late = self._base_comp()
        _apply_weather_to_compiled(comp_late, 'hitze', self._base_tactic(), 70, None)
        self.assertLess(comp_late['pressing_index'], 0.5)

    def test_wind_reduces_xg(self):
        from game.match_engine import _apply_weather_to_compiled
        comp = self._base_comp()
        _apply_weather_to_compiled(comp, 'wind', self._base_tactic(), 10, None)
        self.assertLess(comp['xg_for'], 1.0)

    def test_schnee_hard_tackling_more_fouls(self):
        from game.match_engine import _apply_weather_to_compiled
        comp = self._base_comp()
        _apply_weather_to_compiled(comp, 'schnee', self._base_tactic(), 10, None)
        self.assertGreater(comp['foul_multiplier'], 1.0)


class SimulateMatchWeatherTests(TestCase):
    """Ende-zu-Ende: weather-Parameter landet im Ergebnis, None bleibt Baseline."""

    @classmethod
    def setUpTestData(cls):
        from decimal import Decimal
        from game.models import Club, League, Player, PlayerStrengthProfile
        league = League.objects.create(name='Wetter-Testliga', country='Deutschland')
        positions = ['TW', 'LV', 'IV', 'IV', 'RV', 'DM', 'ZM', 'ZM', 'OM', 'ST', 'ST']
        clubs = []
        for name in ('Wetter FC', 'SV Sturm'):
            club = Club.objects.create(
                name=name,
                short_name=name[:4].upper(),
                founded_year=2000,
                budget=Decimal('5000000.00'),
                league=league,
            )
            for i, pos in enumerate(positions):
                p = Player.objects.create(
                    first_name=f'Sp{i}',
                    last_name=name[:4],
                    wsc_player_id=f'WSC-WX-{name[:4]}-{i}',
                    date_of_birth=date(1995, 1, 1),
                    age=29,
                    position=pos,
                    main_position_1=pos,
                    club=club,
                )
                PlayerStrengthProfile.objects.create(
                    player=p,
                    base_strength=Decimal('60'),
                )
            clubs.append(club)
        cls.home, cls.away = clubs

    def test_weather_key_in_result_and_none_baseline(self):
        from game.match_engine import simulate_match
        res_none = simulate_match(self.home, self.away)
        self.assertIsNone(res_none.get('weather'))
        res_wx = simulate_match(
            self.home, self.away, weather={'type': 'regen', 'temperature': 11}
        )
        self.assertEqual(res_wx['weather'], {'type': 'regen', 'temperature': 11})

    def test_dayweather_instance_accepted(self):
        from game.match_engine import simulate_match
        dw, _ = ensure_weather_for_day(date(2030, 12, 24))
        res = simulate_match(self.home, self.away, weather=dw)
        self.assertEqual(res['weather']['type'], dw.weather_type)
        self.assertEqual(res['weather']['temperature'], dw.temperature)
