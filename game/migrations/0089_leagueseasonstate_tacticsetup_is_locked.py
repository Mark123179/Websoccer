from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0088_seasonfixture_simulated_match'),
    ]

    operations = [
        migrations.AddField(
            model_name='tacticsetup',
            name='is_locked',
            field=models.BooleanField(
                default=False,
                verbose_name='Gesperrt',
                help_text='Taktik während laufender Spieltagssimulation gesperrt.',
            ),
        ),
        migrations.CreateModel(
            name='LeagueSeasonState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('season', models.CharField(default='0', max_length=20, verbose_name='Saison')),
                ('current_matchday', models.PositiveSmallIntegerField(default=1, verbose_name='Aktiver Spieltag')),
                ('is_simulated', models.BooleanField(
                    default=False,
                    verbose_name='Simuliert',
                    help_text='Alle Spiele des aktiven Spieltags wurden simuliert.',
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('league', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='season_states',
                    to='game.league',
                    verbose_name='Liga',
                )),
            ],
            options={
                'verbose_name': 'Liga-Saison-Status',
                'verbose_name_plural': 'Liga-Saison-Status',
                'unique_together': {('league', 'season')},
            },
        ),
    ]
