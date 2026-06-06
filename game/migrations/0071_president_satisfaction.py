from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0070_coin_transaction'),
    ]

    operations = [
        migrations.CreateModel(
            name='PresidentSatisfaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.PositiveSmallIntegerField(
                    default=100,
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(100),
                    ],
                    verbose_name='Zufriedenheit (0\u2013100)',
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('club', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='president_satisfactions',
                    to='game.club',
                    verbose_name='Verein',
                )),
                ('manager', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='president_satisfactions',
                    to='game.managerprofile',
                    verbose_name='Manager',
                )),
            ],
            options={
                'verbose_name': 'Pr\xe4sident-Zufriedenheit',
                'verbose_name_plural': 'Pr\xe4sident-Zufriedenheiten',
                'ordering': ['value', '-updated_at'],
                'unique_together': {('manager', 'club')},
            },
        ),
        migrations.CreateModel(
            name='ManagerAtRisk',
            fields=[
            ],
            options={
                'verbose_name': 'Entlassungskandidat',
                'verbose_name_plural': 'Entlassungskandidaten (Zufriedenheit 0\u202f%)',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('game.presidentsatisfaction',),
        ),
    ]
