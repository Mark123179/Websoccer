"""Abschnitt 'Spieltag- & Saison-Status' — read-only.

Leitet aus LeagueSeasonState (bevorzugt) bzw. den vorhandenen SeasonFixture
den Spieltagstand sowie Inkonsistenzen ab. Keine Annahme über eine einzelne
'aktive' Liga: es werden alle Gruppen mit Spielplan-Daten betrachtet.
"""
from __future__ import annotations


def _global_season():
    from game.models import GameSeasonState
    gs = GameSeasonState.objects.first()
    if not gs:
        return None
    return {'current_season': gs.current_season, 'is_started': gs.is_started}


def _league_groups():
    """(league, season, matchday|None, is_simulated|None)-Gruppen ableiten."""
    from game.models import LeagueSeasonState, SeasonFixture
    states = list(LeagueSeasonState.objects.select_related('league').all())
    if states:
        return [
            (st.league, st.season, st.current_matchday, st.is_simulated)
            for st in states
        ]
    # Fallback: eindeutige (league, season)-Paare aus dem Spielplan.
    seen = {}
    for fx in SeasonFixture.objects.select_related('league').all():
        key = (fx.league_id, fx.season)
        if key not in seen:
            seen[key] = (fx.league, fx.season, None, None)
    return list(seen.values())


def build_season_status():
    from game.models import SeasonFixture
    global_season = _global_season()
    leagues = []
    total_inc = 0
    for league, season, matchday, is_simulated in _league_groups():
        fixtures = list(SeasonFixture.objects.filter(league=league, season=season))
        if not fixtures:
            continue
        played = sum(1 for f in fixtures if f.is_played)
        open_cnt = len(fixtures) - played
        miss_report = sum(
            1 for f in fixtures if f.is_played and f.simulated_match_id is None
        )
        orphan_report = sum(
            1 for f in fixtures if (not f.is_played) and f.simulated_match_id is not None
        )
        miss_goals = sum(
            1 for f in fixtures
            if f.is_played and (f.home_goals is None or f.away_goals is None)
        )
        inconsistencies = []
        if miss_report:
            inconsistencies.append(f'{miss_report}× gespielt ohne verknüpften Spielbericht')
        if orphan_report:
            inconsistencies.append(
                f'{orphan_report}× Spielbericht vorhanden, aber nicht als gespielt markiert'
            )
        if miss_goals:
            inconsistencies.append(f'{miss_goals}× gespielt ohne Ergebnis (Tore fehlen)')
        total_inc += len(inconsistencies)
        leagues.append({
            'league': league.name,
            'season': season,
            'matchday': matchday,
            'is_simulated': is_simulated,
            'played': played,
            'open': open_cnt,
            'total': len(fixtures),
            'inconsistencies': inconsistencies,
        })
    available = bool(leagues)
    return {
        'title': 'Spieltag- & Saison-Status',
        'available': available,
        'note': '' if available else 'Keine Ligen mit Spielplan-Daten gefunden.',
        'global_season': global_season,
        'leagues': leagues,
        'inconsistency_count': total_inc,
    }
