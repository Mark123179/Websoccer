from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0095_club_import_name_provisional_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='clubplayerimportjob',
            name='validation_issues',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'Validierungsprobleme aus dem letzten Import-Lauf '
                    '(Liste von {level, code, message, ref}-Dicts).'
                ),
            ),
        ),
    ]
