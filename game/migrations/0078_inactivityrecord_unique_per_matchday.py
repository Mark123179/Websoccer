from django.db import migrations, models


def deduplicate_inactivity_records(apps, schema_editor):
    """Keep only the earliest record for each (manager, club, squad_scope, season, matchday_label) tuple."""
    InactivityRecord = apps.get_model('game', 'InactivityRecord')

    seen = {}
    to_delete = []

    for record in InactivityRecord.objects.order_by('recorded_at'):
        key = (
            record.manager_id,
            record.club_id,
            record.squad_scope,
            record.season,
            record.matchday_label,
        )
        if key in seen:
            to_delete.append(record.pk)
        else:
            seen[key] = record.pk

    if to_delete:
        InactivityRecord.objects.filter(pk__in=to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0077_seasonfixture_lineup_malus'),
    ]

    operations = [
        migrations.RunPython(
            deduplicate_inactivity_records,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='inactivityrecord',
            constraint=models.UniqueConstraint(
                fields=['manager', 'club', 'squad_scope', 'season', 'matchday_label'],
                name='unique_inactivity_record_per_matchday',
            ),
        ),
    ]
