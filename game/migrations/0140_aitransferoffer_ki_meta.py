from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0139_forcedauctionbid_ki_meta'),
    ]

    operations = [
        migrations.AddField(
            model_name='aitransferoffer',
            name='ki_meta',
            field=models.JSONField(
                blank=True,
                null=True,
                verbose_name='KI-Bewertungsdetails',
                help_text=(
                    'Nur bei KI-Angeboten gesetzt. Enthält: max_gebot (KI-Schmerzgrenzen-'
                    'Maximum), schmerzgrenze, gegenwartswert, zukunftswert (alle in €), '
                    'kernspieler (bool).'
                ),
            ),
        ),
    ]
