from django.db import migrations


CLUB_GEO_DATA = {
    '1. FC Heidenheim':         (48.68,  10.15, 'Heidenheim an der Brenz', 'Deutschland'),
    '1. FC Union Berlin':       (52.46,  13.57, 'Berlin',                   'Deutschland'),
    '1. FSV Mainz 05':          (49.98,   8.25, 'Mainz',                    'Deutschland'),
    'Bayer 04 Leverkusen':      (51.03,   7.00, 'Leverkusen',               'Deutschland'),
    'Borussia Dortmund':        (51.49,   7.45, 'Dortmund',                 'Deutschland'),
    'Borussia Mönchengladbach': (51.17,   6.44, 'Mönchengladbach',          'Deutschland'),
    'Eintracht Frankfurt':      (50.07,   8.64, 'Frankfurt am Main',        'Deutschland'),
    'FC Augsburg':              (48.32,  10.89, 'Augsburg',                 'Deutschland'),
    'FC Bayern München':        (48.22,  11.55, 'München',                  'Deutschland'),
    'FC St. Pauli':             (53.55,   9.97, 'Hamburg',                  'Deutschland'),
    'Holstein Kiel':            (54.32,  10.14, 'Kiel',                     'Deutschland'),
    'RB Leipzig':               (51.35,  12.37, 'Leipzig',                  'Deutschland'),
    'SC Freiburg':              (47.98,   7.89, 'Freiburg im Breisgau',     'Deutschland'),
    'SV Werder Bremen':         (53.07,   8.84, 'Bremen',                   'Deutschland'),
    'TSG 1899 Hoffenheim':      (49.24,   8.89, 'Sinsheim',                 'Deutschland'),
    'VfB Stuttgart':            (48.79,   9.23, 'Stuttgart',                'Deutschland'),
    'VfL Bochum':               (51.49,   7.24, 'Bochum',                   'Deutschland'),
    'VfL Wolfsburg':            (52.43,  10.80, 'Wolfsburg',                'Deutschland'),
}


def populate_coords(apps, schema_editor):
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')
    for profile in ClubPublicProfile.objects.select_related('club').all():
        data = CLUB_GEO_DATA.get(profile.club.name)
        if data:
            lat, lng, city, country = data
            profile.map_lat = lat
            profile.map_lng = lng
            if not profile.city_name:
                profile.city_name = city
            if not profile.city_country:
                profile.city_country = country
            profile.save()


def unpopulate_coords(apps, schema_editor):
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')
    ClubPublicProfile.objects.all().update(map_lat=None, map_lng=None)


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0055_clubpublicprofile_map_coords'),
    ]

    operations = [
        migrations.RunPython(populate_coords, unpopulate_coords),
    ]
