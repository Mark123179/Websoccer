from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0180_tournament_shootout_penalties'),
    ]

    operations = [
        migrations.AddField(
            model_name='managertimelineentry',
            name='competition_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='managertimelineentry',
            name='opponent_name',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]