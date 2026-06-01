from django.db import migrations


def set_intercontinental_cup_asset(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    ClubTrophy = apps.get_model('game', 'ClubTrophy')

    dortmund = Club.objects.filter(fm_inside_id=907).first()
    if dortmund:
        ClubTrophy.objects.filter(
            club=dortmund,
            competition_name='Intercontinental',
            trophy_asset_id='',
        ).update(trophy_asset_id='international-cup-1')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0040_managercareerstation_custom_club_name'),
    ]

    operations = [
        migrations.RunPython(set_intercontinental_cup_asset, noop_reverse),
    ]
