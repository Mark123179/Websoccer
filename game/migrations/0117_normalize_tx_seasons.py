"""Vereinheitlicht die Saison-Konvention in ClubFinancialTransaction.

Alte Scouting-Buchungen trugen TM-Saison-Labels wie "2025/26"; die
Manager-Finanzansicht und alle neuen Buchungen nutzen die numerische
Sim-Saison (GameSeasonState.current_season) als String. Diese Migration
mappt alle Label-Zeilen auf die aktuelle Sim-Saison.
"""
from django.db import migrations


def normalize_seasons(apps, schema_editor):
    Tx = apps.get_model('game', 'ClubFinancialTransaction')
    State = apps.get_model('game', 'GameSeasonState')
    state = State.objects.first()
    season = str(state.current_season) if state else '0'
    Tx.objects.filter(season__contains='/').update(season=season)


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0116_playerclubhistory'),
    ]

    operations = [
        migrations.RunPython(normalize_seasons, migrations.RunPython.noop),
    ]
