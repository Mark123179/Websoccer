from django.db import migrations


def add_explicit_roofs(apps, schema_editor):
    StadiumGeometry = apps.get_model('stadium_editor', 'StadiumGeometry')
    from stadium_editor.seed import build_explicit_roofs

    for row in StadiumGeometry.objects.all().iterator():
        geometry = build_explicit_roofs(row.geometry)
        if geometry != row.geometry:
            row.geometry = geometry
            row.schema_version = max(row.schema_version, 2)
            row.save(update_fields=['geometry', 'schema_version'])


class Migration(migrations.Migration):
    dependencies = [
        ('stadium_editor', '0004_upgrade_design_contract_v2'),
    ]

    operations = [
        migrations.RunPython(add_explicit_roofs, migrations.RunPython.noop),
    ]