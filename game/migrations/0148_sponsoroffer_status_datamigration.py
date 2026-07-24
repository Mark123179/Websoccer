"""DataMigration: SponsorOffer Status-Semantik V1 → V2.

- status='angenommen' → 'fixiert'   (V1-accepted = V2-fixiert)
- status='legacy'     → 'abgesagt'  (V1-Altbestand ohne Contract = V2-abgesagt)
"""
from django.db import migrations


def forward_remap_status(apps, schema_editor):
    SponsorOffer = apps.get_model('game', 'SponsorOffer')
    SponsorOffer.objects.filter(status='angenommen').update(status='fixiert')
    SponsorOffer.objects.filter(status='legacy').update(status='abgesagt')


def reverse_remap_status(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0147_sponsor_domain'),
    ]

    operations = [
        migrations.RunPython(forward_remap_status, reverse_remap_status),
    ]
