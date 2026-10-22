from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("game", "0191_clubrecord_context_text")]

    operations = [
        migrations.CreateModel(
            name="PlayerIdentityAuditSnapshot",
            fields=[
                ("id", models.PositiveSmallIntegerField(
                    primary_key=True, default=1, editable=False, serialize=False)),
                ("generated_at", models.DateTimeField()),
                ("report", models.JSONField()),
            ],
        ),
    ]
