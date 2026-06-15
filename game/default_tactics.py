"""
game/default_tactics.py — Default-Taktik V1
============================================
Wählt automatisch eine taktische Grundeinstellung anhand des Stärkeverhältnisses
zwischen eigener Startelf und gegnerischer Startelf.

Keine Django-Abhängigkeiten — reines Python.

Hauptfunktion:
    generate_default_tactic(
        own_strength, opp_strength,
        own_zones=None, opp_zones=None,
    ) -> dict

Rückgabe:
    {
        'category':      str,   # 'clear_underdog' … 'clear_favorite'
        'first_half':    dict,  # DEFAULT_HALF_TACTIC-Format
        'second_half':   dict,
        'instructions':  dict,  # DEFAULT_INSTRUCTIONS-Format
        'conditions':    list,  # DEFAULT_CONDITIONS-Format
        'line_matchups': dict,  # Erklärungsstruktur
        'side_matchups': dict,
    }
"""
from __future__ import annotations
from copy import deepcopy

# ──────────────────────────────────────────────────────────────────────────────
# Kalibrierte Schwellen
# Empirically calibrated using mirrored synthetic matches (N=5 000, 70 vs 70-80).
# Around −3.5 % relative strength difference marks a meaningful underdog matchup.
# Around −7.0 % marks a clear underdog matchup with approximately
# 31 % wins, 44 % losses and −0.24 xGD per match in the calibration sample.
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_TACTIC_MATCHUP_THRESHOLDS: dict[str, float] = {
    "clear_underdog":  -0.070,
    "underdog":        -0.035,
    "balanced_upper":  +0.035,
    "favorite_upper":  +0.070,
}

# Seitenanalyse: Mindest-Vorteil der eigenen Angriffszone vs. gegnerische
# Defensivzone, ab dem attack_focus angepasst wird.
#
# Regel: Eine Zone wird NUR fokussiert, wenn dort ein echter positiver Vorteil
# besteht (≥ MIN_FOCUS_ADVANTAGE). Alle negativen Zonen → immer ausgewogen.
_SIDE_ADJ_THRESHOLD = 0.02    # 2 % rel. Mindest-Vorteil für Fokus
_SIDE_EDGE_MARGIN   = 0.015   # 1.5 % Mindestabstand zur zweitbesten Seite


# ══════════════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════
def _rel(own: float, opp: float) -> float:
    """Relative Differenz (own − opp) / Mittelwert. Negativ = Nachteil."""
    avg = (own + opp) / 2.0
    return (own - opp) / avg if avg > 0.0 else 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Matchup-Kategorisierung
# ══════════════════════════════════════════════════════════════════════════════
def categorize_matchup(own_overall: float, opp_overall: float) -> str:
    """Leitet die Matchup-Kategorie aus dem Gesamt-Stärkeverhältnis ab.

    Returns:
        'clear_underdog' | 'underdog' | 'balanced' | 'favorite' | 'clear_favorite'
    """
    t = DEFAULT_TACTIC_MATCHUP_THRESHOLDS
    r = _rel(own_overall, opp_overall)
    if r <= t["clear_underdog"]:
        return "clear_underdog"
    if r <= t["underdog"]:
        return "underdog"
    if r < t["balanced_upper"]:
        return "balanced"
    if r < t["favorite_upper"]:
        return "favorite"
    return "clear_favorite"


# ══════════════════════════════════════════════════════════════════════════════
# Linien-Analyse
# ══════════════════════════════════════════════════════════════════════════════
def analyze_line_matchups(own: dict, opp: dict) -> dict:
    """Relative Vor-/Nachteile je Duelllinie.

    Args:
        own, opp: {goalkeeper, defense, midfield, attack, overall}  (float-Werte)

    Returns:
        {
            'defense_vs_attack':    float,   # >0 = eigene Abwehr stärker als gegnerischer Angriff
            'midfield_vs_midfield': float,
            'attack_vs_defense':    float,   # >0 = eigener Angriff stärker als gegnerische Abwehr
        }
    """
    return {
        "defense_vs_attack":    _rel(float(own.get("defense",  50)), float(opp.get("attack",  50))),
        "midfield_vs_midfield": _rel(float(own.get("midfield", 50)), float(opp.get("midfield", 50))),
        "attack_vs_defense":    _rel(float(own.get("attack",   50)), float(opp.get("defense",  50))),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Seiten-Analyse
# ══════════════════════════════════════════════════════════════════════════════
def analyze_side_matchups(own_zones: dict, opp_zones: dict) -> dict:
    """Angriffsvorteil je Seite: eigene Angriffszone vs. gegnerische Defensivzone.

    Korrekte Spiegelung: eigener linker Angriff trifft auf die RECHTE Seite der
    gegnerischen Abwehr (gespiegelte Formation) und umgekehrt.

    Args:
        own_zones: {attack: {left, center, right}, defense: {left, center, right}}
        opp_zones: dasselbe für den Gegner

    Returns:
        {'left': float, 'center': float, 'right': float}   # relativ, >0 = Vorteil
    """
    own_atk = own_zones.get("attack",  {})
    opp_def = opp_zones.get("defense", {})
    return {
        "left":   _rel(float(own_atk.get("left",   0.0)), float(opp_def.get("right",  0.0))),
        "center": _rel(float(own_atk.get("center", 0.0)), float(opp_def.get("center", 0.0))),
        "right":  _rel(float(own_atk.get("right",  0.0)), float(opp_def.get("left",   0.0))),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Basis-Profile
# ══════════════════════════════════════════════════════════════════════════════

def _profile_clear_underdog() -> dict:
    """≤ −7 %: Klarer Außenseiter — tief, kompakt, Konterstrategie."""
    return {
        "first_half": {
            "orientation": 30,
            "defense":     "kompakt_stehen",
            "midfield":    "absichern",
            "attack":      "unterstuetzen",
            "effort":      "normal",
        },
        "second_half": {
            "orientation": 30,
            "defense":     "kompakt_stehen",
            "midfield":    "absichern",
            "attack":      "unterstuetzen",
            "effort":      "normal",
        },
        "instructions": {
            "pressing": {"defense": "passiv", "midfield": "passiv", "attack": "passiv"},
            "pressing_triggers": {
                "ballverlust":    True,    # Konter nach Ballgewinn
                "langer_ball":    False,
                "schlechter_pass": False,
                "torwart_druck":  False,
            },
            "attack_focus": "ausgewogen",
            "buildup": {
                "defense":  "aus_abwehr",
                "midfield": "geduldig",
                "attack":   "tiefenlaeufe",
                "tempo":    35,
            },
            "defending": {
                "deckung":     "raum",
                "zweikampf":   "normal",
                "breite":      "eng",
                "umschalten":  "konter",
            },
        },
        "conditions": [
            # spezifischer zuerst: 2+ Tore Rückstand ab 80' → Schlussangriff
            {"active": True,  "minute": "80", "condition": "rueckstand_2",    "plan": "schlussangriff"},
            # jeder Rückstand ab 65' → kontrolliert öffnen
            {"active": True,  "minute": "65", "condition": "rueckstand",      "plan": "aggressiv_risiko"},
            {"active": True,  "minute": "70", "condition": "fuehrung",        "plan": "zeitspiel"},
            {"active": True,  "minute": "85", "condition": "knappe_fuehrung", "plan": "zeitspiel"},
        ],
    }


def _profile_underdog() -> dict:
    """−7 % bis −3.5 %: Außenseiter — kontrolliert, Umschalten, moderate Tiefe."""
    return {
        "first_half": {
            "orientation": 38,
            "defense":     "kompakt_stehen",
            "midfield":    "absichern",
            "attack":      "unterstuetzen",
            "effort":      "normal",
        },
        "second_half": {
            "orientation": 38,
            "defense":     "kompakt_stehen",
            "midfield":    "absichern",
            "attack":      "unterstuetzen",
            "effort":      "normal",
        },
        "instructions": {
            "pressing": {"defense": "normal", "midfield": "normal", "attack": "passiv"},
            "pressing_triggers": {
                "ballverlust":    True,
                "langer_ball":    False,
                "schlechter_pass": False,
                "torwart_druck":  False,
            },
            "attack_focus": "ausgewogen",
            "buildup": {
                "defense":  "aus_abwehr",
                "midfield": "standard",
                "attack":   "tiefenlaeufe",
                "tempo":    42,
            },
            "defending": {
                "deckung":     "hybrid",
                "zweikampf":   "normal",
                "breite":      "eng",
                "umschalten":  "konter",
            },
        },
        "conditions": [
            {"active": True,  "minute": "60", "condition": "rueckstand",      "plan": "aggressiv_risiko"},
            {"active": True,  "minute": "75", "condition": "fuehrung",        "plan": "kompakt_sichern"},
            {"active": True,  "minute": "85", "condition": "knappe_fuehrung", "plan": "zeitspiel"},
            {"active": False, "minute": "90", "condition": "rueckstand_2",    "plan": "schlussangriff"},
        ],
    }


def _profile_balanced() -> dict:
    """±3.5 %: Ausgeglichenes Spiel — Standard-Einstellungen."""
    return {
        "first_half": {
            "orientation": 50,
            "defense":     "standard",
            "midfield":    "standard",
            "attack":      "standard",
            "effort":      "normal",
        },
        "second_half": {
            "orientation": 50,
            "defense":     "standard",
            "midfield":    "standard",
            "attack":      "standard",
            "effort":      "normal",
        },
        "instructions": {
            "pressing": {"defense": "normal", "midfield": "normal", "attack": "normal"},
            "pressing_triggers": {
                "ballverlust":    False,
                "langer_ball":    False,
                "schlechter_pass": False,
                "torwart_druck":  False,
            },
            "attack_focus": "ausgewogen",
            "buildup": {
                "defense":  "standard",
                "midfield": "standard",
                "attack":   "standard",
                "tempo":    50,
            },
            "defending": {
                "deckung":     "hybrid",
                "zweikampf":   "normal",
                "breite":      "standard",
                "umschalten":  "ausgewogen",
            },
        },
        "conditions": [
            {"active": True,  "minute": "60", "condition": "rueckstand",      "plan": "aggressiv_risiko"},
            {"active": True,  "minute": "75", "condition": "fuehrung",        "plan": "zeitspiel"},
            {"active": True,  "minute": "85", "condition": "knappe_fuehrung", "plan": "zeitspiel"},
            {"active": False, "minute": "90", "condition": "rueckstand_2",    "plan": "schlussangriff"},
        ],
    }


def _profile_favorite() -> dict:
    """+3.5 % bis +7 %: Favorit — höhere Linie, nachrücken, Ballbesitz."""
    return {
        "first_half": {
            "orientation": 62,
            "defense":     "hoeher_stehen",
            "midfield":    "nachruecken",
            "attack":      "abwehrkette_binden",
            "effort":      "normal",
        },
        "second_half": {
            "orientation": 62,
            "defense":     "hoeher_stehen",
            "midfield":    "nachruecken",
            "attack":      "abwehrkette_binden",
            "effort":      "normal",
        },
        "instructions": {
            "pressing": {"defense": "normal", "midfield": "intensiv", "attack": "normal"},
            "pressing_triggers": {
                "ballverlust":    False,
                "langer_ball":    True,    # Zweite Bälle
                "schlechter_pass": False,
                "torwart_druck":  False,
            },
            "attack_focus": "ausgewogen",
            "buildup": {
                "defense":  "standard",
                "midfield": "vertikal",
                "attack":   "kombinieren",
                "tempo":    58,
            },
            "defending": {
                "deckung":     "hybrid",
                "zweikampf":   "normal",
                "breite":      "standard",
                "umschalten":  "ballbesitz",
            },
        },
        "conditions": [
            {"active": True,  "minute": "55", "condition": "rueckstand",      "plan": "aggressiv_risiko"},
            {"active": True,  "minute": "75", "condition": "fuehrung",        "plan": "kontrolle_ballbesitz"},
            {"active": True,  "minute": "85", "condition": "knappe_fuehrung", "plan": "kompakt_sichern"},
            {"active": False, "minute": "90", "condition": "rueckstand_2",    "plan": "schlussangriff"},
        ],
    }


def _profile_clear_favorite() -> dict:
    """> +7 %: Klarer Favorit — hohes Pressing, offensiv, Strafraum besetzen."""
    return {
        "first_half": {
            "orientation": 72,
            "defense":     "hoeher_stehen",
            "midfield":    "offensiv_besetzen",
            "attack":      "strafraum_besetzen",
            "effort":      "hoch",
        },
        "second_half": {
            "orientation": 65,             # zweite Hälfte etwas konservativer
            "defense":     "hoeher_stehen",
            "midfield":    "nachruecken",
            "attack":      "abwehrkette_binden",
            "effort":      "normal",
        },
        "instructions": {
            "pressing": {"defense": "intensiv", "midfield": "intensiv", "attack": "intensiv"},
            "pressing_triggers": {
                "ballverlust":    True,    # Budget 2
                "langer_ball":    True,    # Budget 1 → Gesamt 3 (= Limit)
                "schlechter_pass": False,
                "torwart_druck":  False,
            },
            "attack_focus": "ausgewogen",
            "buildup": {
                "defense":  "direkt_vorne",
                "midfield": "vertikal",
                "attack":   "kombinieren",
                "tempo":    65,
            },
            "defending": {
                "deckung":     "hybrid",
                "zweikampf":   "normal",
                "breite":      "breit",
                "umschalten":  "ballbesitz",
            },
        },
        "conditions": [
            # spezifischer zuerst: 2+ Tore Rückstand ab 75' → Schlussangriff
            {"active": True,  "minute": "75", "condition": "rueckstand_2",    "plan": "schlussangriff"},
            # jeder Rückstand ab 50' → sofort aggressiv
            {"active": True,  "minute": "50", "condition": "rueckstand",      "plan": "aggressiv_risiko"},
            {"active": True,  "minute": "70", "condition": "fuehrung",        "plan": "kompakt_sichern"},
            {"active": True,  "minute": "85", "condition": "knappe_fuehrung", "plan": "zeitspiel"},
        ],
    }


_PROFILE_BUILDERS = {
    "clear_underdog":  _profile_clear_underdog,
    "underdog":        _profile_underdog,
    "balanced":        _profile_balanced,
    "favorite":        _profile_favorite,
    "clear_favorite":  _profile_clear_favorite,
}


# ══════════════════════════════════════════════════════════════════════════════
# Linien- und Seiten-Anpassungen (auf dem Basis-Profil)
# ══════════════════════════════════════════════════════════════════════════════

def _apply_line_adjustments(profile: dict, lines: dict, sides: dict) -> dict:
    """Feinjustiert das Basis-Profil anhand von Linien- und Seiten-Matchups.

    Regeln:
    - Eigener Angriff klar besser  (atk_vs_def ≥ +5 %): Angriffsoption upgraden
    - Eigener Angriff klar schwächer (atk_vs_def ≤ −7 %): Angriffsoption downgraden
    - Eigene Abwehr klar schwächer  (def_vs_atk ≤ −7 %): Defensivoption verstärken
    - Seite mit ≥ 5 % Vorteil und ≥ 2 % Abstand zur zweitbesten: attack_focus setzen
    """
    p = deepcopy(profile)

    atk_adv = lines["attack_vs_defense"]
    def_adv = lines["defense_vs_attack"]

    _UPGRADE_ATK = {
        "unterstuetzen": "standard",
        "standard":      "abwehrkette_binden",
    }
    _DOWNGRADE_ATK = {
        "abwehrkette_binden": "standard",
        "strafraum_besetzen": "abwehrkette_binden",
        "standard":           "unterstuetzen",
    }
    _UPGRADE_DEF = {
        "hoeher_stehen": "standard",
        "standard":      "kompakt_stehen",
        "absichern":     "tief_stehen",
    }

    for half in ("first_half", "second_half"):
        cur_atk = p[half]["attack"]
        cur_def = p[half]["defense"]

        if atk_adv >= 0.05 and cur_atk in _UPGRADE_ATK:
            p[half]["attack"] = _UPGRADE_ATK[cur_atk]
        elif atk_adv <= -0.07 and cur_atk in _DOWNGRADE_ATK:
            p[half]["attack"] = _DOWNGRADE_ATK[cur_atk]

        if def_adv <= -0.07 and cur_def in _UPGRADE_DEF:
            p[half]["defense"] = _UPGRADE_DEF[cur_def]

    left   = sides["left"]
    right  = sides["right"]
    center = sides["center"]
    T = _SIDE_ADJ_THRESHOLD
    M = _SIDE_EDGE_MARGIN

    # Zuerst eindeutige Seitendominanz prüfen, dann erst Flügelspiel.
    if left >= T and left > right + M and left > center + M:
        p["instructions"]["attack_focus"] = "ueber_links"
    elif right >= T and right > left + M and right > center + M:
        p["instructions"]["attack_focus"] = "ueber_rechts"
    elif center >= T and center > left + M and center > right + M:
        p["instructions"]["attack_focus"] = "durch_mitte"
    elif (left >= T and right >= T
          and abs(left - right) < 0.10
          and center < min(left, right) - M):
        # Beide Flügel klar besser als Zentrum → Flügelspiel
        p["instructions"]["attack_focus"] = "fluegelspiel"

    return p


# ══════════════════════════════════════════════════════════════════════════════
# Hauptfunktion
# ══════════════════════════════════════════════════════════════════════════════

def generate_default_tactic(
    own_strength:  dict,
    opp_strength:  dict,
    own_zones:     dict | None = None,
    opp_zones:     dict | None = None,
) -> dict:
    """Erstellt automatisch das optimale Taktik-Dict anhand des Stärkeverhältnisses.

    Args:
        own_strength:  {goalkeeper, defense, midfield, attack, overall}  (float)
        opp_strength:  dasselbe für den Gegner
        own_zones:     {attack: {left,center,right}, defense: {left,center,right}}
                       Aus calculate_zone_strengths(). None → kein Side-Adjust.
        opp_zones:     dasselbe für den Gegner

    Returns:
        {
            'category':      str,
            'first_half':    dict,
            'second_half':   dict,
            'instructions':  dict,
            'conditions':    list,
            'line_matchups': dict,
            'side_matchups': dict,
        }
    """
    category = categorize_matchup(
        float(own_strength.get("overall", 50)),
        float(opp_strength.get("overall", 50)),
    )

    profile = _PROFILE_BUILDERS[category]()

    line_matchups = analyze_line_matchups(own_strength, opp_strength)

    _empty_zones: dict = {
        "attack":  {"left": 0.0, "center": 0.0, "right": 0.0},
        "defense": {"left": 0.0, "center": 0.0, "right": 0.0},
    }
    side_matchups = analyze_side_matchups(
        own_zones or _empty_zones,
        opp_zones or _empty_zones,
    )

    adjusted = _apply_line_adjustments(profile, line_matchups, side_matchups)

    own_overall = float(own_strength.get("overall", 50))
    opp_overall = float(opp_strength.get("overall", 50))
    relative_diff = _rel(own_overall, opp_overall)

    return {
        "category":        category,
        "first_half":      adjusted["first_half"],
        "second_half":     adjusted["second_half"],
        "instructions":    adjusted["instructions"],
        "conditions":      adjusted["conditions"],
        "line_matchups":   line_matchups,
        "side_matchups":   side_matchups,
        # Debug-Felder: Rohwerte für Logging und Tests
        "own_overall":     own_overall,
        "opp_overall":     opp_overall,
        "relative_diff":   relative_diff,
    }
