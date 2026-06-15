from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0092_cup_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='club',
            name='job_availability_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('none',      'Nicht freigegeben'),
                    ('free_pick', 'Free Pick'),
                    ('normal',    'Normale Bewerbung'),
                    ('top',       'Top-Bewerbung'),
                ],
                default='free_pick',
                verbose_name='Job-Freigabe',
                help_text=(
                    'Legt fest, ob und mit welcher Bewerbungsart der Verein '
                    'auf der Job-Angebote-Liste erscheint.'
                ),
            ),
        ),
    ]
