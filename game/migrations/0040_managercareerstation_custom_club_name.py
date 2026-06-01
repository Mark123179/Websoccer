from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0039_update_club_trophies_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='managercareerstation',
            name='custom_club_name',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
