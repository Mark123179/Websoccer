from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0134_snapshot_potential_median_200'),
    ]

    operations = [
        migrations.AddField(
            model_name='financetransaction',
            name='referenz_mw',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    'Marktwert des Spielers zum Buchungszeitpunkt (Snapshot). '
                    'Nur bei Transfer-Buchungen befüllt — ermöglicht historische '
                    'Ablöse/MW-Auswertung ohne Rekonstruktion.'
                ),
                max_digits=14,
                null=True,
                verbose_name='Marktwert-Snapshot (€)',
            ),
        ),
    ]
