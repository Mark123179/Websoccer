"""Seeds für Finanzsystem Phase 2 (Einnahmen komplett).

1. League.level: '2. Bundesliga' → Ebene 2 (alle anderen bleiben 1).
2. LandKoeffizient: reale UEFA-5-Jahreswertungen als Seed-Zeile in
   Saison "0" (eine Zeile = komplette 5-Jahres-Summe, Spec Kap. 7.1).
   Rangfolge entspricht der Spec-Tabelle Kap. 7.2.
3. VereinKoeffizient: reale UEFA-Vereins-5-Jahreswertungen (gerundet)
   für vorhandene Vereine — Zuordnung per Vereinsname, fehlende Vereine
   werden übersprungen (= 0 Punkte, landen am Tabellenende des
   Koeffanteils).
4. Neue EconomyParameter (Saison "0"): PRAEMIE_INTL (Kap. 8.2),
   Sponsor-Kalibrierwerte (Kap. 6.2).
"""
from django.db import migrations

SAISON = '0'

LAND_KOEFF = {
    'England': '96.629',
    'Spanien': '86.541',
    'Deutschland': '84.310',
    'Italien': '82.897',
    'Frankreich': '70.247',
    'Portugal': '59.366',
    'Niederlande': '58.100',
    'Schweiz': '43.900',
    'Österreich': '39.550',
}

VEREIN_KOEFF = {
    'FC Bayern München': '138.250',
    'Borussia Dortmund': '106.750',
    'Bayer 04 Leverkusen': '81.000',
    'RB Leipzig': '78.000',
    'Eintracht Frankfurt': '74.000',
    'SC Freiburg': '36.000',
    'VfL Wolfsburg': '29.000',
    'VfB Stuttgart': '18.000',
    'TSG 1899 Hoffenheim': '15.000',
    '1. FC Union Berlin': '14.000',
    'Borussia Mönchengladbach': '10.000',
    '1. FSV Mainz 05': '8.000',
    '1. FC Köln': '6.000',
    '1. FC Heidenheim 1846': '5.500',
    'SV Werder Bremen': '5.000',
    'Hertha BSC': '5.000',
    'FC Schalke 04': '4.500',
    'FC Augsburg': '4.000',
    'Hamburger SV': '3.000',
    'VfL Bochum': '2.000',
    'Hannover 96': '2.000',
    'FC St. Pauli': '2.000',
    'Fortuna Düsseldorf': '1.500',
    '1. FC Kaiserslautern': '1.500',
    '1. FC Nürnberg': '1.500',
    'Karlsruher SC': '1.000',
    'SC Paderborn 07': '1.000',
    'Holstein Kiel': '1.000',
    'SV Darmstadt 98': '1.000',
    'SpVgg Greuther Fürth': '1.000',
    'SV 07 Elversberg': '1.000',
}

PARAM_SEED = {
    # Kap. 8.2 — Internationale Prämien (fester Europatopf, € je Ereignis)
    'PRAEMIE_INTL': {
        'CL': {
            'start': 30000000, 'sieg': 2500000, 'remis': 800000,
            'achtelfinale': 12000000, 'viertelfinale': 15000000,
            'halbfinale': 20000000, 'finale': 25000000, 'titel': 30000000,
        },
        'EL': {
            'start': 7500000, 'sieg': 600000, 'remis': 200000,
            'achtelfinale': 3000000, 'viertelfinale': 3750000,
            'halbfinale': 5000000, 'finale': 6250000, 'titel': 7500000,
        },
    },
    # Kap. 6.2 — Fixanteil je Angebotstyp (Rest ist variabel)
    'SPONSOR_TYP_SPLIT': {
        'sicherheit': 1.0, 'sieggeld': 0.5,
        'zieljaeger': 0.6, 'zuschauer': 0.5,
    },
    # [KALIBRIERUNG] Erwartete Siegquote (Anteil der Ligaspiele) linear
    # interpoliert vom erwarteten Platz 1 bis zum letzten Platz.
    'SPONSOR_ERWARTETE_SIEGE': {'platz1': 0.72, 'letzter': 0.18},
    # [KALIBRIERUNG] Eintrittswahrscheinlichkeit des Zieljäger-Bonus
    # (Präsidenten-Ziel wird ungefähr in der Hälfte der Fälle erreicht).
    'SPONSOR_ZIEL_WAHRSCHEINLICHKEIT': 0.5,
    # Kap. 6.1 — Platzbonus(Vorsaison): Maximalbonus für Platz 1, linear
    # degressiv bis 0 für den letzten Platz. [KALIBRIERUNG]
    'SPONSOR_PLATZBONUS_MAX': 5000000,
    'SPONSOR_ANGEBOTE_ANZAHL': {'min': 3, 'max': 5},
}


def seed(apps, schema_editor):
    League = apps.get_model('game', 'League')
    LandKoeffizient = apps.get_model('game', 'LandKoeffizient')
    VereinKoeffizient = apps.get_model('game', 'VereinKoeffizient')
    Club = apps.get_model('game', 'Club')
    EconomyParameter = apps.get_model('game', 'EconomyParameter')

    League.objects.filter(name__istartswith='2. ').update(level=2)

    for land, punkte in LAND_KOEFF.items():
        LandKoeffizient.objects.update_or_create(
            land=land, saison=SAISON, defaults={'punkte': punkte},
        )

    for club_name, punkte in VEREIN_KOEFF.items():
        club = Club.objects.filter(name=club_name).first()
        if club is None:
            continue
        VereinKoeffizient.objects.update_or_create(
            club=club, saison=SAISON, defaults={'punkte': punkte},
        )

    for key, value in PARAM_SEED.items():
        EconomyParameter.objects.update_or_create(
            saison=SAISON, key=key, defaults={'value': value},
        )


def unseed(apps, schema_editor):
    League = apps.get_model('game', 'League')
    LandKoeffizient = apps.get_model('game', 'LandKoeffizient')
    VereinKoeffizient = apps.get_model('game', 'VereinKoeffizient')
    EconomyParameter = apps.get_model('game', 'EconomyParameter')

    League.objects.filter(name__istartswith='2. ').update(level=1)
    LandKoeffizient.objects.filter(saison=SAISON).delete()
    VereinKoeffizient.objects.filter(saison=SAISON).delete()
    EconomyParameter.objects.filter(
        saison=SAISON, key__in=list(PARAM_SEED),
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0122_seasonfinancestate_league_level_landkoeffizient_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
