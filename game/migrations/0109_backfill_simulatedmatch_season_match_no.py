from django.db import migrations


def backfill(apps, schema_editor):
    SimulatedMatch = apps.get_model('game', 'SimulatedMatch')

    def resolve_season(sm):
        sf = getattr(sm, 'season_fixture', None)
        if sf is not None and sf.season:
            return str(sf.season)
        cf = getattr(sm, 'cup_fixture', None)
        if cf is not None:
            try:
                return str(cf.cup_round.cup_season.season)
            except Exception:
                pass
        return '0'

    counters = {}
    qs = (
        SimulatedMatch.objects
        .select_related('season_fixture', 'cup_fixture__cup_round__cup_season')
        .order_by('simulated_at', 'id')
    )
    updates = []
    for sm in qs.iterator(chunk_size=500):
        season = resolve_season(sm)
        counters[season] = counters.get(season, 0) + 1
        sm.season = season
        sm.match_no = counters[season]
        updates.append(sm)
        if len(updates) >= 500:
            SimulatedMatch.objects.bulk_update(updates, ['season', 'match_no'])
            updates = []
    if updates:
        SimulatedMatch.objects.bulk_update(updates, ['season', 'match_no'])


def reverse(apps, schema_editor):
    SimulatedMatch = apps.get_model('game', 'SimulatedMatch')
    SimulatedMatch.objects.update(match_no=None, season='0')


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0108_simulatedmatch_match_no_simulatedmatch_season_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse),
    ]
