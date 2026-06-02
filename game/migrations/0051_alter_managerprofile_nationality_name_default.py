from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0050_alter_managerprofile_nationality_flag_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='managerprofile',
            name='nationality_name',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
