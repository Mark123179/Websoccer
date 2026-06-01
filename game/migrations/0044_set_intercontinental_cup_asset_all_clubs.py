from django.db import migrations


def set_intercontinental_cup_asset_all_clubs(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    ClubTrophy = apps.get_model('game', 'ClubTrophy')

    bayern = Club.objects.filter(fm_inside_id=915).first()
    if bayern:
        ClubTrophy.objects.get_or_create(
            club=bayern,
            competition_name='Intercontinental',
            defaults={
                'count': 1,
                'trophy_asset_id': 'international-cup-1',
                'sort_order': 6,
            },
        )

    ClubTrophy.objects.filter(
        competition_name='Intercontinental',
        trophy_asset_id='',
    ).update(trophy_asset_id='international-cup-1')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0043_backfill_name_confirmed'),
    ]

    operations = [
        migrations.RunPython(set_intercontinental_cup_asset_all_clubs, noop_reverse),
    ]
