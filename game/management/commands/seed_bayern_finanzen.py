from django.core.management.base import BaseCommand
from datetime import date, timedelta
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

        # (day_offset, category_key, description, amount)
        transactions = [
            (0,   'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 1',           4_200_000),
            (3,   'transfer_einnahme','Transfererlös: Mazraoui → Man City',                  24_000_000),
            (5,   'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 2',           4_350_000),
            (7,   'profigehalt',      'Spielergehälter Juli 2024',                          -18_500_000),
            (10,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 3',           4_100_000),
            (12,  'transfer_ausgabe', 'Transfer: Michael Olise ← Crystal Palace',          -53_000_000),
            (14,  'sponsor',          'Sponsorenzahlung Q1 – Allianz Arena',                  8_750_000),
            (18,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 4',           4_400_000),
            (21,  'profigehalt',      'Spielergehälter August 2024',                        -18_500_000),
            (23,  'transfer_ausgabe', 'Transfer: João Palhinha ← Fulham',                  -51_000_000),
            (25,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 5',           4_250_000),
            (28,  'praemie',          'UEFA Champions League – Antrittsprämie',             15_640_000),
            (30,  'ticketverkauf',    'Champions League Gruppenspiel Einnahmen',              5_800_000),
            (33,  'profigehalt',      'Spielergehälter September 2024',                    -18_500_000),
            (35,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 6',           4_500_000),
            (38,  'sonstige_ausgabe', 'Stadionwartung & Infrastruktur Q1',                   -2_100_000),
            (40,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 7',           4_300_000),
            (42,  'ticketverkauf',    'Champions League Gruppenspiel Einnahmen',              5_900_000),
            (45,  'profigehalt',      'Spielergehälter Oktober 2024',                       -18_500_000),
            (47,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 8',           4_200_000),
            (49,  'sponsor',          'Sponsorenzahlung Q2 – T-Mobile Trikot-Deal',          12_500_000),
            (52,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 9',           4_450_000),
            (54,  'praemie',          'CL Gruppenphase abgeschlossen – Prämie',               6_400_000),
            (55,  'profigehalt',      'Spielergehälter November 2024',                      -18_500_000),
            (58,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 10',          4_350_000),
            (60,  'sonstige_ausgabe', 'Marketing & Werbung Q2',                              -1_800_000),
            (62,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 11',          4_600_000),
            (65,  'profigehalt',      'Spielergehälter Dezember 2024',                      -18_500_000),
            (67,  'tv_gelder',        'TV-Einnahmen Q2 – Adidas Partnerschaft',             15_000_000),
            (70,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 12',          4_200_000),
            (72,  'transfer_einnahme','Transfererlös: Gravenberch → Liverpool',             18_500_000),
            (75,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 13',          4_350_000),
            (77,  'sonstige_ausgabe', 'Jugendakademie & Nachwuchspflege',                    -3_200_000),
            (80,  'profigehalt',      'Spielergehälter Januar 2025',                        -18_500_000),
            (82,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 14',          4_100_000),
            (85,  'praemie',          'CL Achtelfinale – Prämie',                             9_600_000),
            (87,  'ticketverkauf',    'Champions League Achtelfinale Einnahmen',              6_200_000),
            (90,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 15',          4_400_000),
            (92,  'profigehalt',      'Spielergehälter Februar 2025',                       -18_500_000),
            (94,  'sponsor',          'Sponsorenzahlung Q3 – Allianz Namensrecht',            8_750_000),
            (97,  'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 16',          4_250_000),
            (100, 'sonstige_ausgabe', 'Stadionwartung & Infrastruktur Q3',                   -2_300_000),
            (102, 'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 17',          4_500_000),
            (105, 'profigehalt',      'Spielergehälter März 2025',                          -18_500_000),
            (107, 'praemie',          'CL Viertelfinale – Prämie',                           12_500_000),
            (110, 'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 18',          4_300_000),
            (112, 'ticketverkauf',    'Champions League Viertelfinale Einnahmen',             7_100_000),
            (115, 'profigehalt',      'Spielergehälter April 2025',                         -18_500_000),
            (117, 'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 19',          4_400_000),
            (119, 'sonstige_ausgabe', 'Musiala Vertragsverlängerung Bonus',                  -8_000_000),
            (121, 'sponsor',          'Sponsorenzahlung Q3 – T-Mobile',                     12_500_000),
            (124, 'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 20',          4_450_000),
            (126, 'praemie',          'CL Halbfinale – Prämie',                              15_000_000),
            (128, 'ticketverkauf',    'Champions League Halbfinale Einnahmen',                8_400_000),
            (130, 'profigehalt',      'Spielergehälter Mai 2025',                           -18_500_000),
            (133, 'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 21',          4_200_000),
            (135, 'sonstige_ausgabe', 'Verwaltung & Betrieb Q4',                             -1_600_000),
            (137, 'praemie',          'Bundesliga-Meisterprämie DFL',                         4_500_000),
            (139, 'ticketverkauf',    'Spieltagseinnahmen – Bundesliga Spieltag 22',          4_300_000),
            (141, 'tv_gelder',        'TV-Einnahmen Q4 – Jahresabschluss',                  15_000_000),
            (143, 'profigehalt',      'Spielergehälter Juni 2025',                          -18_500_000),
            (145, 'sonstige_ausgabe', 'Jugendakademie Jahresbudget Abschluss',               -4_000_000),
        ]

        objs = []
        for day_offset, category, description, amount in transactions:
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
            ('Allianz',       'tv',        72_000_000),
            ('T-Mobile',      'trikot',    60_000_000),
            ('Adidas',        'ausrüster', 75_000_000),
            ('Audi',          'haupt',     45_000_000),
            ('Qatar Airways', 'sonstig',   22_000_000),
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
