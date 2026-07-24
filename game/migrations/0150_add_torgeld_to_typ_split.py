"""Ergänzt 'torgeld' in SPONSOR_TYP_SPLIT (split=0.0 = 100 % variabel, per Tor).

SPONSOR_TYP_SPLIT in Migration 0123 enthielt nur:
  sicherheit, sieggeld, zieljaeger, zuschauer.
Der Typ 'torgeld' wurde in V2 hinzugefügt, aber nicht in den Split-Dict
aufgenommen — führt zu KeyError in _build_v2_offer.
"""
from django.db import migrations

TORGELD_SPLIT = 0.0  # 100 % variabel: Fixanteil = 0, alles per-Tor-Rate


def forward_add_torgeld(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    rows = EconomyParameter.objects.filter(key='SPONSOR_TYP_SPLIT')
    for row in rows:
        splits = row.value if isinstance(row.value, dict) else {}
        if 'torgeld' not in splits:
            splits['torgeld'] = TORGELD_SPLIT
            row.value = splits
            row.save(update_fields=['value'])


def reverse_add_torgeld(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    rows = EconomyParameter.objects.filter(key='SPONSOR_TYP_SPLIT')
    for row in rows:
        splits = row.value if isinstance(row.value, dict) else {}
        splits.pop('torgeld', None)
        row.value = splits
        row.save(update_fields=['value'])


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0149_fix_sponsor_params'),
    ]

    operations = [
        migrations.RunPython(forward_add_torgeld, reverse_add_torgeld),
    ]
