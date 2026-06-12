"""season_service — Saisonbetrieb-Kernlogik

Verwaltet den Spieltag-Zyklus pro Liga:
  Offen → simulate_matchday() → Simuliert → close_matchday() → nächster Spieltag

Wiederverwendbar aus Web-Views UND Management-Commands.
"""

from django.db import transaction
from django.db.models import Avg, Sum, Count


_WS_LIGA_SOURCE = 'ws_liga'
_WS_LIGA_SEASON = '2026/27'

_SOURCE_FOR_MATCH_TYPE = {
    'freundschaft': 'ws_freundschaft',
    'pokal':        'ws_pokal',
}

_COMPETITION_FOR_MATCH_TYPE = {
    'freundschaft': 'Freundschaft',
    'pokal':        'Pokal',
}


def _update_player_season_stats(fixture, data: dict) -> None:
    """Schreibt PlayerFormSnapshot + PlayerSeasonStat nach einer Ligasimulation.

    Idempotent: Mehrfachaufruf für dasselbe Fixture überschreibt statt zu duplizieren.
    Schreibt: Tore, Assists, Karten, Minuten, Spiele, Durchschnittsnote, MOTM.
    """
    from django.utils import timezone
    from .models import PlayerFormSnapshot, PlayerSeasonStat

    from .models import SeasonFixture as _SeasonFixture
    fixture_date = fixture.scheduled_date or timezone.localdate()
    fixture_id_str = f'ws_liga_{fixture.id}'
    competition = fixture.league.name  # z.B. "1. Bundesliga"

    # Rating-Lookup: player_id → rating (aus compute_player_ratings)
    rating_map: dict[int, float] = {}
    for r in (data.get('home_ratings') or []) + (data.get('away_ratings') or []):
        pid = r.get('id')
        if pid and r.get('rating') is not None:
            rating_map[pid] = float(r['rating'])

    # MOTM: player_id des Spielers des Spiels (aus compute_player_ratings)
    motm_pid: int | None = None
    motm_data = data.get('man_of_the_match') or {}
    if motm_data:
        motm_pid = motm_data.get('id')

    sides = [
        (data.get('home_players') or [], fixture.home_club_id),
        (data.get('away_players') or [], fixture.away_club_id),
    ]

    affected_player_ids: list[int] = []
    for players, _club_id in sides:
        for p in players:
            pid = p.get('id')
            if not pid:
                continue
            affected_player_ids.append(pid)

            goals   = int(p.get('goals', 0) or 0)
            assists = int(p.get('assists', 0) or 0)
            yellow  = int(p.get('yellow_cards', 0) or 0)
            red     = int(p.get('red_cards', 0) or 0)
            rating  = rating_map.get(pid)

            snap_defaults = {
                'source':           _WS_LIGA_SOURCE,
                'fixture_date':     fixture_date,
                'minutes_played':   90,
                'possible_minutes': 90,
                'started':          True,
                'position':         p.get('position', ''),
                'goals':            goals,
                'assists':          assists,
                'yellow_cards':     yellow,
                'red_cards':        red,
                'raw_payload':      {'is_motm': pid == motm_pid},
            }
            if rating is not None:
                snap_defaults['rating'] = rating

            PlayerFormSnapshot.objects.update_or_create(
                player_id=pid,
                source=_WS_LIGA_SOURCE,
                fixture_id=fixture_id_str,
                defaults=snap_defaults,
            )

    # PlayerSeasonStat neu aus allen ws_liga-Snapshots DIESER Liga berechnen (idempotent)
    if not affected_player_ids:
        return

    league_fixture_id_strs = [
        f'ws_liga_{fid}' for fid in
        _SeasonFixture.objects.filter(league=fixture.league).values_list('id', flat=True)
    ]
    snap_qs = PlayerFormSnapshot.objects.filter(
        player_id__in=affected_player_ids,
        source=_WS_LIGA_SOURCE,
        fixture_id__in=league_fixture_id_strs,
    )

    agg_per_player: dict[int, dict] = {}
    for row in snap_qs.values('player_id').annotate(
        total_goals=Sum('goals'),
        total_assists=Sum('assists'),
        total_minutes=Sum('minutes_played'),
        total_matches=Count('id'),
        total_yellow=Sum('yellow_cards'),
        total_red=Sum('red_cards'),
        avg_grade=Avg('rating'),
    ):
        agg_per_player[row['player_id']] = row

    # MOTM-Zähler: Anzahl Snapshots mit is_motm=True pro Spieler
    motm_counts: dict[int, int] = {}
    for row in (
        snap_qs
        .filter(raw_payload__is_motm=True)
        .values('player_id')
        .annotate(c=Count('id'))
    ):
        motm_counts[row['player_id']] = row['c']

    for pid in affected_player_ids:
        agg = agg_per_player.get(pid, {})
        PlayerSeasonStat.objects.update_or_create(
            player_id=pid,
            season=_WS_LIGA_SEASON,
            competition=competition,
            defaults={},
        )
        avg_grade = agg.get('avg_grade')
        PlayerSeasonStat.objects.filter(
            player_id=pid,
            season=_WS_LIGA_SEASON,
            competition=competition,
        ).update(
            goals=agg.get('total_goals') or 0,
            assists=agg.get('total_assists') or 0,
            minutes_played=agg.get('total_minutes') or 0,
            matches=agg.get('total_matches') or 0,
            yellow_cards=agg.get('total_yellow') or 0,
            red_cards=agg.get('total_red') or 0,
            average_grade=round(avg_grade, 2) if avg_grade is not None else None,
            player_of_match_awards=motm_counts.get(pid, 0),
        )


_COMPETITION_FOR_SOURCE = {
    'ws_freundschaft': 'Freundschaft',
    'ws_pokal':        'Pokal',
}


def write_simulated_match_stats(simulated_match, data: dict) -> None:
    """Schreibt PlayerFormSnapshot + PlayerSeasonStat für ein SimulatedMatch.

    Idempotent: Mehrfachaufruf für dasselbe SimulatedMatch überschreibt statt zu duplizieren.
    source wird aus simulated_match.match_type abgeleitet:
        'freundschaft' → 'ws_freundschaft'
        'pokal'        → 'ws_pokal'
    Schreibt außerdem PlayerSeasonStat für den jeweiligen Wettbewerb.
    """
    from django.utils import timezone
    from django.db.models import Avg, Sum, Count
    from .models import PlayerFormSnapshot, PlayerSeasonStat

    source = _SOURCE_FOR_MATCH_TYPE.get(simulated_match.match_type, 'ws_freundschaft')
    competition = _COMPETITION_FOR_SOURCE[source]
    fixture_id_str = f'{source}_{simulated_match.id}'
    fixture_date = simulated_match.simulated_at.date() if simulated_match.simulated_at else timezone.localdate()

    home_club = simulated_match.home_club
    away_club = simulated_match.away_club
    home_name = (home_club.short_name or home_club.name) if home_club else ''
    away_name = (away_club.short_name or away_club.name) if away_club else ''

    rating_map: dict[int, float] = {}
    for r in (data.get('home_ratings') or []) + (data.get('away_ratings') or []):
        pid = r.get('id')
        if pid and r.get('rating') is not None:
            rating_map[pid] = float(r['rating'])

    motm_pid: int | None = None
    motm_data = data.get('man_of_the_match') or {}
    if motm_data:
        motm_pid = motm_data.get('id')

    sides = [
        (data.get('home_players') or [], home_name, away_name),
        (data.get('away_players') or [], away_name, home_name),
    ]

    affected_player_ids: list[int] = []
    for players, team_name, opponent_name in sides:
        for p in players:
            pid = p.get('id')
            if not pid:
                continue
            affected_player_ids.append(pid)

            goals   = int(p.get('goals',        0) or 0)
            assists = int(p.get('assists',       0) or 0)
            yellow  = int(p.get('yellow_cards',  0) or 0)
            red     = int(p.get('red_cards',     0) or 0)
            rating  = rating_map.get(pid)

            snap_defaults = {
                'source':           source,
                'fixture_date':     fixture_date,
                'minutes_played':   90,
                'possible_minutes': 90,
                'started':          True,
                'position':         p.get('position', ''),
                'team_name':        team_name,
                'opponent_name':    opponent_name,
                'goals':            goals,
                'assists':          assists,
                'yellow_cards':     yellow,
                'red_cards':        red,
                'raw_payload':      {'is_motm': pid == motm_pid},
            }
            if rating is not None:
                snap_defaults['rating'] = rating

            PlayerFormSnapshot.objects.update_or_create(
                player_id=pid,
                source=source,
                fixture_id=fixture_id_str,
                defaults=snap_defaults,
            )

    # PlayerSeasonStat aus allen Snapshots dieser Quelle neu berechnen (idempotent)
    if not affected_player_ids:
        return

    snap_qs = PlayerFormSnapshot.objects.filter(
        player_id__in=affected_player_ids,
        source=source,
    )

    agg_per_player: dict[int, dict] = {}
    for row in snap_qs.values('player_id').annotate(
        total_goals=Sum('goals'),
        total_assists=Sum('assists'),
        total_minutes=Sum('minutes_played'),
        total_matches=Count('id'),
        total_yellow=Sum('yellow_cards'),
        total_red=Sum('red_cards'),
        avg_grade=Avg('rating'),
    ):
        agg_per_player[row['player_id']] = row

    motm_counts: dict[int, int] = {}
    for row in (
        snap_qs
        .filter(raw_payload__is_motm=True)
        .values('player_id')
        .annotate(c=Count('id'))
    ):
        motm_counts[row['player_id']] = row['c']

    for pid in affected_player_ids:
        agg = agg_per_player.get(pid, {})
        PlayerSeasonStat.objects.update_or_create(
            player_id=pid,
            season=_WS_LIGA_SEASON,
            competition=competition,
            defaults={},
        )
        avg_grade = agg.get('avg_grade')
        PlayerSeasonStat.objects.filter(
            player_id=pid,
            season=_WS_LIGA_SEASON,
            competition=competition,
        ).update(
            goals=agg.get('total_goals') or 0,
            assists=agg.get('total_assists') or 0,
            minutes_played=agg.get('total_minutes') or 0,
            matches=agg.get('total_matches') or 0,
            yellow_cards=agg.get('total_yellow') or 0,
            red_cards=agg.get('total_red') or 0,
            average_grade=round(avg_grade, 2) if avg_grade is not None else None,
            player_of_match_awards=motm_counts.get(pid, 0),
        )


def get_season_state(league, season: str):
    """Gibt den LeagueSeasonState zurück, erstellt ihn bei Bedarf (ST1, offen)."""
    from .models import LeagueSeasonState
    state, _ = LeagueSeasonState.objects.get_or_create(
        league=league,
        season=season,
        defaults={'current_matchday': 1, 'is_simulated': False},
    )
    return state


def _max_matchday(league, season: str) -> int:
    """Maximale Spieltagnummer im Spielplan der Liga."""
    from .models import SeasonFixture
    val = (
        SeasonFixture.objects
        .filter(league=league, season=season)
        .order_by('-matchday')
        .values_list('matchday', flat=True)
        .first()
    )
    return val or 0


def simulate_matchday(league, season: str, matchday: int) -> dict:
    """Simuliert alle noch nicht gespielten Fixtures für den Spieltag.

    Gibt ein dict zurück:
        {
            'simulated': [(home_short, score, away_short), ...],
            'skipped':   [(home_short, score, away_short), ...],
            'errors':    [(home_short, away_short, msg), ...],
        }
    Wirft ValueError wenn der Spieltag bereits vollständig simuliert ist.
    Setzt LeagueSeasonState.is_simulated = True wenn alle Spiele gespielt.
    Sperrt TacticSetup.is_locked für alle Clubs der Liga.
    """
    from .models import (
        SeasonFixture, SimulatedMatch, LeagueStandings, TacticSetup,
    )
    from .match_engine import simulate_match
    from .management.commands.play_matchday import (
        _update_standings, _recalculate_positions,
    )

    qs = (
        SeasonFixture.objects
        .filter(league=league, season=season, matchday=matchday)
        .select_related('home_club', 'away_club')
        .order_by('id')
    )
    if not qs.exists():
        raise ValueError(
            f'Keine Fixtures für Spieltag {matchday} (Liga {league.pk}, Saison {season}).'
        )

    all_fixtures = list(qs)
    to_play  = [f for f in all_fixtures if not f.is_played]
    skipped  = [f for f in all_fixtures if f.is_played]

    results = []
    errors  = []

    for fixture in to_play:
        home = fixture.home_club
        away = fixture.away_club
        try:
            data = simulate_match(home, away)
            hg   = data['home_goals']
            ag   = data['away_goals']
            results.append((fixture, data, hg, ag))
        except Exception as exc:
            errors.append((home.short_name or home.name, away.short_name or away.name, str(exc)))

    with transaction.atomic():
        for fixture, data, hg, ag in results:
            if fixture.simulated_match_id:
                old_sm = fixture.simulated_match
                fixture.simulated_match = None
                fixture.save(update_fields=['simulated_match'])
                old_sm.delete()

            sm = SimulatedMatch.objects.create(
                home_club=fixture.home_club,
                away_club=fixture.away_club,
                home_goals=hg,
                away_goals=ag,
                report_data=data,
            )
            fixture.home_goals      = hg
            fixture.away_goals      = ag
            fixture.is_played       = True
            fixture.simulated_match = sm
            fixture.save(update_fields=['home_goals', 'away_goals', 'is_played', 'simulated_match'])

            _update_standings(league, season, fixture.home_club, hg, ag,
                              win=(hg > ag), draw=(hg == ag))
            _update_standings(league, season, fixture.away_club, ag, hg,
                              win=(ag > hg), draw=(hg == ag))

            # ── Spieler-Stats + Form-Snapshots schreiben ──────────────────────
            try:
                _update_player_season_stats(fixture, data)
            except Exception:
                pass  # Stats-Schreibfehler dürfen die Simulation nicht abbrechen

        _recalculate_positions(league, season)

        # ── Taktik-Lock für alle Clubs der Liga ───────────────────────────────
        club_ids = [f.home_club_id for f in all_fixtures] + [f.away_club_id for f in all_fixtures]
        TacticSetup.objects.filter(club_id__in=club_ids, squad_scope='pro').update(is_locked=True)

        # ── Spieltag-Status setzen ────────────────────────────────────────────
        state = get_season_state(league, season)
        all_played = all(f.is_played for f in all_fixtures)
        if all_played:
            state.is_simulated = True
            state.save(update_fields=['is_simulated', 'updated_at'])

    return {
        'simulated': [
            (f.home_club.short_name, f'{hg}:{ag}', f.away_club.short_name)
            for f, _, hg, ag in results
        ],
        'skipped': [
            (f.home_club.short_name, f'{f.home_goals}:{f.away_goals}', f.away_club.short_name)
            for f in skipped
        ],
        'errors': errors,
    }


def close_matchday(league, season: str) -> dict:
    """Schließt den aktuellen Spieltag ab und schaltet den nächsten frei.

    Gibt zurück:
        {'closed': int, 'next': int | None, 'season_complete': bool}
    Wirft ValueError wenn der Spieltag noch nicht simuliert ist.
    Entsperrt TacticSetup.is_locked für alle Clubs der Liga.
    """
    from .models import TacticSetup, SeasonFixture

    state = get_season_state(league, season)

    if not state.is_simulated:
        raise ValueError(
            f'Spieltag {state.current_matchday} wurde noch nicht simuliert — bitte erst simulieren.'
        )

    closed_matchday = state.current_matchday
    max_md = _max_matchday(league, season)
    season_complete = (closed_matchday >= max_md)

    with transaction.atomic():
        if not season_complete:
            state.current_matchday += 1
            state.is_simulated      = False
            state.save(update_fields=['current_matchday', 'is_simulated', 'updated_at'])
        else:
            state.save(update_fields=['updated_at'])

        # ── Taktik-Lock aufheben ──────────────────────────────────────────────
        club_ids = list(
            SeasonFixture.objects
            .filter(league=league, season=season)
            .values_list('home_club_id', flat=True)
            .distinct()
        )
        TacticSetup.objects.filter(club_id__in=club_ids, squad_scope='pro').update(is_locked=False)

    return {
        'closed': closed_matchday,
        'next': state.current_matchday if not season_complete else None,
        'season_complete': season_complete,
    }
