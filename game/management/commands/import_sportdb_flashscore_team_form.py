import json
import os
import time
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from game.models import Club, Player, PlayerFormSnapshot


API_BASE_URL = 'https://api.sportdb.dev'
DEFAULT_COMPETITION_PATH = '/api/flashscore/football/germany:81/bundesliga:W6BOzpK2'
TEAM_MAPPINGS = {
    915: 'Bayern Munich',
    907: 'Dortmund',
}


class Command(BaseCommand):
    help = 'Import SportDB/Flashscore form snapshots for all DB players of selected RL teams.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--club',
            action='append',
            dest='clubs',
            help='Lokaler RL-Vereinsname. Kann mehrfach genutzt werden.',
        )
        parser.add_argument(
            '--club-fm-inside-id',
            action='append',
            dest='club_fm_inside_ids',
            type=int,
            help='Lokale Club-FMInside-ID. Kann mehrfach genutzt werden.',
        )
        parser.add_argument('--competition-path', default=DEFAULT_COMPETITION_PATH)
        parser.add_argument('--season', default=self.default_season())
        parser.add_argument('--days', type=int, default=90)
        parser.add_argument('--from-date', dest='from_date')
        parser.add_argument('--to-date', dest='to_date')
        parser.add_argument('--max-pages', type=int, default=5)
        parser.add_argument('--request-sleep-seconds', type=float, default=0.5)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--show-rows', action='store_true')
        parser.add_argument('--refresh-existing', action='store_true')

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
            raise CommandError('SPORTDB_KEY fehlt.')

        club_names = options['clubs'] or []
        club_fm_inside_ids = options['club_fm_inside_ids'] or []
        if not club_names and not club_fm_inside_ids:
            club_fm_inside_ids = list(TEAM_MAPPINGS)

        clubs_query = Club.objects.none()
        if club_names:
            clubs_query = clubs_query | Club.objects.filter(name__in=club_names)
        if club_fm_inside_ids:
            clubs_query = clubs_query | Club.objects.filter(fm_inside_id__in=club_fm_inside_ids)

        clubs = list(clubs_query.distinct().order_by('name'))
        if not clubs:
            raise CommandError('Keine passenden lokalen Vereine gefunden.')

        missing_clubs = sorted(set(club_names) - {club.name for club in clubs})
        for club_name in missing_clubs:
            self.stdout.write(self.style.WARNING(f'Verein nicht gefunden: {club_name}'))
        missing_fm_ids = sorted(set(club_fm_inside_ids) - {
            club.fm_inside_id for club in clubs if club.fm_inside_id
        })
        for club_fm_inside_id in missing_fm_ids:
            self.stdout.write(
                self.style.WARNING(f'Verein-FMInside-ID nicht gefunden: {club_fm_inside_id}')
            )

        to_date = self.parse_date(options['to_date']) if options['to_date'] else date.today()
        from_date = (
            self.parse_date(options['from_date'])
            if options['from_date']
            else to_date - timedelta(days=options['days'])
        )

        saved_count = 0
        skipped_count = 0
        matched_count = 0
        zero_count = 0
        matched_player_ids = set()
        unmatched_player_ids = set()
        fetched_playerstats = {}

        for club in clubs:
            team_name = TEAM_MAPPINGS.get(club.fm_inside_id, club.name)
            players = list(
                Player.objects.filter(real_life_club=club).order_by('last_name', 'first_name')
            )
            fixtures = self.fetch_recent_fixtures(
                api_key=api_key,
                competition_path=options['competition_path'],
                season=options['season'],
                from_date=from_date,
                to_date=to_date,
                max_pages=options['max_pages'],
                team_name=team_name,
            )

            self.stdout.write(
                f'{club.name}: {len(players)} Spieler, {len(fixtures)} Spiele.'
            )

            for fixture in fixtures:
                fixture_id = str(fixture.get('eventId') or '')
                if not fixture_id:
                    continue

                if not options['refresh_existing']:
                    existing_snapshot_count = PlayerFormSnapshot.objects.filter(
                        player__in=players,
                        source=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
                        fixture_id=fixture_id,
                    ).count()
                    if existing_snapshot_count >= len(players):
                        skipped_count += len(players)
                        continue

                playerstats = fetched_playerstats.get(fixture_id)
                if playerstats is None:
                    playerstats = self.fetch_json(
                        api_key,
                        f'/api/flashscore/match/{fixture_id}/playerstats',
                        options['request_sleep_seconds'],
                    )
                    fetched_playerstats[fixture_id] = playerstats

                team_side = self.fixture_side(fixture, team_name)
                stats_by_player = self.stats_by_player(playerstats)
                flashscore_players = playerstats.get('players') or []
                flashscore_index = self.flashscore_player_index(
                    flashscore_players,
                    team_side=team_side,
                )

                for player in players:
                    snapshot_exists = PlayerFormSnapshot.objects.filter(
                        player=player,
                        source=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
                        fixture_id=fixture_id,
                    ).exists()
                    if snapshot_exists and not options['refresh_existing']:
                        skipped_count += 1
                        continue

                    flashscore_player = self.match_flashscore_player(
                        player,
                        flashscore_index,
                    )
                    player_stats = (
                        stats_by_player.get(str(flashscore_player['id']))
                        if flashscore_player
                        else {}
                    )
                    snapshot_data = self.build_snapshot_data(
                        player=player,
                        club=club,
                        team_name=team_name,
                        fixture=fixture,
                        flashscore_player=flashscore_player,
                        player_stats=player_stats,
                    )

                    if flashscore_player:
                        matched_count += 1
                        matched_player_ids.add(player.id)
                    else:
                        unmatched_player_ids.add(player.id)

                    if snapshot_data['minutes_played'] == 0:
                        zero_count += 1

                    if options['dry_run'] and options['show_rows']:
                        self.stdout.write(
                            (
                                f"{snapshot_data['fixture_date']}: "
                                f"{player.full_name}, "
                                f"{snapshot_data['minutes_played']} Min., "
                                f"Rating {snapshot_data['rating'] or '-'}"
                            )
                        )
                    if options['dry_run']:
                        saved_count += 1
                        continue

                    PlayerFormSnapshot.objects.update_or_create(
                        player=player,
                        source=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
                        fixture_id=fixture_id,
                        defaults=snapshot_data,
                    )
                    saved_count += 1

        never_matched_player_ids = unmatched_player_ids - matched_player_ids
        if never_matched_player_ids:
            unmatched_names = list(
                Player.objects.filter(id__in=never_matched_player_ids)
                .order_by('last_name', 'first_name')
                .values_list('first_name', 'last_name')
            )
            self.stdout.write(
                self.style.WARNING(
                    'Nicht im Flashscore-Spielerindex gefunden: '
                    f'{", ".join(f"{first_name} {last_name}" for first_name, last_name in unmatched_names)}'
                )
            )

        saved_label = (
            'Snapshots wuerden geschrieben'
            if options['dry_run']
            else 'Snapshots gespeichert'
        )
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f'{saved_count} {saved_label}, '
                    f'{skipped_count} vorhandene uebersprungen, '
                    f'{matched_count} Spieler-Matchings, '
                    f'{zero_count} Null-Minuten-Snapshots, '
                    f'{len(fetched_playerstats)} Playerstats-Abfragen.'
                )
            )
        )

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
        normalized_team_name = self.normalize(team_name)

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

                fixture_teams = {
                    self.normalize(fixture.get('homeName') or ''),
                    self.normalize(fixture.get('awayName') or ''),
                }
                if normalized_team_name not in fixture_teams:
                    continue

                if from_date <= fixture_date <= to_date:
                    fixtures.append(fixture)
                    seen_fixture_ids.add(fixture_id)
                elif fixture_date < from_date:
                    return fixtures

        return fixtures

    def build_snapshot_data(
        self,
        player,
        club,
        team_name,
        fixture,
        flashscore_player,
        player_stats,
    ):
        minutes = self.int_stat(player_stats, 'matchMinutesPlayed')
        rating = self.player_rating(flashscore_player)
        goals = self.int_stat(player_stats, 'goals')
        assists = self.int_stat(player_stats, 'assistsGoal')
        yellow_cards = self.int_stat(player_stats, 'cardsYellow')
        red_cards = self.int_stat(player_stats, 'cardsRed')
        team_side = str((flashscore_player or {}).get('teamSide') or '').lower()
        if not team_side:
            team_side = self.fixture_side(fixture, team_name)

        return {
            'fixture_date': self.fixture_date(fixture),
            'league_api_football_id': None,
            'team_api_football_id': None,
            'team_name': team_name,
            'opponent_name': self.opponent_name(fixture, team_side),
            'minutes_played': minutes,
            'possible_minutes': 90,
            'started': bool((flashscore_player or {}).get('inBaseLineup') and minutes > 0),
            'substituted_in': bool(not (flashscore_player or {}).get('inBaseLineup') and minutes > 0),
            'captain': False,
            'position': self.player_position(flashscore_player),
            'rating': rating,
            'goals': goals,
            'assists': assists,
            'yellow_cards': yellow_cards,
            'red_cards': red_cards,
            'raw_payload': {
                'fixture': fixture,
                'flashscore_player': flashscore_player or {},
                'player_stats': player_stats,
                'local_club': club.name,
            },
        }

    def stats_by_player(self, payload):
        grouped = {}
        for stat in payload.get('stats') or []:
            player_id = str(stat.get('playerId') or '')
            stats_key = stat.get('statsKey')
            if not player_id or not stats_key:
                continue

            grouped.setdefault(player_id, {})[stats_key] = stat

        return grouped

    def flashscore_player_index(self, players, team_side):
        indexed = []
        expected_team_side = str(team_side or '').upper()
        for player in players:
            if expected_team_side and str(player.get('teamSide') or '').upper() != expected_team_side:
                continue

            names = {
                player.get('name') or '',
                player.get('shortName') or '',
                (player.get('slug') or '').replace('-', ' '),
            }
            indexed.append(
                {
                    'player': player,
                    'tokens': [
                        self.name_tokens(name)
                        for name in names
                        if name
                    ],
                }
            )

        return indexed

    def match_flashscore_player(self, local_player, flashscore_index):
        local_tokens = self.name_tokens(local_player.full_name)
        if not local_tokens:
            return None

        best_match = None
        best_score = 0
        for item in flashscore_index:
            for candidate_tokens in item['tokens']:
                score = len(local_tokens & candidate_tokens)
                if score > best_score and local_tokens <= candidate_tokens:
                    best_score = score
                    best_match = item['player']
                elif score > best_score and self.surname_token(local_player) in candidate_tokens:
                    best_score = score
                    best_match = item['player']

        if best_score >= 2:
            return best_match

        return None

    def surname_token(self, player):
        tokens = self.name_tokens(player.last_name)
        return next(iter(tokens), '')

    def name_tokens(self, value):
        normalized = self.normalize(value)
        return {
            token
            for token in normalized.replace('-', ' ').split()
            if len(token) > 1
        }

    def normalize(self, value):
        value = unicodedata.normalize('NFKD', str(value or ''))
        value = ''.join(char for char in value if not unicodedata.combining(char))
        value = value.lower().replace('ß', 'ss')
        return ''.join(char if char.isalnum() else ' ' for char in value).strip()

    def int_stat(self, stats, key):
        raw_stat = stats.get(key) or {}
        value = raw_stat.get('numericValue')
        if value in (None, ''):
            return 0

        return int(value)

    def player_rating(self, flashscore_player):
        raw_rating = (flashscore_player or {}).get('rating') or {}
        if not isinstance(raw_rating, dict):
            return None

        value = raw_rating.get('numericValue') or raw_rating.get('value')
        if value in (None, ''):
            return None

        try:
            return Decimal(str(value)).quantize(Decimal('0.01'))
        except InvalidOperation:
            return None

    def player_position(self, flashscore_player):
        position = (flashscore_player or {}).get('position') or {}
        if not isinstance(position, dict):
            return ''

        return {
            'goalkeeper': 'TW',
            'defender': 'IV',
            'midfielder': 'ZM',
            'forward': 'ST',
            'striker': 'ST',
            'winger': 'LF',
        }.get(str(position.get('name') or '').lower(), '')

    def fixture_side(self, fixture, team_name):
        normalized_team_name = self.normalize(team_name)
        if self.normalize(fixture.get('homeName') or '') == normalized_team_name:
            return 'home'
        if self.normalize(fixture.get('awayName') or '') == normalized_team_name:
            return 'away'

        return ''

    def opponent_name(self, fixture, team_side):
        if team_side == 'home':
            return fixture.get('awayName') or ''
        if team_side == 'away':
            return fixture.get('homeName') or ''

        return ''

    def fetch_json(self, api_key, path, request_sleep_seconds=0):
        request = Request(
            f'{API_BASE_URL}{path}',
            headers={
                'X-API-Key': api_key,
                'Accept': 'application/json',
                'User-Agent': 'Websoccer-Team-Importer/0.1',
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
