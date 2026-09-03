from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0167_manager_login_rewards'),
    ]

    operations = [
        migrations.RenameField(
            model_name='managerprofile',
            old_name='active_title_key',
            new_name='active_title',
        ),
    ]