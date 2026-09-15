from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0181_managertimelineentry_ticket_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='cupfixture',
            name='away_manager',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cup_away_fixtures',
                to='game.managerprofile',
                verbose_name='Auswärtsmanager zum Spielzeitpunkt',
            ),
        ),
        migrations.AddField(
            model_name='cupfixture',
            name='home_manager',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cup_home_fixtures',
                to='game.managerprofile',
                verbose_name='Heimmanager zum Spielzeitpunkt',
            ),
        ),
        migrations.AddField(
            model_name='managertimelineentry',
            name='source_key',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='managertimelineentry',
            name='source_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='managertimelineentry',
            name='system_entry',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='managertimelineentry',
            name='tone_override',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddConstraint(
            model_name='managertimelineentry',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('source_type__isnull', False),
                    ('source_key__isnull', False),
                ),
                fields=('source_type', 'source_key'),
                name='unique_manager_timeline_source',
            ),
        ),
    ]