"""
Ergänzt Stadion-Stammdaten für die 8 Vereine, die in 0063 wegen
abweichender DB-Namen übersprungen wurden.
"""
from django.db import migrations
from decimal import Decimal


STADIUM_DATA = [
    # (club_name_in_db, stadion_name, stadt, gesamtkapazität)
    ('FC Bayern München',    'Allianz Arena',        'München',        75024),
    ('Bayer 04 Leverkusen',  'BayArena',             'Leverkusen',     30210),
    ('SV Werder Bremen',     'Weserstadion',         'Bremen',         42100),
    ('TSG 1899 Hoffenheim',  'PreZero Arena',        'Sinsheim',       30150),
    ('1. FC Heidenheim',     'Voith-Arena',          'Heidenheim',     15000),
    ('FC Basel',             'St. Jakob-Park',       'Basel',          38512),
    ('FC Valencia',          'Estadio Mestalla',     'Valencia',       49430),
]


def _verteile(gesamt):
    """
    Verteilt die Gesamtkapazität auf 4 Tribünen × 3 Platztypen.
    Nord (Kurve):  70 % Steh, 30 % Sitz, 0 % VIP
    Ost (Gegengerade): 100 % Sitz
    Süd (Südkurve): 15 % Steh, 85 % Sitz
    West (Haupttribüne): 18 % VIP, Rest Sitz
    """
    q = gesamt // 4

    nord_gesamt = q
    ost_gesamt  = q
    sued_gesamt = q
    west_gesamt = gesamt - 3 * q  # nimmt den Rest

    nord_steh = round(nord_gesamt * 0.70)
    nord_sitz = nord_gesamt - nord_steh
    nord_vip  = 0

    ost_steh  = 0
    ost_sitz  = ost_gesamt
    ost_vip   = 0

    sued_steh = round(sued_gesamt * 0.15)
    sued_sitz = sued_gesamt - sued_steh
    sued_vip  = 0

    west_vip  = round(west_gesamt * 0.18)
    west_steh = 0
    west_sitz = west_gesamt - west_vip

    return dict(
        nord_standing=nord_steh, nord_seating=nord_sitz, nord_vip=nord_vip,
        ost_standing=ost_steh,   ost_seating=ost_sitz,   ost_vip=ost_vip,
        sued_standing=sued_steh, sued_seating=sued_sitz, sued_vip=sued_vip,
        west_standing=west_steh, west_seating=west_sitz, west_vip=west_vip,
    )


def stadien_anlegen(apps, schema_editor):
    Club    = apps.get_model('game', 'Club')
    Stadium = apps.get_model('game', 'Stadium')

    for club_name, stadion_name, stadt, kapazitaet in STADIUM_DATA:
        try:
            club = Club.objects.get(name=club_name)
        except Club.DoesNotExist:
            print(f'  [WARNUNG] Verein nicht gefunden: {club_name!r} — übersprungen')
            continue

        if Stadium.objects.filter(club=club).exists():
            print(f'  [ÜBERSPRINGEN] Stadion bereits vorhanden: {club_name}')
            continue

        plaetze = _verteile(kapazitaet)
        Stadium.objects.create(
            club=club,
            name=stadion_name,
            city=stadt,
            lawn_quality=85,
            price_standing=Decimal('15.00'),
            price_seating=Decimal('35.00'),
            price_vip=Decimal('120.00'),
            **plaetze,
        )
        print(f'  [OK] {stadion_name} ({kapazitaet:,} Plätze) → {club_name}')


def stadien_loeschen(apps, schema_editor):
    Club    = apps.get_model('game', 'Club')
    Stadium = apps.get_model('game', 'Stadium')
    namen   = [row[0] for row in STADIUM_DATA]
    Stadium.objects.filter(club__name__in=namen).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0063_seed_stadium_data'),
    ]

    operations = [
        migrations.RunPython(stadien_anlegen, stadien_loeschen),
    ]
