from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0025_clubnewsitem_clubpublicprofile_clubtrophy_and_more'),
    ]

    operations = [
        migrations.RunPython(noop, noop),
    ]
