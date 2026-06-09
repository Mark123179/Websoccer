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


# Auto-generierte Club-Liste aus der Datenbank (fm_inside_id + sofifa_url)
# Clubs ohne sofifa_url werden uebersprungen.
# Manuelle SoFIFA-URL-Mapping (team-id-slug). Keys = fm_inside_id.
CLUB_SOURCE_DATA = {
    # fm_inside_id: (fm_inside_url, sofifa_url)
    915:   ('https://fminside.net/clubs/7-fm-26/915-fc-bayern',
             'https://sofifa.com/team/21/fc-bayern-munchen/?hl=en-US'),
    907:   ('https://fminside.net/clubs/7-fm-26/907-borussia-dortmund',
             'https://sofifa.com/team/22/borussia-dortmund/?hl=en-US'),
    901:   ('https://fminside.net/clubs/7-fm-26/901-bayer-04-leverkusen',
             'https://sofifa.com/team/32/bayer-04-leverkusen/?hl=en-US'),
    91013388: ('https://fminside.net/clubs/7-fm-26/91013388-rb-leipzig',
               'https://sofifa.com/team/112172/rb-leipzig/?hl=en-US'),
    912:   ('https://fminside.net/clubs/7-fm-26/912-eintracht-frankfurt',
             'https://sofifa.com/team/1824/eintracht-frankfurt/?hl=en-US'),
    961:   ('https://fminside.net/clubs/7-fm-26/961-vfl-wolfsburg',
             'https://sofifa.com/team/12/vfl-wolfsburg/?hl=en-US'),
    944:   ('https://fminside.net/clubs/7-fm-26/944-sc-freiburg',
             'https://sofifa.com/team/28/sc-freiburg/?hl=en-US'),
    121182: ('https://fminside.net/clubs/7-fm-26/121182-1-fc-union-berlin',
             'https://sofifa.com/team/1670/1-fc-union-berlin/?hl=en-US'),
    960:   ('https://fminside.net/clubs/7-fm-26/960-vfb-stuttgart',
             'https://sofifa.com/team/36/vfb-stuttgart/?hl=en-US'),
    879226: ('https://fminside.net/clubs/7-fm-26/879226-1899-hoffenheim',
             'https://sofifa.com/team/100409/1899-hoffenheim/?hl=en-US'),
    905:   ('https://fminside.net/clubs/7-fm-26/905-vfl-bochum',
             'https://sofifa.com/team/160293/vfl-bochum/?hl=en-US'),
    2238:  ('https://fminside.net/clubs/7-fm-26/2238-fc-augsburg',
             'https://sofifa.com/team/1670/fc-augsburg/?hl=en-US'),
    908:   ('https://fminside.net/clubs/7-fm-26/908-borussia-monchengladbach',
             'https://sofifa.com/team/31/borussia-monchengladbach/?hl=en-US'),
    948:   ('https://fminside.net/clubs/7-fm-26/948-sv-werder-bremen',
             'https://sofifa.com/team/162/sv-werder-bremen/?hl=en-US'),
    918:   ('https://fminside.net/clubs/7-fm-26/918-1-fsv-mainz-05',
             'https://sofifa.com/team/39/1-fsv-mainz-05/?hl=en-US'),
    880295: ('https://fminside.net/clubs/7-fm-26/880295-1-fc-heidenheim',
             'https://sofifa.com/team/110502/1-fc-heidenheim/?hl=en-US'),
    3604375: ('https://fminside.net/clubs/7-fm-26/3604375-fc-st-pauli',
              'https://sofifa.com/team/110174/fc-st-pauli/?hl=en-US'),
    2245:  ('https://fminside.net/clubs/7-fm-26/2245-holstein-kiel',
             'https://sofifa.com/team/110703/holstein-kiel/?hl=en-US'),
}


def build_source_clubs():
    """Baue SOURCE_CLUBS dynamisch aus der Datenbank."""
    clubs = []
    for club in Club.objects.filter(
        fm_inside_id__isnull=False,
    ).exclude(
        name__in=['Karrierende', 'FC Basel', 'FC Valencia'],
    ).order_by('name'):
        fm_id = club.fm_inside_id
        data = CLUB_SOURCE_DATA.get(fm_id)
        if not data:
            continue
        fm_url, sofifa_url = data
        clubs.append({
            'club_fm_inside_id': fm_id,
            'fm_inside_url': fm_url,
            'sofifa_url': sofifa_url,
        })
    return clubs


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
    'Defensive awareness': 'defensivstellung',
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
        parser.add_argument(
            '--club-only',
            type=int,
            default=None,
            help='Nur diesen Club (fm_inside_id) importieren.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        player_id = options.get('player_id')
        club_only = options.get('club_only')
        target_player = Player.objects.get(id=player_id) if player_id else None
        today = timezone.localdate()
        fm_data_source = DataSource.objects.get(code=DataSource.CODE_FMINSIDE)
        sofifa_data_source = DataSource.objects.get(code=DataSource.CODE_SOFIFA)
        self._page_cache = {}
        imported_fm = 0
        imported_sofifa = 0
        unmatched_fm = []
        unmatched_sofifa = []

        SOURCE_CLUBS = build_source_clubs()

        for source_club in SOURCE_CLUBS:
            if club_only and source_club['club_fm_inside_id'] != club_only:
                continue
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
                            source_version='SoFIFA EAFC 26',
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

        self.stdout.write(self.style.SUCCESS(
            f'FMI: {imported_fm} importiert, '
            f'{len(unmatched_fm)} nicht gematcht'
        ))
        if unmatched_fm:
            for name in unmatched_fm:
                self.stdout.write(self.style.WARNING(f'  - {name}'))

        self.stdout.write(self.style.SUCCESS(
            f'SoFIFA: {imported_sofifa} importiert, '
            f'{len(unmatched_sofifa)} nicht gematcht'
        ))
        if unmatched_sofifa:
            for name in unmatched_sofifa:
                self.stdout.write(self.style.WARNING(f'  - {name}'))

        if not dry_run and not options['skip_recalculate']:
            self.stdout.write('Recalculate strength profiles...')
            call_command('recalculate_strength_profiles', '--all')
            self.stdout.write(self.style.SUCCESS('Strength profiles recalculated.'))

    def store_source_rating(self, player, source, rating, potential,
                            source_url, source_version, checked_at,
                            data_source, attributes=None):
        defaults = {
            'rating': rating,
            'potential': potential,
            'source_url': source_url,
            'source_version': source_version,
            'checked_at': checked_at,
            'data_source': data_source,
        }
        for col in ALL_ATTR_COLUMNS:
            defaults[col] = None
        if attributes:
            defaults.update(attributes)
        rating_obj, _ = PlayerSourceRating.objects.update_or_create(
            player=player,
            source=source,
            defaults=defaults,
        )
        PlayerSourceRatingSnapshot.objects.create(
            player=player,
            source=source,
            rating=rating,
            potential=potential,
            source_url=source_url,
            source_version=source_version,
            data_source=data_source,
            checked_at=checked_at,
            **{col: defaults[col] for col in ALL_ATTR_COLUMNS},
        )
        return rating_obj

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
        mapping = SOFIFA_GK_MAP if is_gk else SOFIFA_ATTR_MAP
        return {
            column: int(value)
            for value, label in pairs
            for key, column in mapping.items()
            if key.lower() in label.strip().lower()
        }

    def extract_fm_inside_players(self, page):
        rows = re.findall(
            r'<tr[^>]*>.*?<td[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>'
            r'\s*<img[^>]*>\s*([^<]*)</a>.*?'
            r'<td[^>]*class=".*?rating[^"]*"[^>]*>(\d+)</td>.*?'
            r'<td[^>]*class=".*?rating[^"]*"[^>]*>(\d+)</td>.*?'
            r'<td[^>]*class=".*?position[^"]*"[^>]*>([^<]*)</td>.*?'
            r'<td[^>]*class=".*?age[^"]*"[^>]*>(\d+)</td>.*?'
            r'<td[^>]*class=".*?birth[^"]*"[^>]*>(\d{2}\.\d{2}\.\d{4})</td>.*?'
            r'<td[^>]*class=".*?height[^"]*"[^>]*>(\d+)</td>.*?'
            r'<td[^>]*class=".*?foot[^"]*"[^>]*>([^<]*)</td>.*?'
            r'<td[^>]*class=".*?value[^"]*"[^>]*>([^<]*)</td>.*?'
            r'<td[^>]*class=".*?wage[^"]*"[^>]*>([^<]*)</td>.*?'
            r'</tr>',
            page,
            flags=re.S,
        )
        players = []
        for row in rows:
            url, name, rating, potential, position, age, dob, height, foot, value, wage = row
            players.append({
                'url': html.unescape(url),
                'name': html.unescape(name.strip()),
                'rating': int(rating),
                'potential': int(potential),
                'position': position.strip(),
                'age': int(age),
                'dob': datetime.strptime(dob.strip(), '%d.%m.%Y').date(),
                'height': int(height),
                'foot': foot.strip(),
                'value': value.strip(),
                'wage': wage.strip(),
            })
        return players

    def extract_sofifa_players(self, page):
        # SoFIFA player card pattern
        rows = re.findall(
            r'<tr[^>]*>.*?<td[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>'
            r'\s*<img[^>]*>\s*([^<]*)</a>.*?'
            r'<td[^>]*class=".*?col-oa[^"]*"[^>]*>\s*<span[^>]*>(\d+)</span>\s*</td>.*?'
            r'<td[^>]*class=".*?col-pt[^"]*"[^>]*>\s*<span[^>]*>(\d+)</span>\s*</td>.*?'
            r'<td[^>]*class=".*?col-hi[^"]*"[^>]*>(\d+)</td>.*?'
            r'<td[^>]*class=".*?col-wi[^"]*"[^>]*>(\d+)</td>.*?'
            r'<td[^>]*class=".*?col-pf[^"]*"[^>]*>([^<]*)</td>.*?'
            r'<td[^>]*class=".*?col-bo[^"]*"[^>]*>([^<]*)</td>.*?'
            r'<td[^>]*class=".*?col-bp[^"]*"[^>]*>([^<]*)</td>.*?'
            r'<td[^>]*class=".*?col-vl[^"]*"[^>]*>([^<]*)</td>.*?'
            r'<td[^>]*class=".*?col-wg[^"]*"[^>]*>([^<]*)</td>.*?'
            r'</tr>',
            page,
            flags=re.S,
        )
        players = []
        for row in rows:
            url, name, rating, potential, age, dob, position, foot, value, wage = row
            players.append({
                'url': html.unescape(url),
                'name': html.unescape(name.strip()),
                'rating': int(rating),
                'potential': int(potential),
                'age': int(age),
                'dob': datetime.strptime(dob.strip(), '%d/%m/%Y').date(),
                'position': position.strip(),
                'foot': foot.strip(),
                'value': value.strip(),
                'wage': wage.strip(),
            })
        return players

    def find_source_player(self, source_players, player):
        """Match source player by name (fuzzy) and date of birth."""
        target_name = self.normalize_name(player.full_name)
        target_dob = player.date_of_birth

        best = None
        best_score = 0

        for sp in source_players:
            sp_name = self.normalize_name(sp['name'])
            name_score = self.name_similarity(target_name, sp_name)
            dob_match = (target_dob == sp['dob']) if target_dob else False

            score = name_score
            if dob_match:
                score += 100

            if score > best_score:
                best_score = score
                best = sp

        if best_score >= 80:
            return best
        return None

    def normalize_name(self, name):
        name = html.unescape(name)
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ASCII', 'ignore').decode('ASCII')
        return re.sub(r'[^a-zA-Z]', '', name).lower()

    def name_similarity(self, a, b):
        if a == b:
            return 200
        if a in b or b in a:
            return 150
        # Levenshtein distance
        import difflib
        return int(difflib.SequenceMatcher(None, a, b).ratio() * 100)

    def enrich_fm_inside_dynamic_potential(self, fm_player):
        """
        FMInside liefert auf der Club-Seite oft nur die *aktuelle* Ability.
        Die Potential-Spalte ist manchmal leer oder gleich der Ability.
        Versuche, aus dem Detail-Scrape das echte Potential zu ziehen.
        """
        # Aktuell: wir vertrauen dem Potential aus der Club-Seite.
        # Falls spaeter Detail-Scrape ergaenzt wird, hier ergaenzen.
        return fm_player

    def clean_html(self, text):
        return html.unescape(text).strip()
