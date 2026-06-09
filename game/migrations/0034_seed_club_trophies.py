from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0033_add_match_result'),
    ]

    operations = [
        migrations.RunPython(noop, noop),
    ]
