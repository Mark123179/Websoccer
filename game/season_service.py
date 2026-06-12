"""season_service — Saisonbetrieb-Kernlogik

Verwaltet den Spieltag-Zyklus pro Liga:
  Offen → simulate_matchday() → Simuliert → close_matchday() → nächster Spieltag

Wiederverwendbar aus Web-Views UND Management-Commands.
"""

from django.db import transaction


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
