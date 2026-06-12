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


def _apply_match_suspensions(
    card_data: list,
    competition: str,
    season: str,
) -> None:
    """Setzt Sperren nach einem Spiel.

    card_data: [{'pid': int, 'yellow': int, 'red': int}, ...]
    - Rote Karte  → 1-Spiel-Rotsperre (sofort).
    - 5./10./15. Gelbe Karte der Saison (quer über alle Wettbewerbe) → Gelbsperre.
    Idempotent: existierende Restsperre bleibt, wenn sie höher ist.
    """
    from django.utils import timezone as _tz
    from .models import Player, PlayerSuspensionRecord, PlayerSeasonStat

    for item in card_data:
        pid    = item.get('pid')
        yellow = int(item.get('yellow') or 0)
        red    = int(item.get('red')    or 0)
        if not pid or not (red or yellow):
            continue

        try:
            player = Player.objects.get(pk=pid)
        except Player.DoesNotExist:
            continue

        if red:
            player.ws_suspension_reason = 'Rotsperre'
            player.ws_suspension_matches_remaining = max(
                player.ws_suspension_matches_remaining, 1
            )
            player.save(update_fields=[
                'ws_suspension_reason',
                'ws_suspension_matches_remaining',
            ])
            PlayerSuspensionRecord.objects.create(
                player_id=pid,
                reason='Rotsperre',
                matches_missed=1,
                competition=competition,
                is_active=True,
                start_date=_tz.localdate(),
            )

        elif yellow:
            total_yellows = (
                PlayerSeasonStat.objects
                .filter(player_id=pid, season=season)
                .exclude(competition='Freundschaft')
                .aggregate(total=Sum('yellow_cards'))['total'] or 0
            )
            prev_total = total_yellows - yellow
            for threshold in (5, 10, 15):
                if prev_total < threshold <= total_yellows:
                    player.ws_suspension_reason = 'Gelbsperre'
                    player.ws_suspension_matches_remaining = max(
                        player.ws_suspension_matches_remaining, 1
                    )
                    player.save(update_fields=[
                        'ws_suspension_reason',
                        'ws_suspension_matches_remaining',
                    ])
                    PlayerSuspensionRecord.objects.create(
                        player_id=pid,
                        reason='Gelbsperre',
                        matches_missed=1,
                        competition=competition,
                        is_active=True,
                        start_date=_tz.localdate(),
                    )
                    break


def _decrement_suspensions_for_clubs(club_ids: list) -> None:
    """Reduziert ws_suspension_matches_remaining um 1 vor der Spieltag-Simulation.

    Löscht ws_suspension_reason und setzt is_active=False am Record wenn Zähler 0 erreicht.
    """
    from .models import Player, PlayerSuspensionRecord

    qs = Player.objects.filter(
        club_id__in=club_ids,
        ws_suspension_matches_remaining__gt=0,
    )
    for player in qs:
        new_val = player.ws_suspension_matches_remaining - 1
        player.ws_suspension_matches_remaining = new_val
        if new_val == 0:
            player.ws_suspension_reason = ''
        player.save(update_fields=[
            'ws_suspension_matches_remaining',
            'ws_suspension_reason',
        ])
        if new_val == 0:
            PlayerSuspensionRecord.objects.filter(
                player=player,
                is_active=True,
            ).update(is_active=False)


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

    # ── Sperren auslösen (Rotsperre / Gelbsperre bei 5/10/15) ────────────────
    _card_items = [
        {
            'pid': p.get('id'),
            'yellow': int(p.get('yellow_cards', 0) or 0),
            'red':    int(p.get('red_cards',    0) or 0),
        }
        for players, _club_id in sides
        for p in players
        if p.get('id')
    ]
    try:
        _apply_match_suspensions(_card_items, competition, _WS_LIGA_SEASON)
    except Exception:
        pass

    # ── Verletzungen persistieren ────────────────────────────────────────────
    try:
        _write_injury_events(
            data.get('injury_events') or [],
            fixture_date,
            competition,
        )
    except Exception:
        pass

    # ── Frischeverlust nach Spiel schreiben ───────────────────────────────────
    try:
        from .freshness_service import apply_match_freshness_losses
        apply_match_freshness_losses(
            home_players=data.get('home_players') or [],
            away_players=data.get('away_players') or [],
            home_club=fixture.home_club,
            away_club=fixture.away_club,
            fatigue_cost_home=float(data.get('home_fatigue_cost') or 1.0),
            fatigue_cost_away=float(data.get('away_fatigue_cost') or 1.0),
        )
    except Exception:
        pass


_COMPETITION_FOR_SOURCE = {
    'ws_freundschaft': 'Freundschaft',
    'ws_pokal':        'Pokal',
}


def _write_injury_events(injury_events: list, fixture_date, competition: str) -> None:
    """Persistiert Verletzungsereignisse aus einem Match-Report.

    Für jeden Eintrag in injury_events wird:
    - ws_injury_type + ws_injury_days_remaining auf dem Player gesetzt
    - Ein aktiver PlayerInjuryRecord angelegt (vorherige aktive Einträge deaktiviert)

    Bestehende aktive Verletzung wird überschrieben, wenn der Spieler erneut verletzt wird.
    Idempotent wenn injury_events leer ist.
    """
    from django.utils import timezone as _tz
    from .models import Player, PlayerInjuryRecord

    if not injury_events:
        return

    pid_to_event: dict[int, dict] = {}
    for evt in injury_events:
        pid = evt.get('player_id')
        if pid:
            pid_to_event[pid] = evt

    if not pid_to_event:
        return

    players = {p.pk: p for p in Player.objects.filter(pk__in=pid_to_event.keys())}

    for pid, evt in pid_to_event.items():
        player = players.get(pid)
        if not player:
            continue

        injury_type = evt.get('injury_type', 'Leicht')
        days = int(evt.get('days', 5))
        end_date = fixture_date + __import__('datetime').timedelta(days=days)

        PlayerInjuryRecord.objects.filter(player=player, is_active=True).update(
            is_active=False,
        )

        PlayerInjuryRecord.objects.create(
            player=player,
            start_date=fixture_date,
            end_date=end_date,
            injury_type=injury_type,
            days_missed=days,
            competition=competition,
            is_active=True,
        )

        Player.objects.filter(pk=pid).update(
            ws_injury_type=injury_type,
            ws_injury_days_remaining=days,
        )


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

    def _safe_int(v) -> int | None:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    # Einwechslungs-Sets pro Seite aufbauen (Seite bekannt für team_name-Zuordnung)
    home_sub_in_pids: set[int] = set()
    home_sub_out_pids: set[int] = set()
    away_sub_in_pids: set[int] = set()
    away_sub_out_pids: set[int] = set()

    for sub in (data.get('home_substitutions') or []):
        pid = _safe_int(sub.get('in'))
        if pid:
            home_sub_in_pids.add(pid)
        pid = _safe_int(sub.get('out'))
        if pid:
            home_sub_out_pids.add(pid)

    for sub in (data.get('away_substitutions') or []):
        pid = _safe_int(sub.get('in'))
        if pid:
            away_sub_in_pids.add(pid)
        pid = _safe_int(sub.get('out'))
        if pid:
            away_sub_out_pids.add(pid)

    sub_in_pids  = home_sub_in_pids  | away_sub_in_pids
    sub_out_pids = home_sub_out_pids | away_sub_out_pids

    sides = [
        (data.get('home_players') or [], home_name, away_name),
        (data.get('away_players') or [], away_name, home_name),
    ]

    affected_player_ids: list[int] = []
    seen_pids: set[int] = set()

    for players, team_name, opponent_name in sides:
        for p in players:
            pid = _safe_int(p.get('id'))
            if not pid:
                continue
            affected_player_ids.append(pid)
            seen_pids.add(pid)

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
                'raw_payload':      {
                    'is_motm': pid == motm_pid,
                    'sub_in':  pid in sub_in_pids,
                    'sub_out': pid in sub_out_pids,
                },
            }
            if rating is not None:
                snap_defaults['rating'] = rating

            PlayerFormSnapshot.objects.update_or_create(
                player_id=pid,
                source=source,
                fixture_id=fixture_id_str,
                defaults=snap_defaults,
            )

    # Eingewechselte Bankspieler sind nicht in home_players/away_players (nur Starting XI).
    # Für diese Spieler werden minimale Snapshots erzeugt, damit substitutions_in
    # korrekt aggregiert werden kann.
    bench_sides = [
        (home_sub_in_pids, home_name, away_name),
        (away_sub_in_pids, away_name, home_name),
    ]
    for sub_in_set, team_name, opponent_name in bench_sides:
        for pid in sub_in_set:
            if pid in seen_pids:
                continue
            affected_player_ids.append(pid)
            seen_pids.add(pid)
            PlayerFormSnapshot.objects.update_or_create(
                player_id=pid,
                source=source,
                fixture_id=fixture_id_str,
                defaults={
                    'source':           source,
                    'fixture_date':     fixture_date,
                    'minutes_played':   0,
                    'possible_minutes': 90,
                    'started':          False,
                    'substituted_in':   True,
                    'position':         '',
                    'team_name':        team_name,
                    'opponent_name':    opponent_name,
                    'goals':            0,
                    'assists':          0,
                    'yellow_cards':     0,
                    'red_cards':        0,
                    'raw_payload':      {
                        'is_motm': False,
                        'sub_in':  True,
                        'sub_out': False,
                    },
                },
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

    sub_in_counts: dict[int, int] = {}
    for row in (
        snap_qs
        .filter(raw_payload__sub_in=True)
        .values('player_id')
        .annotate(c=Count('id'))
    ):
        sub_in_counts[row['player_id']] = row['c']

    sub_out_counts: dict[int, int] = {}
    for row in (
        snap_qs
        .filter(raw_payload__sub_out=True)
        .values('player_id')
        .annotate(c=Count('id'))
    ):
        sub_out_counts[row['player_id']] = row['c']

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
            substitutions_in=sub_in_counts.get(pid, 0),
            substitutions_out=sub_out_counts.get(pid, 0),
        )

    # ── Sperren auslösen (nur Pflichtspiele: Liga + Pokal) ───────────────────
    if source != 'ws_freundschaft':
        _card_items = [
            {
                'pid': p.get('id'),
                'yellow': int(p.get('yellow_cards', 0) or 0),
                'red':    int(p.get('red_cards',    0) or 0),
            }
            for players, _team_name, _opp_name in sides
            for p in players
            if p.get('id')
        ]
        try:
            _apply_match_suspensions(_card_items, competition, _WS_LIGA_SEASON)
        except Exception:
            pass

    # ── Verletzungen + Frischeverlust: nur Pflichtspiele (Liga + Pokal) ─────────
    if source != 'ws_freundschaft':
        try:
            _write_injury_events(
                data.get('injury_events') or [],
                fixture_date,
                competition,
            )
        except Exception:
            pass

        try:
            from .freshness_service import apply_match_freshness_losses
            apply_match_freshness_losses(
                home_players=data.get('home_players') or [],
                away_players=data.get('away_players') or [],
                home_club=home_club,
                away_club=away_club,
                fatigue_cost_home=float(data.get('home_fatigue_cost') or 1.0),
                fatigue_cost_away=float(data.get('away_fatigue_cost') or 1.0),
            )
        except Exception:
            pass


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

    # ── Sperren vor dem Spieltag abbauen ─────────────────────────────────────
    if to_play:
        _club_ids_to_play = list({
            cid
            for f in to_play
            for cid in (f.home_club_id, f.away_club_id)
        })
        try:
            _decrement_suspensions_for_clubs(_club_ids_to_play)
        except Exception:
            pass

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
