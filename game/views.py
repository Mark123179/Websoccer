from django.shortcuts import render, get_object_or_404
from django.db.models import Avg, Count, Sum
from .models import Club, League, Player


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
        ).prefetch_related('source_ratings'),
        id=player_id,
    )

    return render(
        request,
        'game/player_detail.html',
        {
            'player': player,
        }
    )
