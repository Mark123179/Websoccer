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
            ('DFL-Supercup', 10, '1301397', 3),
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
            ('DFL-Supercup', 5, '1301397', 3),
            ('Ligapokal', 3, '100', 4),
        ],
        'news': [
            ('Guirassy trifft erneut im Training mit Weltklasse-Form', date(2026, 5, 25), 0),
            ('BVB verlängert Partnerschaft mit Hauptsponsor', date(2026, 5, 24), 1),
            ('Vorbereitung auf neue Saison läuft auf Hochtouren', date(2026, 5, 23), 2),
        ],
    },
    {
        'fm_inside_id': 901,
        'profile': {
            'stadium_name': 'BayArena',
            'stadium_capacity': 30210,
            'average_attendance': 28500,
            'city_name': 'Leverkusen',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/b-leverkusen.jpg',
            'city_image_static_path': 'game/images/city/901.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('Bundesliga', 1, '22', 0),
            ('DFB-Pokal', 2, '1301410', 1),
            ('DFL-Supercup', 1, '1301397', 2),
        ],
        'news': [
            ('Wirtz glänzt im Abschlusstraining vor dem Derby', date(2026, 5, 25), 0),
            ('Bayer 04 plant Kaderausbau für die Champions League', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 91013388,
        'profile': {
            'stadium_name': 'Red Bull Arena',
            'stadium_capacity': 47069,
            'average_attendance': 43000,
            'city_name': 'Leipzig',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/redbull-leipzig.jpg',
            'city_image_static_path': 'game/images/city/91013388.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('DFB-Pokal', 2, '1301410', 0),
        ],
        'news': [
            ('Sesko überzeugt Trainer mit starken Leistungen im Testspiel', date(2026, 5, 25), 0),
            ('RB Leipzig verlängert mit Schlüsselspielern bis 2028', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 912,
        'profile': {
            'stadium_name': 'Deutsche Bank Park',
            'stadium_capacity': 58000,
            'average_attendance': 52000,
            'city_name': 'Frankfurt',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/e-frankfurt.jpg',
            'city_image_static_path': 'game/images/city/912.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('Bundesliga', 1, '22', 0),
            ('DFB-Pokal', 5, '1301410', 1),
            ('Europa League', 2, '1301395', 2),
        ],
        'news': [
            ('Eintracht Frankfurt startet mit neuem Trikot in die Saison', date(2026, 5, 25), 0),
            ('Larsson als neuer Mittelfeldanker bestätigt', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 960,
        'profile': {
            'stadium_name': 'MHPArena',
            'stadium_capacity': 60441,
            'average_attendance': 55000,
            'city_name': 'Stuttgart',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/stuttgart.jpg',
            'city_image_static_path': 'game/images/city/960.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('Bundesliga', 5, '22', 0),
            ('DFB-Pokal', 3, '1301410', 1),
            ('DFL-Supercup', 3, '1301397', 2),
        ],
        'news': [
            ('Nübel überzeugt in der Vorbereitung auf die neue Spielzeit', date(2026, 5, 25), 0),
            ('VfB Stuttgart verlängert mit Mittelfeld-Talent', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 944,
        'profile': {
            'stadium_name': 'Europa-Park Stadion',
            'stadium_capacity': 34700,
            'average_attendance': 33200,
            'city_name': 'Freiburg',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/freiburg.jpg',
            'city_image_static_path': 'game/images/city/944.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('DFB-Pokal', 0, '1301410', 0),
        ],
        'news': [
            ('SC Freiburg setzt weiter auf Nachwuchstalente aus der eigenen Akademie', date(2026, 5, 25), 0),
            ('Atubolu verlängert Vertrag bis 2028', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 908,
        'profile': {
            'stadium_name': 'Borussia-Park',
            'stadium_capacity': 54067,
            'average_attendance': 48000,
            'city_name': 'Mönchengladbach',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/b-gladbach.jpg',
            'city_image_static_path': 'game/images/city/908.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('Bundesliga', 5, '22', 0),
            ('DFB-Pokal', 3, '1301410', 1),
            ('UEFA-Pokal', 2, '1301395', 2),
            ('DFL-Supercup', 7, '1301397', 3),
        ],
        'news': [
            ('Gladbach startet Kaderplanung für die neue Saison', date(2026, 5, 25), 0),
            ('Fans feiern 125-jähriges Vereinsjubiläum', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 879226,
        'profile': {
            'stadium_name': 'PreZero Arena',
            'stadium_capacity': 30150,
            'average_attendance': 28000,
            'city_name': 'Sinsheim',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/hoffenheim.jpg',
            'city_image_static_path': 'game/images/city/879226.jpg',
            'partner_club': None,
        },
        'trophies': [],
        'news': [
            ('Hoffenheim holt Nachwuchsspieler aus der eigenen Akademie', date(2026, 5, 25), 0),
            ('TSG-Trainer lobt Teamgeist in der Vorbereitung', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 961,
        'profile': {
            'stadium_name': 'Volkswagen Arena',
            'stadium_capacity': 30000,
            'average_attendance': 27000,
            'city_name': 'Wolfsburg',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/wolfsburg.jpg',
            'city_image_static_path': 'game/images/city/961.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('Bundesliga', 1, '22', 0),
            ('DFB-Pokal', 1, '1301410', 1),
        ],
        'news': [
            ('Wolfsburg präsentiert neuen Cheftrainer', date(2026, 5, 25), 0),
            ('Grabara verlängert Vertrag beim VfL bis 2027', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 948,
        'profile': {
            'stadium_name': 'wohninvest WESERSTADION',
            'stadium_capacity': 42100,
            'average_attendance': 40000,
            'city_name': 'Bremen',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/werder.jpg',
            'city_image_static_path': 'game/images/city/948.jpg',
            'partner_club': None,
        },
        'trophies': [
            ('Bundesliga', 4, '22', 0),
            ('DFB-Pokal', 6, '1301410', 1),
            ('DFL-Supercup', 3, '1301397', 2),
            ('UEFA-Pokal', 1, '1301395', 3),
        ],
        'news': [
            ('Ducksch führt Werder als Kapitän in die neue Saison', date(2026, 5, 25), 0),
            ('SVW plant Ausbau der Weserkurve für 2027', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 2238,
        'profile': {
            'stadium_name': 'WWK Arena',
            'stadium_capacity': 30660,
            'average_attendance': 27500,
            'city_name': 'Augsburg',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/augsburg.jpg',
            'city_image_static_path': 'game/images/city/2238.jpg',
            'partner_club': None,
        },
        'trophies': [],
        'news': [
            ('FC Augsburg verlängert mit Stammtorhüter Dahmen', date(2026, 5, 25), 0),
            ('Augsburg startet Saisonvorbereitung im Trainingslager', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 918,
        'profile': {
            'stadium_name': 'Mewa Arena',
            'stadium_capacity': 33305,
            'average_attendance': 31000,
            'city_name': 'Mainz',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/mainz.jpg',
            'city_image_static_path': 'game/images/city/918.jpg',
            'partner_club': None,
        },
        'trophies': [],
        'news': [
            ('Mainz 05 baut auf Kontinuität im Kader für die neue Saison', date(2026, 5, 25), 0),
            ('Stach als Leitwolf bestätigt — Verlängerung perfekt', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 121182,
        'profile': {
            'stadium_name': 'Stadion An der Alten Försterei',
            'stadium_capacity': 22012,
            'average_attendance': 21500,
            'city_name': 'Berlin',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/union berlin.jpg',
            'city_image_static_path': 'game/images/city/121182.jpg',
            'partner_club': None,
        },
        'trophies': [],
        'news': [
            ('Union Berlin feiert Meilenstein: 10 Jahre in Folge Erstklassigkeit', date(2026, 5, 25), 0),
            ('Alte Försterei erhält neues Flutlichtsystem', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 905,
        'profile': {
            'stadium_name': 'Vonovia Ruhrstadion',
            'stadium_capacity': 27599,
            'average_attendance': 25000,
            'city_name': 'Bochum',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/bochum.jpg',
            'city_image_static_path': 'game/images/city/905.jpg',
            'partner_club': None,
        },
        'trophies': [],
        'news': [
            ('VfL Bochum plant Verstärkungen für den Klassenerhalt', date(2026, 5, 25), 0),
            ('Drewes verlängert — Rückhalt für die kommende Saison gesichert', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 880295,
        'profile': {
            'stadium_name': 'Voith-Arena',
            'stadium_capacity': 15000,
            'average_attendance': 14200,
            'city_name': 'Heidenheim an der Brenz',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/heidenheim.jpg',
            'city_image_static_path': 'game/images/city/880295.jpg',
            'partner_club': None,
        },
        'trophies': [],
        'news': [
            ('Heidenheim schreibt Geschichte: Zweite Bundesliga-Saison in Folge', date(2026, 5, 25), 0),
            ('Sessa verlängert Vertrag und bleibt dem FCH erhalten', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 2245,
        'profile': {
            'stadium_name': 'Holstein-Stadion',
            'stadium_capacity': 15034,
            'average_attendance': 13500,
            'city_name': 'Kiel',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/holstein kiel.jpg',
            'city_image_static_path': 'game/images/city/2245.jpg',
            'partner_club': None,
        },
        'trophies': [],
        'news': [
            ('Holstein Kiel feiert Bundesliga-Premiere mit ausverkauftem Stadion', date(2026, 5, 25), 0),
            ('Machino verlängert und bleibt das Gesicht des KSV', date(2026, 5, 24), 1),
        ],
    },
    {
        'fm_inside_id': 946,
        'profile': {
            'stadium_name': 'Millerntor-Stadion',
            'stadium_capacity': 29546,
            'average_attendance': 28000,
            'city_name': 'Hamburg',
            'city_country': 'Deutschland',
            'stadium_image_static_path': 'game/images/stadiums/germany/st pauli.jpg',
            'city_image_static_path': 'game/images/city/946.jpg',
            'partner_club': None,
        },
        'trophies': [],
        'news': [
            ('FC St. Pauli stärkt Kiezidentität mit neuem Community-Projekt', date(2026, 5, 25), 0),
            ('Wahl bleibt Kapitän — Vertrag bis 2027 verlängert', date(2026, 5, 24), 1),
        ],
    },
]


class Command(BaseCommand):
    help = (
        'Seed ClubPublicProfile, ClubTrophy und ClubNewsItem '
        'für alle 18 Bundesliga-Clubs. Idempotent (update_or_create).'
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
