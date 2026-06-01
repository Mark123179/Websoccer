import datetime
from django.db import migrations


SAMPLE_CAREER = [
    {
        'order': 1,
        'club_fm_id': 27,
        'club_name_fallback': 'FC Augsburg',
        'city_name': 'Augsburg',
        'city_country': 'Deutschland',
        'map_x': 270,
        'map_y': 220,
        'started_at': datetime.date(2019, 7, 1),
        'ended_at': datetime.date(2021, 6, 30),
        'games_played': 74,
    },
    {
        'order': 2,
        'club_fm_id': 17,
        'club_name_fallback': 'Eintracht Frankfurt',
        'city_name': 'Frankfurt',
        'city_country': 'Deutschland',
        'map_x': 248,
        'map_y': 190,
        'started_at': datetime.date(2021, 7, 1),
        'ended_at': datetime.date(2023, 6, 30),
        'games_played': 88,
    },
    {
        'order': 3,
        'club_fm_id': 915,
        'club_name_fallback': 'FC Bayern München',
        'city_name': 'München',
        'city_country': 'Deutschland',
        'map_x': 271,
        'map_y': 214,
        'started_at': datetime.date(2023, 8, 15),
        'ended_at': None,
        'games_played': 0,
    },
]


def seed_career_stations(apps, schema_editor):
    ManagerProfile = apps.get_model('game', 'ManagerProfile')
    ManagerCareerStation = apps.get_model('game', 'ManagerCareerStation')
    Club = apps.get_model('game', 'Club')

    manager = ManagerProfile.objects.filter(name='Kirschgutzje').first()
    if not manager:
        return

    if ManagerCareerStation.objects.filter(manager=manager).exists():
        return

    for entry in SAMPLE_CAREER:
        club = (
            Club.objects.filter(fm_inside_id=entry['club_fm_id']).first()
            or Club.objects.filter(name__icontains=entry['club_name_fallback']).first()
        )
        ManagerCareerStation.objects.create(
            manager=manager,
            club=club,
            order=entry['order'],
            city_name=entry['city_name'],
            city_country=entry['city_country'],
            map_x=entry['map_x'],
            map_y=entry['map_y'],
            started_at=entry['started_at'],
            ended_at=entry['ended_at'],
            games_played=entry['games_played'],
        )


def unseed_career_stations(apps, schema_editor):
    ManagerProfile = apps.get_model('game', 'ManagerProfile')
    ManagerCareerStation = apps.get_model('game', 'ManagerCareerStation')
    manager = ManagerProfile.objects.filter(name='Kirschgutzje').first()
    if manager:
        ManagerCareerStation.objects.filter(manager=manager).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0036_add_manager_career_station'),
    ]

    operations = [
        migrations.RunPython(seed_career_stations, unseed_career_stations),
    ]
