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
from .tactics import default_formation, formation_slots, formation_code, SQUAD_PRO
from .tactic_compiler import (
    calculate_zone_strengths,
    compile_tactic,
    select_active_condition_plan,
)
from .position_service import (
    get_position_fit as _get_position_fit,
    FOREIGN_POSITION_FACTOR as _FP_FACTOR,
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

# ── Wechsel-Konstanten ────────────────────────────────────────────────────────
MAX_SUBSTITUTIONS = 5  # geteiltes Kontingent: geplante + Verletzungswechsel


def _ceil5(minute: int) -> int:
    """Rundet eine Minute auf das nächste 5er-Vielfaches auf.

    Damit stimmt die angezeigte Wechselminute mit dem Segment-Effekt überein.
    Beispiel: 63 → 65, 60 → 60, 45 → 45.
    """
    return math.ceil(max(1, int(minute)) / 5) * 5


def _check_sub_condition(cond: str, own_goals: int, opp_goals: int) -> bool:
    """Prüft ob eine Wechselbedingung zum aktuellen Spielstand erfüllt ist.

    Wird genau einmal pro geplanten Wechsel aufgerufen. Nicht erfüllte
    Bedingungen werden endgültig verworfen — kein späteres Nachholen.
    """
    if not cond or cond == 'immer':
        return True
    if cond == 'fuehrung':
        return own_goals > opp_goals
    if cond == 'rueckstand':
        return own_goals < opp_goals
    if cond == 'unentschieden':
        return own_goals == opp_goals
    return True


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
    Frische unter 80 reduziert das Ergebnis proportional (Frische-Leistungsmalus V1).
    """
    try:
        sp = player.strength_profile
        base = float(sp.base_strength or 50.0)
        form = float(sp.form_modifier or 0.0)
        freshness = int(round(float(sp.freshness or 100.0)))
    except Exception:
        return 50.0

    pot = _potential(player)
    drawn = random.uniform(base, pot) if pot > base else base
    raw = drawn + form

    from .freshness_service import freshness_performance_factor
    perf = freshness_performance_factor(freshness)

    return round(max(0.0, min(200.0, raw * perf)), 2)


def _pos_factor(player, slot_code: str) -> tuple[float, str | None]:
    """Gibt (Multiplikator, Label) zurück basierend auf Spielerposition vs. Slot.

    HP  → (1.00, None)   — Hauptposition, kein Malus
    NP  → (0.90, 'NP')   — Nebenposition, −10 %
    FP  → (0.70, 'FP')   — Fremdposition, −30 % (konsistent mit position_service)
    """
    try:
        if slot_code in player.main_positions:
            return 1.0, None
        if slot_code in player.secondary_positions:
            return 0.90, 'NP'
    except Exception:
        pass
    return _FP_FACTOR, 'FP'


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


def _slot_to_group(slot_code: str) -> str:
    """Positions-Code → Lineup-Gruppenname (für bench-player rows)."""
    s = (slot_code or '').upper()
    if s in ('TW', 'GK'):
        return 'goalkeeper'
    if s in ('IV', 'LV', 'RV', 'LOV', 'ROV', 'CB', 'LB', 'RB', 'WB'):
        return 'defense'
    if s == 'DM':
        return 'defensive_midfield'
    if s in ('ST', 'LF', 'RF', 'CF', 'SS'):
        return 'attack'
    return 'midfield'


def _build_windows_map(sub_events: list[dict]) -> dict[int, tuple[int, int]]:
    """Aktives Zeitfenster (on_minute, off_minute) pro Spieler aus Wechsel-Events.

    Starter ohne Wechsel: nicht im Dict (Caller nimmt Default (0, 90)).
    Starter ausgewechselt bei M: (0, M).
    Eingewechselter rein bei M: (M, 90).
    Wechselkette (rein M1, raus M2): (M1, M2).

    Wird für korrekte Karten-/Verletzungsminuten-Zuweisung benötigt;
    minutes_played + is_sub allein kann Ketten-Fenster nicht korrekt rekonstruieren.
    """
    on_min: dict[int, int]  = {}
    off_min: dict[int, int] = {}

    for evt in (sub_events or []):
        out_pid = evt.get('out')
        in_pid  = evt.get('in')
        minute  = int(evt.get('minute', 90) or 90)
        if out_pid:
            off_min[out_pid] = minute
        if in_pid:
            on_min[in_pid] = minute

    windows: dict[int, tuple[int, int]] = {}
    for pid, off in off_min.items():
        start = on_min.get(pid, 0)
        windows[pid] = (start, off)
    for pid, on in on_min.items():
        if pid not in windows:
            windows[pid] = (on, 90)
    return windows


def _build_minutes_played_map(sub_events: list[dict]) -> dict[int, int]:
    """Einsatzminuten aus Wechsel-Events.

    Starter ohne Wechsel: Default 90 Minuten (nicht im Dict → Caller nimmt 90).
    Starter ausgewechselt bei Minute M: minutes_played = M.
    Eingewechselter kommt rein bei M: minutes_played = 90 - M.
    Wechselkette (rein bei M1, raus bei M2): minutes_played = M2 - M1.
    """
    on_min: dict[int, int]  = {}   # Minute, ab der Spieler spielt (0 = Starter)
    off_min: dict[int, int] = {}   # Minute, in der Spieler rauskommt

    for evt in (sub_events or []):
        out_pid = evt.get('out')
        in_pid  = evt.get('in')
        minute  = int(evt.get('minute', 90) or 90)
        if out_pid:
            off_min[out_pid] = minute
        if in_pid:
            on_min[in_pid] = minute

    minutes: dict[int, int] = {}
    for pid, off in off_min.items():
        start = on_min.get(pid, 0)   # 0 → Starter; sonst Einwechselminute
        minutes[pid] = max(0, off - start)
    for pid, on in on_min.items():
        if pid not in minutes:
            minutes[pid] = max(0, 90 - on)
    return minutes


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


def _active_lineup_players(
    active_lineup: list[dict],
    players_by_id: dict[int, dict],
) -> list[dict]:
    """Aktive Aufstellung → flache Spielerliste mit position/group.

    Entspricht _lineup_players_dict(), aber arbeitet mit der aktuellen
    (möglicherweise durch Wechsel mutierten) Lineup statt dem statischen
    Team-Dict.
    """
    result = []
    for slot in active_lineup:
        pid = slot.get('player_id')
        p = players_by_id.get(pid)
        if p:
            result.append({**p, 'position': slot['position'], 'group': slot.get('group', 'attack')})
    return result


class ActiveLineupState:
    """Gemeinsamer Zustand für alle Lineup-Veränderungen während eines Spiels.

    Verwaltet: geplante Wechsel, Spielminuten-Tracking.
    Dismissals werden über h_dismissed_pids-Set behandelt (bestehende Logik),
    get_active_lineup(dismissed_pids) filtert sie heraus.

    Keine ORM-Abfragen — alle Spielerdaten müssen vorab geladen sein.

    Bedingungsauswertung: jeder geplante Wechsel wird genau EINMAL bewertet
    (im ersten Segment nach seiner Minute). resolved_sub_idxs markiert alle
    bewerteten Wechsel — ausgeführte UND verworfene. Späteres Nachholen
    ist explizit ausgeschlossen.
    """

    def __init__(
        self,
        lineup: list[dict],
        players_by_id: dict[int, dict],
        bench_by_id: dict[int, dict],
        planned_subs: list[dict],
    ) -> None:
        """
        lineup:       [{player_id, position, group}, ...] — Startaufstellung
        players_by_id: {pid: player_dict} — Stammelf (vorab geladen)
        bench_by_id:  {pid: player_dict} — Bankspieler (vorab geladen)
        planned_subs: [{in, out, minute, condition}, ...] aus TacticSetup
        """
        self._lineup_slots: list[dict] = [dict(s) for s in lineup]
        self._pid_to_slot: dict[int, dict] = {
            s['player_id']: s for s in self._lineup_slots
        }
        self.players_by_id: dict[int, dict] = dict(players_by_id)
        for pid, data in (bench_by_id or {}).items():
            if pid not in self.players_by_id:
                self.players_by_id[pid] = dict(data)

        self._bench_available: set[int] = set((bench_by_id or {}).keys())
        self._planned_subs: list[dict] = list(planned_subs or [])

        self.used_substitutions: int = 0
        self._resolved_idxs: set[int] = set()
        self.sub_events: list[dict] = []

        self.player_on_minute: dict[int, int] = {}
        self.player_off_minute: dict[int, int] = {}
        for s in lineup:
            self.player_on_minute[s['player_id']] = 0

    def get_active_lineup(self, dismissed_pids: set | None = None) -> list[dict]:
        """Aktuelle Lineup exkl. verwiesener Spieler (ausgewechselte sind bereits entfernt)."""
        excl = dismissed_pids or set()
        return [dict(s) for s in self._lineup_slots if s['player_id'] not in excl]

    def can_substitute(self) -> bool:
        return self.used_substitutions < MAX_SUBSTITUTIONS

    def process_planned_subs(
        self,
        segment_start: int,
        own_goals: int,
        opp_goals: int,
        dismissed_pids: set | None = None,
    ) -> None:
        """Prüft geplante Wechsel genau einmal je Segment.

        Regel: sub_minute < segment_start → dieser Segment ist der erste,
        in dem der Wechsel hätte wirken sollen.

        Bedingung erfüllt → ausführen.
        Bedingung NICHT erfüllt → endgültig verwerfen (nie wieder prüfen).
        """
        excl = dismissed_pids or set()

        for idx, sub in enumerate(self._planned_subs):
            if idx in self._resolved_idxs:
                continue
            sub_minute = int(sub.get('minute', 999) or 999)
            if sub_minute >= segment_start:
                continue

            # Einmalig bewerten — egal ob ausgeführt oder verworfen
            self._resolved_idxs.add(idx)

            if not self.can_substitute():
                continue

            in_pid  = sub.get('in')
            out_pid = sub.get('out')
            if not in_pid or not out_pid:
                continue
            if in_pid not in self._bench_available:
                continue
            if out_pid not in self._pid_to_slot or out_pid in excl:
                continue
            if in_pid in self._pid_to_slot:
                continue

            # Bedingung einmalig prüfen — nicht erfüllt → verworfen (resolved bleibt)
            cond = sub.get('condition', 'immer')
            if not _check_sub_condition(cond, own_goals, opp_goals):
                continue

            # ── Wechsel ausführen ────────────────────────────────────────────
            executed_minute = _ceil5(sub_minute)
            old_slot = self._pid_to_slot[out_pid]
            target_slot  = old_slot['position']
            target_group = old_slot.get('group', 'attack')

            _, relation = _get_position_fit(
                self.players_by_id.get(in_pid, {}), target_slot
            )

            old_slot['player_id'] = in_pid
            del self._pid_to_slot[out_pid]
            self._pid_to_slot[in_pid] = old_slot

            self._bench_available.discard(in_pid)
            self.used_substitutions += 1
            self.player_off_minute[out_pid] = executed_minute
            self.player_on_minute[in_pid]   = executed_minute

            self.sub_events.append({
                'in':                in_pid,
                'out':               out_pid,
                'minute':            executed_minute,
                'target_slot':       target_slot,
                'position_relation': relation,
                'condition':         cond,
            })

    def process_injury_subs(self) -> None:
        """Wechselt verletzte Startspieler (is_ws_injured=True) automatisch aus.

        Feuert in Minute 5 (früheste sichtbare Wechselminute im Ticker).
        Zählt zum MAX_SUBSTITUTIONS=5-Kontingent.
        Bankspiele werden nach bestem Positionsfit für den freiwerdenden Slot
        ausgewählt. Kein Wechsel wenn kein Bankspiele verfügbar oder Kontingent
        erschöpft.
        """
        injured_slots = [
            s for s in self._lineup_slots
            if self.players_by_id.get(s['player_id'], {}).get('is_ws_injured')
        ]
        for slot in injured_slots:
            if not self.can_substitute():
                break
            if not self._bench_available:
                break
            out_pid = slot['player_id']
            target_slot = slot['position']
            best_in_pid: int | None = None
            best_factor = -1.0
            for bench_pid in self._bench_available:
                if bench_pid in self._pid_to_slot:
                    continue
                factor, _ = _get_position_fit(self.players_by_id.get(bench_pid, {}), target_slot)
                if factor > best_factor:
                    best_factor = factor
                    best_in_pid = bench_pid
            if best_in_pid is None:
                continue
            _, relation = _get_position_fit(self.players_by_id.get(best_in_pid, {}), target_slot)
            executed_minute = 5
            slot['player_id'] = best_in_pid
            del self._pid_to_slot[out_pid]
            self._pid_to_slot[best_in_pid] = slot
            self._bench_available.discard(best_in_pid)
            self.used_substitutions += 1
            self.player_off_minute[out_pid] = executed_minute
            self.player_on_minute[best_in_pid] = executed_minute
            self.sub_events.append({
                'in':                best_in_pid,
                'out':               out_pid,
                'minute':            executed_minute,
                'target_slot':       target_slot,
                'position_relation': relation,
                'condition':         'verletzung',
            })


# ── ORM → Team-Dict Bridge ────────────────────────────────────────────────────

def _build_team_dict(club, tactic_setup, match_strengths: dict | None = None, strength_malus: float = 1.0) -> dict:
    """Konvertiert Django ORM-Objekte in das Team-Dict-Format des Taktik-Compilers.

    Rückgabe-Format entspricht dem Standalone-Format (bayern_fixture.json).
    match_strengths: vorberechnete {player_id → float} Matchstärken (random(basis, pot) + form).
    strength_malus:  Multiplikator für Nichtaufstellungs-Strafe (0.70 = 30 % Abzug).
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
            final_strength = match_strengths[pid] * strength_malus
        else:
            try:
                sp = p.strength_profile
                final_strength = float(sp.final_strength or 50.0) * strength_malus
            except Exception:
                final_strength = 50.0 * strength_malus
        try:
            _freshness = int(round(float(p.strength_profile.freshness or 100.0)))
        except Exception:
            _freshness = 100
        players_list.append({
            'id': p.pk,
            'name': f'{p.first_name} {p.last_name}'.strip() or str(p),
            'final_strength': final_strength,
            'main_positions': list(p.main_positions),
            'secondary_positions': list(p.secondary_positions),
            'teamwork': _teamwork(p),
            'freshness': _freshness,
            'is_ws_injured': bool(getattr(p, 'ws_injury_days_remaining', 0) or 0),
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
    """Delegiert an position_service.get_position_fit() — zentraler Positionsfit."""
    return _get_position_fit(player_dict, position_code)


def _calculate_lineup_strength(
    team: dict,
    tactic_override: Optional[dict] = None,
    compiled_tactic: Optional[dict] = None,
    dismissed_pids: Optional[set] = None,
    gk_strength_override: Optional[float] = None,
) -> dict:
    """Linienstärken inkl. Taktik-Multiplikatoren (Port aus Standalone).

    dismissed_pids:      Spieler-IDs mit Platzverweis — werden aus der
                         Stärkeberechnung ausgeschlossen (T009 Dismissals V1).
    gk_strength_override: Stärke des Ersatz-TW oder Not-TW bei TW-Platzverweis.
    """
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
        if dismissed_pids and pid in dismissed_pids:
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

    # TW-Platzverweis: Bench-TW oder Not-TW-Stärke einsetzen
    if not lines['goalkeeper'] and gk_strength_override is not None:
        lines['goalkeeper'] = [gk_strength_override * multipliers.get('goalkeeper', 1.0)]

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


# ── T009 Dismissals V1 ────────────────────────────────────────────────────────

def _find_bench_gk(team_dict: dict, used_pids: set) -> Optional[dict]:
    """Sucht den ersten TW auf der Bank, der nicht schon in der Lineup ist."""
    bench_ids = list((team_dict.get('tactic') or {}).get('bench') or [])
    players_by_id = {p['id']: p for p in team_dict.get('players', [])}
    for pid in bench_ids:
        if pid in used_pids:
            continue
        p = players_by_id.get(pid)
        if p and p.get('primary_position') == 'TW':
            return p
    return None


def _dismissal_this_segment(
    compiled: dict,
    seg_len: int,
    team_yellows_so_far: int,
) -> tuple[int, str]:
    """Gibt (anzahl_platzverweise, card_type) zurück. Maximal 1 pro Segment.

    card_type: 'red' | 'yellow_red' | ''

    Direktes Rot: feste Wahrscheinlichkeit (wie bisheriges _red_card_this_segment).
    Gelb-Rot:     nur möglich wenn Team ≥ 2 Gelbe angesammelt hat;
                  Wahrscheinlichkeit steigt mit Kartenanzahl.
    """
    scale = seg_len / 90.0
    card_mult = compiled.get('card_multiplier', 1.0)
    if random.random() < min(0.08, 0.025 * card_mult * scale):
        return 1, 'red'
    if team_yellows_so_far >= 2:
        yr_base = 0.018 * card_mult * min(team_yellows_so_far / 3.0, 1.5) * scale
        if random.random() < min(0.05, yr_base):
            return 1, 'yellow_red'
    return 0, ''


def _resolve_dismissal(
    team_dict: dict,
    lineup_players: list[dict],
    dismissed_pids: set,
    minute: int,
    club_side: str,
    card_type: str,
) -> tuple[Optional[dict], Optional[float]]:
    """Verarbeitet einen Platzverweis; gibt (event, gk_strength_override) zurück.

    gk_strength_override wird nur gesetzt wenn der TW verwiesen wird:
    - Bench-TW vorhanden → dessen final_strength
    - Kein Bench-TW      → schlechtester Outfielder × 0.6 (Not-TW-Malus)

    TW-Sonderlogik V1:
    - Outfield-Rot:           10-Mann-Stärke ab Folgesegment.
    - TW-Rot + Bench-TW:      Bench-TW übernimmt GK-Stärke, 1 Outfielder raus.
    - TW-Rot + kein Bench-TW: Not-TW (schwächster Outfielder × 0.6) als GK.
    """
    active = [p for p in lineup_players if p.get('id') not in dismissed_pids]
    if not active:
        return None, None

    non_gk = [p for p in active if p.get('group') != 'goalkeeper']
    gk_active = [p for p in active if p.get('group') == 'goalkeeper']
    gk_override: Optional[float] = None

    if non_gk:
        dismissed = random.choice(non_gk)
    elif gk_active:
        dismissed = gk_active[0]
    else:
        return None, None

    if dismissed.get('group') == 'goalkeeper':
        all_pids = {p['id'] for p in lineup_players}
        bench_gk = _find_bench_gk(team_dict, all_pids)
        if bench_gk:
            gk_override = float(bench_gk.get('final_strength', 50.0))
        else:
            outfield = [
                p for p in lineup_players
                if p.get('group') != 'goalkeeper' and p.get('id') not in dismissed_pids
            ]
            if outfield:
                worst = min(outfield, key=lambda p: float(p.get('final_strength', 50.0)))
                gk_override = float(worst.get('final_strength', 50.0)) * 0.6
            else:
                gk_override = 30.0

    pid = dismissed.get('id')
    dismissed_pids.add(pid)
    return {
        'player_id':   pid,
        'player_name': dismissed.get('name', ''),
        'club_side':   club_side,
        'minute':      minute,
        'card_type':   card_type,
    }, gk_override


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

    # ── Aktive Aufstellung + Wechsel-State (alle Spielerdaten vorab geladen) ──
    h_als = ActiveLineupState(
        lineup=home_team.get('lineup', []),
        players_by_id={p['id']: p for p in home_team.get('players', [])},
        bench_by_id=home_team.get('bench_player_data') or {},
        planned_subs=home_team.get('planned_substitutions') or [],
    )
    a_als = ActiveLineupState(
        lineup=away_team.get('lineup', []),
        players_by_id={p['id']: p for p in away_team.get('players', [])},
        bench_by_id=away_team.get('bench_player_data') or {},
        planned_subs=away_team.get('planned_substitutions') or [],
    )

    # ── Verletzungswechsel vor Anpfiff (Minute 5) ────────────────────────────
    h_als.process_injury_subs()
    a_als.process_injury_subs()

    h_goals = 0
    a_goals = 0
    h_xg_total = 0.0
    a_xg_total = 0.0
    h_red = 0
    a_red = 0
    events: list[dict] = []
    plan_activations: list[dict] = []
    # T009 Dismissals V1
    h_dismissed_pids: set = set()
    a_dismissed_pids: set = set()
    h_gk_str_override: Optional[float] = None
    a_gk_str_override: Optional[float] = None
    h_dismissal_events: list[dict] = []
    a_dismissal_events: list[dict] = []
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

        # ── Geplante Wechsel vor diesem Segment ausführen ────────────────────
        h_als.process_planned_subs(minute, h_goals, a_goals, h_dismissed_pids)
        a_als.process_planned_subs(minute, a_goals, h_goals, a_dismissed_pids)

        # ── Aktuelle Segment-Elf (Wechsel + Platzverweise berücksichtigt) ────
        _h_active = h_als.get_active_lineup(h_dismissed_pids)
        _a_active = a_als.get_active_lineup(a_dismissed_pids)
        _h_cur    = _active_lineup_players(_h_active, h_als.players_by_id)
        _a_cur    = _active_lineup_players(_a_active, a_als.players_by_id)
        _h_team_seg = {**home_team, 'lineup': _h_active, 'players': list(h_als.players_by_id.values())}
        _a_team_seg = {**away_team, 'lineup': _a_active, 'players': list(a_als.players_by_id.values())}

        h_tactic_seg = _with_active_plan(home_base_tactic, h_plan)
        a_tactic_seg = _with_active_plan(away_base_tactic, a_plan)
        h_comp = compile_tactic(_h_team_seg, h_tactic_seg, half=half)
        h_comp['pressing_index'] = _clamp(
            h_comp.get('pressing_index', 0.35) + HOME_PRESSING_BONUS, 0.0, 1.0
        )
        a_comp = compile_tactic(_a_team_seg, a_tactic_seg, half=half)
        h_str  = _calculate_lineup_strength(
            _h_team_seg, h_tactic_seg, h_comp,
            dismissed_pids=None,           # bereits aus _h_active herausgefiltert
            gk_strength_override=h_gk_str_override,
        )
        a_str  = _calculate_lineup_strength(
            _a_team_seg, a_tactic_seg, a_comp,
            dismissed_pids=None,
            gk_strength_override=a_gk_str_override,
        )
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
        # Tore/Assists nur aus aktiven Spielern (ausgewechselt/verwiesen = nicht im Pool)
        events.extend(_goal_events(hg, 'home', _h_cur or _active_lineup_players(h_als.get_active_lineup(), h_als.players_by_id), minute_pool.copy()))
        events.extend(_goal_events(ag, 'away', _a_cur or _active_lineup_players(a_als.get_active_lineup(), a_als.players_by_id), minute_pool.copy()))

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

        # T009 Dismissals V1: Platzverweis (Rot + Gelb-Rot) ──────────────────
        h_dis, h_dis_type = _dismissal_this_segment(h_comp, seg_len, h_stats_total['yellow'])
        a_dis, a_dis_type = _dismissal_this_segment(a_comp, seg_len, a_stats_total['yellow'])
        h_red_seg = h_dis
        a_red_seg = a_dis
        h_red += h_red_seg
        a_red += a_red_seg

        if h_dis:
            ev, gk_ov = _resolve_dismissal(
                home_team, _h_cur, h_dismissed_pids, end_min, 'home', h_dis_type)
            if ev:
                h_dismissal_events.append(ev)
                if gk_ov is not None:
                    h_gk_str_override = gk_ov

        if a_dis:
            ev, gk_ov = _resolve_dismissal(
                away_team, _a_cur, a_dismissed_pids, end_min, 'away', a_dis_type)
            if ev:
                a_dismissal_events.append(ev)
                if gk_ov is not None:
                    a_gk_str_override = gk_ov

        total_strength = h_str['overall'] + a_str['overall'] or 1.0
        poss_delta = (h_comp.get('possession_bonus', 0.0) - a_comp.get('possession_bonus', 0.0)) * 35
        build_delta = (h_comp.get('build_control', 0.0) - a_comp.get('build_control', 0.0)) * 10
        # Realistisches Segmentrauschen ±5 pp — verhindert Fixwert-Ballbesitz über 90 min
        poss_noise = random.gauss(0.0, 5.0)
        home_poss = int(round(_clamp(
            50 + HOME_POSSESSION_BONUS
            + (h_str['overall'] - a_str['overall']) / total_strength * 22
            + poss_delta + build_delta + poss_noise,
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
        'dismissal_events': h_dismissal_events + a_dismissal_events,
        'h_sim_sub_events': h_als.sub_events,
        'a_sim_sub_events': a_als.sub_events,
    }


# ── Spieler-Notensystem ───────────────────────────────────────────────────────

def _rating_pos_group(position: str, group: str) -> str:
    """Gibt die Notengruppe (GK/DEF/DM/MID/FWD) zurück — V1.1.

    Gruppen:
        GK  = Torwart
        DEF = IV, LV, RV und Äquivalente
        DM  = Defensives Mittelfeld (eigene Gruppe, Hybrid DEF/MID)
        MID = Zentrales/Offensives Mittelfeld, Flügelläufer
        FWD = Stürmer, Außenstürmer
    """
    pos = (position or '').upper()
    grp = (group or '').lower()
    if pos in ('TW', 'GK') or grp == 'goalkeeper':
        return 'GK'
    if pos == 'DM':
        return 'DM'
    if grp == 'defense' or pos in ('IV', 'LV', 'RV', 'CB', 'LB', 'RB', 'WB', 'LOV', 'ROV'):
        return 'DEF'
    if grp in ('midfield', 'defensive_midfield', 'offensive_midfield') or pos in (
        'ZM', 'OM', 'LM', 'RM', 'LA', 'RA', 'CM', 'AM',
    ):
        return 'MID'
    return 'FWD'


def _player_active_window(p: dict) -> tuple[int, int]:
    """Gibt (on_minute, off_minute) des Spielers zurück.

    Priorität:
    1. Explizite on_minute/off_minute auf dem Player-Row (gesetzt von simulate_match()
       via _build_windows_map) — korrekt auch für Wechselketten.
    2. Fallback: Inferenz aus minutes_played + is_sub (funktioniert nur für
       Nicht-Ketten-Fälle; Starter und Erst-Eingewechselte ohne Folgekette).
    """
    if 'on_minute' in p and 'off_minute' in p:
        on  = max(0, int(p['on_minute'] or 0))
        off = max(on + 1, int(p['off_minute'] or 90))
        return (max(1, on), off)
    # Fallback (ohne explizites Zeitfenster)
    mp = int(p.get('minutes_played', 90) or 90)
    if p.get('is_sub'):
        on = max(1, 90 - mp)
        return (on, 90)
    return (1, max(1, mp))


def _weighted_sample_no_replace(players: list[dict], k: int) -> list[int]:
    """Sample k einzigartige Spieler-Indizes, gewichtet nach minutes_played.

    Spieler mit mehr Einsatzzeit werden häufiger ausgewählt.
    Gibt eine Liste von Indizes (ohne Dopplungen) zurück.
    """
    pool: list[int] = []
    for i, p in enumerate(players):
        mp = max(5, int(p.get('minutes_played', 90) or 90))
        tickets = max(1, mp // 5)
        pool.extend([i] * tickets)
    random.shuffle(pool)
    result: list[int] = []
    seen: set[int] = set()
    for idx in pool:
        if idx not in seen:
            result.append(idx)
            seen.add(idx)
        if len(result) == k:
            break
    # Lücke mit verbliebenen Spielern schließen (falls Pool zu klein)
    remaining = [i for i in range(len(players)) if i not in seen]
    random.shuffle(remaining)
    result.extend(remaining[: max(0, k - len(result))])
    return result[:k]


def _assign_cards_to_players(
    players: list[dict],
    yellow_count: int,
    red_count: int,
    club_side: str = 'home',
) -> tuple:
    """Verteilt Team-Karten auf Spieler gewichtet nach Einsatzminuten.

    Karten-Minuten liegen im aktiven Zeitfenster jedes Spielers (on_minute..off_minute).
    Jeder Spieler erhält maximal 1 Gelbe und 1 Rote Karte.

    Gibt (players, card_events) zurück.
    """
    players = [dict(p) for p in players]
    n = len(players)
    if not n:
        return players, []
    y = min(max(0, yellow_count), n)
    r = min(max(0, red_count), n)
    card_events = []
    for i in _weighted_sample_no_replace(players, y):
        players[i]['yellow_cards'] = 1
        lo, hi = _player_active_window(players[i])
        card_events.append({
            'player_id':   players[i].get('id'),
            'player_name': players[i].get('name', ''),
            'card_type':   'yellow',
            'minute':      random.randint(lo, hi),
            'club_side':   club_side,
        })
    for i in _weighted_sample_no_replace(players, r):
        players[i]['red_cards'] = 1
        lo, hi = _player_active_window(players[i])
        # min(…, hi) verhindert ValueError wenn hi < 20 (Frühauswechslung)
        red_lo = min(max(lo, 20), hi)
        card_events.append({
            'player_id':   players[i].get('id'),
            'player_name': players[i].get('name', ''),
            'card_type':   'red',
            'minute':      random.randint(red_lo, hi),
            'club_side':   club_side,
        })
    return players, card_events


# ── Verletzungs-Simulation ────────────────────────────────────────────────────

_INJURY_TIERS = [
    ('Leicht',  3,  7, 0.70),
    ('Mittel', 10, 21, 0.25),
    ('Schwer', 28, 56, 0.05),
]

_MAX_INJURIES_PER_TEAM = 2


def _generate_injury_events(
    players: list[dict],
    club_side: str,
    medizin_factor: float = 1.0,
) -> list[dict]:
    """Zieht zufällige Verletzungsereignisse für einen Spieler-Pool (V1-Formel).

    Basisrisiko: 0.9 % pro Spieler/90 min (statt pauschal 4 %).
    Frische-Multiplikator: 1.0 (90–100) bis 2.3 (< 50) → reale Frische fließt ein.
    Medizin-Multiplikator: 1.0 (Stufe 0) bis 0.8 (Stufe 3).
    Maximum: _MAX_INJURIES_PER_TEAM (2) Verletzungen pro Team.

    Gibt eine Liste von injury-Event-Dicts zurück::
        [{player_id, player_name, club_side, minute, injury_type, days}, ...]
    """
    from .freshness_service import BASE_INJURY_RISK_PER_90, freshness_injury_multiplier

    candidates = []
    for p in players:
        freshness = int(p.get('freshness') or 100)
        mp = int(p.get('minutes_played', 90) or 90)
        # Risiko proportional zur Einsatzzeit skalieren
        prob = BASE_INJURY_RISK_PER_90 * freshness_injury_multiplier(freshness) * medizin_factor * (mp / 90.0)
        if random.random() >= prob:
            continue
        r = random.random()
        cumulative = 0.0
        chosen_type, chosen_days = 'Leicht', random.randint(3, 7)
        for itype, dmin, dmax, weight in _INJURY_TIERS:
            cumulative += weight
            if r < cumulative:
                chosen_type = itype
                chosen_days = random.randint(dmin, dmax)
                break
        lo, hi = _player_active_window(p)
        # min(…, hi) verhindert ValueError wenn hi < 10 (Frühauswechslung)
        inj_lo = min(max(lo, 10), hi)
        candidates.append({
            'player_id':   p.get('id'),
            'player_name': p.get('name', ''),
            'club_side':   club_side,
            'minute':      random.randint(inj_lo, hi),
            'injury_type': chosen_type,
            'days':        chosen_days,
            'post_match':  True,   # post-Simulation erzeugt → kein Wechsel erfolgt
        })

    if len(candidates) > _MAX_INJURIES_PER_TEAM:
        candidates = random.sample(candidates, _MAX_INJURIES_PER_TEAM)
    return candidates


def compute_player_ratings(result: dict) -> dict:
    """Berechnet positionsabhängige Spielernoten (1,0–6,0) aus einem Simulations-Dict.

    Noten V1.1 — Modifikatoren:
        A) Team-Ergebnis (gestuft nach Tordifferenz)
        B) Team-xGD (Dominanzindikator, alle Positionen)
        C) Gegnerstärke (overall-Differenz, max ±0.18)
        D) Scorer (positions-differenziert; TW/DEF/DM-MID/FWD; Doppelpack-Boni)
        E) Karten (Gelb +0.30, Rot +1.50)
        F) Positionslogik (GK / DEF / DM / MID / FWD)

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

    h_press_wins = ms.get('home_pressing_ball_wins', 0) or 0
    a_press_wins = ms.get('away_pressing_ball_wins', 0) or 0
    h_press_bp   = ms.get('home_pressing_bypassed', 0) or 0
    a_press_bp   = ms.get('away_pressing_bypassed', 0) or 0
    h_poss       = ms.get('home_possession', 50) or 50
    a_poss       = ms.get('away_possession', 50) or 50

    h_str_overall = float((result.get('home_strength') or {}).get('overall') or 50)
    a_str_overall = float((result.get('away_strength') or {}).get('overall') or 50)

    h_win = h_goals > a_goals
    a_win = a_goals > h_goals

    h_players_raw = result.get('home_players', []) or []
    a_players_raw = result.get('away_players', []) or []

    def _rate(p: dict, is_home: bool) -> float:
        rating = 3.5
        pg = _rating_pos_group(p.get('position', ''), p.get('group', ''))

        goals   = p.get('goals', 0) or 0
        assists = p.get('assists', 0) or 0
        yellow  = p.get('yellow_cards', 0) or 0
        red     = p.get('red_cards', 0) or 0

        my_goals  = h_goals        if is_home else a_goals
        opp_goals = a_goals        if is_home else h_goals
        my_xg     = h_xg           if is_home else a_xg
        opp_xg    = a_xg           if is_home else h_xg
        my_win    = h_win          if is_home else a_win
        opp_win   = a_win          if is_home else h_win
        my_pw     = h_press_wins   if is_home else a_press_wins
        opp_bp    = a_press_bp     if is_home else h_press_bp
        my_poss   = h_poss         if is_home else a_poss
        my_str    = h_str_overall  if is_home else a_str_overall
        opp_str   = a_str_overall  if is_home else h_str_overall

        # A) Team-Ergebnis (gestuft nach Tordifferenz)
        goal_diff = my_goals - opp_goals
        if goal_diff == 1:
            rating -= 0.23
        elif goal_diff == 2:
            rating -= 0.31
        elif goal_diff == 3:
            rating -= 0.49
        elif goal_diff >= 4:
            rating -= 0.55
        elif goal_diff == -1:
            rating += 0.23
        elif goal_diff == -2:
            rating += 0.31
        elif goal_diff == -3:
            rating += 0.49
        elif goal_diff <= -4:
            rating += 0.55

        # B) Team-xGD (Dominanzindikator, alle Positionen)
        xg_diff = my_xg - opp_xg
        if xg_diff >= 1.5:
            rating -= 0.20
        elif xg_diff >= 0.5:
            rating -= 0.10
        elif xg_diff <= -1.5:
            rating += 0.20
        elif xg_diff <= -0.5:
            rating += 0.10

        # C) Gegnerstärke (str_diff positiv = ich bin stärker als Gegner)
        str_diff = my_str - opp_str
        if my_win:
            if str_diff <= -15:
                rating -= 0.18   # Sieg gegen viel stärkeren Gegner
            elif str_diff <= -8:
                rating -= 0.10   # Sieg gegen etwas stärkeren
        elif opp_win:
            if str_diff >= 15:
                rating += 0.18   # Niederlage gegen viel schwächeren
            elif str_diff >= 8:
                rating += 0.10   # Niederlage gegen schwächeren

        # D) Scorer (positions-differenziert)
        if goals > 0:
            per_goal = {
                'GK': 1.50, 'DEF': 1.00, 'DM': 0.85, 'MID': 0.85, 'FWD': 0.70,
            }.get(pg, 0.70)
            rating -= goals * per_goal
            if goals >= 2:
                rating -= 0.25   # Doppelpack-Bonus
            if goals >= 3:
                rating -= 0.20   # Hattrick-Bonus

        if assists > 0:
            per_assist = {
                'GK': 0.80, 'DEF': 0.55, 'DM': 0.45, 'MID': 0.45, 'FWD': 0.35,
            }.get(pg, 0.35)
            rating -= assists * per_assist

        # E) Karten
        rating += yellow * 0.30
        rating += red * 1.50

        # F) Positionslogik
        if pg == 'GK':
            rating += opp_goals * 0.40
            if opp_goals == 0:
                rating -= 0.50
            if opp_xg >= 2.0 and opp_goals <= 1:
                rating -= 0.30   # Stark gehalten trotz Druck
            if opp_xg <= 0.8 and opp_goals >= 2:
                rating += 0.50   # Vermeidbare Gegentore

        elif pg == 'DEF':
            rating += opp_goals * 0.20
            if opp_goals == 0:
                rating -= 0.30
            if my_win:
                rating -= 0.10
            if opp_bp > 3:
                rating += 0.20   # Pressing oft umgangen

        elif pg == 'DM':
            rating += opp_goals * 0.08
            if opp_goals == 0:
                rating -= 0.15
            if xg_diff >= 0.5:
                rating -= 0.15
            elif xg_diff <= -0.5:
                rating += 0.15
            if my_pw > 3:
                rating -= 0.15   # Pressing-Gewinner

        elif pg == 'MID':
            if xg_diff >= 0.5:
                rating -= 0.20
            elif xg_diff <= -0.5:
                rating += 0.20
            if my_pw > 3:
                rating -= 0.15
            if my_poss >= 58 and not opp_win:
                rating -= 0.10   # Ballbesitz-Dominanz ohne Niederlage

        elif pg == 'FWD':
            if my_goals >= 3:
                rating -= 0.20
            elif my_goals == 2:
                rating -= 0.10
            elif my_goals == 0:
                rating += 0.25
            if goals == 0 and assists == 0:
                if my_xg >= 2.0:
                    rating += 0.30   # Kein Scorer trotz hoher Team-xG
                elif my_xg >= 1.5:
                    rating += 0.20

        # G) Einsatzminuten (kurze Einsatzzeit → Note zum Neutral-Wert ziehen)
        mp = p.get('minutes_played', 90)
        if mp < 15:
            rating = 3.5 + (rating - 3.5) * 0.20
        elif mp < 30:
            rating = 3.5 + (rating - 3.5) * 0.50
        elif mp < 45:
            rating = 3.5 + (rating - 3.5) * 0.75

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


# ── Einwechs­lungs-Events ──────────────────────────────────────────────────────

def _score_at_minute(minute: int, goal_events: list, side: str) -> tuple[int, int]:
    """Gibt (eigene, gegnerische) Tore bis einschließlich 'minute' zurück."""
    h, a = 0, 0
    for evt in (goal_events or []):
        if evt.get('minute', 999) <= minute:
            if evt.get('team') == 'home':
                h += 1
            else:
                a += 1
    return (h, a) if side == 'home' else (a, h)


def _sub_condition_met(condition: str, minute: int,
                       goal_events: list, side: str) -> bool:
    """Prüft ob eine Wechselbedingung zum Zeitpunkt 'minute' erfüllt ist."""
    if condition == 'immer':
        return True
    mine, theirs = _score_at_minute(minute, goal_events, side)
    if condition == 'fuehrung':
        return mine > theirs
    if condition == 'rueckstand':
        return mine < theirs
    if condition == 'unentschieden':
        return mine == theirs
    return True


def _generate_substitution_events(tactic_setup, team_dict: dict,
                                   side: str = 'home',
                                   goal_events: list | None = None) -> list[dict]:
    """Gibt Einwechslungs-Events für den Spielbericht zurück.

    Priorität:
      1. Geplante Wechsel aus dem Taktik-Setup (Minuten vom Trainer konfiguriert).
      2. Falls keine geplanten Wechsel: automatisch 2–3 positionspassende Wechsel
         (att→att, mid→mid, def→def) aus Bankspieler-IDs + Nicht-TW-Startern.

    Rückgabe: [{in: pid, out: pid, minute: int}, …]  — nach Minute aufsteigend.
    Namen werden später in _build_sub_name_lookup per DB nachgeschlagen.
    """
    planned = [s for s in (tactic_setup.substitutions or [])
               if s.get('in') and s.get('out') and s.get('minute')]
    if planned:
        result = []
        for s in sorted(planned, key=lambda s: s['minute']):
            cond = s.get('condition', 'immer')
            if _sub_condition_met(cond, s['minute'], goal_events, side):
                result.append(s)
        return result

    from .models import Player as _Player

    # ── Auswechselbare Starter nach Priorität sortieren ───────────────────────
    # Auswechsel-Reihenfolge: attack → offensive_midfield → midfield → defense
    # 'goalkeeper' wird nie ausgewechselt.
    _GROUP_ORDER = {
        'attack':             0,
        'offensive_midfield': 1,
        'midfield':           2,
        'defense':            3,
    }
    lineup = team_dict.get('lineup', [])
    subable = sorted(
        [s for s in lineup if s.get('group') in _GROUP_ORDER and s.get('player_id')],
        key=lambda s: _GROUP_ORDER[s['group']],
    )
    if not subable:
        return []

    # ── Bank-Spieler ermitteln ─────────────────────────────────────────────────
    bench_ids = list(tactic_setup.bench or [])
    lineup_pids = {s['player_id'] for s in lineup if s.get('player_id')}

    if not bench_ids:
        bench_ids = list(
            _Player.objects.filter(club=tactic_setup.club)
            .exclude(pk__in=lineup_pids)
            .order_by('-strength_profile__final_strength')
            .values_list('pk', flat=True)[:8]
        )
    if not bench_ids:
        return []

    # Positionen laden: main_position_1/2/3 (HP) + secondary_position_1/2/3 (NP)
    # TW niemals einwechseln
    bench_pool = []
    for row in (
        _Player.objects.filter(pk__in=bench_ids)
        .exclude(primary_position='TW')
        .values('pk',
                'main_position_1', 'main_position_2', 'main_position_3',
                'secondary_position_1', 'secondary_position_2', 'secondary_position_3')
    ):
        hp = [p for p in (row['main_position_1'], row['main_position_2'], row['main_position_3']) if p]
        np = [p for p in (row['secondary_position_1'], row['secondary_position_2'], row['secondary_position_3']) if p]
        bench_pool.append({'pk': row['pk'], 'hp': hp, 'np': np})

    # ── HP → NP → Positionsfremd matching ─────────────────────────────────────
    n_subs = random.choice([2, 2, 3])
    pairs:      list[tuple[int, int]] = []
    used_bench: set[int] = set()
    used_out:   set[int] = set()

    # Positions-Linien für die linienverwandte Zwischenstufe
    _LINE_POS = {
        'attack':             {'ST', 'LF', 'RF', 'MS', 'OM'},
        'offensive_midfield': {'OM', 'ZM', 'LA', 'RA', 'LF', 'RF'},
        'midfield':           {'ZM', 'DM', 'LA', 'RA', 'LM', 'RM', 'OM'},
        'defense':            {'IV', 'LV', 'RV'},
    }

    for slot in subable:
        if len(pairs) >= n_subs:
            break
        out_pid   = slot['player_id']
        slot_pos  = slot.get('position', '')    # z.B. 'ST', 'LF', 'ZM', 'IV'
        slot_grp  = slot.get('group', '')
        slot_line = _LINE_POS.get(slot_grp, set())
        if out_pid in used_out:
            continue

        chosen: int | None = None

        # 1. HP — exakte Hauptposition stimmt überein
        for bp in bench_pool:
            if bp['pk'] in used_bench:
                continue
            if slot_pos in bp['hp']:
                chosen = bp['pk']
                break

        # 2. NP — exakte Nebenposition stimmt überein
        if chosen is None:
            for bp in bench_pool:
                if bp['pk'] in used_bench:
                    continue
                if slot_pos in bp['np']:
                    chosen = bp['pk']
                    break

        # 2.5 Linienverwandt — HP des Bankspielers liegt in derselben Linie
        #     (z.B. RF für LF-Slot, DM für ZM-Slot)
        if chosen is None:
            for bp in bench_pool:
                if bp['pk'] in used_bench:
                    continue
                if any(p in slot_line for p in bp['hp']):
                    chosen = bp['pk']
                    break

        # 3. Positionsfremd — letzter Ausweg, erster verfügbarer Bankspieler
        if chosen is None:
            for bp in bench_pool:
                if bp['pk'] not in used_bench:
                    chosen = bp['pk']
                    break

        if chosen is None:
            continue
        pairs.append((chosen, out_pid))
        used_bench.add(chosen)
        used_out.add(out_pid)

    if not pairs:
        return []

    # ── Typische Wechselminuten zuweisen ──────────────────────────────────────
    minute_pool = [45, 56, 57, 58, 60, 62, 63, 65, 68, 70, 72, 75, 78, 80, 82, 84]
    minutes = sorted(random.sample(minute_pool, min(len(pairs), len(minute_pool))))

    return [{'in': in_pid, 'out': out_pid, 'minute': minute}
            for (in_pid, out_pid), minute in zip(pairs, minutes)]


# ── Öffentliche API ───────────────────────────────────────────────────────────

def simulate_match(
    home_club,
    away_club,
    home_strength_malus: float = 1.0,
    away_strength_malus: float = 1.0,
) -> dict:
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

    home_strength_malus / away_strength_malus:
        Stärke-Multiplikator für Nichtaufstellung (0.70 = 30 % Abzug).
        Wird von prepare_matchday_lineups gesetzt und vom Spieltags-Hook übergeben.
    """
    # 1. Aufstellungen sicherstellen
    # Trainerlose Vereine: optimal auto-auffüllen via ensure_default_tactic.
    # Gemanagte Vereine: bestehende Aufstellung verwenden (Trainer ist verantwortlich).
    from .models import TacticSetup as _TacticSetup

    if home_club.managed_by_id is None:
        home_tactic, _ = ensure_default_tactic(home_club)
    else:
        home_tactic, _ = _TacticSetup.objects.get_or_create(
            club=home_club,
            squad_scope=SQUAD_PRO,
            defaults={'formation': default_formation(), 'lineup': {}, 'bench': []},
        )

    if away_club.managed_by_id is None:
        away_tactic, _ = ensure_default_tactic(away_club)
    else:
        away_tactic, _ = _TacticSetup.objects.get_or_create(
            club=away_club,
            squad_scope=SQUAD_PRO,
            defaults={'formation': default_formation(), 'lineup': {}, 'bench': []},
        )

    # 2. Pre-compute Matchstärken: random(basis, potential) + form — einmal pro Spieler,
    #    konsistent für Simulation UND Spielbericht-Display.
    #    Bankspieler werden einbezogen, damit ActiveLineupState Stärken ohne DB-Hit hat.
    from .models import Player as _Player

    _lineup_pids: set[int] = {
        pid
        for tactic in (home_tactic, away_tactic)
        for pid in (tactic.lineup or {}).values()
        if pid
    }
    _bench_pids: set[int] = {
        pid
        for tactic in (home_tactic, away_tactic)
        for pid in (getattr(tactic, 'bench', None) or [])
        if pid
    }
    _all_pids = list(_lineup_pids | _bench_pids)

    _players_qs = (
        _Player.objects
        .filter(pk__in=_all_pids)
        .select_related('strength_profile')
        .prefetch_related('source_ratings')
    )
    _all_players_by_id: dict[int, _Player] = {p.pk: p for p in _players_qs}
    match_strengths: dict[int, float] = {
        pk: _draw_match_strength(p) for pk, p in _all_players_by_id.items()
    }

    # 3. ORM → Team-Dicts (mit vorberechneten Matchstärken und optionalem Nichtaufstellungs-Malus)
    home_team = _build_team_dict(home_club, home_tactic, match_strengths=match_strengths, strength_malus=home_strength_malus)
    away_team = _build_team_dict(away_club, away_tactic, match_strengths=match_strengths, strength_malus=away_strength_malus)

    # 3b. Bankspieler-Daten für ActiveLineupState (kein ORM im Simulation-Loop)
    def _make_bench_data(tactic) -> dict[int, dict]:
        result: dict[int, dict] = {}
        for pid in (getattr(tactic, 'bench', None) or []):
            p = _all_players_by_id.get(pid)
            if not p:
                continue
            try:
                fresh = int(round(float(p.strength_profile.freshness or 100.0)))
            except Exception:
                fresh = 100
            result[pid] = {
                'id':                  p.pk,
                'name':               f'{p.first_name} {p.last_name}'.strip() or str(p),
                'final_strength':      match_strengths.get(pid, 50.0),
                'main_positions':      list(getattr(p, 'main_positions', []) or []),
                'secondary_positions': list(getattr(p, 'secondary_positions', []) or []),
                'teamwork':            _teamwork(p),
                'freshness':           fresh,
                'is_ws_injured':       bool(getattr(p, 'ws_injury_days_remaining', 0) or 0),
            }
        return result

    home_team['bench_player_data']     = _make_bench_data(home_tactic)
    home_team['planned_substitutions'] = list(getattr(home_tactic, 'substitutions', None) or [])
    away_team['bench_player_data']     = _make_bench_data(away_tactic)
    away_team['planned_substitutions'] = list(getattr(away_tactic, 'substitutions', None) or [])

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

    # 5d. Einsatzminuten + Zeitfenster aus Wechsel-Events; Eingewechselte als Spieler-Rows
    h_sub_evts = sim.get('h_sim_sub_events', [])
    a_sub_evts = sim.get('a_sim_sub_events', [])
    h_mmap  = _build_minutes_played_map(h_sub_evts)
    a_mmap  = _build_minutes_played_map(a_sub_evts)
    h_wmap  = _build_windows_map(h_sub_evts)   # {pid: (on_minute, off_minute)}
    a_wmap  = _build_windows_map(a_sub_evts)

    def _patch_window(p, mmap, wmap):
        pid = p.get('id')
        p['minutes_played'] = mmap.get(pid, 90)
        if pid in wmap:
            p['on_minute'],  p['off_minute'] = wmap[pid]
        else:
            p['on_minute'],  p['off_minute'] = 0, 90

    for p in h_players:
        _patch_window(p, h_mmap, h_wmap)
    for p in a_players:
        _patch_window(p, a_mmap, a_wmap)

    existing_h_pids = {p['id'] for p in h_players}
    existing_a_pids = {p['id'] for p in a_players}
    for evt in h_sub_evts:
        in_pid = evt.get('in')
        if not in_pid or in_pid in existing_h_pids:
            continue
        p_orm = _all_players_by_id.get(in_pid)
        if not p_orm:
            continue
        sc = evt.get('target_slot', 'ZM')
        row = _player_row(
            {'slot': {'code': sc, 'group': _slot_to_group(sc), 'key': sc}, 'player': p_orm},
            goals=h_goals_map.get(in_pid, {}).get('goals', 0),
            assists=h_goals_map.get(in_pid, {}).get('assists', 0),
            match_strength=match_strengths.get(in_pid),
        )
        row['minutes_played'] = h_mmap.get(in_pid, 0)
        row['is_sub']         = True
        if in_pid in h_wmap:
            row['on_minute'], row['off_minute'] = h_wmap[in_pid]
        h_players.append(row)
        existing_h_pids.add(in_pid)
    for evt in a_sub_evts:
        in_pid = evt.get('in')
        if not in_pid or in_pid in existing_a_pids:
            continue
        p_orm = _all_players_by_id.get(in_pid)
        if not p_orm:
            continue
        sc = evt.get('target_slot', 'ZM')
        row = _player_row(
            {'slot': {'code': sc, 'group': _slot_to_group(sc), 'key': sc}, 'player': p_orm},
            goals=a_goals_map.get(in_pid, {}).get('goals', 0),
            assists=a_goals_map.get(in_pid, {}).get('assists', 0),
            match_strength=match_strengths.get(in_pid),
        )
        row['minutes_played'] = a_mmap.get(in_pid, 0)
        row['is_sub']         = True
        if in_pid in a_wmap:
            row['on_minute'], row['off_minute'] = a_wmap[in_pid]
        a_players.append(row)
        existing_a_pids.add(in_pid)

    # 5. Formations-Label
    def _fmt(tactic) -> str:
        f = tactic.formation or {}
        try:
            return formation_code(f)
        except Exception:
            return '?'

    # 5b. Karten-Flags (0/1) in Spieler-Rows einbetten — persistent im Report
    ms_stats = sim.get('match_stats', {}) or {}
    # T009: Verwiesene Spieler aus Sim-Dismissals vormarkieren; restliche Roten
    # zufällig vergeben (damit kein Spieler doppelt als Rot erscheint).
    sim_dismissals = sim.get('dismissal_events', [])
    h_dismissal_pids = {e['player_id'] for e in sim_dismissals if e.get('club_side') == 'home'}
    a_dismissal_pids = {e['player_id'] for e in sim_dismissals if e.get('club_side') == 'away'}
    for p in h_players:
        if p.get('id') in h_dismissal_pids:
            p['red_cards'] = 1
    for p in a_players:
        if p.get('id') in a_dismissal_pids:
            p['red_cards'] = 1
    h_red_remaining = max(0, (ms_stats.get('home_red', 0) or 0) - len(h_dismissal_pids))
    a_red_remaining = max(0, (ms_stats.get('away_red', 0) or 0) - len(a_dismissal_pids))
    h_players, h_card_events = _assign_cards_to_players(
        h_players,
        ms_stats.get('home_yellow', 0) or 0,
        h_red_remaining,
        club_side='home',
    )
    a_players, a_card_events = _assign_cards_to_players(
        a_players,
        ms_stats.get('away_yellow', 0) or 0,
        a_red_remaining,
        club_side='away',
    )

    # 5c. Verletzungs-Events (post-match Effekt, beeinflusst Spielausgang NICHT)
    from .freshness_service import MEDIZIN_INJURY_FACTOR, _stadium_level
    home_medizin = _stadium_level(home_club, 'medizin_level')
    away_medizin = _stadium_level(away_club, 'medizin_level')
    h_injury_events = _generate_injury_events(
        h_players,
        club_side='home',
        medizin_factor=MEDIZIN_INJURY_FACTOR.get(home_medizin, 1.0),
    )
    a_injury_events = _generate_injury_events(
        a_players,
        club_side='away',
        medizin_factor=MEDIZIN_INJURY_FACTOR.get(away_medizin, 1.0),
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
        # Wechsel-Quellen-Priorirät:
        #   1. Taktik hat geplante Wechsel → immer sim-Events (auch wenn leer, weil
        #      alle Bedingungen verworfen wurden — kein Phantom-Fallback)
        #   2. Keine geplanten Wechsel, aber sim liefert Ereignisse (Verletzungswechsel)
        #      → sim-Events
        #   3. Keine sim-Events und keine geplanten Wechsel → Fallback-Generator
        'home_substitutions': (
            sim['h_sim_sub_events']
            if getattr(home_tactic, 'substitutions', None) or sim['h_sim_sub_events']
            else _generate_substitution_events(home_tactic, home_team, 'home', sim.get('goal_events', []))
        ),
        'away_substitutions': (
            sim['a_sim_sub_events']
            if getattr(away_tactic, 'substitutions', None) or sim['a_sim_sub_events']
            else _generate_substitution_events(away_tactic, away_team, 'away', sim.get('goal_events', []))
        ),
        'card_events':           h_card_events + a_card_events,
        'dismissal_events':      sim_dismissals,
        'injury_events':         h_injury_events + a_injury_events,
        'home_fatigue_cost':     sim.get('home_fatigue_cost', 1.0),
        'away_fatigue_cost':     sim.get('away_fatigue_cost', 1.0),
    }

    # 6. Spielernoten berechnen und in den Report einbetten
    ratings = compute_player_ratings(result)
    result['home_ratings']     = ratings['home_ratings']
    result['away_ratings']     = ratings['away_ratings']
    result['man_of_the_match'] = ratings['man_of_the_match']
    return result
