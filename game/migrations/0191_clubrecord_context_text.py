from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("game", "0190_import_issue_lifecycle")]
    operations = [
        migrations.AlterField(model_name="clubrecord", name="context_line",
                              field=models.TextField(blank=True)),
    ]
