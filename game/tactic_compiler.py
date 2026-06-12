"""
tactic_compiler.py — Django-freier Taktik-Compiler für Websoccer
=================================================================
Komplett standalone (nur Python-Standardbibliothek).
Kein Django, kein ORM, keine Datenbank.

Hauptfunktionen:
    compile_tactic(team, tactic, half) -> dict
    calculate_zone_strengths(team) -> dict
    select_active_condition_plan(tactic, minute, home_goals, away_goals, ...) -> str | None
"""
from __future__ import annotations

from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# Konstanten
# ══════════════════════════════════════════════════════════════════════════════

ATTACK_FOCUS_ZONES: dict[str, dict] = {
    "ausgewogen":       {"left": 33, "center": 34, "right": 33},
    "ueber_links":      {"left": 50, "center": 32, "right": 18},
    "ueber_rechts":     {"left": 18, "center": 32, "right": 50},
    "durch_mitte":      {"left": 22, "center": 56, "right": 22},
    "fluegelspiel":     {"left": 42, "center": 16, "right": 42},
    "ueber_halbraeume": {"left": 28, "center": 44, "right": 28},
    "flanke_kopfball":  {"left": 43, "center": 14, "right": 43},
}

PRESSING_LEVEL_VALUES: dict[str, float] = {
    "passiv":   0.00,
    "normal":   0.35,
    "intensiv": 0.65,
    "hoch":     0.85,
}

PRESSING_TRIGGER_COSTS: dict[str, int] = {
    "ballverlust":    2,
    "langer_ball":    1,
    "schlechter_pass": 1,
    "torwart_druck":  1,
}
PRESSING_TRIGGER_BUDGET = 3

# Matchplan-Modifikatoren: additive Deltas auf State-Felder
CONDITION_PLAN_MODIFIERS: dict[str, dict] = {
    "ausgewogen": {
        "_neutral_pull": 0.3,
    },

    "aggressiv_risiko": {
        "orientation": +18.0,
        "tempo": +12.0,
        "pressing_index": +0.13,
        "pressing_ball_win_bonus": +0.03,
        "pressing_bypassed_risk": +0.04,
        "shot_volume_delta": +0.16,
        "risk": +0.16,
        "fatigue_delta": +0.12,
        "xg_for_delta": +0.08,
        "xg_against_delta": +0.05,
        "foul_delta": +0.05,
        "card_delta": +0.04,
    },

    "schlussangriff": {
        "orientation": +35.0,
        "tempo": +25.0,
        "pressing_index": +0.12,
        "pressing_ball_win_bonus": +0.03,
        "pressing_bypassed_risk": +0.08,
        "shot_volume_delta": +0.35,
        "directness": +0.25,
        "risk": +0.32,
        "fatigue_delta": +0.22,
        "xg_for_delta": +0.18,
        "xg_against_delta": +0.18,
        "attack_delta": +0.08,
        "defense_delta": -0.08,
        "foul_delta": +0.05,
        "card_delta": +0.04,
    },

    "kontrolle_ballbesitz": {
        "possession_bonus": +0.12,
        "build_control": +0.10,
        "tempo": -10.0,
        "risk": -0.10,
        "shot_volume_delta": -0.06,
    },

    "kompakt_sichern": {
        "defense_delta": +0.05,
        "attack_delta": -0.05,
        "pressing_index": -0.05,
        "tempo": -10.0,
        "risk": -0.10,
        "shot_volume_delta": -0.08,
    },

    "zeitspiel": {
        "possession_bonus": +0.18,
        "build_control": +0.15,
        "tempo": -25.0,
        "shot_volume_delta": -0.14,
        "pressing_index": -0.10,
        "risk": -0.16,
        "fatigue_delta": -0.04,
        "xg_for_delta": -0.06,
        "xg_against_delta": -0.08,
        "foul_delta": -0.02,
        "card_delta": -0.01,
    },

    "unterzahl_kompakt": {
        "defense_delta": +0.08,
        "attack_delta": -0.08,
        "pressing_index": -0.10,
        "tempo": -10.0,
        "shot_volume_delta": -0.12,
        "possession_bonus": +0.04,
    },
}

# Zone-Gewichte: Angriff je Position (links / mitte / rechts)
_ZONE_ATK: dict[str, dict[str, float]] = {
    "TW":  {"left": 0.00, "center": 0.00, "right": 0.00},
    "LV":  {"left": 0.15, "center": 0.05, "right": 0.00},
    "IV":  {"left": 0.10, "center": 0.40, "right": 0.10},
    "RV":  {"left": 0.00, "center": 0.05, "right": 0.15},
    "LOV": {"left": 0.25, "center": 0.05, "right": 0.00},
    "ROV": {"left": 0.00, "center": 0.05, "right": 0.25},
    "DM":  {"left": 0.10, "center": 0.50, "right": 0.10},
    "LM":  {"left": 0.70, "center": 0.15, "right": 0.05},
    "ZM":  {"left": 0.20, "center": 0.50, "right": 0.20},
    "RM":  {"left": 0.05, "center": 0.15, "right": 0.70},
    "LOM": {"left": 0.75, "center": 0.15, "right": 0.05},
    "OM":  {"left": 0.20, "center": 0.55, "right": 0.20},
    "ROM": {"left": 0.05, "center": 0.15, "right": 0.75},
    "LF":  {"left": 0.80, "center": 0.15, "right": 0.05},
    "ST":  {"left": 0.20, "center": 0.60, "right": 0.20},
    "RF":  {"left": 0.05, "center": 0.15, "right": 0.80},
}

# Zone-Gewichte: Verteidigung je Position
_ZONE_DEF: dict[str, dict[str, float]] = {
    "TW":  {"left": 0.10, "center": 0.80, "right": 0.10},
    "LV":  {"left": 0.80, "center": 0.10, "right": 0.05},
    "IV":  {"left": 0.20, "center": 0.60, "right": 0.20},
    "RV":  {"left": 0.05, "center": 0.10, "right": 0.80},
    "LOV": {"left": 0.80, "center": 0.10, "right": 0.05},
    "ROV": {"left": 0.05, "center": 0.10, "right": 0.80},
    "DM":  {"left": 0.20, "center": 0.60, "right": 0.20},
    "LM":  {"left": 0.50, "center": 0.30, "right": 0.10},
    "ZM":  {"left": 0.20, "center": 0.50, "right": 0.20},
    "RM":  {"left": 0.10, "center": 0.30, "right": 0.50},
    "LOM": {"left": 0.35, "center": 0.35, "right": 0.15},
    "OM":  {"left": 0.10, "center": 0.60, "right": 0.10},
    "ROM": {"left": 0.15, "center": 0.35, "right": 0.35},
    "LF":  {"left": 0.30, "center": 0.20, "right": 0.05},
    "ST":  {"left": 0.10, "center": 0.50, "right": 0.10},
    "RF":  {"left": 0.05, "center": 0.20, "right": 0.30},
}


# ══════════════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe(d: dict, *keys, default=None):
    """Tiefes dict.get mit Fallback."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
        if cur is None:
            return default
    return cur


# ══════════════════════════════════════════════════════════════════════════════
# Zone-Stärken
# ══════════════════════════════════════════════════════════════════════════════

def calculate_zone_strengths(team: dict) -> dict:
    """Berechnet Angriffs- und Defensivstärken je Zone aus dem Team-Dict.

    Returns:
        {
            "attack":  {"left": float, "center": float, "right": float},
            "defense": {"left": float, "center": float, "right": float},
        }
    Werte entsprechen gewichteten Spielerstärken (~100–200er Skala).
    Bei gleichen Teams sind Angriff- und Defensivwerte symmetrisch.
    """
    pid_map = {p["id"]: p for p in team.get("players", [])}
    atk = {"left": 0.0, "center": 0.0, "right": 0.0}
    dfn = {"left": 0.0, "center": 0.0, "right": 0.0}

    for slot in team.get("lineup", []):
        pid = slot.get("player_id")
        if not pid:
            continue
        p = pid_map.get(pid)
        if not p:
            continue
        pos   = slot.get("position", "ST")
        str_  = float(p.get("final_strength", 50.0))
        aw    = _ZONE_ATK.get(pos, {"left": 0.33, "center": 0.34, "right": 0.33})
        dw    = _ZONE_DEF.get(pos, {"left": 0.33, "center": 0.34, "right": 0.33})
        for z in ("left", "center", "right"):
            atk[z] += str_ * aw[z]
            dfn[z] += str_ * dw[z]

    return {"attack": atk, "defense": dfn}


# ══════════════════════════════════════════════════════════════════════════════
# Bedingungen / Matchpläne
# ══════════════════════════════════════════════════════════════════════════════

def select_active_condition_plan(
    tactic:     dict,
    minute:     int,
    home_goals: int,
    away_goals: int,
    is_home:    bool,
    own_red:    int = 0,
    opp_red:    int = 0,
) -> Optional[str]:
    """Gibt den Plan-Key der ersten passenden aktiven Bedingung zurück.

    Bedingungen gelten ab Minute X (nicht nur in Minute X).
    Erste passende gewinnt.
    Gibt None zurück, wenn keine Bedingung zutrifft.
    """
    own_goals = home_goals if is_home else away_goals
    opp_goals = away_goals if is_home else home_goals
    diff = own_goals - opp_goals

    def _matches(condition: str) -> bool:
        if condition == "rueckstand":
            return diff < 0
        if condition == "rueckstand_2":
            return diff <= -2
        if condition == "unentschieden":
            return diff == 0
        if condition == "fuehrung":
            return diff > 0
        if condition == "knappe_fuehrung":
            return diff == 1
        if condition == "eigene_rot":
            return own_red > 0
        if condition == "gegner_rot":
            return opp_red > 0
        return False

    conditions = tactic.get("conditions", [])
    for cond in conditions:
        if not cond.get("active", False):
            continue
        try:
            cond_minute = int(str(cond.get("minute", "999")))
        except (ValueError, TypeError):
            continue
        if minute < cond_minute:
            continue
        if _matches(cond.get("condition", "")):
            return cond.get("plan")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Taktik-Compiler
# ══════════════════════════════════════════════════════════════════════════════

def compile_tactic(
    team:    dict,
    tactic:  Optional[dict] = None,
    half:    str = "full",
) -> dict:
    """Kompiliert Taktik + Team in ein Profil mit Spiel-Multiplikatoren.

    Args:
        team:    Team-Dict (Format: bayern_fixture.json)
        tactic:  Optional — überschreibt team['tactic']
        half:    "first" | "second" | "full"

    Returns:
        dict mit orientation, tempo, zone_weights, line_multipliers,
        xg_for, xg_against, possession_bonus, shot_volume, shot_quality,
        foul_multiplier, card_multiplier, fatigue_cost, pressing_index,
        pressing_ball_win_bonus, pressing_bypassed_risk, directness, risk,
        width, build_control, teamwork_avg, teamwork_factor, complexity,
        coherence, debug
    """
    t = tactic if tactic is not None else team.get("tactic", {})
    if not isinstance(t, dict):
        t = {}

    # ── Halbzeit-Kontext ──────────────────────────────────────────────────────
    fh = t.get("first_half") or {}
    sh = t.get("second_half") or {}

    def _half_val(key: str, default):
        if half == "first":
            return fh.get(key, default)
        if half == "second":
            return sh.get(key, default)
        # full = Durchschnitt
        fv = fh.get(key, default)
        sv = sh.get(key, default)
        if isinstance(fv, (int, float)) and isinstance(sv, (int, float)):
            return (fv + sv) / 2
        return fv if fv == sv else default

    # ── Arbeitszustand (additive Deltas) ──────────────────────────────────────
    s: dict = {
        "orientation":       float(_half_val("orientation", 50)),
        "tempo":             50.0,
        "defense_delta":     0.0,
        "midfield_delta":    0.0,
        "attack_delta":      0.0,
        "xg_for_delta":      0.0,
        "xg_against_delta":  0.0,
        "possession_bonus":  0.0,
        "shot_volume_delta": 0.0,
        "shot_quality_delta":0.0,
        "foul_delta":        0.0,
        "card_delta":        0.0,
        "fatigue_delta":     0.0,
        "pressing_index":    0.35,
        "pressing_ball_win_bonus": 0.0,
        "pressing_bypassed_risk":  0.0,
        "directness":        0.0,
        "risk":              0.0,
        "width":             0.0,
        "build_control":     0.0,
        "coherence":         1.0,
        "complexity":        0.0,
    }
    dbg: dict = {}

    # ── 1. Angriffsfokus → Zone-Weights ──────────────────────────────────────
    attack_focus = t.get("attack_focus", "ausgewogen") or "ausgewogen"
    raw_zones = ATTACK_FOCUS_ZONES.get(attack_focus, ATTACK_FOCUS_ZONES["ausgewogen"])
    total_z   = sum(raw_zones.values()) or 100
    zone_weights = {k: v / total_z for k, v in raw_zones.items()}
    dbg["attack_focus"] = attack_focus

    # ── 2. Pressing ──────────────────────────────────────────────────────────
    pressing = t.get("pressing") or {}
    if not isinstance(pressing, dict):
        pressing = {}

    p_def = PRESSING_LEVEL_VALUES.get(pressing.get("defense", "normal"), 0.35)
    p_mid = PRESSING_LEVEL_VALUES.get(pressing.get("midfield", "normal"), 0.35)
    p_atk = PRESSING_LEVEL_VALUES.get(pressing.get("attack", "normal"), 0.35)

    pi = p_def * 0.30 + p_mid * 0.40 + p_atk * 0.30
    s["pressing_index"] = pi
    s["pressing_ball_win_bonus"] += pi * 0.12
    s["pressing_bypassed_risk"]  += pi * 0.08
    s["foul_delta"]    += pi * 0.20
    s["card_delta"]    += pi * 0.15
    s["fatigue_delta"] += pi * 0.10
    s["shot_volume_delta"] += pi * 0.04
    s["xg_for_delta"]      += pi * 0.03
    s["xg_against_delta"]  -= pi * 0.04  # schwerer gegen dieses Team zu spielen

    # Pressing-Komplexität
    any_non_normal = any(v not in ("normal",) for v in [pressing.get("defense", "normal"),
                                                         pressing.get("midfield", "normal"),
                                                         pressing.get("attack", "normal")])
    if any_non_normal:
        s["complexity"] += 15

    dbg["pressing_index"] = round(pi, 3)

    # ── 3. Pressing-Auslöser (Budget-Check) ──────────────────────────────────
    triggers = t.get("pressing_triggers") or {}
    if not isinstance(triggers, dict):
        triggers = {}

    budget_used = 0
    active_triggers = []
    for key in PRESSING_TRIGGER_COSTS:
        if not triggers.get(key, False):
            continue
        cost = PRESSING_TRIGGER_COSTS[key]
        if budget_used + cost > PRESSING_TRIGGER_BUDGET:
            dbg[f"trigger_{key}_skipped"] = "budget exceeded"
            continue
        budget_used += cost
        active_triggers.append(key)
        s["complexity"] += 10

    for key in active_triggers:
        if key == "ballverlust":
            s["pressing_ball_win_bonus"] += 0.05
            s["pressing_bypassed_risk"]  += 0.04
            s["fatigue_delta"] += 0.05
            s["risk"]          += 0.03
            # Kohärenz-Check: Gegenpressing + passives Pressing
            if pressing.get("defense", "normal") == "passiv":
                s["coherence"] -= 0.03
        elif key == "langer_ball":
            s["pressing_ball_win_bonus"] += 0.02
            s["defense_delta"]  += 0.02
            s["fatigue_delta"]  += 0.01
        elif key == "schlechter_pass":
            s["pressing_ball_win_bonus"] += 0.02
            s["fatigue_delta"]  += 0.01
        elif key == "torwart_druck":
            s["shot_volume_delta"] += 0.02
            s["fatigue_delta"]     += 0.02

    dbg["active_triggers"] = active_triggers

    # ── 4. Halbzeit-Grundausrichtung ──────────────────────────────────────────
    effort = _half_val("effort", "normal")
    if effort == "hoch":
        s["fatigue_delta"] += 0.06
        s["shot_volume_delta"] += 0.03
    elif effort == "niedrig":
        s["fatigue_delta"] -= 0.04

    # ── 5. Orientierung ───────────────────────────────────────────────────────
    orient_delta = (s["orientation"] - 50.0) / 50.0   # -1 … +1
    s["attack_delta"]  += orient_delta * 0.08
    s["defense_delta"] -= orient_delta * 0.06
    s["xg_for_delta"]  += orient_delta * 0.10
    s["xg_against_delta"] += orient_delta * 0.08
    s["shot_volume_delta"] += orient_delta * 0.10
    s["fatigue_delta"]     += orient_delta * 0.08
    s["risk"]              += orient_delta * 0.15

    dbg["orientation"] = s["orientation"]

    # ── 6. Spielaufbau ────────────────────────────────────────────────────────
    buildup = t.get("buildup") or {}
    if not isinstance(buildup, dict):
        buildup = {}

    # Tempo
    raw_tempo = buildup.get("tempo", t.get("tempo", 50))
    try:
        s["tempo"] = float(raw_tempo)
    except (TypeError, ValueError):
        s["tempo"] = 50.0

    td = (s["tempo"] - 50.0) / 50.0  # -1 … +1
    s["shot_volume_delta"] += td * 0.10
    s["directness"]        += td * 0.15
    s["risk"]              += td * 0.08
    s["fatigue_delta"]     += td * 0.12
    # Hohes Tempo erzeugt mehr Aktionen, Risiko und Belastung,
    # aber keinen pauschalen Malus auf Chancenqualität.
    s["possession_bonus"]   -= td * 0.05

    dbg["tempo"] = s["tempo"]

    # buildup.defense
    bd = buildup.get("defense", "standard") or "standard"
    if bd == "aus_abwehr":
        s["build_control"]  += 0.10
        s["possession_bonus"] += 0.05
        s["directness"]     -= 0.05
        s["complexity"]     += 6
    elif bd == "direkt_vorne":
        s["directness"]     += 0.15
        s["shot_volume_delta"] += 0.05
        s["possession_bonus"] -= 0.05
        s["risk"]           += 0.05
        s["complexity"]     += 6
    elif bd == "lange_baelle":
        s["directness"]     += 0.20
        s["risk"]           += 0.03
        s["possession_bonus"] -= 0.08
        s["complexity"]     += 6

    # buildup.defense_height
    bh = buildup.get("defense_height", "standard") or "standard"
    if bh == "tief":
        s["defense_delta"]  += 0.04
        s["pressing_index"] -= 0.05
        s["attack_delta"]   -= 0.03
        s["risk"]           -= 0.04
        s["complexity"]     += 8
    elif bh == "hoeher":
        s["pressing_index"] += 0.05
        s["attack_delta"]   += 0.03
        s["defense_delta"]  -= 0.03
        s["risk"]           += 0.04
        s["pressing_bypassed_risk"] += 0.02
        s["complexity"]     += 8

    # buildup.midfield
    bm = buildup.get("midfield", "standard") or "standard"
    if bm == "geduldig":
        s["possession_bonus"] += 0.08
        s["build_control"]    += 0.08
        s["shot_volume_delta"] -= 0.05
        s["risk"]             -= 0.04
        s["complexity"]       += 8
    elif bm == "vertikal":
        s["directness"]       += 0.12
        s["shot_volume_delta"] += 0.07
        s["risk"]             += 0.05
        s["possession_bonus"] -= 0.05
        s["complexity"]       += 8
    elif bm == "seiten_verlagern":
        s["width"]            += 0.15
        s["possession_bonus"] += 0.03
        s["complexity"]       += 5

    # buildup.attack
    ba = buildup.get("attack", "standard") or "standard"
    if ba == "kombinieren":
        s["shot_quality_delta"] += 0.06
        s["possession_bonus"]   += 0.03
    elif ba == "tiefenlaeufe":
        s["shot_volume_delta"]  += 0.08
        s["xg_for_delta"]       += 0.05
        s["risk"]               += 0.04
        s["complexity"]         += 8
    elif ba == "flanken_suchen":
        s["width"]              += 0.10
        s["shot_quality_delta"] -= 0.04
        dbg["flanken_corner_bonus"] = True
        s["complexity"]         += 8
    elif ba == "zielspieler_suchen":
        s["directness"]         += 0.08
        s["xg_for_delta"]       += 0.04
        s["possession_bonus"]   -= 0.04
        s["complexity"]         += 6
    elif ba == "frueher_abschluss":
        s["shot_volume_delta"]  += 0.15
        s["shot_quality_delta"] -= 0.08
        s["complexity"]         += 8

    # Kohärenz: Direkt/Lange Bälle + geduldig (Widerspruch)
    if bd in ("direkt_vorne", "lange_baelle") and bm == "geduldig":
        s["coherence"] -= 0.02
    # Geduldig + Tempo >= 75
    if bm == "geduldig" and s["tempo"] >= 75:
        s["coherence"] -= 0.03

    # ── 7. Deckung & Zweikampf ────────────────────────────────────────────────
    defending = t.get("defending") or {}
    if not isinstance(defending, dict):
        defending = {}

    deckung   = defending.get("deckung", "hybrid") or "hybrid"
    zweikampf = defending.get("zweikampf", "normal") or "normal"
    breite    = defending.get("breite", "standard") or "standard"
    umschalten = defending.get("umschalten", "ausgewogen") or "ausgewogen"

    if deckung == "raum":
        s["defense_delta"]  += 0.02
        s["coherence"]      += 0.01
        s["complexity"]     += 6
    elif deckung == "mann":
        s["defense_delta"]  += 0.02
        s["foul_delta"]     += 0.04
        s["risk"]           += 0.03
        s["complexity"]     += 6
        # Kohärenz: Manndeckung + eng
        if breite == "eng":
            s["coherence"] -= 0.02

    if zweikampf == "vorsichtig":
        s["foul_delta"]  -= 0.08
        s["card_delta"]  -= 0.06
        s["defense_delta"] -= 0.02
    elif zweikampf == "hart":
        s["defense_delta"] += 0.02
        s["foul_delta"]    += 0.10
        s["card_delta"]    += 0.08
        s["fatigue_delta"] += 0.04
        s["complexity"]    += 6

    if breite == "eng":
        s["defense_delta"] += 0.02
        s["width"]         -= 0.10
        # Kohärenz: Flügelspiel + eng
        if attack_focus in ("fluegelspiel", "flanke_kopfball"):
            s["coherence"] -= 0.03
    elif breite == "breit":
        s["width"]         += 0.10
        s["defense_delta"] -= 0.02
        # Kohärenz: Durch die Mitte + breit
        if attack_focus == "durch_mitte":
            s["coherence"] -= 0.015

    if umschalten == "konter":
        s["directness"]    += 0.08
        s["shot_volume_delta"] += 0.03
        s["possession_bonus"] -= 0.05
        s["risk"]          += 0.03
        s["complexity"]    += 5
    elif umschalten == "ballbesitz":
        s["possession_bonus"] += 0.07
        s["build_control"]    += 0.05
        s["shot_volume_delta"] -= 0.04
        s["risk"]             -= 0.04
        s["complexity"]       += 5

    # Weitere Kohärenz-Checks
    if s["orientation"] < 30 and p_atk >= 0.65:
        s["coherence"] -= 0.04
    if s["orientation"] < 30 and pi > 0.60:
        s["coherence"] -= 0.05
    if s["orientation"] > 70 and bh == "tief":
        s["coherence"] -= 0.03

    # ── 8. Teamwork ───────────────────────────────────────────────────────────
    pid_map = {p["id"]: p for p in team.get("players", [])}
    lineup_ids = [slot.get("player_id") for slot in team.get("lineup", []) if slot.get("player_id")]
    tw_vals = [pid_map[pid].get("teamwork", 50) for pid in lineup_ids if pid in pid_map]
    teamwork_avg = sum(tw_vals) / len(tw_vals) if tw_vals else 65.0

    # Taktik-Komplexität normiert 0–100
    complexity = _clamp(s["complexity"], 0.0, 100.0)
    tw_effect = max(0.0, complexity - 30.0) / 70.0
    teamwork_factor = 1.0 + ((teamwork_avg - 65.0) / 100.0) * 0.06 * tw_effect
    teamwork_factor = _clamp(teamwork_factor, 0.96, 1.04)

    dbg["teamwork_avg"] = round(teamwork_avg, 1)
    dbg["teamwork_factor"] = round(teamwork_factor, 4)
    dbg["complexity"] = round(complexity, 1)

    # ── 9. Kohärenz final clampen ─────────────────────────────────────────────
    coherence = _clamp(s["coherence"], 0.85, 1.05)

    # ── 10. Line-Multiplikatoren ──────────────────────────────────────────────
    line_multipliers = {
        "goalkeeper": 1.0,
        "defense":    _clamp(1.0 + s["defense_delta"],     0.90, 1.10),
        "midfield":   _clamp(1.0 + s["midfield_delta"],    0.90, 1.10),
        "attack":     _clamp(1.0 + s["attack_delta"],      0.90, 1.10),
        "overall":    _clamp(teamwork_factor * coherence,  0.87, 1.10),
    }

    # ── 11. Konditions-Plan (falls übergeben) ─────────────────────────────────
    # Wenn ein aktiver Plan als tactic["_active_plan"] übergeben wird, dessen
    # Modifikatoren anwenden (wird von run_match für Halbzeitsimulation genutzt).
    active_plan = t.get("_active_plan")
    if active_plan and active_plan in CONDITION_PLAN_MODIFIERS:
        mods = CONDITION_PLAN_MODIFIERS[active_plan]
        neutral_pull = mods.get("_neutral_pull", 0.0)
        for k, v in mods.items():
            if k == "_neutral_pull":
                continue
            if k in s:
                if neutral_pull:
                    # neutral_pull: Wert Richtung 0 ziehen (für "ausgewogen")
                    s[k] = s[k] * (1 - neutral_pull)
                else:
                    s[k] += v
        dbg["active_plan"] = active_plan

        # Multiplikatoren nach Plan-Modifikation neu berechnen
        if active_plan != "ausgewogen":
            line_multipliers["defense"] = _clamp(1.0 + s["defense_delta"], 0.88, 1.12)
            line_multipliers["midfield"] = _clamp(1.0 + s["midfield_delta"], 0.88, 1.12)
            line_multipliers["attack"] = _clamp(1.0 + s["attack_delta"], 0.88, 1.12)

    # ── 12. Output zusammenbauen ──────────────────────────────────────────────
    return {
        "orientation":    _clamp(s["orientation"], 0.0, 100.0),
        "tempo":          _clamp(s["tempo"], 0.0, 100.0),
        "zone_weights":   zone_weights,
        "line_multipliers": line_multipliers,

        "xg_for":     _clamp(1.0 + s["xg_for_delta"],     0.80, 1.30),
        "xg_against": _clamp(1.0 + s["xg_against_delta"], 0.80, 1.30),

        "possession_bonus": _clamp(s["possession_bonus"], -0.20, 0.20),
        "shot_volume":      _clamp(1.0 + s["shot_volume_delta"], 0.70, 1.50),
        "shot_quality":     _clamp(1.0 + s["shot_quality_delta"], 0.75, 1.25),

        "foul_multiplier": _clamp(1.0 + s["foul_delta"],  0.70, 1.60),
        "card_multiplier": _clamp(1.0 + s["card_delta"],  0.70, 1.50),
        "fatigue_cost":    _clamp(1.0 + s["fatigue_delta"], 0.80, 1.50),

        "pressing_index":           _clamp(s["pressing_index"], 0.0, 1.0),
        "pressing_ball_win_bonus":  _clamp(s["pressing_ball_win_bonus"], 0.0, 0.30),
        "pressing_bypassed_risk":   _clamp(s["pressing_bypassed_risk"], 0.0, 0.25),

        "directness":   _clamp(s["directness"],   -0.30, 0.30),
        "risk":         _clamp(s["risk"],          -0.30, 0.40),
        "width":        _clamp(s["width"],         -0.20, 0.30),
        "build_control":_clamp(s["build_control"], -0.20, 0.30),

        "teamwork_avg":    round(teamwork_avg, 2),
        "teamwork_factor": round(teamwork_factor, 4),
        "complexity":      round(complexity, 2),
        "coherence":       round(coherence, 4),

        "debug": dbg,
    }
