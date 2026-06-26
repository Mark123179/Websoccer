from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0101_cmt_datenmodell_v1'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='loan_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('none', 'Kein Leihverhältnis'),
                    ('loaned_in', 'Geliehen'),
                    ('loaned_out', 'Verliehen'),
                    ('extern_loan', 'Extern verliehen'),
                ],
                default='none',
                help_text=(
                    'Geliehen = im Verein aktiv, gehört einem anderen Verein. '
                    'Verliehen = gehört diesem Verein, spielt aktuell woanders. '
                    'Extern verliehen = vereinslos in WS, aber aktiv verliehen '
                    '(CMT-Auto-Create, Stammverein noch nicht importiert).'
                ),
                max_length=12,
                verbose_name='Leihstatus',
            ),
        ),
    ]
