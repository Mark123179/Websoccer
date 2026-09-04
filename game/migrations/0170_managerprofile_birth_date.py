from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0169_managercompetitiontitle'),
    ]

    operations = [
        migrations.AddField(
            model_name='managerprofile',
            name='birth_date',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='Geburtsdatum',
            ),
        ),
    ]