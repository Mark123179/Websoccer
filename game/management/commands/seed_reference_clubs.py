import calendar
import html
import re
import unicodedata
from datetime import date
from decimal import Decimal
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand

from game.models import Club, League, Player, PlayerStrengthProfile


REFERENCE_CLUBS = [
    {
        'name': 'Borussia Dortmund',
        'short_name': 'BVB',
        'fm_inside_id': 907,
        'founded_year': 1909,
        'budget': Decimal('100000000'),
        'fm_inside_url': 'https://fminside.net/clubs/7-fm-26/907-borussia-dortmund',
        'transfermarkt_url': 'https://www.transfermarkt.de/borussia-dortmund/kader/verein/16/saison_id/2025/plus/1',
        'marker': 'Gregor Kobel',
    },
    {
        'name': 'FC Bayern München',
        'short_name': 'FCB',
        'fm_inside_id': 915,
        'founded_year': 1900,
        'budget': Decimal('205000000'),
        'fm_inside_url': 'https://fminside.net/clubs/7-fm-26/915-fc-bayern',
        'transfermarkt_url': 'https://www.transfermarkt.de/fc-bayern-munchen/kader/verein/27/saison_id/2025/plus/1',
        'marker': 'Harry Kane',
    },
]


POSITION_MAP = {
    'Torwart': 'TW',
    'Innenverteidiger': 'IV',
    'Linker Verteidiger': 'LV',
    'Rechter Verteidiger': 'RV',
    'Defensives Mittelfeld': 'ZDM',
    'Zentrales Mittelfeld': 'ZM',
    'Offensives Mittelfeld': 'ZOM',
    'Linkes Mittelfeld': 'LF',
    'Linksaußen': 'LF',
    'Rechtes Mittelfeld': 'RF',
    'Rechtsaußen': 'RF',
    'Hängende Spitze': 'ST',
    'Mittelstürmer': 'ST',
}


class Command(BaseCommand):
    help = 'Seed BVB and FC Bayern first-team squads from Transfermarkt and FMInside IDs.'

    def handle(self, *args, **options):
        league, _ = League.objects.get_or_create(
            name='1. Bundesliga',
            defaults={'country': 'Deutschland'},
        )

        for club_data in REFERENCE_CLUBS:
            fm_inside_players = self.extract_fm_inside_players(
                self.fetch_page(club_data['fm_inside_url'])
            )
            transfermarkt_players = self.extract_transfermarkt_squad(
                self.fetch_page(club_data['transfermarkt_url']),
                club_data['marker'],
            )

            club, _ = Club.objects.update_or_create(
                fm_inside_id=club_data['fm_inside_id'],
                defaults={
                    'name': club_data['name'],
                    'short_name': club_data['short_name'],
                    'founded_year': club_data['founded_year'],
                    'budget': club_data['budget'],
                    'league': league,
                },
            )

            Player.objects.filter(club=club).delete()

            unmatched = []
            for player_data in transfermarkt_players:
                fm_inside_data = self.find_fm_inside_player(
                    fm_inside_players,
                    player_data['name'],
                )
                first_name, last_name = self.split_name(player_data['name'])
                market_value = player_data['market_value']

                player, _ = Player.objects.update_or_create(
                    transfermarkt_id=player_data['transfermarkt_id'],
                    defaults={
                        'fm_inside_id': fm_inside_data.get('fm_inside_id'),
                        'transfermarkt_profile_url': player_data['transfermarkt_profile_url'],
                        'transfermarkt_market_value_url': player_data['transfermarkt_market_value_url'],
                        'first_name': first_name,
                        'last_name': last_name,
                        'date_of_birth': player_data['date_of_birth'],
                        'nationalities': ', '.join(player_data['nationalities']),
                        'age': player_data['age'],
                        'position': POSITION_MAP.get(player_data['primary_position'], 'ZM'),
                        'primary_position': player_data['primary_position'],
                        'source_positions': ', '.join(fm_inside_data.get('positions', [])),
                        'potential': fm_inside_data.get('potential', 50),
                        'market_value': market_value,
                        'salary_per_match': self.calculate_salary_per_match(market_value),
                        'contract_until': player_data['contract_until'],
                        'club': club,
                    },
                )
                PlayerStrengthProfile.objects.update_or_create(
                    player=player,
                    defaults={
                        'base_strength': fm_inside_data.get('rating', 50),
                        'form_modifier': 0,
                    },
                )

                if not fm_inside_data:
                    unmatched.append(player.full_name)

            message = f"{club.name}: {len(transfermarkt_players)} Profis geladen."
            if unmatched:
                message += f" Ohne FMInside-Match: {', '.join(unmatched)}."
            self.stdout.write(self.style.SUCCESS(message))

    def fetch_page(self, url):
        request = Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            },
        )
        with urlopen(request, timeout=30) as response:
            return response.read().decode('utf-8', errors='replace')

    def extract_fm_inside_players(self, page):
        if '<h2>Full Squad</h2>' not in page:
            return {}

        section = page.split('<h2>Full Squad</h2>', 1)[1]
        section = section.split('<h2>', 1)[0]
        rows = re.findall(r'<ul class="player">(.*?)</ul>', section, flags=re.S)
        players = {}

        for row in rows:
            link = re.search(
                r'href="/players/7-fm\d+/(\d+)-[^"]+"[^>]*>([^<]+)</a>',
                row,
            )
            if not link:
                continue

            ratings = [
                int(value)
                for value in re.findall(r'<span class="card [^"]+">(\d+)</span>', row)[:2]
            ]
            positions = list(dict.fromkeys(
                re.findall(r'<span position="[^"]+" class="position [^"]+">([^<]+)</span>', row)
            ))
            name = html.unescape(link.group(2)).strip()

            players[self.normalize_name(name)] = {
                'fm_inside_id': int(link.group(1)),
                'rating': ratings[0] if ratings else 50,
                'potential': ratings[1] if len(ratings) > 1 else (ratings[0] if ratings else 50),
                'positions': positions,
            }

        return players

    def extract_transfermarkt_squad(self, page, marker):
        marker_index = page.find(marker)
        table_start = page.rfind('<tbody>', 0, marker_index)
        table_end = page.find('</tbody>', marker_index) + len('</tbody>')
        table = page[table_start:table_end]
        rows = re.split(r'<tr class="(?:odd|even)">', table)[1:]

        players = []
        for row in rows:
            link = re.search(
                r'<a href="([^"]+/profil/spieler/(\d+))"[^>]*>\s*(.*?)\s*</a>',
                row,
                re.S,
            )
            if not link:
                continue

            position_match = re.search(
                r'<td>\s*([^<]+?)\s*</td>\s*</tr>\s*</table>',
                row,
                re.S,
            )
            birth_match = re.search(
                r'<td class="zentriert">(\d{2}\.\d{2}\.\d{4}) \((\d+)\)</td>',
                row,
            )
            value_match = re.search(
                r'<td class="rechts hauptlink"><a href="([^"]+)">(.*?)</a></td>',
                row,
                re.S,
            )
            centered_cells = re.findall(r'<td class="zentriert">(.*?)</td>', row, re.S)

            flag_names = []
            for image_match in re.finditer(r'<img[^>]+class="flaggenrahmen"[^>]*>', row):
                tag = image_match.group(0)
                flag_match = re.search(r'(?:title|alt)="([^"]+)"', tag)
                if flag_match:
                    flag_names.append(html.unescape(flag_match.group(1)))

            profile_path = link.group(1)
            market_value_path = value_match.group(1) if value_match else ''

            players.append({
                'transfermarkt_id': int(link.group(2)),
                'name': self.clean_html(link.group(3)),
                'transfermarkt_profile_url': f"https://www.transfermarkt.de{profile_path}",
                'transfermarkt_market_value_url': (
                    f"https://www.transfermarkt.de{market_value_path}"
                    if market_value_path
                    else ''
                ),
                'primary_position': (
                    self.clean_html(position_match.group(1))
                    if position_match
                    else ''
                ),
                'date_of_birth': self.parse_date(birth_match.group(1)) if birth_match else None,
                'age': int(birth_match.group(2)) if birth_match else 0,
                'nationalities': list(dict.fromkeys(flag_names)),
                'contract_until': self.parse_date(
                    self.clean_html(centered_cells[-1])
                    if centered_cells
                    else ''
                ),
                'market_value': self.parse_transfermarkt_money(
                    self.clean_html(value_match.group(2))
                    if value_match
                    else ''
                ),
            })

        return players

    def clean_html(self, raw):
        text = re.sub(r'<[^>]+>', ' ', raw)
        return re.sub(r'\s+', ' ', html.unescape(text)).strip()

    def parse_date(self, raw):
        raw = raw.strip()
        if raw == '-':
            return None

        match = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4})', raw)
        if not match:
            return None

        day, month, year = [int(part) for part in match.groups()]
        return date(year, month, day)

    def parse_transfermarkt_money(self, raw):
        suffix = ''
        if 'Mio.' in raw:
            suffix = 'Mio.'
        elif 'Tsd.' in raw:
            suffix = 'Tsd.'

        match = re.search(r'([0-9.,]+)', raw)
        if not match:
            return Decimal('0')

        amount = Decimal(match.group(1).replace('.', '').replace(',', '.'))
        if suffix == 'Mio.':
            amount *= Decimal('1000000')
        elif suffix == 'Tsd.':
            amount *= Decimal('1000')

        return amount

    def calculate_salary_per_match(self, market_value):
        return (market_value / Decimal('1000000')) * Decimal('5000')

    def normalize_name(self, name):
        normalized = unicodedata.normalize('NFKD', name)
        normalized = ''.join(
            char for char in normalized
            if not unicodedata.combining(char)
        )
        return re.sub(r'[^a-z0-9]+', '', normalized.lower())

    def find_fm_inside_player(self, players, name):
        normalized_name = self.normalize_name(name)
        if normalized_name in players:
            return players[normalized_name]

        parts = name.split()
        if len(parts) > 1:
            reversed_name = self.normalize_name(' '.join(reversed(parts)))
            if reversed_name in players:
                return players[reversed_name]

        return {}

    def split_name(self, name):
        parts = name.split()
        if len(parts) == 1:
            return parts[0], ''
        return parts[0], ' '.join(parts[1:])
