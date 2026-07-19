"""Seed der EconomyParameter-Startwerte (Spec Kap. 2, Saison "0").

Werte mit [KALIBRIERUNG] sind bewusste Startschätzungen und werden nach
Launch über Monitoring nachgezogen (Spec Kap. 16).
"""
from django.db import migrations

SAISON = '0'

SEED = {
    # Kap. 4 — Gehälter
    'GEHALT_BASIS': 18.0,
    'GEHALT_PROGRESSION': 6.0,
    'GEHALT_DIVISOR': 40,
    'GEHALT_PROZENT_MIN': 12.0,
    'MEDIAN_DAEMPFUNG': 0.10,
    'MW_MINIMUM': 50000,
    'ABFINDUNG_KARRIEREENDE': 0,
    'ABFINDUNG_TOD': {
        '16-17': 6, '18-20': 5, '21-22': 4, '23-24': 3.5,
        '25-28': 3, '29-32': 2.5, '33+': 1.5,
    },
    # Kap. 5 — Stadion & Zuschauer
    'NACHFRAGE_KOEFF': 1414,
    'NACHFRAGE_EXP': 0.575,
    'PREIS_REFERENZ': {'steh': 18, 'sitz': 45, 'vip': 350},
    'PREIS_ELASTIZITAET': 0.35,
    'UNTERHALT_PLATZ': 40,
    'KOSTEN_BESUCHER': 5,
    'AUSBAU_BAENDER': [
        [20000, 1500], [40000, 2500], [60000, 3500],
        [80000, 5000], [100000, 7000], [120000, 9000],
    ],
    'AUSBAU_FAKTOR_KATEGORIE': {'steh': 0.6, 'sitz': 1.0, 'vip': 4.0},
    'STADION_MAX': 120000,
    # Kap. 6 — Sponsoren
    'SPONSOR_SOCKEL': {'liga1': 10000000, 'liga2': 3000000},
    'SPONSOR_MW_ANTEIL': 0.07,
    'SPONSOR_STREUUNG': 0.10,
    # Kap. 7 — TV-Gelder (Töpfe in € je Saison; Rang 6–9 interpoliert
    # innerhalb der Spec-Spanne 300–520 Mio)
    'TV_TOEPFE': {
        '1': 2200000000, '2': 1930000000, '3': 1700000000,
        '4': 1500000000, '5': 1320000000,
        '6': 520000000, '7': 440000000, '8': 370000000, '9': 300000000,
    },
    'TV_SPLIT_LIGA': {'liga1': 0.8, 'liga2': 0.2},
    'TV_VERTEILUNG': {'sockel': 0.5, 'platz': 0.3, 'koeff': 0.2},
    'FALLSCHIRM_QUOTE': 0.5,
    # Interim Phase 1: Land → Koeffizienten-Rang (bis echte
    # Landeskoeffizienten existieren, Kap. 7.1); unbekannte Länder → Rang 6.
    'TV_INTERIM_RANG_JE_LAND': {
        'Deutschland': 3, 'England': 1, 'Spanien': 2,
        'Italien': 4, 'Frankreich': 5,
    },
    # Kap. 8 — Prämien
    'POKAL_BASIS_ANTEIL': 0.00024,
    'POKAL_TITEL_FAKTOR': 30,
    'SUPERCUP_FAKTOR': {'sieger': 5, 'verlierer': 2.5},
    # Kap. 9 — Transfermarkt
    'AUSBILDUNGSABGABE': 0.05,
    'KADER_MAX_BASIS': 60,
    'KADER_MIN': 18,
    'SCHMERZGRENZE_KONSTANTEN': {
        'altersfaktor': {'u21': 1.6, '22-25': 1.3, '26-29': 1.0, '30+': 0.75},
        'realisierung': {'basis': 0.45, 'luecke_abzug': 0.002,
                         'alter_abzug': 0.015, 'min': 0.08, 'max': 0.45},
        'kernspieler_zuschlag': 1.5,
        'verkaeufer_marge': [1.1, 1.3],
        'eroeffnung_anteil': 0.7,
    },
    'KI_ANGEBOTS_KADENZ': {
        'offene_kaufangebote_je_ki': 1,
        'kaufangebote_je_fenster': 3,
        'offene_angebote_je_manager': 2,
        'angebote_je_manager_fenster': 4,
        'cooldown_tage': {'bedarf': 7, 'qualitaet': 14, 'talent': 'fensterende'},
        'gueltigkeit_stunden': 72,
    },
    # Kap. 10 — Betriebskosten
    'BETRIEBSQUOTE': 0.34,
    'BETRIEB_SOCKEL': 5000000,
    # Kap. 11 — Verband
    'VERBANDSABGABE_ENABLED': False,
    # Kap. 13 — Startbudgets
    'STARTBUDGET_QUOTE': 0.20,
    'STARTBUDGET_MIN': 3000000,
}


def seed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    for key, value in SEED.items():
        EconomyParameter.objects.update_or_create(
            saison=SAISON, key=key, defaults={'value': value},
        )


def unseed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(saison=SAISON, key__in=list(SEED)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0119_seasoneconomysnapshot_economyparameter_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
