from datetime import date

from django.core.management.base import BaseCommand

from game.models import Club, ClubNewsItem, ClubPublicProfile, ClubTrophy


CLUB_PROFILES = [
    {
        'fm_inside_id': 915,
        'profile': {
            'stadium_name': 'Allianz Arena',
            'stadium_capacity': 75000,
            'average_attendance': 74100,
            'city_name': 'München',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/fc-bayern.jpg',
            'city_image_static_path': 'game/images/city/915.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('Bundesliga', 33, '22', 0),
            ('DFB-Pokal', 20, '1301410', 1),
            ('Champions League', 6, '1301394', 2),
            ('Supercup', 10, '1301397', 3),
            ('Klub-WM', 2, '1001959', 4),
            ('Ligapokal', 6, '100', 5),
        ],
        'news': [
            ('Kane wurde zum Spieler des Monats gewählt', date(2026, 5, 25), 0),
            ('Vertragsgespräche mit Musiala schreiten voran', date(2026, 5, 24), 1),
            ('Neue Stadionauslastung meldet Rekordwerte', date(2026, 5, 23), 2),
        ],
    },
    {
        'fm_inside_id': 907,
        'profile': {
            'stadium_name': 'Signal Iduna Park',
            'stadium_capacity': 81365,
            'average_attendance': 80300,
            'city_name': 'Dortmund',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/b-dortmund.jpg',
            'city_image_static_path': 'game/images/city/907.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('Bundesliga', 8, '22', 0),
            ('DFB-Pokal', 5, '1301410', 1),
            ('Champions League', 1, '1301394', 2),
            ('Supercup', 5, '1301397', 3),
            ('Ligapokal', 3, '100', 4),
        ],
        'news': [
            ('Kane wurde zum Spieler des Monats gewählt', date(2026, 5, 25), 0),
            ('Vertragsgespräche mit Musiala schreiten voran', date(2026, 5, 24), 1),
            ('Neue Stadionauslastung meldet Rekordwerte', date(2026, 5, 23), 2),
        ],
    },
]


class Command(BaseCommand):
    help = (
        'Seed ClubPublicProfile, ClubTrophy und ClubNewsItem '
        'für Bayern und Dortmund. Idempotent (update_or_create).'
    )

    def handle(self, *args, **options):
        for entry in CLUB_PROFILES:
            club = Club.objects.filter(fm_inside_id=entry['fm_inside_id']).first()
            if not club:
                self.stdout.write(
                    self.style.WARNING(
                        f"Club mit fm_inside_id={entry['fm_inside_id']} nicht gefunden — übersprungen."
                    )
                )
                continue

            ClubPublicProfile.objects.update_or_create(
                club=club,
                defaults=entry['profile'],
            )
            self.stdout.write(f"  Profil gesetzt: {club.name}")

            for competition_name, count, trophy_asset_id, sort_order in entry['trophies']:
                ClubTrophy.objects.update_or_create(
                    club=club,
                    competition_name=competition_name,
                    defaults={
                        'count': count,
                        'trophy_asset_id': trophy_asset_id,
                        'sort_order': sort_order,
                    },
                )
            self.stdout.write(f"  Trophäen: {len(entry['trophies'])} für {club.name}")

            for title, published_at, sort_order in entry['news']:
                thumbnail_static_path = (
                    f'game/images/crests/{club.fm_inside_id}.png'
                    if club.fm_inside_id
                    else ''
                )
                ClubNewsItem.objects.update_or_create(
                    club=club,
                    title=title,
                    defaults={
                        'published_at': published_at,
                        'thumbnail_static_path': thumbnail_static_path,
                        'sort_order': sort_order,
                    },
                )
            self.stdout.write(f"  News: {len(entry['news'])} für {club.name}")

        self.stdout.write(self.style.SUCCESS('seed_club_profiles abgeschlossen.'))
