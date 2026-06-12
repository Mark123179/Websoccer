"""
Match Engine V2 — Websoccer Spiel-Simulation.

Integriert die akzeptierte Standalone-Simulation (exp 1.25 + Taktik-Compiler +
Minuten-Logik) in die Django-Produktionsumgebung.

Öffentliche API:
    simulate_match(home_club, away_club) → dict

Die zurückgegebene dict-Struktur ist rückwärtskompatibel mit der alten Engine
(gleiche Schlüssel, neue Felder hinzugefügt).
"""
from __future__ import annotations

import math
import random
from copy import deepcopy
from typing import Optional

from .match_readiness import ensure_default_tactic
from .tactics import default_formation, formation_slots, formation_code
from .tactic_compiler import (
    calculate_zone_strengths,
    compile_tactic,
    select_active_condition_plan,
)

# ── Konstanten ────────────────────────────────────────────────────────────────

# Home Advantage V1 — minimaler struktureller Heimvorteil
# Nur xG, Ballbesitz und Pressing-Kontext; keine direkten Karten/Fouls.
HOME_XG_MULTIPLIER      = 1.030   # Heimteam: +3 % xG
AWAY_XG_MULTIPLIER      = 0.985   # Auswärtsteam: -1.5 % xG
HOME_POSSESSION_BONUS   = 0.5     # Prozentpunkte extra Ballbesitz Heim
HOME_PRESSING_BONUS     = 0.01    # additiver Bonus auf pressing_index Heim

_GROUP_KEY: dict[str, str] = {
    'goalkeeper':         'goalkeeper',
    'defense':            'defense',
    'defensive_midfield': 'midfield',
    'midfield':           'midfield',
    'offensive_midfield': 'midfield',
    'attack':             'attack',
}

_GOAL_WEIGHTS: dict[str, float] = {
    'goalkeeper':         0.01,
    'defense':            0.04,
    'defensive_midfield': 0.07,
    'midfield':           0.13,
    'offensive_midfield': 0.22,
    'attack':             0.53,
}


# ── Statistik-Helpers ─────────────────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _poisson(lam: float) -> int:
    """Poisson-Zufallsvariable (Knuth-Algorithmus)."""
    L = math.exp(-max(lam, 0.0))
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


# ── Spieler-Helpers (ORM-seitig) ──────────────────────────────────────────────

def _teamwork(player) -> int:
    """FMI Teamwork-Attribut, Fallback 50."""
    try:
        fm = player.source_ratings.filter(source='FM').first()
        if fm and fm.teamwork is not None:
            return int(fm.teamwork)
    except Exception:
        pass
    return 50


def _potential(player) -> float:
    """Potenzialstärke auf 200er-Skala."""
    try:
        pot = player.calculated_potential_strength
        if pot is not None:
            return float(pot)
    except Exception:
        pass
    return float(getattr(player, 'potential', 50) or 50)


def _draw_match_strength(player) -> float:
    """Zieht vor dem Spiel eine zufällige Matchstärke zwischen Basis und Potential.

    Formel: random.uniform(base, potential) + form_modifier, geclamped auf [0, 200].
    Ein Talent mit hohem Potential kann sein Ceiling abrufen — aber nicht immer.
    """
    try:
        sp = player.strength_profile
        base = float(sp.base_strength or 50.0)
        form = float(sp.form_modifier or 0.0)
    except Exception:
        return 50.0

    pot = _potential(player)
    drawn = random.uniform(base, pot) if pot > base else base
    return round(max(0.0, min(200.0, drawn + form)), 2)


def _pos_factor(player, slot_code: str) -> tuple[float, str | None]:
    """Gibt (Multiplikator, Label) zurück basierend auf Spielerposition vs. Slot.

    HP  → (1.00, None)   — Hauptposition, kein Malus
    NP  → (0.90, 'NP')   — Nebenposition, -10 %
    FP  → (0.80, 'FP')   — Fremdposition, -20 %
    """
    try:
        if slot_code in player.main_positions:
            return 1.0, None
        if slot_code in player.secondary_positions:
            return 0.90, 'NP'
    except Exception:
        pass
    return 0.80, 'FP'


def _player_row(item: dict, goals: int = 0, assists: int = 0, match_strength: float | None = None) -> dict:
    """Lineup-Item {'slot': …, 'player': ORM-Player} → Report-Spielerzeile."""
    p = item['player']
    slot = item['slot']
    try:
        sp = p.strength_profile
        base = float(sp.base_strength)
        freshness = float(sp.freshness)
    except Exception:
        base = 50.0
        freshness = 100.0

    final = match_strength if match_strength is not None else base
    factor, pos_label = _pos_factor(p, slot['code'])
    effective = round(final * factor, 1)

    return {
        'id': p.pk,
        'name': f"{p.first_name} {p.last_name}".strip() or str(p),
        'position': slot['code'],
        'group': slot['group'],
        'base_strength': round(base, 1),
        'potential': round(_potential(p), 1),
        'final_strength': effective,
        'final_strength_raw': round(final, 1),
        'pos_label': pos_label,
        'freshness': int(round(freshness)),
        'teamwork': _teamwork(p),
        'goals': goals,
        'assists': assists,
    }


def _lineup_players_orm(tactic) -> list[dict]:
    """TacticSetup → Liste von {'slot': slot_dict, 'player': Player-ORM}."""
    from .models import Player

    lineup = tactic.lineup or {}
    formation = tactic.formation or default_formation()
    slots = formation_slots(formation)

    player_ids = [lineup.get(s['key']) for s in slots if lineup.get(s['key'])]
    players_by_id = {
        p.pk: p
        for p in Player.objects.filter(pk__in=player_ids)
        .select_related('strength_profile')
        .prefetch_related('source_ratings')
    }

    result = []
    for slot in slots:
        pid = lineup.get(slot['key'])
        if pid and pid in players_by_id:
            result.append({'slot': slot, 'player': players_by_id[pid]})
    return result


# ── ORM → Team-Dict Bridge ────────────────────────────────────────────────────

def _build_team_dict(club, tactic_setup, match_strengths: dict | None = None) -> dict:
    """Konvertiert Django ORM-Objekte in das Team-Dict-Format des Taktik-Compilers.

    Rückgabe-Format entspricht dem Standalone-Format (bayern_fixture.json).
    match_strengths: vorberechnete {player_id → float} Matchstärken (random(basis, pot) + form).
    """
    from .models import Player

    lineup_map = tactic_setup.lineup or {}
    formation = tactic_setup.formation or default_formation()
    slots = formation_slots(formation)

    player_ids = [lineup_map.get(s['key']) for s in slots if lineup_map.get(s['key'])]
    players_qs = (
        Player.objects
        .filter(pk__in=player_ids)
        .select_related('strength_profile')
        .prefetch_related('source_ratings')
    )
    players_by_id = {p.pk: p for p in players_qs}

    players_list: list[dict] = []
    seen_pids: set[int] = set()
    for pid in player_ids:
        if pid in seen_pids:
            continue
        seen_pids.add(pid)
        p = players_by_id.get(pid)
        if not p:
            continue
        if match_strengths and pid in match_strengths:
            final_strength = match_strengths[pid]
        else:
            try:
                sp = p.strength_profile
                final_strength = float(sp.final_strength or 50.0)
            except Exception:
                final_strength = 50.0
        players_list.append({
            'id': p.pk,
            'name': f'{p.first_name} {p.last_name}'.strip() or str(p),
            'final_strength': final_strength,
            'main_positions': list(p.main_positions),
            'secondary_positions': list(p.secondary_positions),
            'teamwork': _teamwork(p),
        })

    lineup_list: list[dict] = []
    for slot in slots:
        pid = lineup_map.get(slot['key'])
        if pid and pid in players_by_id:
            lineup_list.append({
                'player_id': pid,
                'position': slot['code'],
                'group': slot['group'],
            })

    instructions = tactic_setup.instructions or {}
    conditions = tactic_setup.conditions or []
    first_half = tactic_setup.first_half or {}
    second_half = tactic_setup.second_half or {}

    tactic_dict: dict = {
        'attack_focus': instructions.get('attack_focus', 'ausgewogen'),
        'pressing': instructions.get('pressing', {}),
        'pressing_triggers': instructions.get('pressing_triggers', {}),
        'buildup': instructions.get('buildup', {}),
        'defending': instructions.get('defending', {}),
        'conditions': conditions,
        'first_half': first_half,
        'second_half': second_half,
    }

    return {
        'team': {'name': club.name, 'id': club.pk},
        'players': players_list,
        'lineup': lineup_list,
        'tactic': tactic_dict,
    }


# ── Lineup-Stärke (Compiler-basiert) ─────────────────────────────────────────

def _pos_factor_dict(player_dict: dict, position_code: str) -> tuple[float, str]:
    if position_code in player_dict.get('main_positions', []):
        return 1.0, 'HP'
    if position_code in player_dict.get('secondary_positions', []):
        return 0.90, 'NP'
    return 0.80, 'FP'


def _calculate_lineup_strength(
    team: dict,
    tactic_override: Optional[dict] = None,
    compiled_tactic: Optional[dict] = None,
) -> dict:
    """Linienstärken inkl. Taktik-Multiplikatoren (Port aus Standalone)."""
    players_by_id = {p['id']: p for p in team.get('players', [])}
    if compiled_tactic is None:
        compiled_tactic = compile_tactic(
            team,
            tactic_override or team.get('tactic', {}),
            half='full',
        )

    multipliers = compiled_tactic.get('line_multipliers', {})
    lines: dict[str, list[float]] = {
        'goalkeeper': [], 'defense': [], 'midfield': [], 'attack': []
    }

    for slot in team.get('lineup', []):
        pid = slot.get('player_id')
        if not pid:
            continue
        player = players_by_id.get(pid)
        if not player:
            continue
        group = slot.get('group', 'attack')
        line = _GROUP_KEY.get(group, 'attack')
        factor, _ = _pos_factor_dict(player, slot['position'])
        strength = player.get('final_strength', 50.0) * factor
        strength *= multipliers.get(line, 1.0)
        lines[line].append(strength)

    def avg(lst: list[float]) -> float:
        return sum(lst) / len(lst) if lst else 50.0

    gk = avg(lines['goalkeeper'])
    de = avg(lines['defense'])
    mi = avg(lines['midfield'])
    at = avg(lines['attack'])
    all_vals = lines['goalkeeper'] + lines['defense'] + lines['midfield'] + lines['attack']
    overall = avg(all_vals) * multipliers.get('overall', 1.0)

    return {
        'goalkeeper': round(gk, 2),
        'defense':    round(de, 2),
        'midfield':   round(mi, 2),
        'attack':     round(at, 2),
        'overall':    round(overall, 2),
    }


# ── Expected Goals (neue Formel: ratio ** 1.25 + Taktik-Modifikatoren) ────────

def _zone_factor(own_compiled: dict, own_zone: dict, opp_zone: dict) -> float:
    weights = own_compiled.get('zone_weights', {'left': 0.33, 'center': 0.34, 'right': 0.33})
    own_atk = own_zone.get('attack', {})
    opp_def = opp_zone.get('defense', {})
    pairs = [('left', 'right'), ('center', 'center'), ('right', 'left')]

    def _ratio(w):
        val = 0.0
        for oz, dz in pairs:
            val += w.get(oz, 0.0) * (own_atk.get(oz, 1.0) / max(opp_def.get(dz, 1.0), 1.0))
        return val

    balanced = {'left': 0.33, 'center': 0.34, 'right': 0.33}
    raw = _ratio(weights)
    base = _ratio(balanced)
    if base <= 0:
        return 1.0
    return _clamp(raw / base, 0.93, 1.07)


def _expected_goals(
    own_strength: dict,
    opp_strength: dict,
    own_compiled: Optional[dict] = None,
    opp_compiled: Optional[dict] = None,
    own_zone: Optional[dict] = None,
    opp_zone: Optional[dict] = None,
) -> float:
    """Expected Goals aus Linienstärken + Taktik-Modifikatoren (exp 1.25)."""
    own_off = (
        own_strength['overall'] * 0.45
        + own_strength['attack']   * 0.32
        + own_strength['midfield'] * 0.23
    )
    opp_def = (
        opp_strength['overall']    * 0.35
        + opp_strength['defense']  * 0.42
        + opp_strength['goalkeeper'] * 0.23
    )
    ratio = own_off / max(opp_def, 1.0)
    base_xg = 1.36 * (ratio ** 1.25)

    if own_compiled:
        base_xg *= own_compiled.get('xg_for', 1.0)
        base_xg *= own_compiled.get('shot_quality', 1.0)
        base_xg *= 0.85 + 0.15 * own_compiled.get('shot_volume', 1.0)
    if opp_compiled:
        base_xg *= opp_compiled.get('xg_against', 1.0)
    if own_compiled and own_zone and opp_zone:
        base_xg *= _zone_factor(own_compiled, own_zone, opp_zone)

    return _clamp(base_xg, 0.2, 4.5)


# ── Tor-Events ────────────────────────────────────────────────────────────────

def _lineup_players_dict(team: dict) -> list[dict]:
    """Team-Dict → flache Spielerliste mit position/group."""
    pid_map = {p['id']: p for p in team.get('players', [])}
    result = []
    for slot in team.get('lineup', []):
        p = pid_map.get(slot.get('player_id'))
        if p:
            result.append({**p, 'position': slot['position'], 'group': slot.get('group', 'attack')})
    return result


def _goal_events(
    n: int,
    team_key: str,
    lineup_players: list[dict],
    minute_pool: list[int],
) -> list[dict]:
    """n Tor-Events mit Schütze + optionaler Vorlage erzeugen (dict-basiert)."""
    if not lineup_players:
        return []
    weights = [_GOAL_WEIGHTS.get(p.get('group', 'attack'), 0.05) for p in lineup_players]
    w_sum = sum(weights) or 1.0
    weights = [w / w_sum for w in weights]
    events = []
    for _ in range(n):
        minute = (
            minute_pool.pop(random.randint(0, len(minute_pool) - 1))
            if minute_pool
            else random.randint(1, 90)
        )
        scorer = random.choices(lineup_players, weights=weights, k=1)[0]
        assister = None
        if random.random() < 0.72:
            cands = [p for p in lineup_players if p['id'] != scorer['id']]
            if cands:
                assister = random.choice(cands)
        events.append({
            'minute': minute,
            'team': team_key,
            'scorer_id': scorer['id'],
            'scorer_name': scorer['name'],
            'scorer_pos': scorer.get('position', '?'),
            'assister_id': assister['id'] if assister else None,
            'assister_name': assister['name'] if assister else None,
        })
    return events


# ── Segment-Statistiken (Minuten-Simulation) ──────────────────────────────────

def _distribute_attacks(total: int, weights: dict) -> dict[str, int]:
    zones = ['left', 'center', 'right']
    counts = {z: 0 for z in zones}
    w = [weights.get(z, 0.0) for z in zones]
    if sum(w) <= 0:
        w = [0.33, 0.34, 0.33]
    for z in random.choices(zones, weights=w, k=max(0, int(total))):
        counts[z] += 1
    return counts


def _segment_team_stats(goals: int, comp: dict, seg_len: int) -> dict:
    """Leichtgewichtige Segment-Statistiken für die Minuten-Simulation."""
    scale = seg_len / 90.0
    shot_volume  = comp.get('shot_volume', 1.0)
    shot_quality = comp.get('shot_quality', 1.0)
    width        = comp.get('width', 0.0)
    pressing_idx = comp.get('pressing_index', 0.35)

    shots_lam = max(0.05, (9.6 * shot_volume + goals * 1.8) * scale)
    shots = max(goals, _poisson(shots_lam))
    on_lam = max(0.03, shots * _clamp(0.36 * shot_quality, 0.22, 0.55))
    shots_on = max(goals, min(shots, _poisson(on_lam) + goals))

    corner_mult = 1.0 + max(0.0, width) * 0.30 + max(0.0, shot_volume - 1.0) * 0.25
    corners = _poisson(max(0.02, 5.2 * corner_mult * scale))

    fouls  = _poisson(max(0.05, 14.0 * comp.get('foul_multiplier', 1.0) * scale))
    yellow = _poisson(max(0.01, (1.35 * comp.get('card_multiplier', 1.0) + max(0, fouls - 2) * 0.05) * scale))

    pw_lam = (1.5 + pressing_idx * 4.2 + comp.get('pressing_ball_win_bonus', 0.0) * 18) * scale
    pb_lam = max(0.02, (comp.get('pressing_bypassed_risk', 0.0) * 9 + max(0, comp.get('risk', 0.0)) * 3) * scale)

    attack_total = shots + corners + _poisson(max(0.05, 12.0 * scale))
    zones = _distribute_attacks(attack_total, comp.get('zone_weights', {}))

    return {
        'shots':           shots,
        'shots_on_target': shots_on,
        'corners':         corners,
        'fouls':           fouls,
        'yellow':          yellow,
        'pressing_ball_wins': _poisson(max(0.01, pw_lam)),
        'pressing_bypassed':  _poisson(max(0.01, pb_lam)),
        'attacks_left':    zones['left'],
        'attacks_center':  zones['center'],
        'attacks_right':   zones['right'],
    }


def _empty_minute_stats() -> dict:
    return {
        'possession_weighted':  0.0,
        'minutes_weighted':     0,
        'shots':                0,
        'shots_on_target':      0,
        'corners':              0,
        'fouls':                0,
        'yellow':               0,
        'red':                  0,
        'attacks_left':         0,
        'attacks_center':       0,
        'attacks_right':        0,
        'pressing_ball_wins':   0,
        'pressing_bypassed':    0,
        'fatigue_cost_weighted':  0.0,
        'coherence_weighted':     0.0,
        'complexity_weighted':    0.0,
    }


def _add_segment_stats(
    total: dict, seg: dict, comp: dict,
    possession: int, seg_len: int, red: int,
) -> None:
    total['possession_weighted'] += possession * seg_len
    total['minutes_weighted']    += seg_len
    total['shots']               += seg['shots']
    total['shots_on_target']     += seg['shots_on_target']
    total['corners']             += seg['corners']
    total['fouls']               += seg['fouls']
    total['yellow']              += seg['yellow']
    total['red']                 += red
    total['attacks_left']        += seg['attacks_left']
    total['attacks_center']      += seg['attacks_center']
    total['attacks_right']       += seg['attacks_right']
    total['pressing_ball_wins']  += seg['pressing_ball_wins']
    total['pressing_bypassed']   += seg['pressing_bypassed']
    total['fatigue_cost_weighted']  += comp.get('fatigue_cost', 1.0) * seg_len
    total['coherence_weighted']     += comp.get('coherence', 1.0) * seg_len
    total['complexity_weighted']    += comp.get('complexity', 0.0) * seg_len


def _red_card_this_segment(compiled: dict, seg_len: int) -> int:
    match_prob = 0.025 * compiled.get('card_multiplier', 1.0)
    return 1 if random.random() < min(0.08, match_prob * seg_len / 90.0) else 0


def _final_stats(home_total: dict, away_total: dict) -> dict:
    hm = max(1, home_total['minutes_weighted'])
    am = max(1, away_total['minutes_weighted'])
    return {
        'home_possession':       int(round(home_total['possession_weighted'] / hm)),
        'away_possession':       int(round(away_total['possession_weighted'] / am)),
        'home_shots':            home_total['shots'],
        'away_shots':            away_total['shots'],
        'home_shots_on_target':  home_total['shots_on_target'],
        'away_shots_on_target':  away_total['shots_on_target'],
        'home_corners':          home_total['corners'],
        'away_corners':          away_total['corners'],
        'home_fouls':            home_total['fouls'],
        'away_fouls':            away_total['fouls'],
        'home_yellow':           home_total['yellow'],
        'away_yellow':           away_total['yellow'],
        'home_red':              home_total['red'],
        'away_red':              away_total['red'],
        'home_attacks_left':     home_total['attacks_left'],
        'home_attacks_center':   home_total['attacks_center'],
        'home_attacks_right':    home_total['attacks_right'],
        'away_attacks_left':     away_total['attacks_left'],
        'away_attacks_center':   away_total['attacks_center'],
        'away_attacks_right':    away_total['attacks_right'],
        'home_pressing_ball_wins': home_total['pressing_ball_wins'],
        'away_pressing_ball_wins': away_total['pressing_ball_wins'],
        'home_pressing_bypassed':  home_total['pressing_bypassed'],
        'away_pressing_bypassed':  away_total['pressing_bypassed'],
        'home_fatigue_cost':     round(home_total['fatigue_cost_weighted'] / hm, 4),
        'away_fatigue_cost':     round(away_total['fatigue_cost_weighted'] / am, 4),
        'home_tactic_coherence': round(home_total['coherence_weighted'] / hm, 4),
        'away_tactic_coherence': round(away_total['coherence_weighted'] / am, 4),
        'home_tactic_complexity':round(home_total['complexity_weighted'] / hm, 2),
        'away_tactic_complexity':round(away_total['complexity_weighted'] / am, 2),
    }


# ── Minuten-Simulation (Port aus Standalone) ──────────────────────────────────

def _with_active_plan(tactic: Optional[dict], plan: Optional[str]) -> dict:
    t = deepcopy(tactic or {})
    if plan:
        t['_active_plan'] = plan
    else:
        t.pop('_active_plan', None)
    return t


def _simulate_match_minutes(
    home_team: dict,
    away_team: dict,
    segment_minutes: int = 5,
) -> dict:
    """Simuliert ein Spiel in 5-Minuten-Segmenten mit Live-Bedingungsauswertung.

    Identische Logik wie die akzeptierte Standalone-Simulation (run_match.py).
    Eingangsformat: Team-Dicts (aus _build_team_dict).
    Ausgang: Rohes Simulations-Dict mit allen Statistiken + Ereignissen.
    """
    home_base_tactic = deepcopy(home_team.get('tactic', {}))
    away_base_tactic = deepcopy(away_team.get('tactic', {}))
    h_zone = calculate_zone_strengths(home_team)
    a_zone = calculate_zone_strengths(away_team)
    h_lineup = _lineup_players_dict(home_team)
    a_lineup = _lineup_players_dict(away_team)

    h_goals = 0
    a_goals = 0
    h_xg_total = 0.0
    a_xg_total = 0.0
    h_red = 0
    a_red = 0
    events: list[dict] = []
    plan_activations: list[dict] = []
    plan_active_segments: dict[str, dict] = {'home': {}, 'away': {}}
    plan_seg_stats: dict[str, dict] = {'home': {}, 'away': {}}
    last_plan: dict[str, Optional[str]] = {'home': None, 'away': None}
    goals_while_plan: dict = {
        'home_for': 0, 'home_against': 0,
        'away_for': 0, 'away_against': 0,
        'by_plan_home': {}, 'by_plan_away': {},
    }
    h_stats_total = _empty_minute_stats()
    a_stats_total = _empty_minute_stats()
    score_at_60: Optional[dict] = None
    score_at_80: Optional[dict] = None
    last_h_comp: Optional[dict] = None
    last_a_comp: Optional[dict] = None
    last_h_str:  Optional[dict] = None
    last_a_str:  Optional[dict] = None

    seg_min = max(1, int(segment_minutes or 5))
    for minute in range(1, 91, seg_min):
        seg_len = max(1, min(seg_min, 91 - minute))
        end_min = minute + seg_len - 1
        half = 'first' if minute <= 45 else 'second'

        h_plan = select_active_condition_plan(
            home_base_tactic, minute, h_goals, a_goals, True,  h_red, a_red)
        a_plan = select_active_condition_plan(
            away_base_tactic, minute, h_goals, a_goals, False, a_red, h_red)

        for side, plan in (('home', h_plan), ('away', a_plan)):
            if plan:
                plan_active_segments[side][plan] = plan_active_segments[side].get(plan, 0) + 1
            if plan != last_plan[side]:
                if plan:
                    plan_activations.append({
                        'minute': minute,
                        'side':   side,
                        'plan':   plan,
                        'score':  f'{h_goals}:{a_goals}',
                    })
                last_plan[side] = plan

        h_tactic_seg = _with_active_plan(home_base_tactic, h_plan)
        a_tactic_seg = _with_active_plan(away_base_tactic, a_plan)
        h_comp = compile_tactic(home_team, h_tactic_seg, half=half)
        h_comp['pressing_index'] = _clamp(
            h_comp.get('pressing_index', 0.35) + HOME_PRESSING_BONUS, 0.0, 1.0
        )
        a_comp = compile_tactic(away_team, a_tactic_seg, half=half)
        h_str  = _calculate_lineup_strength(home_team, h_tactic_seg, h_comp)
        a_str  = _calculate_lineup_strength(away_team, a_tactic_seg, a_comp)
        last_h_comp, last_a_comp = h_comp, a_comp
        last_h_str,  last_a_str  = h_str,  a_str

        h_xg_match = _expected_goals(h_str, a_str, h_comp, a_comp, h_zone, a_zone) * HOME_XG_MULTIPLIER
        a_xg_match = _expected_goals(a_str, h_str, a_comp, h_comp, a_zone, h_zone) * AWAY_XG_MULTIPLIER
        h_xg_seg   = h_xg_match * seg_len / 90.0
        a_xg_seg   = a_xg_match * seg_len / 90.0
        h_xg_total += h_xg_seg
        a_xg_total += a_xg_seg

        hg = _poisson(h_xg_seg)
        ag = _poisson(a_xg_seg)
        minute_pool = list(range(minute, min(90, end_min) + 1))
        events.extend(_goal_events(hg, 'home', h_lineup, minute_pool.copy()))
        events.extend(_goal_events(ag, 'away', a_lineup, minute_pool.copy()))

        if h_plan:
            goals_while_plan['home_for']  += hg
            goals_while_plan['home_against'] += ag
            goals_while_plan['by_plan_home'][h_plan] = goals_while_plan['by_plan_home'].get(h_plan, 0) + hg
        if a_plan:
            goals_while_plan['away_for']  += ag
            goals_while_plan['away_against'] += hg
            goals_while_plan['by_plan_away'][a_plan] = goals_while_plan['by_plan_away'].get(a_plan, 0) + ag

        h_goals += hg
        a_goals += ag

        h_red_seg = _red_card_this_segment(h_comp, seg_len)
        a_red_seg = _red_card_this_segment(a_comp, seg_len)
        h_red += h_red_seg
        a_red += a_red_seg

        total_strength = h_str['overall'] + a_str['overall'] or 1.0
        poss_delta = (h_comp.get('possession_bonus', 0.0) - a_comp.get('possession_bonus', 0.0)) * 35
        build_delta = (h_comp.get('build_control', 0.0) - a_comp.get('build_control', 0.0)) * 10
        home_poss = int(round(_clamp(
            50 + HOME_POSSESSION_BONUS
            + (h_str['overall'] - a_str['overall']) / total_strength * 22
            + poss_delta + build_delta,
            30, 70,
        )))

        h_seg_stats = _segment_team_stats(hg, h_comp, seg_len)
        a_seg_stats = _segment_team_stats(ag, a_comp, seg_len)
        _add_segment_stats(h_stats_total, h_seg_stats, h_comp, home_poss,       seg_len, h_red_seg)
        _add_segment_stats(a_stats_total, a_seg_stats, a_comp, 100 - home_poss, seg_len, a_red_seg)

        for _side, _plan, _my_seg, _opp_seg, _my_xg, _opp_xg, _my_goals, _opp_goals, _my_comp in [
            ('home', h_plan, h_seg_stats, a_seg_stats, h_xg_seg, a_xg_seg, hg, ag, h_comp),
            ('away', a_plan, a_seg_stats, h_seg_stats, a_xg_seg, h_xg_seg, ag, hg, a_comp),
        ]:
            if _plan:
                pss = plan_seg_stats[_side]
                if _plan not in pss:
                    pss[_plan] = {
                        'segments': 0, 'minutes': 0,
                        'goals_for': 0, 'goals_against': 0,
                        'xg_for': 0.0, 'xg_against': 0.0,
                        'shots_for': 0, 'shots_against': 0,
                        'fouls': 0, 'yellow': 0, 'fatigue_sum': 0.0,
                    }
                s = pss[_plan]
                s['segments']     += 1
                s['minutes']      += seg_len
                s['goals_for']    += _my_goals
                s['goals_against'] += _opp_goals
                s['xg_for']       += _my_xg
                s['xg_against']   += _opp_xg
                s['shots_for']    += _my_seg['shots']
                s['shots_against'] += _opp_seg['shots']
                s['fouls']        += _my_seg['fouls']
                s['yellow']       += _my_seg['yellow']
                s['fatigue_sum']  += _my_comp.get('fatigue_cost', 1.0) * seg_len

        if score_at_60 is None and minute <= 60 <= end_min:
            score_at_60 = {'home': h_goals, 'away': a_goals}
        if score_at_80 is None and minute <= 80 <= end_min:
            score_at_80 = {'home': h_goals, 'away': a_goals}

    events = sorted(events, key=lambda e: e['minute'])

    match_stats = _final_stats(h_stats_total, a_stats_total)

    score_at_60 = score_at_60 or {'home': h_goals, 'away': a_goals}
    score_at_80 = score_at_80 or {'home': h_goals, 'away': a_goals}
    lead_after_80         = score_at_80['home'] > score_at_80['away']
    lead_lost_after_80    = bool(lead_after_80 and h_goals <= a_goals)
    lead_protected_after_80 = bool(lead_after_80 and h_goals > a_goals)
    trailed_at_60         = score_at_60['home'] < score_at_60['away']
    comeback_win          = bool(trailed_at_60 and h_goals > a_goals)
    comeback_draw         = bool(trailed_at_60 and h_goals == a_goals)

    return {
        'home_goals':    h_goals,
        'away_goals':    a_goals,
        'home_xg':       round(h_xg_total, 4),
        'away_xg':       round(a_xg_total, 4),
        'goal_events':   events,
        'match_stats':   match_stats,
        'home_strength': last_h_str or {},
        'away_strength': last_a_str or {},
        'home_compiled_tactic': last_h_comp or {},
        'away_compiled_tactic': last_a_comp or {},
        'home_zone_strengths': h_zone,
        'away_zone_strengths': a_zone,
        'simulation_mode': 'minutes',
        'segment_minutes': seg_min,
        'plan_activations': plan_activations,
        'condition_debug': {
            'plan_activations': plan_activations,
            'plan_activation_counts': {
                'home': {p: sum(1 for e in plan_activations if e['side'] == 'home' and e['plan'] == p)
                         for p in sorted({e['plan'] for e in plan_activations if e['side'] == 'home'})},
                'away': {p: sum(1 for e in plan_activations if e['side'] == 'away' and e['plan'] == p)
                         for p in sorted({e['plan'] for e in plan_activations if e['side'] == 'away'})},
            },
            'plan_active_segments': plan_active_segments,
            'plan_seg_stats':       plan_seg_stats,
            'goals_after_plan_activation': goals_while_plan['home_for'],
            'conceded_after_plan_activation': goals_while_plan['home_against'],
            'goals_while_plan': goals_while_plan,
            'score_at_60':  score_at_60,
            'score_at_80':  score_at_80,
            'lead_after_80':          lead_after_80,
            'lead_protected_after_80': lead_protected_after_80,
            'lead_lost_after_80':      lead_lost_after_80,
            'trailed_at_60':  trailed_at_60,
            'comeback_win':   comeback_win,
            'comeback_draw':  comeback_draw,
        },
    }


# ── Spieler-Notensystem ───────────────────────────────────────────────────────

def _rating_pos_group(position: str, group: str) -> str:
    """Gibt die Notengruppe (GK/DEF/MID/FWD) zurück."""
    pos = (position or '').upper()
    grp = (group or '').lower()
    if pos == 'GK' or grp == 'goalkeeper':
        return 'GK'
    if grp == 'defense' or pos in ('CB', 'LB', 'RB', 'WB'):
        return 'DEF'
    if grp in ('midfield', 'defensive_midfield', 'offensive_midfield') or pos in ('CM', 'DM', 'AM', 'LM', 'RM'):
        return 'MID'
    return 'FWD'


def _assign_cards_to_players(players: list[dict], yellow_count: int, red_count: int) -> list[dict]:
    """Verteilt Team-Karten zufällig auf einzelne Spieler als 0/1-Flags (in-place Kopie).

    Jeder Spieler erhält maximal 1 Gelbe und 1 Rote Karte (sample without replacement).
    Karten-Anzahl wird auf Spieler-Pool-Größe geclampt.
    """
    players = [dict(p) for p in players]
    n = len(players)
    if not n:
        return players
    y = min(max(0, yellow_count), n)
    r = min(max(0, red_count), n)
    for i in random.sample(range(n), y):
        players[i]['yellow_cards'] = 1
    for i in random.sample(range(n), r):
        players[i]['red_cards'] = 1
    return players


def compute_player_ratings(result: dict) -> dict:
    """Berechnet positionsabhängige Spielernoten (1,0–6,0) aus einem Simulations-Dict.

    Rückgabe::
        {
            home_ratings: [{id, name, position, rating}, …],
            away_ratings: [{id, name, position, rating}, …],
            man_of_the_match: {id, name, club_id, club_name, club_crest, club_short, rating, position},
        }
    """
    h_goals = result.get('home_goals', 0) or 0
    a_goals = result.get('away_goals', 0) or 0
    h_xg    = float(result.get('home_xg') or 0)
    a_xg    = float(result.get('away_xg') or 0)
    ms      = result.get('match_stats', {}) or {}

    h_yellow = ms.get('home_yellow', 0) or 0
    a_yellow = ms.get('away_yellow', 0) or 0
    h_red    = ms.get('home_red', 0) or 0
    a_red    = ms.get('away_red', 0) or 0
    h_press_wins = ms.get('home_pressing_ball_wins', 0) or 0
    a_press_wins = ms.get('away_pressing_ball_wins', 0) or 0
    h_press_bp   = ms.get('home_pressing_bypassed', 0) or 0
    a_press_bp   = ms.get('away_pressing_bypassed', 0) or 0

    h_win = h_goals > a_goals
    a_win = a_goals > h_goals

    h_players_raw = result.get('home_players', []) or []
    a_players_raw = result.get('away_players', []) or []

    def _rate(p: dict, is_home: bool) -> float:
        rating = 3.5
        pg     = _rating_pos_group(p.get('position', ''), p.get('group', ''))
        goals   = p.get('goals', 0) or 0
        assists = p.get('assists', 0) or 0
        yellow  = p.get('yellow_cards', 0) or 0
        red     = p.get('red_cards', 0) or 0

        my_goals   = h_goals        if is_home else a_goals
        opp_goals  = a_goals        if is_home else h_goals
        my_xg      = h_xg           if is_home else a_xg
        opp_xg     = a_xg           if is_home else h_xg
        my_win     = h_win          if is_home else a_win
        opp_win    = a_win          if is_home else h_win
        my_pw      = h_press_wins   if is_home else a_press_wins
        opp_bp     = a_press_bp     if is_home else h_press_bp

        rating -= goals * 0.8
        rating -= assists * 0.4
        if my_win:
            rating -= 0.2
        elif opp_win:
            rating += 0.2
        rating += yellow * 0.3
        rating += red * 1.5

        if pg == 'GK':
            rating += opp_goals * 0.4
            if opp_goals == 0:
                rating -= 0.5
            if opp_xg >= 2.0 and opp_goals <= 1:
                rating -= 0.3
            if opp_xg <= 0.8 and opp_goals >= 2:
                rating += 0.5
        elif pg == 'DEF':
            rating += opp_goals * 0.2
            if opp_goals == 0:
                rating -= 0.3
            if opp_bp > 3:
                rating += 0.2
            if my_win:
                rating -= 0.1
        elif pg == 'MID':
            xg_diff = my_xg - opp_xg
            if xg_diff > 0.5:
                rating -= 0.2
            elif xg_diff < -0.5:
                rating += 0.2
            if my_pw > 3:
                rating -= 0.15
        elif pg == 'FWD':
            if goals == 0 and my_xg >= 1.5:
                rating += 0.3

        if pg in ('GK', 'DEF') and goals > 0:
            rating -= 0.3 * goals

        return round(_clamp(rating, 1.0, 6.0), 1)

    home_ratings = [
        {
            'id':       p.get('id'),
            'name':     p.get('name', ''),
            'position': p.get('position', ''),
            'rating':   _rate(p, True),
        }
        for p in h_players_raw
    ]
    away_ratings = [
        {
            'id':       p.get('id'),
            'name':     p.get('name', ''),
            'position': p.get('position', ''),
            'rating':   _rate(p, False),
        }
        for p in a_players_raw
    ]

    motm = None
    all_r = [(r, 'home') for r in home_ratings] + [(r, 'away') for r in away_ratings]
    if all_r:
        best, side = min(all_r, key=lambda x: x[0]['rating'])
        motm = {
            'id':         best['id'],
            'name':       best['name'],
            'position':   best['position'],
            'rating':     best['rating'],
            'club_id':    result.get('home_club_id')    if side == 'home' else result.get('away_club_id'),
            'club_name':  result.get('home_club_name')  if side == 'home' else result.get('away_club_name'),
            'club_crest': result.get('home_club_crest') if side == 'home' else result.get('away_club_crest'),
            'club_short': result.get('home_club_short') if side == 'home' else result.get('away_club_short'),
        }

    return {
        'home_ratings':      home_ratings,
        'away_ratings':      away_ratings,
        'man_of_the_match':  motm,
    }


# ── Öffentliche API ───────────────────────────────────────────────────────────

def simulate_match(home_club, away_club) -> dict:
    """
    Simuliert ein Spiel und gibt ein vollständiges Report-Dict zurück.

    Rückwärtskompatible Schlüssel (identisch zur alten Engine):
        home_club_id, home_club_name, home_club_short, home_club_crest
        away_club_id, away_club_name, away_club_short, away_club_crest
        home_goals, away_goals
        goal_events:   [{minute, team, scorer_id, scorer_name, scorer_pos, assister_id, assister_name}, …]
        match_stats:   {home/away_possession, shots, shots_on_target, corners, fouls, yellow, red, …}
        home_players:  [{id, name, position, group, base_strength, final_strength, teamwork, goals, assists}, …]
        away_players:  (gleiche Struktur)
        home_strength: {goalkeeper, defense, midfield, attack, overall}
        away_strength: (gleiche Struktur)
        home_teamwork: int
        away_teamwork: int
        home_formation, away_formation: str

    Neue Schlüssel (V2):
        home_xg, away_xg: float
        simulation_mode: 'minutes'
        plan_activations: [{minute, side, plan, score}, …]
        condition_debug:  dict
        home_compiled_tactic, away_compiled_tactic: dict
        home_zone_strengths, away_zone_strengths: dict
    """
    # 1. Aufstellungen sicherstellen
    home_tactic, _ = ensure_default_tactic(home_club)
    away_tactic, _ = ensure_default_tactic(away_club)

    # 2. Pre-compute Matchstärken: random(basis, potential) + form — einmal pro Spieler,
    #    konsistent für Simulation UND Spielbericht-Display.
    from .models import Player as _Player
    _all_pids = list({
        pid
        for tactic in (home_tactic, away_tactic)
        for pid in (tactic.lineup or {}).values()
        if pid
    })
    _players_qs = (
        _Player.objects
        .filter(pk__in=_all_pids)
        .select_related('strength_profile')
        .prefetch_related('source_ratings')
    )
    match_strengths: dict[int, float] = {
        p.pk: _draw_match_strength(p) for p in _players_qs
    }

    # 3. ORM → Team-Dicts (mit vorberechneten Matchstärken)
    home_team = _build_team_dict(home_club, home_tactic, match_strengths=match_strengths)
    away_team = _build_team_dict(away_club, away_tactic, match_strengths=match_strengths)

    # 4. Minuten-Simulation
    sim = _simulate_match_minutes(home_team, away_team)

    # 5. Tore/Vorlagen auf ORM-Spieler mappen
    h_goals_map: dict[int, dict] = {}
    a_goals_map: dict[int, dict] = {}
    for evt in sim['goal_events']:
        pmap = h_goals_map if evt['team'] == 'home' else a_goals_map
        sid = evt.get('scorer_id')
        aid = evt.get('assister_id')
        if sid:
            pmap.setdefault(sid, {'goals': 0, 'assists': 0})['goals'] += 1
        if aid:
            pmap.setdefault(aid, {'goals': 0, 'assists': 0})['assists'] += 1

    h_lineup_orm = _lineup_players_orm(home_tactic)
    a_lineup_orm = _lineup_players_orm(away_tactic)

    h_players = [
        _player_row(
            item,
            goals=h_goals_map.get(item['player'].pk, {}).get('goals', 0),
            assists=h_goals_map.get(item['player'].pk, {}).get('assists', 0),
            match_strength=match_strengths.get(item['player'].pk),
        )
        for item in h_lineup_orm
    ]
    a_players = [
        _player_row(
            item,
            goals=a_goals_map.get(item['player'].pk, {}).get('goals', 0),
            assists=a_goals_map.get(item['player'].pk, {}).get('assists', 0),
            match_strength=match_strengths.get(item['player'].pk),
        )
        for item in a_lineup_orm
    ]

    # 5. Formations-Label
    def _fmt(tactic) -> str:
        f = tactic.formation or {}
        try:
            return formation_code(f)
        except Exception:
            return '?'

    # 5b. Karten-Flags (0/1) in Spieler-Rows einbetten — persistent im Report
    ms_stats = sim.get('match_stats', {}) or {}
    h_players = _assign_cards_to_players(
        h_players,
        ms_stats.get('home_yellow', 0) or 0,
        ms_stats.get('home_red', 0) or 0,
    )
    a_players = _assign_cards_to_players(
        a_players,
        ms_stats.get('away_yellow', 0) or 0,
        ms_stats.get('away_red', 0) or 0,
    )

    h_teamwork = sum(p['teamwork'] for p in h_players)
    a_teamwork = sum(p['teamwork'] for p in a_players)

    result = {
        # ── Club-Meta ────────────────────────────────────────────────────────
        'home_club_id':    home_club.pk,
        'home_club_name':  home_club.name,
        'home_club_short': home_club.short_name or home_club.name[:4].upper(),
        'home_club_crest': getattr(home_club, 'crest_static_path', None),
        'away_club_id':    away_club.pk,
        'away_club_name':  away_club.name,
        'away_club_short': away_club.short_name or away_club.name[:4].upper(),
        'away_club_crest': getattr(away_club, 'crest_static_path', None),
        # ── Ergebnis ──────────────────────────────────────────────────────────
        'home_goals': sim['home_goals'],
        'away_goals': sim['away_goals'],
        # ── Ereignisse & Statistiken ──────────────────────────────────────────
        'goal_events':  sim['goal_events'],
        'match_stats':  sim['match_stats'],
        # ── Spieler-Rows (reich angereichert, ORM-Daten) ─────────────────────
        'home_players': h_players,
        'away_players': a_players,
        # ── Stärken & Teamwork ────────────────────────────────────────────────
        'home_strength':  sim['home_strength'],
        'away_strength':  sim['away_strength'],
        'home_teamwork':  h_teamwork,
        'away_teamwork':  a_teamwork,
        # ── Formationen ───────────────────────────────────────────────────────
        'home_formation': _fmt(home_tactic),
        'away_formation': _fmt(away_tactic),
        # ── Neue V2-Felder ────────────────────────────────────────────────────
        'home_xg': sim['home_xg'],
        'away_xg': sim['away_xg'],
        'simulation_mode': 'minutes',
        'plan_activations':      sim.get('plan_activations', []),
        'condition_debug':       sim.get('condition_debug', {}),
        'home_compiled_tactic':  sim.get('home_compiled_tactic', {}),
        'away_compiled_tactic':  sim.get('away_compiled_tactic', {}),
        'home_zone_strengths':   sim.get('home_zone_strengths', {}),
        'away_zone_strengths':   sim.get('away_zone_strengths', {}),
    }

    # 6. Spielernoten berechnen und in den Report einbetten
    ratings = compute_player_ratings(result)
    result['home_ratings']     = ratings['home_ratings']
    result['away_ratings']     = ratings['away_ratings']
    result['man_of_the_match'] = ratings['man_of_the_match']
    return result
