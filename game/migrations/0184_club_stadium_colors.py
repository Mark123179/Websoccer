from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0183_managertimelineentry_cup_fixture'),
    ]

    operations = [
        migrations.AddField(
            model_name='club',
            name='color_primary',
            field=models.CharField(
                blank=True,
                help_text='Hex-Farbe für Stadion-Standarddesigns, z. B. #c8102e.',
                max_length=7,
                verbose_name='Primärfarbe',
            ),
        ),
        migrations.AddField(
            model_name='club',
            name='color_secondary',
            field=models.CharField(
                blank=True,
                help_text='Hex-Farbe für Stadion-Standarddesigns, z. B. #ffffff.',
                max_length=7,
                verbose_name='Sekundärfarbe',
            ),
        ),
    ]