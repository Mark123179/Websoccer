from decimal import Decimal
from datetime import date
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .admin import PlayerNationalityForm
from .models import (
    Club,
    ClubNewsItem,
    ClubProfileMatch,
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
from .tactics import sanitize_assignments


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
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vereins&uuml;bersicht')
        self.assertContains(response, 'MatchEngine')
        self.assertContains(response, 'Letztes Spiel')
        self.assertContains(response, 'Borussia Dortmund')

    def test_club_list_renders_club_metrics(self):
        response = self.client.get(reverse('club_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Borussia Dortmund')
        self.assertContains(response, '1. Bundesliga')

    def test_club_detail_renders_public_profile(self):
        ClubProfileMatch.objects.create(
            club=self.club,
            kind=ClubProfileMatch.KIND_LAST,
            competition_name='1. Bundesliga',
            matchday_label='33. Spieltag',
            home_club=self.club,
            away_club=None,
            home_goals=1,
            away_goals=0,
            result_label=ClubProfileMatch.RESULT_WIN,
            scorers=[
                {
                    'clubId': str(self.club.id),
                    'playerName': 'Harry Kane',
                    'minute': 22,
                },
            ],
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
        self.assertContains(response, 'LETZTES SPIEL')
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
        self.assertContains(response, 'game/images/icons/stat-goals.svg')
        self.assertContains(response, 'Harry Kane')
        self.assertContains(response, 'club-player-cutout')
        self.assertContains(response, 'game/images/players/28049320')
        self.assertNotContains(response, 'game/images/player_composites/')
        self.assertContains(response, 'game/images/kits/907_home.svg')
        self.assertContains(response, 'game/images/flags/765.svg')
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
        option_ids = {
            option['id']
            for option in response.context['player_options']
        }
        self.assertNotIn(injured.id, option_ids)
        self.assertNotIn(suspended.id, option_ids)
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
        self.assertIn('@media (max-width: 1600px)', responsive_css)
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
        self.assertContains(response, 'game/images/trophies/podium-trophy.png')
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

    def test_recalculate_player_strengths_keeps_existing_base_without_sources(self):
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

        call_command('recalculate_player_strengths', stdout=output)
        player.refresh_from_db()
        profile = player.strength_profile
        snapshot = player.strength_snapshots.get(
            match_reference__startswith='RECALC-',
        )

        self.assertEqual(profile.base_strength, Decimal('76.00'))
        self.assertEqual(profile.final_strength, Decimal('77.50'))
        self.assertEqual(snapshot.base_strength, Decimal('76.00'))
        self.assertEqual(snapshot.final_strength, Decimal('77.50'))
        self.assertEqual(snapshot.max_strength, Decimal('82.00'))
        self.assertIn('Spieler berechnet', output.getvalue())

    def test_recalculate_player_strengths_uses_source_ratings_when_available(self):
        player = Player.objects.get(transfermarkt_id=132098)
        output = StringIO()

        call_command('recalculate_player_strengths', stdout=output)
        player.refresh_from_db()

        self.assertEqual(player.strength_profile.base_strength, Decimal('184.00'))
        self.assertEqual(player.strength_profile.final_strength, Decimal('186.00'))

