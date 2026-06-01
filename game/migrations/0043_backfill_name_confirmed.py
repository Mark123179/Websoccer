from django.db import migrations


def backfill_name_confirmed(apps, schema_editor):
    ManagerProfile = apps.get_model('game', 'ManagerProfile')
    updated = (
        ManagerProfile.objects
        .filter(user__isnull=False, name_confirmed=False)
        .exclude(name=None)
    )
    to_confirm = [p for p in updated if p.user and p.name != p.user.username]
    for profile in to_confirm:
        profile.name_confirmed = True
    if to_confirm:
        ManagerProfile.objects.bulk_update(to_confirm, ['name_confirmed'])


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0042_add_name_confirmed_to_manager_profile'),
    ]

    operations = [
        migrations.RunPython(backfill_name_confirmed, migrations.RunPython.noop),
    ]
