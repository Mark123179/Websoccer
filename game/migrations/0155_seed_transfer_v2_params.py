"""Seed der Transfersystem-v2-Balancing-Parameter (Master-Spec §2/§5).

Additiv zu 0120_seed_economy_parameters. Alle Werte leben als
EconomyParameter (Saison '0', mit Saison-Fallback abrufbar), damit das
Creator-Mode-Settings-Panel sie später ohne Code-Deploy justieren kann.

Die alte AUSBILDUNGSABGABE (5 %) bleibt für das bestehende
game.economy.transfers unberührt; die v2-Jugendabgabe nutzt die neuen
Keys JUGENDABGABE_PCT (8 %) und JUGENDABGABE_MIN_JE_VEREIN (50.000 €).
"""
from django.db import migrations

SAISON = '0'

SEED = {
    # Jugendabgabe v2 (Master-Spec §5.6): 8 % gesamt, min. 50.000 € je Verein.
    'JUGENDABGABE_PCT': 0.08,
    'JUGENDABGABE_MIN_JE_VEREIN': 50000,
    # Auktion (Master-Spec §2).
    'TRANSFER_MIN_GEBOT': 500000,
    'TRANSFER_MIN_ERHOEHUNG_ABS': 100000,
    'TRANSFER_MIN_ERHOEHUNG_PCT': 0.05,
    'TRANSFER_ERHOEHUNG_RUNDUNG': 50000,
    'TRANSFER_ANTISNIPING_FENSTER_MIN': 60,
    'TRANSFER_ANTISNIPING_VERLAENGERUNG_H': 24,
    'TRANSFER_FREE_AGENT_STUNDEN': 24,
    # Wechselsperre / Anfragen.
    'TRANSFER_WECHSELSPERRE_TAGE': 21,
    'TRANSFER_ANFRAGE_LAUFZEIT_TAGE': 7,
    # Deal / Tausch.
    'TRANSFER_MAX_PAKET': 5,
    # Leihe (Master-Spec §5.3/§5.4).
    'LEIHE_MIN_GEBUEHR': 1000000,
    'LEIHE_LIMIT_REIN': 6,
    'LEIHE_LIMIT_RAUS': 6,
    'LEIHE_LIMIT_JE_PAAR': 2,
    'LEIHE_DEADLINE_SPIELTAGE': 5,
    # Gerüchte-Wahrscheinlichkeiten (Master-Spec §5.7).
    'RUMOR_P_NEWS': {
        'LISTING_CREATED': 0.15, 'BID_PLACED': 0.08, 'DEAL_SENT': 0.05,
        'TRANSFER_DONE': 0.60, 'LOAN_DONE': 0.40,
    },
    'RUMOR_P_EXACT': 0.50,
    # Ticker-Default.
    'TRANSFER_TICKER_ENABLED': True,
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
        ('game', '0154_positionbarometer_club_reserved_buybackclause_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
