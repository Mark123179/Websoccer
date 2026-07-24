from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0145_rename_game_sponsor_bereich_aktiv_idx_game_sponso_bereich_7e9aac_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sponsoroffer',
            name='status',
            field=models.CharField(
                max_length=12,
                default='legacy',
                db_index=True,
                verbose_name='Status',
                choices=[
                    ('offen',     'Offen'),
                    ('fixiert',   'Fixiert (Vertrag abgeschlossen)'),
                    ('verprellt', 'Verprellt (Sponsor abgesprungen)'),
                    ('abgesagt',  'Abgesagt (durch anderen Slot-Contract)'),
                    ('angenommen', 'Angenommen (V1-Legacy)'),
                    ('legacy',    'Alt (V1)'),
                ],
            ),
        ),
        migrations.AlterField(
            model_name='sponsoroffer',
            name='typ',
            field=models.CharField(
                max_length=20,
                verbose_name='Angebotstyp',
                choices=[
                    ('sicherheit', 'Sicherheit (100 % fix)'),
                    ('sieggeld',   'Sieggeld (fix + €/Sieg)'),
                    ('torgeld',    'Torgeld (fix + €/Tor)'),
                    ('zieljaeger', 'Zieljäger (fix + Zielbonus)'),
                    ('zuschauer',  'Zuschauer (fix + €/Besucher)'),
                ],
            ),
        ),
    ]
