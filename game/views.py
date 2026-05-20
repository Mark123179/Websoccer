import os
from datetime import date, timedelta
from itertools import product

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import redirect, render, get_object_or_404
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from .club_profile import build_club_profile_context
from .club_profile_highlights import nt_confederation_badge
from .competition_assets import (
    _NT_COMPETITION_KEYS,
    _NATIONALITY_CONFEDERATION,
    _CONFEDERATION_BADGE,
    nt_competition_logo,
    competition_logo_static_path,
)
from .context_processors import CURRENT_MANAGER_PROFILE_IMAGE
from .models import (
    Club,
    ClubNewsItem,
    DataSource,
    League,
    Player,
    PlayerAwardTitle,
    PlayerInjuryRecord,
    PlayerSeasonStat,
    PlayerSourceRating,
    PlayerSuspensionRecord,
    PlayerTransferHistory,
    TacticSetup,
    TacticTemplate,
)
from .tactics import (
    HALF_TACTIC_FIELDS,
    OPPONENT_RESULT_FORM,
    RESULT_FORM,
    STANDARD_FIELDS,
    TACTIC_OPTION_GROUPS,
    FORMATION_ORDER,
    FORMATION_PARTS,
    copy_payload_to_setup,
    default_half_tactic,
    default_standards,
    field_player_count,
    formation_choice_groups,
    formation_code,
    formation_part_summaries,
    formation_slots,
    normalize_formation,
    normalize_squad_scope,
    orientation_label,
    player_match_state,
    player_options_for_squad,
    sanitize_assignments,
    sanitize_payload,
    tactic_payload_from_setup,
    unavailable_players_for_squad,
    validate_formation,
    validate_substitutions,
)


def decimal_number(value):
    if value is None:
        return None

    return float(value)


def date_label(value):
    return value.isoformat() if value else ''


def latest_in_chronological_order(queryset):
    return list(queryset.order_by('-recorded_at', '-id')[:10])[::-1]


def latest_form_snapshots_in_chronological_order(queryset):
    return list(queryset.order_by('-fixture_date', '-id')[:10])[::-1]


def award_trophy_shape(award):
    title = award.title.lower()
    image_path = award.trophy_static_path.lower()

    if any(token in title or token in image_path for token in ['meisterschaft', 'schale']):
        return 'wide'

    if any(token in title or token in image_path for token in ['torjäger', 'torjager', 'kanone']):
        return 'small'

    if any(token in title or token in image_path for token in ['spieler der saison', 'player-of-the-season']):
        return 'season-award'

    if any(token in title or token in image_path for token in ['champions league']):
        return 'tall'

    return 'default'


def award_display_title(award):
    title = award.title.strip()
    normalized = title.lower()

    if normalized == 'meisterschaft':
        return '1. Bundesliga Meisterschaft'

    if normalized == 'ligapokal':
        return 'DFL-Ligapokal'

    return title


def static_asset_version(path):
    found_path = finders.find(path)
    if not found_path:
        return ''

    return str(int(os.path.getmtime(found_path)))


def award_podium_slots(awards):
    slots = []
    for index in range(4):
        if index < len(awards):
            award = awards[index]
            slots.append(
                {
                    'award': award,
                    'image_path': award.trophy_static_path,
                    'title': award_display_title(award),
                    'count': award.count,
                    'shape': award_trophy_shape(award),
                    'asset_version': static_asset_version(award.trophy_static_path),
                    'is_placeholder': False,
                }
            )
            continue

        slots.append(
            {
                'award': None,
                'image_path': 'game/images/trophies/default.png',
                'asset_version': None,
                'title': 'Freier Titelplatz',
                'count': None,
                'shape': 'default',
                'is_placeholder': True,
            }
        )

    return slots


def compact_money(value):
    if value is None:
        return '-'

    value = float(value)
    if value >= 1000000:
        millions = value / 1000000
        if millions.is_integer():
            return f'{millions:.0f} Mio. €'
        return f'{millions:.1f}'.replace('.', ',') + ' Mio. €'

    if value >= 1000:
        return f'{value / 1000:.0f} Tsd. €'

    return f'{value:.0f} €'


def compact_money_axis(value):
    if value is None:
        return '-'

    value = float(value)
    if value >= 1000000:
        return f'{value / 1000000:.0f}M'

    if value >= 1000:
        return f'{value / 1000:.0f}K'

    return f'{value:.0f}'


def market_chart_points(rows, current_value):
    entries = [
        {
            'value': float(row.value_eur),
            'date': row.recorded_at,
        }
        for row in rows
        if row.value_eur is not None
    ]
    if not entries and current_value:
        entries = [{
            'value': float(current_value),
            'date': None,
        }]

    if not entries:
        return []

    values = [entry['value'] for entry in entries]
    min_value = min(values)
    max_value = max(values)
    span = max(max_value - min_value, 1)
    points = []

    for index, entry in enumerate(entries):
        value = entry['value']
        x = 6 + (index / max(len(entries) - 1, 1)) * 88
        y = 82 - ((value - min_value) / span) * 66
        date = entry['date']
        points.append({
            'x': f'{x:.2f}',
            'y': f'{y:.2f}',
            'numeric_value': value,
            'value': compact_money(value),
            'axis_value': compact_money_axis(value),
            'date_label': date.strftime('%m/%y') if date else 'aktuell',
            'full_date_label': date.strftime('%d.%m.%Y') if date else 'aktuell',
        })

    return points


def compute_market_value_trend(rows):
    valid = [row for row in rows if row.value_eur is not None]
    if len(valid) < 2:
        return None
    prev_value = float(valid[-2].value_eur)
    curr_value = float(valid[-1].value_eur)
    delta = curr_value - prev_value
    if delta > 0:
        direction = 'up'
        sign = '+'
    elif delta < 0:
        direction = 'down'
        sign = ''
    else:
        direction = 'flat'
        sign = ''
    return {
        'direction': direction,
        'delta': sign + compact_money(abs(delta)),
    }


def market_chart_axis(points):
    raw_values = [point['numeric_value'] for point in points]

    if not raw_values:
        return {
            'max': '-',
            'mid': '-',
            'min': '-',
        }

    min_value = min(raw_values)
    max_value = max(raw_values)
    return {
        'max': compact_money_axis(max_value),
        'mid': compact_money_axis((max_value + min_value) / 2),
        'min': compact_money_axis(min_value),
    }


def market_polyline(points):
    return ' '.join(f"{point['x']},{point['y']}" for point in points)


def market_area_points(points):
    if not points:
        return ''

    return f"8,92 {market_polyline(points)} 92,92"


def stadium_static_path(club):
    if not club or not club.fm_inside_id:
        return ''

    stadium_assets = {
        901:      'game/images/stadiums/germany/b-leverkusen.jpg',
        905:      'game/images/stadiums/germany/bochum.jpg',
        907:      'game/images/stadiums/germany/b-dortmund.jpg',
        908:      'game/images/stadiums/germany/b-gladbach.jpg',
        912:      'game/images/stadiums/germany/e-frankfurt.jpg',
        915:      'game/images/stadiums/germany/fc-bayern.jpg',
        918:      'game/images/stadiums/germany/mainz.jpg',
        944:      'game/images/stadiums/germany/freiburg.jpg',
        948:      'game/images/stadiums/germany/werder.jpg',
        960:      'game/images/stadiums/germany/stuttgart.jpg',
        961:      'game/images/stadiums/germany/wolfsburg.jpg',
        2238:     'game/images/stadiums/germany/augsburg.jpg',
        2245:     'game/images/stadiums/germany/holstein kiel.jpg',
        121182:   'game/images/stadiums/germany/union berlin.jpg',
        879226:   'game/images/stadiums/germany/hoffenheim.jpg',
        880295:   'game/images/stadiums/germany/heidenheim.jpg',
        3604375:  'game/images/stadiums/germany/st pauli.jpg',
        91013388: 'game/images/stadiums/germany/redbull-leipzig.jpg',
    }
    return stadium_assets.get(club.fm_inside_id, '')


def current_manager_club():
    return (
        Club.objects.select_related('league')
        .filter(fm_inside_id=915)
        .first()
        or Club.objects.select_related('league').filter(name__icontains='Bayern').first()
    )


def city_static_path(club):
    if not club or not club.fm_inside_id:
        return ''

    path = f'game/images/city/{club.fm_inside_id}.jpg'
    if finders.find(path):
        return path

    return ''


def build_game_header(
    title,
    subtitle,
    back_url='/',
    current_club=None,
    opponent_club=None,
    calendar_offset=0,
):
    base_game_date = date(2026, 5, 15)
    game_date = base_game_date + timedelta(days=calendar_offset)
    weekday_labels = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    opponent_name = opponent_club.short_name if opponent_club else 'Gegner'
    opponent_crest = opponent_club.crest_static_path if opponent_club else ''
    opponent_url = reverse_club_detail(opponent_club) if opponent_club else ''
    league_name = (
        current_club.league.name
        if current_club and current_club.league
        else '1. Bundesliga'
    )

    def fixture_entry(lineup_saved, result, venue, meta):
        home_club = current_club if venue == 'H' else opponent_club
        return {
            'opponent_name': opponent_name,
            'opponent_crest': opponent_crest,
            'opponent_url': opponent_url,
            'stadium': stadium_static_path(home_club),
            'competition_logo': competition_logo_static_path(league_name),
            'lineup_saved': lineup_saved,
            'result': result,
            'venue': venue,
            'meta': meta,
        }

    fixtures_by_date = {
        base_game_date - timedelta(days=3): fixture_entry(False, '1:1', 'A', '33. Spieltag (A)'),
        base_game_date - timedelta(days=1): fixture_entry(True, '5:0', 'H', 'Testspiel (H)'),
        base_game_date + timedelta(days=2): fixture_entry(False, '', 'H', '27. Spieltag (H)'),
    }

    calendar_days = []
    for offset in range(-3, 4):
        day = game_date + timedelta(days=offset)
        fixture = fixtures_by_date.get(day)
        calendar_days.append({
            'date': day,
            'weekday': weekday_labels[day.weekday()],
            'day_number': day.day,
            'is_today': day == base_game_date,
            'fixture': fixture,
        })

    return {
        'title': title,
        'subtitle': subtitle,
        'back_url': back_url,
        'game_date': game_date,
        'previous_calendar_offset': calendar_offset - 1,
        'next_calendar_offset': calendar_offset + 1,
        'calendar_days': calendar_days,
    }


def calendar_offset_from_request(request):
    try:
        return int(request.GET.get('calendar_offset', 0))
    except (TypeError, ValueError):
        return 0


def grade_badge_class(grade):
    if grade is None:
        return 'grade-empty'

    grade = float(grade)
    if grade <= 1.5:
        return 'grade-elite'
    if grade <= 2.5:
        return 'grade-good'
    if grade <= 3.5:
        return 'grade-ok'
    if grade <= 4.5:
        return 'grade-warn'
    if grade <= 5.3:
        return 'grade-bad'
    return 'grade-disaster'


def season_table_rows(rows, nt_nationality=None):
    return [
        {
            'season_label': f"#{row.season_number}",
            'competition': row.competition,
            'competition_logo': competition_logo_static_path(row.competition, nt_nationality),
            'matches': row.matches,
            'goals': row.goals,
            'assists': row.assists,
            'substitutions_in': row.substitutions_in,
            'substitutions_out': row.substitutions_out,
            'yellow_cards': row.yellow_cards,
            'red_cards': row.red_cards,
            'player_of_match_awards': row.player_of_match_awards,
            'minutes_played': row.minutes_played,
            'average_grade': row.average_grade,
            'grade_class': grade_badge_class(row.average_grade),
        }
        for row in rows
    ]


def stat_bar_percent(value, maximum, minimum=4):
    if not value or not maximum:
        return 0

    return max(minimum, round((value / maximum) * 100))


def performance_visual_rows(rows):
    if not rows:
        return []

    maxima = {
        'matches': max(row['matches'] for row in rows),
        'goals': max(row['goals'] for row in rows),
        'assists': max(row['assists'] for row in rows),
        'minutes_played': max(row['minutes_played'] for row in rows),
        'cards': max(row['yellow_cards'] + row['red_cards'] for row in rows),
        'subs': max(row['substitutions_in'] + row['substitutions_out'] for row in rows),
        'player_of_match_awards': max(row['player_of_match_awards'] for row in rows),
    }

    visual_rows = []
    for row in rows:
        cards = row['yellow_cards'] + row['red_cards']
        subs = row['substitutions_in'] + row['substitutions_out']
        visual_rows.append({
            **row,
            'cards': cards,
            'substitutions_total': subs,
            'matches_bar': stat_bar_percent(row['matches'], maxima['matches']),
            'goals_bar': stat_bar_percent(row['goals'], maxima['goals']),
            'assists_bar': stat_bar_percent(row['assists'], maxima['assists']),
            'minutes_bar': stat_bar_percent(row['minutes_played'], maxima['minutes_played']),
            'cards_bar': stat_bar_percent(cards, maxima['cards']),
            'subs_bar': stat_bar_percent(subs, maxima['subs']),
            'player_of_match_bar': stat_bar_percent(
                row['player_of_match_awards'],
                maxima['player_of_match_awards'],
            ),
        })

    return visual_rows


def preview_performance_rows(rows, minimum_count=6, nt_nationality=None):
    if not rows or len(rows) >= minimum_count:
        return rows

    result = list(rows)
    existing_competitions = {row['competition'] for row in result}
    samples = [
        ('Europa League', 6, 4, 3, 0, 1, 2, 0, 1, 540, 1.82),
        ('Nationalmannschaft', 5, 3, 2, 1, 0, 1, 0, 2, 410, 1.94),
        ('Club-WM', 4, 2, 2, 1, 1, 1, 0, 1, 360, 2.08),
        ('UEFA Super Cup', 1, 1, 0, 0, 1, 0, 0, 0, 90, 2.10),
        ('Freundschaftspokal', 3, 2, 1, 1, 2, 0, 0, 1, 225, 1.76),
        ('Ligapokal', 2, 1, 1, 0, 0, 0, 0, 0, 180, 2.22),
    ]

    for sample in samples:
        if len(result) >= minimum_count:
            break
        competition = sample[0]
        if competition in existing_competitions:
            continue
        average_grade = sample[10]
        result.append({
            'season_label': rows[0].get('season_label', '#1'),
            'competition': competition,
            'competition_logo': competition_logo_static_path(competition, nt_nationality),
            'matches': sample[1],
            'goals': sample[2],
            'assists': sample[3],
            'substitutions_in': sample[4],
            'substitutions_out': sample[5],
            'yellow_cards': sample[6],
            'red_cards': sample[7],
            'player_of_match_awards': sample[8],
            'minutes_played': sample[9],
            'average_grade': average_grade,
            'grade_class': grade_badge_class(average_grade),
            'is_preview': True,
        })
        existing_competitions.add(competition)

    return result


def career_rows_from_ws_stats(rows, nt_nationality=None):
    grouped = {}

    for row in rows:
        bucket = grouped.setdefault(row.competition, {
            'competition': row.competition,
            'competition_logo': competition_logo_static_path(row.competition, nt_nationality),
            'matches': 0,
            'goals': 0,
            'assists': 0,
            'substitutions_in': 0,
            'substitutions_out': 0,
            'yellow_cards': 0,
            'red_cards': 0,
            'player_of_match_awards': 0,
            'minutes_played': 0,
            'grade_minutes': 0,
            'grade_weighted_sum': 0,
        })
        bucket['matches'] += row.matches
        bucket['goals'] += row.goals
        bucket['assists'] += row.assists
        bucket['substitutions_in'] += row.substitutions_in
        bucket['substitutions_out'] += row.substitutions_out
        bucket['yellow_cards'] += row.yellow_cards
        bucket['red_cards'] += row.red_cards
        bucket['player_of_match_awards'] += row.player_of_match_awards
        bucket['minutes_played'] += row.minutes_played
        if row.average_grade is not None and row.matches:
            bucket['grade_minutes'] += row.matches
            bucket['grade_weighted_sum'] += float(row.average_grade) * row.matches

    career_rows = []
    for bucket in grouped.values():
        average_grade = None
        if bucket['grade_minutes']:
            average_grade = round(
                bucket['grade_weighted_sum'] / bucket['grade_minutes'],
                2,
            )
        career_rows.append({
            **bucket,
            'average_grade': average_grade,
            'grade_class': grade_badge_class(average_grade),
        })

    return sorted(career_rows, key=lambda row: row['competition'])


def money_label(value):
    if value is None or value <= 0:
        return ''

    return f'{value:,.0f} EUR'.replace(',', '.')


def money_full_eur(value):
    if value is None:
        return '0 €'

    return f'{value:,.0f} €'.replace(',', '.')


def transfer_detail_players(candidates, offset, fallback_prefix):
    names = [
        player.full_name
        for player in candidates[offset:offset + 3]
    ]
    while len(names) < 3:
        names.append(f'{fallback_prefix} {len(names) + 1}')
    return names


def transfer_display_rows(rows):
    rows = list(rows)[:6]
    if not rows:
        return []

    candidate_players = list(
        Player.objects.select_related('club')
        .exclude(id__in=[row.player_id for row in rows])
        .order_by('-market_value', 'last_name', 'first_name')[:36]
    )
    clubs = list(
        Club.objects.exclude(fm_inside_id__isnull=True)
        .order_by('-budget', 'name')[:6]
    )

    sample_fees = [
        '78.000.000 EUR',
        'WS-Draft/Initialkader',
        '42.500.000 EUR',
        '18.000.000 EUR',
        'Leihe + Kaufoption',
        '12.000.000 EUR',
    ]

    def build_display_row(
        transfer_date,
        from_club,
        to_club,
        fee_label,
        index,
        is_preview=False,
    ):
        fallback_from = clubs[index % len(clubs)] if clubs else None
        fallback_to = clubs[(index + 1) % len(clubs)] if len(clubs) > 1 else fallback_from
        visible_from_club = from_club if from_club and from_club.crest_static_path else fallback_from
        visible_to_club = to_club if to_club and to_club.crest_static_path else fallback_to

        return {
            'date': transfer_date,
            'from_crest': visible_from_club.crest_static_path if visible_from_club else '',
            'to_crest': visible_to_club.crest_static_path if visible_to_club else '',
            'from_club_url': reverse_club_detail(visible_from_club) if visible_from_club else '',
            'to_club_url': reverse_club_detail(visible_to_club) if visible_to_club else '',
            'fee_label': fee_label or sample_fees[index % len(sample_fees)],
            'outgoing_players': transfer_detail_players(
                candidate_players,
                index * 3,
                'Abgabe',
            ),
            'incoming_players': transfer_detail_players(
                candidate_players,
                index * 3 + 9,
                'Zugang',
            ),
            'is_preview': is_preview,
        }

    display_rows = []

    for index, row in enumerate(rows):
        display_rows.append(
            build_display_row(
                row.transfer_date,
                row.from_club,
                row.to_club,
                money_label(row.fee_eur) or row.notes,
                index,
            )
        )

    base_date = rows[-1].transfer_date if rows else timezone.localdate()
    while len(display_rows) < 6:
        index = len(display_rows)
        from_club = clubs[index % len(clubs)] if clubs else None
        to_club = clubs[(index + 1) % len(clubs)] if len(clubs) > 1 else from_club
        display_rows.append(
            build_display_row(
                base_date - timedelta(days=120 * index),
                from_club,
                to_club,
                sample_fees[index % len(sample_fees)],
                index,
                is_preview=True,
            )
        )

    return display_rows


def pitch_position_slots(player):
    coordinate_slots = [
        ('TW', 50, 86),
        ('LV', 23, 74),
        ('IV', 41, 74),
        ('IV', 59, 74),
        ('RV', 77, 74),
        ('LOV', 17, 61),
        ('DM', 41, 61),
        ('DM', 59, 61),
        ('ROV', 83, 61),
        ('LM', 23, 49),
        ('ZM', 41, 49),
        ('ZM', 59, 49),
        ('RM', 77, 49),
        ('LOM', 25, 36),
        ('OM', 41, 36),
        ('OM', 59, 36),
        ('ROM', 75, 36),
        ('LF', 30, 20),
        ('ST', 44, 15),
        ('ST', 56, 15),
        ('RF', 70, 20),
    ]
    main_positions = set(player.main_positions)
    secondary_positions = set(player.secondary_positions)
    slots = []

    for index, (code, x, y) in enumerate(coordinate_slots):
        kind = ''
        state = 'neutral'
        if code in main_positions:
            kind = 'HP'
            state = 'main'
        elif code in secondary_positions:
            kind = 'NP'
            state = 'secondary'

        slots.append({
            'code': code,
            'kind': kind,
            'state': state,
            'key': f'{code}-{index}',
            'x': x,
            'y': y,
        })

    return slots


def career_summary_from_ws_stats(rows):
    return {
        'seasons': len({row.season for row in rows}),
        'matches': sum(row.matches for row in rows),
        'goals': sum(row.goals for row in rows),
        'assists': sum(row.assists for row in rows),
        'substitutions_in': sum(row.substitutions_in for row in rows),
        'substitutions_out': sum(row.substitutions_out for row in rows),
        'yellow_cards': sum(row.yellow_cards for row in rows),
        'red_cards': sum(row.red_cards for row in rows),
        'player_of_match_awards': sum(row.player_of_match_awards for row in rows),
        'minutes_played': sum(row.minutes_played for row in rows),
    }


def home(request):
    clubs = Club.objects.select_related('league').annotate(
        player_count=Count('player'),
        average_strength=Avg('player__strength_profile__final_strength'),
    )
    richest_clubs = clubs.order_by('-budget')[:6]
    primary_club = current_manager_club() or clubs.order_by('-budget').first()
    secondary_club = (
        clubs.exclude(id=primary_club.id).order_by('-budget').first()
        if primary_club
        else None
    )

    transfer_queryset = Player.objects.select_related(
        'club',
        'club__league',
        'strength_profile',
    )
    if primary_club:
        transfer_queryset = transfer_queryset.exclude(club=primary_club)
    transfer_targets = transfer_queryset.order_by(
        '-market_value',
        '-potential',
        'last_name',
        'first_name',
    )[:3]
    transfer_partner_names = [
        ('Michael Olise', 'Alphonso Davies'),
        ('Jamal Musiala', 'Maximilian Beier'),
        ('Aleksandar Pavlovic', 'Tom Bischof'),
    ]
    transfer_rows = []
    for index, player in enumerate(transfer_targets):
        outgoing_players = [player.full_name]
        incoming_players = []
        for outgoing_name, _incoming_name in transfer_partner_names[:2]:
            outgoing_players.append(outgoing_name)
        for _outgoing_name, incoming_name in transfer_partner_names:
            incoming_players.append(incoming_name)

        transfer_rows.append({
            'player': player,
            'date': date(2026, 7, index + 1),
            'from_crest': player.club.crest_static_path if player.club else '',
            'to_crest': primary_club.crest_static_path if primary_club else '',
            'from_club_url': f'/clubs/{player.club.id}/' if player.club else '',
            'to_club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
            'fee_label': money_label(player.market_value) or money_full_eur(player.market_value),
            'from_label': player.club.short_name if player.club else 'Abgebend',
            'to_label': primary_club.short_name if primary_club else 'Zielverein',
            'outgoing_players': outgoing_players[:3],
            'incoming_players': incoming_players[:3],
        })

    top_strength_players = list(Player.objects.select_related(
        'club',
        'strength_profile',
    ).filter(
        strength_profile__isnull=False,
    ).order_by(
        '-strength_profile__final_strength',
        '-market_value',
        'last_name',
        'first_name',
    )[:4])
    top_strength_player = top_strength_players[0] if top_strength_players else None

    primary_players = (
        Player.objects.filter(club=primary_club)
        if primary_club
        else Player.objects.none()
    )
    primary_market_value = (
        primary_players.aggregate(total=Sum('market_value'))['total'] or 0
    )
    primary_top_scorer = primary_players.order_by(
        '-strength_profile__final_strength',
        '-market_value',
        'last_name',
        'first_name',
    ).first()
    primary_market_player = primary_players.order_by(
        '-market_value',
        '-strength_profile__final_strength',
        'last_name',
        'first_name',
    ).first()
    primary_grade_player = (
        primary_players.filter(ws_season_stats__average_grade__isnull=False)
        .annotate(best_grade=Avg('ws_season_stats__average_grade'))
        .order_by('best_grade', '-market_value', 'last_name', 'first_name')
        .first()
    )
    if primary_grade_player is None:
        primary_grade_player = primary_top_scorer

    if primary_top_scorer:
        top_scorer_label = (
            f'{primary_top_scorer.first_name[:1]}. '
            f'{primary_top_scorer.last_name} (18)'
        )
        top_scorer_portrait = primary_top_scorer.portrait_static_path
    else:
        top_scorer_label = 'L. Martinez (18)'
        top_scorer_portrait = ''

    if primary_market_player:
        market_player_label = (
            f'{primary_market_player.first_name[:1]}. '
            f'{primary_market_player.last_name}'
        )
        market_player_value = money_full_eur(primary_market_player.market_value)
        market_player_portrait = primary_market_player.portrait_static_path
    else:
        market_player_label = 'J. Brandt'
        market_player_value = '78.000.000 €'
        market_player_portrait = ''

    grade_value = getattr(primary_grade_player, 'best_grade', None)
    if primary_grade_player:
        grade_player_label = (
            f'{primary_grade_player.first_name[:1]}. '
            f'{primary_grade_player.last_name}'
        )
        grade_player_value = (
            f'Note {float(grade_value):.2f}'.replace('.', ',')
            if grade_value is not None
            else 'Note 1,80'
        )
        grade_player_portrait = primary_grade_player.portrait_static_path
    else:
        grade_player_label = 'L. Martinez'
        grade_player_value = 'Note 1,80'
        grade_player_portrait = ''

    overview_profile = {
        'budget_label': money_full_eur(primary_club.budget if primary_club else 42800000),
        'club_value_label': money_full_eur(primary_market_value or 214000000),
        'attendance_label': '23.856',
        'top_scorer_label': top_scorer_label,
        'top_scorer_portrait': top_scorer_portrait,
        'spotlights': [
            {
                'title': 'Top-Torjaeger',
                'name': top_scorer_label,
                'meta': '18 Tore',
                'portrait': top_scorer_portrait,
                'player_id': primary_top_scorer.id if primary_top_scorer else None,
            },
            {
                'title': 'Wertvollster Spieler',
                'name': market_player_label,
                'meta': market_player_value,
                'portrait': market_player_portrait,
                'player_id': primary_market_player.id if primary_market_player else None,
            },
            {
                'title': 'Notenbester Spieler',
                'name': grade_player_label,
                'meta': grade_player_value,
                'portrait': grade_player_portrait,
                'player_id': primary_grade_player.id if primary_grade_player else None,
            },
        ],
        'city_static_path': city_static_path(primary_club),
        'fan_percent': 86,
        'form': [
            {'label': 'S', 'tone': 'win'},
            {'label': 'S', 'tone': 'win'},
            {'label': 'U', 'tone': 'draw'},
            {'label': 'S', 'tone': 'win'},
            {'label': 'N', 'tone': 'loss'},
        ],
    }

    table_clubs = []
    seen_ids = set()
    for club in [primary_club, secondary_club]:
        if club and club.id not in seen_ids:
            table_clubs.append(club)
            seen_ids.add(club.id)
    for club in clubs.order_by('-budget'):
        if len(table_clubs) >= 5:
            break
        if club.id in seen_ids:
            continue
        table_clubs.append(club)
        seen_ids.add(club.id)

    fallback_table = [
        ('FC Novum', 'FC Novum', 78, '68:29', '+39'),
        ('FC Aurora', 'FC Aurora', 72, '61:28', '+33'),
        ('FC Helios', 'FC Helios', 64, '57:32', '+25'),
        ('SV Fortuna', 'SV Fortuna', 55, '49:37', '+12'),
        ('SC Meridian', 'SC Meridian', 53, '46:40', '+6'),
    ]
    table_points = [78, 72, 64, 55, 53]
    table_goals = ['68:29', '61:28', '57:32', '49:37', '46:40']
    table_diff = ['+39', '+33', '+25', '+12', '+6']
    overview_league_table = []
    for index in range(5):
        club = table_clubs[index] if index < len(table_clubs) else None
        fallback = fallback_table[index]
        overview_league_table.append({
            'position': index + 1,
            'club_name': club.name if club else fallback[0],
            'short_name': club.short_name if club else fallback[1],
            'crest_static_path': club.crest_static_path if club else '',
            'club_url': f'/clubs/{club.id}/' if club else '',
            'played': 33,
            'goals': table_goals[index],
            'goal_difference': table_diff[index],
            'points': table_points[index],
            'is_current_club': bool(primary_club and club and club.id == primary_club.id),
        })

    totals = {
        'league_count': League.objects.count(),
        'club_count': Club.objects.count(),
        'player_count': Player.objects.count(),
        'manager_count': get_user_model().objects.filter(is_active=True).count(),
        'total_budget': Club.objects.aggregate(total=Sum('budget'))['total'] or 0,
        'total_market_value': (
            Player.objects.aggregate(total=Sum('market_value'))['total'] or 0
        ),
        'total_salary_per_match': (
            Player.objects.aggregate(total=Sum('salary_per_match'))['total'] or 0
        ),
        'average_strength': (
            Player.objects.aggregate(
                average=Avg('strength_profile__final_strength')
            )['average'] or 0
        ),
        'average_age': (
            Player.objects.aggregate(average=Avg('age'))['average'] or 0
        ),
    }

    club_news_player = top_strength_player.last_name if top_strength_player else 'Martinez'
    club_news = [
        {'title': f'{club_news_player} zum Spieler des Monats gekuert', 'when': 'Heute'},
        {'title': 'Vertragsverhandlungen mit Kaya gestartet', 'when': 'Gestern'},
        {'title': 'FC Novum erreicht Gewinn im letzten Quartal', 'when': '22. Mai'},
    ]
    sim_news = [
        {'title': 'Martinez zum Spieler des Monats gekuert', 'when': 'Heute'},
        {'title': 'Vertragsverhandlungen mit Kaya gestartet', 'when': 'Gestern'},
        {'title': 'FC Novum erreicht Gewinn im letzten Quartal', 'when': '22. Mai'},
    ]
    home_stadium_static_path = stadium_static_path(primary_club)
    last_match_home_stadium_static_path = stadium_static_path(primary_club)
    competition_logo_static_path_value = competition_logo_static_path(
        primary_club.league.name
        if primary_club and primary_club.league
        else '1. Bundesliga'
    )

    return render(
        request,
        'game/home.html',
        {
            'richest_clubs': richest_clubs,
            'primary_club': primary_club,
            'secondary_club': secondary_club,
            'transfer_targets': transfer_targets,
            'transfer_rows': transfer_rows,
            'top_strength_players': top_strength_players,
            'overview_profile': overview_profile,
            'overview_league_table': overview_league_table,
            'home_stadium_static_path': home_stadium_static_path,
            'last_match_home_stadium_static_path': last_match_home_stadium_static_path,
            'competition_logo_static_path': competition_logo_static_path_value,
            'active_managers': [
                {
                    'name': 'bojankrkic',
                    'crest': primary_club.crest_static_path if primary_club else '',
                    'club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                },
                {
                    'name': 'husteguz92',
                    'crest': secondary_club.crest_static_path if secondary_club else '',
                    'club_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                },
                {
                    'name': 'Doppel_Loewen Power',
                    'crest': primary_club.crest_static_path if primary_club else '',
                    'club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                },
                {
                    'name': 'FootballMaster2017',
                    'crest': secondary_club.crest_static_path if secondary_club else '',
                    'club_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                },
                {
                    'name': 'Fohlenmeister',
                    'crest': primary_club.crest_static_path if primary_club else '',
                    'club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                },
                {
                    'name': 'Ilundehund',
                    'crest': secondary_club.crest_static_path if secondary_club else '',
                    'club_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                },
                {
                    'name': 'Schae',
                    'crest': primary_club.crest_static_path if primary_club else '',
                    'club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                },
                {
                    'name': 'Beppi',
                    'crest': secondary_club.crest_static_path if secondary_club else '',
                    'club_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                },
            ],
            'chat_messages': [
                {
                    'time': '13.05.2026, 19:34',
                    'author': 'Admin',
                    'text': 'Ihr muesst leider heute nochmal mit einer falschen Darstellung in der Aufstellung leben. Es ist nur die Darstellung, alles wurde sauber gespeichert.',
                },
                {
                    'time': '13.05.2026, 19:35',
                    'author': 'roy10',
                    'text': 'Hab dir FS geschickt.',
                },
                {
                    'time': '13.05.2026, 19:49',
                    'author': 'Gdansk Chris',
                    'text': 'aufgestellt',
                },
            ],
            'club_news': club_news,
            'sim_news': sim_news,
            'social_posts': [
                {
                    'source': 'Transfer Radar',
                    'handle': '@transferradar',
                    'text': 'Geruecht: Um Giuliano Whitchurch entbrennt Spekulation - auch RCD Mallorca wird genannt.',
                    'reactions': '0 Kommentare',
                },
                {
                    'source': 'TR',
                    'handle': '@ligafokus',
                    'text': 'Der Titelkampf bleibt bis zum letzten Spieltag offen.',
                    'reactions': '3 Reaktionen',
                },
            ],
            'last_match_scorers': [
                {'name': 'Martinez', 'minute': 23},
                {'name': 'Petrov', 'minute': 58},
                {'name': 'Kaya', 'minute': 67},
            ],
            'live_matches': [
                {
                    'time': '20:40',
                    'home': primary_club.short_name if primary_club else 'ASK',
                    'away': secondary_club.short_name if secondary_club else 'FOR',
                    'home_crest': primary_club.crest_static_path if primary_club else '',
                    'away_crest': secondary_club.crest_static_path if secondary_club else '',
                    'home_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'away_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '21:20',
                    'home': secondary_club.short_name if secondary_club else 'SER',
                    'away': 'KAS',
                    'home_crest': secondary_club.crest_static_path if secondary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '22:20',
                    'home': primary_club.short_name if primary_club else 'LIV',
                    'away': 'RMA',
                    'home_crest': primary_club.crest_static_path if primary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '22:45',
                    'home': secondary_club.short_name if secondary_club else 'SER',
                    'away': primary_club.short_name if primary_club else 'ASK',
                    'home_crest': secondary_club.crest_static_path if secondary_club else '',
                    'away_crest': primary_club.crest_static_path if primary_club else '',
                    'home_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'away_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '23:05',
                    'home': primary_club.short_name if primary_club else 'LIV',
                    'away': 'ROM',
                    'home_crest': primary_club.crest_static_path if primary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '23:30',
                    'home': secondary_club.short_name if secondary_club else 'BVB',
                    'away': 'S04',
                    'home_crest': secondary_club.crest_static_path if secondary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '00:10',
                    'home': primary_club.short_name if primary_club else 'FCB',
                    'away': 'SGE',
                    'home_crest': primary_club.crest_static_path if primary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '00:35',
                    'home': secondary_club.short_name if secondary_club else 'BVB',
                    'away': 'SVW',
                    'home_crest': secondary_club.crest_static_path if secondary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
            ],
            'overview_stats': [
                {'value': str(totals['manager_count']), 'label': 'registrierte Manager'},
                {
                    'value': str(totals['club_count']),
                    'label': 'Profiteam{} in {} Liga{}'.format(
                        's' if totals['club_count'] != 1 else '',
                        totals['league_count'],
                        'en' if totals['league_count'] != 1 else '',
                    ),
                },
                {'value': '0', 'label': 'Jugendteams'},
                {'value': '0', 'label': 'Nationalteams'},
                {'value': str(totals['player_count']), 'label': 'Spieler'},
            ],
            'totals': totals,
            'game_header': build_game_header(
                'MatchEngine',
                'Saisonvorbereitung · Creator Mode',
                '/',
                primary_club,
                secondary_club,
                calendar_offset_from_request(request),
            ),
        }
    )


def club_list(request):
    clubs = Club.objects.select_related('league').annotate(
        player_count=Count('player'),
        average_strength=Avg('player__strength_profile__final_strength'),
    )
    manager_club = current_manager_club()
    header_club = manager_club or clubs.first()
    header_opponent = (
        clubs.exclude(id=header_club.id).order_by('-budget').first()
        if header_club
        else None
    )

    return render(
        request,
        'game/club_list.html',
        {
            'clubs': clubs,
            'game_header': build_game_header(
                'Vereinsübersicht',
                'Scoutingzentrale · Datenbank',
                '/',
                header_club,
                header_opponent,
                calendar_offset_from_request(request),
            ),
        }
    )


def tactic_redirect_url(club, squad_scope, **params):
    query = {'squad': squad_scope, **params}
    query_string = '&'.join(f'{key}={value}' for key, value in query.items())
    return f'/clubs/{club.id}/tactics/?{query_string}'


def squad_scope_label(squad_scope):
    return 'Jugend' if squad_scope == 'youth' else 'Profis'


def safe_int(value, default=0, minimum=None, maximum=None):
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def parse_half_tactic(post_data, prefix):
    defaults = default_half_tactic()
    result = {
        'orientation': safe_int(
            post_data.get(f'{prefix}_orientation'),
            defaults['orientation'],
            0,
            100,
        ),
    }
    for field_name, _label in HALF_TACTIC_FIELDS:
        options = {value for value, _option_label in TACTIC_OPTION_GROUPS[field_name]}
        value = post_data.get(f'{prefix}_{field_name}', defaults[field_name])
        result[field_name] = value if value in options else defaults[field_name]
    return result


def parse_tactic_payload_from_post(post_data, club, squad_scope):
    errors = []
    raw_formation = {
        part: post_data.get(f'formation_{part}')
        for part in FORMATION_ORDER
    }
    formation = normalize_formation(raw_formation)
    try:
        validate_formation(formation)
    except Exception as exc:
        errors.append(str(exc))

    available_ids = {
        option['id']
        for option in player_options_for_squad(club, squad_scope)
    }
    slots = formation_slots(formation)
    raw_lineup = {
        slot['key']: post_data.get(f"lineup_{slot['key']}", '')
        for slot in slots
    }
    raw_bench = [
        post_data.get(f'bench_{index}', '')
        for index in range(1, 8)
    ]
    lineup, bench = sanitize_assignments(raw_lineup, raw_bench, available_ids)
    lineup_ids = {player_id for player_id in lineup.values() if player_id}

    standards = {}
    for key, _label in STANDARD_FIELDS:
        raw_value = post_data.get(f'standard_{key}', '')
        try:
            player_id = int(raw_value) if raw_value else ''
        except (TypeError, ValueError):
            player_id = ''
        standards[key] = player_id if player_id in lineup_ids else ''

    raw_substitutions = []
    for index in range(1, 6):
        raw_in = post_data.get(f'substitution_{index}_in', '')
        raw_out = post_data.get(f'substitution_{index}_out', '')
        try:
            player_in = int(raw_in) if raw_in else ''
        except (TypeError, ValueError):
            player_in = ''
        try:
            player_out = int(raw_out) if raw_out else ''
        except (TypeError, ValueError):
            player_out = ''
        raw_substitutions.append({
            'minute': post_data.get(f'substitution_{index}_minute', ''),
            'in': player_in if player_in in available_ids else '',
            'out': player_out if player_out in available_ids else '',
        })
    substitution_validation = validate_substitutions(
        raw_substitutions,
        lineup,
        bench,
    )
    errors.extend(substitution_validation.errors)

    return {
        'payload': {
            'formation': formation,
            'lineup': lineup,
            'bench': bench,
            'standards': {**default_standards(), **standards},
            'substitutions': substitution_validation.substitutions,
            'first_half': parse_half_tactic(post_data, 'first_half'),
            'second_half': parse_half_tactic(post_data, 'second_half'),
        },
        'errors': errors,
    }


def confirm_errors_for_payload(payload):
    errors = []
    slots = formation_slots(payload['formation'])
    missing_slots = [
        slot['code']
        for slot in slots
        if not payload['lineup'].get(slot['key'])
    ]
    if missing_slots:
        errors.append(
            'Zum Bestätigen müssen Torwart und alle 10 Feldspieler besetzt sein.'
        )
    if field_player_count(payload['formation']) != 10:
        errors.append('Die Formation muss genau 10 Feldspieler enthalten.')
    return errors


def all_valid_formation_slot_data():
    data = {}
    part_values = [
        list(FORMATION_PARTS[part].keys())
        for part in FORMATION_ORDER
    ]
    for values in product(*part_values):
        formation = dict(zip(FORMATION_ORDER, values))
        if field_player_count(formation) != 10:
            continue
        data[formation_code(formation)] = {
            'formation': formation,
            'slots': formation_slots(formation),
            'summaries': formation_part_summaries(formation),
        }
    return data


def top_player_rows(club, squad_scope, metric):
    players = Player.objects.filter(club=club)
    if squad_scope == 'youth':
        players = players.filter(age__lte=21)
    else:
        players = players.filter(age__gt=21)

    if metric == 'goals':
        rows = players.annotate(value=Sum('ws_season_stats__goals')).filter(
            value__gt=0,
        ).order_by('-value', 'last_name', 'first_name')[:3]
        return [
            {'name': player.full_name, 'value': player.value, 'portrait': player.portrait_static_path}
            for player in rows
        ]
    if metric == 'assists':
        rows = players.annotate(value=Sum('ws_season_stats__assists')).filter(
            value__gt=0,
        ).order_by('-value', 'last_name', 'first_name')[:3]
        return [
            {'name': player.full_name, 'value': player.value, 'portrait': player.portrait_static_path}
            for player in rows
        ]

    rows = players.annotate(value=Avg('ws_season_stats__average_grade')).filter(
        value__isnull=False,
    ).order_by('value', 'last_name', 'first_name')[:3]
    return [
        {'name': player.full_name, 'value': f'{player.value:.2f}', 'portrait': player.portrait_static_path}
        for player in rows
    ]


def fallback_top_rows(player_options, value):
    return [
        {
            'name': option['name'],
            'value': value,
            'portrait': option['portrait'],
        }
        for option in player_options[:3]
    ]


def ensure_three_top_rows(rows, player_options, fallback_value):
    result = list(rows[:3])
    used_names = {row['name'] for row in result}
    for option in player_options:
        if len(result) >= 3:
            break
        if option['name'] in used_names:
            continue
        result.append({
            'name': option['name'],
            'value': fallback_value,
            'portrait': option['portrait'],
        })
        used_names.add(option['name'])
    return result


def tactic_template_payload(template):
    return tactic_payload_from_setup(template)


def template_options_for_context(templates):
    return [
        {
            'id': template.id,
            'name': template.name,
            'formation_code': formation_code(template.formation),
        }
        for template in templates
    ]


def player_lookup_from_options(player_options):
    return {
        option['id']: option
        for option in player_options
    }


def formation_layer_counts(slots):
    return {
        'attack': sum(1 for slot in slots if slot['group'] == 'attack'),
        'midfield': sum(
            1
            for slot in slots
            if slot['group'] in {'defensive_midfield', 'midfield', 'offensive_midfield'}
        ),
        'defense': sum(1 for slot in slots if slot['group'] == 'defense'),
        'goalkeeper': sum(1 for slot in slots if slot['group'] == 'goalkeeper'),
    }


def tactic_display_absences(rows):
    if rows:
        return rows
    return [
        {'name': 'Spieler X', 'reason': 'fällt aus', 'tone': 'injury'},
        {'name': 'Spieler Y', 'reason': 'fällt aus', 'tone': 'injury'},
        {'name': 'Spieler X', 'reason': 'gesperrt', 'tone': 'suspension'},
        {'name': 'Spieler Y', 'reason': 'gesperrt', 'tone': 'suspension'},
    ]


def split_absence_labels(rows):
    injuries = [row['name'] for row in rows if row['tone'] == 'injury']
    suspensions = [row['name'] for row in rows if row['tone'] == 'suspension']
    return {
        'injuries': ', '.join(injuries) if injuries else 'keine',
        'suspensions': ', '.join(suspensions) if suspensions else 'keine',
    }


def form_rows_with_opponents(rows, team_club):
    candidates = list(
        Club.objects.filter(fm_inside_id__isnull=False)
        .exclude(id=getattr(team_club, 'id', None))
        .order_by('name', 'id')[:5]
    )
    if not candidates and team_club and team_club.fm_inside_id:
        candidates = [team_club]

    result = []
    for index, row in enumerate(rows):
        opponent = candidates[index % len(candidates)] if candidates else None
        result.append({
            **row,
            'opponent_name': opponent.name if opponent else 'Gegner',
            'opponent_crest': opponent.crest_static_path if opponent else '',
            'opponent_url': reverse_club_detail(opponent) if opponent else '#',
        })
    return result


def opponent_absence_rows(opponent_club):
    players = []
    if opponent_club:
        players = list(opponent_club.player_set.order_by('last_name', 'first_name', 'id')[:4])

    fallback_names = ['Spieler X', 'Spieler Y', 'Spieler Z', 'Spieler A']
    details = [
        ('injury', 'Muskelverletzung', '12 Tage'),
        ('injury', 'Knieprobleme', '3 Wochen'),
        ('suspension', 'Gelbsperre', '1 Spiel'),
        ('suspension', 'Rotsperre', '2 Spiele'),
    ]
    rows = []
    for index, (tone, reason, duration) in enumerate(details):
        player = players[index] if index < len(players) else None
        rows.append({
            'tone': tone,
            'name': player.full_name if player else fallback_names[index],
            'portrait': player.portrait_static_path if player else 'game/images/default_player.svg',
            'reason': reason,
            'duration': duration,
        })
    return rows


def tactic_match_date_display(value):
    if not value:
        return {'weekday': 'Termin offen', 'date': ''}

    month_numbers = {
        'Januar': '01',
        'Februar': '02',
        'März': '03',
        'Maerz': '03',
        'April': '04',
        'Mai': '05',
        'Juni': '06',
        'Juli': '07',
        'August': '08',
        'September': '09',
        'Oktober': '10',
        'November': '11',
        'Dezember': '12',
    }
    if ',' not in value:
        return {'weekday': value, 'date': ''}

    weekday, raw_date = [part.strip() for part in value.split(',', 1)]
    tokens = raw_date.replace('.', '').split()
    if len(tokens) == 3 and tokens[1] in month_numbers:
        return {
            'weekday': f'{weekday},',
            'date': f'{int(tokens[0]):02d}.{month_numbers[tokens[1]]}.{tokens[2]}',
        }
    return {'weekday': f'{weekday},', 'date': raw_date}


def half_tactic_rows(half_tactic):
    return [
        {
            'name': field_name,
            'label': label,
            'selected': half_tactic.get(field_name, default_half_tactic()[field_name]),
            'options': [
                {'value': value, 'label': option_label}
                for value, option_label in TACTIC_OPTION_GROUPS[field_name]
            ],
        }
        for field_name, label in HALF_TACTIC_FIELDS
    ]


def player_name(player_lookup, player_id):
    option = player_lookup.get(player_id)
    return option['name'] if option else ''


def build_tactics_context(request, club, setup, squad_scope, payload=None, form_errors=None):
    payload = payload or tactic_payload_from_setup(setup)
    player_options = player_options_for_squad(club, squad_scope)
    available_ids = {option['id'] for option in player_options}
    payload = sanitize_payload(payload, available_ids)
    player_lookup = player_lookup_from_options(player_options)
    formation = payload['formation']
    slots = []

    for slot in formation_slots(formation):
        selected_id = payload['lineup'].get(slot['key'])
        selected_player = player_lookup.get(selected_id)
        slots.append({
            **slot,
            'selected_id': selected_id or '',
            'player': selected_player,
            'is_captain': bool(
                selected_id and selected_id == payload['standards'].get('captain')
            ),
            'match_state': (
                player_match_state_from_option(selected_player, slot['code'])
                if selected_player
                else 'empty'
            ),
        })

    selected_field_count = sum(
        1
        for slot in slots
        if slot['group'] != 'goalkeeper' and slot['selected_id']
    )
    selected_freshness_values = [
        slot['player']['freshness']
        for slot in slots
        if slot['selected_id'] and slot['player'] and slot['player']['freshness'] is not None
    ]
    average_freshness = (
        round(sum(selected_freshness_values) / len(selected_freshness_values))
        if selected_freshness_values
        else '-'
    )

    bench_rows = []
    for index in range(1, 8):
        selected_id = payload['bench'][index - 1] if index <= len(payload['bench']) else ''
        bench_rows.append({
            'index': index,
            'selected_id': selected_id or '',
            'player': player_lookup.get(selected_id),
        })

    lineup_player_ids = {
        player_id
        for player_id in payload['lineup'].values()
        if player_id
    }
    lineup_player_options = [
        player_lookup[player_id]
        for player_id in lineup_player_ids
        if player_id in player_lookup
    ]
    lineup_player_options.sort(key=lambda option: option['name'])
    standard_rows = []
    for key, label in STANDARD_FIELDS:
        selected_id = payload['standards'].get(key, '')
        standard_rows.append({
            'key': key,
            'label': label,
            'selected_id': selected_id or '',
            'warning': bool(selected_id and selected_id not in lineup_player_ids),
        })

    substitution_rows = []
    for index in range(1, 6):
        existing = payload['substitutions'][index - 1] if index <= len(payload['substitutions']) else {}
        substitution_rows.append({
            'index': index,
            'minute': existing.get('minute', ''),
            'out': existing.get('out', ''),
            'in': existing.get('in', ''),
        })

    profile_context = build_club_profile_context(club)
    profile = profile_context['profile']
    opponent_club = profile_context['opponent_club'] or (
        Club.objects.exclude(id=club.id).order_by('name').first()
    )
    next_match = profile['nextMatch']
    templates = list(
        club.tactic_templates.filter(squad_scope=squad_scope).order_by('name')
    )
    top_goals = ensure_three_top_rows(top_player_rows(club, squad_scope, 'goals'), player_options, 0)
    top_assists = ensure_three_top_rows(top_player_rows(club, squad_scope, 'assists'), player_options, 0)
    top_grades = ensure_three_top_rows(top_player_rows(club, squad_scope, 'grades'), player_options, '-')
    status_label = 'Taktik bestätigt' if setup.is_confirmed else 'Taktik nicht bestätigt'
    formation_choice_rows = []
    for group in formation_choice_groups():
        formation_choice_rows.append({
            **group,
            'selected': formation[group['name']],
        })
    display_absences = tactic_display_absences(
        unavailable_players_for_squad(club, squad_scope)
    )
    duel_home_club = current_manager_club() or club
    duel_away_club = opponent_club
    if duel_home_club and duel_away_club and duel_away_club.id == duel_home_club.id:
        duel_away_club = club
    if duel_home_club and duel_away_club and duel_away_club.id == duel_home_club.id:
        duel_away_club = None

    def duel_avatar_path(manager_club):
        if manager_club and manager_club.crest_static_path:
            return manager_club.crest_static_path
        return 'game/images/default_player.svg'

    return {
        'club': club,
        'squad_scope': squad_scope,
        'squad_scope_label': squad_scope_label(squad_scope),
        'squad_switch': [
            {'value': 'pro', 'label': 'Profis', 'url': tactic_redirect_url(club, 'pro')},
            {'value': 'youth', 'label': 'Jugend', 'url': tactic_redirect_url(club, 'youth')},
        ],
        'setup': setup,
        'payload': payload,
        'status_label': status_label,
        'status_tone': 'confirmed' if setup.is_confirmed else 'open',
        'formation': formation,
        'formation_code': formation_code(formation),
        'formation_count': field_player_count(formation),
        'formation_slots': slots,
        'selected_field_count': selected_field_count,
        'average_freshness': average_freshness,
        'layer_counts': formation_layer_counts(slots),
        'formation_choices': formation_choice_rows,
        'formation_summary': formation_part_summaries(formation),
        'formation_slot_data': all_valid_formation_slot_data(),
        'player_options': player_options,
        'lineup_player_options': lineup_player_options,
        'player_options_by_id': player_lookup,
        'bench_rows': bench_rows,
        'standard_rows': standard_rows,
        'substitution_rows': substitution_rows,
        'unavailable_players': display_absences,
        'hero_absences': split_absence_labels(display_absences),
        'templates': template_options_for_context(templates),
        'template_count': len(templates),
        'template_limit': 10,
        'first_half': {
            **payload['first_half'],
            'orientation_label': orientation_label(payload['first_half']['orientation']),
            'rows': half_tactic_rows(payload['first_half']),
        },
        'second_half': {
            **payload['second_half'],
            'orientation_label': orientation_label(payload['second_half']['orientation']),
            'rows': half_tactic_rows(payload['second_half']),
        },
        'half_tactic_fields': HALF_TACTIC_FIELDS,
        'tactic_option_groups': TACTIC_OPTION_GROUPS,
        'next_match': next_match,
        'match_date_display': tactic_match_date_display(next_match.get('dateLabel')),
        'competition_logo': competition_logo_static_path(next_match.get('competitionName'), next_match.get('ntNationality')),
        'home_club_url': reverse_club_detail(club),
        'away_club_url': reverse_club_detail(opponent_club) if opponent_club else '#',
        'opponent_club': opponent_club,
        'home_form': form_rows_with_opponents(RESULT_FORM, club),
        'away_form': form_rows_with_opponents(OPPONENT_RESULT_FORM, opponent_club or club),
        'opponent_absences': opponent_absence_rows(opponent_club),
        'top_goals': top_goals,
        'top_assists': top_assists,
        'top_grades': top_grades,
        'manager_duel': {
            'home': 'Kirschgutzje',
            'away': 'AjaxTactician' if opponent_club else 'Gastmanager',
            'home_rank': 'Profi',
            'away_rank': 'Legende',
            'home_avatar': CURRENT_MANAGER_PROFILE_IMAGE,
            'away_avatar': duel_avatar_path(duel_away_club),
            'rows': [
                {'label': 'Titel', 'left': 'Profi', 'right': 'Legende', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Trophäen', 'left': '5', 'right': '12', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Highscore', 'left': '2.150', 'right': '2.430', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Registriert seit', 'left': '12.03.2018', 'right': '01.07.2017', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Spiele', 'left': '1.254', 'right': '1.482', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Siege', 'left': '782', 'right': '912', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Unentschieden', 'left': '241', 'right': '270', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Niederlagen', 'left': '231', 'right': '300', 'left_tone': 'lead', 'right_tone': 'trail'},
                {'label': 'Punkte pro Spiel', 'left': '2,02', 'right': '2,04', 'left_tone': 'trail', 'right_tone': 'lead'},
            ],
        },
        'warnings': standard_rows,
        'form_errors': form_errors or [],
        'game_header': build_game_header(
            'Taktik',
            f'{club.name} · {squad_scope_label(squad_scope)}',
            reverse_club_detail(club),
            club,
            opponent_club,
            calendar_offset_from_request(request),
        ),
    }


def player_match_state_from_option(option, slot_code):
    if not option:
        return 'empty'
    if slot_code in option['main_positions']:
        return 'main'
    if slot_code in option['secondary_positions']:
        return 'secondary'
    return 'foreign'


def club_detail(request, club_id):
    club = get_object_or_404(
        Club.objects.select_related('league'),
        id=club_id
    )
    context = build_club_profile_context(club)
    opponent_club = context['opponent_club']
    context['game_header'] = build_game_header(
        club.name,
        f'Saison 2026/27 · {club.league.name}',
        '/clubs/',
        club,
        opponent_club,
        calendar_offset_from_request(request),
    )

    return render(
        request,
        'game/club_detail.html',
        context,
    )


def club_tactics(request, club_id):
    club = get_object_or_404(
        Club.objects.select_related('league'),
        id=club_id,
    )
    squad_scope = normalize_squad_scope(
        request.POST.get('squad_scope') or request.GET.get('squad')
    )
    setup, _created = TacticSetup.objects.get_or_create(
        club=club,
        squad_scope=squad_scope,
    )

    if request.method == 'POST':
        action = request.POST.get('action', 'confirm')

        if action == 'load_template':
            template_id = request.POST.get('template_id')
            if not template_id:
                context = build_tactics_context(
                    request,
                    club,
                    setup,
                    squad_scope,
                    form_errors=['Bitte eine Vorlage auswählen.'],
                )
                return render(request, 'game/tactics.html', context)

            template = get_object_or_404(
                TacticTemplate,
                id=template_id,
                club=club,
                squad_scope=squad_scope,
            )
            available_ids = {
                option['id']
                for option in player_options_for_squad(club, squad_scope)
            }
            payload = sanitize_payload(tactic_template_payload(template), available_ids)
            copy_payload_to_setup(setup, payload, confirmed=False)
            setup.full_clean()
            setup.save()
            messages.success(request, f'Vorlage "{template.name}" geladen.')
            return redirect(tactic_redirect_url(club, squad_scope, loaded=1))

        parsed = parse_tactic_payload_from_post(request.POST, club, squad_scope)
        payload = parsed['payload']
        errors = list(parsed['errors'])

        if action == 'save_template':
            template_name = (request.POST.get('template_name') or '').strip()
            if not template_name:
                errors.append('Bitte einen Namen für die Vorlage eingeben.')
            existing_template = TacticTemplate.objects.filter(
                club=club,
                squad_scope=squad_scope,
                name=template_name,
            ).first() if template_name else None
            if (
                template_name
                and existing_template is None
                and club.tactic_templates.filter(squad_scope=squad_scope).count() >= 10
            ):
                errors.append('Es sind maximal 10 Taktikvorlagen pro Bereich erlaubt.')
            if errors:
                context = build_tactics_context(
                    request,
                    club,
                    setup,
                    squad_scope,
                    payload=payload,
                    form_errors=errors,
                )
                return render(request, 'game/tactics.html', context)

            template = existing_template or TacticTemplate(
                club=club,
                squad_scope=squad_scope,
                name=template_name,
            )
            template.formation = payload['formation']
            template.lineup = payload['lineup']
            template.bench = payload['bench']
            template.standards = payload['standards']
            template.substitutions = payload['substitutions']
            template.first_half = payload['first_half']
            template.second_half = payload['second_half']
            template.full_clean()
            template.save()
            messages.success(request, f'Vorlage "{template.name}" gespeichert.')
            return redirect(tactic_redirect_url(club, squad_scope, template_saved=1))

        errors.extend(confirm_errors_for_payload(payload))
        if errors:
            context = build_tactics_context(
                request,
                club,
                setup,
                squad_scope,
                payload=payload,
                form_errors=errors,
            )
            return render(request, 'game/tactics.html', context)

        copy_payload_to_setup(
            setup,
            payload,
            confirmed=True,
            confirmed_at=timezone.now(),
        )
        setup.full_clean()
        setup.save()
        messages.success(request, 'Taktik bestätigt und gespeichert.')
        return redirect(tactic_redirect_url(club, squad_scope, confirmed=1))

    context = build_tactics_context(request, club, setup, squad_scope)
    return render(request, 'game/tactics.html', context)


def club_professional_squad(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Profikader',
        'Der öffentliche Profikader wird als nächster Detailbereich ausgebaut.',
    )


def club_youth_squad(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Jugendkader',
        'Der öffentliche Jugendkader wird als nächster Detailbereich ausgebaut.',
    )


def club_table(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Ligatabelle',
        'Die komplette öffentliche Tabelle wird als eigener Bereich vorbereitet.',
    )


def club_match_preview(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Spielvorschau',
        'Die öffentliche Spielvorschau wird als eigener Matchbereich vorbereitet.',
    )


def club_match_report(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Spielbericht',
        'Der öffentliche Spielbericht wird als eigener Matchbereich vorbereitet.',
    )


def club_news(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Vereinsnews',
        'Alle öffentlichen Vereinsmeldungen werden hier gebündelt.',
    )


def club_news_detail(request, club_id, news_id):
    club = get_object_or_404(Club.objects.select_related('league'), id=club_id)
    news_item = get_object_or_404(ClubNewsItem, club=club, id=news_id)
    return render_public_club_stub(
        request,
        club_id,
        news_item.title,
        f'Meldung vom {news_item.published_at:%d.%m.%Y}.',
    )


def render_public_club_stub(request, club_id, title, copy):
    club = get_object_or_404(Club.objects.select_related('league'), id=club_id)
    opponent_club = Club.objects.exclude(id=club.id).order_by('name').first()
    return render(
        request,
        'game/club_profile/stub_page.html',
        {
            'club': club,
            'stub_title': title,
            'stub_copy': copy,
            'game_header': build_game_header(
                title,
                club.name,
                reverse_club_detail(club),
                club,
                opponent_club,
                calendar_offset_from_request(request),
            ),
        },
    )


def reverse_club_detail(club):
    return f'/clubs/{club.id}/'


def _player_nation_nt_logo(player):
    from django.contrib.staticfiles import finders
    from game.models import COUNTRY_FLAG_ASSETS

    registered = (player.nt_nationality or '').strip()
    if registered and registered in COUNTRY_FLAG_ASSETS:
        asset_id = COUNTRY_FLAG_ASSETS[registered]['asset_id']
        flag_path = f'game/images/flags/{asset_id}.svg'
    else:
        badges = player.nationality_badges
        if not badges:
            return ''
        asset_id = badges[0].get('flag_static_path', '').replace('game/images/flags/', '').replace('.svg', '').replace('.png', '')
        flag_path = badges[0].get('flag_static_path', '')

    for ext in ('png', 'svg'):
        nt_path = f'game/images/crests/nt_{asset_id}.{ext}'
        if finders.find(nt_path):
            return nt_path
    if flag_path and finders.find(flag_path):
        return flag_path
    return ''


def _player_nation_nt_name(player):
    registered = (player.nt_nationality or '').strip()
    if registered:
        return registered
    badges = player.nationality_badges
    if badges:
        return badges[0].get('name', '')
    return ''


def player_detail(request, player_id):
    player = get_object_or_404(
        Player.objects.select_related(
            'club',
            'club__league',
            'real_life_club',
            'real_life_club__league',
            'strength_profile',
        ),
        id=player_id,
    )
    all_season_rows = list(
        PlayerSeasonStat.objects.filter(player=player).order_by(
            '-season_number',
            'competition',
        )
    )
    selected_season_number = max(
        (row.season_number for row in all_season_rows),
        default=1,
    )
    season_rows = [
        row
        for row in all_season_rows
        if row.season_number == selected_season_number
    ]
    market_rows = latest_in_chronological_order(
        player.market_value_snapshots.select_related('source')
    )
    transfer_rows = PlayerTransferHistory.objects.select_related(
        'from_club',
        'to_club',
    ).filter(player=player)[:6]
    injury_rows = PlayerInjuryRecord.objects.filter(player=player)[:5]
    suspension_rows = PlayerSuspensionRecord.objects.filter(player=player)[:5]
    all_award_rows = list(PlayerAwardTitle.objects.filter(player=player))
    award_paginator = Paginator(all_award_rows, 4)
    award_page = award_paginator.get_page(request.GET.get('awards_page'))
    market_points = market_chart_points(
        market_rows,
        player.market_value,
    )
    market_trend = compute_market_value_trend(market_rows)
    award_total_count = sum(row.count for row in all_award_rows)
    freshness = None
    if hasattr(player, 'strength_profile'):
        freshness = player.strength_profile.freshness

    nt_nationality = (
        player.nt_nationality
        or (player.nationalities.split(',')[0].strip() if player.nationalities else None)
    )

    return render(
        request,
        'game/player_detail.html',
        {
            'player': player,
            'season_rows': performance_visual_rows(
                preview_performance_rows(
                    season_table_rows(season_rows, nt_nationality=nt_nationality),
                    6,
                    nt_nationality=nt_nationality,
                )
            ),
            'season_summary': career_summary_from_ws_stats(season_rows),
            'career_summary': career_summary_from_ws_stats(all_season_rows),
            'career_rows': performance_visual_rows(
                preview_performance_rows(
                    career_rows_from_ws_stats(all_season_rows, nt_nationality=nt_nationality),
                    8,
                    nt_nationality=nt_nationality,
                )
            ),
            'market_rows': market_rows,
            'market_trend': market_trend,
            'market_points': market_points,
            'market_axis': market_chart_axis(market_points),
            'market_polyline': market_polyline(market_points),
            'market_area_points': market_area_points(market_points),
            'transfer_rows': transfer_display_rows(transfer_rows),
            'injury_rows': injury_rows,
            'suspension_rows': suspension_rows,
            'award_rows': award_page.object_list,
            'award_slots': award_podium_slots(award_page.object_list),
            'award_page': award_page,
            'award_page_range': award_paginator.page_range,
            'award_count': len(all_award_rows),
            'award_total_count': award_total_count,
            'pitch_slots': pitch_position_slots(player),
            'league_logo': (
                competition_logo_static_path(player.club.league.name)
                if player.club and player.club.league
                else ''
            ),
            'freshness': freshness,
            'shirt_number': player.shirt_number,
            'rl_club_crest': (
                player.real_life_club.crest_static_path
                if player.real_life_club
                else (player.club.crest_static_path if player.club else '')
            ),
            'nation_nt_logo': _player_nation_nt_logo(player),
            'nation_nt_name': _player_nation_nt_name(player),
            'nt_confederation_badge_url': nt_confederation_badge(player),
            'game_header': build_game_header(
                'Spielerprofil',
                f"{player.full_name} · {player.club.name if player.club else 'ohne Verein'}",
                f"/clubs/{player.club.id}/" if player.club else '/',
                player.club,
                (
                    Club.objects.exclude(id=player.club.id).order_by('name').first()
                    if player.club
                    else None
                ),
                calendar_offset_from_request(request),
            ),
        }
    )


def player_graph_data(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    market_rows = latest_in_chronological_order(
        player.market_value_snapshots.select_related('source')
    )
    rating_rows = latest_in_chronological_order(
        player.source_rating_snapshots.select_related('source')
    )
    strength_rows = latest_in_chronological_order(
        player.strength_snapshots.all()
    )
    weighted_rating_rows = latest_in_chronological_order(
        player.weighted_rating_snapshots.all()
    )
    match_rating_rows = latest_form_snapshots_in_chronological_order(
        player.form_snapshots.all()
    )
    rating_series = {
        'fm_rating': [],
        'fm_potential': [],
        'sofifa_rating': [],
        'sofifa_potential': [],
    }
    source_to_series = {
        DataSource.CODE_FMINSIDE: ('fm_rating', 'fm_potential'),
        DataSource.CODE_SOFIFA: ('sofifa_rating', 'sofifa_potential'),
        PlayerSourceRating.SOURCE_EA: ('sofifa_rating', 'sofifa_potential'),
    }

    for row in rating_rows:
        series_keys = source_to_series.get(row.source.code)
        if not series_keys:
            continue

        rating_key, potential_key = series_keys
        rating_series[rating_key].append({
            'x': date_label(row.recorded_at),
            'y': row.rating,
            'source': row.source.name,
        })
        if row.potential is not None:
            rating_series[potential_key].append({
                'x': date_label(row.recorded_at),
                'y': row.potential,
                'source': row.source.name,
            })

    return JsonResponse({
        'player': {
            'id': player.id,
            'wsc_player_id': player.wsc_player_id,
            'name': player.full_name,
        },
        'market_value': [
            {
                'x': date_label(row.recorded_at),
                'y': decimal_number(row.value_eur),
                'source': row.source.name,
                'profile_url': row.profile_url,
            }
            for row in market_rows
        ],
        'source_ratings': rating_series,
        'match_ratings': [
            {
                'x': date_label(row.fixture_date),
                'y': decimal_number(row.rating),
                'source': row.get_source_display(),
                'fixture_id': row.fixture_id,
                'opponent': row.opponent_name,
                'minutes_played': row.minutes_played,
                'goals': row.goals,
                'assists': row.assists,
            }
            for row in match_rating_rows
            if row.rating is not None
        ],
        'weighted_ratings': [
            {
                'x': date_label(row.recorded_at),
                'y': decimal_number(row.weighted_rating),
                'source': row.get_source_display(),
                'fixture_reference': row.fixture_reference,
                'rating_minutes': row.rating_minutes,
                'match_count': row.match_count,
                'window_label': row.window_label,
            }
            for row in weighted_rating_rows
        ],
        'strength': {
            'base_strength': [
                {
                    'x': date_label(row.recorded_at),
                    'y': decimal_number(row.base_strength),
                    'match_reference': row.match_reference,
                }
                for row in strength_rows
            ],
            'final_strength': [
                {
                    'x': date_label(row.recorded_at),
                    'y': decimal_number(row.final_strength),
                    'match_reference': row.match_reference,
                }
                for row in strength_rows
            ],
            'max_strength': [
                {
                    'x': date_label(row.recorded_at),
                    'y': decimal_number(row.max_strength),
                    'match_reference': row.match_reference,
                }
                for row in strength_rows
            ],
            'last_10_average_strength': [
                {
                    'x': date_label(row.recorded_at),
                    'y': decimal_number(row.last_10_average_strength),
                    'match_reference': row.match_reference,
                }
                for row in strength_rows
                if row.last_10_average_strength is not None
            ],
        },
    })
