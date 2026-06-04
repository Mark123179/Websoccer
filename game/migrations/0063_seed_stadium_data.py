from django.db import migrations
from decimal import Decimal


STADIUM_DATA = [
    # (club_name, stadium_name, city, total_capacity)
    # Capacity distribution per stand:
    #   Nord: fan curve  — ~25%, 70% standing / 30% seating / 0% VIP
    #   Ost:  east stand — ~25%, 0% standing / 100% seating / 0% VIP
    #   Süd:  south      — ~25%, 15% standing / 85% seating / 0% VIP
    #   West: main stand — ~25%, 0% standing / 82% seating / 18% VIP
    ('Bayern München',          'Allianz Arena',           'München',           75024),
    ('Borussia Dortmund',       'Signal Iduna Park',        'Dortmund',          81365),
    ('Bayer Leverkusen',        'BayArena',                 'Leverkusen',        30210),
    ('RB Leipzig',              'Red Bull Arena',           'Leipzig',           47069),
    ('Eintracht Frankfurt',     'Deutsche Bank Park',       'Frankfurt',         58000),
    ('VfB Stuttgart',           'MHP Arena',                'Stuttgart',         60441),
    ('Borussia Mönchengladbach','Borussia-Park',            'Mönchengladbach',   54042),
    ('SC Freiburg',             'Europa-Park Stadion',      'Freiburg',          35000),
    ('Werder Bremen',           'Weserstadion',             'Bremen',            42100),
    ('VfL Wolfsburg',           'Volkswagen Arena',         'Wolfsburg',         30000),
    ('TSG Hoffenheim',          'PreZero Arena',            'Sinsheim',          30150),
    ('FC Augsburg',             'WWK Arena',                'Augsburg',          30660),
    ('VfL Bochum',              'Vonovia Ruhrstadion',      'Bochum',            27599),
    ('1. FC Union Berlin',      'An der Alten Försterei',   'Berlin',            22012),
    ('1. FSV Mainz 05',         'MEWA Arena',               'Mainz',             33305),
    ('1. FC Heidenheim 1846',   'Voith-Arena',              'Heidenheim',        15000),
    ('Holstein Kiel',           'Holstein-Stadion',         'Kiel',              15034),
    ('FC St. Pauli',            'Millerntor-Stadion',       'Hamburg',           29546),
    ('FC Basel 1893',           'St. Jakob-Park',           'Basel',             38512),
    ('Valencia CF',             'Estadio Mestalla',         'Valencia',          49430),
]


def _distribute(total):
    """
    Split total capacity across 4 stands × 3 seat types.
    Returns dict of field_name → int value.
    """
    q = total // 4

    nord_total = q
    ost_total  = q
    sued_total = q
    west_total = total - 3 * q  # absorbs rounding remainder

    nord_standing = round(nord_total * 0.70)
    nord_seating  = nord_total - nord_standing
    nord_vip      = 0

    ost_standing  = 0
    ost_seating   = ost_total
    ost_vip       = 0

    sued_standing = round(sued_total * 0.15)
    sued_seating  = sued_total - sued_standing
    sued_vip      = 0

    west_vip      = round(west_total * 0.18)
    west_standing = 0
    west_seating  = west_total - west_vip

    return dict(
        nord_standing=nord_standing, nord_seating=nord_seating, nord_vip=nord_vip,
        ost_standing=ost_standing,   ost_seating=ost_seating,   ost_vip=ost_vip,
        sued_standing=sued_standing, sued_seating=sued_seating, sued_vip=sued_vip,
        west_standing=west_standing, west_seating=west_seating, west_vip=west_vip,
    )


def seed_stadiums(apps, schema_editor):
    Club   = apps.get_model('game', 'Club')
    Stadium = apps.get_model('game', 'Stadium')

    for club_name, stadium_name, city, capacity in STADIUM_DATA:
        try:
            club = Club.objects.get(name=club_name)
        except Club.DoesNotExist:
            print(f'  [WARN] Club not found: {club_name!r} — skipping')
            continue

        if Stadium.objects.filter(club=club).exists():
            print(f'  [SKIP] Stadium already exists for {club_name}')
            continue

        caps = _distribute(capacity)
        Stadium.objects.create(
            club=club,
            name=stadium_name,
            city=city,
            lawn_quality=85,
            price_standing=Decimal('15.00'),
            price_seating=Decimal('35.00'),
            price_vip=Decimal('120.00'),
            **caps,
        )
        print(f'  [OK] {stadium_name} ({capacity:,}) → {club_name}')


def remove_stadiums(apps, schema_editor):
    Stadium = apps.get_model('game', 'Stadium')
    Stadium.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0062_stadium_model'),
    ]

    operations = [
        migrations.RunPython(seed_stadiums, remove_stadiums),
    ]
