"""Seed für Finanzsystem Phase 6 (Spec Kap. 9.3) — KI-Käufer Stufe 2.

Neuer Parameter KI_KAEUFER ([KALIBRIERUNG]) mit allen Kadenz-, Schwell-
und Gebotsreglern. Auslieferungszustand: dry_run=True (Trockenlauf AN) —
Angebote werden berechnet und geloggt, aber NICHT versendet, bis der
Admin in der KI-Transferzentrale scharf schaltet.
"""
from django.db import migrations

SAISON = '0'

KI_KAEUFER = {
    # Auslieferung: Trockenlauf AN (Spec 9.3 Einführungspfad Stufe 2).
    'dry_run': True,
    # Gebots-Treppe (Anteile des Käufer-Maximums) + Streuung.
    'streuung': 0.05,
    'eroeffnung': 0.70,
    'nachbesserung': 0.90,
    'final': 1.00,
    # Kauftyp-Grenzen (Anteil der Bewertung bzw. des Zukunftswerts).
    'quali_faktor': 0.85,
    'talent_faktor': 0.90,
    'quali_ueberschuss_faktor': 2,     # Überschuss > 2× Puffer nötig
    'quali_staerke_delta': 10,         # ≥ +10 über eigenem Positionsbesten
    'talent_max_alter': 21,
    'talent_potential_delta': 15,      # Potential deutlich über Kaderniveau
    # Bedarfsrechnung.
    'luecken_schwellwert': 15,
    'backup_delta': 25,                # Backup: Stärke ≥ Beste11 − 25
    'dringlichkeit_min': 0.3,
    # Kadenz & Cooldowns.
    'cooldown_tage': {'bedarf': 7, 'qualitaet': 14},
    'max_offen_ki': 1,
    'max_pro_fenster_ki': 3,
    'max_offen_manager': 2,
    'max_pro_fenster_manager': 4,
    'gueltigkeit_stunden': 72,
    # Budgetregel & Governor.
    'puffer_spieltage': 17,            # ≈ halbe Saison Fixkosten
    'governor_anteil': 0.5,            # KI-Volumen ≤ 50 % Gesamtvolumen
    # Verkäufer-Forderung (KI-zu-KI-Clearing).
    'forderung_faktor_min': 1.1,
    'forderung_faktor_max': 1.3,
    'gebot_quantisierung': 10000,
}


def seed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.update_or_create(
        saison=SAISON, key='KI_KAEUFER',
        defaults={'value': KI_KAEUFER},
    )


def unseed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(saison=SAISON, key='KI_KAEUFER').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0132_finance_phase6_ai_buyer'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
