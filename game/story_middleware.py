"""Fail-closed result boundary applied before HTML/API/cache materialization.

Scoped club/league routes do not lock independent competitions. Global
aggregations are replaced with a safe conference list while results are live.
Non-result tools remain usable; their shared calendar is separately protected.
"""
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from .story_release import active_rounds, is_released

# These are read surfaces (and result-publishing actions), not simulation tools.
# Unscoped aggregates necessarily include multiple competitions.
RESULT_VIEWS = {
    'home', 'calendar', 'club_list', 'club_detail', 'club_squad',
    'club_match_report', 'match_report_by_id', 'club_match_preview',
    'club_match_fixture_preview', 'club_news', 'club_news_detail', 'club_news_publish',
    'player_detail', 'player_graph_data', 'league_detail', 'datacenter',
    'data_center', 'manager_profile', 'public_manager_profile',
    'management_friendlies', 'notifications_page', 'creator_dashboard',
    'creator_club_edit', 'creator_league_edit', 'creator_timeline_overview',
    'cup_tree', 'management_finanzen', 'president_office', 'club_records',
    'community_tournament_detail', 'tournament_detail',
    'club_professional_squad', 'club_youth_squad', 'club_table',
    'management_halloffame', 'management_sportgericht', 'management_sponsoring',
    'creator_overview', 'creator_club', 'creator_league',
    'close_matchday', 'creator_cup_advance',
    'creator_index', 'creator_finanzanalyse', 'creator_simulation_diagnostics',
    'creator_system_diagnostics', 'management_sponsoring_finanzen_compat',
    'creator_player_edit', 'creator_manager_edit', 'creator_manager_list',
    'creator_referee_list', 'creator_referee_edit',
    'simulate_matchday', 'creator_cup_simulate_round', 'creator_season_end',
}
SIMULATION_VIEWS = {'simulate_matchday', 'creator_cup_simulate_round'}


class StoryReleaseMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        name = request.resolver_match.url_name or ''
        if (name not in RESULT_VIEWS
                and request.resolver_match.namespace != 'admin'):
            return None
        request._story_result_route = (name, view_kwargs)
        if name in SIMULATION_VIEWS and request.method == 'POST':
            return None  # permit idempotent retries; mask the resulting response
        return self._guard(request, name, view_kwargs)

    def _guard(self, request, name, kwargs):
        from .models import SimulatedMatch, Player, Club, ManagerProfile
        rounds = list(active_rounds())
        request._story_active_rounds = rounds
        if not rounds:
            return None
        if name == 'match_report_by_id':
            sm = SimulatedMatch.objects.select_related('story_round').filter(pk=kwargs['sm_id']).first()
            if not sm or is_released(sm):
                return None
            from .views_story import ticker_page
            return ticker_page(request, sm.pk)
        if 'league_id' in kwargs:
            rounds = [r for r in rounds if r.league_id == kwargs['league_id']]
            season = kwargs.get('season') or request.GET.get('season')
            if season is not None:
                rounds = [r for r in rounds if not r.key.startswith('league:')
                          or r.key.split(':')[2] == str(season)]
        elif 'club_id' in kwargs:
            rounds = [r for r in rounds if kwargs['club_id'] in r.club_ids]
        elif 'player_id' in kwargs:
            club_id = Player.objects.filter(pk=kwargs['player_id']).values_list('club_id', flat=True).first()
            rounds = [r for r in rounds if club_id in r.club_ids]
        elif 'manager_id' in kwargs:
            club_id = Club.objects.filter(managed_by_id=kwargs['manager_id']).values_list('pk', flat=True).first()
            rounds = [r for r in rounds if club_id in r.club_ids]
        elif name == 'public_manager_profile':
            manager_id = ManagerProfile.objects.filter(user__username=kwargs['username']).values_list('pk', flat=True).first()
            club_id = Club.objects.filter(managed_by_id=manager_id).values_list('pk', flat=True).first()
            rounds = [r for r in rounds if club_id in r.club_ids]
        elif name in ('manager_profile', 'management_finanzen', 'president_office',
                      'management_halloffame', 'management_sportgericht', 'management_sponsoring'):
            club_id = Club.objects.filter(managed_by__user_id=request.user.pk).values_list('pk', flat=True).first()
            rounds = [r for r in rounds if club_id in r.club_ids]
        if not rounds:
            return None
        if name == 'club_match_report' and request.method == 'GET':
            club_id = kwargs['club_id']
            sm = SimulatedMatch.objects.filter(
                Q(home_club_id=club_id) | Q(away_club_id=club_id),
                story_round_id__in=[r.pk for r in rounds],
            ).order_by('-simulated_at').first()
            if sm:
                from .views_story import ticker_page
                return ticker_page(request, sm.pk)
        safe = [{'id': r.pk, 'label': r.label, 'url': reverse('story_conference', args=[r.pk])} for r in rounds]
        if name.endswith('_data') or request.headers.get('Accept') == 'application/json':
            response = JsonResponse({'status': 'results_locked', 'rounds': safe}, status=423)
        else:
            response = render(request, 'game/live_locked.html', {'rounds': safe}, status=423)
        response['Cache-Control'] = 'private, no-store'
        return response

    def process_response(self, request, response):
        # A simulation POST may start a round during the request. Never return
        # its freshly completed report or embedded JSON in that same response.
        route = getattr(request, '_story_result_route', None)
        if route and request.method == 'POST' and response.status_code < 400:
            guarded = self._guard(request, *route)
            if guarded is not None:
                return guarded
        if route:
            response['Cache-Control'] = 'private, no-store'
        return response