import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0035_add_user_fields_to_manager_profile'),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagerCareerStation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(default=1)),
                ('city_name', models.CharField(max_length=120)),
                ('city_country', models.CharField(blank=True, max_length=100)),
                ('map_x', models.PositiveSmallIntegerField(default=271)),
                ('map_y', models.PositiveSmallIntegerField(default=214)),
                ('started_at', models.DateField(blank=True, null=True)),
                ('ended_at', models.DateField(blank=True, null=True)),
                ('games_played', models.PositiveIntegerField(default=0)),
                ('club', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='manager_career_stations',
                    to='game.club',
                )),
                ('manager', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='career_stations',
                    to='game.managerprofile',
                )),
            ],
            options={
                'verbose_name': 'Manager-Karriere-Station',
                'verbose_name_plural': 'Manager-Karriere-Stationen',
                'ordering': ['manager', 'order'],
            },
        ),
    ]
