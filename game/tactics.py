import re
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
    'defense': [
        ('standard', 'Standard'),
        ('kompakt_stehen', 'Kompakt stehen'),
        ('tief_stehen', 'Tief stehen'),
        ('hoeher_stehen', 'Höher stehen'),
        ('absichern', 'Absichern'),
        ('frueh_herausruecken', 'Früh herausrücken'),
    ],
    'midfield': [
        ('standard', 'Standard'),
        ('absichern', 'Absichern'),
        ('kurzpassspiel', 'Kurzpassspiel'),
        ('ballbesitz_sichern', 'Ballbesitz sichern'),
        ('vertikal_spielen', 'Vertikal spielen'),
        ('gegenpressing', 'Gegenpressing'),
    ],
    'attack': [
        ('standard', 'Standard'),
        ('anlaufen', 'Anlaufen'),
        ('kombinieren', 'Kombinieren'),
        ('tiefenlaeufe', 'Tiefenläufe'),
        ('zielspieler_suchen', 'Zielspieler suchen'),
        ('flanke_kopfball', 'Flanke & Kopfball'),
    ],
    'effort': [
        ('schonend', 'Schonend'),
        ('vorsichtig', 'Vorsichtig'),
        ('normal', 'Normal'),
        ('hoch', 'Hoch'),
        ('sehr_hoch', 'Sehr hoch'),
    ],
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


# ---------------------------------------------------------------------------
# Bottom-row tactic instructions (global, shared across both halves)
# ---------------------------------------------------------------------------

PRESSING_LINES = [
    ('defense', 'Abwehr'),
    ('midfield', 'Mittelfeld'),
    ('attack', 'Angriff'),
]

PRESSING_LEVELS = [
    ('passiv', 'Passiv'),
    ('normal', 'Normales Pressing'),
    ('intensiv', 'Intensives Pressing'),
    ('hoch', 'Hohes Pressing'),
]

PRESSING_TRIGGERS = [
    ('ballverlust', 'Nach Ballverlust'),
    ('langer_ball', 'Zweite Bälle attackieren'),
    ('schlechter_pass', 'Auf Fehler pressen'),
    ('torwart_druck', 'Torwart anlaufen'),
]

PRESSING_TRIGGER_COSTS = {
    'ballverlust': 2,
    'langer_ball': 1,
    'schlechter_pass': 1,
    'torwart_druck': 1,
}
PRESSING_TRIGGER_BUDGET = 3

PRESSING_TRIGGER_TOOLTIPS = {
    'ballverlust': 'Die Mannschaft versucht nach eigenem Ballverlust sofort den Ball zurückzuerobern. Kostet zusätzliche Frische.',
    'langer_ball': 'Die Mannschaft rückt bei gegnerischen langen Bällen aggressiv auf zweite Bälle nach.',
    'schlechter_pass': 'Die Mannschaft nutzt unsaubere Pässe des Gegners für sofortigen Druck.',
    'torwart_druck': 'Stürmer setzen Torwart und Innenverteidiger im Spielaufbau stärker unter Druck.',
}

ATTACK_FOCUS_OPTIONS = [
    ('ausgewogen', 'Ausgewogen'),
    ('fluegelspiel', 'Flügelspiel'),
    ('ueber_halbraeume', 'Über Halbräume'),
    ('durch_mitte', 'Durch die Mitte'),
    ('ueber_rechts', 'Über rechts'),
    ('ueber_links', 'Über links'),
    ('flanke_kopfball', 'Flanke & Kopfball'),
]

# Attack focus -> mini-pitch zone intensities (0-100) for left / center / right.
ATTACK_FOCUS_ZONES = {
    'ausgewogen': {'left': 33, 'center': 34, 'right': 33},
    'fluegelspiel': {'left': 42, 'center': 16, 'right': 42},
    'ueber_halbraeume': {'left': 34, 'center': 32, 'right': 34},
    'durch_mitte': {'left': 22, 'center': 56, 'right': 22},
    'ueber_rechts': {'left': 18, 'center': 34, 'right': 48},
    'ueber_links': {'left': 48, 'center': 34, 'right': 18},
    'flanke_kopfball': {'left': 40, 'center': 20, 'right': 40},
}

ATTACK_FOCUS_TOOLTIPS = {
    'ausgewogen': 'Ausgeglichener Angriffsstil – keine bevorzugte Seite, flexible Spielgestaltung.',
    'fluegelspiel': 'Angriffe laufen bevorzugt über beide Außenbahnen.',
    'ueber_halbraeume': 'Läufe und Pässe in die halblinke und halbrechte Zone zwischen Abwehr und Flügel.',
    'durch_mitte': 'Angriffe durch das Zentrum mit kurzen Kombinationen.',
    'ueber_rechts': 'Konzentration der Angriffe auf die rechte Außenbahn.',
    'ueber_links': 'Konzentration der Angriffe auf die linke Außenbahn.',
    'flanke_kopfball': 'Viele Flanken von außen – Kopfballstärke der Stürmer ist entscheidend.',
}

BUILDUP_DEFENSE_OPTIONS = [
    ('standard', 'Standard'),
    ('aus_abwehr', 'Aus der Abwehr spielen'),
    ('direkt_vorne', 'Direkt nach vorne'),
    ('lange_baelle', 'Lange Bälle'),
]

BUILDUP_DEFENSE_HEIGHT = [
    ('tief', 'Tief'),
    ('standard', 'Standard'),
    ('hoeher', 'Höher stehen'),
]

BUILDUP_DEFENSE_HEIGHT_TOOLTIPS = {
    'tief': 'Abwehrlinie steht tief – schützt gegen Steilpässe, gibt Raum davor.',
    'standard': 'Ausgeglichene Linienhöhe.',
    'hoeher': 'Abwehrlinie steht höher – erhöht Druck, ermöglicht Abseitsfallen.',
}

BUILDUP_MIDFIELD_OPTIONS = [
    ('standard', 'Standard'),
    ('geduldig', 'Geduldig aufbauen'),
    ('vertikal', 'Vertikal spielen'),
    ('seiten_verlagern', 'Seiten verlagern'),
]

BUILDUP_ATTACK_OPTIONS = [
    ('standard', 'Standard'),
    ('kombinieren', 'Kombinieren'),
    ('tiefenlaeufe', 'Tiefenläufe suchen'),
    ('flanken_suchen', 'Flanken suchen'),
    ('zielspieler_suchen', 'Zielspieler suchen'),
    ('frueher_abschluss', 'Früher Abschluss'),
]

DEFENDING_DECKUNG = [
    ('raum', 'Raumdeckung'),
    ('mann', 'Manndeckung'),
    ('hybrid', 'Hybrid'),
]

DEFENDING_ZWEIKAMPF = [
    ('vorsichtig', 'Vorsichtig'),
    ('normal', 'Normal'),
    ('hart', 'Hart'),
]

DEFENDING_BREITE = [
    ('eng', 'Eng'),
    ('standard', 'Standard'),
    ('breit', 'Breit'),
]

DEFENDING_UMSCHALTEN = [
    ('konter', 'Konter'),
    ('ausgewogen', 'Ausgewogen'),
    ('ballbesitz', 'Ballbesitzsicherung'),
]

CONDITION_OPTIONS = [
    ('rueckstand', 'Bei Rückstand'),
    ('rueckstand_2', 'Bei Rückstand 2+'),
    ('unentschieden', 'Bei Unentschieden'),
    ('fuehrung', 'Bei Führung'),
    ('knappe_fuehrung', 'Bei knapper Führung (1 Tor)'),
    ('eigene_rot', 'Eigene rote Karte'),
    ('gegner_rot', 'Gegner rote Karte'),
]

CONDITION_PLANS = [
    ('ausgewogen', 'Ausgewogen'),
    ('aggressiv_risiko', 'Aggressiv & Risiko'),
    ('schlussangriff', 'Schlussangriff'),
    ('kontrolle_ballbesitz', 'Kontrolle & Ballbesitz'),
    ('kompakt_sichern', 'Kompakt sichern'),
    ('zeitspiel', 'Zeitspiel'),
    ('unterzahl_kompakt', 'Unterzahl kompakt'),
]

MAX_CONDITIONS = 8

DEFAULT_INSTRUCTIONS = {
    'pressing': {'defense': 'normal', 'midfield': 'normal', 'attack': 'normal'},
    'pressing_triggers': {
        'ballverlust': False,
        'langer_ball': False,
        'schlechter_pass': False,
        'torwart_druck': False,
    },
    'attack_focus': 'ausgewogen',
    'buildup': {
        'defense': 'standard',
        'defense_height': 'standard',
        'midfield': 'standard',
        'attack': 'standard',
        'tempo': 50,
    },
    'defending': {
        'deckung': 'hybrid',
        'zweikampf': 'normal',
        'breite': 'standard',
        'umschalten': 'ausgewogen',
    },
}

DEFAULT_CONDITIONS = [
    {'active': False, 'minute': '01', 'condition': 'rueckstand', 'plan': 'aggressiv_risiko'},
    {'active': False, 'minute': '60', 'condition': 'unentschieden', 'plan': 'ausgewogen'},
    {'active': False, 'minute': '80', 'condition': 'fuehrung', 'plan': 'zeitspiel'},
    {'active': False, 'minute': '90', 'condition': 'knappe_fuehrung', 'plan': 'zeitspiel'},
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


def default_instructions():
    return deepcopy(DEFAULT_INSTRUCTIONS)


def default_conditions():
    return deepcopy(DEFAULT_CONDITIONS)


def _choice(value, options, default):
    keys = {key for key, _label in options}
    return value if value in keys else default


def _options_list(options, selected, tooltips=None):
    td = tooltips or {}
    return [
        {'value': value, 'label': label, 'selected': value == selected, 'tooltip': td.get(value, '')}
        for value, label in options
    ]


def normalize_condition_minute(value):
    text = str(value or '').strip()
    match = re.search(r'\d+', text)
    if not match:
        return '01'
    minute = max(1, min(120, int(match.group())))
    return f'{minute:02d}'


def normalize_instructions(raw):
    raw = raw or {}
    defaults = default_instructions()

    pressing = {}
    raw_pressing = raw.get('pressing') or {}
    for line, _label in PRESSING_LINES:
        pressing[line] = _choice(
            raw_pressing.get(line), PRESSING_LEVELS, defaults['pressing'][line]
        )

    triggers = {}
    raw_triggers = raw.get('pressing_triggers') or {}
    for key, _label in PRESSING_TRIGGERS:
        triggers[key] = bool(raw_triggers.get(key, defaults['pressing_triggers'][key]))

    used_budget = 0
    for key, _label in PRESSING_TRIGGERS:
        if triggers[key]:
            cost = PRESSING_TRIGGER_COSTS[key]
            if used_budget + cost > PRESSING_TRIGGER_BUDGET:
                triggers[key] = False
            else:
                used_budget += cost

    attack_focus = _choice(
        raw.get('attack_focus'), ATTACK_FOCUS_OPTIONS, defaults['attack_focus']
    )

    raw_buildup = raw.get('buildup') or {}
    db = defaults['buildup']
    try:
        tempo = int(raw_buildup.get('tempo', db['tempo']))
    except (TypeError, ValueError):
        tempo = db['tempo']
    buildup = {
        'defense': _choice(raw_buildup.get('defense'), BUILDUP_DEFENSE_OPTIONS, db['defense']),
        'defense_height': _choice(
            raw_buildup.get('defense_height'), BUILDUP_DEFENSE_HEIGHT, db['defense_height']
        ),
        'midfield': _choice(raw_buildup.get('midfield'), BUILDUP_MIDFIELD_OPTIONS, db['midfield']),
        'attack': _choice(raw_buildup.get('attack'), BUILDUP_ATTACK_OPTIONS, db['attack']),
        'tempo': max(0, min(100, tempo)),
    }

    raw_def = raw.get('defending') or {}
    dd = defaults['defending']
    defending = {
        'deckung': _choice(raw_def.get('deckung'), DEFENDING_DECKUNG, dd['deckung']),
        'zweikampf': _choice(raw_def.get('zweikampf'), DEFENDING_ZWEIKAMPF, dd['zweikampf']),
        'breite': _choice(raw_def.get('breite'), DEFENDING_BREITE, dd['breite']),
        'umschalten': _choice(raw_def.get('umschalten'), DEFENDING_UMSCHALTEN, dd['umschalten']),
    }

    return {
        'pressing': pressing,
        'pressing_triggers': triggers,
        'attack_focus': attack_focus,
        'buildup': buildup,
        'defending': defending,
    }


def normalize_conditions(raw):
    raw = raw or []
    condition_keys = {key for key, _label in CONDITION_OPTIONS}
    plan_keys = {key for key, _label in CONDITION_PLANS}
    result = []
    for item in raw[:MAX_CONDITIONS]:
        if not isinstance(item, dict):
            continue
        condition = item.get('condition')
        plan = item.get('plan')
        if condition not in condition_keys or plan not in plan_keys:
            continue
        result.append({
            'active': bool(item.get('active', True)),
            'minute': normalize_condition_minute(item.get('minute')),
            'condition': condition,
            'plan': plan,
        })
    return result


def tempo_label(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 50
    if value <= 25:
        return 'Ruhig'
    if value <= 49:
        return 'Kontrolliert'
    if value == 50:
        return 'Normal'
    if value <= 75:
        return 'Zügig'
    return 'Sehr schnell'




def instructions_view(instructions):
    instr = normalize_instructions(instructions)
    pressing = [
        {
            'name': line,
            'label': label,
            'options': _options_list(PRESSING_LEVELS, instr['pressing'][line]),
        }
        for line, label in PRESSING_LINES
    ]
    triggers = [
        {
            'name': key,
            'label': label,
            'active': instr['pressing_triggers'][key],
            'cost': PRESSING_TRIGGER_COSTS[key],
            'tooltip': PRESSING_TRIGGER_TOOLTIPS.get(key, ''),
        }
        for key, label in PRESSING_TRIGGERS
    ]
    trigger_budget_used = sum(
        PRESSING_TRIGGER_COSTS[key]
        for key, _ in PRESSING_TRIGGERS
        if instr['pressing_triggers'][key]
    )
    attack_focus = {
        'selected': instr['attack_focus'],
        'options': _options_list(ATTACK_FOCUS_OPTIONS, instr['attack_focus'], ATTACK_FOCUS_TOOLTIPS),
        'zones': ATTACK_FOCUS_ZONES.get(
            instr['attack_focus'], ATTACK_FOCUS_ZONES['fluegelspiel']
        ),
    }
    buildup = {
        'defense': _options_list(BUILDUP_DEFENSE_OPTIONS, instr['buildup']['defense']),
        'defense_height': _options_list(
            BUILDUP_DEFENSE_HEIGHT, instr['buildup']['defense_height'], BUILDUP_DEFENSE_HEIGHT_TOOLTIPS
        ),
        'midfield': _options_list(BUILDUP_MIDFIELD_OPTIONS, instr['buildup']['midfield']),
        'attack': _options_list(BUILDUP_ATTACK_OPTIONS, instr['buildup']['attack']),
        'tempo': instr['buildup']['tempo'],
        'tempo_label': tempo_label(instr['buildup']['tempo']),
        'selected': instr['buildup'],
    }
    defending = {
        'deckung': _options_list(DEFENDING_DECKUNG, instr['defending']['deckung']),
        'zweikampf': _options_list(DEFENDING_ZWEIKAMPF, instr['defending']['zweikampf']),
        'breite': _options_list(DEFENDING_BREITE, instr['defending']['breite']),
        'umschalten': _options_list(DEFENDING_UMSCHALTEN, instr['defending']['umschalten']),
    }
    return {
        'pressing': pressing,
        'triggers': triggers,
        'trigger_budget': PRESSING_TRIGGER_BUDGET,
        'trigger_budget_used': trigger_budget_used,
        'attack_focus': attack_focus,
        'buildup': buildup,
        'defending': defending,
    }


def conditions_view(conditions):
    conds = normalize_conditions(conditions)
    return [
        {
            'index': index,
            'active': cond['active'],
            'minute': cond['minute'],
            'condition_options': _options_list(CONDITION_OPTIONS, cond['condition']),
            'plan_options': _options_list(CONDITION_PLANS, cond['plan']),
        }
        for index, cond in enumerate(conds)
    ]


def blank_condition_view():
    return {
        'condition_options': _options_list(CONDITION_OPTIONS, CONDITION_OPTIONS[0][0]),
        'plan_options': _options_list(CONDITION_PLANS, CONDITION_PLANS[0][0]),
    }


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
            'is_suspended': player.is_ws_suspended,
            'is_injured': player.is_ws_injured,
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
                'reason': player.ws_injury_type or 'Verletzt',
                'tone': 'injury',
                'portrait': player.portrait_static_path,
            })
        if player.is_ws_suspended:
            rows.append({
                'name': player.full_name,
                'reason': player.ws_suspension_reason or 'Gesperrt',
                'tone': 'suspension',
                'portrait': player.portrait_static_path,
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
        'instructions': normalize_instructions(payload.get('instructions')),
        'conditions': normalize_conditions(payload.get('conditions')),
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
        'instructions': normalize_instructions(getattr(setup, 'instructions', None)),
        'conditions': normalize_conditions(getattr(setup, 'conditions', None)),
    }


def copy_payload_to_setup(setup, payload, confirmed=False, confirmed_at=None):
    setup.formation = normalize_formation(payload.get('formation'))
    setup.lineup = payload.get('lineup') or {}
    setup.bench = payload.get('bench') or []
    setup.standards = {**default_standards(), **(payload.get('standards') or {})}
    setup.substitutions = payload.get('substitutions') or []
    setup.first_half = {**default_half_tactic(), **(payload.get('first_half') or {})}
    setup.second_half = {**default_half_tactic(), **(payload.get('second_half') or {})}
    setup.instructions = normalize_instructions(payload.get('instructions'))
    setup.conditions = normalize_conditions(payload.get('conditions'))
    setup.is_confirmed = confirmed
    setup.confirmed_at = confirmed_at if confirmed else None
    return setup
