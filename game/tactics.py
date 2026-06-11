from copy import deepcopy
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db.models import Q


SQUAD_PRO = 'pro'
SQUAD_YOUTH = 'youth'
SQUAD_SCOPE_CHOICES = [
    (SQUAD_PRO, 'Profis'),
    (SQUAD_YOUTH, 'Jugend'),
]

FORMATION_PARTS = {
    'defense': {
        '3e': ['IV', 'IV', 'IV'],
        '3n': ['LV', 'IV', 'RV'],
        '4n': ['LV', 'IV', 'IV', 'RV'],
        '4o': ['LOV', 'IV', 'IV', 'ROV'],
        '5n': ['LV', 'IV', 'IV', 'IV', 'RV'],
        '5o': ['LOV', 'IV', 'IV', 'IV', 'ROV'],
    },
    'defensive_midfield': {
        '0': [],
        '1': ['DM'],
        '2': ['DM', 'DM'],
        '3': ['DM', 'DM', 'DM'],
    },
    'midfield': {
        '0': [],
        '1': ['ZM'],
        '2': ['ZM', 'ZM'],
        '2o': ['LM', 'RM'],
        '3': ['LM', 'ZM', 'RM'],
        '4': ['LM', 'ZM', 'ZM', 'RM'],
        '5': ['LM', 'ZM', 'ZM', 'ZM', 'RM'],
    },
    'offensive_midfield': {
        '0': [],
        '1': ['OM'],
        '2': ['OM', 'OM'],
        '2o': ['LOM', 'ROM'],
        '3': ['LOM', 'OM', 'ROM'],
    },
    'attack': {
        '1': ['ST'],
        '2': ['ST', 'ST'],
        '3': ['LF', 'ST', 'RF'],
        '4': ['LF', 'ST', 'ST', 'RF'],
    },
}

FORMATION_LABELS = {
    'defense': 'Abwehr',
    'defensive_midfield': 'Defensives Mittelfeld',
    'midfield': 'Mittelfeld',
    'offensive_midfield': 'Offensives Mittelfeld',
    'attack': 'Angriff',
}

FORMATION_ORDER = [
    'defense',
    'defensive_midfield',
    'midfield',
    'offensive_midfield',
    'attack',
]

DEFAULT_FORMATION = {
    'defense': '4n',
    'defensive_midfield': '0',
    'midfield': '4',
    'offensive_midfield': '0',
    'attack': '2',
}

DEFAULT_HALF_TACTIC = {
    'orientation': 50,
    'defense': 'standard',
    'midfield': 'standard',
    'attack': 'standard',
    'effort': 'normal',
}

DEFAULT_STANDARDS = {
    'captain': '',
    'penalty': '',
    'free_kick': '',
    'corner': '',
}

STANDARD_FIELDS = [
    ('captain', 'Kapitän'),
    ('penalty', 'Elfmeter'),
    ('free_kick', 'Freistoß'),
    ('corner', 'Ecken'),
]

HALF_TACTIC_FIELDS = [
    ('defense', 'Abwehr'),
    ('midfield', 'Mittelfeld'),
    ('attack', 'Angriff'),
    ('effort', 'Einsatz'),
]

TACTIC_OPTION_GROUPS = {
    'defense': [('standard', 'Standard')],
    'midfield': [('standard', 'Standard')],
    'attack': [('standard', 'Standard')],
    'effort': [('normal', 'Normal')],
}

RESULT_FORM = [
    {'label': 'S', 'tone': 'win', 'score': '2:1'},
    {'label': 'U', 'tone': 'draw', 'score': '1:1'},
    {'label': 'S', 'tone': 'win', 'score': '3:0'},
    {'label': 'N', 'tone': 'loss', 'score': '0:2'},
    {'label': 'S', 'tone': 'win', 'score': '2:1'},
]

OPPONENT_RESULT_FORM = [
    {'label': 'S', 'tone': 'win', 'score': '1:0'},
    {'label': 'U', 'tone': 'draw', 'score': '2:2'},
    {'label': 'N', 'tone': 'loss', 'score': '1:3'},
    {'label': 'S', 'tone': 'win', 'score': '2:0'},
    {'label': 'N', 'tone': 'loss', 'score': '1:2'},
]


def default_formation():
    return deepcopy(DEFAULT_FORMATION)


def default_lineup():
    return {}


def default_bench():
    return []


def default_standards():
    return deepcopy(DEFAULT_STANDARDS)


def default_substitutions():
    return []


def default_half_tactic():
    return deepcopy(DEFAULT_HALF_TACTIC)


def normalize_squad_scope(value):
    return SQUAD_YOUTH if value == SQUAD_YOUTH else SQUAD_PRO


def normalize_formation(raw_formation):
    formation = default_formation()
    raw_formation = raw_formation or {}
    for part in FORMATION_ORDER:
        value = str(raw_formation.get(part, formation[part]))
        if value in FORMATION_PARTS[part]:
            formation[part] = value
    return formation


def formation_positions(formation, include_goalkeeper=True):
    normalized = normalize_formation(formation)
    positions = ['TW'] if include_goalkeeper else []
    for part in FORMATION_ORDER:
        positions.extend(FORMATION_PARTS[part][normalized[part]])
    return positions


def field_player_count(formation):
    return len(formation_positions(formation, include_goalkeeper=False))


def formation_code(formation):
    normalized = normalize_formation(formation)
    return '-'.join(normalized[part] for part in FORMATION_ORDER)


def validate_formation(formation):
    normalized = normalize_formation(formation)
    for part in FORMATION_ORDER:
        if normalized[part] not in FORMATION_PARTS[part]:
            raise ValidationError({part: 'Ungueltiger Formationsteil.'})

    count = field_player_count(normalized)
    if count != 10:
        raise ValidationError(
            f'Die Formation muss genau 10 Feldspieler enthalten. Aktuell: {count}.'
        )
    return normalized


def x_positions(count):
    return {
        0: [],
        1: [50],
        2: [38, 62],
        3: [25, 50, 75],
        4: [18, 39, 61, 82],
        5: [13, 32, 50, 68, 87],
    }[count]


def line_y(part, code):
    return {
        'goalkeeper': 88,
        'defense': 74,
        'defensive_midfield': 59,
        'midfield': 44,
        'offensive_midfield': 29,
        'attack': 14,
    }[part]


def slot_key_for(code, occurrence):
    return f'{code}-{occurrence}'


def slot_y_for_position(part, code, position):
    if part == 'defense' and position in {'LOV', 'ROV'}:
        return 64
    return line_y(part, code)


def formation_slots(formation):
    normalized = normalize_formation(formation)
    counters = {}
    slots = []

    def add_slot(code, x, y, group):
        counters[code] = counters.get(code, 0) + 1
        occurrence = counters[code]
        slots.append({
            'key': slot_key_for(code, occurrence),
            'code': code,
            'x': x,
            'y': y,
            'group': group,
        })

    add_slot('TW', 50, line_y('goalkeeper', 'TW'), 'goalkeeper')
    for part in FORMATION_ORDER:
        code = normalized[part]
        part_positions = FORMATION_PARTS[part][code]
        xs = x_positions(len(part_positions))
        for index, position in enumerate(part_positions):
            add_slot(position, xs[index], slot_y_for_position(part, code, position), part)

    return slots


def formation_part_summaries(formation):
    normalized = normalize_formation(formation)
    summaries = [{'label': 'Torwart', 'code': 'TW', 'positions': 'TW'}]
    for part in FORMATION_ORDER:
        positions = FORMATION_PARTS[part][normalized[part]]
        summaries.append({
            'label': FORMATION_LABELS[part],
            'code': normalized[part],
            'positions': ', '.join(positions) if positions else 'keine',
        })
    return summaries


def formation_choice_groups():
    groups = []
    for part in FORMATION_ORDER:
        options = []
        for code, positions in FORMATION_PARTS[part].items():
            options.append({
                'value': code,
                'label': code,
                'summary': ', '.join(positions) if positions else 'keine',
                'count': len(positions),
            })
        groups.append({
            'name': part,
            'label': FORMATION_LABELS[part],
            'options': options,
        })
    return groups


def orientation_label(value):
    value = int(value or 0)
    if value <= 20:
        return 'Sehr defensiv'
    if value <= 40:
        return 'Defensiv'
    if value <= 60:
        return 'Normal'
    if value <= 80:
        return 'Offensiv'
    return 'Sehr offensiv'


def freshness_value(player):
    profile = getattr(player, 'strength_profile', None)
    if profile is None:
        return None
    return int(round(float(profile.freshness)))


def freshness_tone(value):
    if value is None:
        return 'empty'
    if value >= 80:
        return 'fresh'
    if value >= 60:
        return 'ok'
    if value >= 40:
        return 'warn'
    return 'bad'


def player_position_label(player):
    positions = player.main_positions or player.secondary_positions
    if positions:
        return '/'.join(positions)
    return player.position or '-'


def player_match_state(player, slot_code):
    if slot_code in player.main_positions:
        return 'main'
    if slot_code in player.secondary_positions:
        return 'secondary'
    return 'foreign'


def player_queryset_for_squad(club, squad_scope):
    queryset = (
        club.player_set.select_related('strength_profile')
        .filter(
            Q(ws_injury_days_remaining=0) | Q(ws_injury_days_remaining__isnull=True),
            Q(ws_suspension_matches_remaining=0)
            | Q(ws_suspension_matches_remaining__isnull=True),
        )
        .order_by('last_name', 'first_name', 'id')
    )
    if normalize_squad_scope(squad_scope) == SQUAD_YOUTH:
        return queryset.filter(age__lte=21)
    return queryset.filter(age__gt=21)


def player_options_for_squad(club, squad_scope):
    from game.models import PlayerFormSnapshot
    players = list(player_queryset_for_squad(club, squad_scope))

    player_ids = [p.id for p in players]
    snapshots = (
        PlayerFormSnapshot.objects
        .filter(player_id__in=player_ids, rating__isnull=False)
        .order_by('player_id', '-fixture_date', '-fixture_id')
        .values_list('player_id', 'rating')
    )
    form_series: dict = {}
    for pid, rating in snapshots:
        bucket = form_series.setdefault(pid, [])
        if len(bucket) < 5:
            bucket.append(float(rating))
    form_map = {pid: list(reversed(vals)) for pid, vals in form_series.items()}

    options = []
    for player in players:
        freshness = freshness_value(player)

        recent = form_map.get(player.id, [])
        form_bars = []
        for v in recent:
            grade = 'good' if v < 3.0 else ('ok' if v < 5.0 else 'weak')
            form_bars.append({
                'val': round(v, 2),
                'height_pct': round((6.0 - v) / 5.0 * 100),
                'grade': grade,
            })
        form_empty_bars = [None] * (5 - len(form_bars))

        options.append({
            'id': player.id,
            'id_string': str(player.id),
            'name': player.full_name,
            'position': player_position_label(player),
            'freshness': freshness,
            'freshness_label': f'{freshness}%' if freshness is not None else '-',
            'freshness_tone': freshness_tone(freshness),
            'portrait': player.portrait_static_path,
            'profile_url': f'/players/{player.id}/',
            'main_positions': player.main_positions,
            'secondary_positions': player.secondary_positions,
            'main_positions_label': ', '.join(player.main_positions) or '-',
            'secondary_positions_label': ', '.join(player.secondary_positions) or '-',
            'form_bars': form_bars,
            'form_empty_bars': form_empty_bars,
        })
    return options


def unavailable_players_for_squad(club, squad_scope):
    queryset = club.player_set.select_related('strength_profile').order_by(
        'last_name',
        'first_name',
        'id',
    )
    if normalize_squad_scope(squad_scope) == SQUAD_YOUTH:
        queryset = queryset.filter(age__lte=21)
    else:
        queryset = queryset.filter(age__gt=21)

    rows = []
    for player in queryset:
        if player.is_ws_injured:
            rows.append({
                'name': player.full_name,
                'reason': player.ws_injury_type,
                'tone': 'injury',
            })
        if player.is_ws_suspended:
            rows.append({
                'name': player.full_name,
                'reason': player.ws_suspension_reason,
                'tone': 'suspension',
            })
    return rows


def clean_player_id(value, available_ids):
    if value in (None, ''):
        return ''
    try:
        player_id = int(value)
    except (TypeError, ValueError):
        return ''
    return player_id if player_id in available_ids else ''


def sanitize_assignments(lineup, bench, available_ids):
    assigned = {}
    sanitized_lineup = {}
    sanitized_bench = []

    for slot_key, raw_player_id in lineup.items():
        player_id = clean_player_id(raw_player_id, available_ids)
        if not player_id:
            sanitized_lineup[slot_key] = ''
            continue
        if player_id in assigned:
            old_area, old_key = assigned[player_id]
            if old_area == 'lineup':
                sanitized_lineup[old_key] = ''
            else:
                sanitized_bench[old_key] = ''
        assigned[player_id] = ('lineup', slot_key)
        sanitized_lineup[slot_key] = player_id

    for index, raw_player_id in enumerate(bench[:7]):
        player_id = clean_player_id(raw_player_id, available_ids)
        if not player_id:
            sanitized_bench.append('')
            continue
        if player_id in assigned:
            old_area, old_key = assigned[player_id]
            if old_area == 'lineup':
                sanitized_lineup[old_key] = ''
            else:
                sanitized_bench[old_key] = ''
        assigned[player_id] = ('bench', index)
        sanitized_bench.append(player_id)

    while len(sanitized_bench) < 7:
        sanitized_bench.append('')

    return sanitized_lineup, sanitized_bench


@dataclass
class SubstitutionValidation:
    substitutions: list
    errors: list


def validate_substitutions(raw_rows, lineup, bench):
    errors = []
    cleaned = []
    field_players = {player_id for player_id in lineup.values() if player_id}
    bench_players = {player_id for player_id in bench if player_id}
    already_subbed_in = set()

    for index, row in enumerate(raw_rows[:5], start=1):
        minute = row.get('minute')
        player_out = row.get('out')
        player_in = row.get('in')
        if not minute and not player_out and not player_in:
            continue
        try:
            minute = int(minute)
        except (TypeError, ValueError):
            errors.append(f'Wechsel {index}: Minute ist ungueltig.')
            continue
        if minute < 1 or minute > 120:
            errors.append(f'Wechsel {index}: Minute muss zwischen 1 und 120 liegen.')
            continue
        if not player_out or not player_in:
            errors.append(f'Wechsel {index}: Spieler rein und raus muessen gesetzt sein.')
            continue
        if player_in == player_out:
            errors.append(f'Wechsel {index}: Spieler rein und raus muessen verschieden sein.')
            continue
        if player_in not in bench_players:
            errors.append(f'Wechsel {index}: Der eingewechselte Spieler muss auf der Bank sein.')
            continue
        if player_out not in field_players:
            errors.append(f'Wechsel {index}: Der ausgewechselte Spieler muss zu diesem Zeitpunkt auf dem Feld sein.')
            continue
        if player_in in already_subbed_in:
            errors.append(f'Wechsel {index}: Ein Spieler darf nicht doppelt eingewechselt werden.')
            continue

        field_players.remove(player_out)
        field_players.add(player_in)
        bench_players.discard(player_in)
        already_subbed_in.add(player_in)
        cleaned.append({
            'minute': minute,
            'out': player_out,
            'in': player_in,
        })

    return SubstitutionValidation(cleaned, errors)


def sanitize_payload(payload, available_ids):
    payload = payload or {}
    formation = normalize_formation(payload.get('formation'))
    slot_keys = [slot['key'] for slot in formation_slots(formation)]
    raw_lineup = payload.get('lineup') or {}
    raw_bench = payload.get('bench') or []
    lineup, bench = sanitize_assignments(
        {slot_key: raw_lineup.get(slot_key, '') for slot_key in slot_keys},
        list(raw_bench),
        available_ids,
    )
    lineup_ids = {player_id for player_id in lineup.values() if player_id}
    standards = {}
    raw_standards = payload.get('standards') or {}
    for key, _label in STANDARD_FIELDS:
        standards[key] = clean_player_id(raw_standards.get(key, ''), lineup_ids)

    substitutions = validate_substitutions(
        payload.get('substitutions') or [],
        lineup,
        bench,
    ).substitutions

    return {
        'formation': formation,
        'lineup': lineup,
        'bench': bench,
        'standards': standards,
        'substitutions': substitutions,
        'first_half': {**default_half_tactic(), **(payload.get('first_half') or {})},
        'second_half': {**default_half_tactic(), **(payload.get('second_half') or {})},
    }


def tactic_payload_from_setup(setup):
    return {
        'formation': normalize_formation(setup.formation),
        'lineup': setup.lineup or {},
        'bench': setup.bench or [],
        'standards': {**default_standards(), **(setup.standards or {})},
        'substitutions': setup.substitutions or [],
        'first_half': {**default_half_tactic(), **(setup.first_half or {})},
        'second_half': {**default_half_tactic(), **(setup.second_half or {})},
    }


def copy_payload_to_setup(setup, payload, confirmed=False, confirmed_at=None):
    setup.formation = normalize_formation(payload.get('formation'))
    setup.lineup = payload.get('lineup') or {}
    setup.bench = payload.get('bench') or []
    setup.standards = {**default_standards(), **(payload.get('standards') or {})}
    setup.substitutions = payload.get('substitutions') or []
    setup.first_half = {**default_half_tactic(), **(payload.get('first_half') or {})}
    setup.second_half = {**default_half_tactic(), **(payload.get('second_half') or {})}
    setup.is_confirmed = confirmed
    setup.confirmed_at = confirmed_at if confirmed else None
    return setup
