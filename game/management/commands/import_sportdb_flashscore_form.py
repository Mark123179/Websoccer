import json
import os
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from game.models import Player, PlayerFormSnapshot


API_BASE_URL = 'https://api.sportdb.dev'
DEFAULT_COMPETITION_PATH = '/api/flashscore/football/germany:81/bundesliga:W6BOzpK2'
DEFAULT_FLASHSCORE_PLAYER_ID = 'v5HSlEAa'
DEFAULT_TRANSFERMARKT_ID = 132098


class Command(BaseCommand):
    help = 'Import recent SportDB/Flashscore form snapshots for one player.'

    def add_arguments(self, parser):
        parser.add_argument('--flashscore-player-id', default=DEFAULT_FLASHSCORE_PLAYER_ID)
        parser.add_argument('--local-player-id', type=int)
        parser.add_argument('--transfermarkt-id', type=int, default=DEFAULT_TRANSFERMARKT_ID)
        parser.add_argument('--competition-path', default=DEFAULT_COMPETITION_PATH)
        parser.add_argument('--team-name', default='Bayern Munich')
        parser.add_argument('--season', default=self.default_season())
        parser.add_argument('--days', type=int, default=90)
        parser.add_argument('--from-date', dest='from_date')
        parser.add_argument('--to-date', dest='to_date')
        parser.add_argument('--max-pages', type=int, default=5)
        parser.add_argument('--limit-fixtures', type=int)
        parser.add_argument('--sleep-seconds', type=float, default=0)
        parser.add_argument('--request-sleep-seconds', type=float, default=0.5)
        parser.add_argument(
            '--include-playerstats',
            action='store_true',
            help='Fetch the large Flashscore playerstats payload in addition to lineups/details.',
        )
        parser.add_argument(
            '--refresh-existing',
            action='store_true',
            help='Fetch match details even when a snapshot already exists.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch and summarize without storing snapshots.',
        )

    @staticmethod
    def default_season():
        today = date.today()
        if today.month >= 7:
            return f'{today.year}-{today.year + 1}'

        return f'{today.year - 1}-{today.year}'

    def handle(self, *args, **options):
        self.load_dotenv()
        api_key = os.environ.get('SPORTDB_KEY')

        if not api_key:
            raise CommandError(
                'SPORTDB_KEY fehlt. Bitte in .env oder als Umgebungsvariable setzen.'
            )

        local_player = self.get_local_player(options)
        to_date = self.parse_date(options['to_date']) if options['to_date'] else date.today()
        from_date = (
            self.parse_date(options['from_date'])
            if options['from_date']
            else to_date - timedelta(days=options['days'])
        )

        fixtures = self.fetch_recent_fixtures(
            api_key=api_key,
            competition_path=options['competition_path'],
            season=options['season'],
            from_date=from_date,
            to_date=to_date,
            max_pages=options['max_pages'],
            team_name=options['team_name'],
        )

        if options['limit_fixtures']:
            fixtures = fixtures[:options['limit_fixtures']]

        saved_count = 0
        found_count = 0
        skipped_count = 0
        missing_count = 0

        for fixture in fixtures:
            fixture_id = str(fixture.get('eventId') or '')
            if not fixture_id:
                continue

            if not options['refresh_existing'] and PlayerFormSnapshot.objects.filter(
                player=local_player,
                source=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
                fixture_id=fixture_id,
            ).exists():
                skipped_count += 1
                continue

            lineups = self.fetch_optional_json(
                api_key,
                f'/api/flashscore/match/{fixture_id}/lineups',
                options['request_sleep_seconds'],
            )
            lineup_player, _side = self.find_lineup_player(
                lineups,
                options['flashscore_player_id'],
            )

            details = self.fetch_optional_json(
                api_key,
                f'/api/flashscore/match/{fixture_id}/details',
                options['request_sleep_seconds'],
            )
            playerstats = None
            if options['include_playerstats']:
                playerstats = self.fetch_optional_json(
                    api_key,
                    f'/api/flashscore/match/{fixture_id}/playerstats',
                    options['request_sleep_seconds'],
                )

            snapshot_data = self.build_snapshot_data(
                local_player=local_player,
                flashscore_player_id=options['flashscore_player_id'],
                fixture=fixture,
                lineups=lineups,
                details=details,
                playerstats=playerstats,
            )

            if not snapshot_data:
                missing_count += 1
                continue

            found_count += 1
            if options['dry_run']:
                self.stdout.write(
                    (
                        f"{snapshot_data['fixture_date']}: "
                        f"{local_player.full_name}, "
                        f"{snapshot_data['team_name']} vs. {snapshot_data['opponent_name']}, "
                        f"{snapshot_data['minutes_played']} Min., "
                        f"Rating {snapshot_data['rating'] or '-'}, "
                        f"T/A {snapshot_data['goals']}/{snapshot_data['assists']}"
                    )
                )
            else:
                PlayerFormSnapshot.objects.update_or_create(
                    player=local_player,
                    source=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
                    fixture_id=fixture_id,
                    defaults=snapshot_data,
                )
                saved_count += 1

            if options['sleep_seconds']:
                time.sleep(options['sleep_seconds'])

        message = (
            f'{found_count} Einsatz/Einsaetze gefunden, '
            f'{saved_count} gespeichert, '
            f'{skipped_count} vorhandene uebersprungen, '
            f'{missing_count} ohne Spielerdaten.'
        )
        self.stdout.write(self.style.SUCCESS(message))

    def get_local_player(self, options):
        if options['local_player_id']:
            player = Player.objects.filter(pk=options['local_player_id']).first()
        else:
            player = Player.objects.filter(
                transfermarkt_id=options['transfermarkt_id'],
            ).first()

        if not player:
            raise CommandError('Kein passender lokaler Spieler gefunden.')

        return player

    def fetch_recent_fixtures(
        self,
        api_key,
        competition_path,
        season,
        from_date,
        to_date,
        max_pages,
        team_name,
    ):
        fixtures = []
        seen_fixture_ids = set()
        normalized_path = competition_path.rstrip('/')
        normalized_team_name = str(team_name or '').strip().lower()

        for page in range(1, max_pages + 1):
            path = f'{normalized_path}/{season}/results?{urlencode({"page": page})}'
            page_fixtures = self.fetch_json(api_key, path)

            if not isinstance(page_fixtures, list) or not page_fixtures:
                break

            for fixture in page_fixtures:
                fixture_id = str(fixture.get('eventId') or '')
                if not fixture_id or fixture_id in seen_fixture_ids:
                    continue

                fixture_date = self.fixture_date(fixture)
                if not fixture_date:
                    continue

                if normalized_team_name and normalized_team_name not in {
                    str(fixture.get('homeName') or '').strip().lower(),
                    str(fixture.get('awayName') or '').strip().lower(),
                }:
                    continue

                if from_date <= fixture_date <= to_date:
                    fixtures.append(fixture)
                    seen_fixture_ids.add(fixture_id)
                elif fixture_date < from_date:
                    return fixtures

        return fixtures

    def build_snapshot_data(
        self,
        local_player,
        flashscore_player_id,
        fixture,
        lineups,
        details,
        playerstats,
    ):
        lineup_player, side = self.find_lineup_player(lineups, flashscore_player_id)
        stats_player = self.find_playerstats_player(playerstats, flashscore_player_id)

        fixture_date = self.fixture_date(fixture)
        events = self.extract_player_events(details, flashscore_player_id, local_player.full_name)

        if not lineup_player and not stats_player and not events['raw_events']:
            return None

        side = side or events['side']
        team_name, opponent_name = self.team_names(fixture, side, stats_player)
        started = self.is_started(lineup_player, stats_player)
        substituted_in_minute = events['substituted_in_minute']
        substituted_out_minute = events['substituted_out_minute']
        substituted_in = not started and substituted_in_minute is not None
        minutes_played = self.calculate_minutes(
            started=started,
            substituted_in_minute=substituted_in_minute,
            substituted_out_minute=substituted_out_minute,
        )
        rating = self.player_rating(lineup_player, stats_player)
        position = self.player_position(lineup_player, stats_player)
        captain = self.is_captain(lineup_player)

        return {
            'fixture_date': fixture_date,
            'league_api_football_id': None,
            'team_api_football_id': None,
            'team_name': team_name,
            'opponent_name': opponent_name,
            'minutes_played': minutes_played,
            'possible_minutes': 90,
            'started': started,
            'substituted_in': substituted_in,
            'captain': captain,
            'position': position,
            'rating': rating,
            'goals': events['goals'],
            'assists': events['assists'],
            'yellow_cards': events['yellow_cards'],
            'red_cards': events['red_cards'],
            'raw_payload': {
                'fixture': fixture,
                'lineup_player': lineup_player or {},
                'stats_player': stats_player or {},
                'events': events['raw_events'],
            },
        }

    def find_lineup_player(self, lineups, flashscore_player_id):
        if not isinstance(lineups, list):
            return None, ''

        for lineup_block in lineups:
            for side in ('home', 'away'):
                for player in lineup_block.get(side) or []:
                    if self.matches_flashscore_player(player, flashscore_player_id):
                        return player, side

        return None, ''

    def find_playerstats_player(self, payload, flashscore_player_id):
        if not payload:
            return None

        for item in self.walk_payload(payload):
            if not isinstance(item, dict):
                continue

            link = str(item.get('link') or '')
            player_id = str(item.get('id') or item.get('playerId') or '')
            if (
                player_id == flashscore_player_id
                or link.endswith(f'/{flashscore_player_id}')
                or f'/{flashscore_player_id}' in link
            ):
                return item

        return None

    def matches_flashscore_player(self, player, flashscore_player_id):
        participant_id = str(player.get('participantId') or '')
        participant_url = str(player.get('participantUrl') or '')
        return (
            participant_id == flashscore_player_id
            or participant_url.rstrip('/').endswith(f'/{flashscore_player_id}')
        )

    def extract_player_events(self, details, flashscore_player_id, full_name):
        result = {
            'goals': 0,
            'assists': 0,
            'yellow_cards': 0,
            'red_cards': 0,
            'substituted_in_minute': None,
            'substituted_out_minute': None,
            'side': '',
            'raw_events': [],
        }

        if not isinstance(details, dict):
            return result

        player_name_tokens = {
            token.lower()
            for token in full_name.replace('-', ' ').split()
            if len(token) > 2
        }

        for event in details.get('events') or []:
            player_ids = self.as_list(event.get('incidentPlayerId'))
            player_names = self.as_list(event.get('incidentPlayerName'))
            type_names = self.as_list(event.get('incidentTypeName'))

            if not self.event_mentions_player(
                player_ids,
                player_names,
                flashscore_player_id,
                player_name_tokens,
            ):
                continue

            result['raw_events'].append(event)
            result['side'] = result['side'] or self.event_side(event)
            minute = self.parse_minute(event.get('incidentTime'))

            for index, type_name in enumerate(type_names):
                normalized_type = str(type_name).lower()
                matching_player_id = str(player_ids[index]) if index < len(player_ids) else ''

                if matching_player_id and matching_player_id != flashscore_player_id:
                    continue

                if 'goal' in normalized_type and 'own' not in normalized_type:
                    result['goals'] += 1
                elif 'assist' in normalized_type:
                    result['assists'] += 1
                elif 'yellow' in normalized_type:
                    result['yellow_cards'] += 1
                elif 'red' in normalized_type:
                    result['red_cards'] += 1
                elif 'substitution - in' in normalized_type:
                    result['substituted_in_minute'] = minute
                elif 'substitution - out' in normalized_type:
                    result['substituted_out_minute'] = minute

        return result

    def event_side(self, event):
        side = str(event.get('incidentSide') or '')
        if side == '1':
            return 'home'
        if side == '2':
            return 'away'

        return ''

    def event_mentions_player(
        self,
        player_ids,
        player_names,
        flashscore_player_id,
        player_name_tokens,
    ):
        if flashscore_player_id in {str(player_id) for player_id in player_ids}:
            return True

        normalized_names = ' '.join(str(name).lower() for name in player_names)
        return bool(player_name_tokens and all(token in normalized_names for token in player_name_tokens))

    def calculate_minutes(
        self,
        started,
        substituted_in_minute,
        substituted_out_minute,
    ):
        if started:
            return substituted_out_minute or 90

        if substituted_in_minute is not None:
            return max(0, 90 - substituted_in_minute)

        return 0

    def is_started(self, lineup_player, stats_player):
        if lineup_player:
            if str(lineup_player.get('lineupIncident') or '') == '7':
                return False

            return str(lineup_player.get('playerType') or '') == '1'

        if stats_player:
            return bool(stats_player.get('inBaseLineup'))

        return False

    def is_captain(self, lineup_player):
        if not lineup_player:
            return False

        return str(lineup_player.get('participantSpecialPositionName') or '').lower() == 'captain'

    def player_rating(self, lineup_player, stats_player):
        if lineup_player:
            rating = self.parse_decimal(lineup_player.get('participantRating'))
            if rating is not None:
                return rating

        if stats_player:
            raw_rating = stats_player.get('rating') or {}
            if isinstance(raw_rating, dict):
                return self.parse_decimal(
                    raw_rating.get('numericValue') or raw_rating.get('value')
                )

        return None

    def player_position(self, lineup_player, stats_player):
        if stats_player:
            position = stats_player.get('position') or {}
            if isinstance(position, dict):
                mapped = self.map_position(position.get('name'))
                if mapped:
                    return mapped

        if lineup_player:
            key = str(lineup_player.get('positionKey') or '')
            return {
                '1': 'TW',
                '2': 'LV',
                '3': 'IV',
                '4': 'IV',
                '5': 'RV',
                '6': 'DM',
                '7': 'ZM',
                '8': 'LM',
                '9': 'RM',
                '10': 'OM',
                '11': 'ST',
            }.get(key, '')

        return ''

    def map_position(self, value):
        normalized = str(value or '').strip().lower()
        return {
            'goalkeeper': 'TW',
            'defender': 'IV',
            'midfielder': 'ZM',
            'forward': 'ST',
            'striker': 'ST',
        }.get(normalized, '')

    def team_names(self, fixture, side, stats_player):
        home = fixture.get('homeName') or ''
        away = fixture.get('awayName') or ''

        if side == 'away':
            return away, home
        if side == 'home':
            return home, away

        team_side = str((stats_player or {}).get('teamSide') or '').lower()
        if team_side == 'away':
            return away, home

        return home, away

    def fetch_optional_json(self, api_key, path, request_sleep_seconds=0):
        try:
            return self.fetch_json(api_key, path, request_sleep_seconds)
        except CommandError as exc:
            self.stdout.write(self.style.WARNING(str(exc)))
            return None

    def fetch_json(self, api_key, path, request_sleep_seconds=0):
        url = f'{API_BASE_URL}{path}'
        request = Request(
            url,
            headers={
                'X-API-Key': api_key,
                'Accept': 'application/json',
                'User-Agent': 'Websoccer-Importer/0.1',
            },
        )

        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise CommandError(f'SportDB HTTP-Fehler {exc.code}: {path}') from exc
        except URLError as exc:
            raise CommandError(f'SportDB Netzwerkfehler: {exc.reason}') from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f'SportDB lieferte kein JSON: {path}') from exc

        if request_sleep_seconds:
            time.sleep(request_sleep_seconds)

        return payload

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

    def fixture_date(self, fixture):
        raw_value = fixture.get('startDateTimeUtc')
        if not raw_value:
            return None

        return datetime.fromisoformat(raw_value.replace('Z', '+00:00')).date()

    def parse_date(self, value):
        return date.fromisoformat(value)

    def parse_decimal(self, value):
        if value in (None, ''):
            return None

        try:
            return Decimal(str(value)).quantize(Decimal('0.01'))
        except InvalidOperation:
            return None

    def parse_minute(self, value):
        if value in (None, ''):
            return None

        raw_value = str(value)
        first_number = ''
        for char in raw_value:
            if char.isdigit():
                first_number += char
            elif first_number:
                break

        if not first_number:
            return None

        return max(0, min(int(first_number), 90))

    def as_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value

        return [value]

    def walk_payload(self, value):
        yield value

        if isinstance(value, dict):
            for child in value.values():
                yield from self.walk_payload(child)
        elif isinstance(value, list):
            for child in value:
                yield from self.walk_payload(child)
