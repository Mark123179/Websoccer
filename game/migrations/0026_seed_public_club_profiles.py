from datetime import date

from django.db import migrations


def seed_public_club_profiles(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    ClubNewsItem = apps.get_model('game', 'ClubNewsItem')
    ClubProfileMatch = apps.get_model('game', 'ClubProfileMatch')
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')
    ClubTrophy = apps.get_model('game', 'ClubTrophy')

    bayern = Club.objects.filter(fm_inside_id=915).first()
    dortmund = Club.objects.filter(fm_inside_id=907).first()

    def club_id(club):
        return str(club.id) if club else ''

    profile_rows = [
        (
            bayern,
            {
                'stadium_name': 'Allianz Arena',
                'stadium_capacity': 75000,
                'average_attendance': 74100,
                'city_name': 'München',
                'city_country': 'Deutschland',
                'stadium_image_static_path': 'game/images/stadiums/germany/fc-bayern.jpg',
                'city_image_static_path': 'game/images/city/915.jpg',
                'partner_club': None,
            },
        ),
        (
            dortmund,
            {
                'stadium_name': 'Signal Iduna Park',
                'stadium_capacity': 81365,
                'average_attendance': 80300,
                'city_name': 'Dortmund',
                'city_country': 'Deutschland',
                'stadium_image_static_path': 'game/images/stadiums/germany/b-dortmund.jpg',
                'city_image_static_path': 'game/images/city/907.jpg',
                'partner_club': None,
            },
        ),
    ]

    for club, defaults in profile_rows:
        if club:
            ClubPublicProfile.objects.update_or_create(
                club=club,
                defaults=defaults,
            )

    trophy_rows = [
        ('Bundesliga', 33, '22'),
        ('DFB-Pokal', 20, '1301410'),
        ('Champions League', 6, '1301394'),
        ('Supercup', 10, '1301397'),
        ('Klub-WM', 2, '1001959'),
        ('Ligapokal', 6, '100'),
    ]
    for club in [bayern, dortmund]:
        if not club:
            continue
        for index, row in enumerate(trophy_rows):
            competition_name, count, trophy_asset_id = row
            ClubTrophy.objects.update_or_create(
                club=club,
                competition_name=competition_name,
                defaults={
                    'count': count if club == bayern else max(count // 2, 1),
                    'trophy_asset_id': trophy_asset_id,
                    'sort_order': index,
                },
            )

    match_rows = [
        (
            bayern,
            'next',
            {
                'competition_name': 'Bundesliga',
                'matchday_label': '34. Spieltag',
                'date_label': 'Sonntag, 25. Mai 2026',
                'time_label': '17:30 Uhr',
                'stadium_name': 'Allianz Arena',
                'home_club': bayern,
                'away_club': dortmund,
            },
        ),
        (
            bayern,
            'last',
            {
                'competition_name': 'Bundesliga',
                'matchday_label': '33. Spieltag',
                'home_club': bayern,
                'away_club': dortmund,
                'home_goals': 3,
                'away_goals': 1,
                'result_label': 'SIEG',
                'scorers': [
                    {'clubId': club_id(bayern), 'playerName': 'Kane', 'minute': 22},
                    {'clubId': club_id(bayern), 'playerName': 'Sané', 'minute': 61},
                    {'clubId': club_id(bayern), 'playerName': 'Musiala', 'minute': 75},
                    {'clubId': club_id(dortmund), 'playerName': 'Adeyemi', 'minute': 84},
                ],
            },
        ),
        (
            dortmund,
            'next',
            {
                'competition_name': 'Bundesliga',
                'matchday_label': '34. Spieltag',
                'date_label': 'Sonntag, 25. Mai 2026',
                'time_label': '17:30 Uhr',
                'stadium_name': 'Allianz Arena',
                'home_club': bayern,
                'away_club': dortmund,
            },
        ),
        (
            dortmund,
            'last',
            {
                'competition_name': 'Bundesliga',
                'matchday_label': '33. Spieltag',
                'home_club': bayern,
                'away_club': dortmund,
                'home_goals': 3,
                'away_goals': 1,
                'result_label': 'NIEDERLAGE',
                'scorers': [
                    {'clubId': club_id(bayern), 'playerName': 'Kane', 'minute': 22},
                    {'clubId': club_id(bayern), 'playerName': 'Sané', 'minute': 61},
                    {'clubId': club_id(bayern), 'playerName': 'Musiala', 'minute': 75},
                    {'clubId': club_id(dortmund), 'playerName': 'Adeyemi', 'minute': 84},
                ],
            },
        ),
    ]
    for club, kind, defaults in match_rows:
        if club:
            ClubProfileMatch.objects.update_or_create(
                club=club,
                kind=kind,
                defaults=defaults,
            )

    news_rows = [
        ('Kane wurde zum Spieler des Monats gewählt', date(2026, 5, 25), 0),
        ('Vertragsgespräche mit Musiala schreiten voran', date(2026, 5, 24), 1),
        ('Neue Stadionauslastung meldet Rekordwerte', date(2026, 5, 23), 2),
    ]
    for club in [bayern, dortmund]:
        if not club:
            continue
        for title, published_at, sort_order in news_rows:
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


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0025_clubnewsitem_clubpublicprofile_clubtrophy_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_public_club_profiles, noop_reverse),
    ]
