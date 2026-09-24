from django.db import migrations


def discard_legacy_dortmund_design(apps, schema_editor):
    # Old Dortmund stand IDs were model-local. The user elected to discard
    # the existing 2D design rather than remap its paint and viewpoint.
    design = apps.get_model('stadium_editor', 'StadiumDesign')
    design.objects.using(schema_editor.connection.alias).filter(
        stadium__club_id=3,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [('stadium_editor', '0007_stadiumgeometry_steckbrief')]

    operations = [
        migrations.RunPython(discard_legacy_dortmund_design, migrations.RunPython.noop),
    ]