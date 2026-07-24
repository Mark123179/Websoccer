"""Seed der neuen EconomyParameter-Keys für Sponsoring V2 (Slot-Modell).

Neue Keys (Saison "0"):
  SPONSOR_SLOT_WEIGHTS   — Gewichtung der 5 Slots an Gesamt-Sponsorwert
  SPONSOR_OFFERS_PER_SLOT — Angebotsanzahl je Slot
  SPONSOR_PUSH_GAINS     — Verhandlungsgewinn je Runde [Liste, r=0..2]
  SPONSOR_PUSH_RISKS     — Verlustrisiko je Runde [Liste, r=0..2]
  SPONSOR_PUSH_MAX_ROUNDS — Maximale Verhandlungsrunden
  SPONSOR_RISK_MODE      — 'malus' oder 'verlust' bei Pech
  SPONSOR_EXCLUSIVITY    — Liste von Slot-Paaren, die sich ausschließen
  SPONSOR_ZIEL_PROB      — Wahrscheinlichkeit, das Saisonziel zu erreichen
"""
from django.db import migrations

SAISON = '0'

SEED = {
    'SPONSOR_SLOT_WEIGHTS': {
        'haupt': 0.40,
        'trikot': 0.26,
        'ausruester': 0.15,
        'stadion': 0.11,
        'tv': 0.08,
    },
    'SPONSOR_OFFERS_PER_SLOT': {
        'haupt': 4,
        'trikot': 3,
        'ausruester': 2,
        'stadion': 2,
        'tv': 2,
    },
    'SPONSOR_PUSH_GAINS': [0.05, 0.03, 0.02],
    'SPONSOR_PUSH_RISKS': [0.08, 0.12, 0.20],
    'SPONSOR_PUSH_MAX_ROUNDS': 3,
    'SPONSOR_RISK_MODE': 'malus',
    'SPONSOR_EXCLUSIVITY': [],
    'SPONSOR_ZIEL_PROB': 0.50,
}


def seed_forward(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    for key, value in SEED.items():
        EconomyParameter.objects.update_or_create(
            saison=SAISON, key=key,
            defaults={'value': value},
        )


def seed_reverse(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(saison=SAISON, key__in=list(SEED)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0143_sponsor_model_and_offer_v2'),
    ]

    operations = [
        migrations.RunPython(seed_forward, reverse_code=seed_reverse),
    ]
