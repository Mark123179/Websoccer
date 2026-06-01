from django.db import migrations


def seed_club_trophies(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    ClubTrophy = apps.get_model('game', 'ClubTrophy')

    bayern = Club.objects.filter(fm_inside_id=915).first()
    dortmund = Club.objects.filter(fm_inside_id=907).first()

    bayern_trophies = [
        ('Bundesliga', 33, '22', 0),
        ('DFB-Pokal', 20, '1301410', 1),
        ('Champions League', 6, '1301394', 2),
        ('Supercup', 10, '1301397', 3),
        ('Klub-WM', 2, '1001959', 4),
        ('Ligapokal', 6, '100', 5),
    ]

    dortmund_trophies = [
        ('Bundesliga', 8, '22', 0),
        ('DFB-Pokal', 5, '1301410', 1),
        ('Champions League', 1, '1301394', 2),
        ('Supercup', 5, '1301397', 3),
        ('Ligapokal', 3, '100', 4),
    ]

    if bayern:
        for competition_name, count, trophy_asset_id, sort_order in bayern_trophies:
            ClubTrophy.objects.update_or_create(
                club=bayern,
                competition_name=competition_name,
                defaults={
                    'count': count,
                    'trophy_asset_id': trophy_asset_id,
                    'sort_order': sort_order,
                },
            )

    if dortmund:
        for competition_name, count, trophy_asset_id, sort_order in dortmund_trophies:
            ClubTrophy.objects.update_or_create(
                club=dortmund,
                competition_name=competition_name,
                defaults={
                    'count': count,
                    'trophy_asset_id': trophy_asset_id,
                    'sort_order': sort_order,
                },
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0033_add_match_result'),
    ]

    operations = [
        migrations.RunPython(seed_club_trophies, noop_reverse),
    ]
