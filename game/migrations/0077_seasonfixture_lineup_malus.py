from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0076_liga_standings_fixtures_news'),
    ]

    operations = [
        migrations.AddField(
            model_name='seasonfixture',
            name='home_lineup_malus',
            field=models.BooleanField(
                default=False,
                verbose_name='Heim-Stärkemalus (-20 %)',
                help_text='Automatisch gesetzt wenn der Heim-Manager keine Aufstellung gestellt hat.',
            ),
        ),
        migrations.AddField(
            model_name='seasonfixture',
            name='away_lineup_malus',
            field=models.BooleanField(
                default=False,
                verbose_name='Auswärts-Stärkemalus (-20 %)',
                help_text='Automatisch gesetzt wenn der Auswärts-Manager keine Aufstellung gestellt hat.',
            ),
        ),
    ]
