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
  python manage.py test_line_tactics --mode single --matches 10000
  python manage.py test_line_tactics --mode matrix --matches 2000 --output .local/line_tactic_test/
  python manage.py test_line_tactics --mode halves --option nachruecken --field midfield
  python manage.py test_line_tactics --mode halves --option offensiv_besetzen --field midfield

EXPLOIT-KRITERIEN
  [CAP]       line_xg_for_applied > 0.060001 oder line_shots_applied > 0.080001
  [GRAT]      xgF↑ + xGA↓ + risk↓ + fatigue↓ gleichzeitig (Gratisvorteil ohne Kosten)
  [VERDACHT]  PPG-Delta > +0.04 UND xGD-Delta > +0.04 (≥10k Matches)
  [ALARM]     PPG-Delta > +0.06 UND xGD-Delta > +0.06
  [COHER]     Kohärenzstrafe tief_stehen+offensiv_besetzen+strafraum_besetzen ≠ 0.96
  [BLEED]     Halbzeit-Option beeinflusst die andere Halbzeit (Compiler-Check)
"""

import csv
import os
import time

from django.core.management.base import BaseCommand

# ─── Optionslisten ────────────────────────────────────────────────────────────
DEFENSE_OPTIONS  = ['standard', 'kompakt_stehen', 'tief_stehen', 'hoeher_stehen',
                    'absichern', 'frueh_herausruecken']
MIDFIELD_OPTIONS = ['standard', 'absichern', 'ballbesitz_sichern', 'nachruecken',
                    'offensiv_besetzen']
ATTACK_OPTIONS   = ['unterstuetzen', 'standard', 'abwehrkette_binden', 'strafraum_besetzen']

# Neue per-Halbzeit-Optionen (ohne 'standard')
NEW_MIDFIELD = ['absichern', 'ballbesitz_sichern', 'nachruecken', 'offensiv_besetzen']
NEW_ATTACK   = ['unterstuetzen', 'abwehrkette_binden', 'strafraum_besetzen']
ALL_NEW_OPTIONS = (
    [('midfield', o) for o in NEW_MIDFIELD] +
    [('attack',   o) for o in NEW_ATTACK]
)

EXTREME_SCENARIOS = [
    {'id': 'max_off_coherent',   'hd': 'hoeher_stehen', 'hm': 'offensiv_besetzen',
     'ha': 'strafraum_besetzen',
     'desc': 'hoeher_stehen + offensiv_besetzen + strafraum_besetzen (kohärent)'},
    {'id': 'max_off_incoherent', 'hd': 'tief_stehen',   'hm': 'offensiv_besetzen',
     'ha': 'strafraum_besetzen',
     'desc': 'tief_stehen + offensiv_besetzen + strafraum_besetzen (inkohärent, 0.96)'},
    {'id': 'max_defensive',      'hd': 'tief_stehen',   'hm': 'absichern',
     'ha': 'unterstuetzen',
     'desc': 'tief_stehen + absichern + unterstuetzen (max defensiv)'},
    {'id': 'ball_control',       'hd': 'standard',      'hm': 'ballbesitz_sichern',
     'ha': 'unterstuetzen',
     'desc': 'standard + ballbesitz_sichern + unterstuetzen (Ballkontrolle)'},
    {'id': 'moderate_offensive', 'hd': 'hoeher_stehen', 'hm': 'nachruecken',
     'ha': 'abwehrkette_binden',
     'desc': 'hoeher_stehen + nachruecken + abwehrkette_binden'},
    {'id': 'standard_baseline',  'hd': 'standard',      'hm': 'standard',
     'ha': 'standard',
     'desc': 'standard + standard + standard (Baseline)'},
]

# ─── Formation 4-4-2 ─────────────────────────────────────────────────────────
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


# ─── Builder ─────────────────────────────────────────────────────────────────

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
    players, lineup = [], []
    for s in _SLOTS_442:
        pid = s['player_id'] + id_offset
        players.append({
            'id': pid, 'name': f'P{pid}',
            'final_strength': float(strength),
            'main_positions': [s['position']], 'secondary_positions': [],
            'teamwork': 70, 'freshness': 100, 'is_ws_injured': False,
        })
        lineup.append({**s, 'player_id': pid})
    return {
        'team': {'name': f'SynTeam_{id_offset}', 'id': id_offset + 1},
        'players': players, 'lineup': lineup, 'tactic': tactic,
        'bench_player_data': {}, 'planned_substitutions': [],
    }


# ─── Match-Runner ─────────────────────────────────────────────────────────────

def _run_raw(home_team, away_team, sim_fn):
    r  = sim_fn(home_team, away_team)
    ms = r.get('match_stats', {})
    return {
        'hg': r['home_goals'], 'ag': r['away_goals'],
        'hxg': r.get('home_xg', 0.0), 'axg': r.get('away_xg', 0.0),
        'hsh': ms.get('home_shots', 0),    'ash': ms.get('away_shots', 0),
        'hpo': ms.get('home_possession', 50),
        'hfc': ms.get('home_fatigue_cost', 1.0),
        'afc': ms.get('away_fatigue_cost', 1.0),
        'hyl': ms.get('home_yellow', 0),   'ayl': ms.get('away_yellow', 0),
        'hrd': ms.get('home_red', 0),       'ard': ms.get('away_red', 0),
        'hco': ms.get('home_tactic_coherence', 1.0),
        'aco': ms.get('away_tactic_coherence', 1.0),
        'plan_acts': len(r.get('plan_activations', [])),
    }


def _from_home(r):
    return {'gf': r['hg'], 'ga': r['ag'], 'xgf': r['hxg'], 'xga': r['axg'],
            'sf': r['hsh'], 'sa': r['ash'], 'poss': r['hpo'],
            'fatigue': r['hfc'], 'yellow': r['hyl'], 'red': r['hrd'],
            'coherence': r['hco'], 'plan_acts': r['plan_acts']}


def _from_away(r):
    return {'gf': r['ag'], 'ga': r['hg'], 'xgf': r['axg'], 'xga': r['hxg'],
            'sf': r['ash'], 'sa': r['hsh'], 'poss': 100 - r['hpo'],
            'fatigue': r['afc'], 'yellow': r['ayl'], 'red': r['ard'],
            'coherence': r['aco'], 'plan_acts': r['plan_acts']}


def _run_mirrored_batch(tactic_a, n, sim_fn, strength=75):
    """n//2 Heimspiele + n//2 Auswärtsspiele — eliminiert Home-Advantage-Bias."""
    tactic_std = _make_tactic()
    n_home = n // 2
    n_away = n - n_home

    team_a_h  = _make_team(tactic_a,   strength, id_offset=0)
    team_s_a  = _make_team(tactic_std, strength, id_offset=100)
    team_s_h  = _make_team(tactic_std, strength, id_offset=0)
    team_a_a  = _make_team(tactic_a,   strength, id_offset=100)

    rows, errors = [], 0
    for _ in range(n_home):
        try:
            rows.append(_from_home(_run_raw(team_a_h, team_s_a, sim_fn)))
        except Exception:
            errors += 1
    for _ in range(n_away):
        try:
            rows.append(_from_away(_run_raw(team_s_h, team_a_a, sim_fn)))
        except Exception:
            errors += 1
    return _aggregate(rows, errors)


def _aggregate(rows, errors=0):
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
        'n': n, 'errors': errors,
        'wins': wins, 'draws': draws, 'losses': losses,
        'ppg':     round(ppg, 4),
        'gf':      round(avg('gf'),  4),
        'ga':      round(avg('ga'),  4),
        'gd':      round(avg('gf') - avg('ga'), 4),
        'xgf':     round(avg('xgf'), 4),
        'xga':     round(avg('xga'), 4),
        'xgd':     round(avg('xgf') - avg('xga'), 4),
        'shots_f': round(avg('sf'),  4),
        'shots_a': round(avg('sa'),  4),
        'poss':    round(avg('poss'), 2),
        'fatigue': round(avg('fatigue'), 4),
        'yellow':  round(avg('yellow'), 4),
        'red':     round(avg('red'), 4),
        'coherence': round(avg('coherence'), 4),
        'plan_acts': round(avg('plan_acts'), 3),
    }


# ─── Exploit-Flag-Logik ────────────────────────────────────────────────────────

def _match_exploit_flags(ppg_d, xgd_d, n_matches):
    """
    Kombinierte Schwellen (beide Metriken müssen überschritten sein):
      [VERDACHT] PPG > +0.04 UND xGD > +0.04
      [ALARM]    PPG > +0.06 UND xGD > +0.06
    """
    flags = []
    if ppg_d > 0.06 and xgd_d > 0.06:
        flags.append('[ALARM]')
    elif ppg_d > 0.04 and xgd_d > 0.04:
        flags.append('[VERDACHT]' if n_matches >= 5000 else '[?VERDACHT<5k]')
    return flags


# ─── Compiler-Check ───────────────────────────────────────────────────────────

def _compiler_check(compile_fn, hd, hm, ha, half='both'):
    tactic  = _make_tactic(hd, hm, ha)
    team    = _make_team(tactic)
    h       = 'first' if half in ('first', 'both') else 'second'
    profile = compile_fn(team, tactic, half=h)
    dbg     = profile.get('debug', {})

    xg_app = dbg.get('line_xg_for_applied', 0.0)
    sh_app = dbg.get('line_shots_applied', 0.0)
    xg_raw = dbg.get('line_xg_for_raw', 0.0)
    sh_raw = dbg.get('line_shots_raw', 0.0)
    risk   = dbg.get('line_risk', 0.0)
    fat    = dbg.get('line_fatigue', 0.0)
    xga    = dbg.get('line_xg_against', 0.0)
    poss   = dbg.get('line_possession', 0.0)
    coh    = profile.get('coherence', 1.0)

    flags = []
    if xg_app > 0.060001:
        flags.append(f'[CAP:xgF={xg_app:.5f}]')
    if sh_app > 0.080001:
        flags.append(f'[CAP:shots={sh_app:.5f}]')
    # Gratisvorteil: mehr xGF, weniger xGA, weniger Risiko, weniger Fatigue
    if xg_app > _EPS and xga < -_EPS and risk < -_EPS and fat < -_EPS:
        flags.append('[GRAT]')
    # Kohärenzfehler bei bekannter inkohärenter Kombo
    if (hd == 'tief_stehen' and hm == 'offensiv_besetzen'
            and ha == 'strafraum_besetzen'):
        expected = round(1.0 - 0.04, 4)
        if abs(coh - expected) > 0.001:
            flags.append(f'[COHER:erw={expected},ist={coh:.4f}]')

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
        'xg_for_final':     round(profile.get('xg_for', 1.0), 4),
        'xg_against_final': round(profile.get('xg_against', 1.0), 4),
        'shot_volume':      round(profile.get('shot_volume', 1.0), 4),
        'fatigue_cost':     round(profile.get('fatigue_cost', 1.0), 4),
        'flags':   ' '.join(flags) if flags else 'OK',
        'exploit': bool(flags),
    }


def _compiler_check_halves(compile_fn, option, field):
    hd = option if field == 'defense'  else 'standard'
    hm = option if field == 'midfield' else 'standard'
    ha = option if field == 'attack'   else 'standard'

    def _dbg_xgf(profile):
        return profile.get('debug', {}).get('line_xg_for_applied', 0.0)

    tactic_1h = _make_tactic(hd, hm, ha, apply_first=True,  apply_second=False)
    tactic_2h = _make_tactic(hd, hm, ha, apply_first=False, apply_second=True)
    tactic_b  = _make_tactic(hd, hm, ha)
    tactic_s  = _make_tactic()

    team_1h = _make_team(tactic_1h)
    team_2h = _make_team(tactic_2h)
    team_b  = _make_team(tactic_b)
    team_s  = _make_team(tactic_s)

    p1h_1 = compile_fn(team_1h, tactic_1h, half='first')
    p1h_2 = compile_fn(team_1h, tactic_1h, half='second')
    p2h_1 = compile_fn(team_2h, tactic_2h, half='first')
    p2h_2 = compile_fn(team_2h, tactic_2h, half='second')
    pb_1  = compile_fn(team_b,  tactic_b,  half='first')
    pb_2  = compile_fn(team_b,  tactic_b,  half='second')
    ps_1  = compile_fn(team_s,  tactic_s,  half='first')
    ps_2  = compile_fn(team_s,  tactic_s,  half='second')

    bleed = []
    if abs(_dbg_xgf(p1h_2) - _dbg_xgf(ps_2)) > _EPS:
        bleed.append(f'[BLEED:1H→2H xgFΔ={_dbg_xgf(p1h_2) - _dbg_xgf(ps_2):.5f}]')
    if abs(_dbg_xgf(p2h_1) - _dbg_xgf(ps_1)) > _EPS:
        bleed.append(f'[BLEED:2H→1H xgFΔ={_dbg_xgf(p2h_1) - _dbg_xgf(ps_1):.5f}]')

    return {
        'option': option, 'field': field,
        '1h_only__1h_xgF': round(_dbg_xgf(p1h_1), 5),
        '1h_only__2h_xgF': round(_dbg_xgf(p1h_2), 5),
        '2h_only__1h_xgF': round(_dbg_xgf(p2h_1), 5),
        '2h_only__2h_xgF': round(_dbg_xgf(p2h_2), 5),
        'both__1h_xgF':    round(_dbg_xgf(pb_1), 5),
        'both__2h_xgF':    round(_dbg_xgf(pb_2), 5),
        'std__1h_xgF':     round(_dbg_xgf(ps_1), 5),
        'std__2h_xgF':     round(_dbg_xgf(ps_2), 5),
        '1h_only__xgF_final': round(p1h_1.get('xg_for', 1.0), 4),
        '2h_only__xgF_final': round(p2h_2.get('xg_for', 1.0), 4),
        'bleeding': ' '.join(bleed) if bleed else 'NONE',
        'exploit':  bool(bleed),
    }


# ─── CSV-Helfer ───────────────────────────────────────────────────────────────

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


# ─── Modus-Handler ────────────────────────────────────────────────────────────

def _mode_compiler(out, csv_dir, compile_fn):
    out('── Compiler-Check aller 120 Kombinationen ──────────────────────────')
    rows, exploits = [], []
    for hd in DEFENSE_OPTIONS:
        for hm in MIDFIELD_OPTIONS:
            for ha in ATTACK_OPTIONS:
                row = _compiler_check(compile_fn, hd, hm, ha)
                rows.append(row)
                if row['exploit']:
                    exploits.append(row)

    if csv_dir:
        _write_csv(os.path.join(csv_dir, 'compiler_all_combos.csv'), rows)

    ok = len(rows) - len(exploits)
    out(f'Gesamt: {len(rows)} Kombos | OK: {ok} | EXPLOIT: {len(exploits)}')

    if exploits:
        out('\n[!] EXPLOITS:')
        for r in exploits:
            out(f"  {r['hd']:22}+{r['hm']:20}+{r['ha']:22}  →  {r['flags']}")
    else:
        out('Keine Exploits detektiert.')

    std = _compiler_check(compile_fn, 'standard', 'standard', 'standard')
    out(f'\nBaseline:  xgF_applied={std["xg_for_applied"]:.5f}  '
        f'shots_applied={std["shots_applied"]:.5f}  '
        f'coherence={std["coherence"]:.4f}  flags={std["flags"]}')

    return rows, exploits


def _mode_single(out, csv_dir, sim_fn, compile_fn, n):
    out(f'── Einzeloptions-Test ──────────────────────────────────────────────')
    out(f'Je {n:,} gespiegelte Matches pro Option')
    out(f'{"Feld":8} {"Option":22}  {"PPG-Δ":>7}  {"xGF-Δ":>7}  '
        f'{"xGA-Δ":>7}  {"xGD-Δ":>7}  {"Schüsse↑":>8}  '
        f'{"Bstz":>5}  {"risk":>7}  {"fat":>7}  {"coh":>6}  {"n":>7}  Flags')
    out('─' * 120)

    std_sim = _run_mirrored_batch(_make_tactic(), n, sim_fn)
    rows, exploits = [], []

    for field, option in ALL_NEW_OPTIONS:
        hd = option if field == 'defense'  else 'standard'
        hm = option if field == 'midfield' else 'standard'
        ha = option if field == 'attack'   else 'standard'

        t0    = time.time()
        stats = _run_mirrored_batch(_make_tactic(hd, hm, ha), n, sim_fn)
        cinfo = _compiler_check(compile_fn, hd, hm, ha)

        ppg_d = stats['ppg']  - std_sim['ppg']
        xgf_d = stats['xgf'] - std_sim['xgf']
        xga_d = stats['xga'] - std_sim['xga']
        xgd_d = stats['xgd'] - std_sim['xgd']
        sf_d  = stats['shots_f'] - std_sim['shots_f']

        flags = _match_exploit_flags(ppg_d, xgd_d, n)
        # Auch CAP-Flags aus Compiler hinzufügen
        if cinfo['flags'] != 'OK':
            flags += [cinfo['flags']]
        exploit = bool(flags)

        row = {
            'field': field, 'option': option,
            'n': stats['n'], 'errors': stats['errors'],
            'ppg': stats['ppg'], 'ppg_delta': round(ppg_d, 4),
            'xgf': stats['xgf'], 'xgf_delta': round(xgf_d, 4),
            'xga': stats['xga'], 'xga_delta': round(xga_d, 4),
            'xgd': stats['xgd'], 'xgd_delta': round(xgd_d, 4),
            'shots_f': stats['shots_f'], 'shots_delta': round(sf_d, 4),
            'poss': stats['poss'],
            'fatigue_sim': stats['fatigue'],
            'coherence': stats['coherence'],
            # Compiler-Werte (Linien-Deltas)
            'c_xgF_raw':  cinfo['xg_for_raw'],
            'c_xgF_app':  cinfo['xg_for_applied'],
            'c_xGA':      cinfo['xg_against'],
            'c_risk':     cinfo['risk'],
            'c_fatigue':  cinfo['fatigue'],
            'c_poss':     cinfo['possession'],
            'c_coherence':cinfo['coherence'],
            'flags': ' '.join(flags) if flags else 'OK',
            'exploit': exploit,
            'elapsed_s': round(time.time() - t0, 1),
        }
        rows.append(row)
        if exploit:
            exploits.append(row)

        flag_str = ' '.join(flags) if flags else 'OK'
        out(f'  {field:8} {option:22}  {ppg_d:+7.3f}  {xgf_d:+7.4f}  '
            f'{xga_d:+7.4f}  {xgd_d:+7.4f}  {sf_d:+8.3f}  '
            f'{stats["poss"]:5.1f}  {cinfo["risk"]:+7.4f}  '
            f'{cinfo["fatigue"]:+7.4f}  {cinfo["coherence"]:6.4f}  '
            f'{stats["n"]:>7,}  {flag_str}')

    if csv_dir:
        _write_csv(os.path.join(csv_dir, 'single_option_test.csv'), rows)

    out(f'\nErgebnis: {len(rows)} Optionen | EXPLOIT: {len(exploits)}')
    if exploits:
        out('[!] ' + ', '.join(f'{r["field"]}.{r["option"]}({r["flags"]})' for r in exploits))

    return rows, exploits


def _mode_extreme(out, csv_dir, sim_fn, compile_fn, n):
    out(f'── Extrem-Kombinations-Test ─────────────────────────────────────────')
    out(f'Je {n:,} gespiegelte Matches | 6 Szenarien')
    out(f'{"Szenario":25}  {"PPG-Δ":>7}  {"xGF":>6}  {"xGA":>6}  '
        f'{"xGD-Δ":>7}  {"Bstz":>5}  {"fat":>7}  {"coh":>6}  '
        f'{"c_risk":>7}  {"c_xgF_app":>10}  Flags')
    out('─' * 120)

    std_sim = _run_mirrored_batch(_make_tactic(), n, sim_fn)
    rows, exploits = [], []

    for sc in EXTREME_SCENARIOS:
        hd, hm, ha = sc['hd'], sc['hm'], sc['ha']
        if hd == 'standard' and hm == 'standard' and ha == 'standard':
            stats = std_sim
        else:
            stats = _run_mirrored_batch(_make_tactic(hd, hm, ha), n, sim_fn)

        cinfo = _compiler_check(compile_fn, hd, hm, ha)
        ppg_d = stats['ppg']  - std_sim['ppg']
        xgd_d = stats['xgd'] - std_sim['xgd']
        flags = _match_exploit_flags(ppg_d, xgd_d, n)
        if cinfo['flags'] != 'OK':
            flags += [cinfo['flags']]
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
            'c_xgF_raw': cinfo['xg_for_raw'],
            'c_xgF_app': cinfo['xg_for_applied'],
            'c_xGA':     cinfo['xg_against'],
            'c_risk':    cinfo['risk'],
            'c_fatigue': cinfo['fatigue'],
            'c_coherence': cinfo['coherence'],
            'flags': ' '.join(flags) if flags else 'OK',
            'exploit': exploit,
        }
        rows.append(row)
        if exploit:
            exploits.append(row)

        flag_str = ' '.join(flags) if flags else 'OK'
        out(f'  {sc["id"]:25}  {ppg_d:+7.3f}  {stats["xgf"]:6.3f}  '
            f'{stats["xga"]:6.3f}  {xgd_d:+7.4f}  {stats["poss"]:5.1f}  '
            f'{cinfo["fatigue"]:+7.4f}  {cinfo["coherence"]:6.4f}  '
            f'{cinfo["risk"]:+7.4f}  {cinfo["xg_for_applied"]:10.5f}  {flag_str}')

    if csv_dir:
        _write_csv(os.path.join(csv_dir, 'extreme_scenarios.csv'), rows)

    out(f'\nErgebnis: {len(rows)} Szenarien | EXPLOIT: {len(exploits)}')
    if exploits:
        out('[!] EXPLOITS: ' + ', '.join(f'{r["id"]}({r["flags"]})' for r in exploits))

    # Kohärenz-Vergleich (kohärent vs. inkohärent max-offensiv)
    r_coh = next((r for r in rows if r['id'] == 'max_off_coherent'),   None)
    r_inc = next((r for r in rows if r['id'] == 'max_off_incoherent'), None)
    if r_coh and r_inc:
        ppg_d_coh = r_coh['ppg_delta']
        ppg_d_inc = r_inc['ppg_delta']
        xgd_d_inc = r_inc['xgd_delta']
        out(f'\nKohärenz-Vergleich: kohärent PPG-Δ={ppg_d_coh:+.3f}  '
            f'inkohärent PPG-Δ={ppg_d_inc:+.3f}  '
            f'(inkohärent darf kohärent langfristig nicht übertreffen)')
        if ppg_d_inc > ppg_d_coh + 0.02:
            out('  [!] WARNUNG: Inkohärente Variante übertrifft kohärente!')

    return rows, exploits


def _mode_matrix(out, csv_dir, sim_fn, compile_fn, n):
    out(f'── Matrix-Test 6×5×4=120 Kombos ────────────────────────────────────')
    out(f'Je {n:,} gespiegelte Matches | Gesamt: {120 * n:,} Match-Pairs')

    std_sim = _run_mirrored_batch(_make_tactic(), n, sim_fn)
    rows, exploits = [], []
    done, total = 0, 120
    t_start = time.time()

    for hd in DEFENSE_OPTIONS:
        for hm in MIDFIELD_OPTIONS:
            for ha in ATTACK_OPTIONS:
                stats = _run_mirrored_batch(_make_tactic(hd, hm, ha), n, sim_fn)
                cinfo = _compiler_check(compile_fn, hd, hm, ha)
                ppg_d = stats['ppg']  - std_sim['ppg']
                xgd_d = stats['xgd'] - std_sim['xgd']
                flags = _match_exploit_flags(ppg_d, xgd_d, n)
                if cinfo['flags'] != 'OK':
                    flags += [cinfo['flags']]
                exploit = bool(flags)

                row = {
                    'hd': hd, 'hm': hm, 'ha': ha,
                    'n': stats['n'], 'errors': stats['errors'],
                    'ppg': stats['ppg'], 'ppg_delta': round(ppg_d, 4),
                    'xgf': stats['xgf'], 'xgf_delta': round(stats['xgf'] - std_sim['xgf'], 4),
                    'xga': stats['xga'], 'xga_delta': round(stats['xga'] - std_sim['xga'], 4),
                    'xgd': stats['xgd'], 'xgd_delta': round(xgd_d, 4),
                    'shots_f': stats['shots_f'], 'shots_a': stats['shots_a'],
                    'poss': stats['poss'], 'fatigue': stats['fatigue'],
                    'coherence': stats['coherence'],
                    'c_xgF_raw': cinfo['xg_for_raw'],
                    'c_xgF_app': cinfo['xg_for_applied'],
                    'c_xGA':     cinfo['xg_against'],
                    'c_risk':    cinfo['risk'],
                    'c_fatigue': cinfo['fatigue'],
                    'c_coherence': cinfo['coherence'],
                    'flags': ' '.join(flags) if flags else 'OK',
                    'exploit': exploit,
                }
                rows.append(row)
                if exploit:
                    exploits.append(row)

                done += 1
                elapsed = time.time() - t_start
                eta     = (elapsed / done) * (total - done)
                status  = '[!]' if exploit else ' ok'
                out(f'  [{done:3}/{total}] {hd:22}+{hm:20}+{ha:20}  '
                    f'PPG Δ={ppg_d:+.3f}  xGD Δ={xgd_d:+.4f}  {status}  '
                    f'ETA {eta:.0f}s', ending='\r' if done < total else '\n')

    out('')
    if csv_dir:
        _write_csv(os.path.join(csv_dir, 'matrix_all_combos.csv'), rows)

    out(f'Gesamt: {len(rows)} Kombos | OK: {sum(1 for r in rows if not r["exploit"])} | '
        f'EXPLOIT: {len(exploits)}')
    if exploits:
        out('[!] EXPLOITS:')
        for r in exploits:
            out(f"  {r['hd']:22}+{r['hm']:20}+{r['ha']:22}  {r['flags']}")

    # Top-5-Verdächtige nach PPG + xGD
    if csv_dir and rows:
        top5_ppg = sorted(rows, key=lambda r: r['ppg_delta'], reverse=True)[:5]
        top5_xgd = sorted(rows, key=lambda r: r['xgd_delta'], reverse=True)[:5]
        out('\nTop-5 nach PPG-Delta:')
        for r in top5_ppg:
            out(f"  {r['hd']:22}+{r['hm']:20}+{r['ha']:20}  PPG Δ={r['ppg_delta']:+.3f}  "
                f"xGD Δ={r['xgd_delta']:+.4f}  {r['flags']}")
        out('\nTop-5 nach xGD-Delta:')
        for r in top5_xgd:
            out(f"  {r['hd']:22}+{r['hm']:20}+{r['ha']:20}  xGD Δ={r['xgd_delta']:+.4f}  "
                f"PPG Δ={r['ppg_delta']:+.3f}  {r['flags']}")

    return rows, exploits


def _mode_halves(out, csv_dir, compile_fn, sim_fn, option, field, n):
    out(f'── Halbzeit-Isolation: {field}.{option} ──────────────────────────────')

    if option == 'all':
        options_to_check = (
            [('midfield', o) for o in NEW_MIDFIELD] +
            [('attack',   o) for o in NEW_ATTACK]
        )
    else:
        options_to_check = [(field, option)]

    out('  Compiler Bleeding-Checks:')
    out(f'  {"Feld":8} {"Option":22}  {"1H-aktiv→1H":12}  '
        f'{"1H-aktiv→2H":12}  {"2H-aktiv→1H":12}  {"2H-aktiv→2H":12}  Status')
    out('  ' + '─' * 90)

    compiler_rows, bleed_found = [], []
    for fld, opt in options_to_check:
        row = _compiler_check_halves(compile_fn, opt, fld)
        compiler_rows.append(row)
        out(f'  {fld:8} {opt:22}  '
            f'{row["1h_only__1h_xgF"]:12.5f}  '
            f'{row["1h_only__2h_xgF"]:12.5f}  '
            f'{row["2h_only__1h_xgF"]:12.5f}  '
            f'{row["2h_only__2h_xgF"]:12.5f}  '
            f'{row["bleeding"]}')
        if row['exploit']:
            bleed_found.append(row)

    if csv_dir:
        tag = f'{field}_{option}'
        _write_csv(os.path.join(csv_dir, f'halves_compiler_{tag}.csv'), compiler_rows)

    # Simulation (nur wenn eine spezifische Option gewählt)
    sim_rows = []
    if option != 'all':
        out(f'\n  Simulation ({n:,} Matches je Konfiguration):')
        hd = option if field == 'defense'  else 'standard'
        hm = option if field == 'midfield' else 'standard'
        ha = option if field == 'attack'   else 'standard'

        configs = [
            ('std',     _make_tactic()),
            ('1H_only', _make_tactic(hd, hm, ha, apply_first=True,  apply_second=False)),
            ('2H_only', _make_tactic(hd, hm, ha, apply_first=False, apply_second=True)),
            ('beide',   _make_tactic(hd, hm, ha, apply_first=True,  apply_second=True)),
        ]
        std_stats = None
        for cfg, tactic in configs:
            s = _run_mirrored_batch(tactic, n, sim_fn)
            if cfg == 'std':
                std_stats = s
            ppg_d = s['ppg'] - (std_stats['ppg'] if std_stats else 0)
            xgd_d = s['xgd'] - (std_stats['xgd'] if std_stats else 0)
            sr = {
                'config': cfg, 'option': option, 'field': field, 'n': s['n'],
                'ppg': s['ppg'], 'ppg_delta': round(ppg_d, 4),
                'xgf': s['xgf'], 'xga': s['xga'], 'xgd': s['xgd'],
                'xgd_delta': round(xgd_d, 4),
                'poss': s['poss'], 'fatigue': s['fatigue'],
            }
            sim_rows.append(sr)
            out(f'    {cfg:10}  PPG={s["ppg"]:.3f} (Δ{ppg_d:+.3f})  '
                f'xGF={s["xgf"]:.3f}  xGA={s["xga"]:.3f}  '
                f'xGD={s["xgd"]:.3f} (Δ{xgd_d:+.3f})  '
                f'poss={s["poss"]:.1f}  fat={s["fatigue"]:.3f}')

        if csv_dir:
            _write_csv(os.path.join(csv_dir, f'halves_sim_{field}_{option}.csv'), sim_rows)

        # Additivitäts-Sanity
        r1h  = next((r for r in sim_rows if r['config'] == '1H_only'), None)
        r2h  = next((r for r in sim_rows if r['config'] == '2H_only'), None)
        rb   = next((r for r in sim_rows if r['config'] == 'beide'),   None)
        if r1h and r2h and rb:
            sum_d  = r1h['xgd_delta'] + r2h['xgd_delta']
            both_d = rb['xgd_delta']
            diff   = abs(sum_d - both_d)
            status = 'OK' if diff <= 0.15 else '[!] diff > 0.15'
            out(f'\n  Additivitäts-Check: 1H+2H={sum_d:.3f}  beide={both_d:.3f}  '
                f'diff={diff:.3f}  {status}')

    if bleed_found:
        out(f'\n  [!] BLEEDING: {[r["option"] for r in bleed_found]}')
    else:
        out('\n  Bleeding-Checks: NONE — keine Halbzeit-Überträge')

    return compiler_rows, sim_rows, bleed_found


# ─── Gesamt-Zusammenfassung ───────────────────────────────────────────────────

def _print_summary(out, all_exploits):
    out('\n' + '═' * 70)
    out('GESAMT-ZUSAMMENFASSUNG')
    out('═' * 70)
    if not all_exploits:
        out('  Keine Exploits/Alarme — alle Linienoptionen in Ordnung.')
    else:
        out(f'  {len(all_exploits)} EXPLOIT(S)/ALARM(E):')
        for item in all_exploits:
            out(f'  [!] {item}')
    out('═' * 70)


# ─── Command ─────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Exploit-Test für Halbzeit-Linienoptionen (Abwehr/Mittelfeld/Angriff)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode', default='compiler',
            choices=['compiler', 'single', 'matrix', 'extreme', 'halves', 'all'],
        )
        parser.add_argument('--matches', type=int, default=5000,
                            help='Gespiegelte Match-Pairs pro Kombo (Standard: 5000)')
        parser.add_argument('--strength', type=float, default=75.0,
                            help='Einheitliche Spielerstärke (Standard: 75)')
        parser.add_argument('--output', default='.local/line_tactic_test',
                            help='Verzeichnis für CSV-Ausgabe')
        parser.add_argument('--option', default='all',
                            help='Option für --mode halves (z.B. nachruecken, all)')
        parser.add_argument('--field', default='midfield',
                            choices=['defense', 'midfield', 'attack'])
        parser.add_argument('--no-csv', action='store_true',
                            help='Keine CSV-Dateien schreiben')

    def handle(self, *args, **options):
        from game.tactic_compiler import compile_tactic
        from game.match_engine import _simulate_match_minutes  # noqa: PLC2701

        mode       = options['mode']
        n          = options['matches']
        csv_dir    = None if options['no_csv'] else options['output']
        opt_option = options['option']
        opt_field  = options['field']

        if csv_dir:
            _ensure_dir(csv_dir)
            self.stdout.write(f'CSV → {os.path.abspath(csv_dir)}')

        out = self.stdout.write
        all_exploits = []
        t0 = time.time()

        out('\n' + '═' * 70)
        out(f'TEST_LINE_TACTICS  |  Modus: {mode}  |  Matches/Kombo: {n:,}'
            f'  |  Stärke: {options["strength"]}')
        out('═' * 70 + '\n')

        def _sim(home, away):
            return _simulate_match_minutes(home, away)

        def _compile(team, tactic, half='full'):
            return compile_tactic(team, tactic, half=half)

        if mode in ('compiler', 'all'):
            _, ex = _mode_compiler(out, csv_dir, _compile)
            all_exploits += [f'compiler:{r["hd"]}+{r["hm"]}+{r["ha"]}→{r["flags"]}' for r in ex]
            out('')

        if mode in ('single', 'all'):
            _, ex = _mode_single(out, csv_dir, _sim, _compile, n)
            all_exploits += [f'single:{r["field"]}.{r["option"]}→{r["flags"]}' for r in ex]
            out('')

        if mode in ('extreme', 'all'):
            _, ex = _mode_extreme(out, csv_dir, _sim, _compile, n)
            all_exploits += [f'extreme:{r["id"]}→{r["flags"]}' for r in ex]
            out('')

        if mode in ('matrix', 'all'):
            _, ex = _mode_matrix(out, csv_dir, _sim, _compile, n)
            all_exploits += [f'matrix:{r["hd"]}+{r["hm"]}+{r["ha"]}→{r["flags"]}' for r in ex]
            out('')

        if mode in ('halves', 'all'):
            opt = opt_option if mode == 'halves' else 'all'
            fld = opt_field  if mode == 'halves' else 'midfield'
            _, _, bleed = _mode_halves(out, csv_dir, _compile, _sim, opt, fld,
                                       min(n, 2000))
            all_exploits += [f'bleed:{r["option"]}→{r["bleeding"]}' for r in bleed]
            out('')

        _print_summary(out, all_exploits)
        out(f'Laufzeit gesamt: {time.time() - t0:.1f}s')
        if csv_dir:
            out(f'CSV in: {os.path.abspath(csv_dir)}')
