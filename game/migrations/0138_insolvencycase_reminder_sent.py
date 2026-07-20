from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0137_fix_financematchdayrun_typ_backfill'),
    ]

    operations = [
        migrations.AddField(
            model_name='insolvencycase',
            name='reminder_sent',
            field=models.BooleanField(
                default=False,
                help_text='Wird gesetzt, sobald die 1–2-Tage-Erinnerungs-News erzeugt wurde.',
                verbose_name='Erinnerung gesendet',
            ),
        ),
    ]
