"""Fix SPONSOR_OFFERS_PER_SLOT und SPONSOR_ZIEL_PROB für alle Saisons.

SPONSOR_OFFERS_PER_SLOT: SPEC §1 fordert 3–4 Angebote je Slot.
  haupt:4, trikot:4, ausruester:3, stadion:3, tv:3

SPONSOR_ZIEL_PROB: SPEC §4 Kalibrierung — Tier-Map mit exakten SeasonGoal.goal_tier-Werten.
  meister:0.45 / top4:0.50 / international:0.50 / mittelfeld:0.60 / klassenerhalt:0.65
"""
from django.db import migrations

OFFERS_PER_SLOT = {
    'haupt':      4,
    'trikot':     4,
    'ausruester': 3,
    'stadion':    3,
    'tv':         3,
}

# Exakte SeasonGoal.goal_tier-Werte + SPEC §4 kalibrierte Wahrscheinlichkeiten
ZIEL_PROB_MAP = {
    'meister':       0.45,
    'top4':          0.50,
    'international': 0.50,
    'mittelfeld':    0.60,
    'klassenerhalt': 0.65,
}


def forward_fix_params(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')

    for row in EconomyParameter.objects.filter(key='SPONSOR_OFFERS_PER_SLOT'):
        existing = row.value if isinstance(row.value, dict) else {}
        existing.update(OFFERS_PER_SLOT)
        row.value = existing
        row.save(update_fields=['value'])

    for row in EconomyParameter.objects.filter(key='SPONSOR_ZIEL_PROB'):
        row.value = ZIEL_PROB_MAP
        row.save(update_fields=['value'])

    # Fehlende Einträge anlegen (leere DB-Umgebung)
    saisons = set(
        EconomyParameter.objects.filter(
            key__in=['SPONSOR_OFFERS_PER_SLOT', 'SPONSOR_ZIEL_PROB'],
        ).values_list('saison', flat=True)
    )
    for s in saisons:
        EconomyParameter.objects.update_or_create(
            key='SPONSOR_OFFERS_PER_SLOT', saison=s,
            defaults={'value': OFFERS_PER_SLOT},
        )
        EconomyParameter.objects.update_or_create(
            key='SPONSOR_ZIEL_PROB', saison=s,
            defaults={'value': ZIEL_PROB_MAP},
        )


def reverse_fix_params(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0148_sponsoroffer_status_datamigration'),
    ]

    operations = [
        migrations.RunPython(forward_fix_params, reverse_fix_params),
    ]
