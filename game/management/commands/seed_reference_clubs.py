import calendar
import html
import re
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
        'city': 'Dortmund',
        'url': 'https://fminside.net/clubs/7-fm-26/907-borussia-dortmund',
    },
    {
        'name': 'FC Bayern München',
        'short_name': 'FCB',
        'fm_inside_id': 915,
        'founded_year': 1900,
        'city': 'München',
        'url': 'https://fminside.net/clubs/7-fm-26/915-fc-bayern',
    },
]


POSITION_MAP = {
    'GK': 'TW',
    'DC': 'IV',
    'DL': 'LV',
    'WBL': 'LV',
    'DR': 'RV',
    'WBR': 'RV',
    'DM': 'ZDM',
    'MC': 'ZM',
    'AMC': 'ZOM',
    'ML': 'LF',
    'AML': 'LF',
    'MR': 'RF',
    'AMR': 'RF',
    'ST': 'ST',
}

POSITION_PRIORITY = [
    'GK',
    'ST',
    'DC',
    'DL',
    'DR',
    'WBL',
    'WBR',
    'DM',
    'MC',
    'AMC',
    'AML',
    'AMR',
    'ML',
    'MR',
]


class Command(BaseCommand):
    help = 'Seed Borussia Dortmund and FC Bayern from FMInside reference data.'

    def handle(self, *args, **options):
        league, _ = League.objects.get_or_create(
            name='1. Bundesliga',
            defaults={'country': 'Deutschland'},
        )

        for club_data in REFERENCE_CLUBS:
            page = self.fetch_page(club_data['url'])
            budget = self.extract_budget(page)
            players = self.extract_full_squad(page)

            duplicate_clubs = Club.objects.filter(
                name=club_data['name'],
                fm_inside_id__isnull=True,
            )
            Player.objects.filter(club__in=duplicate_clubs).delete()
            duplicate_clubs.delete()

            club, _ = Club.objects.update_or_create(
                fm_inside_id=club_data['fm_inside_id'],
                defaults={
                    'name': club_data['name'],
                    'short_name': club_data['short_name'],
                    'founded_year': club_data['founded_year'],
                    'budget': budget,
                    'league': league,
                },
            )

            Player.objects.filter(club=club).delete()

            for player_data in players:
                first_name, last_name = self.split_name(player_data['name'])
                player, _ = Player.objects.update_or_create(
                    fm_inside_id=player_data['fm_inside_id'],
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'age': player_data['age'],
                        'position': self.map_position(player_data['positions']),
                        'source_positions': ', '.join(player_data['positions']),
                        'potential': player_data['potential'],
                        'market_value': player_data['market_value'],
                        'market_value_note': player_data['market_value_note'],
                        'weekly_wage': player_data['weekly_wage'],
                        'contract_until': player_data['contract_until'],
                        'club': club,
                    },
                )
                PlayerStrengthProfile.objects.update_or_create(
                    player=player,
                    defaults={
                        'base_strength': player_data['rating'],
                        'form_modifier': 0,
                    },
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"{club.name}: {len(players)} Spieler mit FMInside-IDs geladen."
                )
            )

    def fetch_page(self, url):
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=30) as response:
            return response.read().decode('utf-8', errors='replace')

    def extract_budget(self, page):
        match = re.search(r'Balance</span>\s*<span[^>]*>(.*?)</span>', page, re.S)
        if not match:
            match = re.search(r'Balance\s*&euro;([0-9]+)\s*<acronym title="Million">M</acronym>', page)
        if not match:
            return Decimal('0')

        return self.parse_money(self.clean_html(match.group(1)))

    def extract_full_squad(self, page):
        section = page.split('<h2>Full Squad</h2>', 1)[1]
        section = section.split('<h2>', 1)[0]
        rows = re.findall(r'<ul class="player">(.*?)</ul>', section, flags=re.S)

        players = []
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
            age_match = re.search(r'<li class="age">(\d+)</li>', row)
            contract_match = re.search(r'<li class="contract">([^<]+)</li>', row)
            wage_match = re.search(r'<li class="wage">(.*?)</li>', row, re.S)
            value_match = re.search(
                r'<li class="value".*?<span class="price">(.*?)</span>',
                row,
                re.S,
            )
            positions = list(dict.fromkeys(
                re.findall(r'<span position="[^"]+" class="position [^"]+">([^<]+)</span>', row)
            ))

            value_note = self.clean_html(value_match.group(1)) if value_match else ''

            players.append({
                'fm_inside_id': int(link.group(1)),
                'name': html.unescape(link.group(2)).strip(),
                'rating': ratings[0] if ratings else 50,
                'potential': ratings[1] if len(ratings) > 1 else (ratings[0] if ratings else 50),
                'age': int(age_match.group(1)) if age_match else 0,
                'positions': positions,
                'market_value': self.parse_value_range(value_note),
                'market_value_note': value_note,
                'weekly_wage': self.parse_money(
                    self.clean_html(wage_match.group(1)) if wage_match else ''
                ),
                'contract_until': self.parse_contract_date(
                    contract_match.group(1) if contract_match else ''
                ),
            })

        return players

    def clean_html(self, raw):
        text = raw.replace('&euro;', '€')
        text = re.sub(r'<acronym title="Million">M</acronym>', 'M', text)
        text = re.sub(r'<acronym title="Thousand">K</acronym>', 'K', text)
        text = re.sub(r'<[^>]+>', '', text)
        return html.unescape(text).strip()

    def parse_money(self, raw):
        raw = raw.replace(' ', '').replace(',', '.')
        match = re.search(r'€?([0-9.]+)([MK]?)', raw)
        if not match:
            return Decimal('0')

        amount = Decimal(match.group(1))
        suffix = match.group(2)
        if suffix == 'M':
            amount *= Decimal('1000000')
        elif suffix == 'K':
            amount *= Decimal('1000')

        return amount

    def parse_value_range(self, raw):
        values = [self.parse_money(part) for part in raw.split('-') if part.strip()]
        if not values:
            return Decimal('0')
        return sum(values) / Decimal(len(values))

    def parse_contract_date(self, raw):
        raw = raw.strip()
        match = re.fullmatch(r'(\d{2})-(\d{4})', raw)
        if not match:
            return None

        month = int(match.group(1))
        year = int(match.group(2))
        return date(year, month, calendar.monthrange(year, month)[1])

    def map_position(self, positions):
        for source_position in POSITION_PRIORITY:
            if source_position in positions:
                return POSITION_MAP[source_position]
        return 'ZM'

    def split_name(self, name):
        parts = name.split()
        if len(parts) == 1:
            return parts[0], ''
        return parts[0], ' '.join(parts[1:])
