from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0113_mediaoutlet'),
    ]

    operations = [
        migrations.AddField(
            model_name='managerprofile',
            name='last_seen',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Zuletzt online',
                help_text='Wird bei jedem Seitenaufruf aktualisiert (max. alle 2 Minuten).',
            ),
        ),
    ]
