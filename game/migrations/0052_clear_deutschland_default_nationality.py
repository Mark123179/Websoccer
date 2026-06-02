from django.db import migrations


def clear_deutschland_default(apps, schema_editor):
    ManagerProfile = apps.get_model('game', 'ManagerProfile')
    ManagerProfile.objects.filter(
        nationality_name='Deutschland',
        nationality_flag='',
    ).update(nationality_name='')


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0051_alter_managerprofile_nationality_name_default'),
    ]

    operations = [
        migrations.RunPython(
            clear_deutschland_default,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
