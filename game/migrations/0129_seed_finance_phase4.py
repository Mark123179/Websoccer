"""Seed + Backfill für Finanzsystem Phase 4 (Spec Kap. 9).

1. SCHMERZGRENZE_KONSTANTEN um die Restnutzwert-Tabelle erweitern
   (Spec 9.2: „z. B. 0,55 bei 33 J., fallend mit Alter").
2. Neuer Parameter KI_VERKAEUFER (reaktive Verkäufer, [KALIBRIERUNG]).
3. potential_median bestehender SeasonEconomySnapshots backfillen
   (nur wo NULL — gehalts_anker/mw_median bleiben unangetastet).
"""
from statistics import median

from django.db import migrations

SAISON = '0'

RESTNUTZWERT = {
    'u26': 1.0, '26': 0.95, '27': 0.92, '28': 0.88, '29': 0.84,
    '30': 0.78, '31': 0.70, '32': 0.62, '33': 0.55, '34': 0.45,
    '35': 0.38, '36+': 0.30,
}

KI_VERKAEUFER = {
    'gegenforderung_faktor': 1.1,   # Gegenforderung = Grenze × 1,1
    'finanzdruck_faktor': 1.0,      # ab Runde 2 bei Finanzdruck
    'streuung': 0.05,               # ±5 % je (Verhandlung, Runde)
    'moderate_luecke_min': 0.70,    # Gebot ≥ 70 % der Grenze → Gegenforderung
    'max_runden': 3,
    'cooldown_tage': 7,
    'gebot_quantisierung': 10000,   # Gegenforderungen auf 10k-Schritte runden
}


def seed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')

    row = EconomyParameter.objects.filter(
        saison=SAISON, key='SCHMERZGRENZE_KONSTANTEN',
    ).first()
    if row is not None:
        value = dict(row.value or {})
        value.setdefault('restnutzwert', RESTNUTZWERT)
        row.value = value
        row.save(update_fields=['value'])

    EconomyParameter.objects.update_or_create(
        saison=SAISON, key='KI_VERKAEUFER',
        defaults={'value': KI_VERKAEUFER},
    )

    # potential_median-Backfill (nur NULL-Zeilen).
    SeasonEconomySnapshot = apps.get_model('game', 'SeasonEconomySnapshot')
    PlayerStrengthProfile = apps.get_model('game', 'PlayerStrengthProfile')
    potentials = [
        p for p in PlayerStrengthProfile.objects.values_list(
            'player__potential', flat=True,
        ) if p is not None
    ]
    if potentials:
        pot_median = median([float(p) for p in potentials])
        SeasonEconomySnapshot.objects.filter(
            potential_median__isnull=True,
        ).update(potential_median=pot_median)


def unseed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(saison=SAISON, key='KI_VERKAEUFER').delete()
    row = EconomyParameter.objects.filter(
        saison=SAISON, key='SCHMERZGRENZE_KONSTANTEN',
    ).first()
    if row is not None and isinstance(row.value, dict):
        row.value.pop('restnutzwert', None)
        row.save(update_fields=['value'])


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0128_finance_phase4_transfermarkt'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
