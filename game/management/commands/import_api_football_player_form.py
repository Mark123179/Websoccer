import json
import os
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from game.models import Player, PlayerFormSnapshot


API_BASE_URL = 'https://v3.football.api-sports.io'


class Command(BaseCommand):
    help = 'Import recent API-Football match form snapshots for one player.'

    def add_arguments(self, parser):
        parser.add_argument('--player-id', type=int, default=184)
        parser.add_argument('--team-id', type=int, default=157)
        parser.add_argument('--league-id', type=int, default=78)
        parser.add_argument('--season', type=int, default=self.default_season())
        parser.add_argument('--days', type=int, default=90)
        parser.add_argument('--from-date', dest='from_date')
        parser.add_argument('--to-date', dest='to_date')
        parser.add_argument('--limit-fixtures', type=int)
        parser.add_argument('--sleep-seconds', type=float, default=0)
        parser.add_argument(
            '--refresh-existing',
            action='store_true',
            help='Fetch fixture/player data even when a snapshot already exists.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch and summarize without storing snapshots.',
        )

    @staticmethod
    def default_season():
        today = date.today()
        return today.year if today.month >= 7 else today.year - 1

    def handle(self, *args, **options):
        self.load_dotenv()
        api_key = os.environ.get('API_FOOTBALL_KEY')

        if not api_key:
            raise CommandError(
                'API_FOOTBALL_KEY fehlt. Bitte in .env oder als Umgebungsvariable setzen.'
            )

        local_player = Player.objects.filter(
            api_football_id=options['player_id'],
        ).first()

        if not local_player:
            raise CommandError(
                'Kein lokaler Spieler mit dieser API-Football-ID gefunden.'
            )

        to_date = self.parse_date(options['to_date']) if options['to_date'] else date.today()
        from_date = (
            self.parse_date(options['from_date'])
            if options['from_date']
            else to_date - timedelta(days=options['days'])
        )

        fixtures = self.fetch_json(
            'fixtures',
            {
                'team': options['team_id'],
                'league': options['league_id'],
                'season': options['season'],
                'from': from_date.isoformat(),
                'to': to_date.isoformat(),
            },
            api_key,
        )
        fixtures = fixtures.get('response', [])

        if options['limit_fixtures']:
            fixtures = fixtures[:options['limit_fixtures']]

        saved_count = 0
        found_count = 0
        skipped_count = 0

        for fixture in fixtures:
            fixture_id = fixture['fixture']['id']

            if not options['refresh_existing'] and PlayerFormSnapshot.objects.filter(
                player=local_player,
                source=PlayerFormSnapshot.SOURCE_API_FOOTBALL,
                fixture_id=fixture_id,
            ).exists():
                skipped_count += 1
                continue

            try:
                player_stats = self.fetch_fixture_player(
                    fixture_id,
                    options['team_id'],
                    options['player_id'],
                    api_key,
                )
            except CommandError as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f'Import gestoppt: {exc}. '
                        'Bereits gespeicherte Snapshots bleiben erhalten.'
                    )
                )
                break

            if not player_stats:
                continue

            found_count += 1
            snapshot_data = self.build_snapshot_data(
                local_player,
                fixture,
                player_stats,
                options,
            )

            if options['dry_run']:
                self.stdout.write(
                    (
                        f"{snapshot_data['fixture_date']}: "
                        f"{local_player.full_name}, "
                        f"{snapshot_data['minutes_played']} Min., "
                        f"Rating {snapshot_data['rating'] or '-'}"
                    )
                )
                continue

            PlayerFormSnapshot.objects.update_or_create(
                player=local_player,
                source=PlayerFormSnapshot.SOURCE_API_FOOTBALL,
                fixture_id=str(fixture_id),
                defaults=snapshot_data,
            )
            saved_count += 1

            if options['sleep_seconds']:
                time.sleep(options['sleep_seconds'])

        if options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f'Dry-Run abgeschlossen: {found_count} Einsatz/Einsaetze '
                        f'gefunden, {skipped_count} vorhandene uebersprungen.'
                    )
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f'{saved_count} Form-Snapshot(s) gespeichert, '
                        f'{skipped_count} vorhandene uebersprungen.'
                    )
                )
            )

    def load_dotenv(self):
        env_path = Path(settings.BASE_DIR) / '.env'
        if not env_path.exists():
            return

        for line in env_path.read_text(encoding='utf-8').splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                continue

            key, value = stripped.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    def fetch_json(self, endpoint, params, api_key):
        url = f'{API_BASE_URL}/{endpoint}?{urlencode(params)}'
        request = Request(
            url,
            headers={
                'x-apisports-key': api_key,
                'Accept': 'application/json',
            },
        )

        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise CommandError(f'API-Football HTTP-Fehler: {exc.code}') from exc
        except URLError as exc:
            raise CommandError(f'API-Football Netzwerkfehler: {exc.reason}') from exc

        errors = payload.get('errors')
        if errors:
            raise CommandError(f'API-Football Fehler: {errors}')

        return payload

    def fetch_fixture_player(self, fixture_id, team_id, player_id, api_key):
        payload = self.fetch_json(
            'fixtures/players',
            {
                'fixture': fixture_id,
                'team': team_id,
            },
            api_key,
        )

        for team in payload.get('response', []):
            for player_entry in team.get('players', []):
                if player_entry.get('player', {}).get('id') == player_id:
                    return player_entry

        return None

    def build_snapshot_data(self, local_player, fixture, player_stats, options):
        statistics = (player_stats.get('statistics') or [{}])[0]
        games = statistics.get('games') or {}
        goals = statistics.get('goals') or {}
        cards = statistics.get('cards') or {}
        fixture_date = self.parse_date(fixture['fixture']['date'][:10])
        teams = fixture.get('teams') or {}
        home_team = (teams.get('home') or {}).get('name', '')
        away_team = (teams.get('away') or {}).get('name', '')
        team_name = home_team
        opponent_name = away_team

        if (teams.get('away') or {}).get('id') == options['team_id']:
            team_name = away_team
            opponent_name = home_team

        minutes = games.get('minutes') or 0
        substituted_in = bool(games.get('substitute'))

        return {
            'fixture_date': fixture_date,
            'league_api_football_id': options['league_id'],
            'team_api_football_id': options['team_id'],
            'team_name': team_name,
            'opponent_name': opponent_name,
            'minutes_played': minutes,
            'possible_minutes': 90,
            'started': minutes > 0 and not substituted_in,
            'substituted_in': substituted_in,
            'captain': bool(games.get('captain')),
            'position': games.get('position') or '',
            'rating': self.parse_decimal(games.get('rating')),
            'goals': goals.get('total') or 0,
            'assists': goals.get('assists') or 0,
            'yellow_cards': cards.get('yellow') or 0,
            'red_cards': cards.get('red') or 0,
            'raw_payload': player_stats,
        }

    def parse_date(self, value):
        return date.fromisoformat(value)

    def parse_decimal(self, value):
        if value in (None, ''):
            return None

        try:
            return Decimal(str(value)).quantize(Decimal('0.01'))
        except InvalidOperation:
            return None
