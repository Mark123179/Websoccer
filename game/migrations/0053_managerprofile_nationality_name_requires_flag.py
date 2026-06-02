from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0052_clear_deutschland_default_nationality'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='managerprofile',
            constraint=models.CheckConstraint(
                condition=models.Q(nationality_name='') | ~models.Q(nationality_flag=''),
                name='managerprofile_nationality_name_requires_flag',
            ),
        ),
    ]
