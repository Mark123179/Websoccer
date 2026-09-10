from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0173_friendlyfixture_simulation_claim'),
    ]

    operations = [
        migrations.AddField(
            model_name='friendlyfixture',
            name='simulation_attempts',
            field=models.PositiveSmallIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name='friendlyfixture',
            name='next_simulation_attempt_at',
            field=models.DateTimeField(
                blank=True, db_index=True, editable=False, null=True,
            ),
        ),
        migrations.AddField(
            model_name='friendlyfixture',
            name='simulation_last_error',
            field=models.TextField(blank=True, default='', editable=False),
        ),
    ]