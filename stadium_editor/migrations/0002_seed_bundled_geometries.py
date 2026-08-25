from django.db import migrations


def seed_bundled_geometries(apps, schema_editor):
    from stadium_editor.seed import seed_existing_stadiums

    Stadium = apps.get_model('game', 'Stadium')
    StadiumGeometry = apps.get_model('stadium_editor', 'StadiumGeometry')
    seed_existing_stadiums(Stadium.objects.select_related('club').all(), StadiumGeometry)


class Migration(migrations.Migration):
    dependencies = [
        ('stadium_editor', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_bundled_geometries, migrations.RunPython.noop),
    ]