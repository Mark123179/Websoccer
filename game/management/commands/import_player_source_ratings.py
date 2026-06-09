import html
import json
import re
import unicodedata
from datetime import datetime
from urllib.request import Request, urlopen

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from game.models import (
    Club,
    DataSource,
    Player,
    PlayerExternalId,
    PlayerSourceRating,
    PlayerSourceRatingSnapshot,
)


SOURCE_CLUBS = [
    {
        'club_fm_inside_id': 907,
        'fm_inside_url': 'https://fminside.net/clubs/7-fm-26/907-borussia-dortmund',
        'sofifa_url': 'https://sofifa.com/team/22/borussia-dortmund/?hl=en-US',
    },
    {
        'club_fm_inside_id': 915,
        'fm_inside_url': 'https://fminside.net/clubs/7-fm-26/915-fc-bayern',
        'sofifa_url': 'https://sofifa.com/team/21/fc-bayern-munchen/?hl=en-US',
    },
]

# FMInside-Attribut-IDs (tr id) -> Spalte auf PlayerSourceRating (Feldspieler).
FMI_ATTR_MAP = {
    'pace': 'tempo',
    'stamina': 'ausdauer',
    'strength': 'kraft',
    'technique': 'technik',
    'dribbling': 'dribbling',
    'passing': 'passspiel',
    'crossing': 'flanken',
    'finishing': 'abschluss',
    'heading': 'kopfball',
    'tackling': 'zweikampf',
    'positioning': 'defensivstellung',
    'vision': 'uebersicht',
    'teamwork': 'teamwork',
    'corners': 'ecken',
    'free-kick-taking': 'freistoss',
    'penalty-taking': 'elfmeter',
}

# FMInside-Attribut-IDs -> Spalte (Torwart).
FMI_GK_MAP = {
    'reflexes': 'tw_reflexe',
    'handling': 'tw_fangsicherheit',
    'one-on-ones': 'tw_eins_gegen_eins',
    'positioning': 'tw_stellungsspiel',
    'passing': 'tw_passen',
}

# SoFIFA-Attributlabel (englisch) -> Spalte (Feldspieler).
SOFIFA_ATTR_MAP = {
    'Acceleration': 'tempo',
    'Stamina': 'ausdauer',
    'Strength': 'kraft',
    'Dribbling': 'dribbling',
    'Short passing': 'passspiel',
    'Crossing': 'flanken',
    'Finishing': 'abschluss',
    'Heading accuracy': 'kopfball',
    'Standing tackle': 'zweikampf',
    'Attack position': 'defensivstellung',  # SoFIFA "Stellungsspiel"
    'Vision': 'uebersicht',
    'Penalties': 'elfmeter',
    'FK Accuracy': 'freistoss',
}

# SoFIFA-Attributlabel -> Spalte (Torwart). Kein SoFIFA-Pendant fuer
# tw_eins_gegen_eins -> bleibt NULL auf der EA-Zeile.
SOFIFA_GK_MAP = {
    'GK Reflexes': 'tw_reflexe',
    'GK Handling': 'tw_fangsicherheit',
    'GK Positioning': 'tw_stellungsspiel',
    'GK Kicking': 'tw_passen',
}

# Alle Attributspalten (fuer Reset vor dem Schreiben).
ALL_ATTR_COLUMNS = sorted(
    set(FMI_ATTR_MAP.values())
    | set(FMI_GK_MAP.values())
    | set(SOFIFA_ATTR_MAP.values())
    | set(SOFIFA_GK_MAP.values())
)


class Command(BaseCommand):
    help = 'Import FMInside and SoFIFA ratings/potentials for reference players.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch and match sources without writing changes.',
        )
        parser.add_argument(
            '--skip-recalculate',
            action='store_true',
            help='Do not recalculate strength profiles after import.',
        )
        parser.add_argument(
            '--player-id',
            type=int,
            default=None,
            help='Nur diesen Spieler (Pilot) importieren; Club muss in SOURCE_CLUBS sein.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        player_id = options.get('player_id')
        target_player = Player.objects.get(id=player_id) if player_id else None
        today = timezone.localdate()
        fm_data_source = DataSource.objects.get(code=DataSource.CODE_FMINSIDE)
        sofifa_data_source = DataSource.objects.get(code=DataSource.CODE_SOFIFA)
        self._page_cache = {}
        imported_fm = 0
        imported_sofifa = 0
        unmatched_fm = []
        unmatched_sofifa = []

        for source_club in SOURCE_CLUBS:
            club = Club.objects.get(fm_inside_id=source_club['club_fm_inside_id'])
            if target_player and target_player.club_id != club.id:
                continue
            if target_player:
                players = [target_player]
            else:
                players = list(Player.objects.filter(club=club).order_by('last_name'))
            fm_players = self.extract_fm_inside_players(
                self.fetch_page(source_club['fm_inside_url'])
            )
            sofifa_players = self.extract_sofifa_players(
                self.fetch_page(source_club['sofifa_url'])
            )

            for player in players:
                is_gk = player.position == 'TW'
                fm_player = self.find_source_player(fm_players, player)
                sofifa_player = self.find_source_player(sofifa_players, player)

                if fm_player:
                    fm_player['url'] = self.fm_inside_detail_url(fm_player['url'])
                    fm_player = self.enrich_fm_inside_dynamic_potential(fm_player)
                    detail_page = self.fetch_page(fm_player['url'])
                    fm_attrs = self.extract_fm_inside_attributes(detail_page, is_gk)
                    fm_version = self.extract_fm_inside_version(detail_page)
                    imported_fm += 1
                    if not fm_attrs:
                        self.stdout.write(self.style.WARNING(
                            f'FMI ohne Attribute (Scrape pruefen): {player.full_name}'
                        ))
                    if not dry_run:
                        self.store_source_rating(
                            player=player,
                            source=PlayerSourceRating.SOURCE_FM,
                            rating=fm_player['rating'],
                            potential=fm_player['potential'],
                            source_url=fm_player['url'],
                            source_version=fm_version,
                            checked_at=today,
                            data_source=fm_data_source,
                            attributes=fm_attrs,
                        )
                        PlayerExternalId.objects.update_or_create(
                            player=player,
                            source=fm_data_source,
                            defaults={
                                'external_id': str(fm_player['id']),
                                'profile_url': fm_player['url'],
                                'is_primary': False,
                            },
                        )
                        player.fm_inside_id = fm_player['id']
                        player.potential = fm_player['potential']
                        player.save(update_fields=['fm_inside_id', 'potential'])
                else:
                    unmatched_fm.append(player.full_name)

                if sofifa_player:
                    sofifa_page = self.fetch_page(sofifa_player['url'])
                    sofifa_attrs = self.extract_sofifa_attributes(sofifa_page, is_gk)
                    imported_sofifa += 1
                    if not sofifa_attrs:
                        self.stdout.write(self.style.WARNING(
                            f'SoFIFA ohne Attribute (Scrape pruefen): {player.full_name}'
                        ))
                    if not dry_run:
                        self.store_source_rating(
                            player=player,
                            source=PlayerSourceRating.SOURCE_EA,
                            rating=sofifa_player['rating'],
                            potential=sofifa_player['potential'],
                            source_url=sofifa_player['url'],
                            source_version=sofifa_player['source_version'],
                            checked_at=today,
                            data_source=sofifa_data_source,
                            attributes=sofifa_attrs,
                        )
                        PlayerExternalId.objects.update_or_create(
                            player=player,
                            source=sofifa_data_source,
                            defaults={
                                'external_id': str(sofifa_player['id']),
                                'profile_url': sofifa_player['url'],
                                'is_primary': False,
                            },
                        )
                else:
                    unmatched_sofifa.append(player.full_name)

        if not dry_run and not options['skip_recalculate']:
            call_command('recalculate_player_strengths')

        mode = 'DRY RUN' if dry_run else 'OK'
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}: FMInside {imported_fm}, SoFIFA {imported_sofifa}, '
                f'FMI-only moeglich bei Spielern ohne SoFIFA.'
            )
        )
        if unmatched_fm:
            self.stdout.write(self.style.WARNING(f'Ohne FMI: {", ".join(unmatched_fm)}'))
        if unmatched_sofifa:
            self.stdout.write(
                self.style.WARNING(f'Ohne SoFIFA: {", ".join(unmatched_sofifa)}')
            )

    def fetch_page(self, url):
        if hasattr(self, '_page_cache') and url in self._page_cache:
            return self._page_cache[url]

        request = Request(
            url,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
                'Referer': 'https://www.google.com/',
            },
        )
        with urlopen(request, timeout=30) as response:
            page = response.read().decode('utf-8', errors='replace')

        if hasattr(self, '_page_cache'):
            self._page_cache[url] = page

        return page

    def fm_inside_detail_url(self, url):
        """Pinne die FMInside-URL auf die FM26.2-Datenbank (Prefix 7-fm262)."""
        return re.sub(r'/players/7-fm[^/]+/', '/players/7-fm262/', url)

    def extract_fm_inside_version(self, page):
        match = re.search(
            r'<li class="active">.*?>([^<]*FM\s*[\d.]+[^<]*)</a>',
            page,
            flags=re.S,
        )
        if match:
            return f'FMInside {self.clean_html(match.group(1))}'
        return 'FMInside FM26'

    def extract_fm_inside_attributes(self, page, is_gk):
        rows = dict(
            re.findall(
                r'<tr id="([^"]+)">.*?<td class="stat[^"]*">(\d+)</td>',
                page,
                flags=re.S,
            )
        )
        mapping = FMI_GK_MAP if is_gk else FMI_ATTR_MAP
        return {
            column: int(rows[attr_id])
            for attr_id, column in mapping.items()
            if attr_id in rows
        }

    def extract_sofifa_attributes(self, page, is_gk):
        pairs = re.findall(
            r'<em title="(\d+)">\d+</em></span>\s*'
            r'<span data-tippy-right-start[^>]*>([^<]+)</span>',
            page,
        )
        lookup = {
            html.unescape(label).strip(): int(value)
            for value, label in pairs
        }
        mapping = SOFIFA_GK_MAP if is_gk else SOFIFA_ATTR_MAP
        return {
            column: lookup[label]
            for label, column in mapping.items()
            if label in lookup
        }

    def extract_fm_inside_players(self, page):
        if '<h2>Full Squad</h2>' not in page:
            return {}

        section = page.split('<h2>Full Squad</h2>', 1)[1]
        section = section.split('<h2>', 1)[0]
        rows = re.findall(r'<ul class="player">(.*?)</ul>', section, flags=re.S)
        players = {}

        for row in rows:
            link = re.search(
                r'href="(/players/7-fm-?\d+/(\d+)-[^"]+)"[^>]*>([^<]+)</a>',
                row,
            )
            if not link:
                continue

            ratings = [
                int(value)
                for value in re.findall(r'<span class="card [^"]+">(\d+)</span>', row)[:2]
            ]
            name = html.unescape(link.group(3)).strip()
            players[self.normalize_name(name)] = {
                'id': int(link.group(2)),
                'name': name,
                'rating': ratings[0] if ratings else 50,
                'potential': ratings[1] if len(ratings) > 1 else (ratings[0] if ratings else 50),
                'url': f"https://fminside.net{link.group(1)}",
            }

        return players

    def enrich_fm_inside_dynamic_potential(self, player_data):
        if player_data['potential'] > player_data['rating']:
            return player_data

        detail_page = self.fetch_page(player_data['url'])
        dynamic_potential = self.extract_fm_inside_dynamic_potential(detail_page)
        if dynamic_potential and dynamic_potential > player_data['potential']:
            return {
                **player_data,
                'potential': dynamic_potential,
            }

        return player_data

    def extract_fm_inside_dynamic_potential(self, page):
        potential_range = re.search(
            r'data-title="Potential between\s+(\d+)\s+and\s+(\d+)',
            page,
            flags=re.I,
        )
        if potential_range:
            return int(potential_range.group(2))

        return None

    def extract_sofifa_players(self, page):
        title_match = re.search(r'<title>(.*?)</title>', page, re.S)
        source_version = (
            self.clean_html(title_match.group(1))
            if title_match
            else 'SoFIFA FC26'
        )
        players = {}

        for row in re.findall(r'<tr class="(?:starting|sub|res)".*?</tr>', page, re.S):
            link = re.search(
                r'<a href="(/player/(\d+)/[^"]+)"[^>]*data-tippy-content="([^"]+)"',
                row,
                re.S,
            )
            if not link:
                continue

            rating_match = re.search(r'data-col="oa"><em title="(\d+)">', row)
            potential_match = re.search(r'data-col="pt"><em title="(\d+)">', row)
            if not rating_match:
                continue

            name = html.unescape(link.group(3)).strip()
            players[self.normalize_name(name)] = {
                'id': int(link.group(2)),
                'name': name,
                'rating': int(rating_match.group(1)),
                'potential': (
                    int(potential_match.group(1))
                    if potential_match
                    else int(rating_match.group(1))
                ),
                'url': f"https://sofifa.com{link.group(1)}",
                'source_version': source_version,
            }

        return players

    def store_source_rating(
        self,
        player,
        source,
        rating,
        potential,
        source_url,
        source_version,
        checked_at,
        data_source,
        attributes=None,
    ):
        defaults = {
            'rating': rating,
            'potential': potential,
            'source_url': source_url,
            'source_version': source_version,
            'checked_at': checked_at,
        }
        # Attributspalten immer komplett setzen: gemappte Werte schreiben,
        # nicht gelieferte (quellenfremde) Spalten explizit auf NULL.
        for column in ALL_ATTR_COLUMNS:
            defaults[column] = (attributes or {}).get(column)
        PlayerSourceRating.objects.update_or_create(
            player=player,
            source=source,
            defaults=defaults,
        )
        PlayerSourceRatingSnapshot.objects.update_or_create(
            player=player,
            source=data_source,
            recorded_at=checked_at,
            defaults={
                'rating': rating,
                'potential': potential,
                'source_url': source_url,
                'source_version': source_version,
                'update_current': False,
                'notes': 'Automatisch aus externer Quelle importiert.',
            },
        )

    def clean_html(self, raw):
        text = re.sub(r'<[^>]+>', ' ', raw)
        return re.sub(r'\s+', ' ', html.unescape(text)).strip()

    def normalize_name(self, name):
        normalized = unicodedata.normalize('NFKD', name)
        normalized = ''.join(
            char for char in normalized
            if not unicodedata.combining(char)
        )
        return re.sub(r'[^a-z0-9]+', '', normalized.lower())

    def find_source_player(self, source_players, player):
        full_name_key = self.normalize_name(player.full_name)
        reversed_name_key = self.normalize_name(f'{player.last_name} {player.first_name}')
        if full_name_key in source_players:
            return source_players[full_name_key]
        if reversed_name_key in source_players:
            return source_players[reversed_name_key]

        name_tokens = [
            self.normalize_name(token)
            for token in player.full_name.split()
            if token.strip()
        ]
        candidates = [
            data
            for key, data in source_players.items()
            if all(token and token in key for token in name_tokens)
        ]
        if len(candidates) == 1:
            return candidates[0]

        return None
