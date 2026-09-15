from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('stadium_editor', '0006_merge_0005_roof_and_bvb_grid')]

    operations = [
        migrations.AddField(
            model_name='stadiumgeometry',
            name='steckbrief',
            field=models.JSONField(default=dict),
        ),
    ]