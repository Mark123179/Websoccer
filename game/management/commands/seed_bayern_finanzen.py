from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import random
from game.models import Club, ClubFinancialTransaction, ClubSponsor


class Command(BaseCommand):
    help = 'Seed dummy Finanzen data for FC Bayern München'

    def handle(self, *args, **kwargs):
        try:
            bayern = Club.objects.get(id=2)
        except Club.DoesNotExist:
            self.stderr.write('FC Bayern nicht gefunden (id=2)')
            return

        SEASON = 0

        ClubFinancialTransaction.objects.filter(club=bayern, season=SEASON).delete()
        ClubSponsor.objects.filter(club=bayern, season=SEASON).delete()
        self.stdout.write('Alte Daten gelöscht.')

        base = date(2024, 7, 1)

        transactions = [
            (0,   'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 1',        4_200_000),
            (3,   'TRANSFER',  'Einnahmen',  'Transfererlös: Mazraoui → Man City',               24_000_000),
            (5,   'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 2',        4_350_000),
            (7,   'SALARY',    'Ausgaben',   'Spielergehälter Juli 2024',                        -18_500_000),
            (10,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 3',        4_100_000),
            (12,  'TRANSFER',  'Ausgaben',   'Transfer: Michael Olise ← Crystal Palace',        -53_000_000),
            (14,  'SPONSOR',   'Einnahmen',  'Sponsorenzahlung Q1 – Allianz Arena',               8_750_000),
            (18,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 4',        4_400_000),
            (21,  'SALARY',    'Ausgaben',   'Spielergehälter August 2024',                     -18_500_000),
            (23,  'TRANSFER',  'Ausgaben',   'Transfer: João Palhinha ← Fulham',                -51_000_000),
            (25,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 5',        4_250_000),
            (28,  'CL',        'Einnahmen',  'UEFA Champions League – Antrittsprämie',           15_640_000),
            (30,  'TICKET',    'Einnahmen',  'Champions League Gruppenspiel Einnahmen',           5_800_000),
            (33,  'SALARY',    'Ausgaben',   'Spielergehälter September 2024',                  -18_500_000),
            (35,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 6',        4_500_000),
            (38,  'SONSTIGES', 'Ausgaben',   'Stadionwartung & Infrastruktur Q1',                -2_100_000),
            (40,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 7',        4_300_000),
            (42,  'TICKET',    'Einnahmen',  'Champions League Gruppenspiel Einnahmen',           5_900_000),
            (45,  'SALARY',    'Ausgaben',   'Spielergehälter Oktober 2024',                    -18_500_000),
            (47,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 8',        4_200_000),
            (49,  'SPONSOR',   'Einnahmen',  'Sponsorenzahlung Q2 – T-Mobile Trikot-Deal',       12_500_000),
            (52,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 9',        4_450_000),
            (54,  'CL',        'Einnahmen',  'CL Gruppenphase abgeschlossen – Prämie',            6_400_000),
            (55,  'SALARY',    'Ausgaben',   'Spielergehälter November 2024',                   -18_500_000),
            (58,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 10',       4_350_000),
            (60,  'SONSTIGES', 'Ausgaben',   'Marketing & Werbung Q2',                           -1_800_000),
            (62,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 11',       4_600_000),
            (65,  'SALARY',    'Ausgaben',   'Spielergehälter Dezember 2024',                   -18_500_000),
            (67,  'SPONSOR',   'Einnahmen',  'Sponsorenzahlung Q2 – Adidas Ausrüsterdeal',       15_000_000),
            (70,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 12',       4_200_000),
            (72,  'TRANSFER',  'Einnahmen',  'Transfererlös: Gravenberch → Liverpool',           18_500_000),
            (75,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 13',       4_350_000),
            (77,  'SONSTIGES', 'Ausgaben',   'Jugendakademie & Nachwuchspflege',                 -3_200_000),
            (80,  'SALARY',    'Ausgaben',   'Spielergehälter Januar 2025',                     -18_500_000),
            (82,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 14',       4_100_000),
            (85,  'CL',        'Einnahmen',  'CL Achtelfinale – Prämie',                          9_600_000),
            (87,  'TICKET',    'Einnahmen',  'Champions League Achtelfinale Einnahmen',           6_200_000),
            (90,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 15',       4_400_000),
            (92,  'SALARY',    'Ausgaben',   'Spielergehälter Februar 2025',                    -18_500_000),
            (94,  'SPONSOR',   'Einnahmen',  'Sponsorenzahlung Q3 – Allianz Namensrecht',         8_750_000),
            (97,  'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 16',       4_250_000),
            (100, 'SONSTIGES', 'Ausgaben',   'Stadionwartung & Infrastruktur Q3',                -2_300_000),
            (102, 'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 17',       4_500_000),
            (105, 'SALARY',    'Ausgaben',   'Spielergehälter März 2025',                       -18_500_000),
            (107, 'CL',        'Einnahmen',  'CL Viertelfinale – Prämie',                        12_500_000),
            (110, 'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 18',       4_300_000),
            (112, 'TICKET',    'Einnahmen',  'Champions League Viertelfinale Einnahmen',          7_100_000),
            (115, 'SALARY',    'Ausgaben',   'Spielergehälter April 2025',                      -18_500_000),
            (117, 'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 19',       4_400_000),
            (119, 'TRANSFER',  'Ausgaben',   'Transfer: Jamal Musiala Vertragsverlängerung Bonus', -8_000_000),
            (121, 'SPONSOR',   'Einnahmen',  'Sponsorenzahlung Q3 – T-Mobile',                  12_500_000),
            (124, 'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 20',       4_450_000),
            (126, 'CL',        'Einnahmen',  'CL Halbfinale – Prämie',                           15_000_000),
            (128, 'TICKET',    'Einnahmen',  'Champions League Halbfinale Einnahmen',             8_400_000),
            (130, 'SALARY',    'Ausgaben',   'Spielergehälter Mai 2025',                        -18_500_000),
            (133, 'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 21',       4_200_000),
            (135, 'SONSTIGES', 'Ausgaben',   'Verwaltung & Betrieb Q4',                          -1_600_000),
            (137, 'MEISTER',   'Einnahmen',  'Bundesliga-Meisterprämie DFL',                     4_500_000),
            (139, 'TICKET',    'Einnahmen',  'Spieltagseinnahmen – Bundesliga Spieltag 22',       4_300_000),
            (141, 'SPONSOR',   'Einnahmen',  'Sponsorenzahlung Q4 – Adidas Jahresabschluss',     15_000_000),
            (143, 'SALARY',    'Ausgaben',   'Spielergehälter Juni 2025',                       -18_500_000),
            (145, 'SONSTIGES', 'Ausgaben',   'Jugendakademie Jahresbudget Abschluss',             -4_000_000),
        ]

        objs = []
        for day_offset, category, _, description, amount in transactions:
            objs.append(ClubFinancialTransaction(
                club=bayern,
                date=base + timedelta(days=day_offset),
                season=SEASON,
                category=category,
                description=description,
                amount=amount,
            ))
        ClubFinancialTransaction.objects.bulk_create(objs)
        self.stdout.write(f'{len(objs)} Transaktionen eingefügt.')

        sponsors = [
            ('Allianz',         'TV',       72_000_000),
            ('T-Mobile',        'TRIKOT',   60_000_000),
            ('Adidas',          'AUSRUESTER', 75_000_000),
            ('Audi',            'HAUPT',    45_000_000),
            ('Qatar Airways',   'SONSTIGES', 22_000_000),
        ]
        sponsor_objs = []
        for name, stype, amount in sponsors:
            sponsor_objs.append(ClubSponsor(
                club=bayern,
                name=name,
                sponsor_type=stype,
                amount_per_season=amount,
                season=SEASON,
                is_active=True,
            ))
        ClubSponsor.objects.bulk_create(sponsor_objs)
        self.stdout.write(f'{len(sponsor_objs)} Sponsoren eingefügt.')
        self.stdout.write(self.style.SUCCESS('Dummy-Daten für FC Bayern erfolgreich eingefügt!'))
