from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0022_playerseasonstat_grade_season_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerseasonstat',
            name='substitutions_in',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='playerseasonstat',
            name='substitutions_out',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
