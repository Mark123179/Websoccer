from django.db import migrations

_OLD_PATH_TO_CDN = {
    'game/images/flags/5.svg': 'https://flagcdn.com/dz.svg',
    'game/images/flags/1651.svg': 'https://flagcdn.com/br.svg',
    'game/images/flags/771.svg': 'https://flagcdn.com/de.svg',
    'game/images/flags/24.svg': 'https://flagcdn.com/ci.svg',
    'game/images/flags/765.svg': 'https://flagcdn.com/gb-eng.svg',
    'game/images/flags/769.svg': 'https://flagcdn.com/fr.svg',
    'game/images/flags/20.svg': 'https://flagcdn.com/gm.svg',
    'game/images/flags/22.svg': 'https://flagcdn.com/gn.svg',
    'game/images/flags/23.svg': 'https://flagcdn.com/gw.svg',
    'game/images/flags/789.svg': 'https://flagcdn.com/ie.svg',
    'game/images/flags/776.svg': 'https://flagcdn.com/it.svg',
    'game/images/flags/116.svg': 'https://flagcdn.com/jp.svg',
    'game/images/flags/364.svg': 'https://flagcdn.com/ca.svg',
    'game/images/flags/1653.svg': 'https://flagcdn.com/co.svg',
    'game/images/flags/761.svg': 'https://flagcdn.com/hr.svg',
    'game/images/flags/27.svg': 'https://flagcdn.com/lr.svg',
    'game/images/flags/28.svg': 'https://flagcdn.com/ly.svg',
    'game/images/flags/38.svg': 'https://flagcdn.com/ng.svg',
    'game/images/flags/786.svg': 'https://flagcdn.com/no.svg',
    'game/images/flags/755.svg': 'https://flagcdn.com/at.svg',
    'game/images/flags/788.svg': 'https://flagcdn.com/pt.svg',
    'game/images/flags/797.svg': 'https://flagcdn.com/se.svg',
    'game/images/flags/798.svg': 'https://flagcdn.com/ch.svg',
    'game/images/flags/41.svg': 'https://flagcdn.com/sn.svg',
    'game/images/flags/802.svg': 'https://flagcdn.com/rs.svg',
    'game/images/flags/135.svg': 'https://flagcdn.com/kr.svg',
    'game/images/flags/799.svg': 'https://flagcdn.com/tr.svg',
    'game/images/flags/390.svg': 'https://flagcdn.com/us.svg',
}


def migrate_flag_urls(apps, schema_editor):
    ManagerProfile = apps.get_model('game', 'ManagerProfile')
    old_paths = list(_OLD_PATH_TO_CDN.keys())
    profiles = ManagerProfile.objects.filter(nationality_flag__in=old_paths)
    to_update = []
    for profile in profiles.iterator():
        cdn_url = _OLD_PATH_TO_CDN.get(profile.nationality_flag)
        if cdn_url:
            profile.nationality_flag = cdn_url
            to_update.append(profile)
    if to_update:
        ManagerProfile.objects.bulk_update(to_update, ['nationality_flag'])


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0045_seed_intercontinental_cup_other_clubs'),
    ]

    operations = [
        migrations.RunPython(migrate_flag_urls, migrations.RunPython.noop),
    ]
