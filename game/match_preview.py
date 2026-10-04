"""Read-only match briefing. Never simulate, backfill or invent missing data."""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.exceptions import ObjectDoesNotExist
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from .asset_urls import (
    asset_url, assets_root, club_stadium_url, default_player_url, resolve_stadium_url,
)
from .fixture_display import get_form_rows, get_last_match
from .models import DayWeather, GameSeasonState, Player, PlayerSeasonStat, Referee
from .tactics import FORMATION_ORDER, FORMATION_PARTS
from .weather_service import weather_context


def _date(value):
    return value.strftime('%d.%m.%Y') if value else ''


def _image(path):
    if not path:
        return ''
    if path.startswith(('/', 'https://', 'http://')):
        return path
    return static(path)


def _prefer_existing_image(url, category, filename, legacy):
    """Prefer the canonical pack; use an existing, same-ID local photo if absent."""
    if url == asset_url(category, filename):
        if not (Path(assets_root()) / category / filename).is_file() and finders.find(legacy):
            return static(legacy)
    return url


def _report_portrait(path):
    for prefix in ('/static/assets/players/', '/assets/players/', 'players/'):
        if path and path.startswith(prefix):
            path = asset_url('players', path[len(prefix):])
            break
    url = _image(path)
    filename = url.rsplit('/', 1)[-1]
    match = re.fullmatch(r'face_(\d+)\.(?:png|jpg|jpeg|webp)', filename)
    if match:
        return _prefer_existing_image(
            url, 'players', filename, f'game/images/players/{match[1]}.png',
        )
    return url


def _crest(club):
    return _prefer_existing_image(
        club.crest_static_path, 'clubs/logos', f'{club.fm_inside_id}_club.png',
        f'game/images/crests/{club.fm_inside_id}.png',
    )


def _formation_label(code):
    parts = code.split('-') if isinstance(code, str) else []
    if len(parts) != len(FORMATION_ORDER):
        return ''
    counts = []
    for group, key in zip(FORMATION_ORDER, parts):
        if key not in FORMATION_PARTS[group]:
            return ''
        counts.append(len(FORMATION_PARTS[group][key]))
    return '-'.join(str(count) for count in counts if count) if sum(counts) == 10 else ''


def _pid(value):
    try:
        number = int(value)
        return number if number > 0 else None
    except (ValueError, TypeError):
        return None


def _player(player=None, snapshot=None):
    snapshot = snapshot or {}
    name = snapshot.get('name') or (player.full_name if player else '')
    pid = player.pk if player else _pid(snapshot.get('id'))
    grade = _grade(snapshot.get('rating'))
    return {
        'id': pid, 'name': name, 'short_name': name.split()[-1] if name else '',
        'portrait_url': (
            _report_portrait(player.portrait_url) if player else
            _report_portrait(snapshot.get('portrait_url'))
        ) or default_player_url(),
        'url': reverse('player_detail', kwargs={'player_id': player.pk}) if player else '',
        'position': snapshot.get('position') or (player.position if player else ''),
        'number': snapshot.get('shirt_number', player.shirt_number if player else None),
        'grade_label': f'{grade:.1f}'.replace('.', ',') if grade is not None else '',
    }


def _club(club, kit):
    if not club:
        return None
    label = 'Heim' if kit == 'home' else 'Auswärts'
    kits = {item['label']: item['path'] for item in club.kit_static_paths}
    return {
        'id': club.pk, 'name': club.name, 'short_name': club.short_name,
        'crest_url': _crest(club),
        'url': reverse('club_detail', kwargs={'club_id': club.pk}),
        'kit_url': kits.get(label, ''), 'kit_label': label,
    }


def _stadium(home):
    profile = stadium = None
    if home:
        try:
            profile = home.public_profile
        except ObjectDoesNotExist:
            pass
        try:
            stadium = home.stadium
        except ObjectDoesNotExist:
            pass
    photo = getattr(profile, 'stadium_image_static_path', '')
    return {
        'name': getattr(stadium, 'name', '') or getattr(profile, 'stadium_name', ''),
        'location': getattr(profile, 'city_name', ''),
        'photo_url': resolve_stadium_url(photo) if photo else (
            club_stadium_url(home.fm_inside_id) if home else ''
        ),
        # The user explicitly requested Dortmund's model as a labeled visual test.
        'model_available': bool(home),
        'model_is_demo': bool(home and not (home.pk == 3 and home.fm_inside_id == 907)),
        'model_name': 'Signal Iduna Park · Dortmund',
        'model_scene_url': static('stadium_editor/dortmund_editor_scene.js') + '?v=54',
        'url': reverse('club_detail', kwargs={'club_id': home.pk}) if home else '',
    }


def _trainer(opponent):
    if not opponent or not opponent.managed_by:
        return None
    manager = opponent.managed_by
    path = manager.profile_image
    portrait = path if path.startswith(('/', 'https://', 'http://')) else (
        settings.MEDIA_URL + path if path else ''
    )
    return {
        'name': manager.name, 'portrait_url': portrait,
        'kind': manager.trainer_type_label,
        'url': reverse('public_manager_profile', kwargs={'username': manager.user.username})
        if manager.user else '',
    }


def _grade(value):
    try:
        value = float(value)
        return value if 1 <= value <= 6 else None
    except (ValueError, TypeError):
        return None


def _money(value):
    value = Decimal(value)
    if value >= 1_000_000:
        return f'{value / 1_000_000:.1f}'.replace('.', ',') + ' Mio. €'
    return f'{value:,.0f}'.replace(',', '.') + ' €'


def _referee_profile(referee, *, is_demo=False):
    profile = {
        'name': referee.name, 'portrait_url': referee.face_url(),
        'nationality': getattr(referee, 'nationality', ''),
        'level_label': Referee.LEVEL_LABEL_MAP.get(getattr(referee, 'level', None), ''),
        'summary': getattr(referee, 'schlagwort', '') or 'Profil aus der Schiedsrichterdatenbank.',
        'ratings': [
            {'label': label, 'text': words[getattr(referee, field)]}
            for field, label, words in (
                ('karten_bucket', 'Karten', ('Nachsichtig', 'Ausgewogen', 'Kartenfreudig')),
                ('spielfluss_bucket', 'Spielfluss', ('Pfeift viel ab', 'Ausgewogen', 'Lässt laufen')),
            ) if getattr(referee, field, None) in (0, 1, 2)
        ],
    }
    if is_demo:
        profile['is_demo'] = True
    return profile


def _report_team_stats(report, side):
    """Display actual last-match stats, never fabricate season averages."""
    match_stats = report.get('match_stats') or {}
    result = []
    for key, label, suffix in (
        ('possession', 'Ballbesitz', ' %'), ('shots', 'Schüsse', ''),
        ('shots_on_target', 'Aufs Tor', ''), ('corners', 'Ecken', ''),
    ):
        value = match_stats.get(f'{side}_{key}')
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        if valid and value >= 0 and value != float('inf'):
            formatted = f'{value:g}'.replace('.', ',') + suffix
        else:
            formatted = '—'
        result.append({'label': label, 'value': formatted})
    return result


def _form_stats(club, last_report):
    last, report, side = last_report
    return {
        'name': club.name, 'url': reverse('club_detail', kwargs={'club_id': club.pk}),
        'crest_url': _crest(club), 'form': get_form_rows(club, 5),
        'date_label': _date(last.scheduled_date) if last else '',
        'stats': _report_team_stats(report, side),
    }


def _season_leaders(opponent, players):
    """Club-scoped, current-season statistics; German grades: lower is better."""
    current = GameSeasonState.objects.values_list('current_season', flat=True).first()
    rows = PlayerSeasonStat.objects.filter(
        club=opponent, player__club=opponent, season_number=current,
    ) if current is not None else PlayerSeasonStat.objects.none()
    totals = defaultdict(lambda: {'goals': 0, 'matches': 0, 'weighted': 0.0, 'graded': 0})
    for row in rows:
        bucket = totals[row.player_id]
        bucket['goals'] += row.goals
        bucket['matches'] += row.matches
        grade = _grade(row.average_grade)
        if grade is not None and row.matches:
            bucket['weighted'] += grade * row.matches
            bucket['graded'] += row.matches
    by_id = {p.pk: p for p in players}
    scorers = [(pid, row) for pid, row in totals.items()
               if row['goals'] > 0 and pid in by_id]
    graded = [(pid, row) for pid, row in totals.items()
              if row['graded'] and pid in by_id]
    scorer = min(scorers, key=lambda item: (-item[1]['goals'], item[0])) if scorers else None
    best = min(graded, key=lambda item: (
        item[1]['weighted'] / item[1]['graded'], item[0],
    )) if graded else None
    return [
        {'label': 'Top-Torjäger', 'player': _player(by_id[scorer[0]]) if scorer else None,
         'value': f"{scorer[1]['goals']} Tore" if scorer else '',
         'context': f'Saison {current}' if current is not None else ''},
        {'label': 'Notenbester', 'player': _player(by_id[best[0]]) if best else None,
         'value': f"Ø {best[1]['weighted'] / best[1]['graded']:.2f}".replace('.', ',')
         if best else '', 'context': 'Saisonschnitt'},
    ]


def _last_report(opponent):
    display = get_last_match(opponent)
    if not display:
        return None, {}, ''
    fixture = display._f
    side = 'home' if fixture.home_club_id == opponent.pk else 'away'
    return fixture, fixture.simulated_match.report_data or {}, side


def _report_players(report, side):
    """Re-use the canonical snapshot formation, never today's tactic setup."""
    from .views import _build_pitch_positions

    positions = _build_pitch_positions(report, {}).get(f'{side}_pitch_players', [])
    ratings = report.get(f'{side}_ratings') or []
    ids = {_pid(p.get('id')) for p in positions + ratings} - {None}
    known = Player.objects.in_bulk(ids)
    lineup = [
        {**_player(known.get(_pid(row.get('id'))), row),
         'x': row['pitch_x'], 'y': row['pitch_y']}
        for row in positions
    ]
    # Empty tactical lines must not squeeze adjacent portrait rows together.
    occupied_rows = sorted({row['y'] for row in lineup})
    if len(occupied_rows) > 1:
        display_y = {
            y: 10 + 80 * index / (len(occupied_rows) - 1)
            for index, y in enumerate(occupied_rows)
        }
        for row in lineup:
            row['y'] = display_y[row['y']]
    rated = [row for row in ratings if _grade(row.get('rating')) is not None]
    best = min(rated, key=lambda row: (
        _grade(row['rating']), _pid(row.get('id')) or 0,
    )) if rated else None
    spotlight = {
        'label': 'Spieler des letzten Spiels',
        'player': _player(known.get(_pid(best.get('id'))), best) if best else None,
        'value': f"Note {_grade(best['rating']):.1f}".replace('.', ',') if best else '',
        'context': 'Gegner · letzter Spielbericht',
    }
    return lineup, spotlight


def build_match_preview_context(club, fixture):
    """The page is safe without a fixture or a complete opponent history."""
    home = fixture.home_club if fixture else None
    away = fixture.away_club if fixture else None
    opponent = (away if home.pk == club.pk else home) if fixture else None
    preview = {
        'has_fixture': bool(fixture), 'home': _club(home, 'home'),
        'away': _club(away, 'away'), 'opponent': _club(opponent, 'away'),
        'matchday_label': f'{fixture.matchday}. Spieltag' if fixture and fixture.matchday else '',
        'date_label': _date(fixture.scheduled_date) if fixture else '',
        'time_label': fixture.scheduled_time.strftime('%H:%M Uhr')
        if fixture and fixture.scheduled_time else '',
        'stadium': _stadium(home), 'trainer': _trainer(opponent),
        'referee': None, 'weather': None, 'lineup': [], 'formation_label': '',
        'lineup_date_label': '', 'last_result': None, 'form': [],
        'absences': [], 'injuries': [], 'suspensions': [], 'spotlights': [], 'news': [],
        'home_form': [], 'away_form': [], 'form_stats': [],
        'news_url': reverse('club_news', kwargs={'club_id': opponent.pk}) if opponent else '',
        'default_player_url': default_player_url(),
    }
    # No GET-side weather roll, referee assignment or historical backfill.
    if fixture:
        referee = fixture.simulated_match.referee if fixture.simulated_match_id else None
        if referee:
            preview['referee'] = _referee_profile(referee)
        if fixture.scheduled_date:
            weather = DayWeather.objects.filter(sim_day=fixture.scheduled_date).first()
            preview['weather'] = weather_context(weather) if weather else None
            if preview['weather']:
                preview['weather']['icon_class'] = preview['weather']['type']
        # Display-only test data: never persist or feed these into simulation.
        if not preview['trainer']:
            preview['trainer'] = {
                'name': 'Alexander Weber', 'kind': 'Trainer', 'url': '',
                'portrait_url': static('game/images/managers/default-manager.png'),
                'is_demo': True,
            }
        if not preview['referee']:
            demo_referee = Referee.objects.filter(
                fm_uid__in=(98033209, 85133471),
            ).order_by('pk').first()
            preview['referee'] = _referee_profile(demo_referee, is_demo=True) if demo_referee else {
                'name': 'Max Mustermann', 'is_demo': True,
                'portrait_url': static('game/images/managers/default-manager.png'),
                'nationality': 'Deutschland', 'level_label': 'Testprofil',
                'summary': 'Neutrales Schiedsrichter-Testprofil.',
            }
        if not preview['weather']:
            preview['weather'] = {
                'label': 'Sonnig', 'temperature': 18, 'type': 'normal',
                'icon_class': 'normal', 'is_demo': True,
            }
    if not opponent:
        return preview
    players = list(Player.objects.filter(club=opponent).order_by('pk'))
    preview['news'] = [
        {'title': item.title, 'date_label': _date(item.published_at),
         'url': reverse('club_news_detail', kwargs={'club_id': opponent.pk, 'news_id': item.pk}),
         'thumbnail_url': _image(item.thumbnail_static_path),
         'category': getattr(item, 'category', '') or 'Vereinsnews',
         'author': getattr(item, 'outlet', '') or 'Vereinsredaktion'}
        for item in opponent.public_news.filter(published_at__lte=timezone.localdate())
        .order_by('-published_at', '-pk')[:2]
    ]
    if not preview['news']:
        # Visual examples only: no news records, transfers or club changes.
        name = opponent.short_name or opponent.name
        portrait = _report_portrait(players[0].portrait_url) if players else default_player_url()
        preview['news'] = [
            {'title': f'{name} plant Verstärkung',
             'thumbnail_url': portrait, 'category': 'Transfer-News'},
            {'title': f'{name} vor nächstem Transfer',
             'thumbnail_url': _crest(opponent), 'category': 'Transfer-News'},
        ]
        for item in preview['news']:
            item.update(date_label=_date(timezone.localdate()), url='',
                        author='Vereinsredaktion', is_demo=True)
    preview['form'] = get_form_rows(opponent, 5)
    last, report, side = _last_report(opponent)
    opponent_report = (last, report, side)
    for team in (home, away):
        team_report = opponent_report if team.pk == opponent.pk else _last_report(team)
        team_stats = _form_stats(team, team_report)
        preview['form_stats'].append(team_stats)
        preview['home_form' if team.pk == home.pk else 'away_form'] = team_stats['form']
    lineup, last_best = _report_players(report, side)
    preview['lineup'] = lineup
    preview['formation_label'] = _formation_label(report.get(f'{side}_formation', ''))
    preview['lineup_date_label'] = _date(last.scheduled_date) if last else ''
    if last:
        preview['last_result'] = {
            'home_name': last.home_club.name, 'away_name': last.away_club.name,
            'home_crest': _crest(last.home_club),
            'away_crest': _crest(last.away_club),
            'home_goals': last.home_goals, 'away_goals': last.away_goals,
            'date_label': _date(last.scheduled_date),
            'url': reverse('match_report_by_id', kwargs={'sm_id': last.simulated_match_id}),
        }
    preview['spotlights'] = _season_leaders(opponent, players) + [last_best]
    valued = [p for p in players if p.market_value is not None]
    valuable = min(valued, key=lambda p: (-p.market_value, p.pk)) if valued else None
    preview['spotlights'].append({
        'label': 'Wertvollster Spieler', 'player': _player(valuable) if valuable else None,
        'value': _money(valuable.market_value) if valuable else '', 'context': 'Marktwert',
    })
    for player in players:
        if player.is_ws_injured:
            absence = {
                'player': _player(player), 'kind': 'injury',
                'reason': player.ws_injury_type, 'duration': f'{player.ws_injury_days_remaining} Tage',
            }
            preview['absences'].append(absence)
            preview['injuries'].append(absence)
        if player.is_ws_suspended:
            absence = {
                'player': _player(player), 'kind': 'suspension',
                'reason': player.ws_suspension_reason,
                'duration': f'{player.ws_suspension_matches_remaining} Spiel(e)',
            }
            preview['absences'].append(absence)
            preview['suspensions'].append(absence)
    return preview