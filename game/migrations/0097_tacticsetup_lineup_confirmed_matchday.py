from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0096_clubplayerimportjob_validation_issues'),
    ]

    operations = [
        migrations.AddField(
            model_name='tacticsetup',
            name='lineup_confirmed_matchday',
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name='Bestätigt für Spieltag',
                help_text='Spieltagnummer, für die der Manager die Aufstellung zuletzt bestätigt hat.',
            ),
        ),
    ]
