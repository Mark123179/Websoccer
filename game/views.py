import os

from django.contrib.staticfiles import finders
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.db.models import Avg, Count, Sum
from .models import (
    Club,
    DataSource,
    League,
    Player,
    PlayerAwardTitle,
    PlayerInjuryRecord,
    PlayerSeasonStat,
    PlayerSourceRating,
    PlayerSuspensionRecord,
    PlayerTransferHistory,
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
                    'title': award.title,
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
                'image_path': None,
                'title': 'Freier Titelplatz',
                'count': None,
                'shape': 'empty',
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


def competition_logo_static_path(competition):
    assets = {
        '1. Bundesliga': 'game/images/competitions/bundesliga.png',
        'Bundesliga': 'game/images/competitions/bundesliga.png',
        'Websoccer Liga': 'game/images/competitions/websoccer-liga.svg',
        'DFB-Pokal': 'game/images/competitions/dfb-pokal.png',
        'Pokal': 'game/images/competitions/dfb-pokal.png',
        'Champions League': 'game/images/competitions/champions-league.png',
        'CL': 'game/images/competitions/champions-league.png',
        'Supercup': 'game/images/competitions/supercup.png',
    }
    return assets.get(competition, '')


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


def season_table_rows(rows):
    return [
        {
            'season_label': f"#{row.season_number}",
            'competition': row.competition,
            'competition_logo': competition_logo_static_path(row.competition),
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


def career_rows_from_ws_stats(rows):
    grouped = {}

    for row in rows:
        bucket = grouped.setdefault(row.competition, {
            'competition': row.competition,
            'competition_logo': competition_logo_static_path(row.competition),
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


def transfer_display_rows(rows):
    display_rows = []

    for row in rows:
        swap_player = None
        swap_club = row.from_club or row.to_club
        if swap_club:
            swap_player = (
                Player.objects.filter(club=swap_club)
                .exclude(id=row.player_id)
                .order_by('last_name', 'first_name')
                .first()
            )

        has_fee = row.fee_eur is not None and row.fee_eur > 0
        if has_fee:
            detail = f'{row.fee_eur:,.0f} EUR'.replace(',', '.')
        elif row.notes:
            detail = row.notes
        else:
            detail = 'Tausch / offen'

        display_rows.append({
            'transfer': row,
            'detail': detail,
            'from_crest': row.from_club.crest_static_path if row.from_club else '',
            'to_crest': row.to_club.crest_static_path if row.to_club else '',
            'swap_player': swap_player,
        })

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
    featured_clubs = list(clubs.order_by('-budget')[:2])
    primary_club = featured_clubs[0] if featured_clubs else None
    secondary_club = featured_clubs[1] if len(featured_clubs) > 1 else None
    top_market_players = Player.objects.select_related(
        'club',
        'strength_profile',
    ).order_by(
        '-market_value',
        '-potential',
        'last_name',
        'first_name',
    )[:4]
    top_strength_players = Player.objects.select_related(
        'club',
        'strength_profile',
    ).filter(
        strength_profile__isnull=False,
    ).order_by(
        '-strength_profile__final_strength',
        '-market_value',
        'last_name',
        'first_name',
    )[:4]

    totals = {
        'league_count': League.objects.count(),
        'club_count': Club.objects.count(),
        'player_count': Player.objects.count(),
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

    return render(
        request,
        'game/home.html',
        {
            'richest_clubs': richest_clubs,
            'primary_club': primary_club,
            'secondary_club': secondary_club,
            'top_market_players': top_market_players,
            'top_strength_players': top_strength_players,
            'totals': totals,
        }
    )


def club_list(request):
    clubs = Club.objects.select_related('league').annotate(
        player_count=Count('player'),
        average_strength=Avg('player__strength_profile__final_strength'),
    )

    return render(
        request,
        'game/club_list.html',
        {
            'clubs': clubs
        }
    )


def club_detail(request, club_id):
    club = get_object_or_404(
        Club.objects.select_related('league'),
        id=club_id
    )
    opponent_club = Club.objects.exclude(id=club.id).order_by('name').first()
    players = club.player_set.select_related('strength_profile').order_by(
        'main_position_1',
        'last_name',
        'first_name',
    )
    average_strength = players.aggregate(
        average=Avg('strength_profile__final_strength')
    )['average']
    total_market_value = players.aggregate(
        total=Sum('market_value')
    )['total'] or 0
    average_age = players.aggregate(
        average=Avg('age')
    )['average']
    player_count = players.count()
    top_market_player = players.order_by('-market_value').first()
    top_strength_player = players.order_by(
        '-strength_profile__final_strength'
    ).first()
    top_potential_player = players.order_by('-potential').first()
    top_salary_player = players.order_by('-salary_per_match').first()
    squad_preview = players.order_by(
        '-strength_profile__final_strength',
        '-market_value',
        'main_position_1',
        'last_name',
        'first_name',
    )[:8]
    notable_market_players = players.order_by(
        '-market_value',
        '-strength_profile__final_strength',
        'last_name',
        'first_name',
    )[:3]
    transfer_targets = Player.objects.select_related(
        'club',
        'club__league',
        'strength_profile',
    ).exclude(
        club=club,
    ).order_by(
        '-market_value',
        '-potential',
        'last_name',
        'first_name',
    )[:3]
    total_salary_per_match = players.aggregate(
        total=Sum('salary_per_match')
    )['total'] or 0
    finance_summary = {
        'budget': club.budget or 0,
        'total_market_value': total_market_value,
        'total_salary_per_match': total_salary_per_match,
        'average_market_value': (
            total_market_value / player_count
            if player_count
            else 0
        ),
        'top_market_player': top_market_player,
        'top_salary_player': top_salary_player,
    }
    league_table_mock = []
    table_clubs = [
        {
            'club_name': club.name,
            'short_name': club.short_name,
            'points': 78,
            'goals_for': 68,
            'goals_against': 29,
        },
        {
            'club_name': opponent_club.name if opponent_club else 'FC Bayern',
            'short_name': opponent_club.short_name if opponent_club else 'FCB',
            'points': 72,
            'goals_for': 61,
            'goals_against': 24,
        },
        {
            'club_name': 'RB Leipzig',
            'short_name': 'RBL',
            'points': 64,
            'goals_for': 59,
            'goals_against': 33,
        },
        {
            'club_name': 'Bayer Leverkusen',
            'short_name': 'B04',
            'points': 59,
            'goals_for': 52,
            'goals_against': 35,
        },
    ]
    seen_short_names = set()

    for table_club in table_clubs:
        short_name = table_club['short_name']
        if short_name in seen_short_names:
            continue

        seen_short_names.add(short_name)
        league_table_mock.append({
            'position': len(league_table_mock) + 1,
            'club_name': table_club['club_name'],
            'short_name': short_name,
            'played': 33,
            'points': table_club['points'],
            'goals': (
                f"{table_club['goals_for']}:"
                f"{table_club['goals_against']}"
            ),
            'goal_difference': (
                table_club['goals_for'] -
                table_club['goals_against']
            ),
            'is_current_club': short_name == club.short_name,
        })

    if not any(row['is_current_club'] for row in league_table_mock):
        league_table_mock.insert(0, {
            'position': 1,
            'club_name': club.name,
            'short_name': club.short_name,
            'played': 33,
            'points': 78,
            'goals': '68:29',
            'goal_difference': 39,
            'is_current_club': True,
        })
        for index, row in enumerate(league_table_mock, start=1):
            row['position'] = index
    match_center_mock = {
        'next_match': {
            'competition': club.league.name if club.league else 'Liga',
            'home_team': club.short_name or club.name,
            'away_team': (
                opponent_club.short_name
                if opponent_club
                else 'FCB'
            ),
            'status': 'Vorschau',
            'kickoff': 'Nächstes Spiel',
        },
        'last_match': {
            'competition': club.league.name if club.league else 'Liga',
            'home_team': 'BVB',
            'away_team': club.short_name or club.name,
            'score': '0:0',
            'status': 'Letztes Spiel',
        },
    }

    return render(
        request,
        'game/club_detail.html',
        {
            'club': club,
            'players': players,
            'player_count': player_count,
            'average_strength': average_strength,
            'average_age': average_age,
            'top_market_player': top_market_player,
            'top_potential_player': top_potential_player,
            'top_salary_player': top_salary_player,
            'top_strength_player': top_strength_player,
            'total_market_value': total_market_value,
            'squad_preview': squad_preview,
            'notable_market_players': notable_market_players,
            'transfer_targets': transfer_targets,
            'finance_summary': finance_summary,
            'league_table_mock': league_table_mock,
            'match_center_mock': match_center_mock,
            'opponent_club': opponent_club,
        }
    )


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
    award_total_count = sum(row.count for row in all_award_rows)
    freshness = None
    if hasattr(player, 'strength_profile'):
        freshness = player.strength_profile.freshness

    return render(
        request,
        'game/player_detail.html',
        {
            'player': player,
            'season_rows': performance_visual_rows(season_table_rows(season_rows)),
            'season_summary': career_summary_from_ws_stats(season_rows),
            'career_summary': career_summary_from_ws_stats(all_season_rows),
            'career_rows': performance_visual_rows(
                career_rows_from_ws_stats(all_season_rows)
            ),
            'market_rows': market_rows,
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
