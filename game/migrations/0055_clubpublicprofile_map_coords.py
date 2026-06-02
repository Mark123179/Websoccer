from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0054_managerprofile_favourite_club'),
    ]

    operations = [
        migrations.AddField(
            model_name='clubpublicprofile',
            name='map_lat',
            field=models.FloatField(
                blank=True,
                null=True,
                verbose_name='Breitengrad (Karte)',
            ),
        ),
        migrations.AddField(
            model_name='clubpublicprofile',
            name='map_lng',
            field=models.FloatField(
                blank=True,
                null=True,
                verbose_name='Längengrad (Karte)',
            ),
        ),
    ]
