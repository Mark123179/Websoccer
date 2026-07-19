"""Seed der Phase-3-Stadionparameter (Spec Kap. 5, Saison "0").

GEGNERFAKTOR: Zuschläge für die Gegner-Attraktivität der Nachfrageformel —
MW-Verhältnis-Spanne plus additive Boni (Topspiel bei ≤ 9 Punkten Abstand,
Pokal-K.o., Derby), gesamt geklemmt auf min–max.

UMFELD_EURO_BESUCHER_JE_STUFE: Zusatzeinnahme des Stadionumfelds je Besucher
und Facility-Ausbaustufe (Summe aller Stufen × Wert, Kap. 5.4).
[KALIBRIERUNG] — wird nach Launch über Monitoring nachgezogen.
"""
from django.db import migrations

SAISON = '0'

SEED = {
    'GEGNERFAKTOR': {
        'mw_min': 0.85, 'mw_max': 1.15,
        'topspiel': 0.10, 'pokal': 0.15, 'derby': 0.15,
        'min': 0.85, 'max': 1.3,
        'topspiel_punktabstand': 9,
    },
    'UMFELD_EURO_BESUCHER_JE_STUFE': 0.5,
}


def seed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    for key, value in SEED.items():
        EconomyParameter.objects.update_or_create(
            saison=SAISON, key=key, defaults={'value': value},
        )


def unseed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(saison=SAISON, key__in=list(SEED)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0124_seed_abfindung_params'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
