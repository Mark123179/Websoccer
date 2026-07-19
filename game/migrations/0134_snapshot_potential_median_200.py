# Rechnet potential_median bestehender SeasonEconomySnapshots auf die
# 200er-Stärkeskala um (Skalenfalle: Player.potential ist ein 100er-Rohwert,
# base_strength/staerke_median leben auf der 200er-Skala — der Zukunftswert-
# Pfad der Schmerzgrenze v2 war dadurch praktisch tot; Spec 9.2 nennt
# Potential-Median ~150).
#
# Logik spiegelt game.economy.schmerzgrenze.potential_200 mit historischen
# Modellen: Quellen-Potentiale (CMTRACKER+FM) summiert bzw. ×2 bei nur einer
# Quelle; ohne Quellen-Potentiale Basis-Stärke aus den Quellen-Ratings;
# zuletzt Rohwert × 2.
from statistics import median

from django.db import migrations


def _potential_200(raw_potential, ea, fm):
    ea_pot = ea.get('potential') if ea else None
    fm_pot = fm.get('potential') if fm else None
    if ea_pot is not None and fm_pot is not None:
        return float(ea_pot + fm_pot)
    if ea_pot is not None:
        return float(ea_pot * 2)
    if fm_pot is not None:
        return float(fm_pot * 2)
    ea_rat = ea.get('rating') if ea else None
    fm_rat = fm.get('rating') if fm else None
    if ea_rat is not None and fm_rat is not None:
        return float(ea_rat + fm_rat)
    if ea_rat is not None:
        return float(ea_rat * 2)
    if fm_rat is not None:
        return float(fm_rat * 2)
    if raw_potential:
        return float(raw_potential * 2)
    return None


def recompute(apps, schema_editor):
    Snapshot = apps.get_model('game', 'SeasonEconomySnapshot')
    Player = apps.get_model('game', 'Player')
    Rating = apps.get_model('game', 'PlayerSourceRating')

    if not Snapshot.objects.exists():
        return

    quellen = {}
    for pid, source, rating, potential in Rating.objects.values_list(
            'player_id', 'source', 'rating', 'potential'):
        quellen.setdefault(pid, {})[source] = {
            'rating': rating, 'potential': potential,
        }

    werte = []
    spieler = Player.objects.filter(
        strength_profile__isnull=False,
    ).values_list('id', 'potential')
    for pid, raw in spieler:
        q = quellen.get(pid, {})
        wert = _potential_200(raw, q.get('CMTRACKER'), q.get('FM'))
        if wert is not None:
            werte.append(wert)

    if not werte:
        return

    neuer_median = round(median(werte), 2)
    Snapshot.objects.update(potential_median=neuer_median)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0133_seed_ki_kaeufer'),
    ]

    operations = [
        migrations.RunPython(recompute, noop),
    ]
