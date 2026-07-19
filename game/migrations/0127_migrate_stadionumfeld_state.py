"""Datenmigration Stadionumfeld (Phase 3): Ambiente-Keys per Verein.

Kopiert die Ambiente-Keys (heimspiel, tod, wetter, day) aus dem globalen
StadionumfeldConfig-Singleton in ClubStadionumfeldState für ALLE Vereine
und lässt im Singleton nur das Szenen-Layout (positions, badgePos,
selected) zurück.
"""
from django.db import migrations

AMBIENTE_KEYS = {'heimspiel', 'tod', 'wetter', 'day'}
LAYOUT_KEYS = {'positions', 'badgePos', 'selected'}


def forwards(apps, schema_editor):
    Config = apps.get_model('game', 'StadionumfeldConfig')
    ClubState = apps.get_model('game', 'ClubStadionumfeldState')
    Club = apps.get_model('game', 'Club')

    cfg = Config.objects.order_by('id').first()
    state = (cfg.state or {}) if cfg else {}
    ambiente = {k: v for k, v in state.items() if k in AMBIENTE_KEYS}

    for club in Club.objects.all():
        ClubState.objects.get_or_create(
            club=club, defaults={'state': dict(ambiente)},
        )

    if cfg is not None:
        cfg.state = {k: v for k, v in state.items() if k in LAYOUT_KEYS}
        cfg.save(update_fields=['state'])


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0126_matchdayrevenue_attendance_seating_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
