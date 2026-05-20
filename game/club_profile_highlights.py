import hashlib
import logging
import re
from collections import defaultdict
from decimal import Decimal

from django.urls import reverse

from .competition_assets import competition_logo_static_path, _NATIONALITY_CONFEDERATION
from .models import PlayerFormSnapshot, PlayerSeasonStat

logger = logging.getLogger(__name__)


CURRENT_SEASON = '2026/27'
YOUTH_MAX_AGE = 21


def build_highlights(club, players, season, is_youth):
    if is_youth:
        categories = [
            ('Wertvollster Jugendspieler', 'market', 'max'),
            ('Bester Torschütze', 'goals', 'max'),
            ('Bester Vorbereiter', 'assists', 'max'),
            ('Notenbester', 'grade', 'min'),
        ]
        pool = [player for player in players if player.age <= YOUTH_MAX_AGE] or players
    else:
        categories = [
            ('Wertvollster Spieler', 'market', 'max'),
            ('Bester Torschütze', 'goals', 'max'),
            ('Bester Vorbereiter', 'assists', 'max'),
            ('Bester Passgeber', 'pass_quote', 'max'),
            ('Notenbester Spieler', 'grade', 'min'),
        ]
        pool = [player for player in players if player.age > YOUTH_MAX_AGE] or players

    stats = collect_player_stats(pool, season)
    highlights = []
    for category, metric_key, direction in categories:
        player, value = pick_highlight_player(
            club,
            pool,
            stats,
            category,
            metric_key,
            direction,
            season,
        )
        if not player:
            continue
        highlights.append({
            'category': category,
            'playerId': str(player.id),
            'playerName': player.full_name,
            'position': player.main_position_1 or player.position or player.primary_position or '-',
            'flagUrl': primary_flag(player),
            'ntBadgeUrl': nt_confederation_badge(player),
            'cutoutUrl': player.portrait_static_path,
            'metricLabel': metric_label(metric_key, value),
            'metricTone': metric_key,
            'metricUrl': metric_url(metric_key, player),
            'profileUrl': reverse('player_detail', kwargs={'player_id': player.id}),
        })

    return highlights


def collect_player_stats(players, season):
    player_ids = [player.id for player in players]
    stats = {
        player.id: {
            'market': Decimal(player.market_value or 0),
            'goals': 0,
            'assists': 0,
            'grade': None,
            'pass_quote': None,
        }
        for player in players
    }
    if not player_ids:
        return stats

    season_rows = PlayerSeasonStat.objects.filter(
        player_id__in=player_ids,
        season=season,
    )
    if not season_rows.exists():
        season_rows = PlayerSeasonStat.objects.filter(player_id__in=player_ids)

    grade_values = defaultdict(list)
    for row in season_rows:
        bucket = stats[row.player_id]
        bucket['goals'] += row.goals
        bucket['assists'] += row.assists
        if row.average_grade is not None:
            grade_values[row.player_id].append(Decimal(row.average_grade))

    for player_id, values in grade_values.items():
        stats[player_id]['grade'] = sum(values) / len(values)

    pass_values = defaultdict(list)
    for snapshot in PlayerFormSnapshot.objects.filter(player_id__in=player_ids):
        player_stats = snapshot.raw_payload.get('player_stats', {})
        value = raw_stat_number(player_stats.get('passesAccuracy'))
        if value is not None:
            pass_values[snapshot.player_id].append(Decimal(str(value)))

    for player_id, values in pass_values.items():
        stats[player_id]['pass_quote'] = sum(values) / len(values)

    return stats


def pick_highlight_player(club, players, stats, category, metric_key, direction, season):
    if not players:
        return None, None

    ranked = []
    for player in players:
        value = stats[player.id].get(metric_key)
        if value is None:
            value = fallback_metric(metric_key, player)
        ranked.append((player, value))

    values = [value for _player, value in ranked]
    target = min(values) if direction == 'min' else max(values)
    tied = [player for player, value in ranked if value == target]
    seed = f'{club.id}:{season}:{category}'
    selected = tied[seeded_index(seed, len(tied))]
    return selected, target


def fallback_metric(metric_key, player):
    if metric_key == 'grade':
        return Decimal('1.80')
    if metric_key == 'pass_quote':
        base = getattr(getattr(player, 'strength_profile', None), 'final_strength', None)
        if base is None:
            return Decimal('88')
        return min(Decimal('96'), Decimal('82') + Decimal(base) / Decimal('20'))
    if metric_key in {'goals', 'assists'}:
        return 0
    return Decimal(player.market_value or 0)


def metric_label(metric_key, value):
    if metric_key == 'market':
        return compact_money(value)
    if metric_key == 'goals':
        return f'{int(value)} Tore'
    if metric_key == 'assists':
        return f'{int(value)} Vorlagen'
    if metric_key == 'pass_quote':
        return f'{Decimal(value).quantize(Decimal("1"))} %'
    if metric_key == 'grade':
        return f'{Decimal(value).quantize(Decimal("0.01"))}'.replace('.', ',')
    return str(value)


def metric_url(metric_key, player):
    if metric_key != 'market':
        return ''
    return player.transfermarkt_profile_url or player.transfermarkt_market_value_url or ''


def primary_flag(player):
    for nationality in player.nationality_badges:
        if nationality.get('flag_static_path'):
            return nationality['flag_static_path']
    return ''


def nt_confederation_badge(player):
    nt_nationality = (player.nt_nationality or '').strip()

    if not nt_nationality:
        badges = player.nationality_badges
        nt_nationality = badges[0].get('name', '') if badges else ''

    if not nt_nationality:
        logger.warning(
            'nt_confederation_badge: player %s (id=%s) has no nt_nationality and no '
            'nationality_badges — using generic NT badge.',
            getattr(player, 'full_name', repr(player)),
            getattr(player, 'id', '?'),
        )
        return competition_logo_static_path('Nationalmannschaft', '')

    if nt_nationality not in _NATIONALITY_CONFEDERATION:
        logger.warning(
            'nt_confederation_badge: nationality %r for player %s (id=%s) is not in '
            '_NATIONALITY_CONFEDERATION — falling back to generic NT badge.',
            nt_nationality,
            getattr(player, 'full_name', repr(player)),
            getattr(player, 'id', '?'),
        )

    return competition_logo_static_path('Nationalmannschaft', nt_nationality)


def raw_stat_number(raw_stat):
    if not raw_stat:
        return None
    if isinstance(raw_stat, dict):
        if raw_stat.get('numericValue') is not None:
            return raw_stat['numericValue']
        display_value = raw_stat.get('displayValue', '')
        match = re.search(r'(\d+(?:[,.]\d+)?)\s*%', display_value)
        if match:
            return match.group(1).replace(',', '.')
    return None


def seeded_index(seed, length):
    if length <= 1:
        return 0
    digest = hashlib.sha256(seed.encode('utf-8')).hexdigest()
    return int(digest, 16) % length


def compact_money(value):
    value = Decimal(value or 0)
    if value >= Decimal('1000000000'):
        amount = value / Decimal('1000000000')
        return f'{amount:.2f}'.replace('.', ',') + ' Mrd. €'
    if value >= Decimal('1000000'):
        amount = value / Decimal('1000000')
        return f'{amount:.0f} Mio. €'
    if value >= Decimal('1000'):
        amount = value / Decimal('1000')
        return f'{amount:.0f} Tsd. €'
    return f'{value:.0f} €'
