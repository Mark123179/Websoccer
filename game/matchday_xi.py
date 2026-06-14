"""matchday_xi — Elf des Spieltags

Berechnet on-the-fly die beste Elf für den letzten vollständig abgeschlossenen
Spieltag einer Liga aus den SimulatedMatch-report_data-Einträgen.

Keine persistente Speicherung. Kein Player-ORM-Lookup (außer Club für Wappen).
Integer-Arithmetik für Scoring (Hundertstel-Noten) — deterministisch, float-frei.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Scoring ──────────────────────────────────────────────────────────────────

FIT_PENALTY_SCORE: dict[str, int] = {"exact": 0, "compatible": 15}  # Hundertstel

# ── Anzeige-Labels (deutsch) ─────────────────────────────────────────────────

DISPLAY_ROLE: dict[str, str] = {
    "GK":  "TW",
    "LB":  "LV",
    "LCB": "IV",
    "RCB": "IV",
    "CB":  "IV",
    "RB":  "RV",
    "LCM": "ZM",
    "RCM": "ZM",
    "CDM": "DM",
    "LDM": "DM",
    "RDM": "DM",
    "CM":  "ZM",
    "LM":  "LM",
    "RM":  "RM",
    "LAM": "LOM",
    "RAM": "ROM",
    "CAM": "OM",
    "ST":  "ST",
    "LST": "ST",
    "RST": "ST",
    "LW":  "LF",
    "RW":  "RF",
}

# ── Positionskompatibilität ───────────────────────────────────────────────────

SLOT_COMPATIBILITY: dict[str, dict[str, set[str]]] = {
    "GK":  {"exact": {"TW"},              "compatible": set()},
    "LB":  {"exact": {"LV"},              "compatible": {"LOV", "LM"}},
    "RB":  {"exact": {"RV"},              "compatible": {"ROV", "RM"}},
    "LCB": {"exact": {"IV"},              "compatible": {"LV", "RV"}},
    "RCB": {"exact": {"IV"},              "compatible": {"LV", "RV"}},
    "CB":  {"exact": {"IV"},              "compatible": {"LV", "RV"}},
    "LCM": {"exact": {"ZM"},              "compatible": {"DM", "LM"}},
    "RCM": {"exact": {"ZM"},              "compatible": {"DM", "RM"}},
    "CDM": {"exact": {"DM"},              "compatible": {"ZM"}},
    "LDM": {"exact": {"DM"},              "compatible": {"ZM"}},
    "RDM": {"exact": {"DM"},              "compatible": {"ZM"}},
    "CM":  {"exact": {"ZM"},              "compatible": {"DM", "LM", "RM"}},
    "LM":  {"exact": {"LM"},              "compatible": {"LOM", "LF", "ZM"}},
    "RM":  {"exact": {"RM"},              "compatible": {"ROM", "RF", "ZM"}},
    "LAM": {"exact": {"LOM", "LF"},       "compatible": {"LM", "OM"}},
    "RAM": {"exact": {"ROM", "RF"},       "compatible": {"RM", "OM"}},
    "CAM": {"exact": {"OM"},              "compatible": {"ZM", "LOM", "ROM"}},
    "ST":  {"exact": {"ST"},              "compatible": {"LF", "RF"}},
    "LST": {"exact": {"LF", "ST"},        "compatible": {"LOM", "RF"}},
    "RST": {"exact": {"RF", "ST"},        "compatible": {"ROM", "LF"}},
    "LW":  {"exact": {"LF", "LOM"},       "compatible": {"LM", "ST"}},
    "RW":  {"exact": {"RF", "ROM"},       "compatible": {"RM", "ST"}},
}

# ── Formations-Katalog ────────────────────────────────────────────────────────

FORMATION_PRIORITY: list[str] = [
    "4-4-2", "4-2-3-1", "4-3-3", "3-5-2", "5-3-2", "4-5-1", "3-4-3",
]

# Zentrale/defensive Mittelfeld-Slots (für Constraint-Prüfung)
_CENTRAL_MID_SLOTS: frozenset[str] = frozenset({"LCM", "RCM", "CDM", "LDM", "RDM", "CM"})

FORMATION_SLOTS: dict[str, list[dict]] = {
    "4-4-2": [
        {"slot_id": "GK",  "line": "gk",  "x": 50, "y": 88},
        {"slot_id": "LB",  "line": "def", "x": 15, "y": 70},
        {"slot_id": "LCB", "line": "def", "x": 36, "y": 74},
        {"slot_id": "RCB", "line": "def", "x": 64, "y": 74},
        {"slot_id": "RB",  "line": "def", "x": 85, "y": 70},
        {"slot_id": "LM",  "line": "mid", "x": 12, "y": 50},
        {"slot_id": "LCM", "line": "mid", "x": 35, "y": 54},
        {"slot_id": "RCM", "line": "mid", "x": 65, "y": 54},
        {"slot_id": "RM",  "line": "mid", "x": 88, "y": 50},
        {"slot_id": "LST", "line": "att", "x": 36, "y": 22},
        {"slot_id": "RST", "line": "att", "x": 64, "y": 22},
    ],
    "4-2-3-1": [
        {"slot_id": "GK",  "line": "gk",  "x": 50, "y": 88},
        {"slot_id": "LB",  "line": "def", "x": 15, "y": 70},
        {"slot_id": "LCB", "line": "def", "x": 36, "y": 74},
        {"slot_id": "RCB", "line": "def", "x": 64, "y": 74},
        {"slot_id": "RB",  "line": "def", "x": 85, "y": 70},
        {"slot_id": "LDM", "line": "dm",  "x": 36, "y": 54},
        {"slot_id": "RDM", "line": "dm",  "x": 64, "y": 54},
        {"slot_id": "LAM", "line": "am",  "x": 18, "y": 36},
        {"slot_id": "CAM", "line": "am",  "x": 50, "y": 32},
        {"slot_id": "RAM", "line": "am",  "x": 82, "y": 36},
        {"slot_id": "ST",  "line": "att", "x": 50, "y": 16},
    ],
    "4-3-3": [
        {"slot_id": "GK",  "line": "gk",  "x": 50, "y": 88},
        {"slot_id": "LB",  "line": "def", "x": 15, "y": 70},
        {"slot_id": "LCB", "line": "def", "x": 36, "y": 74},
        {"slot_id": "RCB", "line": "def", "x": 64, "y": 74},
        {"slot_id": "RB",  "line": "def", "x": 85, "y": 70},
        {"slot_id": "LCM", "line": "mid", "x": 24, "y": 54},
        {"slot_id": "CDM", "line": "mid", "x": 50, "y": 56},
        {"slot_id": "RCM", "line": "mid", "x": 76, "y": 54},
        {"slot_id": "LW",  "line": "att", "x": 18, "y": 22},
        {"slot_id": "ST",  "line": "att", "x": 50, "y": 18},
        {"slot_id": "RW",  "line": "att", "x": 82, "y": 22},
    ],
    "3-5-2": [
        {"slot_id": "GK",  "line": "gk",  "x": 50, "y": 88},
        {"slot_id": "LCB", "line": "def", "x": 24, "y": 74},
        {"slot_id": "CB",  "line": "def", "x": 50, "y": 78},
        {"slot_id": "RCB", "line": "def", "x": 76, "y": 74},
        {"slot_id": "LM",  "line": "mid", "x": 10, "y": 52},
        {"slot_id": "LCM", "line": "mid", "x": 32, "y": 56},
        {"slot_id": "CDM", "line": "mid", "x": 50, "y": 58},
        {"slot_id": "RCM", "line": "mid", "x": 68, "y": 56},
        {"slot_id": "RM",  "line": "mid", "x": 90, "y": 52},
        {"slot_id": "LST", "line": "att", "x": 36, "y": 22},
        {"slot_id": "RST", "line": "att", "x": 64, "y": 22},
    ],
    "5-3-2": [
        {"slot_id": "GK",  "line": "gk",  "x": 50, "y": 88},
        {"slot_id": "LB",  "line": "def", "x":  8, "y": 66},
        {"slot_id": "LCB", "line": "def", "x": 27, "y": 72},
        {"slot_id": "CB",  "line": "def", "x": 50, "y": 76},
        {"slot_id": "RCB", "line": "def", "x": 73, "y": 72},
        {"slot_id": "RB",  "line": "def", "x": 92, "y": 66},
        {"slot_id": "LCM", "line": "mid", "x": 24, "y": 50},
        {"slot_id": "CDM", "line": "mid", "x": 50, "y": 54},
        {"slot_id": "RCM", "line": "mid", "x": 76, "y": 50},
        {"slot_id": "LST", "line": "att", "x": 36, "y": 22},
        {"slot_id": "RST", "line": "att", "x": 64, "y": 22},
    ],
    "4-5-1": [
        {"slot_id": "GK",  "line": "gk",  "x": 50, "y": 88},
        {"slot_id": "LB",  "line": "def", "x": 15, "y": 70},
        {"slot_id": "LCB", "line": "def", "x": 36, "y": 74},
        {"slot_id": "RCB", "line": "def", "x": 64, "y": 74},
        {"slot_id": "RB",  "line": "def", "x": 85, "y": 70},
        {"slot_id": "LM",  "line": "mid", "x": 10, "y": 50},
        {"slot_id": "LCM", "line": "mid", "x": 30, "y": 54},
        {"slot_id": "CDM", "line": "mid", "x": 50, "y": 56},
        {"slot_id": "RCM", "line": "mid", "x": 70, "y": 54},
        {"slot_id": "RM",  "line": "mid", "x": 90, "y": 50},
        {"slot_id": "ST",  "line": "att", "x": 50, "y": 18},
    ],
    "3-4-3": [
        {"slot_id": "GK",  "line": "gk",  "x": 50, "y": 88},
        {"slot_id": "LCB", "line": "def", "x": 24, "y": 74},
        {"slot_id": "CB",  "line": "def", "x": 50, "y": 78},
        {"slot_id": "RCB", "line": "def", "x": 76, "y": 74},
        {"slot_id": "LM",  "line": "mid", "x": 18, "y": 52},
        {"slot_id": "LCM", "line": "mid", "x": 38, "y": 56},
        {"slot_id": "RCM", "line": "mid", "x": 62, "y": 56},
        {"slot_id": "RM",  "line": "mid", "x": 82, "y": 52},
        {"slot_id": "LW",  "line": "att", "x": 18, "y": 22},
        {"slot_id": "ST",  "line": "att", "x": 50, "y": 18},
        {"slot_id": "RW",  "line": "att", "x": 82, "y": 22},
    ],
}

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def normalize_player_id(value) -> Optional[int]:
    """Normalisiert Spieler-IDs aus JSON (int oder str) auf int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_fit(slot_id: str, player_position: str) -> Optional[str]:
    """Gibt 'exact', 'compatible' oder None zurück."""
    compat = SLOT_COMPATIBILITY.get(slot_id, {})
    if player_position in compat.get("exact", set()):
        return "exact"
    if player_position in compat.get("compatible", set()):
        return "compatible"
    return None


def effective_score(rating_score: int, fit_type: str) -> int:
    """Integer-Score: rating_score (Hundertstel) + Fit-Malus."""
    return rating_score + FIT_PENALTY_SCORE[fit_type]


def _compute_minutes(ratings: list[dict], substitutions: list[dict], dismissals: list[dict]) -> dict[int, int]:
    """Berechnet minutes_played pro Spieler aus Wechsel- und Platzverweis-Events.

    Returns: {player_id: minutes_played}
    """
    on: dict[int, int] = {}
    off: dict[int, int] = {}

    for r in ratings:
        pid = normalize_player_id(r.get("id"))
        if pid is None:
            continue
        is_sub = bool(r.get("is_sub", False))
        if is_sub:
            on[pid] = 90
            off[pid] = 90
        else:
            on[pid] = 0
            off[pid] = 90

    for sub in (substitutions or []):
        out_pid = normalize_player_id(sub.get("out"))
        in_pid  = normalize_player_id(sub.get("in"))
        minute  = int(sub.get("minute") or 0)

        if out_pid is not None and out_pid in off:
            off[out_pid] = min(off[out_pid], minute)
        if in_pid is not None:
            on[in_pid]  = minute
            off[in_pid] = 90

    for d in (dismissals or []):
        pid    = normalize_player_id(d.get("player_id") or d.get("id"))
        minute = int(d.get("minute") or 0)
        if pid is not None and pid in off:
            off[pid] = min(off[pid], minute)

    result: dict[int, int] = {}
    for pid in set(on) | set(off):
        on_min  = max(0, on.get(pid, 0))
        off_min = max(on_min, off.get(pid, 90))
        result[pid] = max(0, min(90, off_min) - on_min)
    return result


def _build_player_pool(fixtures) -> list[dict]:
    """Baut den qualifizierten Spieler-Pool aus allen Fixtures des Spieltags.

    Gibt eine Liste von Spieler-Dicts zurück (≥ 30 Minuten gespielt).
    """
    from .position_service import normalize_position as _norm_pos

    pool: list[dict] = []

    for fixture in fixtures:
        sm = fixture.simulated_match
        rd = sm.report_data

        home_club = fixture.home_club
        away_club = fixture.away_club

        home_subs       = rd.get("home_substitutions") or []
        away_subs       = rd.get("away_substitutions") or []
        home_dismissals = rd.get("home_dismissals") or []
        away_dismissals = rd.get("away_dismissals") or []

        home_ratings = rd.get("home_ratings") or []
        away_ratings = rd.get("away_ratings") or []

        home_minutes = _compute_minutes(home_ratings, home_subs, home_dismissals)
        away_minutes = _compute_minutes(away_ratings, away_subs, away_dismissals)

        for side_ratings, club, minutes_map in [
            (home_ratings, home_club, home_minutes),
            (away_ratings, away_club, away_minutes),
        ]:
            for r in side_ratings:
                pid = normalize_player_id(r.get("id"))
                if pid is None:
                    logger.warning("Matchday XI skipped rating entry: missing or invalid player id")
                    continue

                raw_pos = r.get("position")
                if not raw_pos:
                    logger.warning("Matchday XI skipped player %s: missing played position", pid)
                    continue

                position = _norm_pos(raw_pos)
                if not position:
                    logger.warning("Matchday XI skipped player %s: unrecognised position %r", pid, raw_pos)
                    continue

                minutes = minutes_map.get(pid, 90)
                if minutes < 30:
                    continue

                rating = float(r.get("rating") or 3.0)
                rating_score = int(round(rating * 100))

                pool.append({
                    "player_id":    pid,
                    "name":         r.get("name", ""),
                    "rating":       rating,
                    "rating_score": rating_score,
                    "goals":        int(r.get("goals") or 0),
                    "assists":      int(r.get("assists") or 0),
                    "position":     position,
                    "is_sub":       bool(r.get("is_sub", False)),
                    "club_id":      club.id,
                    "club_name":    club.name,
                    "crest":        club.crest_static_path,
                    "minutes_played": minutes,
                })

    return pool


def _validate_formation_constraints(slots: list[dict]) -> bool:
    """Prüft ob die belegte Elf die Nutzer-Constraints erfüllt."""
    gk_count     = sum(1 for s in slots if s["line"] == "gk")
    def_count    = sum(1 for s in slots if s["line"] == "def")
    central_mid  = sum(1 for s in slots if s["slot_id"] in _CENTRAL_MID_SLOTS)
    att_count    = sum(1 for s in slots if s["line"] == "att")
    offensive    = sum(1 for s in slots if s["line"] in {"am", "att"})

    return (
        gk_count == 1
        and def_count >= 3
        and central_mid >= 2
        and att_count >= 1
        and offensive <= 4
    )


def _find_best_lineup(
    formation_name: str,
    slots: list[dict],
    pool: list[dict],
) -> Optional[dict]:
    """Findet die optimale Spielerzuweisung für eine Formation via Backtracking.

    Returns dict mit Scoring-Metriken oder None wenn keine vollständige Elf möglich.
    """
    MAX_CANDIDATES = 15

    candidates_by_slot: dict[str, list[tuple[dict, str, int]]] = {}
    for slot in slots:
        sid = slot["slot_id"]
        cands: list[tuple[dict, str, int]] = []
        for p in pool:
            fit = get_fit(sid, p["position"])
            if fit is None:
                continue
            eff = effective_score(p["rating_score"], fit)
            cands.append((p, fit, eff))
        cands.sort(key=lambda x: (
            x[2],
            -x[0]["goals"] - x[0]["assists"],
            -x[0]["minutes_played"],
            x[0]["player_id"],
        ))
        candidates_by_slot[sid] = cands[:MAX_CANDIDATES]

    ordered_slots = sorted(
        slots,
        key=lambda s: len(candidates_by_slot[s["slot_id"]]),
    )

    best: list[Optional[dict]] = [None]

    def _backtrack(
        idx: int,
        used_pids: set[int],
        assignment: dict[str, tuple[dict, str]],
        eff_sum: int,
    ) -> None:
        if idx == len(ordered_slots):
            exact_matches  = sum(1 for _, ft in assignment.values() if ft == "exact")
            rating_cents   = sum(p["rating_score"] for p, _ in assignment.values())
            goal_contrib   = sum(p["goals"] + p["assists"] for p, _ in assignment.values())
            minutes_sum    = sum(p["minutes_played"] for p, _ in assignment.values())
            pids           = tuple(sorted(used_pids))

            key = (eff_sum, -exact_matches, rating_cents, -goal_contrib, -minutes_sum, pids)
            if best[0] is None or key < best[0]["_key"]:
                best[0] = {
                    "_key":         key,
                    "complete":     True,
                    "eff_sum":      eff_sum,
                    "exact_matches": exact_matches,
                    "rating_cents": rating_cents,
                    "goal_contrib": goal_contrib,
                    "minutes_sum":  minutes_sum,
                    "assignment":   dict(assignment),
                }
            return

        cur_slot = ordered_slots[idx]
        sid = cur_slot["slot_id"]
        cands = candidates_by_slot[sid]

        best_eff = best[0]["eff_sum"] if best[0] is not None else None

        for p, fit, eff in cands:
            pid = p["player_id"]
            if pid in used_pids:
                continue
            new_eff = eff_sum + eff
            if best_eff is not None and new_eff > best_eff:
                break
            used_pids.add(pid)
            assignment[sid] = (p, fit)
            _backtrack(idx + 1, used_pids, assignment, new_eff)
            del assignment[sid]
            used_pids.remove(pid)

    _backtrack(0, set(), {}, 0)

    if best[0] is None:
        return None

    result = best[0]
    result["formation"] = formation_name
    return result


def build_matchday_xi(league, season: str, matchday: int) -> Optional[dict]:
    """Berechnet die Elf des Spieltags für den angegebenen Spieltag.

    Args:
        league:   League-ORM-Objekt
        season:   Saison-String, z. B. "1"
        matchday: Spieltag-Nummer

    Returns:
        {
          "formation": "4-4-2",
          "matchday": int,
          "slots": [
            {slot_id, display_role, line, x, y,
             player_id, name, rating, goals, assists,
             minutes_played, club_id, club_name, crest,
             position, fit_type},
            ...
          ]
        }
        oder None wenn keine valide Elf existiert.
    """
    from .models import SeasonFixture

    fixtures = list(
        SeasonFixture.objects
        .filter(season=season, league=league, matchday=matchday)
        .select_related("home_club", "away_club", "simulated_match")
    )

    if not fixtures:
        return None

    if any(f.simulated_match_id is None for f in fixtures):
        return None

    for f in fixtures:
        rd = f.simulated_match.report_data
        if not rd:
            return None
        if not rd.get("home_ratings"):
            return None
        if not rd.get("away_ratings"):
            return None

    pool = _build_player_pool(fixtures)
    if not pool:
        return None

    formation_priority_idx = {name: i for i, name in enumerate(FORMATION_PRIORITY)}
    best_result: Optional[dict] = None

    for formation_name in FORMATION_PRIORITY:
        slots = FORMATION_SLOTS[formation_name]

        if not _validate_formation_constraints(slots):
            continue

        result = _find_best_lineup(formation_name, slots, pool)
        if result is None:
            continue

        if not result.get("complete"):
            continue

        f_key = (
            0,
            result["eff_sum"],
            -result["exact_matches"],
            result["rating_cents"],
            -result["goal_contrib"],
            -result["minutes_sum"],
            formation_priority_idx.get(formation_name, 99),
        )
        result["_formation_key"] = f_key

        if best_result is None or f_key < best_result["_formation_key"]:
            best_result = result

    if best_result is None:
        return None

    formation_name = best_result["formation"]
    slots          = FORMATION_SLOTS[formation_name]
    assignment     = best_result["assignment"]

    output_slots: list[dict] = []
    for slot in slots:
        sid = slot["slot_id"]
        if sid not in assignment:
            return None
        player, fit_type = assignment[sid]
        output_slots.append({
            "slot_id":      sid,
            "display_role": DISPLAY_ROLE.get(sid, sid),
            "line":         slot["line"],
            "x":            slot["x"],
            "y":            slot["y"],
            "player_id":    player["player_id"],
            "name":         player["name"],
            "rating":       player["rating"],
            "goals":        player["goals"],
            "assists":      player["assists"],
            "minutes_played": player["minutes_played"],
            "club_id":      player["club_id"],
            "club_name":    player["club_name"],
            "crest":        player["crest"],
            "position":     player["position"],
            "fit_type":     fit_type,
        })

    return {
        "formation": formation_name,
        "matchday":  matchday,
        "slots":     output_slots,
    }


def get_last_complete_matchday_xi(league, season: str) -> Optional[dict]:
    """Sucht den höchsten vollständig abgeschlossenen Spieltag und berechnet die Elf.

    Iteriert rückwärts über alle is_played-Spieltage bis ein vollständiger gefunden wird.
    """
    from .models import SeasonFixture

    played_matchdays = list(
        SeasonFixture.objects
        .filter(league=league, season=season, is_played=True)
        .order_by("-matchday")
        .values_list("matchday", flat=True)
        .distinct()
    )

    for matchday in played_matchdays:
        result = build_matchday_xi(league, season, matchday)
        if result is not None:
            return result

    return None
