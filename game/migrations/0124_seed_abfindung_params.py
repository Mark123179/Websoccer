"""Seeds für Abfindungs-Parameter (Spec Kap. 4, Phase 2).

ABFINDUNG_KARRIEREENDE = 0: Karriereende zahlt bewusst NICHTS —
alternde Kader sind ein Spielelement.
ABFINDUNG_TOD: WSC-Alterstabelle, Faktor × Marktwert je Altersstufe.
"""
from django.db import migrations

SAISON = '0'

PARAM_SEED = {
    'ABFINDUNG_KARRIEREENDE': 0,
    'ABFINDUNG_TOD': {
        '16-17': 6, '18-20': 5, '21-22': 4, '23-24': 3.5,
        '25-28': 3, '29-32': 2.5, '33+': 1.5,
    },
}


def seed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    for key, value in PARAM_SEED.items():
        EconomyParameter.objects.update_or_create(
            saison=SAISON, key=key, defaults={'value': value},
        )


def unseed(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(
        saison=SAISON, key__in=list(PARAM_SEED),
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0123_seed_finance_phase2'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
