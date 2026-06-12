from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0089_leagueseasonstate_tacticsetup_is_locked'),
    ]

    operations = [
        migrations.AddField(
            model_name='simulatedmatch',
            name='match_type',
            field=models.CharField(
                choices=[('freundschaft', 'Freundschaftsspiel'), ('pokal', 'Pokal')],
                default='freundschaft',
                max_length=20,
                verbose_name='Spieltyp',
            ),
        ),
    ]
