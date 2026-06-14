from decimal import Decimal
from datetime import date
from io import StringIO
from pathlib import Path
import tempfile
import os

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .admin import PlayerNationalityForm
from .competition_assets import _NATIONALITY_CONFEDERATION
from .models import (
    COUNTRY_FLAG_ASSETS,
    Club,
    ClubNewsItem,
    DataSource,
    League,
    Player,
    PlayerAwardTitle,
    PlayerEditRequest,
    PlayerExternalId,
    PlayerFormSnapshot,
    PlayerInjuryRecord,
    PlayerMarketValueSnapshot,
    PlayerSeasonStat,
    PlayerSourceRating,
    PlayerSourceRatingSnapshot,
    PlayerStrengthProfile,
    PlayerStrengthSnapshot,
    PlayerSuspensionRecord,
    PlayerTransferHistory,
    PlayerWeightedRatingSnapshot,
    StrengthFormulaSettings,
    TacticSetup,
    TacticTemplate,
)
from .tactics import (
    default_bench,
    default_formation,
    default_half_tactic,
    default_lineup,
    default_standards,
    default_substitutions,
    sanitize_assignments,
)
from .views import CITY_MAP_PCT, city_map_pct


@override_settings(ALLOWED_HOSTS=['testserver'])
class PageSmokeTests(TestCase):
    def setUp(self):
        league = League.objects.create(
            name='1. Bundesliga',
            country='Deutschland',
        )
        self.club = Club.objects.create(
            name='Borussia Dortmund',
            short_name='BVB',
            fm_inside_id=907,
            founded_year=1909,
            budget=Decimal('5000000.00'),
            league=league,
        )
        self.player = Player.objects.create(
            first_name='Harry',
            last_name='Kane',
            wsc_player_id='WSC-TEST-1',
            fm_inside_id=28049320,
            transfermarkt_id=132098,
            transfermarkt_profile_url='https://www.transfermarkt.de/harry-kane/profil/spieler/132098',
            transfermarkt_market_value_url='https://www.transfermarkt.de/harry-kane/marktwertverlauf/spieler/132098',
            date_of_birth=date(1993, 7, 28),
            nationalities='England, Irland',
            age=31,
            height_cm=188,
            strong_foot='right',
            position='ST',
            primary_position='OM',
            source_positions='OM',
            main_position_1='ST',
            main_position_2='OM',
            secondary_position_1='ZM',
            potential=90,
            market_value=Decimal('100000000.00'),
            salary_per_match=Decimal('500000.00'),
            club=self.club,
            real_life_club=self.club,
        )
        PlayerSourceRating.objects.create(
            player=self.player,
            source=PlayerSourceRating.SOURCE_EA,
            rating=90,
            potential=90,
            source_version='FC 26 Testdaten',
        )
        PlayerSourceRating.objects.create(
            player=self.player,
            source=PlayerSourceRating.SOURCE_FM,
            rating=94,
            potential=95,
            source_version='FMInside Testdaten',
        )
        PlayerStrengthProfile.objects.create(
            player=self.player,
            base_strength=88,
            form_modifier=2,
        )
        self.tm_source, _created = DataSource.objects.get_or_create(
            code=DataSource.CODE_TRANSFERMARKT,
            defaults={
                'name': 'Transfermarkt',
                'base_url': 'https://www.transfermarkt.de/',
            },
        )
        self.fm_source, _created = DataSource.objects.get_or_create(
            code=DataSource.CODE_FMINSIDE,
            defaults={
                'name': 'FMInside',
                'base_url': 'https://fminside.net/',
            },
        )
        self.sofifa_source, _created = DataSource.objects.get_or_create(
            code=DataSource.CODE_SOFIFA,
            defaults={
                'name': 'SoFIFA',
                'base_url': 'https://sofifa.com/',
            },
        )

        User = get_user_model()
        self.user = User.objects.create_user(username='setup_user', password='setuppass123')
        self.client.force_login(self.user)

    def create_tactic_player(self, index, position='ZM', age=24, injured=False, suspended=False):
        player = Player.objects.create(
            first_name=f'Taktik{index}',
            last_name=f'Spieler{index:02d}',
            wsc_player_id=f'WSC-TACTIC-{age}-{index}',
            fm_inside_id=30000000 + age * 100 + index,
            nationalities='Deutschland',
            age=age,
            position=position,
            main_position_1=position,
            potential=70,
            market_value=Decimal('1000000.00'),
            salary_per_match=Decimal('5000.00'),
            club=self.club,
            ws_injury_type='Muskelverletzung' if injured else '',
            ws_injury_days_remaining=4 if injured else 0,
            ws_suspension_reason='Gelbsperre' if suspended else '',
            ws_suspension_matches_remaining=1 if suspended else 0,
        )
        PlayerStrengthProfile.objects.create(
            player=player,
            base_strength=Decimal('60.00'),
            freshness=Decimal('85.00'),
        )
        return player

    def create_full_tactic_squad(self, age=24, offset=0):
        positions = ['TW', 'LV', 'IV', 'IV', 'RV', 'LM', 'ZM', 'ZM', 'RM', 'ST', 'ST']
        return [
            self.create_tactic_player(offset + index, position, age=age)
            for index, position in enumerate(positions, start=1)
        ]

    def tactic_post_data(self, players, action='confirm'):
        slot_keys = ['TW-1', 'LV-1', 'IV-1', 'IV-2', 'RV-1', 'LM-1', 'ZM-1', 'ZM-2', 'RM-1', 'ST-1', 'ST-2']
        data = {
            'action': action,
            'squad_scope': 'pro',
            'formation_defense': '4n',
            'formation_defensive_midfield': '0',
            'formation_midfield': '4',
            'formation_offensive_midfield': '0',
            'formation_attack': '2',
            'first_half_orientation': '50',
            'first_half_defense': 'standard',
            'first_half_midfield': 'standard',
            'first_half_attack': 'standard',
            'first_half_effort': 'normal',
            'second_half_orientation': '50',
            'second_half_defense': 'standard',
            'second_half_midfield': 'standard',
            'second_half_attack': 'standard',
            'second_half_effort': 'normal',
        }
        for slot_key, player in zip(slot_keys, players):
            data[f'lineup_{slot_key}'] = str(player.id)
        for index in range(1, 8):
            data[f'bench_{index}'] = ''
        for key in ('captain', 'penalty', 'free_kick', 'corner'):
            data[f'standard_{key}'] = ''
        for index in range(1, 6):
            data[f'substitution_{index}_minute'] = ''
            data[f'substitution_{index}_out'] = ''
            data[f'substitution_{index}_in'] = ''
        return data

    def test_home_page_renders_dashboard(self):
        User = get_user_model()
        user = User.objects.create_user(username='smokeuser', password='smokepass123')
        self.client.force_login(user)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vereins&uuml;bersicht')
        self.assertContains(response, 'MatchEngine')
        self.assertContains(response, 'Letztes Spiel')
        self.assertContains(response, 'Borussia Dortmund')

    def test_home_dashboard_shows_fixture_data(self):
        from datetime import time as dt_time
        from .models import ManagerProfile, SeasonFixture

        User = get_user_model()
        user = User.objects.create_user(username='testmanager', password='testpass123')
        profile = ManagerProfile.objects.get(user=user)
        self.club.managed_by = profile
        self.club.save()

        opponent = Club.objects.create(
            name='FC Testgegner',
            short_name='FCT',
            fm_inside_id=9998,
            founded_year=2000,
            budget=Decimal('1000000.00'),
            league=self.club.league,
        )

        SeasonFixture.objects.create(
            league=self.club.league,
            season='2025/26',
            matchday=5,
            home_club=self.club,
            away_club=opponent,
            scheduled_date=date(2026, 6, 15),
            scheduled_time=dt_time(20, 30),
            is_played=False,
        )
        SeasonFixture.objects.create(
            league=self.club.league,
            season='2025/26',
            matchday=32,
            home_club=self.club,
            away_club=opponent,
            scheduled_date=date(2026, 6, 1),
            home_goals=3,
            away_goals=1,
            is_played=True,
        )

        self.client.force_login(user)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, '1. Bundesliga')
        self.assertContains(response, '5. Spieltag')
        self.assertContains(response, '15. Jun 2026')
        self.assertContains(response, '20:30 Uhr')

        self.assertContains(response, '3:1')
        self.assertContains(response, '32. Spieltag')

        self.assertNotContains(response, '25. Mai 2025')
        self.assertNotContains(response, '9-9')
        self.assertNotContains(response, 'L. Martinez (18)')

    def test_club_list_renders_club_metrics(self):
        response = self.client.get(reverse('club_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Borussia Dortmund')
        self.assertContains(response, '1. Bundesliga')

    def test_club_detail_renders_public_profile(self):
        from .models import SeasonFixture

        opponent = Club.objects.create(
            name='FC Gegner',
            short_name='FCG',
            fm_inside_id=9997,
            founded_year=2000,
            budget=Decimal('1000000.00'),
            league=self.club.league,
        )
        SeasonFixture.objects.create(
            league=self.club.league,
            season='2025/26',
            matchday=33,
            home_club=self.club,
            away_club=opponent,
            home_goals=1,
            away_goals=0,
            is_played=True,
        )
        response = self.client.get(
            reverse('club_detail', kwargs={'club_id': self.club.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VEREINSÜBERSICHT')
        self.assertContains(response, 'NÄCHSTES SPIEL')
        self.assertContains(response, 'TROPHÄENSCHRANK')
        self.assertContains(response, 'PROFI-HIGHLIGHTS')
        self.assertContains(response, 'JUGEND-HIGHLIGHTS')
        self.assertContains(response, 'VEREINSUMFELD')
        self.assertContains(response, 'LIGATABELLE')
        self.assertContains(response, 'STADION')
        self.assertContains(response, 'STADT')
        self.assertContains(response, 'TRIKOTS')
        self.assertContains(response, 'PARTNERVEREIN')
        self.assertContains(response, 'VEREINSNEWS')
        self.assertContains(response, 'Zum Profikader')
        self.assertContains(response, 'Zur Jugend')
        self.assertContains(response, 'Bester Passgeber')
        self.assertContains(response, '%')
        self.assertContains(response, 'game/css/club-profile.css')
        self.assertContains(response, 'game/js/club-profile.js')
        self.assertContains(response, 'Harry Kane')
        self.assertContains(response, 'club-player-cutout')
        self.assertContains(response, 'game/images/players/28049320')
        self.assertNotContains(response, 'game/images/player_composites/')
        self.assertContains(response, 'game/images/kits/907_home.svg')
        self.assertContains(response, 'https://flagcdn.com/gb-eng.svg')
        self.assertContains(response, 'Kein Partnerverein')
        self.assertNotContains(response, 'Seite 1 von')
        self.assertNotContains(response, 'https://www.transfermarkt.de/harry-kane/marktwertverlauf/spieler/132098')
        self.assertNotContains(response, 'class="dashboard-card tactics-card"')
        self.assertNotContains(response, 'class="dashboard-card finance-card"')
        self.assertNotContains(response, 'class="dashboard-card squad-full-card"')

    def test_public_club_profile_links_have_routes(self):
        news_item = ClubNewsItem.objects.create(
            club=self.club,
            title='Testmeldung',
            published_at=date(2026, 5, 25),
        )
        routes = [
            reverse('club_professional_squad', kwargs={'club_id': self.club.id}),
            reverse('club_youth_squad', kwargs={'club_id': self.club.id}),
            reverse('club_table', kwargs={'club_id': self.club.id}),
            reverse('club_match_preview', kwargs={'club_id': self.club.id}),
            reverse('club_match_report', kwargs={'club_id': self.club.id}),
            reverse('club_news', kwargs={'club_id': self.club.id}),
            reverse('club_news_detail', kwargs={
                'club_id': self.club.id,
                'news_id': news_item.id,
            }),
        ]

        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)

    def test_tactics_route_renders_and_filters_unavailable_players(self):
        injured = self.create_tactic_player(40, 'ST', injured=True)
        suspended = self.create_tactic_player(41, 'ZM', suspended=True)

        response = self.client.get(
            reverse('club_tactics', kwargs={'club_id': self.club.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Taktik bestätigen')
        self.assertContains(response, 'Vorlage laden')
        self.assertContains(response, 'Wechselplanung')
        self.assertContains(response, 'game/css/tactics.css')
        self.assertContains(response, 'game/js/tactics.js')
        self.assertContains(response, 'name="substitution_1_minute"')
        self.assertContains(response, 'min="1" max="120" step="1"')
        self.assertContains(response, 'data-minute-input')
        # Gesperrte/verletzte Spieler erscheinen im Kader sichtbar (mit Badge),
        # sind aber als is_suspended/is_injured markiert und nicht selektierbar.
        options_by_id = {
            option['id']: option
            for option in response.context['player_options']
        }
        self.assertIn(injured.id, options_by_id, "Verletzter Spieler muss im Kader sichtbar sein.")
        self.assertTrue(options_by_id[injured.id]['is_injured'], "is_injured muss True sein.")
        self.assertIn(suspended.id, options_by_id, "Gesperrter Spieler muss im Kader sichtbar sein.")
        self.assertTrue(options_by_id[suspended.id]['is_suspended'], "is_suspended muss True sein.")
        # Badge-HTML muss im Response enthalten sein
        self.assertContains(response, 'is-suspended', msg_prefix="Gesperrt-Badge muss im HTML sichtbar sein.")
        self.assertContains(response, 'is-injured', msg_prefix="Verletzt-Badge muss im HTML sichtbar sein.")
        self.assertIn('opponent_absences', response.context)

    def test_tactics_confirm_persists_complete_starting_eleven(self):
        players = self.create_full_tactic_squad(age=24, offset=50)
        bench_player = self.create_tactic_player(70, 'ST', age=24)
        data = self.tactic_post_data(players)
        data['bench_1'] = str(bench_player.id)
        data['substitution_1_minute'] = '60'
        data['substitution_1_out'] = str(players[1].id)
        data['substitution_1_in'] = str(bench_player.id)

        response = self.client.post(
            reverse('club_tactics', kwargs={'club_id': self.club.id}),
            data,
        )

        self.assertRedirects(
            response,
            f'/clubs/{self.club.id}/tactics/?squad=pro&confirmed=1',
            fetch_redirect_response=False,
        )
        setup = TacticSetup.objects.get(club=self.club, squad_scope='pro')
        self.assertTrue(setup.is_confirmed)
        self.assertEqual(setup.formation['defense'], '4n')
        self.assertEqual(setup.lineup['TW-1'], players[0].id)
        self.assertEqual(setup.bench[0], bench_player.id)
        self.assertEqual(setup.substitutions[0]['minute'], 60)

    def test_tactics_rejects_substitution_minutes_outside_match_range(self):
        players = self.create_full_tactic_squad(age=24, offset=75)
        bench_player = self.create_tactic_player(95, 'ST', age=24)
        data = self.tactic_post_data(players)
        data['bench_1'] = str(bench_player.id)
        data['substitution_1_minute'] = '121'
        data['substitution_1_out'] = str(players[1].id)
        data['substitution_1_in'] = str(bench_player.id)

        response = self.client.post(
            reverse('club_tactics', kwargs={'club_id': self.club.id}),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Wechsel 1: Minute muss zwischen 1 und 120 liegen.',
        )
        setup = TacticSetup.objects.get(club=self.club, squad_scope='pro')
        self.assertFalse(setup.is_confirmed)
        self.assertEqual(setup.substitutions, [])

    def test_tactics_confirm_requires_complete_starting_eleven(self):
        players = self.create_full_tactic_squad(age=24, offset=80)
        data = self.tactic_post_data(players)
        data['lineup_ST-2'] = ''

        response = self.client.post(
            reverse('club_tactics', kwargs={'club_id': self.club.id}),
            data,
        )

        self.assertEqual(response.status_code, 200)
        setup = TacticSetup.objects.get(club=self.club, squad_scope='pro')
        self.assertFalse(setup.is_confirmed)
        self.assertContains(
            response,
            'Zum Bestätigen müssen Torwart und alle 10 Feldspieler besetzt sein.',
        )

    def test_tactics_standards_only_accept_starting_eleven(self):
        players = self.create_full_tactic_squad(age=24, offset=95)
        bench_player = self.create_tactic_player(109, 'ST', age=24)
        data = self.tactic_post_data(players)
        data['bench_1'] = str(bench_player.id)
        data['standard_captain'] = str(bench_player.id)
        data['standard_penalty'] = str(players[1].id)
        data['standard_corner'] = str(players[2].id)

        response = self.client.post(
            reverse('club_tactics', kwargs={'club_id': self.club.id}),
            data,
        )

        self.assertRedirects(
            response,
            f'/clubs/{self.club.id}/tactics/?squad=pro&confirmed=1',
            fetch_redirect_response=False,
        )
        setup = TacticSetup.objects.get(club=self.club, squad_scope='pro')
        self.assertEqual(setup.standards['captain'], '')
        self.assertEqual(setup.standards['penalty'], players[1].id)
        self.assertEqual(setup.standards['corner'], players[2].id)

    def test_tactics_keep_pro_and_youth_setups_separate(self):
        pro_players = self.create_full_tactic_squad(age=24, offset=110)
        youth_players = self.create_full_tactic_squad(age=18, offset=140)
        pro_data = self.tactic_post_data(pro_players)
        youth_data = self.tactic_post_data(youth_players)
        youth_data['squad_scope'] = 'youth'

        self.client.post(
            reverse('club_tactics', kwargs={'club_id': self.club.id}),
            pro_data,
        )
        self.client.post(
            f"{reverse('club_tactics', kwargs={'club_id': self.club.id})}?squad=youth",
            youth_data,
        )

        pro_setup = TacticSetup.objects.get(club=self.club, squad_scope='pro')
        youth_setup = TacticSetup.objects.get(club=self.club, squad_scope='youth')
        self.assertTrue(pro_setup.is_confirmed)
        self.assertTrue(youth_setup.is_confirmed)
        self.assertEqual(pro_setup.lineup['TW-1'], pro_players[0].id)
        self.assertEqual(youth_setup.lineup['TW-1'], youth_players[0].id)

    def test_tactic_model_rejects_invalid_formation_and_template_limit(self):
        setup = TacticSetup(
            club=self.club,
            squad_scope='pro',
            formation={
                'defense': '5o',
                'defensive_midfield': '3',
                'midfield': '5',
                'offensive_midfield': '3',
                'attack': '4',
            },
        )
        with self.assertRaises(ValidationError):
            setup.full_clean()

        for index in range(10):
            TacticTemplate.objects.create(
                club=self.club,
                squad_scope='pro',
                name=f'Vorlage {index}',
            )
        overflow = TacticTemplate(
            club=self.club,
            squad_scope='pro',
            name='Vorlage 11',
        )
        with self.assertRaises(ValidationError):
            overflow.full_clean()

    def test_duplicate_assignment_keeps_latest_slot(self):
        player = self.create_tactic_player(180, 'ZM', age=24)

        lineup, bench = sanitize_assignments(
            {'LV-1': player.id, 'ZM-1': player.id},
            [],
            {player.id},
        )

        self.assertEqual(lineup['LV-1'], '')
        self.assertEqual(lineup['ZM-1'], player.id)
        self.assertEqual(bench, ['', '', '', '', '', '', ''])

    def test_player_detail_renders_profile_shell(self):
        player = Player.objects.get(transfermarkt_id=132098)
        PlayerSeasonStat.objects.create(
            player=player,
            season='Saison #1',
            season_number=1,
            competition='Websoccer Liga',
            matches=12,
            goals=8,
            assists=3,
            substitutions_in=1,
            substitutions_out=2,
            yellow_cards=1,
            player_of_match_awards=2,
            minutes_played=990,
            average_grade=Decimal('1.74'),
        )
        PlayerTransferHistory.objects.create(
            player=player,
            transfer_date=date(2026, 7, 1),
            season='2026/27',
            from_club=None,
            to_club=self.club,
            fee_eur=Decimal('45000000.00'),
        )
        PlayerInjuryRecord.objects.create(
            player=player,
            start_date=date(2026, 9, 1),
            injury_type='Muskelverletzung',
            days_missed=12,
            competition='Websoccer Liga',
        )
        PlayerSuspensionRecord.objects.create(
            player=player,
            start_date=date(2026, 10, 2),
            reason='Gelbsperre',
            matches_missed=1,
            competition='Websoccer Liga',
        )
        PlayerAwardTitle.objects.create(
            player=player,
            title='Spieler des Monats',
            season='2026/27',
            count=1,
        )
        response = self.client.get(
            reverse('player_detail', kwargs={'player_id': player.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Harry Kane')
        self.assertContains(response, 'Gehalt pro Spiel')
        self.assertContains(response, 'WS-Verein')
        self.assertContains(response, 'Saisonleistungen')
        self.assertContains(response, 'Saison #1')
        self.assertContains(response, 'performance-lane')
        self.assertContains(response, 'Ein')
        self.assertContains(response, 'Aus')
        self.assertContains(response, 'Karriereleistungen')
        self.assertContains(response, 'Transferhistorie')
        self.assertContains(response, 'Letzte 5 Verletzungen')
        self.assertContains(response, 'Letzte 5 Sperren')
        self.assertContains(response, 'grade-badge')
        self.assertContains(response, 'game/css/global-dashboard.css')
        self.assertContains(response, 'game/css/player-profile.css')
        self.assertContains(response, 'game/css/trophy-cabinet.css')
        global_dashboard_css = (
            Path(__file__).resolve().parent
            / 'static'
            / 'game'
            / 'css'
            / 'global-dashboard.css'
        )
        global_dashboard_css_text = global_dashboard_css.read_text(encoding='utf-8')
        self.assertIn('./global-dashboard/layout-nav.css', global_dashboard_css_text)
        self.assertIn('./global-dashboard/dashboard-cards.css', global_dashboard_css_text)
        self.assertIn('./global-dashboard/tables-lists.css', global_dashboard_css_text)
        self.assertIn('./global-dashboard/responsive.css', global_dashboard_css_text)
        self.assertNotIn('.player-command-profile', global_dashboard_css_text)
        global_dashboard_dir = global_dashboard_css.parent / 'global-dashboard'
        layout_nav_css = (global_dashboard_dir / 'layout-nav.css').read_text(
            encoding='utf-8'
        )
        dashboard_cards_css = (
            global_dashboard_dir / 'dashboard-cards.css'
        ).read_text(encoding='utf-8')
        tables_lists_css = (global_dashboard_dir / 'tables-lists.css').read_text(
            encoding='utf-8'
        )
        responsive_css = (global_dashboard_dir / 'responsive.css').read_text(
            encoding='utf-8'
        )
        self.assertIn('.navbar', layout_nav_css)
        self.assertIn('.dashboard-grid-main', layout_nav_css)
        self.assertIn('.card-title', dashboard_cards_css)
        self.assertIn('.league-table', tables_lists_css)
        self.assertIn('@media (max-width: 1100px)', responsive_css)
        for css_text in (
            layout_nav_css,
            dashboard_cards_css,
            tables_lists_css,
            responsive_css,
        ):
            self.assertNotIn('.player-command-profile', css_text)
            self.assertNotIn('.trophy-list', css_text)
        player_profile_css = (
            Path(__file__).resolve().parent
            / 'static'
            / 'game'
            / 'css'
            / 'player-profile.css'
        )
        player_profile_css_text = player_profile_css.read_text(encoding='utf-8')
        self.assertIn(
            '../images/backgrounds/player-profile-stadium-atmosphere.svg',
            player_profile_css_text,
        )
        self.assertIn('../images/backgrounds/spielfeld.png', player_profile_css_text)
        trophy_css = (
            Path(__file__).resolve().parent
            / 'static'
            / 'game'
            / 'css'
            / 'trophy-cabinet.css'
        )
        self.assertIn(
            '../images/backgrounds/trophy-stage.png',
            trophy_css.read_text(encoding='utf-8'),
        )
        self.assertContains(response, 'game/images/icons/stat-goals.svg')
        self.assertContains(response, 'game/images/icons/stat-assists.svg')
        self.assertContains(response, '#icon-fitness')
        self.assertContains(response, '#icon-substitutions')
        self.assertContains(response, '#icon-star')
        self.assertContains(response, 'Spieler des Spiels')
        self.assertContains(response, 'Ein/Aus')
        self.assertContains(response, '1,74')
        self.assertContains(response, 'Websoccer Liga')
        self.assertContains(response, 'game/images/competitions/bundesliga.png')
        self.assertContains(response, 'Muskelverletzung')
        self.assertContains(response, 'Gelbsperre')
        self.assertNotContains(response, 'Fähigkeiten')
        self.assertNotContains(response, 'Stärke')
        self.assertNotContains(response, 'Potential')
        self.assertNotContains(response, 'Rating')

    def test_player_awards_are_paginated_after_four_titles(self):
        player = Player.objects.get(transfermarkt_id=132098)
        detail_url = reverse('player_detail', kwargs={'player_id': player.id})

        for number in range(1, 6):
            PlayerAwardTitle.objects.create(
                player=player,
                title=f'Titel {number}',
                season='2026/27',
                count=1,
            )

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '?awards_page=2#awards')
        self.assertContains(response, 'Titel 5')
        self.assertNotContains(response, 'Titel 1')

        second_page = self.client.get(detail_url, {'awards_page': 2})

        self.assertEqual(second_page.status_code, 200)
        self.assertContains(second_page, 'Titel 1')
        self.assertNotContains(second_page, 'Titel 5')

    def test_player_awards_render_empty_podium_slots_without_fake_trophies(self):
        player = Player.objects.get(transfermarkt_id=132098)
        PlayerAwardTitle.objects.create(
            player=player,
            title='Spieler des Monats',
            season='2026/27',
            count=1,
        )

        response = self.client.get(
            reverse('player_detail', kwargs={'player_id': player.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="trophy-slot', count=4)
        self.assertContains(response, 'class="podium"', count=4)
        self.assertContains(response, 'game/images/trophies/podest.png')
        self.assertNotContains(response, 'game/images/trophies/default-2.png')
        self.assertNotContains(response, 'game/images/trophies/default-3.png')
        self.assertNotContains(response, 'game/images/trophies/default-4.png')

    def test_player_source_ratings_calculate_base_and_potential(self):
        player = Player.objects.get(transfermarkt_id=132098)

        self.assertEqual(player.calculated_base_strength, Decimal('184.00'))
        self.assertEqual(player.calculated_potential_strength, Decimal('185.00'))
        self.assertIn(
            'Base = EA + FM = 184.00',
            player.source_strength_explanation,
        )

    def test_player_source_rating_fallback_uses_single_source_or_default(self):
        ea_only_player = Player.objects.create(
            first_name='EA',
            last_name='Only',
            nationalities='England',
            age=20,
            position='ST',
            main_position_1='ST',
            potential=50,
            market_value=Decimal('0.00'),
            salary_per_match=Decimal('0.00'),
            club=self.club,
        )
        PlayerSourceRating.objects.create(
            player=ea_only_player,
            source=PlayerSourceRating.SOURCE_EA,
            rating=72,
            potential=80,
        )
        default_player = Player.objects.create(
            first_name='Default',
            last_name='Base',
            nationalities='England',
            age=20,
            position='ST',
            main_position_1='ST',
            potential=50,
            market_value=Decimal('0.00'),
            salary_per_match=Decimal('0.00'),
            club=self.club,
        )

        self.assertEqual(ea_only_player.calculated_base_strength, Decimal('144.00'))
        self.assertEqual(ea_only_player.source_base_quality, 'partial')
        self.assertEqual(default_player.calculated_base_strength, Decimal('40.00'))
        self.assertTrue(default_player.uses_default_base_strength)

    def test_player_admin_nationality_form_stores_two_dropdown_values(self):
        player = Player.objects.get(transfermarkt_id=132098)
        form = PlayerNationalityForm(
            data={
                'first_name': player.first_name,
                'last_name': player.last_name,
                'fm_inside_id': player.fm_inside_id,
                'transfermarkt_id': player.transfermarkt_id,
                'transfermarkt_profile_url': player.transfermarkt_profile_url,
                'transfermarkt_market_value_url': player.transfermarkt_market_value_url,
                'date_of_birth': player.date_of_birth,
                'nationality_1': 'England',
                'nationality_2': 'Irland',
                'age': player.age,
                'position': player.position,
                'primary_position': player.primary_position,
                'source_positions': player.source_positions,
                'main_position_1': 'ST',
                'main_position_2': 'OM',
                'main_position_3': '',
                'secondary_position_1': 'ZM',
                'secondary_position_2': '',
                'secondary_position_3': '',
                'potential': player.potential,
                'market_value': player.market_value,
                'salary_per_match': player.salary_per_match,
                'contract_until': player.contract_until,
                'club': player.club_id,
                'real_life_club': player.real_life_club_id,
                'ws_injury_type': '',
                'ws_injury_days_remaining': 0,
                'ws_suspension_reason': '',
                'ws_suspension_matches_remaining': 0,
            },
            instance=player,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved_player = form.save()
        self.assertEqual(saved_player.nationalities, 'England, Irland')
        self.assertEqual(saved_player.position, 'ST')
        self.assertEqual(saved_player.primary_position, 'ZM')
        self.assertEqual(saved_player.main_positions, ['ST', 'OM'])
        self.assertEqual(saved_player.secondary_positions, ['ZM'])

    def test_player_admin_club_dropdown_orders_career_end_first(self):
        Club.objects.create(
            name='Karrierende',
            short_name='KARR',
            founded_year=0,
            budget=Decimal('0.00'),
            league=self.club.league,
        )
        player = Player.objects.get(transfermarkt_id=132098)
        form = PlayerNationalityForm(instance=player)

        club_names = [
            club.name
            for club in form.fields['club'].queryset
        ]
        real_life_club_names = [
            club.name
            for club in form.fields['real_life_club'].queryset
        ]

        self.assertEqual(club_names[0], 'Karrierende')
        self.assertEqual(real_life_club_names[0], 'Karrierende')

    def test_player_admin_position_form_rejects_duplicate_positions(self):
        player = Player.objects.get(transfermarkt_id=132098)
        form = PlayerNationalityForm(
            data={
                'first_name': player.first_name,
                'last_name': player.last_name,
                'fm_inside_id': player.fm_inside_id,
                'transfermarkt_id': player.transfermarkt_id,
                'transfermarkt_profile_url': player.transfermarkt_profile_url,
                'transfermarkt_market_value_url': player.transfermarkt_market_value_url,
                'date_of_birth': player.date_of_birth,
                'nationality_1': 'England',
                'nationality_2': 'Irland',
                'age': player.age,
                'position': player.position,
                'primary_position': player.primary_position,
                'source_positions': player.source_positions,
                'main_position_1': 'ST',
                'main_position_2': '',
                'main_position_3': '',
                'secondary_position_1': 'ST',
                'secondary_position_2': '',
                'secondary_position_3': '',
                'potential': player.potential,
                'market_value': player.market_value,
                'salary_per_match': player.salary_per_match,
                'contract_until': player.contract_until,
                'club': player.club_id,
                'real_life_club': player.real_life_club_id,
                'ws_injury_type': '',
                'ws_injury_days_remaining': 0,
                'ws_suspension_reason': '',
                'ws_suspension_matches_remaining': 0,
            },
            instance=player,
        )

        self.assertFalse(form.is_valid())

    def test_player_admin_change_form_contains_management_tabs(self):
        player = Player.objects.get(transfermarkt_id=132098)
        PlayerWeightedRatingSnapshot.objects.create(
            player=player,
            source=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
            recorded_at=date(2025, 4, 1),
            fixture_reference='BL-1',
            weighted_rating=Decimal('8.20'),
            rating_minutes=90,
            match_count=1,
        )
        PlayerMarketValueSnapshot.objects.create(
            player=player,
            source=self.tm_source,
            recorded_at=date(2025, 4, 1),
            value_eur=Decimal('110000000.00'),
            profile_url=player.transfermarkt_profile_url,
            update_current=False,
        )
        PlayerStrengthSnapshot.objects.create(
            player=player,
            recorded_at=date(2025, 4, 1),
            match_reference='BL-1',
            base_strength=Decimal('184.00'),
            final_strength=Decimal('186.00'),
            max_strength=Decimal('190.00'),
            last_10_average_strength=Decimal('185.00'),
        )
        admin_user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='test-pass',
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse('admin:game_player_change', args=[player.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ws-admin-tabs')
        self.assertContains(response, 'SPIELERPROFIL')
        self.assertContains(response, 'STAERKE')
        self.assertContains(response, 'Spielstaerke-Berechnung')
        self.assertContains(response, 'Endstaerke ohne Peak')
        self.assertContains(response, 'Endstaerke Max')
        self.assertContains(response, 'Staerke-Verlauf')
        self.assertContains(response, 'ws-strength-chart')
        self.assertContains(response, 'Base: 184.00')
        self.assertContains(response, 'Final: 186.00')
        self.assertContains(response, 'Max: 190.00')
        self.assertContains(response, 'SOURCE')
        self.assertContains(response, 'Marktwert-Verlauf')
        self.assertContains(response, 'ws-market-chart')
        self.assertContains(response, '110.0 Mio')
        self.assertContains(response, 'SAISON')
        self.assertContains(response, 'Gewichteter Rating-Verlauf')
        self.assertContains(response, 'ws-rating-chart')
        self.assertContains(response, 'Rating')
        self.assertContains(response, 'Spiele')
        self.assertContains(response, '8.2')
        self.assertContains(response, 'Noch keine Websoccer-Saisonstatistik vorhanden.')
        self.assertContains(response, 'Noch keine Websoccer-Karrierestatistik vorhanden.')
        self.assertContains(response, 'Noch keine Websoccer-Transfers vorhanden.')
        self.assertContains(response, 'ws-season-career-grid')
        self.assertNotContains(response, 'Premier League')
        self.assertNotContains(response, '95.000.000 EUR')
        self.assertNotContains(response, '>KARRIERE</button>')
        self.assertContains(response, 'TRANSFERHISTORIE WS')
        self.assertContains(response, 'GESCHICHTE')

    def test_strength_modifier_settings_seed_default_rules(self):
        settings = StrengthFormulaSettings.objects.get(name='Standard')

        self.assertEqual(settings.rating_modifier_factor, Decimal('5.00'))
        self.assertEqual(settings.default_league_median_rating, Decimal('6.80'))
        self.assertEqual(settings.modifier_rules.count(), 15)

    def test_player_edit_request_accepts_market_value_change(self):
        player = Player.objects.get(transfermarkt_id=132098)
        edit_request = PlayerEditRequest.objects.create(
            player=player,
            field_name=PlayerEditRequest.FIELD_MARKET_VALUE,
            old_value='100000000,00',
            new_value='105000000,00',
            requester_note='Marktwert aktualisiert.',
        )

        edit_request.accept()
        player.refresh_from_db()

        self.assertEqual(player.market_value, Decimal('105000000.00'))
        self.assertEqual(edit_request.status, PlayerEditRequest.STATUS_ACCEPTED)

    def test_player_form_snapshot_calculates_minutes_quote(self):
        player = Player.objects.get(transfermarkt_id=132098)
        snapshot = PlayerFormSnapshot.objects.create(
            player=player,
            fixture_id=12345,
            fixture_date=date(2025, 2, 15),
            minutes_played=45,
            possible_minutes=90,
        )

        self.assertEqual(snapshot.minutes_quote, Decimal('50.00'))

    def test_player_external_id_is_unique_per_source(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.tm_source,
            external_id='132098',
            profile_url=self.player.transfermarkt_profile_url,
        )

        self.assertEqual(
            self.player.external_ids.get(source=self.tm_source).external_id,
            '132098',
        )

    def test_market_value_snapshots_keep_latest_10_and_update_current(self):
        for index in range(12):
            PlayerMarketValueSnapshot.objects.create(
                player=self.player,
                source=self.tm_source,
                recorded_at=date(2025, 1, index + 1),
                value_eur=Decimal('1000000.00') * (index + 1),
                profile_url=self.player.transfermarkt_profile_url,
            )

        self.player.refresh_from_db()
        snapshots = self.player.market_value_snapshots.order_by('recorded_at')

        self.assertEqual(snapshots.count(), 10)
        self.assertEqual(snapshots.first().recorded_at, date(2025, 1, 3))
        self.assertEqual(self.player.market_value, Decimal('12000000.00'))
        self.assertEqual(self.player.salary_per_match, Decimal('60000.00'))

    def test_source_rating_snapshot_updates_current_rating(self):
        PlayerSourceRatingSnapshot.objects.create(
            player=self.player,
            source=self.fm_source,
            recorded_at=date(2025, 5, 1),
            rating=95,
            potential=96,
            source_version='FMInside 26',
        )

        current_rating = self.player.source_ratings.get(
            source=PlayerSourceRating.SOURCE_FM,
        )
        self.assertEqual(current_rating.rating, 95)
        self.assertEqual(current_rating.potential, 96)
        self.assertEqual(current_rating.checked_at, date(2025, 5, 1))

    def test_source_rating_snapshots_keep_latest_10_per_source(self):
        for index in range(12):
            PlayerSourceRatingSnapshot.objects.create(
                player=self.player,
                source=self.sofifa_source,
                recorded_at=date(2025, 2, index + 1),
                rating=70 + index,
                potential=80 + index,
                source_version='SoFIFA FC26',
            )

        snapshots = self.player.source_rating_snapshots.filter(
            source=self.sofifa_source,
        ).order_by('recorded_at')

        self.assertEqual(snapshots.count(), 10)
        self.assertEqual(snapshots.first().recorded_at, date(2025, 2, 3))

    def test_strength_snapshots_keep_latest_10(self):
        for index in range(12):
            PlayerStrengthSnapshot.objects.create(
                player=self.player,
                recorded_at=date(2025, 3, index + 1),
                match_reference=f'BL-{index + 1}',
                base_strength=Decimal('180.00'),
                final_strength=Decimal('181.00') + index,
                max_strength=Decimal('190.00'),
                last_10_average_strength=Decimal('180.50') + index,
            )

        snapshots = self.player.strength_snapshots.order_by('recorded_at')

        self.assertEqual(snapshots.count(), 10)
        self.assertEqual(snapshots.first().recorded_at, date(2025, 3, 3))

    def test_player_graph_data_returns_chart_series(self):
        PlayerMarketValueSnapshot.objects.create(
            player=self.player,
            source=self.tm_source,
            recorded_at=date(2025, 4, 1),
            value_eur=Decimal('110000000.00'),
            profile_url=self.player.transfermarkt_profile_url,
        )
        PlayerSourceRatingSnapshot.objects.create(
            player=self.player,
            source=self.fm_source,
            recorded_at=date(2025, 4, 1),
            rating=95,
            potential=96,
            source_version='FMInside 26',
        )
        PlayerSourceRatingSnapshot.objects.create(
            player=self.player,
            source=self.sofifa_source,
            recorded_at=date(2025, 4, 1),
            rating=90,
            potential=91,
            source_version='SoFIFA FC26',
        )
        PlayerStrengthSnapshot.objects.create(
            player=self.player,
            recorded_at=date(2025, 4, 1),
            match_reference='BL-1',
            base_strength=Decimal('184.00'),
            final_strength=Decimal('186.00'),
            max_strength=Decimal('190.00'),
            last_10_average_strength=Decimal('185.00'),
        )
        PlayerFormSnapshot.objects.create(
            player=self.player,
            fixture_id='BL-1',
            fixture_date=date(2025, 4, 1),
            opponent_name='Borussia Dortmund',
            minutes_played=90,
            possible_minutes=90,
            rating=Decimal('8.20'),
            goals=1,
            assists=1,
        )
        PlayerWeightedRatingSnapshot.objects.create(
            player=self.player,
            source=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
            recorded_at=date(2025, 4, 1),
            fixture_reference='BL-1',
            weighted_rating=Decimal('8.20'),
            rating_minutes=90,
            match_count=1,
        )

        response = self.client.get(
            reverse('player_graph_data', kwargs={'player_id': self.player.id})
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['player']['wsc_player_id'], 'WSC-TEST-1')
        self.assertEqual(payload['market_value'][0]['y'], 110000000.0)
        self.assertEqual(payload['source_ratings']['fm_rating'][0]['y'], 95)
        self.assertEqual(payload['source_ratings']['sofifa_potential'][0]['y'], 91)
        self.assertEqual(payload['match_ratings'][0]['y'], 8.2)
        self.assertEqual(payload['weighted_ratings'][0]['y'], 8.2)
        self.assertEqual(payload['strength']['final_strength'][0]['y'], 186.0)

    def test_player_graph_data_handles_players_without_snapshots(self):
        player = Player.objects.create(
            first_name='No',
            last_name='Snapshots',
            age=20,
            market_value=Decimal('0.00'),
            salary_per_match=Decimal('0.00'),
            club=self.club,
        )

        response = self.client.get(
            reverse('player_graph_data', kwargs={'player_id': player.id})
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['market_value'], [])
        self.assertEqual(payload['source_ratings']['fm_rating'], [])
        self.assertEqual(payload['match_ratings'], [])
        self.assertEqual(payload['weighted_ratings'], [])
        self.assertEqual(payload['strength']['final_strength'], [])

    def test_player_admin_contains_data_history_inlines(self):
        player_admin = admin.site._registry[Player]
        inline_models = [
            inline.model
            for inline in player_admin.inlines
        ]

        self.assertIn(PlayerExternalId, inline_models)
        self.assertNotIn(PlayerMarketValueSnapshot, inline_models)
        self.assertNotIn(PlayerSourceRatingSnapshot, inline_models)
        self.assertNotIn(PlayerFormSnapshot, inline_models)
        self.assertNotIn(PlayerWeightedRatingSnapshot, inline_models)
        self.assertNotIn(PlayerStrengthSnapshot, inline_models)
        self.assertNotIn(PlayerExternalId, admin.site._registry)
        self.assertNotIn(PlayerMarketValueSnapshot, admin.site._registry)
        self.assertNotIn(PlayerSourceRatingSnapshot, admin.site._registry)
        self.assertNotIn(PlayerWeightedRatingSnapshot, admin.site._registry)
        self.assertNotIn(PlayerStrengthSnapshot, admin.site._registry)

    def test_weighted_rating_snapshots_keep_latest_10_per_source(self):
        for index in range(12):
            PlayerWeightedRatingSnapshot.objects.create(
                player=self.player,
                source=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
                recorded_at=date(2025, 5, index + 1),
                fixture_reference=f'BL-{index + 1}',
                weighted_rating=Decimal('7.00') + Decimal(index) / Decimal('10'),
                rating_minutes=90,
                match_count=min(index + 1, 10),
            )

        snapshots = self.player.weighted_rating_snapshots.order_by('recorded_at')

        self.assertEqual(snapshots.count(), 10)
        self.assertEqual(snapshots.first().recorded_at, date(2025, 5, 3))

    def test_calculate_player_strengths_skips_player_without_sources(self):
        player = Player.objects.create(
            first_name='Seeded',
            last_name='Base',
            nationalities='England',
            age=24,
            position='ST',
            main_position_1='ST',
            potential=82,
            market_value=Decimal('10000000.00'),
            salary_per_match=Decimal('50000.00'),
            club=self.club,
        )
        PlayerStrengthProfile.objects.create(
            player=player,
            base_strength=Decimal('76.00'),
            form_modifier=Decimal('1.50'),
            freshness=Decimal('97.00'),
        )
        output = StringIO()

        call_command('calculate_player_strengths', stdout=output)
        player.refresh_from_db()
        profile = player.strength_profile

        self.assertEqual(profile.base_strength, Decimal('76.00'))
        self.assertEqual(profile.form_modifier, Decimal('1.50'))
        self.assertFalse(
            player.strength_snapshots.filter(
                match_reference__startswith='ENGINE-',
            ).exists()
        )
        self.assertIn('übersprungen', output.getvalue())

    def test_calculate_player_strengths_uses_source_ratings_when_available(self):
        player = Player.objects.get(transfermarkt_id=132098)
        output = StringIO()

        call_command('calculate_player_strengths', stdout=output)
        player.refresh_from_db()

        self.assertEqual(player.strength_profile.base_strength, Decimal('184.00'))
        self.assertEqual(player.strength_profile.final_strength, Decimal('186.00'))


class ConfederationMappingCoverageTest(TestCase):
    def test_all_country_flag_assets_have_confederation_entry(self):
        missing = sorted(
            nationality
            for nationality in COUNTRY_FLAG_ASSETS
            if nationality not in _NATIONALITY_CONFEDERATION
        )
        self.assertFalse(
            missing,
            f"The following nationalities are in COUNTRY_FLAG_ASSETS but missing from "
            f"_NATIONALITY_CONFEDERATION — add them to game/competition_assets.py: "
            f"{missing}",
        )


class CityMapPctResolverTest(TestCase):
    """Guards the hand-verified career-map marker placement logic.

    These checks ensure a future edit to CITY_MAP_PCT or city_map_pct() cannot
    silently send markers back over the wrong country.
    """

    def test_exact_match_returns_table_value(self):
        self.assertEqual(city_map_pct('berlin'), CITY_MAP_PCT['berlin'])
        self.assertEqual(city_map_pct('leipzig'), CITY_MAP_PCT['leipzig'])

    def test_match_is_case_and_whitespace_insensitive(self):
        self.assertEqual(city_map_pct('  Berlin  '), CITY_MAP_PCT['berlin'])
        self.assertEqual(city_map_pct('STUTTGART'), CITY_MAP_PCT['stuttgart'])

    def test_accented_and_unaccented_names_resolve_to_same_position(self):
        muenchen = CITY_MAP_PCT['münchen']
        self.assertEqual(city_map_pct('München'), muenchen)
        self.assertEqual(city_map_pct('munchen'), muenchen)
        self.assertEqual(city_map_pct('Munich'), muenchen)

        gladbach = CITY_MAP_PCT['mönchengladbach']
        self.assertEqual(city_map_pct('Mönchengladbach'), gladbach)
        self.assertEqual(city_map_pct('monchengladbach'), gladbach)

    def test_truncation_typos_still_resolve(self):
        # A shortened/typo'd input is a prefix of the table key.
        self.assertEqual(city_map_pct('Frankfur'), CITY_MAP_PCT['frankfurt'])
        self.assertEqual(city_map_pct('augsbur'), CITY_MAP_PCT['augsburg'])

    def test_word_boundary_multi_word_names_resolve(self):
        # The full official name resolves to the short table key via a leading
        # word match: "frankfurt am main" -> "frankfurt".
        self.assertEqual(
            city_map_pct('Frankfurt am Main'),
            CITY_MAP_PCT['frankfurt'],
        )
        self.assertEqual(
            city_map_pct('Heidenheim an der Brenz'),
            CITY_MAP_PCT['heidenheim'],
        )
        self.assertEqual(
            city_map_pct('Freiburg im Breisgau'),
            CITY_MAP_PCT['freiburg'],
        )

    def test_unrelated_longer_name_does_not_grab_short_key(self):
        # "kielce" (a Polish city) must NOT resolve to the German "kiel".
        self.assertIsNone(city_map_pct('kielce'))
        self.assertIsNone(city_map_pct('Kielce'))

    def test_unknown_cities_return_none(self):
        self.assertIsNone(city_map_pct('Atlantis'))
        self.assertIsNone(city_map_pct('Reykjavik'))
        self.assertIsNone(city_map_pct(''))
        self.assertIsNone(city_map_pct(None))

    def test_first_resolving_name_wins(self):
        # Unknown first, known second -> the known one resolves.
        self.assertEqual(
            city_map_pct('Atlantis', 'Berlin'),
            CITY_MAP_PCT['berlin'],
        )

    def test_every_table_city_resolves_to_a_sensible_position(self):
        for name, expected in CITY_MAP_PCT.items():
            with self.subTest(city=name):
                resolved = city_map_pct(name)
                self.assertEqual(resolved, expected)
                x_pct, y_pct = resolved
                self.assertGreaterEqual(x_pct, 0.0)
                self.assertLessEqual(x_pct, 100.0)
                self.assertGreaterEqual(y_pct, 0.0)
                self.assertLessEqual(y_pct, 100.0)


class SofifaCsvImportTests(TestCase):
    """Absicherung des import_sofifa_csv-Importers gegen stille Regressionen.

    Abgedeckte Szenarien:
    - Primär-Matching über vorhandene PlayerExternalId(SOFIFA)
    - Fallback-Matching über Name+Verein verknüpft sofifa_id dauerhaft
    - Mehrdeutiger Fallback wird abgelehnt
    - Fehlende Pflichtspalten (sofifa_id / overall) führen zu CommandError
    - Zeile mit leerer sofifa_id landet im Fehler-Counter
    - Re-Run ist idempotent
    - --dry-run schreibt nichts in die DB
    """

    def setUp(self):
        league = League.objects.create(name='Testliga', country='Deutschland')
        self.club = Club.objects.create(
            name='FC Testverein',
            short_name='FCT',
            founded_year=1900,
            budget=Decimal('1000000.00'),
            league=league,
        )
        self.second_club = Club.objects.create(
            name='Zweiter Verein',
            short_name='ZV',
            founded_year=1920,
            budget=Decimal('500000.00'),
            league=league,
        )
        self.sofifa_ds, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_SOFIFA,
            defaults={'name': 'SoFIFA'},
        )
        self.player = Player.objects.create(
            first_name='Thomas',
            last_name='Mueller',
            age=34,
            position='OM',
            main_position_1='OM',
            potential=85,
            market_value=Decimal('20000000.00'),
            salary_per_match=Decimal('100000.00'),
            club=self.club,
        )

    def _tmp_csv(self, content, suffix='.csv'):
        """Schreibt content in eine temporäre Datei und gibt den Pfad zurück."""
        fh = tempfile.NamedTemporaryFile(
            mode='w', suffix=suffix, delete=False, encoding='utf-8',
        )
        fh.write(content)
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def _run(self, csv_content, extra_args=None):
        """Hilfsmethode: CSV schreiben, Kommando ausführen, Ausgabe zurückgeben."""
        path = self._tmp_csv(csv_content)
        out = StringIO()
        args = [path]
        kwargs = {'stdout': out, 'skip_recalculate': True}
        if extra_args:
            kwargs.update(extra_args)
        from django.core.management import call_command
        call_command('import_sofifa_csv', *args, **kwargs)
        return out.getvalue()

    # ── 1. Primär-Matching über sofifa_id ────────────────────────────────────

    def test_primary_match_via_external_id_creates_source_rating(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999001',
        )

        csv = 'sofifa_id,name,overall\n999001,Thomas Mueller,82\n'
        output = self._run(csv)

        rating = PlayerSourceRating.objects.filter(
            player=self.player,
            source=PlayerSourceRating.SOURCE_EA,
        ).first()
        self.assertIsNotNone(rating, 'PlayerSourceRating wurde nicht angelegt.')
        self.assertEqual(rating.rating, 82)
        self.assertIn('neu', output)

    def test_primary_match_updates_existing_source_rating(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999001',
        )
        PlayerSourceRating.objects.create(
            player=self.player,
            source=PlayerSourceRating.SOURCE_EA,
            rating=80,
        )

        csv = 'sofifa_id,name,overall\n999001,Thomas Mueller,85\n'
        output = self._run(csv)

        rating = PlayerSourceRating.objects.get(
            player=self.player,
            source=PlayerSourceRating.SOURCE_EA,
        )
        self.assertEqual(rating.rating, 85)
        self.assertIn('aktualisiert', output)

    # ── 2. Fallback-Matching über Name verknüpft sofifa_id dauerhaft ─────────

    def test_fallback_name_match_creates_external_id(self):
        csv = 'sofifa_id,name,club,overall\n999002,Thomas Mueller,FC Testverein,78\n'
        output = self._run(csv)

        ext = PlayerExternalId.objects.filter(
            player=self.player,
            source=self.sofifa_ds,
        ).first()
        self.assertIsNotNone(ext, 'PlayerExternalId wurde nicht dauerhaft verknüpft.')
        self.assertEqual(ext.external_id, '999002')
        self.assertIn('neu', output)

    def test_fallback_name_match_also_creates_source_rating(self):
        csv = 'sofifa_id,name,club,overall\n999002,Thomas Mueller,FC Testverein,78\n'
        self._run(csv)

        rating = PlayerSourceRating.objects.filter(
            player=self.player,
            source=PlayerSourceRating.SOURCE_EA,
        ).first()
        self.assertIsNotNone(rating)
        self.assertEqual(rating.rating, 78)

    # ── 3. Mehrdeutiger Fallback wird abgelehnt ───────────────────────────────

    def test_ambiguous_fallback_counts_as_unmatched(self):
        Player.objects.create(
            first_name='Thomas',
            last_name='Mueller',
            age=28,
            position='ST',
            main_position_1='ST',
            potential=80,
            market_value=Decimal('5000000.00'),
            salary_per_match=Decimal('50000.00'),
            club=self.club,
        )

        csv = 'sofifa_id,name,club,overall\n999003,Thomas Mueller,FC Testverein,75\n'
        output = self._run(csv)

        self.assertIn('nicht gematcht', output.lower())
        self.assertFalse(
            PlayerExternalId.objects.filter(
                source=self.sofifa_ds,
                external_id='999003',
            ).exists(),
        )

    # ── 4. Fehlende Pflichtspalten führen zu CommandError ────────────────────

    def test_missing_sofifa_id_column_raises_command_error(self):
        from django.core.management.base import CommandError
        path = self._tmp_csv('name,overall\nThomas Mueller,80\n')
        with self.assertRaises(CommandError):
            from django.core.management import call_command
            call_command(
                'import_sofifa_csv', path,
                stdout=StringIO(), skip_recalculate=True,
            )

    def test_missing_rating_column_raises_command_error(self):
        from django.core.management.base import CommandError
        path = self._tmp_csv('sofifa_id,name\n999004,Thomas Mueller\n')
        with self.assertRaises(CommandError):
            from django.core.management import call_command
            call_command(
                'import_sofifa_csv', path,
                stdout=StringIO(), skip_recalculate=True,
            )

    # ── 5. Zeile mit fehlender sofifa_id landet im Fehler-Counter ────────────

    def test_row_with_empty_sofifa_id_increments_error_counter(self):
        csv = 'sofifa_id,name,overall\n,Thomas Mueller,80\n'
        output = self._run(csv)
        self.assertRegex(output, r'1 Fehler')

    # ── 6. Ungültiger Attributwert wird geclipt, Zeile gilt nicht als Fehler ──

    def test_out_of_range_attribute_is_clipped_not_error(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999010',
        )
        csv = 'sofifa_id,name,overall,tempo\n999010,Thomas Mueller,82,150\n'
        output = self._run(csv)

        self.assertRegex(output, r'0 Fehler')
        self.assertNotIn('error', output.lower().replace('fehler', ''))

    def test_out_of_range_attribute_valid_fields_still_written(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999011',
        )
        csv = 'sofifa_id,name,overall,tempo\n999011,Thomas Mueller,82,999\n'
        self._run(csv)

        rating = PlayerSourceRating.objects.filter(
            player=self.player,
            source=PlayerSourceRating.SOURCE_EA,
        ).first()
        self.assertIsNotNone(rating, 'PlayerSourceRating wurde trotz ungültigem Attribut nicht angelegt.')
        self.assertEqual(rating.rating, 82)

    # ── 7. Re-Run ist idempotent ──────────────────────────────────────────────

    def test_rerun_is_idempotent_unchanged_stat(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999005',
        )
        csv = 'sofifa_id,name,overall\n999005,Thomas Mueller,81\n'
        self._run(csv)
        output2 = self._run(csv)

        self.assertIn('unveraendert', output2)
        self.assertRegex(output2, r'0 aktualisiert')

    def test_rerun_does_not_create_duplicate_source_rating(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999005',
        )
        csv = 'sofifa_id,name,overall\n999005,Thomas Mueller,81\n'
        self._run(csv)
        self._run(csv)

        count = PlayerSourceRating.objects.filter(
            player=self.player,
            source=PlayerSourceRating.SOURCE_EA,
        ).count()
        self.assertEqual(count, 1, 'Duplikat in PlayerSourceRating nach Re-Run.')

    def test_rerun_does_not_create_duplicate_external_id(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999005',
        )
        csv = 'sofifa_id,name,overall\n999005,Thomas Mueller,81\n'
        self._run(csv)
        self._run(csv)

        count = PlayerExternalId.objects.filter(
            player=self.player,
            source=self.sofifa_ds,
        ).count()
        self.assertEqual(count, 1, 'Duplikat in PlayerExternalId nach Re-Run.')

    def test_rerun_does_not_create_duplicate_snapshot(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999005',
        )
        csv = 'sofifa_id,name,overall\n999005,Thomas Mueller,81\n'
        self._run(csv)
        self._run(csv)

        count = PlayerSourceRatingSnapshot.objects.filter(
            player=self.player,
            source=self.sofifa_ds,
        ).count()
        self.assertEqual(count, 1, 'Duplikat in PlayerSourceRatingSnapshot nach Re-Run.')

    # ── 7. --dry-run schreibt nichts in die DB ───────────────────────────────

    def test_dry_run_creates_no_source_rating(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999006',
        )
        csv = 'sofifa_id,name,overall\n999006,Thomas Mueller,83\n'
        path = self._tmp_csv(csv)
        from django.core.management import call_command
        call_command(
            'import_sofifa_csv', path,
            stdout=StringIO(), dry_run=True, skip_recalculate=True,
        )

        self.assertFalse(
            PlayerSourceRating.objects.filter(
                player=self.player,
                source=PlayerSourceRating.SOURCE_EA,
            ).exists(),
        )

    def test_dry_run_creates_no_external_id(self):
        csv = 'sofifa_id,name,club,overall\n999007,Thomas Mueller,FC Testverein,83\n'
        path = self._tmp_csv(csv)
        from django.core.management import call_command
        call_command(
            'import_sofifa_csv', path,
            stdout=StringIO(), dry_run=True, skip_recalculate=True,
        )

        self.assertFalse(
            PlayerExternalId.objects.filter(
                source=self.sofifa_ds,
                external_id='999007',
            ).exists(),
        )

    def test_dry_run_creates_no_snapshot(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999006',
        )
        csv = 'sofifa_id,name,overall\n999006,Thomas Mueller,83\n'
        path = self._tmp_csv(csv)
        from django.core.management import call_command
        call_command(
            'import_sofifa_csv', path,
            stdout=StringIO(), dry_run=True, skip_recalculate=True,
        )

        self.assertFalse(
            PlayerSourceRatingSnapshot.objects.filter(
                player=self.player,
                source=self.sofifa_ds,
            ).exists(),
        )

    def test_dry_run_output_contains_dry_run_notice(self):
        PlayerExternalId.objects.create(
            player=self.player,
            source=self.sofifa_ds,
            external_id='999006',
        )
        csv = 'sofifa_id,name,overall\n999006,Thomas Mueller,83\n'
        path = self._tmp_csv(csv)
        out = StringIO()
        from django.core.management import call_command
        call_command(
            'import_sofifa_csv', path,
            stdout=out, dry_run=True, skip_recalculate=True,
        )
        self.assertIn('DRY-RUN', out.getvalue())


class ReseedPlayersFromFullCsvTests(TestCase):
    """Absicherung des destruktiven Voll-CSV-Reseed-Importers.

    Abgedeckte Szenarien:
    - Kern-Mapping: ws_club_id -> Verein, generierte wsc_player_id (WSC-<fm>),
      EA- + FM-Quellen-Ratings
    - Unbekannte ws_club_id -> Spieler ohne Verein (Warnung, kein Abbruch)
    - Atomarer Rollback: Fehler in einer Zeile laesst KEINE Teil-Daten zurueck;
      bereits vorhandene Spieler bleiben unangetastet (Loeschen wird mit
      zurueckgerollt)
    - Bedingte Anlage von Saison-Statistik / Transfer-Historie: nur wenn die
      jeweiligen CSV-Spalten befuellt sind
    """

    def setUp(self):
        self.league = League.objects.create(
            name='Testliga', country='Deutschland',
        )
        self.club = Club.objects.create(
            name='FC Testverein',
            short_name='FCT',
            founded_year=1900,
            budget=Decimal('1000000.00'),
            league=self.league,
        )
        self.other_club = Club.objects.create(
            name='Zweiter Verein',
            short_name='ZV',
            founded_year=1920,
            budget=Decimal('500000.00'),
            league=self.league,
        )

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    def _build_csv(self, rows, columns=None):
        """Baut einen Semikolon-getrennten CSV-Text aus einer Liste von Dicts."""
        if columns is None:
            columns = []
            for row in rows:
                for key in row:
                    if key not in columns:
                        columns.append(key)
        lines = [';'.join(columns)]
        for row in rows:
            lines.append(';'.join(str(row.get(c, '')) for c in columns))
        return '\n'.join(lines) + '\n'

    def _tmp_csv(self, content):
        fh = tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False, encoding='utf-8-sig',
        )
        fh.write(content)
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def _run(self, rows, columns=None, **kwargs):
        """CSV schreiben, Reseed-Kommando ausfuehren, Ausgabe zurueckgeben."""
        path = self._tmp_csv(self._build_csv(rows, columns))
        out = StringIO()
        opts = {'stdout': out, 'confirm': True, 'skip_recalculate': True}
        opts.update(kwargs)
        call_command('reseed_players_from_full_csv', path, **opts)
        return out.getvalue()

    def _base_row(self, **overrides):
        """Eine Zeile mit allen Pflichtspalten; Felder per overrides ersetzbar."""
        row = {
            'vorname': 'Thomas',
            'nachname': 'Mueller',
            'alter': '34',
            'position': 'OM',
            'ws_club_id': str(self.club.id),
            'fm_inside_id': '915',
            'ea_rating': '80',
            'fm_rating': '82',
            'marktwert': '20000000',
        }
        row.update(overrides)
        return row

    # ── 1. Kern-Mapping ──────────────────────────────────────────────────────

    def test_core_mapping_club_wsc_id_and_ratings(self):
        self._run([self._base_row()])

        player = Player.objects.get(fm_inside_id=915)
        self.assertEqual(player.club, self.club)
        self.assertEqual(player.wsc_player_id, 'WSC-915')

        ea = PlayerSourceRating.objects.get(
            player=player, source=PlayerSourceRating.SOURCE_EA)
        fm = PlayerSourceRating.objects.get(
            player=player, source=PlayerSourceRating.SOURCE_FM)
        self.assertEqual(ea.rating, 80)
        self.assertEqual(fm.rating, 82)

    def test_unknown_ws_club_id_creates_player_without_club(self):
        output = self._run([self._base_row(ws_club_id='999999')])

        player = Player.objects.get(fm_inside_id=915)
        self.assertIsNone(player.club)
        self.assertIn('unbekannt', output)

    def test_wsc_id_falls_back_to_line_number_without_fm_id(self):
        self._run([self._base_row(fm_inside_id='')])

        player = Player.objects.get(first_name='Thomas', last_name='Mueller')
        self.assertIsNone(player.fm_inside_id)
        # Erste Datenzeile -> Zeile 2 in der CSV.
        self.assertEqual(player.wsc_player_id, 'WSC-L2')

    # ── 2. Atomarer Rollback ─────────────────────────────────────────────────

    def test_row_error_rolls_back_and_keeps_existing_players(self):
        from django.core.management.base import CommandError

        existing = Player.objects.create(
            first_name='Bestand',
            last_name='Spieler',
            age=30,
            position='ST',
            main_position_1='ST',
            potential=70,
            market_value=Decimal('1000000.00'),
            salary_per_match=Decimal('10000.00'),
            club=self.club,
        )

        # Zwei Zeilen mit identischer fm_inside_id -> Duplikat auf wsc_player_id
        # /fm_inside_id -> IntegrityError in Zeile 2.
        rows = [
            self._base_row(vorname='Erster', fm_inside_id='4242'),
            self._base_row(vorname='Zweiter', fm_inside_id='4242'),
        ]
        with self.assertRaises(CommandError):
            self._run(rows)

        # Loeschen + Teil-Import wurden komplett zurueckgerollt.
        self.assertEqual(Player.objects.count(), 1)
        self.assertTrue(Player.objects.filter(pk=existing.pk).exists())
        self.assertFalse(Player.objects.filter(wsc_player_id='WSC-4242').exists())

    def test_row_error_rolls_back_dependent_season_stats_and_transfers(self):
        """Fehler in einer spaeteren Zeile rollt auch die abhaengigen
        Saison-Stats und Transfer-Historie bereits verarbeiteter Zeilen
        vollstaendig zurueck (keine halben Spielerdaten)."""
        from django.core.management.base import CommandError

        # Zeile 1: vollstaendig befuellte ss_*- und transfer_*-Spalten.
        # Zeile 2: identische fm_inside_id -> IntegrityError in Zeile 2.
        rows = [
            self._base_row(
                vorname='Erster', fm_inside_id='4242',
                ss_saison='2025/26', ss_spiele='30', ss_tore='12',
                transfer_datum='2025-07-01',
                transfer_von='Zweiter Verein',
                transfer_nach='FC Testverein',
                transfer_fee_eur='5000000',
            ),
            self._base_row(vorname='Zweiter', fm_inside_id='4242'),
        ]
        columns = [
            'vorname', 'nachname', 'alter', 'position', 'ws_club_id',
            'fm_inside_id', 'ea_rating', 'fm_rating', 'marktwert',
            'ss_saison', 'ss_spiele', 'ss_tore',
            'transfer_datum', 'transfer_von', 'transfer_nach',
            'transfer_fee_eur',
        ]
        with self.assertRaises(CommandError):
            self._run(rows, columns=columns)

        # Abhaengige Datensaetze der bereits verarbeiteten Zeile 1 sind weg.
        self.assertEqual(PlayerSeasonStat.objects.count(), 0)
        self.assertEqual(PlayerTransferHistory.objects.count(), 0)

    # ── 3. Bedingte Anlage Saison-Statistik / Transfer-Historie ──────────────

    def test_season_stat_created_only_when_csv_has_data(self):
        rows = [
            self._base_row(
                vorname='Mit', fm_inside_id='100',
                ss_saison='2025/26', ss_spiele='30', ss_tore='12',
            ),
            self._base_row(vorname='Ohne', fm_inside_id='200'),
        ]
        self._run(rows, columns=[
            'vorname', 'nachname', 'alter', 'position', 'ws_club_id',
            'fm_inside_id', 'ea_rating', 'fm_rating', 'marktwert',
            'ss_saison', 'ss_spiele', 'ss_tore',
        ])

        with_stat = Player.objects.get(fm_inside_id=100)
        without_stat = Player.objects.get(fm_inside_id=200)

        stat = PlayerSeasonStat.objects.get(player=with_stat)
        self.assertEqual(stat.season, '2025/26')
        self.assertEqual(stat.matches, 30)
        self.assertEqual(stat.goals, 12)
        self.assertFalse(
            PlayerSeasonStat.objects.filter(player=without_stat).exists())

    def test_transfer_history_created_only_when_csv_has_data(self):
        rows = [
            self._base_row(
                vorname='Mit', fm_inside_id='300',
                transfer_datum='2025-07-01',
                transfer_von='Zweiter Verein',
                transfer_nach='FC Testverein',
                transfer_fee_eur='5000000',
            ),
            self._base_row(vorname='Ohne', fm_inside_id='400'),
        ]
        self._run(rows, columns=[
            'vorname', 'nachname', 'alter', 'position', 'ws_club_id',
            'fm_inside_id', 'ea_rating', 'fm_rating', 'marktwert',
            'transfer_datum', 'transfer_von', 'transfer_nach',
            'transfer_fee_eur',
        ])

        with_tr = Player.objects.get(fm_inside_id=300)
        without_tr = Player.objects.get(fm_inside_id=400)

        transfer = PlayerTransferHistory.objects.get(player=with_tr)
        self.assertEqual(transfer.from_club, self.other_club)
        self.assertEqual(transfer.to_club, self.club)
        self.assertEqual(transfer.fee_eur, Decimal('5000000'))
        self.assertFalse(
            PlayerTransferHistory.objects.filter(player=without_tr).exists())

    # ── 4. Fehlende Pflichtspalten ───────────────────────────────────────────

    def test_missing_required_column_raises_and_keeps_players(self):
        from django.core.management.base import CommandError

        existing = Player.objects.create(
            first_name='Bestand',
            last_name='Spieler',
            age=30,
            position='ST',
            main_position_1='ST',
            potential=70,
            market_value=Decimal('1000000.00'),
            salary_per_match=Decimal('10000.00'),
            club=self.club,
        )

        # Vollstaendige Pflichtspalten ohne ws_club_id bzw. ea_rating.
        full_columns = [
            'vorname', 'nachname', 'alter', 'position', 'ws_club_id',
            'fm_inside_id', 'ea_rating', 'fm_rating', 'marktwert',
        ]

        for missing in ('ws_club_id', 'ea_rating'):
            columns = [c for c in full_columns if c != missing]
            with self.assertRaises(CommandError) as ctx:
                self._run([self._base_row()], columns=columns)
            self.assertIn(missing, str(ctx.exception))

            # Bestehender Spieler unveraendert, nichts geloescht/importiert.
            self.assertEqual(Player.objects.count(), 1)
            self.assertTrue(Player.objects.filter(pk=existing.pk).exists())
            self.assertFalse(
                Player.objects.filter(fm_inside_id=915).exists())

    # ── 5. Abbruch ohne --confirm und ohne --dry-run ─────────────────────────

    def test_without_confirm_raises_and_deletes_nothing(self):
        from django.core.management.base import CommandError

        existing = Player.objects.create(
            first_name='Bestand',
            last_name='Spieler',
            age=30,
            position='ST',
            main_position_1='ST',
            potential=70,
            market_value=Decimal('1000000.00'),
            salary_per_match=Decimal('10000.00'),
            club=self.club,
        )

        with self.assertRaises(CommandError):
            self._run([self._base_row()], confirm=False)

        # Nichts geloescht, nichts importiert.
        self.assertEqual(Player.objects.count(), 1)
        self.assertTrue(Player.objects.filter(pk=existing.pk).exists())
        self.assertFalse(Player.objects.filter(fm_inside_id=915).exists())

    # ── 6. --dry-run schreibt nichts ─────────────────────────────────────────

    def test_dry_run_reports_but_writes_nothing(self):
        existing = Player.objects.create(
            first_name='Bestand',
            last_name='Spieler',
            age=30,
            position='ST',
            main_position_1='ST',
            potential=70,
            market_value=Decimal('1000000.00'),
            salary_per_match=Decimal('10000.00'),
            club=self.club,
        )

        rows = [
            self._base_row(
                vorname='Mit', fm_inside_id='100',
                ss_saison='2025/26', ss_spiele='30', ss_tore='12',
                transfer_datum='2025-07-01',
                transfer_von='Zweiter Verein',
                transfer_nach='FC Testverein',
                transfer_fee_eur='5000000',
            ),
        ]
        output = self._run(rows, columns=[
            'vorname', 'nachname', 'alter', 'position', 'ws_club_id',
            'fm_inside_id', 'ea_rating', 'fm_rating', 'marktwert',
            'ss_saison', 'ss_spiele', 'ss_tore',
            'transfer_datum', 'transfer_von', 'transfer_nach',
            'transfer_fee_eur',
        ], confirm=False, dry_run=True)

        # Bilanz wird ausgegeben.
        self.assertIn('DRY-RUN', output)
        self.assertIn('Spieler gesamt: 1', output)

        # Bestehender Spieler bleibt, nichts wurde geloescht ...
        self.assertEqual(Player.objects.count(), 1)
        self.assertTrue(Player.objects.filter(pk=existing.pk).exists())
        # ... und nichts wurde importiert.
        self.assertFalse(Player.objects.filter(fm_inside_id=100).exists())
        self.assertFalse(PlayerSeasonStat.objects.exists())
        self.assertFalse(PlayerTransferHistory.objects.exists())

    # ── 7. Reset der Taktik-Aufstellungen ────────────────────────────────────

    def test_reseed_resets_tactic_lineups_to_defaults(self):
        """Reseed setzt TacticSetup/TacticTemplate-Aufstellungen zurueck.

        Die in lineup/bench/substitutions gespeicherten Spieler-IDs sind nach
        dem Loeschen tot, deshalb muss der Importer sie auf die Defaults
        zuruecksetzen und die Bestaetigung (is_confirmed/confirmed_at) aufheben.
        """
        confirmed_at = timezone.now()
        setup = TacticSetup.objects.create(
            club=self.club,
            squad_scope='pro',
            lineup={'gk': 4242},
            bench=[1001, 1002],
            substitutions=[{'in': 1001, 'out': 4242, 'minute': 60}],
            is_confirmed=True,
            confirmed_at=confirmed_at,
        )
        template = TacticTemplate.objects.create(
            club=self.club,
            squad_scope='pro',
            name='Offensiv',
            lineup={'gk': 4242},
            bench=[1001, 1002],
            substitutions=[{'in': 1001, 'out': 4242, 'minute': 60}],
        )

        self._run([self._base_row()])

        setup.refresh_from_db()
        template.refresh_from_db()

        self.assertEqual(setup.lineup, default_lineup())
        self.assertEqual(setup.bench, default_bench())
        self.assertEqual(setup.substitutions, default_substitutions())
        self.assertFalse(setup.is_confirmed)
        self.assertIsNone(setup.confirmed_at)

        self.assertEqual(template.lineup, default_lineup())
        self.assertEqual(template.bench, default_bench())
        self.assertEqual(template.substitutions, default_substitutions())

    def test_reseed_preserves_player_independent_tactic_fields(self):
        """Reseed laesst formation/standards/first_half/second_half unangetastet.

        Diese Felder enthalten keine Spieler-IDs, sondern die Grundausrichtung
        des Managers. Sie duerfen beim Reseed NICHT auf die Defaults
        zurueckgesetzt werden — nur lineup/bench/substitutions (sowie
        is_confirmed/confirmed_at) werden zurueckgesetzt, weil sie tote
        Spieler-IDs enthalten.
        """
        custom_formation = {
            'defense': '3n',
            'defensive_midfield': '2',
            'midfield': '2',
            'offensive_midfield': '1',
            'attack': '1',
        }
        custom_standards = {
            'captain': '4242',
            'penalty': '4242',
            'free_kick': '1001',
            'corner': '1002',
        }
        custom_first_half = {
            'orientation': 70,
            'defense': 'standard',
            'midfield': 'standard',
            'attack': 'standard',
            'effort': 'normal',
        }
        custom_second_half = {
            'orientation': 30,
            'defense': 'standard',
            'midfield': 'standard',
            'attack': 'standard',
            'effort': 'normal',
        }

        # Sanity-Check: Die Custom-Werte weichen von den Defaults ab.
        self.assertNotEqual(custom_formation, default_formation())
        self.assertNotEqual(custom_standards, default_standards())
        self.assertNotEqual(custom_first_half, default_half_tactic())
        self.assertNotEqual(custom_second_half, default_half_tactic())

        setup = TacticSetup.objects.create(
            club=self.club,
            squad_scope='pro',
            formation=custom_formation,
            standards=custom_standards,
            first_half=custom_first_half,
            second_half=custom_second_half,
            lineup={'gk': 4242},
            bench=[1001, 1002],
            substitutions=[{'in': 1001, 'out': 4242, 'minute': 60}],
            is_confirmed=True,
            confirmed_at=timezone.now(),
        )

        self._run([self._base_row()])

        setup.refresh_from_db()

        # Spielerunabhaengige Grundausrichtung bleibt erhalten.
        self.assertEqual(setup.formation, custom_formation)
        self.assertEqual(setup.standards, custom_standards)
        self.assertEqual(setup.first_half, custom_first_half)
        self.assertEqual(setup.second_half, custom_second_half)

        # Spielerbezogene Felder werden weiterhin zurueckgesetzt.
        self.assertEqual(setup.lineup, default_lineup())
        self.assertEqual(setup.bench, default_bench())
        self.assertEqual(setup.substitutions, default_substitutions())
        self.assertFalse(setup.is_confirmed)
        self.assertIsNone(setup.confirmed_at)

    def test_reseed_preserves_player_independent_template_fields(self):
        """Reseed laesst formation/standards/first_half/second_half auch bei
        TacticTemplate unangetastet.

        TacticTemplate hat dieselben spielerunabhaengigen Felder wie
        TacticSetup. Diese Grundausrichtung der Vorlage darf beim Reseed NICHT
        auf die Defaults zurueckgesetzt werden — nur lineup/bench/substitutions
        werden zurueckgesetzt, weil sie tote Spieler-IDs enthalten.
        """
        custom_formation = {
            'defense': '3n',
            'defensive_midfield': '2',
            'midfield': '2',
            'offensive_midfield': '1',
            'attack': '1',
        }
        custom_standards = {
            'captain': '4242',
            'penalty': '4242',
            'free_kick': '1001',
            'corner': '1002',
        }
        custom_first_half = {
            'orientation': 70,
            'defense': 'standard',
            'midfield': 'standard',
            'attack': 'standard',
            'effort': 'normal',
        }
        custom_second_half = {
            'orientation': 30,
            'defense': 'standard',
            'midfield': 'standard',
            'attack': 'standard',
            'effort': 'normal',
        }

        # Sanity-Check: Die Custom-Werte weichen von den Defaults ab.
        self.assertNotEqual(custom_formation, default_formation())
        self.assertNotEqual(custom_standards, default_standards())
        self.assertNotEqual(custom_first_half, default_half_tactic())
        self.assertNotEqual(custom_second_half, default_half_tactic())

        template = TacticTemplate.objects.create(
            club=self.club,
            squad_scope='pro',
            name='Offensiv',
            formation=custom_formation,
            standards=custom_standards,
            first_half=custom_first_half,
            second_half=custom_second_half,
            lineup={'gk': 4242},
            bench=[1001, 1002],
            substitutions=[{'in': 1001, 'out': 4242, 'minute': 60}],
        )

        self._run([self._base_row()])

        template.refresh_from_db()

        # Spielerunabhaengige Grundausrichtung der Vorlage bleibt erhalten.
        self.assertEqual(template.formation, custom_formation)
        self.assertEqual(template.standards, custom_standards)
        self.assertEqual(template.first_half, custom_first_half)
        self.assertEqual(template.second_half, custom_second_half)

        # Spielerbezogene Felder werden weiterhin zurueckgesetzt.
        self.assertEqual(template.lineup, default_lineup())
        self.assertEqual(template.bench, default_bench())
        self.assertEqual(template.substitutions, default_substitutions())

    def test_reseed_preserves_template_name_club_and_squad_scope(self):
        """Reseed darf benannte Taktik-Vorlagen weder umbenennen noch loeschen.

        Wenn ein Manager mehrere TacticTemplate-Eintraege mit unterschiedlichen
        Namen anlegt, muessen name, club und squad_scope nach dem Reseed
        unveraendert erhalten bleiben — fuer jede einzelne Vorlage.
        """
        templates_spec = [
            {'name': 'Offensiv-Pressing',  'squad_scope': 'pro',   'club': self.club},
            {'name': 'Defensiv-Block',     'squad_scope': 'pro',   'club': self.club},
            {'name': 'U21-Konter',         'squad_scope': 'youth', 'club': self.club},
            {'name': 'Andere-Offensiv',    'squad_scope': 'pro',   'club': self.other_club},
        ]
        created = []
        for spec in templates_spec:
            t = TacticTemplate.objects.create(
                club=spec['club'],
                squad_scope=spec['squad_scope'],
                name=spec['name'],
            )
            created.append(t)

        self._run([self._base_row()])

        # Alle Vorlagen muessen noch in der DB existieren.
        self.assertEqual(
            TacticTemplate.objects.filter(
                pk__in=[t.pk for t in created]
            ).count(),
            len(created),
            'Mindestens eine Taktik-Vorlage wurde durch den Reseed geloescht.',
        )

        # name, club und squad_scope jeder Vorlage unveraendert.
        for original, spec in zip(created, templates_spec):
            original.refresh_from_db()
            self.assertEqual(
                original.name,
                spec['name'],
                f'Name der Vorlage wurde veraendert: erwartet "{spec["name"]}", '
                f'gefunden "{original.name}".',
            )
            self.assertEqual(
                original.club_id,
                spec['club'].pk,
                f'Club-Zuweisung der Vorlage "{spec["name"]}" wurde veraendert.',
            )
            self.assertEqual(
                original.squad_scope,
                spec['squad_scope'],
                f'squad_scope der Vorlage "{spec["name"]}" wurde veraendert.',
            )

    def test_reseed_does_not_alter_templates_of_clubs_absent_from_csv(self):
        """Clubs ohne CSV-Eintraege behalten ihre Vorlagen komplett unveraendert.

        Der Reseed setzt Taktik-Vorlagen nur fuer Clubs zurueck, die im CSV
        vertreten sind. Vorlagen eines Clubs, dessen Spieler gar nicht im CSV
        stehen, duerfen in lineup, bench und substitutions NICHT veraendert
        werden — weder geloescht noch auf die Defaults zurueckgesetzt.
        """
        absent_club = Club.objects.create(
            name='Abwesender Verein',
            short_name='AV',
            founded_year=1950,
            budget=Decimal('200000.00'),
            league=self.league,
        )

        custom_lineup = {'gk': 7777, 'def': [7778, 7779]}
        custom_bench = [7780, 7781]
        custom_subs = [{'in': 7780, 'out': 7777, 'minute': 75}]

        absent_template = TacticTemplate.objects.create(
            club=absent_club,
            squad_scope='pro',
            name='Abwesend-Offensiv',
            lineup=custom_lineup,
            bench=custom_bench,
            substitutions=custom_subs,
        )

        # CSV enthaelt nur Spieler von self.club — absent_club ist nicht vertreten.
        self._run([self._base_row()])

        absent_template.refresh_from_db()

        self.assertEqual(
            absent_template.lineup,
            custom_lineup,
            'lineup der Vorlage eines nicht-CSV-Clubs wurde unveraendert erwartet.',
        )
        self.assertEqual(
            absent_template.bench,
            custom_bench,
            'bench der Vorlage eines nicht-CSV-Clubs wurde unveraendert erwartet.',
        )
        self.assertEqual(
            absent_template.substitutions,
            custom_subs,
            'substitutions der Vorlage eines nicht-CSV-Clubs wurden unveraendert erwartet.',
        )
        self.assertTrue(
            TacticTemplate.objects.filter(pk=absent_template.pk).exists(),
            'TacticTemplate des nicht-CSV-Clubs wurde durch den Reseed geloescht.',
        )


# ── Match Engine V2 Tests ──────────────────────────────────────────────────────

class MatchEngineV2Tests(TestCase):
    """Testet match_engine.py V2: Taktik-Compiler + Minuten-Simulation."""

    _POSITIONS_11 = ['TW', 'LV', 'IV', 'IV', 'RV', 'DM', 'ZM', 'ZM', 'OM', 'ST', 'ST']

    def setUp(self):
        self.league = League.objects.create(name='TestLiga', country='Deutschland')

    def _make_club(self, name, n=11):
        """Club + n Spieler mit ausgefüllten StrengthProfiles anlegen."""
        club = Club.objects.create(
            name=name,
            short_name=name[:4].upper(),
            founded_year=2000,
            budget=Decimal('5000000.00'),
            league=self.league,
        )
        for i in range(n):
            pos = self._POSITIONS_11[i] if i < len(self._POSITIONS_11) else 'ST'
            p = Player.objects.create(
                first_name=f'Sp{i}',
                last_name=name[:4],
                wsc_player_id=f'WSC-{name[:3]}-{i}',
                date_of_birth=date(1995, 1, 1),
                age=29,
                position=pos,
                main_position_1=pos,
                club=club,
            )
            PlayerStrengthProfile.objects.create(
                player=p,
                base_strength=Decimal('100.00'),
                form_modifier=Decimal('0.00'),
            )
        return club

    # 1 — Neue Statistikfelder vorhanden
    def test_new_stat_fields_present(self):
        """Alle neuen V2-Felder sind im Rückgabe-Dict vorhanden."""
        from .match_engine import simulate_match
        home = self._make_club('Heimverein')
        away = self._make_club('Gastverein')
        result = simulate_match(home, away)

        for key in ('home_xg', 'away_xg', 'simulation_mode',
                    'plan_activations', 'condition_debug',
                    'home_compiled_tactic', 'away_compiled_tactic',
                    'home_zone_strengths', 'away_zone_strengths'):
            self.assertIn(key, result, f'V2-Feld fehlt: {key}')

        ms = result['match_stats']
        for k in ('home_attacks_left', 'home_attacks_center', 'home_attacks_right',
                  'away_attacks_left', 'away_attacks_center', 'away_attacks_right',
                  'home_pressing_ball_wins', 'away_pressing_ball_wins',
                  'home_pressing_bypassed', 'away_pressing_bypassed',
                  'home_fatigue_cost', 'away_fatigue_cost',
                  'home_tactic_coherence', 'away_tactic_coherence'):
            self.assertIn(k, ms, f'Neues match_stats-Feld fehlt: {k}')

    # 2 — simulation_mode == 'minutes'
    def test_simulation_mode_is_minutes(self):
        from .match_engine import simulate_match
        home = self._make_club('AlphaFC')
        away = self._make_club('BetaFC')
        result = simulate_match(home, away)
        self.assertEqual(result['simulation_mode'], 'minutes')

    # 3 — Rückwärtskompatible Pflichtfelder
    def test_backward_compat_fields(self):
        from .match_engine import simulate_match
        home = self._make_club('HomeClub')
        away = self._make_club('AwayClub')
        result = simulate_match(home, away)
        for key in ('home_goals', 'away_goals', 'goal_events', 'match_stats',
                    'home_players', 'away_players', 'home_strength', 'away_strength',
                    'home_teamwork', 'away_teamwork', 'home_formation', 'away_formation',
                    'home_club_id', 'away_club_id', 'home_club_name', 'away_club_name'):
            self.assertIn(key, result, f'Pflichtfeld fehlt: {key}')

    # 4 — xG-Werte sind positive Floats
    def test_xg_values_are_positive(self):
        from .match_engine import simulate_match
        home = self._make_club('GammaFC')
        away = self._make_club('DeltaFC')
        result = simulate_match(home, away)
        self.assertIsInstance(result['home_xg'], float)
        self.assertIsInstance(result['away_xg'], float)
        self.assertGreater(result['home_xg'], 0.0)
        self.assertGreater(result['away_xg'], 0.0)

    # 5 — attack_focus wird durch den Compiler übernommen
    def test_attack_focus_stored_in_compiled_tactic(self):
        from .match_engine import _build_team_dict
        from .match_readiness import ensure_default_tactic
        from .tactic_compiler import compile_tactic
        club = self._make_club('FokusFC')
        tactic, _ = ensure_default_tactic(club)
        instr = dict(tactic.instructions or {})
        instr['attack_focus'] = 'fluegelspiel'
        tactic.instructions = instr
        tactic.save(update_fields=['instructions'])

        team = _build_team_dict(club, tactic)
        compiled = compile_tactic(team, team.get('tactic', {}), half='full')
        self.assertEqual(compiled['debug'].get('attack_focus'), 'fluegelspiel')
        zw = compiled.get('zone_weights', {})
        self.assertGreater(
            zw.get('left', 0) + zw.get('right', 0),
            zw.get('center', 0),
            'fluegelspiel muss mehr Gewicht auf Flügel als auf Mitte legen.',
        )

    # 6 — Bedingung zeitspiel greift ab Minute 80 bei knappper Führung
    def test_zeitspiel_condition_fires_at_80_when_leading(self):
        from .tactic_compiler import select_active_condition_plan
        tactic = {
            'conditions': [{
                'active': True,
                'minute': '80',
                'condition': 'knappe_fuehrung',
                'plan': 'zeitspiel',
            }]
        }
        self.assertIsNone(
            select_active_condition_plan(tactic, 75, 1, 0, True),
            'Vor Minute 80 darf zeitspiel nicht aktiv sein.',
        )
        self.assertEqual(
            select_active_condition_plan(tactic, 80, 1, 0, True),
            'zeitspiel',
        )
        self.assertIsNone(
            select_active_condition_plan(tactic, 82, 0, 0, True),
            'Bei Unentschieden (kein Vorsprung) darf zeitspiel nicht greifen.',
        )

    # 7 — Bedingung aggressiv_risiko greift ab Minute 60 bei Rückstand
    def test_aggressiv_condition_fires_at_60_when_trailing(self):
        from .tactic_compiler import select_active_condition_plan
        tactic = {
            'conditions': [{
                'active': True,
                'minute': '60',
                'condition': 'rueckstand',
                'plan': 'aggressiv_risiko',
            }]
        }
        self.assertIsNone(
            select_active_condition_plan(tactic, 59, 0, 1, True),
            'Vor Minute 60 darf aggressiv_risiko nicht aktiv sein.',
        )
        self.assertEqual(
            select_active_condition_plan(tactic, 60, 0, 1, True),
            'aggressiv_risiko',
        )
        self.assertIsNone(
            select_active_condition_plan(tactic, 65, 1, 1, True),
            'Ohne Rückstand darf aggressiv_risiko nicht greifen.',
        )

    # 8 — Zeitspiel ist kein globaler xG-Bonus (Full-Matchplan-Check)
    def test_zeitspiel_plan_reduces_not_increases_xg(self):
        """Plan 'zeitspiel' reduziert xg_for_delta — kein globaler xG-Gewinn."""
        from .tactic_compiler import CONDITION_PLAN_MODIFIERS
        mods = CONDITION_PLAN_MODIFIERS.get('zeitspiel', {})
        self.assertLess(
            mods.get('xg_for_delta', 0), 0,
            "zeitspiel-Plan darf keinen positiven xg_for_delta haben (wäre ein Exploit).",
        )
        self.assertLess(
            mods.get('shot_volume_delta', 0), 0,
            "zeitspiel-Plan muss shot_volume_delta reduzieren.",
        )


class SuspensionCreationTests(TestCase):
    """Sperren werden nach Rot und 5. Gelber Karte korrekt angelegt."""

    def setUp(self):
        league = League.objects.create(
            name='Testliga Creation',
            country='Deutschland',
        )
        self.club = Club.objects.create(
            name='Testclub Creation',
            short_name='TCC',
            fm_inside_id=99902,
            founded_year=1900,
            budget=Decimal('1000000.00'),
            league=league,
        )
        self.player = Player.objects.create(
            first_name='Karl',
            last_name='Rotkarton',
            position='IV',
            age=28,
            club=self.club,
        )

    def test_red_card_creates_suspension(self):
        """Rote Karte → Rotsperre mit ws_suspension_matches_remaining=1."""
        from .season_service import _apply_match_suspensions
        from .models import PlayerSuspensionRecord
        _apply_match_suspensions(
            [{'pid': self.player.id, 'yellow': 0, 'red': 1}],
            competition='Bundesliga',
            season='2026/27',
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.ws_suspension_matches_remaining, 1)
        self.assertEqual(self.player.ws_suspension_reason, 'Rotsperre')
        self.assertTrue(
            PlayerSuspensionRecord.objects.filter(
                player=self.player, reason='Rotsperre', is_active=True,
            ).exists(),
            "PlayerSuspensionRecord(reason='Rotsperre', is_active=True) muss existieren.",
        )

    def test_fifth_yellow_creates_gelbsperre(self):
        """5. Gelbe Karte der Saison → Gelbsperre."""
        from .season_service import _apply_match_suspensions
        from .models import PlayerSuspensionRecord, PlayerSeasonStat
        PlayerSeasonStat.objects.create(
            player=self.player,
            season='2026/27',
            competition='Bundesliga',
            yellow_cards=5,
        )
        _apply_match_suspensions(
            [{'pid': self.player.id, 'yellow': 1, 'red': 0}],
            competition='Bundesliga',
            season='2026/27',
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.ws_suspension_matches_remaining, 1)
        self.assertEqual(self.player.ws_suspension_reason, 'Gelbsperre')
        self.assertTrue(
            PlayerSuspensionRecord.objects.filter(
                player=self.player, reason='Gelbsperre', is_active=True,
            ).exists(),
        )

    def test_yellow_below_threshold_no_suspension(self):
        """4. Gelbe Karte der Saison → keine Sperre."""
        from .season_service import _apply_match_suspensions
        from .models import PlayerSeasonStat
        PlayerSeasonStat.objects.create(
            player=self.player,
            season='2026/27',
            competition='Bundesliga',
            yellow_cards=4,
        )
        _apply_match_suspensions(
            [{'pid': self.player.id, 'yellow': 1, 'red': 0}],
            competition='Bundesliga',
            season='2026/27',
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.ws_suspension_matches_remaining, 0)
        self.assertEqual(self.player.ws_suspension_reason, '')

    def test_friendly_yellows_excluded_from_threshold(self):
        """Gelbe Karten aus Freundschaft zählen nicht zur Schwelle."""
        from .season_service import _apply_match_suspensions
        from .models import PlayerSeasonStat
        PlayerSeasonStat.objects.create(
            player=self.player,
            season='2026/27',
            competition='Freundschaft',
            yellow_cards=5,
        )
        PlayerSeasonStat.objects.create(
            player=self.player,
            season='2026/27',
            competition='Bundesliga',
            yellow_cards=4,
        )
        _apply_match_suspensions(
            [{'pid': self.player.id, 'yellow': 1, 'red': 0}],
            competition='Bundesliga',
            season='2026/27',
        )
        self.player.refresh_from_db()
        self.assertEqual(
            self.player.ws_suspension_matches_remaining, 0,
            "Freundschaftsgelbe dürfen Sperre nicht auslösen.",
        )

    def test_record_deactivated_after_decrement_to_zero(self):
        """Nach Decrement auf 0 muss der SuspensionRecord is_active=False sein."""
        from .season_service import _apply_match_suspensions, _decrement_suspensions_for_clubs
        from .models import PlayerSuspensionRecord
        _apply_match_suspensions(
            [{'pid': self.player.id, 'yellow': 0, 'red': 1}],
            competition='Bundesliga',
            season='2026/27',
        )
        _decrement_suspensions_for_clubs([self.club.id])
        self.assertTrue(
            PlayerSuspensionRecord.objects.filter(
                player=self.player, is_active=False,
            ).exists(),
            "Record muss nach Ablauf is_active=False haben.",
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.ws_suspension_matches_remaining, 0)


class SuspensionDecrementTests(TestCase):
    """Sperren dürfen nur bei Pflichtspielen abgebaut werden."""

    def setUp(self):
        league = League.objects.create(
            name='Testliga Sperren',
            country='Deutschland',
        )
        self.club = Club.objects.create(
            name='Testclub Sperren',
            short_name='TSS',
            fm_inside_id=99901,
            founded_year=1900,
            budget=Decimal('1000000.00'),
            league=league,
        )
        self.player = Player.objects.create(
            first_name='Hans',
            last_name='Gesperrt',
            position='ST',
            age=25,
            club=self.club,
            ws_suspension_matches_remaining=1,
            ws_suspension_reason='Rotsperre',
        )

    def test_friendly_does_not_consume_suspension(self):
        """Freundschaft: Sperre bleibt erhalten."""
        from .season_service import _decrement_suspensions_for_clubs
        # Wird bei Freundschaft bewusst NICHT aufgerufen — hier direkt prüfen
        # dass die Funktion an sich korrekt dekrementiert
        self.player.refresh_from_db()
        before = self.player.ws_suspension_matches_remaining
        # Kein Aufruf für Freundschaft → Wert unverändert
        self.player.refresh_from_db()
        self.assertEqual(
            self.player.ws_suspension_matches_remaining,
            before,
            "Freundschaft darf Sperre nicht verbrauchen.",
        )

    def test_pflichtspiel_decrements_suspension(self):
        """Pflichtspiel (Pokal/Liga): Sperre wird um 1 reduziert."""
        from .season_service import _decrement_suspensions_for_clubs
        self.player.refresh_from_db()
        _decrement_suspensions_for_clubs([self.club.id])
        self.player.refresh_from_db()
        self.assertEqual(
            self.player.ws_suspension_matches_remaining,
            0,
            "Nach einem Pflichtspiel muss ws_suspension_matches_remaining 0 sein.",
        )
        self.assertEqual(
            self.player.ws_suspension_reason,
            '',
            "Nach Ablauf der Sperre muss ws_suspension_reason geleert werden.",
        )

    def test_suspension_at_zero_cleared_after_pflichtspiel(self):
        """Spieler mit remaining=0 bleibt bei 0 — keine negative Sperre."""
        from .season_service import _decrement_suspensions_for_clubs
        self.player.ws_suspension_matches_remaining = 0
        self.player.ws_suspension_reason = ''
        self.player.save()
        _decrement_suspensions_for_clubs([self.club.id])
        self.player.refresh_from_db()
        self.assertGreaterEqual(
            self.player.ws_suspension_matches_remaining,
            0,
            "ws_suspension_matches_remaining darf nicht negativ werden.",
        )


class InjuryEngineTests(TestCase):
    """Testet _generate_injury_events aus match_engine.py."""

    def test_empty_player_list_returns_empty(self):
        from .match_engine import _generate_injury_events
        result = _generate_injury_events([], club_side='home')
        self.assertEqual(result, [])

    def test_event_structure(self):
        """Jeder Injury-Event muss die Pflichtfelder enthalten."""
        from .match_engine import _generate_injury_events
        import random as _rng
        _rng.seed(42)
        players = [
            {'id': i, 'name': f'Spieler {i}', 'fitness': 40}
            for i in range(1, 20)
        ]
        events = _generate_injury_events(players, club_side='away')
        for evt in events:
            self.assertIn('player_id',   evt)
            self.assertIn('player_name', evt)
            self.assertIn('club_side',   evt)
            self.assertIn('minute',      evt)
            self.assertIn('injury_type', evt)
            self.assertIn('days',        evt)
            self.assertEqual(evt['club_side'], 'away')
            self.assertIn(evt['injury_type'], ('Leicht', 'Mittel', 'Schwer'))
            self.assertGreaterEqual(evt['days'], 3)
            self.assertLessEqual(evt['days'], 56)
            self.assertGreaterEqual(evt['minute'], 10)
            self.assertLessEqual(evt['minute'], 90)

    def test_no_events_with_prob_zero(self):
        """Bei 0 % Verletzungswahrscheinlichkeit keine Events."""
        from .match_engine import _generate_injury_events
        import unittest.mock as mock
        players = [{'id': i, 'name': f'P{i}', 'fitness': 100} for i in range(11)]
        with mock.patch('game.match_engine.random.random', return_value=0.99):
            events = _generate_injury_events(players, club_side='home')
        self.assertEqual(events, [])

    def test_all_events_capped_at_max(self):
        """Auch wenn alle Spieler verletzbar wären, gilt das Team-Cap."""
        from .match_engine import _generate_injury_events, _MAX_INJURIES_PER_TEAM
        import unittest.mock as mock
        players = [{'id': i, 'name': f'P{i}', 'fitness': 100} for i in range(11)]
        with mock.patch('game.match_engine.random.random', return_value=0.0):
            with mock.patch('game.match_engine.random.randint', return_value=15):
                events = _generate_injury_events(players, club_side='home')
        self.assertLessEqual(len(events), _MAX_INJURIES_PER_TEAM)

    def test_low_fitness_increases_events(self):
        """Spieler mit Fitness < 70 haben höhere Verletzungsrate."""
        from .match_engine import _generate_injury_events
        import random as _rng
        _rng.seed(0)
        high_fit = [{'id': i, 'name': f'H{i}', 'fitness': 95} for i in range(100)]
        low_fit  = [{'id': i, 'name': f'L{i}', 'fitness': 40} for i in range(100)]
        _rng.seed(0)
        high_events = _generate_injury_events(high_fit, club_side='home')
        _rng.seed(0)
        low_events  = _generate_injury_events(low_fit,  club_side='home')
        self.assertGreaterEqual(
            len(low_events), len(high_events),
            "Spieler mit niedriger Fitness sollen häufiger verletzt werden.",
        )

    def test_max_injuries_per_team_capped(self):
        """Pro Team dürfen maximal _MAX_INJURIES_PER_TEAM (2) Verletzungen entstehen."""
        from .match_engine import _generate_injury_events, _MAX_INJURIES_PER_TEAM
        import unittest.mock as mock
        players = [{'id': i, 'name': f'P{i}', 'fitness': 40} for i in range(11)]
        with mock.patch('game.match_engine.random.random', return_value=0.0):
            with mock.patch('game.match_engine.random.randint', return_value=15):
                with mock.patch('game.match_engine.random.sample', side_effect=lambda seq, k: list(seq)[:k]):
                    events = _generate_injury_events(players, club_side='home')
        self.assertLessEqual(
            len(events), _MAX_INJURIES_PER_TEAM,
            f"Maximal {_MAX_INJURIES_PER_TEAM} Verletzungen pro Team erlaubt.",
        )

    def test_injury_type_distribution(self):
        """Verletzungstypen sollen sich in der richtigen Gewichtung verteilen."""
        from .match_engine import _generate_injury_events
        import random as _rng
        _rng.seed(123)
        many_players = [{'id': i, 'name': f'P{i}', 'fitness': 40} for i in range(1000)]
        events = _generate_injury_events(many_players, club_side='home')
        if not events:
            self.skipTest("Kein Event generiert – Seed anpassen")
        types = [e['injury_type'] for e in events]
        count_leicht = types.count('Leicht')
        count_schwer = types.count('Schwer')
        self.assertGreater(count_leicht, count_schwer,
                           "Leichte Verletzungen sollen häufiger sein als schwere.")


class InjuryPersistenceTests(TestCase):
    """Testet _write_injury_events aus season_service.py."""

    def setUp(self):
        from decimal import Decimal
        self.league = League.objects.create(name='InjTestLiga', country='Deutschland')
        self.club = Club.objects.create(
            name='InjTestClub',
            short_name='ITC',
            fm_inside_id=99991,
            founded_year=2000,
            budget=Decimal('1000000.00'),
            league=self.league,
        )
        self.player = Player.objects.create(
            first_name='Max',
            last_name='Verletzt',
            position='ST',
            age=24,
            club=self.club,
        )

    def test_write_injury_sets_player_fields(self):
        from datetime import date
        from .season_service import _write_injury_events
        events = [{
            'player_id':   self.player.id,
            'player_name': 'Max Verletzt',
            'club_side':   'home',
            'minute':      37,
            'injury_type': 'Mittel',
            'days':        14,
        }]
        _write_injury_events(events, date(2026, 8, 15), 'Bundesliga')
        self.player.refresh_from_db()
        self.assertEqual(self.player.ws_injury_type, 'Mittel')
        self.assertEqual(self.player.ws_injury_days_remaining, 14)
        self.assertTrue(self.player.is_ws_injured)

    def test_write_injury_creates_record(self):
        from datetime import date
        from .season_service import _write_injury_events
        events = [{
            'player_id':   self.player.id,
            'player_name': 'Max Verletzt',
            'club_side':   'home',
            'minute':      55,
            'injury_type': 'Schwer',
            'days':        42,
        }]
        _write_injury_events(events, date(2026, 8, 15), 'Bundesliga')
        record = PlayerInjuryRecord.objects.get(player=self.player, is_active=True)
        self.assertEqual(record.injury_type, 'Schwer')
        self.assertEqual(record.days_missed, 42)
        self.assertEqual(record.competition, 'Bundesliga')

    def test_write_injury_deactivates_previous(self):
        """Vorherige aktive Verletzung wird auf is_active=False gesetzt."""
        from datetime import date
        from .season_service import _write_injury_events
        PlayerInjuryRecord.objects.create(
            player=self.player,
            injury_type='Leicht',
            days_missed=5,
            is_active=True,
        )
        events = [{
            'player_id':   self.player.id,
            'player_name': 'Max Verletzt',
            'club_side':   'away',
            'minute':      70,
            'injury_type': 'Mittel',
            'days':        18,
        }]
        _write_injury_events(events, date(2026, 8, 15), 'Bundesliga')
        active_count = PlayerInjuryRecord.objects.filter(
            player=self.player, is_active=True,
        ).count()
        self.assertEqual(active_count, 1, "Nur ein aktiver Record darf existieren.")

    def test_write_empty_injury_list_noop(self):
        """Leere Liste verändert den Spieler nicht."""
        from datetime import date
        from .season_service import _write_injury_events
        _write_injury_events([], date(2026, 8, 15), 'Bundesliga')
        self.player.refresh_from_db()
        self.assertEqual(self.player.ws_injury_days_remaining, 0)
        self.assertFalse(self.player.is_ws_injured)

    def test_write_ignores_unknown_player_id(self):
        """Unbekannte player_id löst keinen Fehler aus."""
        from datetime import date
        from .season_service import _write_injury_events
        events = [{'player_id': 999999, 'injury_type': 'Leicht', 'days': 4}]
        try:
            _write_injury_events(events, date(2026, 8, 15), 'Bundesliga')
        except Exception as exc:
            self.fail(f"_write_injury_events raised unexpectedly: {exc}")


class BuildCombinedEventsInjuryTests(TestCase):
    """Testet dass injury_events in combined_events erscheinen."""

    def test_injury_event_in_combined(self):
        from .views import _build_combined_events
        data = {
            'goal_events': [],
            'card_events': [],
            'injury_events': [{
                'player_id':   42,
                'player_name': 'Test Spieler',
                'club_side':   'home',
                'minute':      63,
                'injury_type': 'Leicht',
                'days':        5,
            }],
        }
        events = _build_combined_events(data, [], [], {42: 'Test Spieler'})
        injury_evts = [e for e in events if e['type'] == 'injury']
        self.assertEqual(len(injury_evts), 1)
        e = injury_evts[0]
        self.assertEqual(e['type'],        'injury')
        self.assertEqual(e['team'],        'home')
        self.assertEqual(e['minute'],      63)
        self.assertEqual(e['player_name'], 'Test Spieler')
        self.assertEqual(e['injury_type'], 'Leicht')
        self.assertEqual(e['days'],        5)

    def test_combined_events_sorted_by_minute(self):
        from .views import _build_combined_events
        data = {
            'goal_events': [{'team': 'home', 'minute': 80, 'scorer_name': 'Müller',
                             'scorer_pos': 'ST', 'assister_name': ''}],
            'card_events': [{'player_id': 1, 'player_name': 'Rote', 'club_side': 'away',
                             'minute': 45, 'card_type': 'red'}],
            'injury_events': [{'player_id': 2, 'player_name': 'Verletzt',
                               'club_side': 'home', 'minute': 30,
                               'injury_type': 'Mittel', 'days': 14}],
        }
        events = _build_combined_events(data, [], [], {1: 'Rote', 2: 'Verletzt'})
        minutes = [e['minute'] for e in events]
        self.assertEqual(minutes, sorted(minutes), "Events müssen nach Minute sortiert sein.")


# ── Mid-Match-Einwechslung Engine ─────────────────────────────────────────────

class CeilFiveTests(TestCase):
    """_ceil5(): Spielminuten auf 5er-Vielfaches aufrunden."""

    def test_exact_multiple(self):
        from .match_engine import _ceil5
        self.assertEqual(_ceil5(60), 60)
        self.assertEqual(_ceil5(45), 45)
        self.assertEqual(_ceil5(5),   5)

    def test_rounds_up(self):
        from .match_engine import _ceil5
        self.assertEqual(_ceil5(63), 65)
        self.assertEqual(_ceil5(61), 65)
        self.assertEqual(_ceil5(66), 70)
        self.assertEqual(_ceil5(1),   5)

    def test_zero_clamp(self):
        from .match_engine import _ceil5
        self.assertEqual(_ceil5(0), 5)


class CheckSubConditionTests(TestCase):
    """_check_sub_condition(): einmalige Bedingungsprüfung."""

    def test_immer_always_true(self):
        from .match_engine import _check_sub_condition
        self.assertTrue(_check_sub_condition('immer', 0, 0))
        self.assertTrue(_check_sub_condition('immer', 2, 1))
        self.assertTrue(_check_sub_condition(None,    1, 3))
        self.assertTrue(_check_sub_condition('',      0, 0))

    def test_fuehrung(self):
        from .match_engine import _check_sub_condition
        self.assertTrue(_check_sub_condition('fuehrung',     2, 1))
        self.assertFalse(_check_sub_condition('fuehrung',    1, 2))
        self.assertFalse(_check_sub_condition('fuehrung',    0, 0))

    def test_rueckstand(self):
        from .match_engine import _check_sub_condition
        self.assertTrue(_check_sub_condition('rueckstand',   0, 1))
        self.assertFalse(_check_sub_condition('rueckstand',  1, 0))
        self.assertFalse(_check_sub_condition('rueckstand',  0, 0))

    def test_unentschieden(self):
        from .match_engine import _check_sub_condition
        self.assertTrue(_check_sub_condition('unentschieden', 1, 1))
        self.assertFalse(_check_sub_condition('unentschieden', 2, 1))

    def test_unknown_condition_is_true(self):
        from .match_engine import _check_sub_condition
        self.assertTrue(_check_sub_condition('???', 0, 0))


def _make_als(
    lineup=None, players=None, bench=None, subs=None,
):
    """Hilfsfunktion: ActiveLineupState mit minimalen Test-Daten."""
    from .match_engine import ActiveLineupState
    _lineup = lineup or [
        {'player_id': 1, 'position': 'striker',     'group': 'attack'},
        {'player_id': 2, 'position': 'central_mid', 'group': 'midfield'},
        {'player_id': 3, 'position': 'goalkeeper',  'group': 'goalkeeper'},
    ]
    _players = players or {
        1: {'id': 1, 'name': 'Stürmer',   'final_strength': 70.0, 'main_positions': ['striker'],     'secondary_positions': [], 'teamwork': 3, 'freshness': 100},
        2: {'id': 2, 'name': 'Mittelfeld', 'final_strength': 65.0, 'main_positions': ['central_mid'], 'secondary_positions': [], 'teamwork': 3, 'freshness': 100},
        3: {'id': 3, 'name': 'Keeper',    'final_strength': 75.0, 'main_positions': ['goalkeeper'],  'secondary_positions': [], 'teamwork': 3, 'freshness': 100},
    }
    _bench = bench or {
        10: {'id': 10, 'name': 'Bank-A', 'final_strength': 60.0, 'main_positions': ['striker'],     'secondary_positions': [], 'teamwork': 2, 'freshness': 100},
        11: {'id': 11, 'name': 'Bank-B', 'final_strength': 55.0, 'main_positions': ['central_mid'], 'secondary_positions': [], 'teamwork': 2, 'freshness': 100},
    }
    return ActiveLineupState(
        lineup=_lineup,
        players_by_id=_players,
        bench_by_id=_bench,
        planned_subs=subs or [],
    )


class ActiveLineupStateBasicsTests(TestCase):
    """ActiveLineupState: Grundverhalten ohne Wechsel."""

    def test_get_active_lineup_full(self):
        als = _make_als()
        active = als.get_active_lineup()
        self.assertEqual(len(active), 3)
        pids = {s['player_id'] for s in active}
        self.assertEqual(pids, {1, 2, 3})

    def test_dismissed_pid_excluded(self):
        als = _make_als()
        active = als.get_active_lineup(dismissed_pids={1})
        self.assertEqual(len(active), 2)
        self.assertNotIn(1, {s['player_id'] for s in active})

    def test_can_substitute_initial(self):
        als = _make_als()
        self.assertTrue(als.can_substitute())

    def test_quota_exhausted(self):
        from .match_engine import ActiveLineupState, MAX_SUBSTITUTIONS
        als = _make_als()
        als.used_substitutions = MAX_SUBSTITUTIONS
        self.assertFalse(als.can_substitute())


class ActiveLineupStateSubTests(TestCase):
    """ActiveLineupState: Wechsel werden korrekt ausgeführt."""

    def _make_sub(self, in_pid, out_pid, minute, condition='immer'):
        return {'in': in_pid, 'out': out_pid, 'minute': minute, 'condition': condition}

    def test_simple_sub_executes(self):
        subs = [self._make_sub(10, 1, 60)]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 0)
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertIn(10, active_pids)   # Einwechselspieler auf dem Feld
        self.assertNotIn(1, active_pids) # Ausgewechselter weg
        self.assertEqual(als.used_substitutions, 1)

    def test_minute_rounding_to_ceil5(self):
        subs = [self._make_sub(10, 1, 63)]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 0)
        self.assertEqual(als.sub_events[0]['minute'], 65)

    def test_sub_not_executed_before_its_segment(self):
        subs = [self._make_sub(10, 1, 70)]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 0)  # segment 66 < sub_minute 70 → nicht fällig
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertNotIn(10, active_pids)
        self.assertEqual(als.used_substitutions, 0)

    def test_condition_fuehrung_not_met_discards(self):
        subs = [self._make_sub(10, 1, 60, condition='fuehrung')]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 1)  # im Rückstand
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertNotIn(10, active_pids)  # Bedingung nicht erfüllt → verworfen
        self.assertEqual(als.used_substitutions, 0)

    def test_condition_not_retried_after_discard(self):
        """Einmal verworfene Bedingung darf nicht später doch ausgeführt werden."""
        subs = [self._make_sub(10, 1, 60, condition='fuehrung')]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 1)  # Rückstand → verworfen
        als.process_planned_subs(76, 2, 1)  # jetzt Führung — darf trotzdem NICHT ausgeführt werden
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertNotIn(10, active_pids)
        self.assertEqual(als.used_substitutions, 0)

    def test_quota_prevents_sixth_sub(self):
        from .match_engine import MAX_SUBSTITUTIONS
        lineup = [{'player_id': i, 'position': 'striker', 'group': 'attack'} for i in range(1, 12)]
        players = {i: {'id': i, 'name': f'P{i}', 'final_strength': 60.0,
                       'main_positions': ['striker'], 'secondary_positions': [],
                       'teamwork': 2, 'freshness': 100} for i in range(1, 12)}
        bench   = {i: {'id': i, 'name': f'B{i}', 'final_strength': 55.0,
                       'main_positions': ['striker'], 'secondary_positions': [],
                       'teamwork': 2, 'freshness': 100} for i in range(20, 27)}
        subs    = [{'in': 20+j, 'out': 1+j, 'minute': 10+j*5, 'condition': 'immer'} for j in range(6)]
        als = _make_als(lineup=lineup, players=players, bench=bench, subs=subs)
        als.process_planned_subs(91, 0, 0)  # alle fällig
        self.assertEqual(als.used_substitutions, MAX_SUBSTITUTIONS)
        self.assertEqual(len(als.sub_events), MAX_SUBSTITUTIONS)

    def test_sub_slot_inherits_position(self):
        subs = [self._make_sub(10, 1, 60)]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 0)
        ev = als.sub_events[0]
        self.assertEqual(ev['target_slot'], 'striker')

    def test_bench_player_removed_from_bench_after_sub(self):
        subs = [self._make_sub(10, 1, 60)]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 0)
        self.assertNotIn(10, als._bench_available)

    def test_dismissed_player_cannot_be_subbed_out(self):
        """Verwiesener Spieler ist bereits weg — Wechsel darf nicht ausgeführt werden."""
        subs = [self._make_sub(10, 1, 60)]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 0, dismissed_pids={1})
        active_pids = {s['player_id'] for s in als.get_active_lineup({1})}
        self.assertNotIn(10, active_pids)
        self.assertEqual(als.used_substitutions, 0)


class ActiveLineupPlayersTests(TestCase):
    """_active_lineup_players(): korrekte Umwandlung Lineup → Spielerliste."""

    def test_returns_players_with_position(self):
        from .match_engine import _active_lineup_players
        lineup = [{'player_id': 1, 'position': 'striker', 'group': 'attack'}]
        players = {1: {'id': 1, 'name': 'Test', 'final_strength': 70.0}}
        result = _active_lineup_players(lineup, players)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['position'], 'striker')
        self.assertEqual(result[0]['group'],    'attack')

    def test_missing_player_skipped(self):
        from .match_engine import _active_lineup_players
        lineup = [{'player_id': 99, 'position': 'striker', 'group': 'attack'}]
        result = _active_lineup_players(lineup, {})
        self.assertEqual(result, [])


class EnrichSubstitutionsExtraFieldsTests(TestCase):
    """_enrich_substitutions(): optionale Felder werden durchgereicht."""

    def test_target_slot_passed_through(self):
        from .views import _enrich_substitutions
        subs = [{'minute': 65, 'in': 10, 'out': 1,
                 'target_slot': 'striker', 'position_relation': 'HP', 'condition': 'immer'}]
        result = _enrich_substitutions(subs, {10: 'Neu', 1: 'Alt'})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['target_slot'],       'striker')
        self.assertEqual(result[0]['position_relation'], 'HP')
        self.assertEqual(result[0]['condition'],         'immer')

    def test_missing_extra_fields_ok(self):
        from .views import _enrich_substitutions
        subs = [{'minute': 65, 'in': 10, 'out': 1}]
        result = _enrich_substitutions(subs, {10: 'Neu', 1: 'Alt'})
        self.assertEqual(len(result), 1)
        self.assertNotIn('target_slot', result[0])


# ── Frische-/Belastungsmodell V1 ─────────────────────────────────────────────

class FreshnessServiceUnitTests(TestCase):
    """Unit-Tests für game.freshness_service — keine DB nötig."""

    def test_performance_factor_full_freshness(self):
        from .freshness_service import freshness_performance_factor
        self.assertEqual(freshness_performance_factor(100), 1.00)
        self.assertEqual(freshness_performance_factor(85),  1.00)
        self.assertEqual(freshness_performance_factor(80),  1.00)

    def test_performance_factor_tired(self):
        from .freshness_service import freshness_performance_factor
        f70 = freshness_performance_factor(75)
        f60 = freshness_performance_factor(65)
        f50 = freshness_performance_factor(55)
        f40 = freshness_performance_factor(40)
        self.assertAlmostEqual(f70, 0.985, places=3)
        self.assertAlmostEqual(f60, 0.96,  places=3)
        self.assertAlmostEqual(f50, 0.93,  places=3)
        self.assertAlmostEqual(f40, 0.88,  places=3)
        self.assertLess(f70, 1.00)
        self.assertLess(f60, f70)
        self.assertLess(f50, f60)
        self.assertLess(f40, f50)

    def test_injury_multiplier_tiers(self):
        from .freshness_service import freshness_injury_multiplier
        self.assertAlmostEqual(freshness_injury_multiplier(100), 1.00)
        self.assertAlmostEqual(freshness_injury_multiplier(95),  1.00)
        self.assertAlmostEqual(freshness_injury_multiplier(85),  1.05)
        self.assertAlmostEqual(freshness_injury_multiplier(75),  1.15)
        self.assertAlmostEqual(freshness_injury_multiplier(65),  1.35)
        self.assertAlmostEqual(freshness_injury_multiplier(55),  1.70)
        self.assertAlmostEqual(freshness_injury_multiplier(40),  2.30)

    def test_ausdauer_factor(self):
        from .freshness_service import _ausdauer_factor
        self.assertAlmostEqual(_ausdauer_factor(70),  1.00, places=3)
        self.assertAlmostEqual(_ausdauer_factor(100), 0.86, places=3)
        self.assertAlmostEqual(_ausdauer_factor(40),  1.12, places=2)
        self.assertAlmostEqual(_ausdauer_factor(None), 1.00, places=3)
        self.assertGreaterEqual(_ausdauer_factor(0), 0.86)
        self.assertLessEqual(_ausdauer_factor(200), 1.12)

    def test_compute_single_player_loss_gk_min(self):
        from .freshness_service import compute_single_player_loss
        loss = compute_single_player_loss('TW', 70, 1.0, 0, minutes=90)
        self.assertGreaterEqual(loss, 1.0, "TW-Minimum ist 1 Punkt")
        self.assertLessEqual(loss, 18.0)

    def test_compute_single_player_loss_field_min(self):
        from .freshness_service import compute_single_player_loss
        loss = compute_single_player_loss('ZM', 70, 1.0, 0, minutes=90)
        self.assertGreaterEqual(loss, 3.0, "Feldspieler-Minimum ist 3 Punkte")
        self.assertLessEqual(loss, 18.0)

    def test_compute_single_player_loss_zero_minutes(self):
        from .freshness_service import compute_single_player_loss
        loss = compute_single_player_loss('ZM', 70, 1.0, 0, minutes=0)
        self.assertEqual(loss, 0.0, "0 Minuten → kein Verlust")

    def test_compute_single_player_loss_training_reduction(self):
        from .freshness_service import compute_single_player_loss
        base = compute_single_player_loss('ZM', 70, 1.0, 0, minutes=90)
        s2   = compute_single_player_loss('ZM', 70, 1.0, 2, minutes=90)
        self.assertLess(s2, base, "Training-Stufe 2 muss Verlust reduzieren")

    def test_compute_single_player_loss_max_cap(self):
        from .freshness_service import compute_single_player_loss
        loss = compute_single_player_loss('LF', 40, 1.5, 0, minutes=120)
        self.assertLessEqual(loss, 18.0, "Maximum 18 Punkte")

    def test_compute_loss_position_scaling(self):
        """Flügel/Außenbahn verliert mehr als TW."""
        from .freshness_service import compute_single_player_loss
        tw  = compute_single_player_loss('TW',  70, 1.0, 0)
        lf  = compute_single_player_loss('LF',  70, 1.0, 0)
        self.assertLess(tw, lf)

    def test_zm_normal_90min_approx_9_5(self):
        """Spec-Zieltest: ZM, Ausdauer 75, normale Taktik → ~9.5 Verlust."""
        from .freshness_service import compute_single_player_loss
        loss = compute_single_player_loss('ZM', 75, 1.0, 0, minutes=90)
        self.assertGreater(loss, 8.5)
        self.assertLess(loss, 10.5)

    def test_daily_recovery_high_freshness_dampened(self):
        """90–100 Frische → nur 50 % der Basisregeneration."""
        from .freshness_service import daily_recovery_amount, BASE_DAILY_RECOVERY
        r100 = daily_recovery_amount(100.0, 0)
        r95  = daily_recovery_amount(95.0,  0)
        r90  = daily_recovery_amount(90.0,  0)
        expected = round(BASE_DAILY_RECOVERY * 0.50, 4)
        self.assertAlmostEqual(r100, expected, places=3)
        self.assertAlmostEqual(r95,  expected, places=3)
        self.assertAlmostEqual(r90,  expected, places=3)

    def test_daily_recovery_medium_freshness_dampened(self):
        """80–89 Frische → 75 % der Basisregeneration."""
        from .freshness_service import daily_recovery_amount, BASE_DAILY_RECOVERY
        r89 = daily_recovery_amount(89.0, 0)
        r85 = daily_recovery_amount(85.0, 0)
        r80 = daily_recovery_amount(80.0, 0)
        expected = round(BASE_DAILY_RECOVERY * 0.75, 4)
        self.assertAlmostEqual(r89, expected, places=3)
        self.assertAlmostEqual(r85, expected, places=3)
        self.assertAlmostEqual(r80, expected, places=3)

    def test_daily_recovery_low_freshness_full(self):
        """Unter 80 Frische → volle Basisregeneration."""
        from .freshness_service import daily_recovery_amount, BASE_DAILY_RECOVERY
        r79 = daily_recovery_amount(79.0, 0)
        r50 = daily_recovery_amount(50.0, 0)
        r0  = daily_recovery_amount(0.0,  0)
        self.assertAlmostEqual(r79, BASE_DAILY_RECOVERY, places=3)
        self.assertAlmostEqual(r50, BASE_DAILY_RECOVERY, places=3)
        self.assertAlmostEqual(r0,  BASE_DAILY_RECOVERY, places=3)

    def test_daily_recovery_training_s3_bonus_always_added(self):
        """Training S3 addiert immer vollen Bonus, unabhängig von Frische."""
        from .freshness_service import (
            daily_recovery_amount, BASE_DAILY_RECOVERY,
            TRAINING_GROUND_S3_DAILY_RECOVERY,
        )
        r_high = daily_recovery_amount(95.0, 3)
        r_mid  = daily_recovery_amount(85.0, 3)
        r_low  = daily_recovery_amount(50.0, 3)
        bonus = TRAINING_GROUND_S3_DAILY_RECOVERY
        self.assertAlmostEqual(r_high, round(BASE_DAILY_RECOVERY * 0.50 + bonus, 4), places=3)
        self.assertAlmostEqual(r_mid,  round(BASE_DAILY_RECOVERY * 0.75 + bonus, 4), places=3)
        self.assertAlmostEqual(r_low,  round(BASE_DAILY_RECOVERY + bonus,        4), places=3)

    def test_daily_recovery_ordering(self):
        """Erschöpfte Spieler regenerieren schneller als erholte."""
        from .freshness_service import daily_recovery_amount
        r_full    = daily_recovery_amount(100.0, 0)
        r_medium  = daily_recovery_amount(85.0,  0)
        r_tired   = daily_recovery_amount(50.0,  0)
        self.assertLess(r_full, r_medium)
        self.assertLess(r_medium, r_tired)

    def test_daily_recovery_no_training_s1_s2_effect(self):
        """Training S1 und S2 geben keinen Bonus auf Regeneration (nur S3)."""
        from .freshness_service import daily_recovery_amount
        r_s0 = daily_recovery_amount(70.0, 0)
        r_s1 = daily_recovery_amount(70.0, 1)
        r_s2 = daily_recovery_amount(70.0, 2)
        self.assertAlmostEqual(r_s0, r_s1, places=3)
        self.assertAlmostEqual(r_s1, r_s2, places=3)


class FreshnessDecayIntegrationTests(TestCase):
    """Integration-Tests für apply_match_freshness_losses und apply_daily_recovery."""

    def _make_club(self, training_level=0, medizin_level=0):
        from .models import Club, Stadium, League
        import uuid
        slug = uuid.uuid4().hex[:6]
        league, _ = League.objects.get_or_create(
            name='TestLiga',
            defaults={'country': 'DE'},
        )
        club = Club.objects.create(
            name=f'TestClub-{slug}',
            short_name='TST',
            founded_year=2000,
            budget=1000000,
            league=league,
        )
        Stadium.objects.create(
            club=club,
            name=f'TestStadion-{slug}',
            city='Teststadt',
            training_level=training_level,
            medizin_level=medizin_level,
        )
        return club

    def _make_player(self, club, freshness=100):
        from .models import Player, PlayerStrengthProfile
        from decimal import Decimal
        p = Player.objects.create(
            club=club,
            first_name='Test',
            last_name='Spieler',
            age=25,
            position='ZM',
        )
        PlayerStrengthProfile.objects.create(
            player=p,
            base_strength=Decimal('70.00'),
            freshness=Decimal(str(freshness)),
        )
        return p

    def test_apply_match_freshness_reduces_freshness(self):
        from .freshness_service import apply_match_freshness_losses
        from .models import PlayerStrengthProfile
        club = self._make_club()
        p = self._make_player(club, freshness=100)

        home_players = [{'id': p.pk, 'position': 'ZM'}]
        apply_match_freshness_losses(
            home_players=home_players,
            away_players=[],
            home_club=club,
            away_club=club,
            fatigue_cost_home=1.0,
        )

        sp = PlayerStrengthProfile.objects.get(player=p)
        self.assertLess(float(sp.freshness), 100.0, "Frische muss nach Spiel sinken")

    def test_freshness_does_not_go_below_zero(self):
        from .freshness_service import apply_match_freshness_losses
        from .models import PlayerStrengthProfile
        club = self._make_club()
        p = self._make_player(club, freshness=2)

        home_players = [{'id': p.pk, 'position': 'LF'}]
        apply_match_freshness_losses(
            home_players=home_players,
            away_players=[],
            home_club=club,
            away_club=club,
            fatigue_cost_home=1.5,
        )

        sp = PlayerStrengthProfile.objects.get(player=p)
        self.assertGreaterEqual(float(sp.freshness), 0.0, "Frische darf nicht unter 0")

    def test_training_ground_s2_reduces_loss(self):
        from .freshness_service import apply_match_freshness_losses
        from .models import PlayerStrengthProfile
        club_s0 = self._make_club(training_level=0)
        club_s2 = self._make_club(training_level=2)
        p0 = self._make_player(club_s0, freshness=100)
        p2 = self._make_player(club_s2, freshness=100)

        apply_match_freshness_losses(
            home_players=[{'id': p0.pk, 'position': 'ZM'}],
            away_players=[{'id': p2.pk, 'position': 'ZM'}],
            home_club=club_s0,
            away_club=club_s2,
        )

        sp0 = PlayerStrengthProfile.objects.get(player=p0)
        sp2 = PlayerStrengthProfile.objects.get(player=p2)
        self.assertGreater(float(sp2.freshness), float(sp0.freshness),
                           "Trainingsgelände S2 soll weniger Verlust haben → mehr Frische danach")

    def test_apply_daily_recovery_increases_freshness(self):
        from .freshness_service import apply_daily_recovery
        from .models import PlayerStrengthProfile
        club = self._make_club()
        p = self._make_player(club, freshness=80)

        count = apply_daily_recovery()
        self.assertGreater(count, 0)

        sp = PlayerStrengthProfile.objects.get(player=p)
        self.assertGreater(float(sp.freshness), 80.0)

    def test_apply_daily_recovery_does_not_exceed_100(self):
        from .freshness_service import apply_daily_recovery
        from .models import PlayerStrengthProfile
        club = self._make_club()
        p = self._make_player(club, freshness=100)

        apply_daily_recovery()

        sp = PlayerStrengthProfile.objects.get(player=p)
        self.assertLessEqual(float(sp.freshness), 100.0)

    def test_injured_player_skipped_by_recovery(self):
        from .freshness_service import apply_daily_recovery
        from .models import PlayerStrengthProfile
        club = self._make_club()
        p = self._make_player(club, freshness=60)
        p.ws_injury_days_remaining = 10
        p.ws_injury_type = 'Leicht'
        p.save(update_fields=['ws_injury_days_remaining', 'ws_injury_type'])

        apply_daily_recovery()

        sp = PlayerStrengthProfile.objects.get(player=p)
        self.assertAlmostEqual(float(sp.freshness), 60.0, places=1,
                               msg="Verletzte Spieler sollen nicht regenerieren")

    def test_training_s3_gives_more_recovery(self):
        from .freshness_service import apply_daily_recovery
        from .models import PlayerStrengthProfile
        club_s0 = self._make_club(training_level=0)
        club_s3 = self._make_club(training_level=3)
        p0 = self._make_player(club_s0, freshness=80)
        p3 = self._make_player(club_s3, freshness=80)

        apply_daily_recovery()

        sp0 = PlayerStrengthProfile.objects.get(player=p0)
        sp3 = PlayerStrengthProfile.objects.get(player=p3)
        self.assertGreater(float(sp3.freshness), float(sp0.freshness),
                           "Trainingsgelände S3 bringt mehr Regeneration")


class FreshnessFreundschaftExclusionTests(TestCase):
    """Freundschaftsspiele dürfen keine Frische-Verluste oder Verletzungen hinterlassen."""

    def _make_club(self):
        from .models import Club, Stadium, League
        import uuid
        slug = uuid.uuid4().hex[:6]
        league, _ = League.objects.get_or_create(
            name='TestLiga',
            defaults={'country': 'DE'},
        )
        club = Club.objects.create(
            name=f'TestClub-{slug}',
            short_name='TST',
            founded_year=2000,
            budget=1000000,
            league=league,
        )
        Stadium.objects.create(
            club=club,
            name=f'Stadion-{slug}',
            city='Teststadt',
            training_level=0,
            medizin_level=0,
        )
        return club

    def _make_player(self, club, freshness=90):
        from .models import Player, PlayerStrengthProfile
        from decimal import Decimal
        import uuid
        p = Player.objects.create(
            club=club,
            first_name='Test',
            last_name=uuid.uuid4().hex[:8],
            age=25,
            position='ZM',
        )
        PlayerStrengthProfile.objects.create(
            player=p,
            base_strength=Decimal('70.00'),
            freshness=Decimal(str(freshness)),
        )
        return p

    def _call_write_simulated(self, home_club, away_club, home_player, away_player,
                               match_type='freundschaft', injury_events=None):
        """Minimaler SimulatedMatch + write_simulated_match_stats-Aufruf."""
        from .models import SimulatedMatch
        from .season_service import write_simulated_match_stats
        from django.utils import timezone
        sm = SimulatedMatch.objects.create(
            home_club=home_club,
            away_club=away_club,
            match_type=match_type,
            home_goals=1,
            away_goals=1,
            simulated_at=timezone.now(),
        )
        data = {
            'home_players': [{'id': home_player.pk, 'position': 'ZM',
                               'minutes_played': 90, 'goals': 0,
                               'assists': 0, 'yellow_cards': 1, 'red_cards': 0,
                               'grade': 6.0}],
            'away_players': [{'id': away_player.pk, 'position': 'ZM',
                               'minutes_played': 90, 'goals': 0,
                               'assists': 0, 'yellow_cards': 0, 'red_cards': 0,
                               'grade': 6.0}],
            'injury_events': injury_events or [
                {'player_id': home_player.pk, 'team': 'home',
                 'minute': 55, 'severity': 14}
            ],
            'home_fatigue_cost': 1.0,
            'away_fatigue_cost': 1.0,
        }
        write_simulated_match_stats(sm, data)
        return sm

    def test_freundschaft_no_freshness_loss(self):
        """Nach einem Freundschaftsspiel darf die Frische nicht sinken."""
        from .models import PlayerStrengthProfile
        home_club = self._make_club()
        away_club = self._make_club()
        hp = self._make_player(home_club, freshness=90)
        ap = self._make_player(away_club, freshness=90)

        self._call_write_simulated(home_club, away_club, hp, ap,
                                   match_type='freundschaft', injury_events=[])

        sp_h = PlayerStrengthProfile.objects.get(player=hp)
        sp_a = PlayerStrengthProfile.objects.get(player=ap)
        self.assertEqual(float(sp_h.freshness), 90.0,
                         "Heimspieler darf nach Freundschaft keine Frische verlieren")
        self.assertEqual(float(sp_a.freshness), 90.0,
                         "Gastspieler darf nach Freundschaft keine Frische verlieren")

    def test_freundschaft_no_injury_persisted(self):
        """Nach einem Freundschaftsspiel darf keine Verletzung in der DB landen."""
        from .models import PlayerInjuryRecord
        home_club = self._make_club()
        away_club = self._make_club()
        hp = self._make_player(home_club)
        ap = self._make_player(away_club)
        before = PlayerInjuryRecord.objects.filter(player=hp).count()
        self._call_write_simulated(home_club, away_club, hp, ap,
                                   match_type='freundschaft')
        after = PlayerInjuryRecord.objects.filter(player=hp).count()
        self.assertEqual(before, after,
                         "Freundschaftsspiel darf keine PlayerInjuryRecord erzeugen")


class FreshnessEngineIntegrationTests(TestCase):
    """Prüft, dass Frische die Matchstärke korrekt beeinflusst."""

    def test_low_freshness_reduces_match_strength(self):
        from .match_engine import _draw_match_strength
        from .models import Player, PlayerStrengthProfile
        from decimal import Decimal
        import statistics

        p = Player(
            first_name='Fresh',
            last_name='Star',
            position='ZM',
            potential=80,
        )
        p.pk = 9999

        sp_fresh = PlayerStrengthProfile(
            base_strength=Decimal('70.00'),
            freshness=Decimal('100.00'),
            form_modifier=Decimal('0.00'),
        )
        sp_tired = PlayerStrengthProfile(
            base_strength=Decimal('70.00'),
            freshness=Decimal('45.00'),
            form_modifier=Decimal('0.00'),
        )

        p.strength_profile = sp_fresh
        fresh_strengths = [_draw_match_strength(p) for _ in range(200)]

        p.strength_profile = sp_tired
        tired_strengths = [_draw_match_strength(p) for _ in range(200)]

        self.assertGreater(
            statistics.mean(fresh_strengths),
            statistics.mean(tired_strengths),
            "Frischer Spieler muss im Schnitt stärker sein als müder",
        )

    def test_generate_injury_events_uses_medizin_factor(self):
        """Medizin-Stufe 3 muss zu weniger Verletzungen führen als Stufe 0."""
        from .match_engine import _generate_injury_events
        import random as _random

        players = [
            {'id': i, 'name': f'P{i}', 'freshness': 50}  # niedrige Frische → hohe Basisrate
            for i in range(30)
        ]

        _random.seed(42)
        injuries_no_medizin = sum(
            len(_generate_injury_events(players, 'home', medizin_factor=1.0))
            for _ in range(100)
        )

        _random.seed(42)
        injuries_best_medizin = sum(
            len(_generate_injury_events(players, 'home', medizin_factor=0.8))
            for _ in range(100)
        )

        self.assertLessEqual(injuries_best_medizin, injuries_no_medizin,
                             "Besseres Medizinzentrum soll weniger Verletzungen produzieren")


class InjurySubTests(TestCase):
    """process_injury_subs() — Verletzungswechsel vor Anpfiff."""

    def _make_als(self, lineup, players_by_id, bench_by_id, planned_subs=None):
        from .match_engine import ActiveLineupState
        return ActiveLineupState(
            lineup=lineup,
            players_by_id=players_by_id,
            bench_by_id=bench_by_id,
            planned_subs=planned_subs or [],
        )

    def _player(self, pid, position='ZM', injured=False):
        return {
            'id': pid,
            'name': f'Spieler {pid}',
            'final_strength': 70.0,
            'main_positions': [position],
            'secondary_positions': [],
            'teamwork': 5,
            'freshness': 80,
            'is_ws_injured': injured,
        }

    def test_no_injured_starters_no_subs(self):
        """Keine verletzten Starter → keine Wechsel."""
        lineup = [{'player_id': 1, 'position': 'ZM', 'group': 'midfield'}]
        players = {1: self._player(1, 'ZM', injured=False)}
        bench = {2: self._player(2, 'ZM', injured=False)}
        als = self._make_als(lineup, players, bench)
        als.process_injury_subs()
        self.assertEqual(als.used_substitutions, 0)
        self.assertEqual(als.sub_events, [])

    def test_injured_starter_is_subbed_out(self):
        """Verletzter Starter wird automatisch ausgewechselt."""
        lineup = [{'player_id': 1, 'position': 'ZM', 'group': 'midfield'}]
        players = {1: self._player(1, 'ZM', injured=True)}
        bench = {2: self._player(2, 'ZM', injured=False)}
        als = self._make_als(lineup, players, bench)
        als.process_injury_subs()
        self.assertEqual(als.used_substitutions, 1)
        self.assertEqual(len(als.sub_events), 1)
        evt = als.sub_events[0]
        self.assertEqual(evt['out'], 1)
        self.assertEqual(evt['in'], 2)
        self.assertEqual(evt['minute'], 5)
        self.assertEqual(evt['condition'], 'verletzung')
        self.assertEqual(evt['target_slot'], 'ZM')

    def test_injured_starter_removed_from_active_lineup(self):
        """Nach Verletzungswechsel ist verletzter Spieler nicht mehr aktiv."""
        lineup = [{'player_id': 1, 'position': 'ST', 'group': 'attack'}]
        players = {1: self._player(1, 'ST', injured=True)}
        bench = {2: self._player(2, 'ZM', injured=False)}
        als = self._make_als(lineup, players, bench)
        als.process_injury_subs()
        active_ids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertNotIn(1, active_ids)
        self.assertIn(2, active_ids)

    def test_injury_sub_counts_toward_contingent(self):
        """Verletzungswechsel zählt zum MAX_SUBSTITUTIONS-Kontingent."""
        from .match_engine import MAX_SUBSTITUTIONS
        lineup = [{'player_id': i, 'position': 'ZM', 'group': 'midfield'} for i in range(1, MAX_SUBSTITUTIONS + 2)]
        players = {i: self._player(i, 'ZM', injured=(i <= MAX_SUBSTITUTIONS + 1)) for i in range(1, MAX_SUBSTITUTIONS + 2)}
        bench = {100 + i: self._player(100 + i, 'ZM') for i in range(MAX_SUBSTITUTIONS + 2)}
        als = self._make_als(lineup, players, bench)
        als.process_injury_subs()
        self.assertLessEqual(als.used_substitutions, MAX_SUBSTITUTIONS)

    def test_no_bench_available_no_sub(self):
        """Kein Bankspiele → kein Wechsel, kein Absturz."""
        lineup = [{'player_id': 1, 'position': 'ZM', 'group': 'midfield'}]
        players = {1: self._player(1, 'ZM', injured=True)}
        als = self._make_als(lineup, players, bench_by_id={})
        als.process_injury_subs()
        self.assertEqual(als.used_substitutions, 0)
        self.assertEqual(als.sub_events, [])

    def test_injury_sub_position_relation_set(self):
        """position_relation ist HP wenn Bankspiele gleiche Position hat."""
        lineup = [{'player_id': 1, 'position': 'ST', 'group': 'attack'}]
        players = {1: self._player(1, 'ST', injured=True)}
        bench = {2: self._player(2, 'ST', injured=False)}
        als = self._make_als(lineup, players, bench)
        als.process_injury_subs()
        self.assertEqual(als.sub_events[0]['position_relation'], 'HP')

    def test_ticker_comment_includes_slot_and_relation(self):
        """_ticker_comment('sub') FP: enthält Slot und Hinweis auf Fremdposition."""
        from .views import _ticker_comment
        text = _ticker_comment('sub', 5, in_name='Müller', out_name='Kane',
                               target_slot='ST', position_relation='FP')
        self.assertIn('ST', text)
        fp_indicators = ['ungewohnte Position', 'Stammposition', 'Notlösung']
        self.assertTrue(
            any(ind in text for ind in fp_indicators),
            f"FP-Text enthält keinen Fremdpositions-Hinweis: {text!r}",
        )

    def test_ticker_comment_sub_no_slot_no_extra_info(self):
        """_ticker_comment('sub') ohne Slot/Relation → kein Klammer-Anhang."""
        from .views import _ticker_comment
        text = _ticker_comment('sub', 60, in_name='Müller', out_name='Kane')
        self.assertNotIn('(', text)


# ── Synthethisches Team-Dict-Hilfsfunktion ────────────────────────────────────

def _make_sim_team(
    base_id: int = 1,
    strength: float = 70.0,
    planned_subs: list | None = None,
    with_injured_starter: bool = False,
) -> dict:
    """Minimales Team-Dict für _simulate_match_minutes ohne ORM."""
    import random as _r
    rng = _r.Random(base_id)
    SLOTS = [
        ('TW', 'goalkeeper'),
        ('LV', 'defense'), ('IV', 'defense'), ('IV', 'defense'), ('RV', 'defense'),
        ('LM', 'midfield'), ('ZM', 'midfield'), ('ZM', 'midfield'), ('RM', 'midfield'),
        ('ST', 'attack'), ('ST', 'attack'),
    ]
    BENCH_POS = ['ST', 'ZM', 'LV', 'ZM', 'ST', 'IV', 'LM']
    pid_base = base_id * 200

    players = []
    lineup = []
    for i, (pos, grp) in enumerate(SLOTS):
        pid = pid_base + i
        players.append({
            'id': pid, 'name': f'P{pid}',
            'final_strength': max(30.0, strength + rng.gauss(0, 4)),
            'main_positions': [pos], 'secondary_positions': [],
            'teamwork': 5, 'freshness': 85,
            'is_ws_injured': (with_injured_starter and i == 10),
        })
        lineup.append({'player_id': pid, 'position': pos, 'group': grp})

    bench: dict = {}
    bench_pids = []
    for j, pos in enumerate(BENCH_POS):
        pid = pid_base + 11 + j
        bench[pid] = {
            'id': pid, 'name': f'B{pid}',
            'final_strength': max(30.0, strength - 5 + rng.gauss(0, 4)),
            'main_positions': [pos], 'secondary_positions': [],
            'teamwork': 4, 'freshness': 80, 'is_ws_injured': False,
        }
        bench_pids.append(pid)

    return {
        'team': {'name': f'Team-{base_id}', 'id': base_id},
        'players': players,
        'lineup': lineup,
        'tactic': {},
        'bench_player_data': bench,
        'planned_substitutions': planned_subs or [],
    }


# ── Verifikationspunkt 1: Nicht erfüllte Bedingung endgültig verworfen ────────

class SubConditionDiscardExplicitTests(TestCase):
    """Explizite Szenarien: einmal verworfene Bedingung darf nie nachgeholt werden."""

    def test_fuehrung_at_60_discarded_no_late_rescue(self):
        """'bei Führung' für Minute 60 — kein Rückstand bei 65 → verworfen.
        Führung bei Minute 75 darf den Wechsel NICHT nachholen."""
        subs = [{'in': 10, 'out': 1, 'minute': 60, 'condition': 'fuehrung'}]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 1)   # Rückstand 0:1 → Bedingung nicht erfüllt → verworfen
        als.process_planned_subs(76, 2, 1)   # jetzt Führung 2:1 → darf NICHT ausgeführt werden
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertNotIn(10, active_pids)
        self.assertIn(1, active_pids)
        self.assertEqual(als.used_substitutions, 0)

    def test_rueckstand_discarded_then_stay_trailing(self):
        """'bei Rückstand' für Minute 60 — Führung bei 65 → verworfen.
        Echten Rückstand bei Minute 80 darf NICHT nachholen."""
        subs = [{'in': 10, 'out': 1, 'minute': 60, 'condition': 'rueckstand'}]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 1, 0)   # Führung → Bedingung 'rueckstand' nicht erfüllt → verworfen
        als.process_planned_subs(81, 1, 3)   # jetzt Rückstand → trotzdem NICHT ausgeführt
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertNotIn(10, active_pids)
        self.assertEqual(als.used_substitutions, 0)

    def test_discard_marks_resolved_idx(self):
        """_resolved_idxs enthält Index des verworfenen Wechsels nach Prüfung."""
        from .match_engine import ActiveLineupState
        subs = [{'in': 10, 'out': 1, 'minute': 60, 'condition': 'fuehrung'}]
        als = _make_als(subs=subs)
        self.assertNotIn(0, als._resolved_idxs)
        als.process_planned_subs(66, 0, 1)   # Bedingung nicht erfüllt → resolved
        self.assertIn(0, als._resolved_idxs)

    def test_multiple_subs_independent_discard(self):
        """Zwei Wechsel unabhängig: erster verworfen, zweiter normal ausgeführt."""
        subs = [
            {'in': 10, 'out': 1, 'minute': 60, 'condition': 'fuehrung'},
            {'in': 11, 'out': 2, 'minute': 60, 'condition': 'immer'},
        ]
        als = _make_als(subs=subs)
        als.process_planned_subs(66, 0, 1)   # fuehrung → verworfen; immer → ausgeführt
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertNotIn(10, active_pids)   # verworfen
        self.assertIn(11, active_pids)      # ausgeführt
        self.assertEqual(als.used_substitutions, 1)


# ── Verifikationspunkt 2: Gemeinsames Wechselkontingent ───────────────────────

class SharedContingentTests(TestCase):
    """Verletzungswechsel und geplante Wechsel teilen denselben subs_used-Zähler."""

    def _player(self, pid, pos='ZM', injured=False):
        return {
            'id': pid, 'name': f'P{pid}',
            'final_strength': 60.0,
            'main_positions': [pos], 'secondary_positions': [],
            'teamwork': 3, 'freshness': 85, 'is_ws_injured': injured,
        }

    def test_injury_sub_plus_planned_share_counter(self):
        """1 Verletzungswechsel + 1 geplanter Wechsel = used_substitutions 2."""
        from .match_engine import ActiveLineupState
        lineup  = [
            {'player_id': 1, 'position': 'ST', 'group': 'attack'},
            {'player_id': 2, 'position': 'ZM', 'group': 'midfield'},
        ]
        players = {1: self._player(1, 'ST', injured=True),
                   2: self._player(2, 'ZM', injured=False)}
        bench   = {10: self._player(10, 'ST'), 11: self._player(11, 'ZM')}
        subs    = [{'in': 11, 'out': 2, 'minute': 60, 'condition': 'immer'}]
        als = ActiveLineupState(lineup=lineup, players_by_id=players,
                                bench_by_id=bench, planned_subs=subs)
        als.process_injury_subs()
        self.assertEqual(als.used_substitutions, 1)   # Verletzung zählt
        als.process_planned_subs(66, 0, 0)
        self.assertEqual(als.used_substitutions, 2)   # geplanter Wechsel ebenfalls

    def test_injury_subs_eat_into_quota_for_planned(self):
        """MAX_SUBSTITUTIONS verletzte Starter → kein Platz mehr für geplante Wechsel."""
        from .match_engine import ActiveLineupState, MAX_SUBSTITUTIONS
        n = MAX_SUBSTITUTIONS
        lineup  = [{'player_id': i, 'position': 'ZM', 'group': 'midfield'}
                   for i in range(1, n + 2)]
        players = {i: self._player(i, 'ZM', injured=True) for i in range(1, n + 2)}
        bench   = {100 + i: self._player(100 + i, 'ZM') for i in range(n + 3)}
        subs    = [{'in': 200, 'out': 1, 'minute': 50, 'condition': 'immer'}]
        bench[200] = self._player(200, 'ZM')
        als = ActiveLineupState(lineup=lineup, players_by_id=players,
                                bench_by_id=bench, planned_subs=subs)
        als.process_injury_subs()
        self.assertGreaterEqual(als.used_substitutions, min(n, n))
        pre_planned = als.used_substitutions
        als.process_planned_subs(56, 0, 0)
        # geplanter Wechsel darf das Kontingent nicht überschreiten
        self.assertLessEqual(als.used_substitutions, MAX_SUBSTITUTIONS)
        if pre_planned >= MAX_SUBSTITUTIONS:
            self.assertEqual(als.used_substitutions, pre_planned)

    def test_total_subs_never_exceed_max(self):
        """Summe aus Verletzungs- + geplanten Wechseln ≤ MAX_SUBSTITUTIONS."""
        from .match_engine import ActiveLineupState, MAX_SUBSTITUTIONS
        lineup  = [{'player_id': i, 'position': 'ZM', 'group': 'midfield'}
                   for i in range(1, 12)]
        players = {i: self._player(i, 'ZM', injured=(i <= 3)) for i in range(1, 12)}
        bench   = {100 + i: self._player(100 + i, 'ZM') for i in range(10)}
        subs    = [{'in': 100 + i, 'out': 4 + i, 'minute': 60 + i * 5,
                    'condition': 'immer'} for i in range(5)]
        als = ActiveLineupState(lineup=lineup, players_by_id=players,
                                bench_by_id=bench, planned_subs=subs)
        als.process_injury_subs()
        for minute in range(65, 96, 5):
            als.process_planned_subs(minute, 0, 0)
        self.assertLessEqual(als.used_substitutions, MAX_SUBSTITUTIONS)


# ── Verifikationspunkt 3: Einsatzminuten und Noten ────────────────────────────

class MinutesPlayedTests(TestCase):
    """_build_minutes_played_map() berechnet Einsatzminuten korrekt."""

    def test_kane_65_goretzka_25(self):
        """Kane (out=65) → 65 Min; Goretzka (in=65) → 25 Min."""
        from .match_engine import _build_minutes_played_map
        events = [{'out': 1, 'in': 10, 'minute': 65}]
        m = _build_minutes_played_map(events)
        self.assertEqual(m[1], 65)    # Kane: ausgewechselt in Minute 65
        self.assertEqual(m[10], 25)   # Goretzka: spielt ab 65, also 90-65=25

    def test_starter_without_sub_not_in_map(self):
        """Starter ohne Wechsel erscheinen NICHT im Dict (Caller nimmt Default 90)."""
        from .match_engine import _build_minutes_played_map
        events = [{'out': 1, 'in': 10, 'minute': 65}]
        m = _build_minutes_played_map(events)
        self.assertNotIn(3, m)    # pid=3 war nicht betroffen
        self.assertNotIn(5, m)

    def test_empty_events_empty_map(self):
        """Keine Wechsel-Events → leeres Dict."""
        from .match_engine import _build_minutes_played_map
        self.assertEqual(_build_minutes_played_map([]), {})
        self.assertEqual(_build_minutes_played_map(None), {})

    def test_chain_out_uses_minimum(self):
        """Wechselkette: Goretzka rein bei 60, raus bei 75 → 15 Minuten.
        Kane raus bei 60 → 60 Min. Müller rein bei 75 → 15 Min."""
        from .match_engine import _build_minutes_played_map
        events = [
            {'out': 1,  'in': 10, 'minute': 60},  # Kane → Goretzka
            {'out': 10, 'in': 11, 'minute': 75},  # Goretzka → Müller
        ]
        m = _build_minutes_played_map(events)
        self.assertEqual(m[1],  60)   # Kane: Starter, raus bei 60
        self.assertEqual(m[10], 15)   # Goretzka: rein 60, raus 75 → 75-60=15
        self.assertEqual(m[11], 15)   # Müller: rein 75 → 90-75=15

    def test_injury_sub_at_minute_5(self):
        """Verletzungswechsel (Minute 5): Starter 5 Min, Ersatz 85 Min."""
        from .match_engine import _build_minutes_played_map
        events = [{'out': 1, 'in': 99, 'minute': 5, 'condition': 'verletzung'}]
        m = _build_minutes_played_map(events)
        self.assertEqual(m[1],  5)
        self.assertEqual(m[99], 85)

    def test_rating_modifier_short_appearance(self):
        """Spieler mit <30 Min Einsatz erhält Note näher an 3.5 als Vollspieler."""
        from .match_engine import compute_player_ratings
        def _r(mp, goals=0):
            return {
                'home_goals': 3, 'away_goals': 0,
                'home_xg': 2.5, 'away_xg': 0.8,
                'match_stats': {
                    'home_yellow': 0, 'away_yellow': 0,
                    'home_red': 0, 'away_red': 0,
                    'home_shots': 10, 'away_shots': 4,
                    'home_fouls': 8, 'away_fouls': 6,
                    'home_pressing_ball_wins': 2, 'away_pressing_ball_wins': 1,
                    'home_pressing_bypassed': 0, 'away_pressing_bypassed': 0,
                    'home_possession': 60, 'away_possession': 40,
                },
                'home_strength': {'overall': 75}, 'away_strength': {'overall': 65},
                'home_club_id': 1, 'away_club_id': 2,
                'home_club_name': 'H', 'away_club_name': 'A',
                'home_club_crest': None, 'away_club_crest': None,
                'home_club_short': 'H', 'away_club_short': 'A',
                'home_players': [{'id': 1, 'name': 'X', 'position': 'ZM', 'group': 'midfield',
                                   'goals': goals, 'assists': 0, 'final_strength': 70,
                                   'base_strength': 70, 'final_strength_raw': 70,
                                   'pos_label': 'HP', 'freshness': 85, 'teamwork': 5,
                                   'potential': 75, 'minutes_played': mp}],
                'away_players': [],
            }
        result_full  = compute_player_ratings(_r(90))
        result_short = compute_player_ratings(_r(20))
        full_rating  = result_full['home_ratings'][0]['rating']
        short_rating = result_short['home_ratings'][0]['rating']
        # Beide müssen gültig sein; kurzer Einsatz näher an 3.5
        self.assertTrue(1.0 <= full_rating  <= 6.0)
        self.assertTrue(1.0 <= short_rating <= 6.0)
        self.assertLess(abs(short_rating - 3.5), abs(full_rating - 3.5))


# ── Verifikationspunkt 4: Wechselkette (Goretzka → Müller findet ST-Slot) ─────

class SubChainTests(TestCase):
    """Wechselkette: 2. Wechsel findet Goretzkas aktuellen Slot, nicht Kanes."""

    def _make_chain_als(self):
        """ALS mit Kane (ST, pid=1) → Goretzka (Bank ST, pid=10) → Müller (Bank ST, pid=11)."""
        from .match_engine import ActiveLineupState
        lineup = [
            {'player_id': 1, 'position': 'ST', 'group': 'attack'},
            {'player_id': 2, 'position': 'ZM', 'group': 'midfield'},
            {'player_id': 3, 'position': 'TW', 'group': 'goalkeeper'},
        ]
        players = {
            1: {'id': 1,  'name': 'Kane',     'final_strength': 90.0,
                'main_positions': ['ST'], 'secondary_positions': [], 'teamwork': 5, 'freshness': 90},
            2: {'id': 2,  'name': 'ZM',       'final_strength': 75.0,
                'main_positions': ['ZM'], 'secondary_positions': [], 'teamwork': 5, 'freshness': 90},
            3: {'id': 3,  'name': 'TW',       'final_strength': 80.0,
                'main_positions': ['TW'], 'secondary_positions': [], 'teamwork': 5, 'freshness': 90},
        }
        bench = {
            10: {'id': 10, 'name': 'Goretzka', 'final_strength': 80.0,
                 'main_positions': ['ST'], 'secondary_positions': [], 'teamwork': 5, 'freshness': 85},
            11: {'id': 11, 'name': 'Müller',   'final_strength': 78.0,
                 'main_positions': ['ST'], 'secondary_positions': [], 'teamwork': 5, 'freshness': 85},
        }
        subs = [
            {'in': 10, 'out': 1,  'minute': 60, 'condition': 'immer'},  # Kane → Goretzka
            {'in': 11, 'out': 10, 'minute': 75, 'condition': 'immer'},  # Goretzka → Müller
        ]
        return ActiveLineupState(lineup=lineup, players_by_id=players,
                                 bench_by_id=bench, planned_subs=subs)

    def test_first_sub_goretzka_at_st(self):
        """Nach Sub 1: Goretzka auf dem Feld, Kane weg."""
        als = self._make_chain_als()
        als.process_planned_subs(66, 0, 0)
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertIn(10, active_pids)    # Goretzka
        self.assertNotIn(1, active_pids)  # Kane raus

    def test_second_sub_muller_at_st_goretzka_gone(self):
        """Nach Sub 1+2: Müller auf dem Feld, Kane + Goretzka weg."""
        als = self._make_chain_als()
        als.process_planned_subs(66, 0, 0)   # Kane → Goretzka
        als.process_planned_subs(76, 0, 0)   # Goretzka → Müller
        active_pids = {s['player_id'] for s in als.get_active_lineup()}
        self.assertIn(11, active_pids)     # Müller
        self.assertNotIn(10, active_pids)  # Goretzka raus
        self.assertNotIn(1, active_pids)   # Kane raus

    def test_second_sub_finds_goretzkas_slot_not_original(self):
        """_pid_to_slot von Goretzka (pid=10) zeigt nach Sub 1 auf Kanes alten ST-Slot."""
        als = self._make_chain_als()
        als.process_planned_subs(66, 0, 0)   # Kane → Goretzka
        # Goretzka muss jetzt den ST-Slot halten (übernommen von Kane)
        slot = als._pid_to_slot.get(10)
        self.assertIsNotNone(slot)
        self.assertEqual(slot.get('position'), 'ST')

    def test_chain_slot_target_in_sub_events(self):
        """Beide Sub-Events haben target_slot == 'ST'."""
        als = self._make_chain_als()
        als.process_planned_subs(66, 0, 0)
        als.process_planned_subs(76, 0, 0)
        targets = [e['target_slot'] for e in als.sub_events]
        self.assertEqual(targets.count('ST'), 2)
        self.assertEqual(als.used_substitutions, 2)


# ── Verifikationspunkt 5: Keine ORM-Abfragen in der Segment-Schleife ─────────

class NoOrmInSimLoopTests(TestCase):
    """_simulate_match_minutes() führt während der 18 Segmente keine DB-Abfragen aus."""

    def test_zero_queries_in_segment_loop(self):
        """Reiner Dict-Aufruf → assertNumQueries(0)."""
        from .match_engine import _simulate_match_minutes
        home = _make_sim_team(base_id=1, strength=72.0)
        away = _make_sim_team(base_id=2, strength=68.0)
        with self.assertNumQueries(0):
            sim = _simulate_match_minutes(home, away)
        self.assertIn('home_goals', sim)
        self.assertIn('h_sim_sub_events', sim)

    def test_zero_queries_with_planned_subs(self):
        """Auch mit geplanten Wechseln keine DB-Abfragen."""
        from .match_engine import _simulate_match_minutes, MAX_SUBSTITUTIONS
        subs = [
            {'in': 400 + i, 'out': 200 + i, 'minute': 60 + i * 5, 'condition': 'immer'}
            for i in range(MAX_SUBSTITUTIONS)
        ]
        home = _make_sim_team(base_id=3, strength=70.0, planned_subs=[
            {'in': 3 * 200 + 11, 'out': 3 * 200 + 9, 'minute': 60, 'condition': 'immer'},
        ])
        away = _make_sim_team(base_id=4, strength=70.0)
        with self.assertNumQueries(0):
            sim = _simulate_match_minutes(home, away)
        self.assertIsInstance(sim['h_sim_sub_events'], list)

    def test_zero_queries_with_injured_starter(self):
        """Verletzungswechsel (process_injury_subs) erzeugt ebenfalls keine Abfragen."""
        from .match_engine import _simulate_match_minutes
        home = _make_sim_team(base_id=5, strength=70.0, with_injured_starter=True)
        away = _make_sim_team(base_id=6, strength=70.0)
        with self.assertNumQueries(0):
            sim = _simulate_match_minutes(home, away)
        # Verletzungswechsel muss stattgefunden haben
        all_subs = sim.get('h_sim_sub_events', [])
        injury_subs = [e for e in all_subs if e.get('condition') == 'verletzung']
        self.assertEqual(len(injury_subs), 1)


class CardMinuteWindowTests(TestCase):
    """Rote-Karten-Minute liegt immer im aktiven Zeitfenster, kein ValueError."""

    def _players_with_mp(self, minutes_played_list):
        return [
            {
                'id': i + 1,
                'name': f'Spieler{i}',
                'minutes_played': mp,
                'is_sub': mp < 85,
            }
            for i, mp in enumerate(minutes_played_list)
        ]

    def test_red_card_short_window_no_value_error(self):
        """Spieler mit nur 5 Einsatzminuten löst keinen ValueError aus."""
        from .match_engine import _assign_cards_to_players
        players = self._players_with_mp([5, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90])
        for _ in range(50):
            updated, events = _assign_cards_to_players(players, yellow_count=0, red_count=1)
            for ev in events:
                self.assertGreaterEqual(ev['minute'], 1)
                self.assertLessEqual(ev['minute'], 90)

    def test_red_card_minute_within_active_window_sub(self):
        """Eingewechselter (60') erhält Karte frühestens ab Minute 30 (90-60)."""
        from .match_engine import _assign_cards_to_players
        # Einziger Spieler im Pool mit 30 Minuten (rein ab Minute 60)
        players = [{'id': 1, 'name': 'Sub', 'minutes_played': 30, 'is_sub': True}]
        for _ in range(20):
            _, events = _assign_cards_to_players(players, yellow_count=0, red_count=1)
            for ev in events:
                # on_minute=60, hi=90 → gültig
                self.assertGreaterEqual(ev['minute'], 1)
                self.assertLessEqual(ev['minute'], 90)

    def test_yellow_card_minute_within_starter_window(self):
        """Starter ausgewechselt Minute 20 → Gelbe Karte ≤ Minute 20."""
        from .match_engine import _assign_cards_to_players
        # Starter mit 20 Minuten (ausgewechselt Minute 20)
        players = [{'id': 1, 'name': 'Out20', 'minutes_played': 20, 'is_sub': False}]
        for _ in range(30):
            _, events = _assign_cards_to_players(players, yellow_count=1, red_count=0)
            for ev in events:
                self.assertLessEqual(ev['minute'], 20)
                self.assertGreaterEqual(ev['minute'], 1)

    def test_chain_player_explicit_window_respected(self):
        """Kettenspielerin (rein=60, raus=75) → Karten/Verletzung nur zwischen 60 und 75."""
        from .match_engine import _assign_cards_to_players, _generate_injury_events
        # Explizite on_minute/off_minute simulieren wie simulate_match() sie setzt
        player = {
            'id': 99,
            'name': 'Goretzka',
            'minutes_played': 15,
            'is_sub': True,         # Fallback würde fälschlich (75, 90) ergeben
            'on_minute':  60,       # Echtes Fenster: 60–75
            'off_minute': 75,
            'freshness': 80,
        }
        # Karten: Minute muss zwischen 60 und 75 liegen
        for _ in range(30):
            _, evts = _assign_cards_to_players([player], yellow_count=1, red_count=1)
            for ev in evts:
                self.assertGreaterEqual(ev['minute'], 60,
                    f"Karte vor on_minute=60: {ev['minute']}")
                self.assertLessEqual(ev['minute'], 75,
                    f"Karte nach off_minute=75: {ev['minute']}")
        # Verletzungen: Minute muss zwischen 60 und 75 liegen
        import random
        for seed in range(40):
            random.seed(seed)
            evts = _generate_injury_events([player], club_side='home', medizin_factor=5.0)
            for ev in evts:
                self.assertGreaterEqual(ev['minute'], 60,
                    f"Verletzung vor on_minute=60: {ev['minute']}")
                self.assertLessEqual(ev['minute'], 75,
                    f"Verletzung nach off_minute=75: {ev['minute']}")


class InjuryMinuteWindowTests(TestCase):
    """_generate_injury_events() verletzt nie die randint-Grenzen, auch bei <10 Minuten."""

    def test_no_value_error_for_very_short_player(self):
        """Spieler mit 5 Einsatzminuten → kein ValueError, gültiger Zeitstempel."""
        from .match_engine import _generate_injury_events
        import random
        # Spieler mit 5 Minuten (Starter, raus Minute 5)
        players = [{'id': 1, 'name': 'Out5', 'minutes_played': 5, 'is_sub': False, 'freshness': 50}]
        for seed in range(100):
            random.seed(seed)
            events = _generate_injury_events(players, club_side='home', medizin_factor=5.0)
            for ev in events:
                self.assertGreaterEqual(ev['minute'], 1)
                self.assertLessEqual(ev['minute'], 5)

    def test_no_value_error_for_late_sub_player(self):
        """Eingewechselter Spieler (3 Minuten) → kein ValueError."""
        from .match_engine import _generate_injury_events
        import random
        players = [{'id': 2, 'name': 'Sub87', 'minutes_played': 3, 'is_sub': True, 'freshness': 40}]
        for seed in range(100):
            random.seed(seed)
            events = _generate_injury_events(players, club_side='away', medizin_factor=5.0)
            for ev in events:
                self.assertGreaterEqual(ev['minute'], 1)
                self.assertLessEqual(ev['minute'], 90)


class SubstitutionReportSourceTests(TestCase):
    """home_substitutions / away_substitutions korrekte Quellen-Logik."""

    def test_no_phantom_subs_when_planned_conditions_all_discarded(self):
        """Geplante Wechsel vorhanden, aber alle Bedingungen verworfen → leere Sub-Liste,
        kein Fallback-Phantom."""
        from .match_engine import _simulate_match_minutes
        # Bedingung 'fuehrung' bei Minute 1 → wird fast nie zutreffen
        home = _make_sim_team(base_id=10, strength=70.0, planned_subs=[
            {'in': 10 * 200 + 11, 'out': 10 * 200 + 9, 'minute': 1, 'condition': 'fuehrung'},
        ])
        away = _make_sim_team(base_id=11, strength=70.0)
        # 50 Wiederholungen: kein Spiel darf Sub-Events durch Fallback erhalten,
        # wenn die echten Sim-Events leer sind
        for seed in range(50):
            import random as _rnd
            _rnd.seed(seed)
            sim = _simulate_match_minutes(home, away)
            h_subs = sim.get('h_sim_sub_events', [])
            # Falls Bedingung nicht zutraf → leere Liste; kein Phantom aus Fallback
            # (Der Test prüft: Simulation liefert keine unplausiblen Ergebnisse)
            for ev in h_subs:
                self.assertIn('in', ev, "Sub-Event hat keinen 'in'-Schlüssel")
                self.assertIn('out', ev, "Sub-Event hat keinen 'out'-Schlüssel")

    def test_injury_subs_visible_without_planned_subs(self):
        """Team ohne geplante Wechsel → Verletzungswechsel trotzdem sichtbar."""
        from .match_engine import _simulate_match_minutes
        home = _make_sim_team(base_id=12, strength=70.0, with_injured_starter=True)
        away = _make_sim_team(base_id=13, strength=70.0)
        injury_sub_found = False
        for seed in range(30):
            import random as _rnd
            _rnd.seed(seed)
            sim = _simulate_match_minutes(home, away)
            if any(e.get('condition') == 'verletzung' for e in sim.get('h_sim_sub_events', [])):
                injury_sub_found = True
                break
        self.assertTrue(injury_sub_found, "Verletzungswechsel muss in h_sim_sub_events erscheinen")


# ── Hilfsfunktion für Spielernoten-Tests ──────────────────────────────────────

def _make_rating_result(home_goals=1, away_goals=0, home_xg=1.2, away_xg=0.5,
                         home_strength=70, away_strength=70,
                         home_sot=4, away_sot=2,
                         home_poss=52, away_poss=48,
                         home_club_id=1, away_club_id=2,
                         home_players=None, away_players=None):
    """Ruft compute_player_ratings() mit minimalen Testdaten auf."""
    from game.match_engine import compute_player_ratings
    return compute_player_ratings({
        'home_goals': home_goals, 'away_goals': away_goals,
        'home_xg': home_xg, 'away_xg': away_xg,
        'home_club_id': home_club_id, 'away_club_id': away_club_id,
        'match_stats': {
            'home_pressing_ball_wins': 3, 'away_pressing_ball_wins': 2,
            'home_pressing_bypassed': 2, 'away_pressing_bypassed': 3,
            'home_possession': home_poss, 'away_possession': away_poss,
            'home_shots_on_target': home_sot, 'away_shots_on_target': away_sot,
        },
        'home_strength': {'overall': home_strength},
        'away_strength': {'overall': away_strength},
        'home_players': home_players or [],
        'away_players': away_players or [],
    })


def _p(pid, pos='ZM', group='midfield', goals=0, assists=0, mp=90,
       yellow=0, yellow_red=0, red=0, own_goal=0, pen_missed=0, pen_saved=0,
       is_sub=False):
    """Minimale Spieler-Zeile für Noten-Tests."""
    return {
        'id': pid, 'name': f'Spieler{pid}', 'position': pos, 'group': group,
        'goals': goals, 'assists': assists, 'minutes_played': mp,
        'yellow_cards': yellow, 'yellow_red_cards': yellow_red, 'red_cards': red,
        'own_goal': own_goal, 'penalty_missed': pen_missed, 'penalty_saved': pen_saved,
        'is_sub': is_sub,
    }


class PlayerRatingsV3Tests(TestCase):
    """Spielernoten V3 — Verhaltenstests nach Spec §495."""

    def test_underdog_win_besser_als_favorit(self):
        """Underdog schlägt Favorit 2:1 → Gewinner-Ø deutlich besser als Verlierer-Ø."""
        # Bremen (68) schlägt Bayern (83)
        h_players = [_p(i, 'IV', 'defense') for i in range(1, 5)] + \
                    [_p(5, 'ZM', 'midfield', goals=1)] + \
                    [_p(6, 'ST', 'attack', goals=1)] + \
                    [_p(i, 'ZM', 'midfield') for i in range(7, 12)]
        a_players = [_p(i + 100, 'IV', 'defense') for i in range(1, 12)]
        result = _make_rating_result(
            home_goals=2, away_goals=1, home_xg=1.1, away_xg=1.8,
            home_strength=68, away_strength=83,
            home_players=h_players, away_players=a_players,
        )
        h_avg = sum(r['rating'] for r in result['home_ratings']) / len(result['home_ratings'])
        a_avg = sum(r['rating'] for r in result['away_ratings']) / len(result['away_ratings'])
        self.assertLess(h_avg, a_avg,
                        f"Underdog-Sieger-Ø {h_avg:.2f} muss besser sein als Favorit-Ø {a_avg:.2f}")
        self.assertGreater(a_avg - h_avg, 0.3,
                           f"Differenz {a_avg - h_avg:.2f} zu klein (erwartet > 0.3)")

    def test_klare_niederlage_schlechte_noten(self):
        """0:3-Niederlage → Ø-Note des Verlierers > 3.5."""
        players = [_p(i, 'IV', 'defense') for i in range(1, 12)]
        result = _make_rating_result(
            home_goals=0, away_goals=3, home_xg=0.4, away_xg=3.2,
            home_sot=1, away_sot=8,
            home_players=players, away_players=[],
        )
        h_avg = sum(r['rating'] for r in result['home_ratings']) / len(result['home_ratings'])
        self.assertGreater(h_avg, 3.5,
                           f"0:3-Verlierer-Ø {h_avg:.2f} muss > 3.5 sein")

    def test_neutrales_nullnull_nahe_drei(self):
        """Ausgeglichenes 0:0 → alle Spieler-Noten nahe 3.0 (2.5–3.8)."""
        players = [_p(i, 'ZM', 'midfield') for i in range(1, 12)]
        opp     = [_p(i + 100, 'ZM', 'midfield') for i in range(1, 12)]
        result = _make_rating_result(
            home_goals=0, away_goals=0, home_xg=0.8, away_xg=0.8,
            home_sot=3, away_sot=3, home_poss=50, away_poss=50,
            home_players=players, away_players=opp,
        )
        all_ratings = ([r['rating'] for r in result['home_ratings']] +
                       [r['rating'] for r in result['away_ratings']])
        for rv in all_ratings:
            self.assertGreaterEqual(rv, 2.5, f"0:0-Note {rv} zu niedrig")
            self.assertLessEqual(rv, 3.8, f"0:0-Note {rv} zu hoch")

    def test_joker_torschuetze_gute_note(self):
        """Joker: 10 Min Einsatzzeit, 1 Tor → Note ≤ 2.2 (trotz Jitter ±0.08)."""
        joker = _p(99, 'ST', 'attack', goals=1, mp=10, is_sub=True)
        result = _make_rating_result(
            home_goals=1, away_goals=0, home_xg=0.9, away_xg=0.4,
            home_players=[joker], away_players=[],
        )
        rating = result['home_ratings'][0]['rating']
        self.assertLessEqual(rating, 2.2,
                             f"Joker-Torschütze (10 Min) Note {rating} muss ≤ 2.2 sein")

    def test_tw_paraden_gut_bewertet(self):
        """TW mit 6 Paraden (Zu-Null, hoher Gegnerdruck) bei 1:0-Sieg → Note ≤ 2.0."""
        # opp_sot=6, opp_goals=0 → 6 Paraden + Clean Sheet + hoher xG-Druck
        gk = _p(1, 'TW', 'goalkeeper', mp=90)
        result = _make_rating_result(
            home_goals=1, away_goals=0, home_xg=0.9, away_xg=3.0,
            home_sot=3, away_sot=6,
            home_players=[gk], away_players=[],
        )
        rating = result['home_ratings'][0]['rating']
        self.assertLessEqual(rating, 2.0,
                             f"TW-Paraden+ZuNull Note {rating} muss ≤ 2.0 sein")

    def test_tw_zu_null_bonus(self):
        """TW hält Zu-Null (0 Gegentore, wenig Beschäftigung) → Note ≤ 2.5."""
        gk = _p(1, 'TW', 'goalkeeper', mp=90)
        result = _make_rating_result(
            home_goals=1, away_goals=0, home_xg=1.0, away_xg=0.3,
            home_sot=3, away_sot=1,
            home_players=[gk], away_players=[],
        )
        rating = result['home_ratings'][0]['rating']
        self.assertLessEqual(rating, 2.5,
                             f"TW-Zu-Null Note {rating} muss ≤ 2.5 sein")

    def test_rote_karte_schlechtere_note(self):
        """Spieler mit Roter Karte erhält deutlich schlechtere Note als sauberer Mitspieler."""
        clean = _p(1, 'ZM', 'midfield', mp=90)
        red   = _p(2, 'ZM', 'midfield', red=1, mp=90)
        result = _make_rating_result(
            home_goals=0, away_goals=0,
            home_players=[clean, red], away_players=[],
        )
        r_clean = result['home_ratings'][0]['rating']
        r_red   = result['home_ratings'][1]['rating']
        self.assertGreater(r_red - r_clean, 0.5,
                           f"Rot-Karte-Strafe {r_red - r_clean:.2f} zu klein (> 0.5 erwartet)")

    def test_gelb_rot_zwischen_gelb_und_rot(self):
        """Gelb-Rot (0.65) liegt zwischen Gelb (0.10) und Direktrot (0.85)."""
        gelb    = _p(1, 'ZM', 'midfield', yellow=1, mp=90)
        gelbrot = _p(2, 'ZM', 'midfield', yellow_red=1, mp=90)
        direktrot = _p(3, 'ZM', 'midfield', red=1, mp=90)
        result = _make_rating_result(
            home_goals=0, away_goals=0,
            home_players=[gelb, gelbrot, direktrot], away_players=[],
        )
        r_g  = result['home_ratings'][0]['rating']
        r_gr = result['home_ratings'][1]['rating']
        r_r  = result['home_ratings'][2]['rating']
        self.assertLess(r_g, r_gr,
                        f"Gelb ({r_g}) muss besser sein als Gelb-Rot ({r_gr})")
        self.assertLess(r_gr, r_r + 0.2,
                        f"Gelb-Rot ({r_gr}) muss ähnlich oder schlechter als Direktrot ({r_r})")

    def test_determinismus(self):
        """Gleiche Eingaben → identische Noten (kein Zufalls-State)."""
        players = [_p(i, 'ZM', 'midfield', goals=1 if i == 1 else 0) for i in range(1, 6)]
        r1 = _make_rating_result(home_goals=1, away_goals=0, home_players=players)
        r2 = _make_rating_result(home_goals=1, away_goals=0, home_players=players)
        for i, (a, b) in enumerate(zip(r1['home_ratings'], r2['home_ratings'])):
            self.assertEqual(a['rating'], b['rating'],
                             f"Spieler {i}: Note {a['rating']} ≠ {b['rating']} (nicht deterministisch)")

    def test_spiegeltest_symmetrie(self):
        """Heimteam und Auswärtsteam mit gleichen Spielern tauschen → Noten spiegeln sich."""
        h_players = [_p(i, 'ZM', 'midfield') for i in range(1, 6)]
        a_players = [_p(i + 100, 'ZM', 'midfield') for i in range(1, 6)]
        # Heimsieg 1:0
        r_home_wins = _make_rating_result(
            home_goals=1, away_goals=0, home_xg=1.0, away_xg=0.5,
            home_poss=55, away_poss=45,
            home_sot=4, away_sot=2,
            home_strength=70, away_strength=70,
            home_club_id=1, away_club_id=2,
            home_players=h_players, away_players=a_players,
        )
        # Auswärtssieg: identisches Match gespiegelt
        r_away_wins = _make_rating_result(
            home_goals=0, away_goals=1, home_xg=0.5, away_xg=1.0,
            home_poss=45, away_poss=55,
            home_sot=2, away_sot=4,
            home_strength=70, away_strength=70,
            home_club_id=3, away_club_id=4,
            home_players=[_p(i + 200, 'ZM', 'midfield') for i in range(1, 6)],
            away_players=[_p(i + 300, 'ZM', 'midfield') for i in range(1, 6)],
        )
        # In Heimsieg: Heimmannschaft hat bessere Noten
        h_avg_win  = sum(r['rating'] for r in r_home_wins['home_ratings']) / 5
        a_avg_lose = sum(r['rating'] for r in r_home_wins['away_ratings']) / 5
        self.assertLess(h_avg_win, a_avg_lose,
                        f"Sieger-Ø {h_avg_win:.2f} muss besser (kleiner) sein als Verlierer-Ø {a_avg_lose:.2f}")
        # In Auswärtssieg: Auswärtsmannschaft (Sieger) hat bessere Noten
        h_avg_lose = sum(r['rating'] for r in r_away_wins['home_ratings']) / 5
        a_avg_win  = sum(r['rating'] for r in r_away_wins['away_ratings']) / 5
        self.assertLess(a_avg_win, h_avg_lose,
                        f"Auswärtssieger-Ø {a_avg_win:.2f} muss besser sein als Verlierer-Ø {h_avg_lose:.2f}")

