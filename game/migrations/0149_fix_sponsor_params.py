"""Fix SPONSOR_OFFERS_PER_SLOT und SPONSOR_ZIEL_PROB für alle Saisons.

SPONSOR_OFFERS_PER_SLOT: SPEC §1 fordert 3–4 Angebote je Slot.
  haupt:4, trikot:4, ausruester:3, stadion:3, tv:3
  (zuvor: haupt:4, trikot:3, ausruester:2, stadion:2, tv:2)

SPONSOR_ZIEL_PROB: SPEC §4 — Tier-Map statt Scalar.
  {meister, top2, top4, top6, top_half, mittelfeld, klassenerhalt,
   avoid_relegation, aufstieg, abstieg_kampf}
"""
from django.db import migrations

OFFERS_PER_SLOT = {
    'haupt':      4,
    'trikot':     4,
    'ausruester': 3,
    'stadion':    3,
    'tv':         3,
}

ZIEL_PROB_MAP = {
    'meister':          0.08,
    'top2':             0.14,
    'top4':             0.22,
    'top6':             0.34,
    'top_half':         0.50,
    'mittelfeld':       0.50,
    'klassenerhalt':    0.65,
    'avoid_relegation': 0.65,
    'aufstieg':         0.30,
    'abstieg_kampf':    0.55,
}


def forward_fix_params(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    # Alle Saisons patchen (idempotent via update_or_create)
    for row in EconomyParameter.objects.filter(key='SPONSOR_OFFERS_PER_SLOT'):
        # Vorhandene Werte mergen: Scalar-Feld belassen, Dict-Felder überschreiben
        existing = row.value if isinstance(row.value, dict) else {}
        existing.update(OFFERS_PER_SLOT)
        row.value = existing
        row.save(update_fields=['value'])

    for row in EconomyParameter.objects.filter(key='SPONSOR_ZIEL_PROB'):
        # Scalar (0.50) → Tier-Map
        if not isinstance(row.value, dict):
            row.value = ZIEL_PROB_MAP
            row.save(update_fields=['value'])
        else:
            # Bereits dict: fehlende Keys ergänzen
            changed = False
            for k, v in ZIEL_PROB_MAP.items():
                if k not in row.value:
                    row.value[k] = v
                    changed = True
            if changed:
                row.save(update_fields=['value'])

    # Falls kein Eintrag vorhanden (z. B. leere DB-Umgebung): anlegen
    saisons_offers = set(
        EconomyParameter.objects.filter(key='SPONSOR_OFFERS_PER_SLOT')
        .values_list('saison', flat=True)
    )
    saisons_ziel = set(
        EconomyParameter.objects.filter(key='SPONSOR_ZIEL_PROB')
        .values_list('saison', flat=True)
    )
    for s in saisons_offers.union(saisons_ziel):
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
