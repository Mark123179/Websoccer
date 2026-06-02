import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0053_managerprofile_nationality_name_requires_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='managerprofile',
            name='favourite_club',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='game.club',
                verbose_name='Lieblingsverein',
            ),
        ),
    ]
