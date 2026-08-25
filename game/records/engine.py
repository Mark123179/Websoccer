"""Vollständiger Recompute der materialisierten Ruhmeshallen-Rekorde.

Der öffentliche Schreibpfad ist ausschließlich :func:`rebuild_for_club`.
Er liest nur Aggregattabellen, niemals unstrukturierte Spielberichtsdaten, und
schreibt ausschließlich ``ClubRecord.source == SIM``.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from game.models import (
    Club,
    ClubRecord,
    ClubRecordBreak,
    ClubNewsItem,
    CupFixture,
    CupSeason,
    LeagueStandings,
    ManagerCareerEntry,
    Player,
    PlayerMarketValueSnapshot,
    PlayerSeasonStat,
    PlayerTransferHistory,
    SeasonFixture,
)
from game.records.registry import RECORD_REGISTRY, RECORDS_BY_KEY


ZERO = Decimal('0')
MIN_PPG_MATCHES = 30
LOWER_VALUE_WINS = {'worst_season', 'fewest_conceded_season'}


@dataclass
class Candidate:
    value_numeric: Decimal
    value_display: str
    holder_name: str
    holder_player_id: int | None = None
    holder_coach_id: int | None = None
    holder_manager_id: int | None = None
    opponent_name: str = ''
    opponent_club_id: int | None = None
    context_line: str = ''
    record_date: date | None = None
    period_from: date | None = None
    period_to: date | None = None
    season: str = ''
    competition: str = ''
    linked_match_id: int | None = None


@dataclass
class MatchRow:
    record_date: date | None
    home_goals: int
    away_goals: int
    home_id: int
    away_id: int
    opponent_id: int
    opponent_name: str
    winner_id: int | None
    competition: str
    season: str
    linked_match_id: int | None
    is_league: bool


def _q(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _season_sort(value):
    try:
        return (0, int(str(value).split('/')[0]))
    except (TypeError, ValueError):
        return (1, str(value))


def _display_money(value):
    value = Decimal(value)
    if value >= Decimal('1000000'):
        return f'{value / Decimal("1000000"):.2f}'.replace('.', ',') + ' Mio. €'
    return f'{value:,.0f}'.replace(',', '.') + ' €'


def _fixture_date(fixture):
    if getattr(fixture, 'scheduled_date', None):
        return fixture.scheduled_date
    simulated = getattr(fixture, 'simulated_match', None)
    return simulated.simulated_at.date() if simulated else None


def _not_friendly(simulated):
    return simulated is None or simulated.match_type != 'freundschaft'


def _league_matches(club):
    fixtures = (
        SeasonFixture.objects
        .filter(Q(home_club=club) | Q(away_club=club), is_played=True)
        .exclude(home_goals__isnull=True)
        .exclude(away_goals__isnull=True)
        .select_related('home_club', 'away_club', 'simulated_match', 'league')
        .order_by('scheduled_date', 'pk')
    )
    rows = []
    for fixture in fixtures:
        # A SeasonFixture is, by definition, a scheduled league match.  Older
        # simulation rows may still carry ``match_type='freundschaft'`` from
        # their generic report factory; using that report flag here would
        # silently discard real Bundesliga results from club records.
        home_goals = int(fixture.home_goals)
        away_goals = int(fixture.away_goals)
        if home_goals > away_goals:
            winner_id = fixture.home_club_id
        elif away_goals > home_goals:
            winner_id = fixture.away_club_id
        else:
            winner_id = None
        opponent = fixture.away_club if fixture.home_club_id == club.pk else fixture.home_club
        rows.append(MatchRow(
            record_date=_fixture_date(fixture),
            home_goals=home_goals,
            away_goals=away_goals,
            home_id=fixture.home_club_id,
            away_id=fixture.away_club_id,
            opponent_id=opponent.pk,
            opponent_name=opponent.name,
            winner_id=winner_id,
            competition=fixture.league.name,
            season=str(fixture.season),
            linked_match_id=fixture.simulated_match_id,
            is_league=True,
        ))
    return rows


def _cup_matches(club):
    fixtures = (
        CupFixture.objects
        .filter(Q(home_club=club) | Q(away_club=club), status=CupFixture.STATUS_PLAYED)
        .exclude(is_bye=True)
        .select_related(
            'home_club', 'away_club', 'winner_club', 'simulated_match',
            'cup_round__cup_season__competition',
        )
        .order_by('cup_round__scheduled_date', 'pk')
    )
    rows = []
    for fixture in fixtures:
        if not _not_friendly(fixture.simulated_match):
            continue
        if fixture.final_home_goals is None or fixture.final_away_goals is None:
            continue
        winner_id = fixture.winner_club_id
        if winner_id is None:
            if fixture.final_home_goals > fixture.final_away_goals:
                winner_id = fixture.home_club_id
            elif fixture.final_away_goals > fixture.final_home_goals:
                winner_id = fixture.away_club_id
            elif fixture.home_penalties is not None and fixture.away_penalties is not None:
                winner_id = (
                    fixture.home_club_id
                    if fixture.home_penalties > fixture.away_penalties
                    else fixture.away_club_id
                )
        opponent = fixture.away_club if fixture.home_club_id == club.pk else fixture.home_club
        rows.append(MatchRow(
            record_date=fixture.cup_round.scheduled_date or _fixture_date(fixture),
            home_goals=fixture.final_home_goals,
            away_goals=fixture.final_away_goals,
            home_id=fixture.home_club_id,
            away_id=fixture.away_club_id,
            opponent_id=opponent.pk,
            opponent_name=opponent.name,
            winner_id=winner_id,
            competition=fixture.cup_round.cup_season.competition.name,
            season=str(fixture.cup_round.cup_season.season),
            linked_match_id=fixture.simulated_match_id,
            is_league=False,
        ))
    return rows


def _all_matches(club):
    return sorted(
        _league_matches(club) + _cup_matches(club),
        key=lambda row: (row.record_date or date.min, _season_sort(row.season), row.linked_match_id or 0),
    )


def _pick(candidates, *, reverse=True):
    if not candidates:
        return None
    if reverse:
        best_value = max(item.value_numeric for item in candidates)
    else:
        best_value = min(item.value_numeric for item in candidates)
    same = [item for item in candidates if item.value_numeric == best_value]
    return min(
        same,
        key=lambda item: (
            item.record_date or date.max,
            _season_sort(item.season),
            item.holder_name,
        ),
    )


def _player_stats(club):
    rows = (
        PlayerSeasonStat.objects
        .filter(club=club)
        .select_related('player')
        .order_by('player_id', 'season_number', 'pk')
    )
    grouped = {}
    for row in rows:
        if str(row.competition).strip().lower() in {'freundschaft', 'freundschaftsspiel'}:
            continue
        item = grouped.setdefault(row.player_id, {
            'player': row.player,
            'matches': 0,
            'goals': 0,
            'assists': 0,
            'first_season': str(row.season),
            'season_matches': defaultdict(int),
        })
        item['matches'] += row.matches
        item['goals'] += row.goals
        item['assists'] += row.assists
        item['season_matches'][str(row.season)] += row.matches
        if _season_sort(row.season) < _season_sort(item['first_season']):
            item['first_season'] = str(row.season)
    return list(grouped.values())


def _player_candidate(item, value, *, context=''):
    player = item['player']
    return Candidate(
        value_numeric=Decimal(value),
        value_display=str(value),
        holder_name=player.full_name,
        holder_player_id=player.pk,
        context_line=context,
        season=item['first_season'],
    )


def _player_records(club, title_events):
    stats = _player_stats(club)
    records = {}
    for key, field in (
        ('top_scorer', 'goals'),
        ('top_assists', 'assists'),
    ):
        records[key] = _pick(
            [_player_candidate(item, item[field]) for item in stats if item[field] > 0],
        )
    records['most_apps_field'] = _pick([
        _player_candidate(item, item['matches'])
        for item in stats if item['player'].position != 'TW' and item['matches'] > 0
    ])
    records['most_apps_gk'] = _pick([
        _player_candidate(item, item['matches'])
        for item in stats if item['player'].position == 'TW' and item['matches'] > 0
    ])
    records['most_titles_player'] = _most_titles_player(stats, title_events)
    records['highest_market_value'] = _highest_market_value(club)
    return records


def _title_events(club, league_matches=None):
    events = []
    standings = (
        LeagueStandings.objects
        .filter(club=club, position=1)
        .select_related('league')
        .order_by('season', 'pk')
    )
    league_dates = {}
    for match in league_matches if league_matches is not None else _league_matches(club):
        league_dates.setdefault(match.season, []).append(match.record_date)
    for standing in standings:
        dates = [d for d in league_dates.get(str(standing.season), []) if d]
        events.append({
            'kind': 'championship',
            'season': str(standing.season),
            'date': max(dates) if dates else None,
            'competition': standing.league.name,
        })
    cups = (
        CupSeason.objects
        .filter(winner_club=club)
        .select_related('competition')
        .prefetch_related('rounds__fixtures')
        .order_by('season', 'pk')
    )
    for cup in cups:
        dates = [
            fixture.cup_round.scheduled_date
            for round_obj in cup.rounds.all()
            for fixture in round_obj.fixtures.all()
            if fixture.status == CupFixture.STATUS_PLAYED and fixture.cup_round.scheduled_date
        ]
        events.append({
            'kind': 'cup',
            'season': str(cup.season),
            'date': max(dates) if dates else None,
            'competition': cup.competition.name,
        })
    return sorted(events, key=lambda item: (item['date'] or date.max, _season_sort(item['season'])))


def _most_titles_player(stats, title_events):
    if not title_events:
        return None
    candidates = []
    for item in stats:
        count = sum(
            1 for event in title_events
            if item['season_matches'].get(event['season'], 0) > 0
        )
        if count:
            candidates.append(Candidate(
                value_numeric=Decimal(count),
                value_display=str(count),
                holder_name=item['player'].full_name,
                holder_player_id=item['player'].pk,
                record_date=min((e['date'] for e in title_events if e['date']), default=None),
                context_line='Titel für den Verein',
            ))
    return _pick(candidates)


def _owned_on(snapshot_date, transfers, club_id):
    if not transfers:
        return True
    start = None
    for transfer in transfers:
        if transfer.to_club_id == club_id:
            start = transfer.transfer_date
        if transfer.from_club_id == club_id:
            # Importhistorien beginnen oft erst mit dem ersten dokumentierten
            # Abgang. Dann gilt die Vereinszugehörigkeit bis zu diesem Datum
            # als anfängliche Station, auch ohne vorherigen Zugangseintrag.
            interval_start = start if start is not None else date.min
            if interval_start <= snapshot_date <= transfer.transfer_date:
                return True
            start = None
    return start is not None and start <= snapshot_date


def _highest_market_value(club):
    snapshots = list(
        PlayerMarketValueSnapshot.objects
        .filter(
            Q(player__club=club) |
            Q(player__ws_transfer_history__to_club=club) |
            Q(player__ws_transfer_history__from_club=club)
        )
        .select_related('player')
        .order_by('-value_eur', 'recorded_at', 'pk')
        .distinct()
    )
    player_ids = {snapshot.player_id for snapshot in snapshots}
    transfers_by_player = defaultdict(list)
    for transfer in (
        PlayerTransferHistory.objects
        .filter(player_id__in=player_ids)
        .order_by('player_id', 'transfer_date', 'pk')
    ):
        transfers_by_player[transfer.player_id].append(transfer)
    candidates = []
    for snapshot in snapshots:
        transfers = transfers_by_player[snapshot.player_id]
        if not _owned_on(snapshot.recorded_at, transfers, club.pk):
            continue
        if not transfers and snapshot.player.club_id != club.pk:
            continue
        candidates.append(Candidate(
            value_numeric=_q(snapshot.value_eur),
            value_display=_display_money(snapshot.value_eur),
            holder_name=snapshot.player.full_name,
            holder_player_id=snapshot.player_id,
            record_date=snapshot.recorded_at,
        ))
    return _pick(candidates)


def _club_match_records(club, matches, title_events):
    result = {}
    win_candidates = []
    defeat_candidates = []
    for match in matches:
        is_home = match.home_id == club.pk
        own = match.home_goals if is_home else match.away_goals
        conceded = match.away_goals if is_home else match.home_goals
        diff = own - conceded
        base = dict(
            value_display=f'{own}:{conceded}',
            holder_name=club.name,
            opponent_name=match.opponent_name,
            opponent_club_id=match.opponent_id,
            record_date=match.record_date,
            season=match.season,
            competition=match.competition,
            linked_match_id=match.linked_match_id,
        )
        if diff > 0:
            win_candidates.append((Candidate(Decimal(diff), **base), own))
        elif diff < 0:
            defeat_candidates.append((Candidate(Decimal(-diff), **base), conceded))
    result['biggest_win'] = _pick_score(win_candidates)
    result['biggest_defeat'] = _pick_score(defeat_candidates)
    result.update(_streak_records(club, matches))
    result.update(_season_records(club))
    result['championships'] = _count_title_record(club, title_events, 'championship')
    result['cup_wins'] = _count_title_record(club, title_events, 'cup')
    result['record_signing'] = _transfer_record(club, incoming=True)
    result['record_sale'] = _transfer_record(club, incoming=False)
    return result


def _pick_score(candidates):
    """Höchste Differenz, dann erzielte Tore des Siegers, dann früheres Datum."""
    if not candidates:
        return None
    best_difference = max(candidate.value_numeric for candidate, _ in candidates)
    same_difference = [
        pair for pair in candidates if pair[0].value_numeric == best_difference
    ]
    best_goals = max(goals for _, goals in same_difference)
    return min(
        (candidate for candidate, goals in same_difference if goals == best_goals),
        key=lambda candidate: (
            candidate.record_date or date.max,
            _season_sort(candidate.season),
        ),
    )


def _streak_records(club, matches):
    result = {}
    for key, acceptable in (
        ('longest_win_streak', {'W'}),
        ('longest_unbeaten', {'W', 'D'}),
        ('longest_winless', {'D', 'L'}),
    ):
        best = 0
        best_start = None
        best_end = None
        run = 0
        run_start = None
        for match in matches:
            is_home = match.home_id == club.pk
            own = match.home_goals if is_home else match.away_goals
            conceded = match.away_goals if is_home else match.home_goals
            if match.winner_id == club.pk:
                outcome = 'W'
            elif match.winner_id is None and own == conceded:
                outcome = 'D'
            else:
                outcome = 'L'
            if outcome in acceptable:
                if run == 0:
                    run_start = match.record_date
                run += 1
                if run > best:
                    best = run
                    best_start = run_start
                    best_end = match.record_date
            else:
                run = 0
                run_start = None
        result[key] = (
            Candidate(
                value_numeric=Decimal(best),
                value_display=str(best),
                holder_name=club.name,
                record_date=best_end,
                period_from=best_start,
                period_to=best_end,
                context_line='Pflichtspiele',
            ) if best else None
        )
    return result


def _season_records(club):
    rows = list(
        LeagueStandings.objects.filter(club=club).select_related('league')
        .order_by('season', 'pk')
    )
    if not rows:
        return {key: None for key in (
            'best_season', 'worst_season', 'most_goals_season', 'fewest_conceded_season',
        )}
    dates = {}
    for match in _league_matches(club):
        if match.record_date:
            dates.setdefault(match.season, []).append(match.record_date)

    def candidate(row, value, context):
        season = str(row.season)
        return Candidate(
            value_numeric=Decimal(value),
            value_display=str(value),
            holder_name=club.name,
            record_date=max(dates.get(season, []), default=None),
            season=season,
            competition=row.league.name,
            context_line=context,
        )

    return {
        'best_season': _pick([
            candidate(row, row.points, f'{row.points} Punkte · Platz {row.position}')
            for row in rows
        ]),
        'worst_season': _pick([
            candidate(row, row.points, f'{row.points} Punkte · Platz {row.position}')
            for row in rows
        ], reverse=False),
        'most_goals_season': _pick([
            candidate(row, row.goals_for, f'{row.goals_for} Tore')
            for row in rows
        ]),
        'fewest_conceded_season': _pick([
            candidate(row, row.goals_against, f'{row.goals_against} Gegentore')
            for row in rows
        ], reverse=False),
    }


def _count_title_record(club, title_events, kind):
    events = [event for event in title_events if (
        event['kind'] == kind
    )]
    if not events:
        return None
    last = events[-1]
    return Candidate(
        value_numeric=Decimal(len(events)),
        value_display=str(len(events)),
        holder_name=club.name,
        record_date=last['date'],
        season=last['season'],
        competition=last['competition'],
    )


def _transfer_record(club, *, incoming):
    field = 'to_club' if incoming else 'from_club'
    candidates = [
        Candidate(
            value_numeric=_q(row.fee_eur),
            value_display=_display_money(row.fee_eur),
            holder_name=row.player.full_name,
            holder_player_id=row.player_id,
            record_date=row.transfer_date,
            season=str(row.season or ''),
            context_line='Einkauf' if incoming else 'Verkauf',
        )
        for row in (
            PlayerTransferHistory.objects
            .filter(**{field: club})
            .exclude(fee_eur__isnull=True)
            .select_related('player')
        )
    ]

    # PlayerTransferHistory enthält Import-/Legacydaten. Die v2-Historie ist
    # die Quelle für tatsächlich im Spiel abgeschlossene Transfers und muss
    # deshalb ebenfalls berücksichtigt werden.
    from game.transfer_v2.models import TransferRecord, TransferRecordPlayer
    v2_rows = (
        TransferRecordPlayer.objects
        .filter(
            player__isnull=False,
            record__is_cancelled=False,
        )
        .exclude(record__kind__in=[
            TransferRecord.KIND_LOAN,
            TransferRecord.KIND_FREE,
            TransferRecord.KIND_ADMIN,
        ])
        .select_related('record', 'player')
        .order_by('record__date', 'pk')
    )
    for row in v2_rows:
        record = row.record
        if row.side == TransferRecordPlayer.SIDE_A:
            receiving_club_id = record.club_b_id
            paying_amount = record.cash_b
            outgoing_club_id = record.club_a_id
        else:
            receiving_club_id = record.club_a_id
            paying_amount = record.cash_a
            outgoing_club_id = record.club_b_id
        relevant_club_id = receiving_club_id if incoming else outgoing_club_id
        amount = _q(paying_amount)
        if relevant_club_id != club.pk or amount <= 0:
            continue
        candidates.append(Candidate(
            value_numeric=amount,
            value_display=_display_money(amount),
            holder_name=row.player.full_name,
            holder_player_id=row.player_id,
            record_date=record.date,
            context_line='Einkauf' if incoming else 'Verkauf',
        ))

    return _pick(candidates)


def _coach_records(club, matches, title_events):
    entries = list(
        ManagerCareerEntry.objects
        .filter(club=club)
        .select_related('manager')
        .order_by('started_at', 'pk')
    )
    # Career history is an additive archive. Newly assigned managers can
    # already lead fixtures before a historical entry exists, and "Neue
    # Geschichte" must still show their live records.  Use the first
    # documented fixture as the conservative start of that live tenure.
    if not entries and club.managed_by_id:
        dated_matches = [match.record_date for match in matches if match.record_date]
        live_start = min(dated_matches) if dated_matches else timezone.localdate()

        class _LiveManagerEntry:
            manager = club.managed_by
            manager_id = club.managed_by_id
            started_at = live_start
            ended_at = None

        entries = [_LiveManagerEntry()]

    candidates = {
        'longest_tenure': [],
        'most_matches_coach': [],
        'most_titles_coach': [],
        'best_ppg_coach': [],
        'most_wins_coach': [],
    }
    today = timezone.localdate()
    for entry in entries:
        end = entry.ended_at or today
        if end < entry.started_at:
            continue
        scoped = [
            match for match in matches
            if match.record_date and entry.started_at <= match.record_date <= end
        ]
        league = [match for match in scoped if match.is_league]
        wins = sum(match.winner_id == club.pk for match in scoped)
        points = 0
        for match in league:
            is_home = match.home_id == club.pk
            own = match.home_goals if is_home else match.away_goals
            conceded = match.away_goals if is_home else match.home_goals
            points += 3 if own > conceded else 1 if own == conceded else 0
        days = (end - entry.started_at).days
        base = dict(
            holder_name=entry.manager.name,
            holder_manager_id=entry.manager_id,
            record_date=entry.started_at,
            period_from=entry.started_at,
            period_to=entry.ended_at,
            season='',
            competition='Pflichtspiele',
        )
        candidates['longest_tenure'].append(Candidate(
            Decimal(days), f'{days} Tage', context_line=f'{days // 365} Jahre', **base,
        ))
        candidates['most_matches_coach'].append(Candidate(
            Decimal(len(scoped)), str(len(scoped)), **base,
        ))
        title_count = sum(
            event['date'] is not None and entry.started_at <= event['date'] <= end
            for event in title_events
        )
        candidates['most_titles_coach'].append(Candidate(
            Decimal(title_count), str(title_count), **base,
        ))
        if len(league) >= MIN_PPG_MATCHES:
            ppg = _q(Decimal(points) / Decimal(len(league)))
            candidates['best_ppg_coach'].append(Candidate(
                ppg, f'{ppg:.2f}', context_line=f'{points} Punkte aus {len(league)} Ligaspielen', **base,
            ))
        candidates['most_wins_coach'].append(Candidate(
            Decimal(wins), str(wins), **base,
        ))
    return {
        key: _pick(values)
        for key, values in candidates.items()
    }


def _candidate_payload(candidate):
    return {
        'value_numeric': _q(candidate.value_numeric),
        'value_display': candidate.value_display,
        'holder_name': candidate.holder_name,
        'holder_player_id': candidate.holder_player_id,
        'holder_coach_id': candidate.holder_coach_id,
        'holder_manager_id': candidate.holder_manager_id,
        'opponent_name': candidate.opponent_name,
        'opponent_club_id': candidate.opponent_club_id,
        'context_line': candidate.context_line,
        'record_date': candidate.record_date,
        'period_from': candidate.period_from,
        'period_to': candidate.period_to,
        'season': candidate.season,
        'competition': candidate.competition,
        'linked_match_id': candidate.linked_match_id,
        'is_anonymized': False,
    }


def _record_changed(record, payload):
    fields = (
        'value_numeric', 'value_display', 'holder_name', 'holder_player_id',
        'holder_coach_id', 'holder_manager_id', 'opponent_name',
        'opponent_club_id', 'context_line', 'record_date', 'period_from',
        'period_to', 'season', 'competition', 'linked_match_id',
    )
    return any(getattr(record, field) != payload[field] for field in fields)


def _beats_seed(record_key, value_numeric, seed_value):
    """Vergleicht nur strikt; Gleichstände bleiben bewusst beim Seed."""
    if record_key in LOWER_VALUE_WINS:
        return value_numeric < seed_value
    return value_numeric > seed_value


def _seed_break_news(club, record_key, candidate):
    definition = RECORDS_BY_KEY[record_key]
    ClubNewsItem.objects.create(
        club=club,
        title=f'Neuer Vereinsrekord: {definition.label}',
        subtitle=f'{candidate.holder_name} stellt mit {candidate.value_display} einen historischen Bestwert auf.',
        category='Ruhmeshalle',
        outlet='Vereinsredaktion',
        published_at=candidate.record_date or timezone.localdate(),
        blocks=[],
    )


def _write_candidate(club, record_key, candidate):
    record = (
        ClubRecord.objects
        .select_for_update()
        .filter(club=club, record_key=record_key, source=ClubRecord.SOURCE_SIM)
        .first()
    )
    if candidate is None:
        if record is not None:
            ClubRecordBreak.objects.create(
                club=club,
                record_key=record_key,
                old_value_numeric=record.value_numeric,
                old_value_display=record.value_display,
                old_holder_name=record.holder_name,
                new_value_numeric=None,
                new_value_display='',
                new_holder_name='',
                broke_seed=False,
                season=record.season,
            )
            record.delete()
            return 'changed'
        return 'empty'
    payload = _candidate_payload(candidate)
    if record is None:
        ClubRecord.objects.create(
            club=club,
            record_key=record_key,
            source=ClubRecord.SOURCE_SIM,
            **payload,
        )
        return 'created'
    if not _record_changed(record, payload):
        return 'unchanged'
    seed = ClubRecord.objects.filter(
        club=club,
        record_key=record_key,
        source=ClubRecord.SOURCE_SEED,
    ).only('value_numeric').first()
    broke_seed = (
        seed is not None
        and not _beats_seed(record_key, record.value_numeric, seed.value_numeric)
        and _beats_seed(record_key, payload['value_numeric'], seed.value_numeric)
    )
    ClubRecordBreak.objects.create(
        club=club,
        record_key=record_key,
        old_value_numeric=record.value_numeric,
        old_value_display=record.value_display,
        old_holder_name=record.holder_name,
        new_value_numeric=payload['value_numeric'],
        new_value_display=payload['value_display'],
        new_holder_name=payload['holder_name'],
        broke_seed=broke_seed,
        season=payload['season'],
    )
    for field, value in payload.items():
        setattr(record, field, value)
    record.save()
    if broke_seed:
        _seed_break_news(club, record_key, candidate)
    return 'changed'


@transaction.atomic
def rebuild_for_club(club):
    """Berechnet und materialisiert alle Registry-Rekorde für ``club``.

    Der Aufruf ist idempotent. Ein Erstlauf erzeugt keine Break-Zeile; bei
    späterem Wechsel eines materialisierten SIM-Rekords wird genau ein Ereignis
    geschrieben. Seed-Zeilen werden weder gelesen noch verändert.
    """
    if not isinstance(club, Club):
        club = Club.objects.get(pk=club)
    matches = _all_matches(club)
    title_events = _title_events(
        club,
        [match for match in matches if match.is_league],
    )
    records = {}
    records.update(_player_records(club, title_events))
    records.update(_club_match_records(club, matches, title_events))
    records.update(_coach_records(club, matches, title_events))
    summary = {'created': 0, 'changed': 0, 'unchanged': 0, 'empty': 0}
    for definition in RECORD_REGISTRY:
        result = _write_candidate(club, definition.key, records.get(definition.key))
        summary[result] += 1
    return summary