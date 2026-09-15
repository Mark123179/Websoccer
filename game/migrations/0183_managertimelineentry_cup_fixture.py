from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0182_manager_timeline_system_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='managertimelineentry',
            name='cup_fixture',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='manager_timeline_entries',
                to='game.cupfixture',
            ),
        ),
    ]