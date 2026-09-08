from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('stadium_editor', '0002_seed_bundled_geometries')]

    operations = [
        migrations.AddField(
            model_name='stadiumdesign',
            name='blickrichtung',
            field=models.CharField(default='NORD', max_length=4),
        ),
    ]