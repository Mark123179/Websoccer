from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('game', '0161_dealrequest_counter'),
    ]

    operations = [
        migrations.CreateModel(
            name='StadiumDesign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('design', models.JSONField(default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('stadium', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='editor_design', to='game.stadium')),
            ],
            options={
                'verbose_name': 'Stadion-Design',
                'verbose_name_plural': 'Stadion-Designs',
            },
        ),
        migrations.CreateModel(
            name='StadiumGeometry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geometry', models.JSONField(default=dict)),
                ('schema_version', models.PositiveSmallIntegerField(default=1)),
                ('source', models.CharField(blank=True, default='OSM', max_length=120)),
                ('attribution', models.CharField(default='Blaupause: OpenStreetMap-Daten (ODbL)', max_length=120)),
                ('last_warning', models.TextField(blank=True, default='')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('stadium', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='editor_geometry', to='game.stadium')),
            ],
            options={
                'verbose_name': 'Stadion-Geometrie',
                'verbose_name_plural': 'Stadion-Geometrien',
            },
        ),
    ]