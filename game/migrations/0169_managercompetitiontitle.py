import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0168_rename_manager_active_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='leagueseasonstate',
            name='champion_club',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='completed_league_seasons', to='game.club', verbose_name='Meister dieser Saison'),
        ),
        migrations.AddField(
            model_name='leagueseasonstate',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Saison abgeschlossen am'),
        ),
        migrations.CreateModel(
            name='ManagerCompetitionTitle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('competition_name', models.CharField(max_length=120)),
                ('season', models.CharField(max_length=20)),
                ('won_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('club', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='manager_competition_titles', to='game.club')),
                ('competition', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='manager_titles', to='game.league')),
                ('manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='competition_titles', to='game.managerprofile')),
            ],
            options={
                'verbose_name': 'Persönlicher Manager-Titel',
                'verbose_name_plural': 'Persönliche Manager-Titel',
                'ordering': ['-won_at', '-id'],
                'constraints': [
                    models.UniqueConstraint(fields=('competition', 'season'), name='unique_manager_title_competition_season'),
                ],
            },
        ),
    ]