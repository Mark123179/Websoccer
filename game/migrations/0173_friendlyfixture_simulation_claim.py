from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('game', '0172_friendly_fixture_neutral_venue'),
    ]

    operations = [
        migrations.AddField(
            model_name='friendlyfixture',
            name='simulation_claim',
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='friendlyfixture',
            name='simulation_claimed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]