from django.db import migrations


def forwards(apps, schema_editor):
    """Bestandsdaten auf CMTracker konsolidieren (reine Identitäts-Umbenennung)."""
    DataSource = apps.get_model('game', 'DataSource')
    PlayerSourceRating = apps.get_model('game', 'PlayerSourceRating')
    SourceImportRun = apps.get_model('game', 'SourceImportRun')

    DataSource.objects.filter(code='SOFIFA').update(code='CMTRACKER', name='CMTracker')
    PlayerSourceRating.objects.filter(source='EA').update(source='CMTRACKER')
    SourceImportRun.objects.filter(source='sofifa').update(source='cmtracker')


def backwards(apps, schema_editor):
    DataSource = apps.get_model('game', 'DataSource')
    PlayerSourceRating = apps.get_model('game', 'PlayerSourceRating')
    SourceImportRun = apps.get_model('game', 'SourceImportRun')

    DataSource.objects.filter(code='CMTRACKER').update(code='SOFIFA', name='SoFIFA')
    PlayerSourceRating.objects.filter(source='CMTRACKER').update(source='EA')
    SourceImportRun.objects.filter(source='cmtracker').update(source='sofifa')


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0099_alter_datasource_code_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
