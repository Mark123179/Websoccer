from django.db import migrations


COMPETITION_ASSET_MAP = {
    # Continental / global
    'Copa Libertadores':   '1002136',
    'Europa League':       '1001960',
    # England
    'Premier League':      '1301393',
    'FA Cup':              '1301406',
    # Spain
    'La Liga':             '1301395',
    'Copa del Rey':        '1301417',
    'Supercopa de España': '1301419',
    # Italy
    'Serie A':             '1301398',
    'Coppa Italia':        '1301407',
    # Netherlands
    'Eredivisie':          '1301412',
    'KNVB Cup':            '1301411',
    # Portugal
    'Primeira Liga':       '1301403',
    'Taça de Portugal':    '1301404',
    # Serbia
    'Superliga Srbije':    '1301427',
    'Kup Srbije':          '1301426',
    # South America — no confirmed FM Inside badge IDs; keep generic assets
    'Brasileirão':         'national championship 1',
    'Copa do Brasil':      'national cup 1',
    'Taça Brasil':         'national cup 1',
    'Primera División':    'national championship 1',
    'Copa Argentina':      'national cup 1',
    'Copa Uruguay':        'national cup 1',
    'División de Honor':   'national championship 1',
    'Copa Paraguay':       'national cup 1',
}


def update_trophy_asset_ids(apps, schema_editor):
    ClubTrophy = apps.get_model('game', 'ClubTrophy')
    for competition_name, asset_id in COMPETITION_ASSET_MAP.items():
        ClubTrophy.objects.filter(competition_name=competition_name).update(
            trophy_asset_id=asset_id,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0048_alter_managerprofile_nationality_flag_default'),
    ]

    operations = [
        migrations.RunPython(update_trophy_asset_ids, noop_reverse),
    ]
