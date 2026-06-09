from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0084_sourceimportrun'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ClubProfileMatch',
        ),
    ]
