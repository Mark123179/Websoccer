from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0030_add_nt_nationality_to_player'),
    ]

    operations = [
        migrations.AddField(
            model_name='clubprofilematch',
            name='nt_nationality',
            field=models.CharField(
                blank=True,
                help_text='Die Nationalität für NT-Wettbewerbe (z. B. "Deutschland"). Wird verwendet, um das richtige Konföderation-Badge anzuzeigen.',
                max_length=60,
                verbose_name='NT-Nationalität',
            ),
        ),
    ]
