from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('game', '0185_live_match_stories')]

    # Only the default changes; already narrated stories retain their version.
    operations = [
        migrations.AlterField(
            model_name='matchstory',
            name='version',
            field=models.CharField(default='v4.1', max_length=16),
        ),
    ]