from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0138_insolvencycase_reminder_sent'),
    ]

    operations = [
        migrations.AddField(
            model_name='forcedauctionbid',
            name='ki_meta',
            field=models.JSONField(
                blank=True,
                null=True,
                verbose_name='KI-Bewertungsdetails',
                help_text=(
                    'Nur bei KI-Geboten gesetzt. Enthält: max_gebot (KI-Schmerzgrenzen-'
                    'Maximum), schmerzgrenze, gegenwartswert, zukunftswert (alle in €), '
                    'kernspieler (bool), akute_positionen (Liste von Positions-Codes).'
                ),
            ),
        ),
    ]
