from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0026_seed_public_club_profiles'),
    ]

    operations = [
        migrations.RunPython(noop, noop),
    ]
