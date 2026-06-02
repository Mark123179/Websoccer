from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0049_update_trophy_asset_ids'),
    ]

    operations = [
        migrations.AlterField(
            model_name='managerprofile',
            name='nationality_flag',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
