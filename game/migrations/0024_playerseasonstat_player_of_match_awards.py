from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0023_playerseasonstat_substitutions'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerseasonstat',
            name='player_of_match_awards',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
