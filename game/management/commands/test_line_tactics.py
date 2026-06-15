"""
Exploit-Test-Tool für Halbzeit-Linienoptionen (Abwehr / Mittelfeld / Angriff).

MODI
  compiler  — Compiler-Checks aller 6×5×4=120 Kombinationen (keine Simulation)
  single    — Neue Einzeloptionen isoliert gegen Standard (gespiegelte Matches)
  matrix    — Volle 6×5×4 Kombinationsmatrix (gespiegelte Matches)
  extreme   — Vordefinierte Extremkombinationen (gespiegelte Matches)
  halves    — Halbzeit-Isolation: Option nur 1H / nur 2H / beide vs. Standard
  all       — Alle Modi nacheinander

AUFRUF
  python manage.py test_line_tactics
  python manage.py test_line_tactics --mode single --matches 5000
  python manage.py test_line_tactics --mode matrix --matches 2000 --output .local/test/
  python manage.py test_line_tactics --mode all --matches 1000
  python manage.py test_line_tactics --mode halves --option nachruecken --field midfield

EXPLOIT-KRITERIEN (werden automatisch markiert)
  [CAP]   xg_for_applied > 0.060 + ε  oder  shots_applied > 0.080 + ε
  [NEG]   Negativer Wert capped → falsch
  [GRAT]  xGF ↑ UND xGA ↓ UND risk ↓ UND fatigue ↓ gleichzeitig (Gratisvorteil)
  [PPG]   PPG-Delta > 0.05 vs. Standard über ≥2k gespiegelte Matches
  [XGD]   xGD-Delta > 0.05 vs. Standard
  [COHER] Kohärenzstrafe tief_stehen+offensiv_besetzen+strafraum_besetzen ≠ 0.96
  [BLEED] Halbzeit-Option beeinflusst die andere Halbzeit (Compiler-Verifikation)
"""

import csv
import os
import sys
import time
from copy import deepcopy

from django.core.management.base import BaseCommand, CommandError

# ─── Optionslisten ────────────────────────────────────────────────────────────
DEFENSE_OPTIONS  = ['standard', 'kompakt_stehen', 'tief_stehen', 'hoeher_stehen',
                    'absichern', 'frueh_herausruecken']
MIDFIELD_OPTIONS = ['standard', 'absichern', 'ballbesitz_sichern', 'nachruecken', 'offensiv_besetzen']
ATTACK_OPTIONS   = ['unterstuetzen', 'standard', 'abwehrkette_binden', 'strafraum_besetzen']

# Neue Optionen (nur diese im single-mode isoliert testen)
NEW_MIDFIELD = ['nachruecken', 'offensiv_besetzen']
NEW_ATTACK   = ['unterstuetzen', 'abwehrkette_binden', 'strafraum_besetzen']
ALL_NEW_OPTIONS = [
    ('midfield', o) for o in NEW_MIDFIELD
] + [
    ('attack', o) for o in NEW_ATTACK
]

EXTREME_SCENARIOS = [
    {'id': 'max_off_coherent',   'hd': 'hoeher_stehen', 'hm': 'offensiv_besetzen',   'ha': 'strafraum_besetzen',
     'desc': 'hoeher_stehen + offensiv_besetzen + strafraum_besetzen (kohärent)'},
    {'id': 'max_off_incoherent', 'hd': 'tief_stehen',   'hm': 'offensiv_besetzen',   'ha': 'strafraum_besetzen',
     'desc': 'tief_stehen + offensiv_besetzen + strafraum_besetzen (inkohärent)'},
    {'id': 'max_defensive',      'hd': 'tief_stehen',   'hm': 'absichern',            'ha': 'unterstuetzen',
     'desc': 'tief_stehen + absichern + unterstuetzen (max defensiv)'},
    {'id': 'ball_control',       'hd': 'standard',      'hm': 'ballbesitz_sichern',   'ha': 'unterstuetzen',
     'desc': 'standard + ballbesitz_sichern + unterstuetzen (Ballkontrolle)'},
    {'id': 'moderate_offensive', 'hd': 'hoeher_stehen', 'hm': 'nachruecken',          'ha': 'abwehrkette_binden',
     'desc': 'hoeher_stehen + nachruecken + abwehrkette_binden'},
    {'id': 'standard_baseline',  'hd': 'standard',      'hm': 'standard',             'ha': 'standard',
     'desc': 'standard + standard + standard (Baseline)'},
]

# ─── Formation 4-4-2 (synthetisch, kein ORM) ─────────────────────────────────
_SLOTS_442 = [
    {'player_id':  1, 'position': 'TW', 'group': 'goalkeeper'},
    {'player_id':  2, 'position': 'LV', 'group': 'defense'},
    {'player_id':  3, 'position': 'IV', 'group': 'defense'},
    {'player_id':  4, 'position': 'IV', 'group': 'defense'},
    {'player_id':  5, 'position': 'RV', 'group': 'defense'},
    {'player_id':  6, 'position': 'LM', 'group': 'midfield'},
    {'player_id':  7, 'position': 'ZM', 'group': 'midfield'},
    {'player_id':  8, 'position': 'ZM', 'group': 'midfield'},
    {'player_id':  9, 'position': 'RM', 'group': 'midfield'},
    {'player_id': 10, 'position': 'ST', 'group': 'attack'},
    {'player_id': 11, 'position': 'ST', 'group': 'attack'},
]

_STD_HALF = {
    'orientation': 50, 'effort': 'normal',
    'defense': 'standard', 'midfield': 'standard', 'attack': 'standard',
}
_EPS = 1e-6


# ─── Builder-Funktionen ───────────────────────────────────────────────────────

def _make_half(hd='standard', hm='standard', ha='standard'):
    return {'orientation': 50, 'effort': 'normal', 'defense': hd, 'midfield': hm, 'attack': ha}


def _make_tactic(hd='standard', hm='standard', ha='standard',
                 apply_first=True, apply_second=True):
    active = _make_half(hd, hm, ha)
    std    = dict(_STD_HALF)
    return {
        'attack_focus': 'ausgewogen',
        'pressing': {}, 'pressing_triggers': {}, 'buildup': {}, 'defending': {},
        'conditions': [],
        'first_half':  active if apply_first  else std,
        'second_half': active if apply_second else std,
    }


def _make_team(tactic, strength=75, id_offset=0):
    """Synthetisches Team-Dict ohne ORM-Zugriff."""
    players = []
    lineup  = []
    for s in _SLOTS_442:
        pid = s['player_id'] + id_offset
        players.append({
            'id':                   pid,
            'name':                 f'P{pid}',
            'final_strength':       float(strength),
            'main_positions':       [s['position']],
            'secondary_positions':  [],
            'teamwork':             70,
            'freshness':            100,
            'is_ws_injured':        False,
        })
        lineup.append({**s, 'player_id': pid})
    return {
        'team':                 {'name': f'SynTeam_{id_offset}', 'id': id_offset + 1},
        'players':              players,
        'lineup':               lineup,
        'tactic':               tactic,
        'bench_player_data':    {},
        'planned_substitutions':[],
    }


# ─── Match-Runner ─────────────────────────────────────────────────────────────

def _run_raw(home_team, away_team, sim_fn):
    """Simuliert ein Spiel — gibt Rohstats beider Seiten zurück."""
    r  = sim_fn(home_team, away_team)
    ms = r.get('match_stats', {})
    return {
        'hg':  r['home_goals'],
        'ag':  r['away_goals'],
        'hxg': r.get('home_xg', 0.0),
        'axg': r.get('away_xg', 0.0),
        'hsh': ms.get('home_shots', 0),
        'ash': ms.get('away_shots', 0),
        'hpo': ms.get('home_possession', 50),
        'hfc': ms.get('home_fatigue_cost', 1.0),
        'afc': ms.get('away_fatigue_cost', 1.0),
        'hyl': ms.get('home_yellow', 0),
        'ayl': ms.get('away_yellow', 0),
        'hrd': ms.get('home_red', 0),
        'ard': ms.get('away_red', 0),
        'hco': ms.get('home_tactic_coherence', 1.0),
        'aco': ms.get('away_tactic_coherence', 1.0),
        'plan_acts': len(r.get('plan_activations', [])),
    }


def _from_home(r):
    """Stats aus Heimteam-Perspektive."""
    return {
        'gf': r['hg'], 'ga': r['ag'], 'xgf': r['hxg'], 'xga': r['axg'],
        'sf': r['hsh'], 'sa': r['ash'], 'poss': r['hpo'],
        'fatigue': r['hfc'], 'yellow': r['hyl'], 'red': r['hrd'],
        'coherence': r['hco'], 'plan_acts': r['plan_acts'],
    }


def _from_away(r):
    """Stats aus Auswärtsteam-Perspektive."""
    return {
        'gf': r['ag'], 'ga': r['hg'], 'xgf': r['axg'], 'xga': r['hxg'],
        'sf': r['ash'], 'sa': r['hsh'], 'poss': 100 - r['hpo'],
        'fatigue': r['afc'], 'yellow': r['ayl'], 'red': r['ard'],
        'coherence': r['aco'], 'plan_acts': r['plan_acts'],
    }


def _run_mirrored_batch(tactic_a, n, sim_fn, strength=75):
    """
    n//2 Heimspiele (A Heim vs Std Gast) + n//2 Auswärtsspiele (Std Heim vs A Gast).
    Eliminiert Home-Advantage-Bias. Gibt Aggregat aus A's Perspektive zurück.
    """
    tactic_std = _make_tactic()
    n_home = n // 2
    n_away = n - n_home

    team_a   = _make_team(tactic_a,   strength, id_offset=0)
    team_std = _make_team(tactic_std, strength, id_offset=100)

    rows = []
    errors = 0

    for _ in range(n_home):
        try:
            rows.append(_from_home(_run_raw(team_a, team_std, sim_fn)))
        except Exception:
            errors += 1

    team_a2   = _make_team(tactic_a,   strength, id_offset=100)
    team_std2 = _make_team(tactic_std, strength, id_offset=0)

    for _ in range(n_away):
        try:
            rows.append(_from_away(_run_raw(team_std2, team_a2, sim_fn)))
        except Exception:
            errors += 1

    return _aggregate(rows, errors)


def _aggregate(rows, errors=0):
    """Aggregiert Einzel-Match-Rows zu Mittelwerten + W/D/L."""
    n = len(rows)
    if n == 0:
        return {'n': 0, 'errors': errors}
    wins   = sum(1 for r in rows if r['gf'] > r['ga'])
    draws  = sum(1 for r in rows if r['gf'] == r['ga'])
    losses = sum(1 for r in rows if r['gf'] < r['ga'])
    ppg    = (wins * 3 + draws) / n

    def avg(key):
        return sum(r[key] for r in rows) / n

    return {
        'n':        n,
        'errors':   errors,
        'wins':     wins,
        'draws':    draws,
        'losses':   losses,
        'ppg':      round(ppg, 4),
        'gf':       round(avg('gf'),  4),
        'ga':       round(avg('ga'),  4),
        'gd':       round(avg('gf') - avg('ga'), 4),
        'xgf':      round(avg('xgf'), 4),
        'xga':      round(avg('xga'), 4),
        'xgd':      round(avg('xgf') - avg('xga'), 4),
        'shots_f':  round(avg('sf'),  4),
        'shots_a':  round(avg('sa'),  4),
        'poss':     round(avg('poss'), 2),
        'fatigue':  round(avg('fatigue'), 4),
        'yellow':   round(avg('yellow'), 4),
        'red':      round(avg('red'), 4),
        'coherence':round(avg('coherence'), 4),
        'plan_acts':round(avg('plan_acts'), 3),
    }


# ─── Compiler-Check ───────────────────────────────────────────────────────────

def _compiler_check(compile_fn, hd, hm, ha, half='both'):
    """
    Ruft compile_tactic für eine Kombination auf und gibt alle Debug-Werte zurück.
    half: 'first', 'second', 'both' (dann erste Hälfte wird verwendet)
    """
    tactic = _make_tactic(hd, hm, ha)
    team   = _make_team(tactic)
    h = 'first' if half in ('first', 'both') else 'second'
    profile = compile_fn(team, tactic, half=h)
    dbg = profile.get('debug', {})

    # Exploits detektieren
    flags = []
    xg_app = dbg.get('line_xg_for_applied', 0.0)
    sh_app = dbg.get('line_shots_applied', 0.0)
    xg_raw = dbg.get('line_xg_for_raw', 0.0)
    sh_raw = dbg.get('line_shots_raw', 0.0)
    risk   = dbg.get('line_risk', 0.0)
    fat    = dbg.get('line_fatigue', 0.0)
    xga    = dbg.get('line_xg_against', 0.0)
    poss   = dbg.get('line_possession', 0.0)
    coh    = profile.get('coherence', 1.0)

    if xg_app > 0.060 + _EPS:
        flags.append(f'[CAP:xgF={xg_app:.4f}>0.06]')
    if sh_app > 0.080 + _EPS:
        flags.append(f'[CAP:shots={sh_app:.4f}>0.08]')
    if xg_raw > 0.0 and xg_app < xg_raw - _EPS and xg_app < 0.0:
        flags.append(f'[NEG:xgF_capped_negative]')
    if sh_raw > 0.0 and sh_app < 0.0:
        flags.append(f'[NEG:shots_capped_negative]')
    # Gratisvorteil: alles gleichzeitig positiv ohne jede Gegenwirkung
    if xg_app > _EPS and xga < -_EPS and risk < -_EPS and fat < -_EPS:
        flags.append('[GRAT:xgF+/xgA-/risk-/fat-]')
    # Spezielle Kohärenzprüfung: tief + offensiv_besetzen + strafraum_besetzen
    if (hd == 'tief_stehen' and hm == 'offensiv_besetzen'
            and ha == 'strafraum_besetzen'):
        expected_coh = round(1.0 - 0.04, 4)
        if abs(coh - expected_coh) > 0.001:
            flags.append(f'[COHER:expected={expected_coh},got={coh:.4f}]')

    return {
        'hd': hd, 'hm': hm, 'ha': ha,
        'xg_for_raw':    round(xg_raw, 5),
        'xg_for_applied':round(xg_app, 5),
        'shots_raw':     round(sh_raw, 5),
        'shots_applied': round(sh_app, 5),
        'xg_against':    round(xga, 5),
        'risk':          round(risk, 5),
        'fatigue':       round(fat, 5),
        'possession':    round(poss, 5),
        'coherence':     round(coh, 4),
        'xg_for_final':  round(profile.get('xg_for', 1.0), 4),
        'xg_against_final': round(profile.get('xg_against', 1.0), 4),
        'shot_volume':   round(profile.get('shot_volume', 1.0), 4),
        'fatigue_cost':  round(profile.get('fatigue_cost', 1.0), 4),
        'flags':         ' '.join(flags) if flags else 'OK',
        'exploit':       bool(flags),
    }


def _compiler_check_halves(compile_fn, option, field):
    """
    Prüft Bleeding: Option nur in 1. Halbzeit → 2. Halbzeit muss standard-Werte zeigen.
    """
    hd = option if field == 'defense'  else 'standard'
    hm = option if field == 'midfield' else 'standard'
    ha = option if field == 'attack'   else 'standard'

    results = {}
    # 1H only
    tactic_1h = _make_tactic(hd, hm, ha, apply_first=True, apply_second=False)
    team_1h = _make_team(tactic_1h)
    p1h_first  = compile_fn(team_1h, tactic_1h, half='first')
    p1h_second = compile_fn(team_1h, tactic_1h, half='second')

    # 2H only
    tactic_2h = _make_tactic(hd, hm, ha, apply_first=False, apply_second=True)
    team_2h = _make_team(tactic_2h)
    p2h_first  = compile_fn(team_2h, tactic_2h, half='first')
    p2h_second = compile_fn(team_2h, tactic_2h, half='second')

    # Both
    tactic_both = _make_tactic(hd, hm, ha)
    team_both = _make_team(tactic_both)
    p_both_first  = compile_fn(team_both, tactic_both, half='first')
    p_both_second = compile_fn(team_both, tactic_both, half='second')

    # Standard baseline
    tactic_std = _make_tactic()
    team_std = _make_team(tactic_std)
    p_std_first  = compile_fn(team_std, tactic_std, half='first')
    p_std_second = compile_fn(team_std, tactic_std, half='second')

    def _dbg_xgf(profile):
        return profile.get('debug', {}).get('line_xg_for_applied', 0.0)

    # Bleeding-Check: 1H-Option darf 2H-Profil nicht ändern
    bleed_flags = []
    std_2h_xgf = _dbg_xgf(p_std_second)
    act_2h_xgf = _dbg_xgf(p1h_second)
    if abs(act_2h_xgf - std_2h_xgf) > _EPS:
        bleed_flags.append(f'[BLEED:1H→2H xgF_delta={act_2h_xgf - std_2h_xgf:.5f}]')

    std_1h_xgf = _dbg_xgf(p_std_first)
    act_1h_xgf = _dbg_xgf(p2h_first)
    if abs(act_1h_xgf - std_1h_xgf) > _EPS:
        bleed_flags.append(f'[BLEED:2H→1H xgF_delta={act_1h_xgf - std_1h_xgf:.5f}]')

    return {
        'option': option, 'field': field,
        '1h_only__1h_xgF':    round(_dbg_xgf(p1h_first), 5),
        '1h_only__2h_xgF':    round(_dbg_xgf(p1h_second), 5),
        '2h_only__1h_xgF':    round(_dbg_xgf(p2h_first), 5),
        '2h_only__2h_xgF':    round(_dbg_xgf(p2h_second), 5),
        'both__1h_xgF':       round(_dbg_xgf(p_both_first), 5),
        'both__2h_xgF':       round(_dbg_xgf(p_both_second), 5),
        'std__1h_xgF':        round(_dbg_xgf(p_std_first), 5),
        'std__2h_xgF':        round(_dbg_xgf(p_std_second), 5),
        'bleeding':           ' '.join(bleed_flags) if bleed_flags else 'NONE',
        'exploit':            bool(bleed_flags),
    }


# ─── CSV-Hilfsfunktionen ──────────────────────────────────────────────────────

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _write_csv(path, rows, fieldnames=None):
    if not rows:
        return
    fields = fieldnames or list(rows[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def _ppg_flag(ppg_delta):
    return '[PPG]' if ppg_delta > 0.05 else ''


def _xgd_flag(xgd_delta):
    return '[XGD]' if xgd_delta > 0.05 else ''


# ─── Modus-Handler ────────────────────────────────────────────────────────────

def _mode_compiler(out, csv_dir, compile_fn):
    """Prüft alle 6×5×4=120 Kombinationen via compile_tactic."""
    out('── Compiler-Check aller 120 Kombinationen ──────────────────────────')
    rows = []
    exploits = []
    for hd in DEFENSE_OPTIONS:
        for hm in MIDFIELD_OPTIONS:
            for ha in ATTACK_OPTIONS:
                row = _compiler_check(compile_fn, hd, hm, ha)
                rows.append(row)
                if row['exploit']:
                    exploits.append(row)

    if csv_dir:
        _write_csv(os.path.join(csv_dir, 'compiler_all_combos.csv'), rows)

    ok = sum(1 for r in rows if not r['exploit'])
    out(f'Gesamt: {len(rows)} Kombos | OK: {ok} | EXPLOIT: {len(exploits)}')

    if exploits:
        out('\n[!] EXPLOITS GEFUNDEN:')
        for r in exploits:
            out(f"  {r['hd']:22} + {r['hm']:20} + {r['ha']:22}  →  {r['flags']}")
    else:
        out('Keine Exploits detektiert.')

    # Standard-Baseline-Check (alle Werte = 0)
    std_row = _compiler_check(compile_fn, 'standard', 'standard', 'standard')
    out(f'\nBaseline (standard+standard+standard):')
    out(f"  xgF_applied={std_row['xg_for_applied']:.5f}  "
        f"shots_applied={std_row['shots_applied']:.5f}  "
        f"coherence={std_row['coherence']:.4f}  "
        f"flags={std_row['flags']}")

    return rows, exploits


def _mode_single(out, csv_dir, sim_fn, matches_per_option):
    """Testet jede neue Option isoliert gegen Standard."""
    out(f'── Einzeloptions-Test ──────────────────────────────────────────────')
    out(f'Je {matches_per_option:,} gespiegelte Matches pro Option')

    std_stats = _run_mirrored_batch(_make_tactic(), matches_per_option, sim_fn)
    rows = []
    exploits = []

    for field, option in ALL_NEW_OPTIONS:
        hd = option if field == 'defense'  else 'standard'
        hm = option if field == 'midfield' else 'standard'
        ha = option if field == 'attack'   else 'standard'

        t0 = time.time()
        stats = _run_mirrored_batch(_make_tactic(hd, hm, ha), matches_per_option, sim_fn)
        elapsed = time.time() - t0

        ppg_d = stats['ppg']  - std_stats['ppg']
        xgd_d = stats['xgd'] - std_stats['xgd']
        flags = [_ppg_flag(ppg_d), _xgd_flag(xgd_d)]
        flags = [f for f in flags if f]
        exploit = bool(flags)

        row = {
            'field': field, 'option': option,
            'n': stats['n'], 'errors': stats['errors'],
            'ppg': stats['ppg'], 'ppg_delta': round(ppg_d, 4),
            'xgf': stats['xgf'], 'xga': stats['xga'],
            'xgd': stats['xgd'], 'xgd_delta': round(xgd_d, 4),
            'shots_f': stats['shots_f'], 'shots_a': stats['shots_a'],
            'poss': stats['poss'], 'fatigue': stats['fatigue'],
            'coherence': stats['coherence'],
            'flags': ' '.join(flags) if flags else 'OK',
            'exploit': exploit,
            'elapsed_s': round(elapsed, 1),
        }
        rows.append(row)
        if exploit:
            exploits.append(row)

        flag_str = ' '.join(flags) if flags else 'OK'
        out(f"  {field:8} {option:22}  PPG Δ={ppg_d:+.3f}  xGD Δ={xgd_d:+.4f}  "
            f"n={stats['n']:,}  t={elapsed:.1f}s  {flag_str}")

    if csv_dir:
        _write_csv(os.path.join(csv_dir, 'single_option_test.csv'), rows)

    out(f'\nErgebnis: {len(rows)} Optionen | EXPLOIT: {len(exploits)}')
    if exploits:
        out('[!] EXPLOITS: ' + ', '.join(f"{r['field']}.{r['option']}" for r in exploits))

    return rows, exploits


def _mode_matrix(out, csv_dir, sim_fn, matches_per_combo):
    """Volle 6×5×4=120 Kombinationsmatrix."""
    out(f'── Matrix-Test 6×5×4=120 Kombos ────────────────────────────────────')
    out(f'Je {matches_per_combo:,} gespiegelte Matches pro Kombo')
    total = len(DEFENSE_OPTIONS) * len(MIDFIELD_OPTIONS) * len(ATTACK_OPTIONS)
    out(f'Gesamt: {total} Kombos × {matches_per_combo} = {total * matches_per_combo:,} Match-Pairs')

    std_stats = _run_mirrored_batch(_make_tactic(), matches_per_combo, sim_fn)
    rows = []
    exploits = []
    done = 0
    t_start = time.time()

    for hd in DEFENSE_OPTIONS:
        for hm in MIDFIELD_OPTIONS:
            for ha in ATTACK_OPTIONS:
                stats = _run_mirrored_batch(_make_tactic(hd, hm, ha), matches_per_combo, sim_fn)
                ppg_d = stats['ppg']  - std_stats['ppg']
                xgd_d = stats['xgd'] - std_stats['xgd']
                flags = [_ppg_flag(ppg_d), _xgd_flag(xgd_d)]
                flags = [f for f in flags if f]
                exploit = bool(flags)

                row = {
                    'hd': hd, 'hm': hm, 'ha': ha,
                    'n': stats['n'], 'errors': stats['errors'],
                    'ppg': stats['ppg'], 'ppg_delta': round(ppg_d, 4),
                    'xgf': stats['xgf'], 'xga': stats['xga'],
                    'xgd': stats['xgd'], 'xgd_delta': round(xgd_d, 4),
                    'shots_f': stats['shots_f'], 'shots_a': stats['shots_a'],
                    'poss': stats['poss'], 'fatigue': stats['fatigue'],
                    'coherence': stats['coherence'],
                    'flags': ' '.join(flags) if flags else 'OK',
                    'exploit': exploit,
                }
                rows.append(row)
                if exploit:
                    exploits.append(row)

                done += 1
                elapsed = time.time() - t_start
                eta = (elapsed / done) * (total - done) if done < total else 0
                out(f"  [{done:3}/{total}] {hd:22}+{hm:20}+{ha:22}  "
                    f"PPG Δ={ppg_d:+.3f}  xGD Δ={xgd_d:+.4f}  "
                    f"{'[!]' if exploit else 'ok'}  ETA {eta:.0f}s", ending='\r' if done < total else '\n')

    out('')  # Zeilenumbruch nach \r
    if csv_dir:
        _write_csv(os.path.join(csv_dir, 'matrix_all_combos.csv'), rows)

    out(f'Gesamt: {len(rows)} Kombos | OK: {sum(1 for r in rows if not r["exploit"])} | '
        f'EXPLOIT: {len(exploits)}')
    if exploits:
        out('[!] EXPLOITS:')
        for r in exploits:
            out(f"  {r['hd']:22}+{r['hm']:20}+{r['ha']:22}  {r['flags']}")

    return rows, exploits


def _mode_extreme(out, csv_dir, sim_fn, matches_per_scenario):
    """Testet vordefinierte Extremkombinationen."""
    out(f'── Extrem-Kombinations-Test ─────────────────────────────────────────')
    out(f'Je {matches_per_scenario:,} gespiegelte Matches pro Szenario')

    std_stats = _run_mirrored_batch(_make_tactic(), matches_per_scenario, sim_fn)
    rows = []
    exploits = []

    for sc in EXTREME_SCENARIOS:
        hd, hm, ha = sc['hd'], sc['hm'], sc['ha']
        if hd == 'standard' and hm == 'standard' and ha == 'standard':
            stats = std_stats
        else:
            t0 = time.time()
            stats = _run_mirrored_batch(_make_tactic(hd, hm, ha), matches_per_scenario, sim_fn)

        ppg_d = stats['ppg']  - std_stats['ppg']
        xgd_d = stats['xgd'] - std_stats['xgd']
        flags = [_ppg_flag(ppg_d), _xgd_flag(xgd_d)]
        flags = [f for f in flags if f]
        exploit = bool(flags)

        row = {
            'id': sc['id'], 'desc': sc['desc'],
            'hd': hd, 'hm': hm, 'ha': ha,
            'n': stats['n'], 'errors': stats['errors'],
            'ppg': stats['ppg'], 'ppg_delta': round(ppg_d, 4),
            'xgf': stats['xgf'], 'xga': stats['xga'],
            'xgd': stats['xgd'], 'xgd_delta': round(xgd_d, 4),
            'shots_f': stats['shots_f'], 'shots_a': stats['shots_a'],
            'poss': stats['poss'], 'fatigue': stats['fatigue'],
            'coherence': stats['coherence'],
            'flags': ' '.join(flags) if flags else 'OK',
            'exploit': exploit,
        }
        rows.append(row)
        if exploit:
            exploits.append(row)

        out(f"  {sc['id']:25}  PPG Δ={ppg_d:+.3f}  xGD Δ={xgd_d:+.4f}  "
            f"poss={stats['poss']:.1f}  fat={stats['fatigue']:.3f}  "
            f"coh={stats['coherence']:.3f}  {'[!] ' + row['flags'] if exploit else 'OK'}")

    if csv_dir:
        _write_csv(os.path.join(csv_dir, 'extreme_scenarios.csv'), rows)

    out(f'\nErgebnis: {len(rows)} Szenarien | EXPLOIT: {len(exploits)}')
    return rows, exploits


def _mode_halves(out, csv_dir, compile_fn, sim_fn, option, field, matches_per_test):
    """
    Halbzeit-Isolation:
    1. Compiler-Bleeding-Check (für 'option' in 'field')
    2. Simulation: Option nur 1H / nur 2H / beide / standard — Effekt-Aufteilung prüfen
    """
    out(f'── Halbzeit-Isolation: {field}.{option} ────────────────────────────────')

    # Compiler-Teil: alle neuen Optionen auf Bleeding prüfen
    compiler_rows = []
    options_to_check = (
        [('midfield', o) for o in NEW_MIDFIELD] +
        [('attack',   o) for o in NEW_ATTACK]
    )
    if option != 'all':
        options_to_check = [(field, option)]

    out('  Compiler Bleeding-Checks:')
    bleed_found = []
    for fld, opt in options_to_check:
        row = _compiler_check_halves(compile_fn, opt, fld)
        compiler_rows.append(row)
        status = row['bleeding']
        out(f"    {fld:8} {opt:22}  1H→2H_xgF={row['1h_only__2h_xgF']:.5f}  "
            f"2H→1H_xgF={row['2h_only__1h_xgF']:.5f}  {status}")
        if row['exploit']:
            bleed_found.append(row)

    if csv_dir:
        _write_csv(os.path.join(csv_dir, f'halves_compiler_{field}_{option}.csv'), compiler_rows)

    # Simulation-Teil (einzelne Option)
    out(f'\n  Simulation ({matches_per_test:,} Matches pro Konfiguration):')

    hd = option if field == 'defense'  else 'standard'
    hm = option if field == 'midfield' else 'standard'
    ha = option if field == 'attack'   else 'standard'

    configs = [
        ('std',    _make_tactic()),
        ('1H_only', _make_tactic(hd, hm, ha, apply_first=True,  apply_second=False)),
        ('2H_only', _make_tactic(hd, hm, ha, apply_first=False, apply_second=True)),
        ('both',    _make_tactic(hd, hm, ha, apply_first=True,  apply_second=True)),
    ]

    sim_rows = []
    std_stats = None
    for cfg_name, tactic in configs:
        stats = _run_mirrored_batch(tactic, matches_per_test, sim_fn)
        if cfg_name == 'std':
            std_stats = stats
        ppg_d = stats['ppg'] - (std_stats['ppg'] if std_stats else 0)
        xgd_d = stats['xgd'] - (std_stats['xgd'] if std_stats else 0)
        sim_rows.append({
            'config': cfg_name, 'option': option, 'field': field,
            'n': stats['n'],
            'ppg': stats['ppg'], 'ppg_delta': round(ppg_d, 4),
            'xgf': stats['xgf'], 'xga': stats['xga'], 'xgd': stats['xgd'],
            'xgd_delta': round(xgd_d, 4),
            'poss': stats['poss'], 'fatigue': stats['fatigue'],
        })
        out(f"    {cfg_name:10}  PPG={stats['ppg']:.3f} (Δ{ppg_d:+.3f})  "
            f"xGD={stats['xgd']:.3f} (Δ{xgd_d:+.3f})  "
            f"poss={stats['poss']:.1f}  fat={stats['fatigue']:.3f}")

    if csv_dir:
        _write_csv(os.path.join(csv_dir, f'halves_sim_{field}_{option}.csv'), sim_rows)

    # Sanity-Check: 1H_only + 2H_only ≈ both (ungefähr)
    r1h = next((r for r in sim_rows if r['config'] == '1H_only'), None)
    r2h = next((r for r in sim_rows if r['config'] == '2H_only'), None)
    rb  = next((r for r in sim_rows if r['config'] == 'both'),    None)
    if r1h and r2h and rb:
        sum_d  = r1h['xgd_delta'] + r2h['xgd_delta']
        both_d = rb['xgd_delta']
        diff   = abs(sum_d - both_d)
        if diff > 0.15:
            out(f"  [!] Additivitäts-Check: 1H+2H={sum_d:.3f}  both={both_d:.3f}  diff={diff:.3f} > 0.15")
        else:
            out(f"  Additivitäts-Check OK: 1H+2H≈both ({sum_d:.3f}≈{both_d:.3f}, diff={diff:.3f})")

    if bleed_found:
        out(f'  [!] BLEEDING GEFUNDEN bei: {[r["option"] for r in bleed_found]}')
    else:
        out('  Bleeding-Checks: NONE')

    return compiler_rows, sim_rows, bleed_found


# ─── Gesamt-Zusammenfassung ───────────────────────────────────────────────────

def _print_summary(out, all_exploits):
    out('\n' + '═' * 70)
    out('GESAMT-ZUSAMMENFASSUNG')
    out('═' * 70)
    if not all_exploits:
        out('  Keine Exploits gefunden — alle Linienoptionen in Ordnung.')
    else:
        out(f'  {len(all_exploits)} EXPLOIT(S) GEFUNDEN:')
        for item in all_exploits:
            out(f"  [!] {item}")
    out('═' * 70)


# ─── Management Command ───────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Exploit-Test für Halbzeit-Linienoptionen (Abwehr/Mittelfeld/Angriff)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode', default='compiler',
            choices=['compiler', 'single', 'matrix', 'extreme', 'halves', 'all'],
            help='Test-Modus',
        )
        parser.add_argument(
            '--matches', type=int, default=5000,
            help='Anzahl gespiegelter Match-Pairs pro Kombination/Option (Standard: 5000)',
        )
        parser.add_argument(
            '--strength', type=float, default=75.0,
            help='Einheitliche Spieler-Stärke für synthetische Teams (Standard: 75)',
        )
        parser.add_argument(
            '--output', default='.local/line_tactic_test',
            help='Verzeichnis für CSV-Ausgabedateien (leer = kein CSV)',
        )
        parser.add_argument(
            '--option', default='all',
            help='Option für --mode halves (z.B. nachruecken, all)',
        )
        parser.add_argument(
            '--field', default='midfield',
            choices=['defense', 'midfield', 'attack'],
            help='Feld für --mode halves (Standard: midfield)',
        )
        parser.add_argument(
            '--no-csv', action='store_true',
            help='Keine CSV-Dateien schreiben',
        )

    def handle(self, *args, **options):
        from game.tactic_compiler import compile_tactic
        from game.match_engine import _simulate_match_minutes  # noqa: PLC2701

        mode         = options['mode']
        matches      = options['matches']
        strength     = options['strength']
        csv_dir      = None if options['no_csv'] else options['output']
        opt_option   = options['option']
        opt_field    = options['field']

        if csv_dir:
            _ensure_dir(csv_dir)
            self.stdout.write(f'CSV-Ausgabe: {os.path.abspath(csv_dir)}')

        out = self.stdout.write
        all_exploits = []
        t_total = time.time()

        out('\n' + '═' * 70)
        out(f'TEST_LINE_TACTICS  |  Modus: {mode}  |  Matches/Kombo: {matches:,}'
            f'  |  Stärke: {strength}')
        out('═' * 70 + '\n')

        def _sim(home, away):
            return _simulate_match_minutes(home, away)

        def _compile(team, tactic, half='full'):
            return compile_tactic(team, tactic, half=half)

        if mode in ('compiler', 'all'):
            rows, exploits = _mode_compiler(out, csv_dir, _compile)
            all_exploits += [f"compiler:{r['hd']}+{r['hm']}+{r['ha']} → {r['flags']}"
                             for r in exploits]
            out('')

        if mode in ('single', 'all'):
            rows, exploits = _mode_single(out, csv_dir, _sim, matches)
            all_exploits += [f"single:{r['field']}.{r['option']} → {r['flags']}"
                             for r in exploits]
            out('')

        if mode in ('extreme', 'all'):
            rows, exploits = _mode_extreme(out, csv_dir, _sim, matches)
            all_exploits += [f"extreme:{r['id']} → {r['flags']}"
                             for r in exploits]
            out('')

        if mode in ('matrix', 'all'):
            rows, exploits = _mode_matrix(out, csv_dir, _sim, matches)
            all_exploits += [f"matrix:{r['hd']}+{r['hm']}+{r['ha']} → {r['flags']}"
                             for r in exploits]
            out('')

        if mode in ('halves', 'all'):
            opt = opt_option if mode == 'halves' else 'all'
            fld = opt_field  if mode == 'halves' else 'midfield'
            _, _, bleed = _mode_halves(out, csv_dir, _compile, _sim, opt, fld, min(matches, 2000))
            all_exploits += [f"bleed:{r['option']} → {r['bleeding']}"
                             for r in bleed]
            out('')

        _print_summary(out, all_exploits)

        elapsed = time.time() - t_total
        out(f'\nLaufzeit gesamt: {elapsed:.1f}s')

        if csv_dir:
            out(f'CSV-Dateien in: {os.path.abspath(csv_dir)}')
