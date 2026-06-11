"""
Match Engine — Spiel-Simulation für Websoccer.

Öffentliche API:
    simulate_match(home_club, away_club) → dict

Rückgabe-Dict enthält alle Daten für den Spielbericht:
    home/away_goals, goal_events, match_stats,
    home/away_players, home/away_strength, home/away_teamwork, Formationen.
"""
import math
import random
from decimal import Decimal

from .match_readiness import calculate_lineup_strength, ensure_default_tactic
from .tactics import default_formation, formation_slots

# Relative Torwahrscheinlichkeit je Slot-Gruppe
_GOAL_WEIGHTS = {
    'goalkeeper':         0.01,
    'defense':            0.04,
    'defensive_midfield': 0.07,
    'midfield':           0.13,
    'offensive_midfield': 0.22,
    'attack':             0.53,
}


# ── Statistik-Helpers ────────────────────────────────────────────────────────

def _poisson(lam: float) -> int:
    """Poisson-Zufallsvariable (Knuth-Algorithmus)."""
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def _expected_goals(strength: Decimal, opp: Decimal) -> float:
    ratio = float(strength) / max(float(opp), 1.0)
    return max(0.2, 1.4 * ratio)


# ── Spieler-Helpers ──────────────────────────────────────────────────────────

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


def _lineup_players(tactic) -> list:
    """Liste von {'slot': slot_dict, 'player': Player} aus TacticSetup."""
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


def _pos_factor(player, slot_code: str) -> tuple[float, str | None]:
    """Gibt (Multiplikator, Label) zurück basierend auf Spielerposition vs. Slot.

    HP  → (1.00, None)   — Hauptposition, kein Malus
    NP  → (0.90, 'NP')   — Nebenposition, -10 %
    FP  → (0.80, 'FP')   — Fremdposition, -20 % (= LINEUP_MALUS_FACTOR)
    """
    try:
        if slot_code in player.main_positions:
            return 1.0, None
        if slot_code in player.secondary_positions:
            return 0.90, 'NP'
    except Exception:
        pass
    return 0.80, 'FP'


def _player_row(item: dict) -> dict:
    """Lineup-Item → Report-Spielerzeile."""
    p = item['player']
    slot = item['slot']
    try:
        sp = p.strength_profile
        base = float(sp.base_strength)
        final = float(sp.final_strength)
        freshness = float(sp.freshness)
    except Exception:
        base = final = 50.0
        freshness = 100.0

    factor, pos_label = _pos_factor(p, slot['code'])
    effective = round(final * factor, 1)

    return {
        'id': p.pk,
        'name': f"{p.first_name} {p.last_name}".strip() or str(p),
        'position': slot['code'],
        'group': slot['group'],
        'base_strength': round(base, 1),
        'potential': round(_potential(p), 1),
        'final_strength': effective,       # positionsbereinigt
        'final_strength_raw': round(final, 1),  # ohne Malus (für Tooltip)
        'pos_label': pos_label,            # None | 'NP' | 'FP'
        'freshness': int(round(freshness)),
        'teamwork': _teamwork(p),
        'goals': 0,
        'assists': 0,
    }


# ── Event-Generierung ────────────────────────────────────────────────────────

def _goal_events(n: int, team_key: str, lineup: list, minute_pool: list) -> list:
    """n Tor-Events mit Schütze + optionaler Vorlage erzeugen."""
    events = []
    weights = [_GOAL_WEIGHTS.get(item['slot']['group'], 0.05) for item in lineup]
    wsum = sum(weights) or 1.0
    weights = [w / wsum for w in weights]

    for _ in range(n):
        if minute_pool:
            minute = minute_pool.pop(random.randint(0, len(minute_pool) - 1))
        else:
            minute = random.randint(1, 90)

        scorer_idx = random.choices(range(len(lineup)), weights=weights, k=1)[0]
        scorer = lineup[scorer_idx]

        assister = None
        if random.random() < 0.72:
            cands = [i for i in range(len(lineup)) if i != scorer_idx]
            if cands:
                assister = lineup[random.choice(cands)]

        sp = scorer['player']
        ap = assister['player'] if assister else None

        events.append({
            'minute': minute,
            'team': team_key,
            'scorer_id': sp.pk,
            'scorer_name': f"{sp.first_name} {sp.last_name}".strip(),
            'scorer_pos': scorer['slot']['code'],
            'assister_id': ap.pk if ap else None,
            'assister_name': f"{ap.first_name} {ap.last_name}".strip() if ap else None,
        })

    return events


def _match_stats(hs: dict, as_: dict, hg: int, ag: int) -> dict:
    """Klassische Matchstatistiken generieren."""
    h = float(hs['overall'])
    a = float(as_['overall'])
    total = h + a or 1.0

    home_poss = int(round(max(30, min(70, 45 + (h - a) / total * 22))))

    def shots(goals):
        on_t = goals + random.randint(2, 5)
        return on_t, on_t + random.randint(3, 9)

    h_on, h_all = shots(hg)
    a_on, a_all = shots(ag)

    return {
        'home_possession': home_poss,
        'away_possession': 100 - home_poss,
        'home_shots': h_all,
        'away_shots': a_all,
        'home_shots_on_target': h_on,
        'away_shots_on_target': a_on,
        'home_corners': random.randint(2, 10),
        'away_corners': random.randint(2, 10),
        'home_fouls': random.randint(8, 20),
        'away_fouls': random.randint(8, 20),
        'home_yellow': random.randint(0, 3),
        'away_yellow': random.randint(0, 3),
        'home_red': 1 if random.random() < 0.04 else 0,
        'away_red': 1 if random.random() < 0.04 else 0,
    }


# ── Öffentliche API ──────────────────────────────────────────────────────────

def simulate_match(home_club, away_club) -> dict:
    """
    Simuliert ein Spiel und gibt ein vollständiges Report-Dict zurück.

    Rückgabe-Schlüssel:
        home_club_id, home_club_name, home_club_short, home_club_crest
        away_club_id, away_club_name, away_club_short, away_club_crest
        home_goals, away_goals
        goal_events:    [{minute, team, scorer_name, scorer_pos, assister_name}, …]
        match_stats:    {home/away_possession, shots, shots_on_target, corners, fouls, yellow, red}
        home_players:   [{name, position, base_strength, potential, final_strength, teamwork, goals, assists}, …]
        away_players:   (gleiche Struktur)
        home_strength:  {goalkeeper, defense, midfield, attack, overall}
        away_strength:  (gleiche Struktur)
        home_teamwork:  int  (Summe aller 11 Startspieler)
        away_teamwork:  int
        home_formation, away_formation: str
    """
    # 1. Aufstellungen sicherstellen
    home_tactic, _ = ensure_default_tactic(home_club)
    away_tactic, _ = ensure_default_tactic(away_club)

    # 2. Stärken
    h_str = calculate_lineup_strength(
        home_tactic.lineup or {},
        home_tactic.formation or default_formation(),
    )
    a_str = calculate_lineup_strength(
        away_tactic.lineup or {},
        away_tactic.formation or default_formation(),
    )

    # 3. Ergebnis
    h_goals = _poisson(_expected_goals(h_str['overall'], a_str['overall']))
    a_goals = _poisson(_expected_goals(a_str['overall'], h_str['overall']))

    # 4. Spieler
    h_lineup = _lineup_players(home_tactic)
    a_lineup = _lineup_players(away_tactic)
    h_players = [_player_row(item) for item in h_lineup]
    a_players = [_player_row(item) for item in a_lineup]

    # 5. Tor-Events
    minutes = list(range(1, 91))
    random.shuffle(minutes)
    events = (
        _goal_events(h_goals, 'home', h_lineup, minutes) +
        _goal_events(a_goals, 'away', a_lineup, minutes)
    )
    events.sort(key=lambda e: e['minute'])

    # Tore/Vorlagen in Spieler-Dicts eintragen
    h_pid = {p['id']: p for p in h_players}
    a_pid = {p['id']: p for p in a_players}
    for evt in events:
        pid_map = h_pid if evt['team'] == 'home' else a_pid
        if evt['scorer_id'] in pid_map:
            pid_map[evt['scorer_id']]['goals'] += 1
        if evt['assister_id'] and evt['assister_id'] in pid_map:
            pid_map[evt['assister_id']]['assists'] += 1

    # 6. Statistiken + Teamwork
    stats = _match_stats(h_str, a_str, h_goals, a_goals)
    h_teamwork = sum(p['teamwork'] for p in h_players)
    a_teamwork = sum(p['teamwork'] for p in a_players)

    def _fmt(tactic):
        f = tactic.formation or {}
        return f.get('name', '') or '4-4-2'

    return {
        'home_club_id':    home_club.pk,
        'home_club_name':  home_club.name,
        'home_club_short': home_club.short_name or home_club.name[:4].upper(),
        'home_club_crest': getattr(home_club, 'crest_static_path', None),
        'away_club_id':    away_club.pk,
        'away_club_name':  away_club.name,
        'away_club_short': away_club.short_name or away_club.name[:4].upper(),
        'away_club_crest': getattr(away_club, 'crest_static_path', None),
        'home_goals':      h_goals,
        'away_goals':      a_goals,
        'goal_events':     events,
        'match_stats':     stats,
        'home_players':    h_players,
        'away_players':    a_players,
        'home_strength':   {k: round(float(v), 1) for k, v in h_str.items()},
        'away_strength':   {k: round(float(v), 1) for k, v in a_str.items()},
        'home_teamwork':   h_teamwork,
        'away_teamwork':   a_teamwork,
        'home_formation':  _fmt(home_tactic),
        'away_formation':  _fmt(away_tactic),
    }
