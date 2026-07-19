"""Seed für die Verbandsabgabe (Spec Kap. 12.5) — HART DEAKTIVIERT.

enabled=False: Der Runner (run_verbandsabgabe) verweigert die Ausführung,
solange der Schalter nicht explizit nach Balancing-Freigabe umgelegt wird.
faktor/satz sind [KALIBRIERUNG]-Startwerte.
"""
from django.db import migrations

SAISON = '0'

VERBANDSABGABE = {
    'enabled': False,   # HART AUS — Aktivierung nur nach Balancing-Freigabe
    'faktor': 2.0,      # Freibetrag = 2× Jahresumsatz [KALIBRIERUNG]
    'satz': 0.10,       # 10 % auf den Überschuss [KALIBRIERUNG]
}


def seed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.update_or_create(
        saison=SAISON, key='VERBANDSABGABE',
        defaults={'value': VERBANDSABGABE},
    )


def unseed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(saison=SAISON, key='VERBANDSABGABE').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0130_finance_phase5_insolvency_auction'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
