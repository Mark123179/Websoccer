"""Korrigiert SPONSOR_RISK_MODE von 'malus' auf 'Standard'.

Migration 0144 hatte 'malus' gesetzt, aber die Runtime-Logik in
sponsors.py erwartet 'Entschärft'|'Standard'|'Hardcore' als Werte.
'malus' fällt auf RISK_MULTS.get(risk_mode, 1.0) = 1.0 zurück
(identisch mit 'Standard'), daher funktional unverändert — aber
der explizite Wert soll dem Runtime-Vokabular entsprechen.
"""
from django.db import migrations

OLD_VALUE = 'malus'
NEW_VALUE = 'Standard'


def forward_fix_risk_mode(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(
        key='SPONSOR_RISK_MODE', value=OLD_VALUE,
    ).update(value=NEW_VALUE)


def reverse_fix_risk_mode(apps, schema_editor):
    EconomyParameter = apps.get_model('game', 'EconomyParameter')
    EconomyParameter.objects.filter(
        key='SPONSOR_RISK_MODE', value=NEW_VALUE,
    ).update(value=OLD_VALUE)


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0150_add_torgeld_to_typ_split'),
    ]

    operations = [
        migrations.RunPython(forward_fix_risk_mode, reverse_fix_risk_mode),
    ]
