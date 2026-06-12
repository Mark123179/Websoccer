from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0087_simulated_match'),
    ]

    operations = [
        migrations.AddField(
            model_name='seasonfixture',
            name='simulated_match',
            field=models.OneToOneField(
                blank=True,
                help_text='Verlinkter SimulatedMatch-Eintrag mit V2-Report-Daten.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='season_fixture',
                to='game.simulatedmatch',
                verbose_name='Spielbericht (V2)',
            ),
        ),
    ]
