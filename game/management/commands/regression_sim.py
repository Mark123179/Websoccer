"""Regressionsbericht V3 — 100 vollständige Bundesliga-Saisons (kein ORM).

Aufruf:
  python manage.py regression_sim                        # 100 Saisons, seed=42
  python manage.py regression_sim --seeds 1,7,21,42,99  # Multi-Seed-Stabilitätstest
  python manage.py regression_sim --seasons 10           # schneller Test
  python manage.py regression_sim --games 3400           # V1-kompatibler Schnellmodus
  python manage.py regression_sim --output /tmp/reg_out

Sektionen:
  A  Technische Integrität
  B  Match- und Ergebnisverteilung  (inkl. Scoreline-Matrix, Tordifferenz)
  C  Tabelle und Stärkeverhalten    (inkl. Ø GD, Bias per Club)
  D  Heimvorteil, Stärke-Brackets, Wechsel  (inkl. Heim nach Stärkeverhältnis)
  E  Verletzungen (inkl. Frische-Buckets), Frische (inkl. Saison-Kurve), Ticker
  F  Laufzeit und Performance
  G  Taktik-Balance (6 Profile, strength-adjustiertes Δ)
  H  Formations-Balance (5 Formationen, HP/NP/FP)
  I  Spielverlauf und Comebacks
  J  Saisonstreuung und Extremwerte
  K  Konfidenzintervalle (95%-KI)
"""
from __future__ import annotations
import csv
import json
import math
import os
import random
import time
from collections import defaultdict
from django.core.management.base import BaseCommand
from game.match_engine import (
    _simulate_match_minutes, MAX_SUBSTITUTIONS, _generate_injury_events,
)


# ── Klubkonstanten ────────────────────────────────────────────────────────────

CLUBS = [
    {'id': 1,  'name': 'Bayern',     'strength': 83.0},
    {'id': 2,  'name': 'Dortmund',   'strength': 79.0},
    {'id': 3,  'name': 'Leipzig',    'strength': 77.0},
    {'id': 4,  'name': 'Frankfurt',  'strength': 74.0},
    {'id': 5,  'name': 'Leverkusen', 'strength': 74.0},
    {'id': 6,  'name': 'Wolfsburg',  'strength': 71.0},
    {'id': 7,  'name': 'Freiburg',   'strength': 70.0},
    {'id': 8,  'name': 'Hoffenheim', 'strength': 69.0},
    {'id': 9,  'name': 'Bremen',     'strength': 68.0},
    {'id': 10, 'name': 'Gladbach',   'strength': 67.0},
    {'id': 11, 'name': 'Köln',       'strength': 66.0},
    {'id': 12, 'name': 'Stuttgart',  'strength': 66.0},
    {'id': 13, 'name': 'Augsburg',   'strength': 65.0},
    {'id': 14, 'name': 'Mainz',      'strength': 65.0},
    {'id': 15, 'name': 'Bochum',     'strength': 63.0},
    {'id': 16, 'name': 'Schalke',    'strength': 63.0},
    {'id': 17, 'name': 'Heidenheim', 'strength': 62.0},
    {'id': 18, 'name': 'Darmstadt',  'strength': 61.0},
]
N_CLUBS   = len(CLUBS)
CID_INDEX = {c['id']: i for i, c in enumerate(CLUBS)}

# Basis-Aufstellung (4-4-2 / Standard)
SLOTS = [
    ('TW', 'goalkeeper'),
    ('LV', 'defense'), ('IV', 'defense'), ('IV', 'defense'), ('RV', 'defense'),
    ('LM', 'midfield'), ('ZM', 'midfield'), ('ZM', 'midfield'), ('RM', 'midfield'),
    ('ST', 'attack'), ('ST', 'attack'),
]
BENCH_POS   = ['ST', 'ZM', 'LV', 'ZM', 'ST', 'IV', 'LM']
N_STARTERS  = len(SLOTS)
N_BENCH     = len(BENCH_POS)

# ── Taktik-Profile (G) ────────────────────────────────────────────────────────

_TACTIC_PROFILES: dict[str, dict] = {
    'normal': {},
    'offensiv': {
        'first_half':  {'orientation': 70, 'effort': 'hoch'},
        'second_half': {'orientation': 75, 'effort': 'hoch'},
    },
    'defensiv': {
        'first_half':  {'orientation': 30, 'effort': 'normal'},
        'second_half': {'orientation': 25, 'effort': 'normal'},
    },
    'konter': {
        'first_half':  {'orientation': 35},
        'second_half': {'orientation': 38},
        'defending':   {'umschalten': 'konter'},
        'buildup':     {'tempo': 65},
    },
    'hoch_pressing': {
        'pressing':    {'defense': 'hoch', 'midfield': 'intensiv', 'attack': 'intensiv'},
        'first_half':  {'orientation': 55, 'effort': 'sehr_hoch'},
        'second_half': {'orientation': 55, 'effort': 'hoch'},
    },
    'tief_stehend': {
        'pressing':    {'defense': 'passiv', 'midfield': 'normal', 'attack': 'normal'},
        'buildup':     {'defense_height': 'tief', 'tempo': 35},
        'first_half':  {'orientation': 35},
        'second_half': {'orientation': 35},
        'defending':   {'umschalten': 'ballbesitz'},
    },
}
_TACTIC_KEYS = list(_TACTIC_PROFILES.keys())

# ── Formations-Slots (H) ──────────────────────────────────────────────────────

_FORMATION_SLOTS: dict[str, list[tuple[str, str]]] = {
    '4-4-2': [
        ('TW', 'goalkeeper'),
        ('LV', 'defense'), ('IV', 'defense'), ('IV', 'defense'), ('RV', 'defense'),
        ('LM', 'midfield'), ('ZM', 'midfield'), ('ZM', 'midfield'), ('RM', 'midfield'),
        ('ST', 'attack'), ('ST', 'attack'),
    ],
    '4-3-3': [
        ('TW', 'goalkeeper'),
        ('LV', 'defense'), ('IV', 'defense'), ('IV', 'defense'), ('RV', 'defense'),
        ('ZM', 'midfield'), ('ZM', 'midfield'), ('ZM', 'midfield'),
        ('LF', 'attack'), ('ST', 'attack'), ('RF', 'attack'),
    ],
    '3-5-2': [
        ('TW', 'goalkeeper'),
        ('IV', 'defense'), ('IV', 'defense'), ('IV', 'defense'),
        ('LM', 'midfield'), ('ZM', 'midfield'), ('ZM', 'midfield'),
        ('ZM', 'midfield'), ('RM', 'midfield'),
        ('ST', 'attack'), ('ST', 'attack'),
    ],
    '5-3-2': [
        ('TW', 'goalkeeper'),
        ('LV', 'defense'), ('IV', 'defense'), ('IV', 'defense'),
        ('IV', 'defense'), ('RV', 'defense'),
        ('ZM', 'midfield'), ('ZM', 'midfield'), ('ZM', 'midfield'),
        ('ST', 'attack'), ('ST', 'attack'),
    ],
    '4-2-3-1': [
        ('TW', 'goalkeeper'),
        ('LV', 'defense'), ('IV', 'defense'), ('IV', 'defense'), ('RV', 'defense'),
        ('ZM', 'midfield'), ('ZM', 'midfield'),
        ('LM', 'midfield'), ('ZM', 'midfield'), ('RM', 'midfield'),
        ('ST', 'attack'),
    ],
}
_FORMATION_KEYS = list(_FORMATION_SLOTS.keys())

# ── Baselines und Alarmschwellen ──────────────────────────────────────────────

BASELINE = {
    'goals_per_game':  2.707,
    'home_win_pct':    0.386,
    'draw_pct':        0.259,
    'away_win_pct':    0.355,
    'yellow_per_game': 2.92,
    'red_per_game':    0.055,
    'shots_per_game':  21.2,
    'inj_per_game':    0.18,
}
ALARM = {
    'goals':  0.05,
    'result': 0.015,
    'cards':  0.15,
    'inj':    0.15,
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n; my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx  = sum((x - mx) ** 2 for x in xs)
    vy  = sum((y - my) ** 2 for y in ys)
    return cov / math.sqrt(vx * vy) if (vx * vy) > 0 else 0.0


def _spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    rx = [sorted(xs).index(x) for x in xs]
    ry = [sorted(ys).index(y) for y in ys]
    return _pearson(rx, ry)


def _mean(lst: list) -> float:
    return sum(lst) / len(lst) if lst else 0.0


def _std(lst: list) -> float:
    if len(lst) < 2:
        return 0.0
    m = _mean(lst)
    return math.sqrt(sum((x - m) ** 2 for x in lst) / len(lst))


def _median(lst: list) -> float:
    if not lst:
        return 0.0
    s = sorted(lst)
    n = len(s)
    if n % 2 == 1:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _pct(n: int | float, d: int | float) -> str:
    return f'{100*n/d:.1f}%' if d else 'n/a'


def _bar(val: float, lo: float, hi: float, width: int = 20) -> str:
    if hi <= lo:
        return ''
    filled = int(round((val - lo) / (hi - lo) * width))
    filled = max(0, min(width, filled))
    return '█' * filled + '·' * (width - filled)


def _alarm(label: str, val: float, base: float, tol: float) -> str:
    diff = abs(val - base)
    pct  = diff / abs(base) if base else diff
    if pct > tol:
        return f'  ⚠ ALARM  {label}: {val:.4f}  Basis {base:.4f}  Δ={diff:+.4f} ({100*pct:.1f}%)'
    return ''


def _linreg(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Lineare Regression y = a + b*x, gibt (a, b) zurück."""
    n = len(xs)
    if n < 2:
        return (0.0, 0.0)
    mx = _mean(xs); my = _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    b = num / den if den else 0.0
    return (my - b * mx, b)


def _ci95(lst: list[float]) -> tuple[float, float]:
    """95%-Konfidenzintervall (Normalapproximation): (lo, hi)."""
    if not lst:
        return (0.0, 0.0)
    m = _mean(lst)
    s = _std(lst)
    margin = 1.96 * s / math.sqrt(len(lst))
    return (m - margin, m + margin)


def _bootstrap_spearman_ci(
    str_ranks: list[float],
    pos_by_str: list[float],
    n_boot: int = 500,
    rng: random.Random | None = None,
) -> tuple[float, float]:
    """Bootstrap-CI für Spearman-Korrelation (500 Stichproben à n//2 Einträge)."""
    _rng = rng or random.Random(42)
    n = len(str_ranks)
    if n < 4:
        return (0.0, 0.0)
    k = max(4, n // 2)
    vals = []
    for _ in range(n_boot):
        idxs = [_rng.randint(0, n - 1) for _ in range(k)]
        xs = [str_ranks[i] for i in idxs]
        ys = [pos_by_str[i] for i in idxs]
        vals.append(_spearman(xs, ys))
    vals.sort()
    lo_i = int(0.025 * n_boot)
    hi_i = int(0.975 * n_boot) - 1
    return (vals[lo_i], vals[hi_i])


# ── Spielplanzeugung ─────────────────────────────────────────────────────────

def _make_schedule() -> list[list[tuple[int, int]]]:
    n = N_CLUBS
    ids = [c['id'] for c in CLUBS]
    first_leg: list[list[tuple[int, int]]] = []
    for _ in range(n - 1):
        pairs = []
        for k in range(n // 2):
            h = ids[k]; a = ids[n - 1 - k]
            pairs.append((h, a))
        first_leg.append(pairs)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    second_leg = [[(a, h) for h, a in rnd] for rnd in first_leg]
    return first_leg + second_leg


SCHEDULE = _make_schedule()


# ── Team-Bau ─────────────────────────────────────────────────────────────────

def _player_id(cid: int, slot: int) -> int:
    return cid * 200 + slot


def _make_league_team(
    club: dict,
    freshness_arr: list[float],
    rng: random.Random,
    psubs: list,
    slots: list[tuple[str, str]] | None = None,
    tactic_override: dict | None = None,
) -> dict:
    if slots is None:
        slots = SLOTS
    cid  = club['id']
    str0 = club['strength']
    players, lineup = [], []
    for i, (pos, grp) in enumerate(slots):
        pid = _player_id(cid, i)
        fr  = int(max(30, min(100, freshness_arr[i])))
        players.append({
            'id': pid, 'name': f"{club['name']}_{i}",
            'final_strength': max(30.0, str0 + rng.gauss(0, 3)),
            'main_positions': [pos], 'secondary_positions': [],
            'teamwork': 5, 'freshness': fr, 'is_ws_injured': False,
        })
        lineup.append({'player_id': pid, 'position': pos, 'group': grp})
    bench: dict = {}
    for j, pos in enumerate(BENCH_POS):
        pid = _player_id(cid, N_STARTERS + j)
        fr  = int(max(30, min(100, freshness_arr[N_STARTERS + j])))
        bench[pid] = {
            'id': pid, 'name': f"{club['name']}_B{j}",
            'final_strength': max(30.0, str0 - 6 + rng.gauss(0, 3)),
            'main_positions': [pos], 'secondary_positions': [],
            'teamwork': 4, 'freshness': fr, 'is_ws_injured': False,
        }
    return {
        'team': {'name': club['name'], 'id': cid},
        'players': players, 'lineup': lineup,
        'tactic': tactic_override or {},
        'bench_player_data': bench,
        'planned_substitutions': psubs,
    }


def _make_psubs(cid: int, rng: random.Random) -> list[dict]:
    starters = [_player_id(cid, i) for i in range(7, 11)]
    bench    = [_player_id(cid, N_STARTERS + j) for j in range(N_BENCH)]
    rng.shuffle(starters); rng.shuffle(bench)
    conditions = ['immer', 'immer', 'rueckstand']
    n = rng.randint(2, 3)
    return [
        {'in': bench[k], 'out': starters[k], 'minute': 55 + k * 12,
         'condition': conditions[k % len(conditions)]}
        for k in range(min(n, len(starters), len(bench)))
    ]


# ── Frische-Verwaltung ────────────────────────────────────────────────────────

def _init_freshness(rng: random.Random) -> dict[int, list[float]]:
    return {c['id']: [85 + rng.random() * 10 for _ in range(N_STARTERS + N_BENCH)]
            for c in CLUBS}


def _update_freshness_after_game(
    fr_map: dict, cid: int,
    sub_events: list, rng: random.Random,
):
    arr        = fr_map[cid]
    swapped_in  = {e['in']  for e in sub_events if e.get('in')}
    swapped_out = {e['out'] for e in sub_events if e.get('out')}
    for i in range(N_STARTERS + N_BENCH):
        pid = _player_id(cid, i)
        recovery = rng.uniform(4.0, 6.0)
        arr[i]   = min(100.0, arr[i] + recovery)
        if i < N_STARTERS:
            if pid in swapped_out:
                fatigue = rng.uniform(3.5, 5.5)
            else:
                fatigue = rng.uniform(5.0, 6.5)
            arr[i] = max(30.0, arr[i] - fatigue)
        elif pid in swapped_in:
            fatigue = rng.uniform(2.5, 4.0)
            arr[i] = max(30.0, arr[i] - fatigue)


# ── V1-kompatibler Schnellmodus ───────────────────────────────────────────────

def _make_team_v1(seed: int, strength: float, psubs: list) -> dict:
    rng = random.Random(seed)
    pid_base = seed * 200
    players, lineup = [], []
    for i, (pos, grp) in enumerate(SLOTS):
        pid = pid_base + i
        players.append({
            'id': pid, 'name': f'P{pid}',
            'final_strength': max(30.0, strength + rng.gauss(0, 4)),
            'main_positions': [pos], 'secondary_positions': [],
            'teamwork': 5, 'freshness': 80 + rng.randint(0, 15),
            'is_ws_injured': False,
        })
        lineup.append({'player_id': pid, 'position': pos, 'group': grp})
    bench: dict = {}
    for j, pos in enumerate(BENCH_POS):
        pid = pid_base + 11 + j
        bench[pid] = {
            'id': pid, 'name': f'B{pid}',
            'final_strength': max(30.0, strength - 6 + rng.gauss(0, 4)),
            'main_positions': [pos], 'secondary_positions': [],
            'teamwork': 4, 'freshness': 75 + rng.randint(0, 15),
            'is_ws_injured': False,
        }
    return {
        'team': {'name': f'Team-{seed}', 'id': seed},
        'players': players, 'lineup': lineup,
        'tactic': {},
        'bench_player_data': bench,
        'planned_substitutions': psubs,
    }


def _make_subs_v1(seed: int, pid_base: int, bench_pids: list, n: int = 3) -> list:
    rng = random.Random(seed + 77)
    conditions = ['immer', 'immer', 'fuehrung', 'rueckstand', 'immer']
    targets = [pid_base + i for i in range(7, 11)]
    rng.shuffle(targets)
    result = []; used_out: set = set()
    for k in range(min(n, len(bench_pids), len(targets))):
        if targets[k] in used_out:
            continue
        used_out.add(targets[k])
        result.append({
            'in': bench_pids[k], 'out': targets[k],
            'minute': 55 + k * 10, 'condition': conditions[k % len(conditions)],
        })
    return result


# ── Ticker-Integritätsprüfung ─────────────────────────────────────────────────

def _check_ticker_integrity(n_samples: int = 200) -> dict:
    from game.ticker_commentary import stable_seed, build_ticker_text, build_flow_text
    errors: list[str] = []
    rng = random.Random(9999)
    for _ in range(50):
        ms = rng.randint(0, 2**32); ei = rng.randint(0, 20); min_ = rng.randint(1, 90)
        t1 = build_ticker_text('shot', minute=min_, player='Müller', match_seed=ms, event_index=ei)
        t2 = build_ticker_text('shot', minute=min_, player='Müller', match_seed=ms, event_index=ei)
        if t1 != t2:
            errors.append(f'Instabiler Text: shot min={min_} seed={ms} ei={ei}')
    ms = 12345678
    shots = [build_ticker_text('shot', minute=i+1, player=f'P{i}',
                               match_seed=ms, event_index=i) for i in range(15)]
    if len(set(shots)) < 10:
        errors.append(f'Zu viele Wiederholungen: {len(set(shots))}/15 eindeutig')
    s1 = stable_seed('Bayern', 'Dortmund', 3, 1)
    s2 = stable_seed('Bayern', 'Dortmund', 3, 1)
    s3 = stable_seed('Bayern', 'Dortmund', 3, 2)
    if s1 != s2:
        errors.append('stable_seed: gleiche Eingabe → unterschiedlicher Seed')
    if s1 == s3:
        errors.append('stable_seed: verschiedene Eingabe → gleicher Seed')
    t1 = build_flow_text(45, 54321, 3, 'Bayern', 'BVB')
    t2 = build_flow_text(45, 54321, 3, 'Bayern', 'BVB')
    if t1 != t2:
        errors.append('build_flow_text: instabil')
    for i in range(20):
        txt = build_ticker_text('goal', minute=30+i, player='Lewandowski',
                                assister='Müller', score_h=1, score_a=0,
                                match_seed=ms, event_index=i)
        if '1:0' not in txt:
            errors.append(f'Tor-Text enthält kein Score-Format: {txt[:60]}'); break
    return {'errors': errors, 'ok': len(errors) == 0}


# ── Hauptklasse ───────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Regressionsbericht V3 — 100 Bundesliga-Saisons (kein ORM)'

    def add_arguments(self, parser):
        parser.add_argument('--seasons', type=int, default=100)
        parser.add_argument('--games',   type=int, default=0,
                            help='Schnellmodus: N zufällige Spiele statt Saisons')
        parser.add_argument('--seed',    type=int, default=42)
        parser.add_argument('--seeds',   type=str, default='',
                            help='Komma-getrennte Liste (z.B. 1,7,21,42,99,2026)')
        parser.add_argument('--output',  type=str, default='')
        parser.add_argument('--verbose', action='store_true', default=False)

    def handle(self, *args, **options):
        quick_n  = options['games']
        n_seas   = options['seasons']
        seed0    = options['seed']
        seeds_str = options['seeds']
        out_dir  = options['output']
        verbose  = options['verbose']

        if quick_n > 0:
            self._run_quick_mode(quick_n, seed0, verbose)
            return

        if seeds_str:
            seeds = [int(s.strip()) for s in seeds_str.split(',') if s.strip()]
        else:
            seeds = [seed0]

        all_metrics: list[tuple[int, dict]] = []
        for idx, seed in enumerate(seeds):
            is_last = (idx == len(seeds) - 1)
            metrics = self._run_league_mode(
                n_seas, seed, verbose,
                out_dir if is_last else '',
                print_details=is_last,
            )
            all_metrics.append((seed, metrics))

        if len(seeds) > 1:
            self._print_stability_table(all_metrics)

    # ── Liga-Modus ────────────────────────────────────────────────────────────

    def _run_league_mode(
        self, n_seas: int, seed0: int, verbose: bool,
        out_dir: str, print_details: bool = True,
    ) -> dict:
        w  = self.stdout.write
        HR = '─' * 72
        N_GAMES = n_seas * N_CLUBS * (N_CLUBS - 1)

        if print_details:
            w(f'\n{HR}')
            w(f'  Regressionsbericht V3  —  {n_seas} Saisons × 306 Spiele = {N_GAMES} Gesamt  [seed={seed0}]')
            w(f'{HR}')
        else:
            self.stdout.write(f'  Seed {seed0:>6}  … running {n_seas} seasons … ', ending='')

        t0  = time.time()
        rng = random.Random(seed0)

        # ── Akkumulatoren ─────────────────────────────────────────────────────

        total_games = errors = 0

        # A: Integrität
        v_double_sub = v_post_sub_goal = v_post_dis_goal = 0
        v_neg_xg = v_invalid_poss = v_over_5_subs = 0

        # B: Ergebnisse
        total_goals = home_wins = draws = away_wins = 0
        total_yellow = total_red = 0
        xg_home_sum = xg_away_sum = 0.0
        shots_sum = shots_on_sum = corners_sum = fouls_sum = 0
        goals_phase = [0, 0, 0]
        score_matrix: dict[tuple[int, int], int] = {}   # (hg, ag) capped at 5
        goals_per_game_list: list[float] = []
        gd_buckets = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}   # Tordifferenz: 0-3 exact, 4+=4
        five_plus_games = seven_plus_games = 0
        poss_list: list[int] = []
        press_wins_h = press_wins_a = 0
        press_bp_h = press_bp_a = 0
        att_left = att_center = att_right = 0

        # B: Heimvorteil nach Stärkeverhältnis
        # key: 'h_fav_big'|'h_fav'|'equal'|'a_fav'|'a_fav_big'
        # val: [h_wins, draws, a_wins, n_games]
        hv_by_str: dict[str, list[int]] = {
            'h_fav_big': [0,0,0,0], 'h_fav': [0,0,0,0],
            'equal':     [0,0,0,0], 'a_fav': [0,0,0,0], 'a_fav_big': [0,0,0,0],
        }

        # C: Standings
        club_seasons: dict[int, list[dict]] = defaultdict(list)
        championship: dict[int, int] = defaultdict(int)
        top4:         dict[int, int] = defaultdict(int)
        bottom3:      dict[int, int] = defaultdict(int)
        season_xgd_pts: list[tuple[float, float]] = []

        # D: Stärke-Brackets
        BKT = {
            '0-2':  [0,0,0,0.0,0.0], '3-7':   [0,0,0,0.0,0.0],
            '8-14': [0,0,0,0.0,0.0], '15-24':  [0,0,0,0.0,0.0], '25+': [0,0,0,0.0,0.0],
        }
        mirrored: dict[tuple, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])

        # D: Wechsel
        total_subs_exec = total_planned_in = total_planned_exec = total_inj_subs = 0
        hp_count = np_count = fp_count = 0
        strength_delta_sum = 0.0; strength_delta_n = 0
        cond_counts: dict[str, int] = {}
        cond_exec:   dict[str, int] = {}
        sub_minutes: list[int] = []

        # Formation HP/NP/FP per formation key
        form_hp: dict[str, int] = {k: 0 for k in _FORMATION_KEYS}
        form_np: dict[str, int] = {k: 0 for k in _FORMATION_KEYS}
        form_fp: dict[str, int] = {k: 0 for k in _FORMATION_KEYS}

        # E: Verletzungen
        inj_ingame = inj_postmatch = 0
        inj_light = inj_mid = inj_heavy = inj_extreme = 0
        inj_days_sum = 0; inj_days_n = 0
        inj_days_list: list[int] = []
        # Freshness buckets at time of (post-match) injury
        inj_fr_bucket = {'90-100': [0, 0], '75-89': [0, 0], '60-74': [0, 0], '<60': [0, 0]}
        # [injuries, total_player_games] per bucket

        # E: Frische
        fr_start_list: list[float] = []
        fr_end_list:   list[float] = []
        fr_by_matchday: list[list[float]] = [[] for _ in range(34)]  # one slot per matchday

        # G: Taktik-Balance
        _ts_zero = lambda: {'n': 0, 'pts': 0, 'gf': 0, 'ga': 0,
                            'xgf': 0.0, 'xga': 0.0, 'poss': 0.0, 'str_sum': 0.0}
        tactic_stats: dict[str, dict] = {k: _ts_zero() for k in _TACTIC_KEYS}
        # season-level: list of (club_strength, season_pts) per tactic
        tactic_season: dict[str, list[tuple[float, int]]] = {k: [] for k in _TACTIC_KEYS}

        # H: Formations-Balance
        formation_stats: dict[str, dict] = {k: _ts_zero() for k in _FORMATION_KEYS}
        formation_season: dict[str, list[tuple[float, int]]] = {k: [] for k in _FORMATION_KEYS}

        # I: Spielverlauf
        first_goal_total = first_goal_wins_h = first_goal_wins_a = 0
        ht_01_total = ht_01_comeback = 0
        ht_02_total = ht_02_comeback = 0
        late_goals_total = sub_goals_total = 0
        goals_after_red = 0
        red_card_games = 0

        # J: Saisonstreuung
        season_champion_pts: list[int] = []
        season_relegation_pts: list[int] = []
        season_title_delta: list[int] = []

        # ── Saisonschleife ────────────────────────────────────────────────────
        for season_i in range(n_seas):
            season_rng = random.Random(seed0 * 100000 + season_i)
            fr_map     = _init_freshness(season_rng)

            standing: dict[int, dict] = {
                c['id']: {'pts': 0, 'gf': 0, 'ga': 0, 'xgf': 0.0, 'xga': 0.0, 'won': 0}
                for c in CLUBS
            }

            # Saisonzuweisungen: Taktik und Formation pro Club
            tactic_assign    = {c['id']: _TACTIC_KEYS[season_rng.randint(0, len(_TACTIC_KEYS)-1)]
                                for c in CLUBS}
            formation_assign = {c['id']: _FORMATION_KEYS[season_rng.randint(0, len(_FORMATION_KEYS)-1)]
                                for c in CLUBS}

            for md_i, matchday in enumerate(SCHEDULE):
                # Frische-Kurve: Ø Frische aller Stammelf vor Spieltag
                for c in CLUBS:
                    avg_fr = _mean(fr_map[c['id']][:N_STARTERS])
                    fr_by_matchday[md_i].append(avg_fr)

                for h_id, a_id in matchday:
                    game_rng  = random.Random(season_rng.randint(0, 2**32))
                    h_club    = CLUBS[CID_INDEX[h_id]]
                    a_club    = CLUBS[CID_INDEX[a_id]]
                    h_psubs   = _make_psubs(h_id, game_rng)
                    a_psubs   = _make_psubs(a_id, game_rng)

                    # Frische vor Spiel
                    h_fr_avg = _mean(fr_map[h_id][:N_STARTERS])
                    a_fr_avg = _mean(fr_map[a_id][:N_STARTERS])
                    fr_start_list.append(h_fr_avg); fr_start_list.append(a_fr_avg)

                    for ps in h_psubs + a_psubs:
                        c = ps.get('condition', 'immer')
                        cond_counts[c] = cond_counts.get(c, 0) + 1
                    total_planned_in += len(h_psubs) + len(a_psubs)

                    # Taktik und Formation
                    h_tac_key  = tactic_assign[h_id]
                    a_tac_key  = tactic_assign[a_id]
                    h_form_key = formation_assign[h_id]
                    a_form_key = formation_assign[a_id]
                    h_slots    = _FORMATION_SLOTS[h_form_key]
                    a_slots    = _FORMATION_SLOTS[a_form_key]
                    h_tactic   = _TACTIC_PROFILES[h_tac_key]
                    a_tactic   = _TACTIC_PROFILES[a_tac_key]

                    home_team = _make_league_team(
                        h_club, fr_map[h_id], game_rng, h_psubs, h_slots, h_tactic)
                    away_team = _make_league_team(
                        a_club, fr_map[a_id], game_rng, a_psubs, a_slots, a_tactic)

                    try:
                        sim = _simulate_match_minutes(home_team, away_team)
                    except Exception as exc:
                        errors += 1
                        self.stderr.write(f'  ERROR s{season_i} md{md_i}: {exc}')
                        continue

                    total_games += 1
                    hg, ag   = sim['home_goals'], sim['away_goals']
                    hxg, axg = float(sim.get('home_xg') or 0), float(sim.get('away_xg') or 0)
                    ms_      = sim.get('match_stats', {}) or {}
                    goal_evts = sim.get('goal_events', []) or []
                    h_evts    = sim.get('h_sim_sub_events', [])
                    a_evts    = sim.get('a_sim_sub_events', [])
                    dis_evts  = sim.get('dismissal_events', []) or []

                    # ── A: Integrität ──────────────────────────────────────────
                    if hxg < 0 or axg < 0 or math.isnan(hxg) or math.isnan(axg):
                        v_neg_xg += 1
                    hp = ms_.get('home_possession', 50) or 50
                    ap = ms_.get('away_possession', 50) or 50
                    if abs((hp + ap) - 100) > 2:
                        v_invalid_poss += 1
                    if len([e for e in h_evts if e.get('condition') != 'verletzung']) > MAX_SUBSTITUTIONS:
                        v_over_5_subs += 1
                    if len([e for e in a_evts if e.get('condition') != 'verletzung']) > MAX_SUBSTITUTIONS:
                        v_over_5_subs += 1
                    for side_evts in (h_evts, a_evts):
                        in_pids = [e['in'] for e in side_evts if e.get('in')]
                        if len(in_pids) != len(set(in_pids)):
                            v_double_sub += 1
                        out_map = {e['out']: e['minute'] for e in side_evts if e.get('out')}
                        for ge in goal_evts:
                            sid = ge.get('scorer_id'); gmin = ge.get('minute', 0)
                            if sid and sid in out_map and gmin > out_map[sid]:
                                v_post_sub_goal += 1
                    dis_map: dict = {}
                    for de in dis_evts:
                        dis_map[de.get('player_id')] = de.get('minute', 0)
                    for ge in goal_evts:
                        sid = ge.get('scorer_id'); gmin = ge.get('minute', 0)
                        if sid and sid in dis_map and gmin > dis_map[sid]:
                            v_post_dis_goal += 1

                    # ── B: Ergebnisse ─────────────────────────────────────────
                    total_goals += hg + ag
                    goals_per_game_list.append(hg + ag)
                    hg_cap = min(hg, 5); ag_cap = min(ag, 5)
                    score_matrix[(hg_cap, ag_cap)] = score_matrix.get((hg_cap, ag_cap), 0) + 1
                    tot = hg + ag
                    if tot >= 7: seven_plus_games += 1
                    if tot >= 5: five_plus_games  += 1
                    gd = abs(hg - ag)
                    gd_buckets[min(gd, 4)] += 1
                    if hg > ag:    home_wins += 1
                    elif hg == ag: draws     += 1
                    else:          away_wins += 1
                    total_yellow += ms_.get('home_yellow', 0) + ms_.get('away_yellow', 0)
                    total_red    += ms_.get('home_red',    0) + ms_.get('away_red',    0)
                    xg_home_sum  += hxg; xg_away_sum += axg
                    shots_sum    += ms_.get('home_shots', 0) + ms_.get('away_shots', 0)
                    shots_on_sum += ms_.get('home_shots_on_target', 0) + ms_.get('away_shots_on_target', 0)
                    corners_sum  += ms_.get('home_corners', 0) + ms_.get('away_corners', 0)
                    fouls_sum    += ms_.get('home_fouls',   0) + ms_.get('away_fouls',   0)
                    press_wins_h += ms_.get('home_pressing_ball_wins', 0)
                    press_wins_a += ms_.get('away_pressing_ball_wins', 0)
                    press_bp_h   += ms_.get('home_pressing_bypassed', 0)
                    press_bp_a   += ms_.get('away_pressing_bypassed', 0)
                    att_left     += ms_.get('home_attacks_left',   0) + ms_.get('away_attacks_left',   0)
                    att_center   += ms_.get('home_attacks_center', 0) + ms_.get('away_attacks_center', 0)
                    att_right    += ms_.get('home_attacks_right',  0) + ms_.get('away_attacks_right',  0)
                    poss_list.append(hp)
                    for ge in goal_evts:
                        m = ge.get('minute', 45)
                        if m <= 30:   goals_phase[0] += 1
                        elif m <= 60: goals_phase[1] += 1
                        else:         goals_phase[2] += 1

                    # ── B: Heimvorteil nach Stärkeverhältnis ──────────────────
                    h_str = h_club['strength']; a_str = a_club['strength']
                    str_diff = h_str - a_str
                    if str_diff >= 10:    hv_key = 'h_fav_big'
                    elif str_diff >= 1:   hv_key = 'h_fav'
                    elif str_diff == 0:   hv_key = 'equal'
                    elif str_diff >= -9:  hv_key = 'a_fav'
                    else:                 hv_key = 'a_fav_big'
                    hv = hv_by_str[hv_key]
                    if hg > ag:    hv[0] += 1
                    elif hg == ag: hv[1] += 1
                    else:          hv[2] += 1
                    hv[3] += 1

                    # ── D: Stärke-Brackets ────────────────────────────────────
                    diff_abs = abs(h_str - a_str)
                    fav_home = h_str > a_str
                    if diff_abs <= 2:
                        bkt = '0-2'
                    elif diff_abs <= 7:
                        bkt = '3-7'
                    elif diff_abs <= 14:
                        bkt = '8-14'
                    elif diff_abs <= 24:
                        bkt = '15-24'
                    else:
                        bkt = '25+'
                    b = BKT[bkt]
                    fav_won  = (fav_home and hg > ag) or (not fav_home and ag > hg)
                    is_draw  = hg == ag
                    if fav_won:   b[0] += 1
                    elif is_draw: b[1] += 1
                    else:         b[2] += 1
                    b[3] += hg - ag if fav_home else ag - hg
                    b[4] += (hxg - axg) if fav_home else (axg - hxg)

                    # ── D: Heimvorteil gespiegelt ─────────────────────────────
                    pair_key = (min(h_id, a_id), max(h_id, a_id))
                    m_entry  = mirrored[pair_key]
                    if h_id < a_id:
                        m_entry[0] += hg; m_entry[1] += ag
                    else:
                        m_entry[0] += ag; m_entry[1] += hg
                    m_entry[2] += 1

                    # ── C: Standings ──────────────────────────────────────────
                    s_h = standing[h_id]; s_a = standing[a_id]
                    s_h['gf'] += hg; s_h['ga'] += ag
                    s_a['gf'] += ag; s_a['ga'] += hg
                    s_h['xgf'] += hxg; s_h['xga'] += axg
                    s_a['xgf'] += axg; s_a['xga'] += hxg
                    if hg > ag:    s_h['pts'] += 3; s_h['won'] += 1
                    elif hg == ag: s_h['pts'] += 1; s_a['pts'] += 1
                    else:          s_a['pts'] += 3; s_a['won'] += 1

                    # ── D: Wechsel ────────────────────────────────────────────
                    for side_evts, side_team, side_form_key in (
                        (h_evts, home_team, h_form_key),
                        (a_evts, away_team, a_form_key),
                    ):
                        pid_str_map = {p['id']: p['final_strength'] for p in side_team['players']}
                        pid_str_map.update({pid: p['final_strength']
                                            for pid, p in side_team['bench_player_data'].items()})
                        for evt in side_evts:
                            in_p  = evt.get('in'); out_p = evt.get('out')
                            cond  = evt.get('condition', 'immer')
                            rel   = evt.get('position_relation', '')
                            minute = evt.get('minute', 0)
                            total_subs_exec += 1
                            if cond == 'verletzung':
                                total_inj_subs += 1
                            else:
                                total_planned_exec += 1
                                cond_exec[cond] = cond_exec.get(cond, 0) + 1
                            if rel == 'HP':
                                hp_count += 1; form_hp[side_form_key] += 1
                            elif rel == 'NP':
                                np_count += 1; form_np[side_form_key] += 1
                            elif rel == 'FP':
                                fp_count += 1; form_fp[side_form_key] += 1
                            if in_p and out_p:
                                delta = pid_str_map.get(in_p, 0) - pid_str_map.get(out_p, 0)
                                strength_delta_sum += delta; strength_delta_n += 1
                            if minute:
                                sub_minutes.append(minute)

                    # ── E: Verletzungen ───────────────────────────────────────
                    for side_evts_inj in (h_evts, a_evts):
                        for evt in side_evts_inj:
                            if evt.get('condition') == 'verletzung':
                                days = evt.get('days', 5)
                                inj_ingame += 1
                                if days <= 7:    inj_light   += 1
                                elif days <= 21: inj_mid     += 1
                                elif days <= 56: inj_heavy   += 1
                                else:            inj_extreme += 1
                                inj_days_sum += days; inj_days_n += 1
                                inj_days_list.append(days)

                    for pm_team, pm_fr_arr in (
                        (home_team, fr_map[h_id]),
                        (away_team, fr_map[a_id]),
                    ):
                        # Build freshness map for injury bucket tracking
                        pid_fr_map = {p['id']: p.get('freshness', 80)
                                      for p in pm_team['players']}
                        # Count total player-games per bucket (only starters)
                        for p in pm_team['players']:
                            fr_val = p.get('freshness', 80)
                            if fr_val >= 90:   inj_fr_bucket['90-100'][1] += 1
                            elif fr_val >= 75: inj_fr_bucket['75-89'][1] += 1
                            elif fr_val >= 60: inj_fr_bucket['60-74'][1] += 1
                            else:              inj_fr_bucket['<60'][1]    += 1

                        pm_evts = _generate_injury_events(pm_team['players'], 'home')
                        for evt in pm_evts:
                            days = evt.get('days', 5)
                            inj_postmatch += 1
                            if days <= 7:    inj_light   += 1
                            elif days <= 21: inj_mid     += 1
                            elif days <= 56: inj_heavy   += 1
                            else:            inj_extreme += 1
                            inj_days_sum += days; inj_days_n += 1
                            inj_days_list.append(days)
                            # Freshness bucket of injured player
                            inj_pid = evt.get('player_id')
                            if inj_pid:
                                fr_val = pid_fr_map.get(inj_pid, 80)
                                if fr_val >= 90:   inj_fr_bucket['90-100'][0] += 1
                                elif fr_val >= 75: inj_fr_bucket['75-89'][0]  += 1
                                elif fr_val >= 60: inj_fr_bucket['60-74'][0]  += 1
                                else:              inj_fr_bucket['<60'][0]    += 1

                    # ── Frische nach Spiel ────────────────────────────────────
                    _update_freshness_after_game(fr_map, h_id, h_evts, game_rng)
                    _update_freshness_after_game(fr_map, a_id, a_evts, game_rng)
                    fr_end_list.append(_mean(fr_map[h_id][:N_STARTERS]))
                    fr_end_list.append(_mean(fr_map[a_id][:N_STARTERS]))

                    # ── G: Taktik ─────────────────────────────────────────────
                    pts_h = 3 if hg > ag else (1 if hg == ag else 0)
                    pts_a = 3 - pts_h if hg != ag else 1
                    for tk, t_pts, t_gf, t_ga, t_xgf, t_xga, t_poss, t_str in [
                        (h_tac_key, pts_h, hg, ag, hxg, axg, hp, h_club['strength']),
                        (a_tac_key, pts_a, ag, hg, axg, hxg, ap, a_club['strength']),
                    ]:
                        ts = tactic_stats[tk]
                        ts['n'] += 1; ts['pts'] += t_pts
                        ts['gf'] += t_gf; ts['ga'] += t_ga
                        ts['xgf'] += t_xgf; ts['xga'] += t_xga
                        ts['poss'] += t_poss; ts['str_sum'] += t_str

                    # ── H: Formation ──────────────────────────────────────────
                    for fk, f_pts, f_gf, f_ga, f_xgf, f_xga, f_poss, f_str in [
                        (h_form_key, pts_h, hg, ag, hxg, axg, hp, h_club['strength']),
                        (a_form_key, pts_a, ag, hg, axg, hxg, ap, a_club['strength']),
                    ]:
                        fs = formation_stats[fk]
                        fs['n'] += 1; fs['pts'] += f_pts
                        fs['gf'] += f_gf; fs['ga'] += f_ga
                        fs['xgf'] += f_xgf; fs['xga'] += f_xga
                        fs['poss'] += f_poss; fs['str_sum'] += f_str

                    # ── I: Spielverlauf ───────────────────────────────────────
                    sorted_goals = sorted(goal_evts, key=lambda g: g.get('minute', 99))
                    if sorted_goals:
                        first_goal_total += 1
                        first_team = sorted_goals[0].get('team', '')
                        if first_team == 'home' and hg > ag:
                            first_goal_wins_h += 1
                        elif first_team == 'away' and ag > hg:
                            first_goal_wins_a += 1

                    # HT score (minute ≤ 45)
                    ht_h = sum(1 for ge in goal_evts
                               if ge.get('team') == 'home' and ge.get('minute', 0) <= 45)
                    ht_a = sum(1 for ge in goal_evts
                               if ge.get('team') == 'away' and ge.get('minute', 0) <= 45)
                    if ht_h == 0 and ht_a == 1:
                        ht_01_total += 1
                        if hg >= ag:  # drew or won = comeback
                            ht_01_comeback += 1
                    if ht_h == 0 and ht_a == 2:
                        ht_02_total += 1
                        if hg >= ag:
                            ht_02_comeback += 1

                    # Late goals (76–90)
                    late_goals = sum(1 for ge in goal_evts if ge.get('minute', 0) > 75)
                    late_goals_total += late_goals

                    # Goals by substitutes
                    sub_pids = {e['in'] for e in h_evts + a_evts if e.get('in')}
                    sub_g = sum(1 for ge in goal_evts
                                if ge.get('scorer_id') in sub_pids)
                    sub_goals_total += sub_g

                    # Goals after red card
                    if dis_evts:
                        red_card_games += 1
                        min_red = min(de.get('minute', 90) for de in dis_evts)
                        after_red = sum(1 for ge in goal_evts
                                        if ge.get('minute', 0) > min_red)
                        goals_after_red += after_red

            # ── Saison auswerten ──────────────────────────────────────────────
            sorted_clubs = sorted(
                standing.items(),
                key=lambda x: (-x[1]['pts'], -(x[1]['gf'] - x[1]['ga'])),
            )
            for pos_idx, (cid, st) in enumerate(sorted_clubs):
                club_seasons[cid].append({
                    'pts': st['pts'], 'gf': st['gf'], 'ga': st['ga'],
                    'pos': pos_idx + 1,
                    'xgd': st['xgf'] - st['xga'],
                    'gd':  st['gf'] - st['ga'],
                })
                season_xgd_pts.append((st['xgf'] - st['xga'], st['pts']))
            championship[sorted_clubs[0][0]] += 1
            for cid, _ in sorted_clubs[:4]:   top4[cid]   += 1
            for cid, _ in sorted_clubs[-3:]:  bottom3[cid]+= 1

            # J: Saisonstreuung
            pts_sorted = [st['pts'] for _, st in sorted_clubs]
            season_champion_pts.append(pts_sorted[0])
            season_relegation_pts.append(pts_sorted[-1])
            season_title_delta.append(pts_sorted[0] - pts_sorted[1] if len(pts_sorted) > 1 else 0)

            # G+H: Taktik/Formation season-level records
            for cid in [c['id'] for c in CLUBS]:
                ss = standing[cid]
                tk = tactic_assign[cid]
                fk = formation_assign[cid]
                str_ = CLUBS[CID_INDEX[cid]]['strength']
                tactic_season[tk].append((str_, ss['pts']))
                formation_season[fk].append((str_, ss['pts']))

        # ── Ende Simulationsschleife ──────────────────────────────────────────
        elapsed = time.time() - t0
        N = total_games or 1
        gpg = total_goals / N
        hw  = home_wins / N; drw = draws / N; aw = away_wins / N
        ypg = total_yellow / N; rpg = total_red / N
        xh  = xg_home_sum / N; xa  = xg_away_sum / N
        inj_total = inj_ingame + inj_postmatch

        # Spearman Korrelation
        str_ordered    = sorted(CLUBS, key=lambda c: -c['strength'])
        str_ranks_all  = list(range(1, N_CLUBS + 1))
        avg_pos_by_str = [_mean([s['pos'] for s in club_seasons[c['id']]]) for c in str_ordered]
        avg_pts_by_str = [_mean([s['pts'] for s in club_seasons[c['id']]]) for c in str_ordered]
        r_str_pos = _spearman(str_ranks_all, avg_pos_by_str)
        r_str_pts = _pearson(str_ranks_all, [-p for p in avg_pts_by_str])
        r_xgd_pts = _pearson([t[0] for t in season_xgd_pts], [t[1] for t in season_xgd_pts])

        # Compact metrics dict (for multi-seed comparison)
        metrics = {
            'goals_per_game': gpg, 'home_pct': hw, 'draw_pct': drw, 'away_pct': aw,
            'spearman': r_str_pos, 'pearson_xgd': r_xgd_pts,
            'inj_per_game': inj_total / N, 'errors': errors,
            'yellow_per_game': ypg, 'red_per_game': rpg,
        }

        if not print_details:
            self.stdout.write(
                f"goals={gpg:.3f}  home%={100*hw:.1f}  remis%={100*drw:.1f}  "
                f"spearman={r_str_pos:.3f}  inj/Sp={inj_total/N:.3f}  "
                f"err={errors}"
            )
            return metrics

        # ════════════════════════════════════════════════════════════════════
        # AUSGABE — SEKTIONEN A–K
        # ════════════════════════════════════════════════════════════════════

        w(f'  Laufzeit    : {elapsed:.1f} s  ({elapsed/N*1000:.1f} ms/Spiel)')
        w(f'  Fehler      : {errors}  ← muss 0 sein')

        # ── A: INTEGRITÄT ─────────────────────────────────────────────────────
        w(f'\n{HR}'); w('  A  TECHNISCHE INTEGRITÄT'); w(HR)
        def _chk(label: str, n: int) -> str:
            return f'  {"✓" if n==0 else "✗ FAIL"}  {label:44}  {n}'
        w(_chk('Exceptions',             errors))
        w(_chk('Doppelte Einwechslungen', v_double_sub))
        w(_chk('Tore nach Auswechslung',  v_post_sub_goal))
        w(_chk('Tore nach Platzverweis',  v_post_dis_goal))
        w(_chk('Negative / NaN xG',       v_neg_xg))
        w(_chk('Ungültige Ballbesitzsumme', v_invalid_poss))
        w(_chk('Geplante Wechsel > 5',    v_over_5_subs))
        ok = all(v == 0 for v in [errors, v_double_sub, v_post_sub_goal,
                                   v_post_dis_goal, v_neg_xg, v_invalid_poss, v_over_5_subs])
        w(f'\n  Gesamtstatus: {"✓ ALLE INVARIANTEN GRÜN" if ok else "✗ FEHLER — SIEHE OBEN"}')

        # ── B: ERGEBNISVERTEILUNG ─────────────────────────────────────────────
        w(f'\n{HR}'); w('  B  MATCH- UND ERGEBNISVERTEILUNG'); w(HR)
        w(f'  Tore/Spiel        : {gpg:.3f}  '
          f'(Heim xG {xh:.2f}  /  Gast xG {xa:.2f}  /  Gesamt xG/Sp {xh+xa:.2f})')
        w(f'  Heim / Remis / Aus: {home_wins}/{draws}/{away_wins}  '
          f'({_pct(home_wins,N)} / {_pct(draws,N)} / {_pct(away_wins,N)})')
        w(f'  Gelb/Spiel        : {ypg:.2f}')
        w(f'  Rot/Spiel         : {rpg:.4f}')
        w(f'  Schüsse/Spiel     : {shots_sum/N:.1f}')
        w(f'  Schüsse aufs Tor  : {shots_on_sum/N:.1f}  (Schüsse/Tor: {shots_sum/max(1,total_goals):.1f})')
        w(f'  Ecken/Spiel       : {corners_sum/N:.1f}')
        w(f'  Fouls/Spiel       : {fouls_sum/N:.1f}')
        if total_goals > 0:
            w(f'  Tore/xG           : {total_goals/(xg_home_sum+xg_away_sum+0.001):.3f}  (Ziel ~1.0)')
        w(f'  Pressing-Siege/Sp : Heim {press_wins_h/N:.1f}  Gast {press_wins_a/N:.1f}')
        att_total = att_left + att_center + att_right or 1
        w(f'  Angriffszone      : Links {_pct(att_left,att_total)}  '
          f'Mitte {_pct(att_center,att_total)}  Rechts {_pct(att_right,att_total)}')

        alarms = []
        for lbl, val, base, tol in [
            ('Tore/Spiel',  gpg, BASELINE['goals_per_game'], ALARM['goals']),
            ('Heimsiege%',  hw,  BASELINE['home_win_pct'],   ALARM['result']),
            ('Remis%',      drw, BASELINE['draw_pct'],        ALARM['result']),
            ('Gelb/Spiel',  ypg, BASELINE['yellow_per_game'],ALARM['cards']),
        ]:
            a = _alarm(lbl, val, base, tol)
            if a: alarms.append(a)
        if alarms:
            w('\n  Basis-Alarme:')
            for a in alarms: w(a)
        else:
            w('\n  Alle Kernwerte innerhalb Toleranz.')

        # Scoreline-Matrix (Heim=Zeile, Gast=Spalte, capped bei 5)
        w('\n  Scoreline-Matrix (Heim → Zeile, Gast → Spalte; 5 = 5+):')
        header = '       '  + ''.join(f' {g:>6}' for g in range(6))
        w(f'  {header}')
        for hg_c in range(6):
            row = f'  {hg_c:>3}  '
            for ag_c in range(6):
                cnt = score_matrix.get((hg_c, ag_c), 0)
                row += f' {cnt:>6}' if cnt else '      ·'
            w(row)
        w(f'\n  5+ Tore-Spiele : {five_plus_games}  ({_pct(five_plus_games,N)})')
        w(f'  7+ Tore-Spiele : {seven_plus_games}  ({_pct(seven_plus_games,N)})')

        # Tordifferenz-Verteilung
        w('\n  Tordifferenz-Verteilung:')
        gd_labels = ['Remis (0)', 'Sieg +1 Tor', 'Sieg +2 Tore', 'Sieg +3 Tore', 'Sieg +4+ Tore']
        for lbl, cnt_key in zip(gd_labels, range(5)):
            cnt = gd_buckets.get(cnt_key, 0)
            w(f'    {lbl:>14} : {cnt:>7}  ({_pct(cnt,N)})')

        # Tore nach Phase
        gp_t = sum(goals_phase) or 1
        w('\n  Tore nach Spielphase:')
        for lbl, cnt in zip(['1–30 min', '31–60 min', '61–90 min'], goals_phase):
            w(f'    {lbl}  {cnt:>6}  ({_pct(cnt,gp_t)})  {_bar(cnt,0,gp_t//2)}')

        # Ballbesitz
        if poss_list:
            avg_p = _mean(poss_list); std_p = _std(poss_list)
            w(f'\n  Ballbesitz Heim: Ø {avg_p:.1f}%  σ={std_p:.1f}  '
              f'Min {min(poss_list)}%  Max {max(poss_list)}%')
            w(f'  (Ziel: Ø 49–52%, σ 6,5–8,0)')
            buckets = [0] * 10
            for p in poss_list:
                idx = max(0, min(9, (p - 25) // 5))
                buckets[idx] += 1
            labels = ['25-30','30-35','35-40','40-45','45-50','50-55','55-60','60-65','65-70','70-75']
            for lbl, cnt in zip(labels, buckets):
                w(f'    {lbl}%  {_bar(cnt,0,max(buckets))}  {cnt}×')

        # ── C: TABELLE ────────────────────────────────────────────────────────
        w(f'\n{HR}'); w(f'  C  TABELLE UND STÄRKEVERHALTEN ({n_seas} SAISONS)'); w(HR)
        pts_by_pos: list[list[int]] = [[] for _ in range(N_CLUBS)]
        for cid, seasons in club_seasons.items():
            for ss in seasons:
                pts_by_pos[ss['pos'] - 1].append(ss['pts'])
        w(f'  {"Platz":>5}  {"Ø Pkt":>7}  {"Min":>5}  {"Max":>5}  {"σ":>5}')
        for pos_i in range(N_CLUBS):
            lst = pts_by_pos[pos_i]
            if not lst: continue
            w(f'  {pos_i+1:>5}  {_mean(lst):>7.1f}  {min(lst):>5}  {max(lst):>5}  {_std(lst):>5.1f}')

        w(f'\n  Meisterhäufigkeit über {n_seas} Saisons:')
        for cid, cnt in sorted(championship.items(), key=lambda x: -x[1]):
            name = CLUBS[CID_INDEX[cid]]['name']
            w(f'    {name:>12}  {cnt:>4}×  {_pct(cnt,n_seas)}  {_bar(cnt,0,n_seas//2,30)}')

        w('\n  Ø Tabellenplatz je Verein:')
        club_avg_data = []
        for cid, seass in club_seasons.items():
            c_info    = CLUBS[CID_INDEX[cid]]
            avg_pos   = _mean([s['pos'] for s in seass])
            avg_gd    = _mean([s['gd']  for s in seass])
            str_rank  = sorted(CLUBS, key=lambda c: -c['strength']).index(c_info) + 1
            pos_bias  = avg_pos - str_rank   # positive = underperforms
            club_avg_data.append((c_info['name'], c_info['strength'], avg_pos,
                                  top4.get(cid,0), bottom3.get(cid,0), avg_gd, pos_bias))
        club_avg_data.sort(key=lambda x: x[2])
        w(f'  {"Verein":>12}  {"Stärke":>6}  {"Ø Platz":>8}  '
          f'{"Top4":>5}×  {"Abst":>5}×  {"Ø GD":>6}  {"Bias":>6}')
        for name, strength, avg_pos, t4, b3, avg_gd, bias in club_avg_data:
            w(f'  {name:>12}  {strength:>6.0f}  {avg_pos:>8.2f}  '
              f'{t4:>5}  {b3:>5}  {avg_gd:>+6.1f}  {bias:>+6.2f}')

        w('\n  Korrelationen:')
        w(f'    Stärke-Rang → Ø Tabellenplatz (Spearman) : {r_str_pos:+.3f}  (Ziel ≥ 0.90)')
        w(f'    Stärke-Rang → Ø Punkte        (Pearson)  : {r_str_pts:+.3f}  (|Ziel| ≥ 0.88)')
        w(f'    xGD → Punkte                  (Pearson)  : {r_xgd_pts:+.3f}  (Ziel 0.58–0.70)')
        total_xg = xg_home_sum + xg_away_sum
        w(f'\n  xG-Qualität:')
        w(f'    Heim-xG/Sp : {xg_home_sum/N:.3f}  Gast-xG/Sp : {xg_away_sum/N:.3f}')
        w(f'    Tore/xG    : {total_goals/max(1,total_xg):.3f}')

        # ── D: HEIMVORTEIL, BRACKETS, WECHSEL ────────────────────────────────
        w(f'\n{HR}'); w('  D  HEIMVORTEIL, STÄRKE-BRACKETS, WECHSEL'); w(HR)
        h_goals_mirror = sum(v[0] for v in mirrored.values())
        a_goals_mirror = sum(v[1] for v in mirrored.values())
        n_pairs = sum(v[2] for v in mirrored.values())
        w(f'  Heimvorteil (gespiegelte Paarungen):')
        w(f'    Ø Tore Heimmannschaft  : {h_goals_mirror/max(1,n_pairs):.3f}')
        w(f'    Ø Tore Gastmannschaft  : {a_goals_mirror/max(1,n_pairs):.3f}')
        w(f'    Heimtore-Anteil        : {_pct(int(h_goals_mirror),int(h_goals_mirror+a_goals_mirror))}')

        w('\n  Heimvorteil nach Stärkeverhältnis:')
        w(f'  {"Konstellation":>18}  {"N":>7}  {"Heim%":>6}  {"Remis%":>7}  {"Gast%":>6}')
        hv_labels = {
            'h_fav_big': 'Heim kl. Fav (Δ≥10)',
            'h_fav':     'Heim l. Fav (Δ1-9)',
            'equal':     'Ausgeglichen (Δ0)',
            'a_fav':     'Gast l. Fav (Δ1-9)',
            'a_fav_big': 'Gast kl. Fav (Δ≥10)',
        }
        for key, label in hv_labels.items():
            hv = hv_by_str[key]; n_hv = hv[3]
            if n_hv == 0: continue
            w(f'  {label:>22}  {n_hv:>7}  {_pct(hv[0],n_hv):>6}  {_pct(hv[1],n_hv):>7}  {_pct(hv[2],n_hv):>6}')

        w('\n  Stärke-Bracket-Analyse (Favorit vs. Außenseiter):')
        w(f'  {"Differenz":>10}  {"N":>6}  {"Fav%":>6}  {"Remis%":>7}  {"Auß%":>6}  '
          f'{"Ø GD":>6}  {"Ø xGD":>7}')
        for bkt, b in BKT.items():
            bn = b[0] + b[1] + b[2]
            if bn == 0: continue
            w(f'  {bkt:>10}  {bn:>6}  {_pct(b[0],bn):>6}  {_pct(b[1],bn):>7}  '
              f'{_pct(b[2],bn):>6}  {b[3]/bn:>+6.2f}  {b[4]/bn:>+7.3f}')

        w('\n  WECHSEL:')
        w(f'    Ø Wechsel/Spiel    : {total_subs_exec/N:.2f}')
        w(f'    davon Verletzung   : {total_inj_subs}  ({_pct(total_inj_subs, total_subs_exec)})')
        w(f'    Geplant aufgest.   : {total_planned_in}')
        w(f'    Geplant ausgeführt : {total_planned_exec}  ({_pct(total_planned_exec, total_planned_in)})')
        rel_total = hp_count + np_count + fp_count
        w(f'    HP / NP / FP       : {hp_count}/{np_count}/{fp_count}  (von {rel_total} klassifiziert)')
        avg_d = strength_delta_sum / strength_delta_n if strength_delta_n else 0.0
        w(f'    Ø Stärkeänderung   : {avg_d:+.2f}  (negativ = schwächerer Einwechsler)')
        if verbose:
            w('\n    Bedingungsverteilung:')
            for cond in sorted(cond_counts):
                n_in = cond_counts[cond]; n_ex = cond_exec.get(cond, 0)
                w(f'      {cond:>14}  aufgest.: {n_in:>7}  ausgeführt: {n_ex:>7}  '
                  f'Quote: {_pct(n_ex, n_in)}')
        if sub_minutes:
            w('\n    Wechsel-Timing:')
            bkts = {'≤55': 0, '56-65': 0, '66-75': 0, '76-85': 0, '86+': 0}
            for m in sub_minutes:
                if m <= 55:   bkts['≤55']   += 1
                elif m <= 65: bkts['56-65'] += 1
                elif m <= 75: bkts['66-75'] += 1
                elif m <= 85: bkts['76-85'] += 1
                else:         bkts['86+']   += 1
            mx = max(bkts.values()) or 1
            for lbl, cnt in bkts.items():
                w(f'      {lbl} min  {_bar(cnt,0,mx)}  {cnt}×  {_pct(cnt,len(sub_minutes))}')

        # ── E: VERLETZUNGEN, FRISCHE, TICKER ─────────────────────────────────
        w(f'\n{HR}'); w('  E  VERLETZUNGEN, FRISCHE, TICKER-INTEGRITÄT'); w(HR)

        inj_total_sum = inj_ingame + inj_postmatch
        w(f'  Verletzungen gesamt            : {inj_total_sum}  ({inj_total_sum/N:.3f}/Spiel, Ziel 0.15–0.22)')
        w(f'    davon in-game Wechsel        : {inj_ingame}  (V1 = 0 erwartet — nur post-match)')
        w(f'    davon post-match             : {inj_postmatch}  ({inj_postmatch/N:.3f}/Spiel)')
        if inj_total_sum:
            w(f'    Leicht (≤7 Tage)           : {inj_light}  ({_pct(inj_light,inj_total_sum)})')
            w(f'    Mittel (8–21 T.)           : {inj_mid}  ({_pct(inj_mid,inj_total_sum)})')
            w(f'    Schwer (22–56 T.)          : {inj_heavy}  ({_pct(inj_heavy,inj_total_sum)})')
            w(f'    Extrem (>56 T.)            : {inj_extreme}')
            if inj_days_n:
                w(f'    Ø Ausfalltage              : {inj_days_sum/inj_days_n:.1f}')
            if inj_days_list:
                w(f'    Median Ausfalltage         : {_median(inj_days_list):.1f}')
        inj_alarm = _alarm('Verletzungen/Spiel', inj_total_sum/N, BASELINE['inj_per_game'], ALARM['inj'])
        if inj_alarm: w(inj_alarm)

        # Verletzungen nach Frische-Bucket
        w('\n  Verletzungen nach Frische-Bucket (post-match):')
        w(f'  {"Bucket":>8}  {"Verlet.":>8}  {"Spieler-Sp.":>12}  {"Rate":>8}')
        for bucket, (inj_cnt, pg_cnt) in inj_fr_bucket.items():
            rate = inj_cnt / pg_cnt if pg_cnt else 0.0
            w(f'  {bucket:>8}  {inj_cnt:>8}  {pg_cnt:>12}  {rate:>8.4f}')
        w('  (Erwartung: Rate steigt mit sinkender Frische)')

        # Frische-Kurve über Saison
        if fr_by_matchday[0]:
            w('\n  Frische-Kurve über Saison (Ø Stammelf):')
            sample_days = [0, 8, 16, 24, 33]  # Spieltage 1,9,17,25,34 (0-indexed)
            pts_str = '  '
            for md in sample_days:
                if fr_by_matchday[md]:
                    pts_str += f'  ST{md+1:>2}: {_mean(fr_by_matchday[md]):.1f}%'
            w(pts_str)
            # ASCII-Kurve über alle 34 Spieltage
            fr_curve = [_mean(fr_by_matchday[md]) if fr_by_matchday[md] else 0.0
                        for md in range(34)]
            lo_fr = max(60.0, min(fr_curve) - 2)
            hi_fr = min(100.0, max(fr_curve) + 2)
            w('  Kurve (●=Ø Frische, Bereich 60–100%):')
            for md, fr_val in enumerate(fr_curve):
                pos = int(round((fr_val - lo_fr) / (hi_fr - lo_fr) * 30))
                pos = max(0, min(30, pos))
                bar = ' ' * pos + '●' + ' ' * (30 - pos)
                w(f'    ST{md+1:>2} [{bar}] {fr_val:.1f}%')

        # Frische allgemein
        if fr_start_list and fr_end_list:
            avg_start = _mean(fr_start_list); std_start = _std(fr_start_list)
            avg_end   = _mean(fr_end_list)
            under80   = sum(1 for f in fr_end_list if f < 80)
            under70   = sum(1 for f in fr_end_list if f < 70)
            w(f'\n  Frische (Starter, vor Spiel):')
            w(f'    Ø beim Anpfiff : {avg_start:.1f}%  σ={std_start:.1f}')
            w(f'    Ø nach Spiel   : {avg_end:.1f}%')
            w(f'    Unter 80%      : {_pct(under80, len(fr_end_list))}')
            w(f'    Unter 70%      : {_pct(under70, len(fr_end_list))}')

        # Ticker
        w('\n  TICKER-INTEGRITÄT:')
        try:
            ticker_result = _check_ticker_integrity()
            if ticker_result['ok']:
                w('    ✓ Alle Basis-Invarianten bestanden (Stabilität, Anti-Repetition, Score-Format)')
            else:
                for err in ticker_result['errors']:
                    w(f'    ✗ {err}')
        except Exception as exc:
            w(f'    ⚠ Ticker-Check fehlgeschlagen: {exc}')

        # ── F: PERFORMANCE ────────────────────────────────────────────────────
        w(f'\n{HR}'); w('  F  LAUFZEIT UND PERFORMANCE'); w(HR)
        w(f'  Gesamtlaufzeit     : {elapsed:.2f} s')
        w(f'  ms/Spiel           : {elapsed/N*1000:.2f}')
        w(f'  Spiele gesamt      : {total_games}')
        w(f'  Fehler gesamt      : {errors}')

        # ── G: TAKTIK-BALANCE ─────────────────────────────────────────────────
        w(f'\n{HR}'); w('  G  TAKTIK-BALANCE (6 Profile, strength-adjustiertes Δ)'); w(HR)
        # Global strength→pts linear fit (season-level)
        all_str = []; all_pts_s = []
        for k in _TACTIC_KEYS:
            for str_, pts_s in tactic_season[k]:
                all_str.append(str_); all_pts_s.append(pts_s)
        ta_g, tb_g = _linreg(all_str, all_pts_s)  # pts = ta + tb * strength

        w(f'  {"Taktik":>14}  {"N":>6}  {"Pts/Sp":>7}  {"Tore/Sp":>8}  {"GTA/Sp":>8}  '
          f'{"xG/Sp":>6}  {"xGA/Sp":>7}  {"Poss%":>6}  {"Ø Stärke":>9}  {"Δ adj":>7}')
        for k in _TACTIC_KEYS:
            ts = tactic_stats[k]
            n_ts = ts['n'] or 1
            avg_str = ts['str_sum'] / n_ts
            pts_per_game = ts['pts'] / n_ts
            expected_pts = ta_g + tb_g * avg_str
            delta_adj    = pts_per_game - (expected_pts / 34)  # season→game scale
            w(f'  {k:>14}  {ts["n"]:>6}  {ts["pts"]/n_ts:>7.3f}  '
              f'{ts["gf"]/n_ts:>8.3f}  {ts["ga"]/n_ts:>8.3f}  '
              f'{ts["xgf"]/n_ts:>6.3f}  {ts["xga"]/n_ts:>7.3f}  '
              f'{ts["poss"]/n_ts:>6.1f}  {avg_str:>9.1f}  {delta_adj:>+7.4f}')
        tac_alarm_tol = 0.10  # Alarm wenn |Δ adj pts/game| > 0.10
        max_delta = max(abs(ts['pts']/max(1,ts['n']) - (ta_g + tb_g*(ts['str_sum']/max(1,ts['n'])))/34)
                        for ts in tactic_stats.values())
        if max_delta > tac_alarm_tol:
            w(f'  ⚠ ALARM Taktik-Bias: max |Δ adj| = {max_delta:.4f} > {tac_alarm_tol}')
        else:
            w(f'  ✓ Taktik-Balance: max |Δ adj| = {max_delta:.4f} < {tac_alarm_tol}  — keine Dominanz')

        # ── H: FORMATIONS-BALANCE ─────────────────────────────────────────────
        w(f'\n{HR}'); w('  H  FORMATIONS-BALANCE (5 Formationen, strength-adjustiertes Δ)'); w(HR)
        all_str_f = []; all_pts_f = []
        for k in _FORMATION_KEYS:
            for str_, pts_s in formation_season[k]:
                all_str_f.append(str_); all_pts_f.append(pts_s)
        fa_g, fb_g = _linreg(all_str_f, all_pts_f)

        w(f'  {"Formation":>10}  {"N":>6}  {"Pts/Sp":>7}  {"Tore/Sp":>8}  {"GTA/Sp":>8}  '
          f'{"xG/Sp":>6}  {"xGA/Sp":>7}  {"Poss%":>6}  {"Ø Stärke":>9}  {"Δ adj":>7}  '
          f'{"HP%":>4}  {"NP%":>4}  {"FP%":>4}')
        for k in _FORMATION_KEYS:
            fs = formation_stats[k]; n_fs = fs['n'] or 1
            avg_str = fs['str_sum'] / n_fs
            pts_pg  = fs['pts'] / n_fs
            exp_pg  = (fa_g + fb_g * avg_str) / 34
            d_adj   = pts_pg - exp_pg
            fhp = form_hp[k]; fnp = form_np[k]; ffp = form_fp[k]
            ftot = fhp + fnp + ffp or 1
            w(f'  {k:>10}  {fs["n"]:>6}  {fs["pts"]/n_fs:>7.3f}  '
              f'{fs["gf"]/n_fs:>8.3f}  {fs["ga"]/n_fs:>8.3f}  '
              f'{fs["xgf"]/n_fs:>6.3f}  {fs["xga"]/n_fs:>7.3f}  '
              f'{fs["poss"]/n_fs:>6.1f}  {avg_str:>9.1f}  {d_adj:>+7.4f}  '
              f'{_pct(fhp,ftot):>4}  {_pct(fnp,ftot):>4}  {_pct(ffp,ftot):>4}')
        form_alarm_tol = 0.10
        max_delta_f = max(
            abs(fs['pts']/max(1,fs['n']) - (fa_g + fb_g*(fs['str_sum']/max(1,fs['n'])))/34)
            for fs in formation_stats.values()
        )
        if max_delta_f > form_alarm_tol:
            w(f'  ⚠ ALARM Formation-Bias: max |Δ adj| = {max_delta_f:.4f} > {form_alarm_tol}')
        else:
            w(f'  ✓ Formations-Balance: max |Δ adj| = {max_delta_f:.4f} < {form_alarm_tol}')

        # ── I: SPIELVERLAUF UND COMEBACKS ─────────────────────────────────────
        w(f'\n{HR}'); w('  I  SPIELVERLAUF UND COMEBACKS'); w(HR)
        if first_goal_total:
            first_goal_wins = first_goal_wins_h + first_goal_wins_a
            w(f'  Erstes Tor (von {first_goal_total} Spielen mit ≥1 Tor):')
            w(f'    Erste-Tor-Team gewinnt : {first_goal_wins}  ({_pct(first_goal_wins,first_goal_total)})')
        if ht_01_total:
            w(f'\n  Comebacks nach 0:1 zur Halbzeit:')
            w(f'    Spiele mit 0:1 HZ      : {ht_01_total}  ({_pct(ht_01_total,N)})')
            w(f'    Comeback (Remis/Sieg)  : {ht_01_comeback}  ({_pct(ht_01_comeback,ht_01_total)})')
        if ht_02_total:
            w(f'\n  Comebacks nach 0:2 zur Halbzeit:')
            w(f'    Spiele mit 0:2 HZ      : {ht_02_total}  ({_pct(ht_02_total,N)})')
            w(f'    Comeback (Remis/Sieg)  : {ht_02_comeback}  ({_pct(ht_02_comeback,ht_02_total)})')
        w(f'\n  Tore in letzten 15 Min (76–90) : {late_goals_total}  '
          f'({late_goals_total/max(1,total_goals)*100:.1f}% aller Tore, '
          f'{late_goals_total/N:.3f}/Spiel)')
        w(f'  Tore durch Einwechslungen       : {sub_goals_total}  '
          f'({sub_goals_total/max(1,total_goals)*100:.1f}% aller Tore)')
        if red_card_games:
            w(f'\n  Spiele mit Platzverweis         : {red_card_games}  ({_pct(red_card_games,N)})')
            w(f'  Tore nach erster Roter Karte    : {goals_after_red}  '
              f'({goals_after_red/max(1,red_card_games):.2f}/Spiel mit Rot)')

        # ── J: SAISONSTREUUNG ─────────────────────────────────────────────────
        w(f'\n{HR}'); w('  J  SAISONSTREUUNG UND EXTREMWERTE'); w(HR)
        if season_champion_pts:
            w(f'  Meisterpunkte:')
            w(f'    Ø   : {_mean(season_champion_pts):.1f}')
            w(f'    Min : {min(season_champion_pts)}  Max : {max(season_champion_pts)}  σ : {_std(season_champion_pts):.1f}')
        if season_relegation_pts:
            w(f'  Abstiegsgrenze (18. Platz):')
            w(f'    Ø   : {_mean(season_relegation_pts):.1f}')
            w(f'    Min : {min(season_relegation_pts)}  Max : {max(season_relegation_pts)}  σ : {_std(season_relegation_pts):.1f}')
        if season_title_delta:
            w(f'  Titelkampf (Pkt-Abstand Platz 1→2):')
            w(f'    Ø   : {_mean(season_title_delta):.1f}')
            w(f'    Min : {min(season_title_delta)}  Max : {max(season_title_delta)}  σ : {_std(season_title_delta):.1f}')
            w(f'    Knappe Titel (≤2 Pkt Vorsprung): '
              f'{sum(1 for d in season_title_delta if d <= 2)}×  '
              f'({_pct(sum(1 for d in season_title_delta if d <= 2), n_seas)})')

        # ── K: KONFIDENZINTERVALLE ────────────────────────────────────────────
        w(f'\n{HR}'); w('  K  KONFIDENZINTERVALLE (95%-KI)'); w(HR)
        ci_gpg  = _ci95(goals_per_game_list)
        ci_drw  = (drw - 1.96*math.sqrt(drw*(1-drw)/N), drw + 1.96*math.sqrt(drw*(1-drw)/N))
        ci_inj  = (inj_total_sum/N - 1.96*math.sqrt((inj_total_sum/N)/N),
                   inj_total_sum/N + 1.96*math.sqrt((inj_total_sum/N)/N))
        boot_rng = random.Random(seed0 + 1)
        ci_spear = _bootstrap_spearman_ci(str_ranks_all, avg_pos_by_str, 500, boot_rng)
        w(f'  Tore/Spiel     : {gpg:.4f}  95%-KI [{ci_gpg[0]:.4f}, {ci_gpg[1]:.4f}]')
        w(f'  Remis%         : {drw:.4f}  95%-KI [{ci_drw[0]:.4f}, {ci_drw[1]:.4f}]')
        w(f'  Verletz./Spiel : {inj_total_sum/N:.4f}  95%-KI [{ci_inj[0]:.4f}, {ci_inj[1]:.4f}]')
        w(f'  Spearman(str→pos): {r_str_pos:.4f}  Bootstrap 95%-KI [{ci_spear[0]:.4f}, {ci_spear[1]:.4f}]')
        w(f'  (n={N} Spiele, Bootstrap 500 Subsampling à {N_CLUBS//2} Clubs)')

        w(f'\n{HR}\n')

        # Export
        if out_dir:
            self._export(out_dir, n_seas, total_games, elapsed, club_seasons,
                         championship, top4, bottom3, N, total_goals, total_yellow,
                         total_red, home_wins, draws, away_wins)
        return metrics

    # ── Multi-Seed Stabilitätstabelle ────────────────────────────────────────

    def _print_stability_table(self, all_metrics: list[tuple[int, dict]]):
        w  = self.stdout.write
        HR = '─' * 72
        w(f'\n{HR}')
        w(f'  MULTI-SEED STABILITÄTSBERICHT  ({len(all_metrics)} Seeds)')
        w(HR)

        keys = ['goals_per_game', 'home_pct', 'draw_pct', 'away_pct',
                'spearman', 'pearson_xgd', 'inj_per_game', 'yellow_per_game']
        labels = ['Tore/Sp', 'Heim%', 'Remis%', 'Aus%',
                  'Spearman', 'xGD-Pearson', 'Verletz./Sp', 'Gelb/Sp']

        # Tabellenkopf
        header = f'  {"Metrik":>14} '
        for seed, _ in all_metrics:
            header += f'  {seed:>8}'
        header += f'  {"Min":>8}  {"Max":>8}  {"Δ":>6}  {"Δ/Med%":>7}  Status'
        w(header)
        w('  ' + '─' * (len(header) - 2))

        all_ok = True
        STAB_TOL = 0.05  # 5% Abweichung vom Median = ALARM
        for key, lbl in zip(keys, labels):
            vals = [m.get(key, 0.0) for _, m in all_metrics]
            mn = min(vals); mx = max(vals); delta = mx - mn
            med = _median(vals)
            pct_delta = delta / abs(med) if med else delta
            status = '✓' if pct_delta <= STAB_TOL else '⚠'
            if pct_delta > STAB_TOL:
                all_ok = False
            row = f'  {lbl:>14} '
            for v in vals:
                row += f'  {v:>8.4f}'
            row += f'  {mn:>8.4f}  {mx:>8.4f}  {delta:>6.4f}  {100*pct_delta:>6.1f}%  {status}'
            w(row)

        w(f'\n  Gesamtbefund: {"✓ STABIL (alle Metriken ≤5% Abweichung)" if all_ok else "⚠ INSTABIL — mindestens eine Metrik > 5%"}')
        w(f'{HR}\n')

    # ── Export ────────────────────────────────────────────────────────────────

    def _export(self, out_dir, n_seas, total_games, elapsed, club_seasons,
                championship, top4, bottom3, N, total_goals, total_yellow,
                total_red, home_wins, draws, away_wins):
        os.makedirs(out_dir, exist_ok=True)

        summary = {
            'n_seasons': n_seas, 'total_games': total_games,
            'elapsed_s': round(elapsed, 2), 'ms_per_game': round(elapsed/N*1000, 2),
            'goals_per_game': round(total_goals/N, 4),
            'home_win_pct': round(home_wins/N, 4),
            'draw_pct': round(draws/N, 4),
            'away_win_pct': round(away_wins/N, 4),
            'yellow_per_game': round(total_yellow/N, 3),
            'red_per_game': round(total_red/N, 4),
        }
        with open(os.path.join(out_dir, 'summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)

        with open(os.path.join(out_dir, 'club_averages.csv'), 'w', newline='') as f:
            wc = csv.writer(f)
            wc.writerow(['club_id', 'name', 'strength', 'avg_pts', 'avg_pos',
                         'championships', 'top4', 'relegated'])
            for cid, seass in club_seasons.items():
                ci = CLUBS[CID_INDEX[cid]]
                wc.writerow([cid, ci['name'], ci['strength'],
                             round(_mean([s['pts'] for s in seass]), 2),
                             round(_mean([s['pos'] for s in seass]), 2),
                             championship.get(cid, 0),
                             top4.get(cid, 0),
                             bottom3.get(cid, 0)])
        self.stdout.write(f'  Export → {out_dir}/')

    # ── V1-kompatibler Schnellmodus ───────────────────────────────────────────

    def _run_quick_mode(self, N: int, seed0: int, verbose: bool):
        w   = self.stdout.write
        rng = random.Random(seed0)
        STRENGTHS = [50, 55, 60, 65, 70, 75, 80]
        t0  = time.time()
        total = wins = draws = losses = goals = xg_sum = 0
        for _ in range(N):
            s1 = rng.choice(STRENGTHS); s2 = rng.choice(STRENGTHS)
            pid1 = rng.randint(1, 10000); pid2 = rng.randint(10001, 20000)
            bench1 = [pid1 * 200 + 11 + j for j in range(N_BENCH)]
            bench2 = [pid2 * 200 + 11 + j for j in range(N_BENCH)]
            psubs1 = _make_subs_v1(pid1, pid1 * 200, bench1)
            psubs2 = _make_subs_v1(pid2, pid2 * 200, bench2)
            t1 = _make_team_v1(pid1, s1, psubs1)
            t2 = _make_team_v1(pid2, s2, psubs2)
            try:
                sim = _simulate_match_minutes(t1, t2)
            except Exception:
                continue
            hg = sim['home_goals']; ag = sim['away_goals']
            total += 1; goals += hg + ag
            xg_sum += float(sim.get('home_xg') or 0) + float(sim.get('away_xg') or 0)
            if hg > ag: wins += 1
            elif hg == ag: draws += 1
            else: losses += 1
        elapsed = time.time() - t0
        w(f'\n  Schnellmodus: {total} Spiele in {elapsed:.1f}s  ({elapsed/max(1,total)*1000:.2f}ms/Sp)')
        def pct(n, d): return f'{100*n/d:.1f}%' if d else 'n/a'
        w(f'  Heim/Remis/Auswärts: {pct(wins,total)} / {pct(draws,total)} / {pct(losses,total)}')
        w(f'  Tore/Spiel: {goals/max(1,total):.3f}   xG/Spiel: {xg_sum/max(1,total):.3f}')
