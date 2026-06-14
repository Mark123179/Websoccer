"""Regressionsbericht V2 — 100 vollständige Bundesliga-Saisons (kein ORM).

Aufruf:
  python manage.py regression_sim                 # 100 Saisons
  python manage.py regression_sim --seasons 10    # schneller Test
  python manage.py regression_sim --games 3400    # V1-kompatibler Schnellmodus
  python manage.py regression_sim --output /tmp/reg_out

Sektionen:
  A  Technische Integrität         (alle Violations müssen 0 sein)
  B  Match- und Ergebnisverteilung (Tore, xG, Karten, Ergebnisquoten)
  C  Tabelle und Stärkeverhalten   (100-Saisons-Standings, Meisterhäufigkeit)
  D  Heimvorteil, Stärke-Brackets, Wechsel
  E  Verletzungen, Frische, Ticker-Integrität
  F  Laufzeit und Performance
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


# ── Konstanten ────────────────────────────────────────────────────────────────

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

SLOTS = [
    ('TW', 'goalkeeper'),
    ('LV', 'defense'), ('IV', 'defense'), ('IV', 'defense'), ('RV', 'defense'),
    ('LM', 'midfield'), ('ZM', 'midfield'), ('ZM', 'midfield'), ('RM', 'midfield'),
    ('ST', 'attack'), ('ST', 'attack'),
]
BENCH_POS   = ['ST', 'ZM', 'LV', 'ZM', 'ST', 'IV', 'LM']
N_STARTERS  = len(SLOTS)
N_BENCH     = len(BENCH_POS)

# Akzeptierte Basiswerte (vorheriger 100-Saisons-Lauf)
BASELINE = {
    'goals_per_game': 2.707,
    'home_win_pct':   0.386,
    'draw_pct':       0.259,
    'away_win_pct':   0.355,
    'fav_win_pct':    0.587,
    'yellow_per_game': 2.92,
    'red_per_game':    0.055,
    'shots_per_game': 21.2,
    'inj_per_game':   0.18,
}

ALARM = {          # maximale Abweichung vom Baseline bevor Alarm
    'goals':  0.05,
    'result': 0.015,
    'cards':  0.15,
    'inj':    0.15,
}


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
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


def _pct(n: int, d: int) -> str:
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


# ── Spielplanzeugung ─────────────────────────────────────────────────────────

def _make_schedule() -> list[list[tuple[int, int]]]:
    """Doppelter Rundenplan für N_CLUBS Teams (Kreis-Methode).

    Gibt 2*(N-1) Spieltage zurück, jeder mit N//2 (Heim-ID, Gast-ID)-Paaren.
    Summe: 18 × 17 = 306 Spiele pro Saison, 34 Spieltage.
    """
    n = N_CLUBS
    ids = [c['id'] for c in CLUBS]
    first_leg: list[list[tuple[int, int]]] = []
    for rnd in range(n - 1):
        pairs = []
        for k in range(n // 2):
            h = ids[k]
            a = ids[n - 1 - k]
            pairs.append((h, a))
        first_leg.append(pairs)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    second_leg = [[(a, h) for h, a in rnd] for rnd in first_leg]
    return first_leg + second_leg


SCHEDULE = _make_schedule()   # 34 Spieltage × 9 Spiele (erstellt einmal)


# ── Team-Bau ─────────────────────────────────────────────────────────────────

def _player_id(cid: int, slot: int) -> int:
    return cid * 200 + slot


def _make_league_team(club: dict, freshness_arr: list[float],
                       rng: random.Random, psubs: list) -> dict:
    cid  = club['id']
    str0 = club['strength']
    players, lineup = [], []
    for i, (pos, grp) in enumerate(SLOTS):
        pid  = _player_id(cid, i)
        fr   = int(max(30, min(100, freshness_arr[i])))
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
        'tactic': {},
        'bench_player_data': bench,
        'planned_substitutions': psubs,
    }


def _make_psubs(cid: int, rng: random.Random) -> list[dict]:
    starters = [_player_id(cid, i) for i in range(7, 11)]
    bench    = [_player_id(cid, N_STARTERS + j) for j in range(N_BENCH)]
    rng.shuffle(starters)
    rng.shuffle(bench)
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


def _update_freshness_after_game(fr_map: dict, cid: int,
                                  sub_events: list, rng: random.Random):
    """Frische-Update nach einem Spieltag.

    Alle Spieler erhalten zuerst Wochenend-Recovery (≈ 1 Woche Pause zwischen
    Bundesliga-Spieltagen), dann wird für die tatsächlich eingesetzten Spieler
    Match-Fatigue abgezogen.  Netto für 90-min-Starter: ≈ -0,5/Spiel → sanfte
    Abnahme von ~90 auf ~73 über eine 34-Spieltage-Saison.
    """
    arr         = fr_map[cid]
    swapped_in  = {e['in']  for e in sub_events if e.get('in')}
    swapped_out = {e['out'] for e in sub_events if e.get('out')}

    for i in range(N_STARTERS + N_BENCH):
        pid = _player_id(cid, i)

        # 1. Wochenregeneration (alle Spieler)
        recovery = rng.uniform(4.0, 6.0)          # Ø +5.0
        arr[i]   = min(100.0, arr[i] + recovery)

        # 2. Match-Fatigue nur für eingesetzte Spieler
        if i < N_STARTERS:
            if pid in swapped_out:                 # früh ausgewechselt
                fatigue = rng.uniform(3.5, 5.5)   # Ø +4.5 → netto Ø +0.5
            else:                                  # volle 90 min
                fatigue = rng.uniform(5.0, 6.5)   # Ø +5.75 → netto Ø -0.75
            arr[i] = max(30.0, arr[i] - fatigue)
        elif pid in swapped_in:                    # Joker (ca. 25–35 min)
            fatigue = rng.uniform(2.5, 4.0)        # Ø +3.25 → netto Ø +1.75
            arr[i] = max(30.0, arr[i] - fatigue)


# ── V1-kompatibler Schnellmodus ───────────────────────────────────────────────

SLOTS_V1 = SLOTS
BENCH_POS_V1 = BENCH_POS

def _make_team_v1(seed: int, strength: float, psubs: list) -> dict:
    rng = random.Random(seed)
    pid_base = seed * 200
    players, lineup = [], []
    for i, (pos, grp) in enumerate(SLOTS_V1):
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
    for j, pos in enumerate(BENCH_POS_V1):
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
    result = []
    used_out: set = set()
    for k in range(min(n, len(bench_pids), len(targets))):
        if targets[k] in used_out:
            continue
        used_out.add(targets[k])
        result.append({
            'in': bench_pids[k], 'out': targets[k],
            'minute': 55 + k * 10, 'condition': conditions[k % len(conditions)],
        })
    return result


# ── Ticker-Integritätsprüfung (Section 15) ───────────────────────────────────

def _check_ticker_integrity(n_samples: int = 200) -> dict:
    """Überprüft grundlegende Ticker-Invarianten ohne ORM."""
    from game.ticker_commentary import stable_seed, build_ticker_text, build_flow_text
    errors: list[str] = []
    rng = random.Random(9999)

    # 1. Stabilität: gleiche Parameter → gleicher Text
    for _ in range(50):
        ms  = rng.randint(0, 2**32)
        ei  = rng.randint(0, 20)
        min_ = rng.randint(1, 90)
        t1 = build_ticker_text('shot', minute=min_, player='Müller',
                               match_seed=ms, event_index=ei)
        t2 = build_ticker_text('shot', minute=min_, player='Müller',
                               match_seed=ms, event_index=ei)
        if t1 != t2:
            errors.append(f'Instabiler Text: shot min={min_} seed={ms} ei={ei}')

    # 2. Anti-Repetition: erste N Texte aller Shot-Varianten sollten eindeutig sein
    ms = 12345678
    shots = [build_ticker_text('shot', minute=i+1, player=f'P{i}',
                               match_seed=ms, event_index=i) for i in range(15)]
    if len(set(shots)) < 10:
        errors.append(f'Zu viele Wiederholungen in Shot-Pool: {len(set(shots))}/15 eindeutig')

    # 3. stable_seed: identische Eingaben → identischer Seed
    s1 = stable_seed('Bayern', 'Dortmund', 3, 1)
    s2 = stable_seed('Bayern', 'Dortmund', 3, 1)
    s3 = stable_seed('Bayern', 'Dortmund', 3, 2)
    if s1 != s2:
        errors.append('stable_seed: gleiche Eingabe → unterschiedlicher Seed')
    if s1 == s3:
        errors.append('stable_seed: verschiedene Eingabe → gleicher Seed')

    # 4. build_flow_text: zwei Aufrufe mit gleichen Params → gleicher Text
    t1 = build_flow_text(45, 54321, 3, 'Bayern', 'BVB')
    t2 = build_flow_text(45, 54321, 3, 'Bayern', 'BVB')
    if t1 != t2:
        errors.append('build_flow_text: instabil')

    # 5. Goal texts erzeugen Score-String
    for i in range(20):
        txt = build_ticker_text('goal', minute=30+i, player='Lewandowski',
                                assister='Müller', score_h=1, score_a=0,
                                match_seed=ms, event_index=i)
        if '1:0' not in txt:
            errors.append(f'Tor-Text enthält kein Score-Format: {txt[:60]}')
            break

    return {'errors': errors, 'ok': len(errors) == 0}


# ── Hauptklasse ───────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Regressionsbericht V2 — 100 Bundesliga-Saisons (kein ORM)'

    def add_arguments(self, parser):
        parser.add_argument('--seasons', type=int, default=100,
                            help='Anzahl Saisons im Liga-Modus (Default: 100)')
        parser.add_argument('--games',   type=int, default=0,
                            help='Schnellmodus: N zufällige Spiele statt Saisons')
        parser.add_argument('--seed',    type=int, default=42)
        parser.add_argument('--output',  type=str, default='',
                            help='Verzeichnis für CSV/JSON-Export')
        parser.add_argument('--verbose', action='store_true', default=False)

    def handle(self, *args, **options):
        quick_n  = options['games']
        n_seas   = options['seasons']
        seed0    = options['seed']
        out_dir  = options['output']
        verbose  = options['verbose']

        if quick_n > 0:
            self._run_quick_mode(quick_n, seed0, verbose)
        else:
            self._run_league_mode(n_seas, seed0, verbose, out_dir)

    # ── Liga-Modus ───────────────────────────────────────────────────────────

    def _run_league_mode(self, n_seas: int, seed0: int, verbose: bool, out_dir: str):
        w  = self.stdout.write
        HR = '─' * 72

        N_GAMES = n_seas * N_CLUBS * (N_CLUBS - 1)  # 100 × 306 = 30 600
        w(f'\n{HR}')
        w(f'  Regressionsbericht V2  —  {n_seas} Saisons × 306 Spiele = {N_GAMES} Gesamt')
        w(f'{HR}')

        t0  = time.time()
        rng = random.Random(seed0)

        # ── Akkumulatoren ────────────────────────────────────────────────────
        total_games = 0
        errors      = 0

        # A: Integrität
        v_double_sub   = 0
        v_post_sub_goal = 0
        v_post_dis_goal = 0
        v_neg_xg        = 0
        v_invalid_poss  = 0
        v_over_5_subs   = 0

        # B: Engine-Metriken
        total_goals = home_wins = draws = away_wins = 0
        total_yellow = total_red = 0
        xg_home_sum = xg_away_sum = 0.0
        shots_sum = shots_on_sum = corners_sum = fouls_sum = 0
        goals_phase = [0, 0, 0]
        scores: dict[str, int] = {}
        poss_list: list[int] = []

        # Pressing / Angriffszonen
        press_wins_h = press_wins_a = 0
        press_bp_h   = press_bp_a   = 0
        att_left = att_center = att_right = 0

        # C: Tabellen / Standings
        # club_id → list of (season_pts, season_gf, season_ga, pos_1based)
        club_seasons: dict[int, list[dict]] = defaultdict(list)
        championship: dict[int, int] = defaultdict(int)
        top4:         dict[int, int] = defaultdict(int)
        bottom3:      dict[int, int] = defaultdict(int)

        # D: Stärke-Brackets
        BKT = {'3-7': [0,0,0,0.0,0.0], '8-14': [0,0,0,0.0,0.0],
               '15-24': [0,0,0,0.0,0.0], '25+': [0,0,0,0.0,0.0]}
        # [fav_wins, draws, fav_losses, gd_sum, xgd_sum]

        # Heimvorteil: für gespiegelte Paare
        # pair (min_id, max_id) → [home_goals, away_goals, n_games]
        mirrored: dict[tuple, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])

        # D: Wechsel
        total_subs_exec = total_planned_in = total_planned_exec = 0
        total_inj_subs  = 0
        hp_count = np_count = fp_count = 0
        strength_delta_sum = 0.0; strength_delta_n = 0
        cond_counts: dict[str, int] = {}
        cond_exec:   dict[str, int] = {}
        sub_minutes: list[int] = []

        # E: Verletzungen (getrennt: in-game Wechsel vs. post-match)
        inj_ingame  = 0   # in-game Verletzungswechsel (condition='verletzung')
        inj_postmatch = 0 # post-match via _generate_injury_events
        inj_light = inj_mid = inj_heavy = inj_extreme = 0
        inj_days_sum = 0; inj_days_n = 0

        # Frische-Tracking (über alle Spieltage)
        fr_start_list: list[float] = []
        fr_end_list:   list[float] = []

        # xGD–Punkte-Korrelation (pro Saison)
        season_xgd_pts: list[tuple[float, float]] = []   # (xgd_club, pts_club)

        # ── Saisonschleife ────────────────────────────────────────────────────
        for season_i in range(n_seas):
            season_rng  = random.Random(seed0 * 100000 + season_i)
            fr_map      = _init_freshness(season_rng)

            # Saisonstatistiken
            standing: dict[int, dict] = {
                c['id']: {'pts': 0, 'gf': 0, 'ga': 0,
                          'xgf': 0.0, 'xga': 0.0, 'won': 0}
                for c in CLUBS
            }

            for md_i, matchday in enumerate(SCHEDULE):
                for h_id, a_id in matchday:
                    game_rng   = random.Random(season_rng.randint(0, 2**32))
                    h_club     = CLUBS[CID_INDEX[h_id]]
                    a_club     = CLUBS[CID_INDEX[a_id]]
                    h_psubs    = _make_psubs(h_id, game_rng)
                    a_psubs    = _make_psubs(a_id, game_rng)

                    # Frische erfassen (vor Spiel)
                    h_fr_avg = _mean(fr_map[h_id][:N_STARTERS])
                    a_fr_avg = _mean(fr_map[a_id][:N_STARTERS])
                    fr_start_list.append(h_fr_avg)
                    fr_start_list.append(a_fr_avg)

                    for ps in h_psubs + a_psubs:
                        c = ps.get('condition', 'immer')
                        cond_counts[c] = cond_counts.get(c, 0) + 1
                    total_planned_in += len(h_psubs) + len(a_psubs)

                    home_team = _make_league_team(h_club, fr_map[h_id], game_rng, h_psubs)
                    away_team = _make_league_team(a_club, fr_map[a_id], game_rng, a_psubs)

                    try:
                        sim = _simulate_match_minutes(home_team, away_team)
                    except Exception as exc:
                        errors += 1
                        self.stderr.write(f'  ERROR s{season_i} md{md_i}: {exc}')
                        continue

                    total_games += 1
                    hg, ag  = sim['home_goals'], sim['away_goals']
                    hxg, axg = float(sim.get('home_xg') or 0), float(sim.get('away_xg') or 0)
                    ms_     = sim.get('match_stats', {}) or {}

                    # ── Integrität A ──────────────────────────────────────────
                    if hxg < 0 or axg < 0 or math.isnan(hxg) or math.isnan(axg):
                        v_neg_xg += 1
                    hp  = ms_.get('home_possession', 50) or 50
                    ap  = ms_.get('away_possession', 50) or 50
                    if abs((hp + ap) - 100) > 2:
                        v_invalid_poss += 1

                    h_evts = sim.get('h_sim_sub_events', [])
                    a_evts = sim.get('a_sim_sub_events', [])
                    all_subs = h_evts + a_evts
                    if len([e for e in h_evts if e.get('condition') != 'verletzung']) > MAX_SUBSTITUTIONS:
                        v_over_5_subs += 1
                    if len([e for e in a_evts if e.get('condition') != 'verletzung']) > MAX_SUBSTITUTIONS:
                        v_over_5_subs += 1

                    for side_evts in (h_evts, a_evts):
                        in_pids = [e['in'] for e in side_evts if e.get('in')]
                        if len(in_pids) != len(set(in_pids)):
                            v_double_sub += 1
                        out_map = {e['out']: e['minute'] for e in side_evts if e.get('out')}
                        for ge in sim.get('goal_events', []):
                            sid  = ge.get('scorer_id')
                            gmin = ge.get('minute', 0)
                            if sid and sid in out_map and gmin > out_map[sid]:
                                v_post_sub_goal += 1

                    dis_evts = sim.get('dismissal_events', [])
                    dis_map: dict = {}
                    for de in dis_evts:
                        dis_map[de.get('player_id')] = de.get('minute', 0)
                    for ge in sim.get('goal_events', []):
                        sid  = ge.get('scorer_id')
                        gmin = ge.get('minute', 0)
                        if sid and sid in dis_map and gmin > dis_map[sid]:
                            v_post_dis_goal += 1

                    # ── Ergebnisse B ──────────────────────────────────────────
                    total_goals += hg + ag
                    key = f'{hg}:{ag}'
                    scores[key] = scores.get(key, 0) + 1
                    if hg > ag:    home_wins += 1
                    elif hg == ag: draws     += 1
                    else:          away_wins += 1

                    total_yellow += ms_.get('home_yellow', 0) + ms_.get('away_yellow', 0)
                    total_red    += ms_.get('home_red',    0) + ms_.get('away_red',    0)
                    xg_home_sum  += hxg; xg_away_sum += axg

                    shots_sum    += ms_.get('home_shots', 0) + ms_.get('away_shots', 0)
                    shots_on_sum += ms_.get('home_shots_on_target', 0) + ms_.get('away_shots_on_target', 0)
                    corners_sum  += ms_.get('home_corners', 0) + ms_.get('away_corners', 0)
                    fouls_sum    += ms_.get('home_fouls', 0) + ms_.get('away_fouls', 0)
                    press_wins_h += ms_.get('home_pressing_ball_wins', 0)
                    press_wins_a += ms_.get('away_pressing_ball_wins', 0)
                    press_bp_h   += ms_.get('home_pressing_bypassed', 0)
                    press_bp_a   += ms_.get('away_pressing_bypassed', 0)
                    att_left     += ms_.get('home_attacks_left', 0) + ms_.get('away_attacks_left', 0)
                    att_center   += ms_.get('home_attacks_center', 0) + ms_.get('away_attacks_center', 0)
                    att_right    += ms_.get('home_attacks_right', 0) + ms_.get('away_attacks_right', 0)
                    poss_list.append(hp)

                    for ge in sim.get('goal_events', []):
                        m = ge.get('minute', 45)
                        if m <= 30:   goals_phase[0] += 1
                        elif m <= 60: goals_phase[1] += 1
                        else:         goals_phase[2] += 1

                    # ── Stärke-Brackets D ─────────────────────────────────────
                    h_str = h_club['strength']
                    a_str = a_club['strength']
                    diff  = abs(h_str - a_str)
                    fav_home = h_str > a_str
                    if diff >= 3:
                        bkt = ('3-7' if diff < 8 else
                               '8-14' if diff < 15 else
                               '15-24' if diff < 25 else '25+')
                        b = BKT[bkt]
                        fav_won = (fav_home and hg > ag) or (not fav_home and ag > hg)
                        is_draw = hg == ag
                        if fav_won:  b[0] += 1
                        elif is_draw: b[1] += 1
                        else:        b[2] += 1
                        gd = hg - ag if fav_home else ag - hg
                        b[3] += gd
                        b[4] += (hxg - axg) if fav_home else (axg - hxg)

                    # ── Heimvorteil gespiegelt ────────────────────────────────
                    pair_key = (min(h_id, a_id), max(h_id, a_id))
                    m_entry  = mirrored[pair_key]
                    if h_id < a_id:
                        m_entry[0] += hg; m_entry[1] += ag
                    else:
                        m_entry[0] += ag; m_entry[1] += hg
                    m_entry[2] += 1

                    # ── Standings C ───────────────────────────────────────────
                    s_h = standing[h_id]
                    s_a = standing[a_id]
                    s_h['gf'] += hg; s_h['ga'] += ag
                    s_a['gf'] += ag; s_a['ga'] += hg
                    s_h['xgf'] += hxg; s_h['xga'] += axg
                    s_a['xgf'] += axg; s_a['xga'] += hxg
                    if hg > ag:   s_h['pts'] += 3; s_h['won'] += 1
                    elif hg == ag: s_h['pts'] += 1; s_a['pts'] += 1
                    else:         s_a['pts'] += 3; s_a['won'] += 1

                    # ── Wechsel D ─────────────────────────────────────────────
                    for side_evts, side_team in ((h_evts, home_team), (a_evts, away_team)):
                        pid_str_map = {p['id']: p['final_strength']
                                       for p in side_team['players']}
                        pid_str_map.update({pid: p['final_strength']
                                            for pid, p in side_team['bench_player_data'].items()})
                        for evt in side_evts:
                            in_p  = evt.get('in')
                            out_p = evt.get('out')
                            cond  = evt.get('condition', 'immer')
                            rel   = evt.get('position_relation', '')
                            minute = evt.get('minute', 0)
                            total_subs_exec += 1
                            if cond == 'verletzung':
                                total_inj_subs += 1
                            else:
                                total_planned_exec += 1
                                cond_exec[cond] = cond_exec.get(cond, 0) + 1
                            if rel == 'HP':   hp_count += 1
                            elif rel == 'NP': np_count += 1
                            elif rel == 'FP': fp_count += 1
                            if in_p and out_p:
                                delta = pid_str_map.get(in_p, 0) - pid_str_map.get(out_p, 0)
                                strength_delta_sum += delta; strength_delta_n += 1
                            if minute:
                                sub_minutes.append(minute)

                    # ── Verletzungen E ───────────────────────────────────────
                    # a) In-game Verletzungswechsel (condition='verletzung')
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

                    # b) Post-Match-Verletzungen via _generate_injury_events
                    for pm_team, pm_side in ((home_team, 'home'), (away_team, 'away')):
                        pm_evts = _generate_injury_events(pm_team['players'], pm_side)
                        for evt in pm_evts:
                            days = evt.get('days', 5)
                            inj_postmatch += 1
                            if days <= 7:    inj_light   += 1
                            elif days <= 21: inj_mid     += 1
                            elif days <= 56: inj_heavy   += 1
                            else:            inj_extreme += 1
                            inj_days_sum += days; inj_days_n += 1

                    # ── Frische nach Spiel ────────────────────────────────────
                    _update_freshness_after_game(fr_map, h_id, h_evts, game_rng)
                    _update_freshness_after_game(fr_map, a_id, a_evts, game_rng)
                    fr_end_list.append(_mean(fr_map[h_id][:N_STARTERS]))
                    fr_end_list.append(_mean(fr_map[a_id][:N_STARTERS]))

            # ── Saison auswerten ──────────────────────────────────────────────
            sorted_clubs = sorted(standing.items(),
                                  key=lambda x: (-x[1]['pts'], -(x[1]['gf'] - x[1]['ga'])))
            for pos_idx, (cid, st) in enumerate(sorted_clubs):
                club_seasons[cid].append({
                    'pts': st['pts'], 'gf': st['gf'], 'ga': st['ga'],
                    'pos': pos_idx + 1,
                    'xgd': st['xgf'] - st['xga'],
                })
                # xGD–Punkte für Korrelation
                season_xgd_pts.append((st['xgf'] - st['xga'], st['pts']))
            championship[sorted_clubs[0][0]]  += 1
            for cid, _ in sorted_clubs[:4]:   top4[cid]    += 1
            for cid, _ in sorted_clubs[-3:]:  bottom3[cid] += 1

        elapsed = time.time() - t0
        w(f'  Laufzeit    : {elapsed:.1f} s  ({elapsed/max(1,total_games)*1000:.1f} ms/Spiel)')
        w(f'  Fehler      : {errors}  ← muss 0 sein')

        # ════════════════════════════════════════════════════════════════════
        # SEKTION A — TECHNISCHE INTEGRITÄT
        # ════════════════════════════════════════════════════════════════════
        w(f'\n{HR}')
        w('  A  TECHNISCHE INTEGRITÄT')
        w(HR)

        def _chk(label: str, n: int) -> str:
            return f'  {"✓" if n==0 else "✗ FAIL"}  {label:44}  {n}'

        w(_chk('Exceptions',                    errors))
        w(_chk('Doppelte Einwechslungen',        v_double_sub))
        w(_chk('Tore nach Auswechslung',         v_post_sub_goal))
        w(_chk('Tore nach Platzverweis',         v_post_dis_goal))
        w(_chk('Negative / NaN xG',             v_neg_xg))
        w(_chk('Ungültige Ballbesitzsumme',     v_invalid_poss))
        w(_chk('Geplante Wechsel > 5',          v_over_5_subs))

        integrity_ok = all(v == 0 for v in [
            errors, v_double_sub, v_post_sub_goal, v_post_dis_goal,
            v_neg_xg, v_invalid_poss, v_over_5_subs])
        w(f'\n  Gesamtstatus: {"✓ ALLE INVARIANTEN GRÜN" if integrity_ok else "✗ FEHLER — SIEHE OBEN"}')

        # ════════════════════════════════════════════════════════════════════
        # SEKTION B — MATCH- UND ERGEBNISVERTEILUNG
        # ════════════════════════════════════════════════════════════════════
        N = total_games or 1
        w(f'\n{HR}')
        w('  B  MATCH- UND ERGEBNISVERTEILUNG')
        w(HR)

        gpg  = total_goals / N
        hw   = home_wins / N
        drw  = draws / N
        aw   = away_wins / N
        ypg  = total_yellow / N
        rpg  = total_red / N
        spg  = shots_sum / N
        xh   = xg_home_sum / N
        xa   = xg_away_sum / N

        w(f'  Tore/Spiel        : {gpg:.3f}  '
          f'(Heim xG {xh:.2f}  /  Gast xG {xa:.2f}  /  Gesamt xG/Spiel {xh+xa:.2f})')
        w(f'  Heim / Remis / Aus: {home_wins}/{draws}/{away_wins}  '
          f'({_pct(home_wins,N)} / {_pct(draws,N)} / {_pct(away_wins,N)})')
        w(f'  Gelb/Spiel        : {ypg:.2f}')
        w(f'  Rot/Spiel         : {rpg:.4f}')
        w(f'  Schüsse/Spiel     : {spg:.1f}')
        w(f'  Schüsse aufs Tor  : {shots_on_sum/N:.1f}  '
          f'(Schüsse/Tor: {shots_sum/max(1,total_goals):.1f})')
        w(f'  Ecken/Spiel       : {corners_sum/N:.1f}')
        w(f'  Fouls/Spiel       : {fouls_sum/N:.1f}')
        if total_goals > 0:
            w(f'  Tore/xG           : {total_goals/(xg_home_sum+xg_away_sum+0.001):.3f}  (Ziel ~1.0)')

        # Pressing
        w(f'  Pressing-Siege/Sp : Heim {press_wins_h/N:.1f}  Gast {press_wins_a/N:.1f}')
        w(f'  Pressing übersplt : Heim {press_bp_h/N:.1f}  Gast {press_bp_a/N:.1f}')
        att_total = att_left + att_center + att_right or 1
        w(f'  Angriffszone      : Links {_pct(att_left,att_total)}  '
          f'Mitte {_pct(att_center,att_total)}  Rechts {_pct(att_right,att_total)}')

        # Alarme vs. Baseline
        alarms = []
        for lbl, val, base, tol in [
            ('Tore/Spiel',   gpg, BASELINE['goals_per_game'], ALARM['goals']),
            ('Heimsiege%',   hw,  BASELINE['home_win_pct'],   ALARM['result']),
            ('Remis%',       drw, BASELINE['draw_pct'],       ALARM['result']),
            ('Gelb/Spiel',   ypg, BASELINE['yellow_per_game'],ALARM['cards']),
        ]:
            a = _alarm(lbl, val, base, tol)
            if a:
                alarms.append(a)
        if alarms:
            w('\n  Basis-Alarme:')
            for a in alarms:
                w(a)
        else:
            w('\n  Alle Kernwerte innerhalb Toleranz.')

        # Häufigste Ergebnisse
        top_sc = sorted(scores.items(), key=lambda x: -x[1])[:8]
        w(f'\n  Häufigste Ergebnisse:')
        for sc, cnt in top_sc:
            w(f'    {sc:>5}  {cnt:>6}×  {_bar(cnt,0,top_sc[0][1])}  {_pct(cnt,N)}')

        # Tore nach Phase
        gp_t = sum(goals_phase) or 1
        w(f'\n  Tore nach Spielphase:')
        for lbl, cnt in zip(['1–30 min','31–60 min','61–90 min'], goals_phase):
            w(f'    {lbl}  {cnt:>6}  ({_pct(cnt,gp_t)})  {_bar(cnt,0,gp_t//2)}')

        # Ballbesitz
        if poss_list:
            avg_p  = _mean(poss_list)
            std_p  = _std(poss_list)
            w(f'\n  Ballbesitz Heim: Ø {avg_p:.1f}%  σ={std_p:.1f}  '
              f'Min {min(poss_list)}%  Max {max(poss_list)}%')
            w(f'  (Ziel: Ø 49–52%, σ 6,5–8,0, Bereich 25–75%)')
            buckets = [0] * 10
            for p in poss_list:
                idx = max(0, min(9, (p - 25) // 5))
                buckets[idx] += 1
            labels = ['25-30','30-35','35-40','40-45','45-50',
                      '50-55','55-60','60-65','65-70','70-75']
            for lbl, cnt in zip(labels, buckets):
                w(f'    {lbl}%  {_bar(cnt,0,max(buckets))}  {cnt}×')

        # ════════════════════════════════════════════════════════════════════
        # SEKTION C — TABELLE UND STÄRKEVERHALTEN
        # ════════════════════════════════════════════════════════════════════
        w(f'\n{HR}')
        w('  C  TABELLE UND STÄRKEVERHALTEN (100 SAISONS)')
        w(HR)

        # Ø Punkte je Tabellenplatz
        pts_by_pos: list[list[int]] = [[] for _ in range(N_CLUBS)]
        for cid, seasons in club_seasons.items():
            for s in seasons:
                pts_by_pos[s['pos'] - 1].append(s['pts'])

        w(f'  {"Platz":>5}  {"Ø Pkt":>7}  {"Min":>5}  {"Max":>5}  {"σ":>5}')
        for pos_i in range(N_CLUBS):
            lst = pts_by_pos[pos_i]
            if not lst:
                continue
            w(f'  {pos_i+1:>5}  {_mean(lst):>7.1f}  {min(lst):>5}  {max(lst):>5}  {_std(lst):>5.1f}')

        # Meisterhäufigkeit
        w(f'\n  Meisterhäufigkeit über {n_seas} Saisons:')
        for cid, cnt in sorted(championship.items(), key=lambda x: -x[1]):
            name = CLUBS[CID_INDEX[cid]]['name']
            w(f'    {name:>12}  {cnt:>4}×  {_pct(cnt,n_seas)}  {_bar(cnt,0,n_seas//2,30)}')

        # Ø Tabellenplatz je Verein
        w(f'\n  Ø Tabellenplatz je Verein:')
        club_avg_pos = [(CLUBS[CID_INDEX[cid]]['name'],
                         CLUBS[CID_INDEX[cid]]['strength'],
                         _mean([s['pos'] for s in seass]),
                         top4.get(cid, 0), bottom3.get(cid, 0))
                        for cid, seass in club_seasons.items()]
        club_avg_pos.sort(key=lambda x: x[2])
        w(f'  {"Verein":>12}  {"Stärke":>6}  {"Ø Platz":>8}  {"Top4":>5}×  {"Abst.":>5}×')
        for name, strength, avg_pos, t4, b3 in club_avg_pos:
            w(f'  {name:>12}  {strength:>6.0f}  {avg_pos:>8.2f}  {t4:>5}  {b3:>5}')

        # Korrelationen
        str_ranks   = list(range(1, N_CLUBS + 1))
        str_ordered = sorted(CLUBS, key=lambda c: -c['strength'])
        avg_pos_by_str = [_mean([s['pos'] for s in club_seasons[c['id']]])
                          for c in str_ordered]
        avg_pts_by_str = [_mean([s['pts'] for s in club_seasons[c['id']]])
                          for c in str_ordered]
        r_str_pos = _spearman(str_ranks, avg_pos_by_str)
        r_str_pts = _pearson(str_ranks, [-p for p in avg_pts_by_str])  # neg. weil Stärke-Rang
        r_xgd_pts = _pearson(
            [t[0] for t in season_xgd_pts],
            [t[1] for t in season_xgd_pts])
        w(f'\n  Korrelationen:')
        w(f'    Stärke-Rang → Ø Tabellenplatz (Spearman) : {r_str_pos:+.3f}  (Ziel ≥ 0.90)')
        w(f'    Stärke-Rang → Ø Punkte        (Pearson)  : {r_str_pts:+.3f}  (|Ziel| ≥ 0.88)')
        w(f'    xGD → Punkte                  (Pearson)  : {r_xgd_pts:+.3f}  (Ziel 0.58–0.70)')

        # xG-Qualität
        total_xg = xg_home_sum + xg_away_sum
        w(f'\n  xG-Qualität:')
        w(f'    Heim-xG/Spiel : {xg_home_sum/N:.3f}')
        w(f'    Gast-xG/Spiel : {xg_away_sum/N:.3f}')
        w(f'    Tore/xG       : {total_goals/max(1,total_xg):.3f}')

        # ════════════════════════════════════════════════════════════════════
        # SEKTION D — HEIMVORTEIL, STÄRKE-BRACKETS, WECHSEL
        # ════════════════════════════════════════════════════════════════════
        w(f'\n{HR}')
        w('  D  HEIMVORTEIL, STÄRKE-BRACKETS, WECHSEL')
        w(HR)

        # Heimvorteil (gespiegelte Paare)
        h_goals_mirror = sum(v[0] for v in mirrored.values())
        a_goals_mirror = sum(v[1] for v in mirrored.values())
        n_pairs = sum(v[2] for v in mirrored.values())
        w(f'  Heimvorteil (gespiegelte Paarungen):')
        w(f'    Ø Tore Heimmannschaft  : {h_goals_mirror/max(1,n_pairs):.3f}')
        w(f'    Ø Tore Gastmannschaft  : {a_goals_mirror/max(1,n_pairs):.3f}')
        w(f'    Heimtore-Anteil        : {_pct(int(h_goals_mirror), int(h_goals_mirror+a_goals_mirror))}')

        # Stärke-Brackets
        w(f'\n  Stärke-Bracket-Analyse (Favorit vs. Außenseiter):')
        w(f'  {"Differenz":>10}  {"N":>6}  {"Fav%":>6}  {"Remis%":>7}  {"Auß%":>6}  '
          f'{"Ø GD":>6}  {"Ø xGD":>7}')
        for bkt, b in BKT.items():
            bn = b[0] + b[1] + b[2]
            if bn == 0:
                continue
            w(f'  {bkt:>10}  {bn:>6}  {_pct(b[0],bn):>6}  {_pct(b[1],bn):>7}  '
              f'{_pct(b[2],bn):>6}  {b[3]/bn:>+6.2f}  {b[4]/bn:>+7.3f}')

        # Wechsel
        w(f'\n  WECHSEL:')
        w(f'    Ø Wechsel/Spiel    : {total_subs_exec/N:.2f}')
        w(f'    davon Verletzung   : {total_inj_subs}  ({_pct(total_inj_subs, total_subs_exec)})')
        w(f'    Geplant aufgest.   : {total_planned_in}')
        w(f'    Geplant ausgeführt : {total_planned_exec}  ({_pct(total_planned_exec, total_planned_in)})')
        rel_total = hp_count + np_count + fp_count
        w(f'    HP / NP / FP       : {hp_count}/{np_count}/{fp_count}  '
          f'(von {rel_total} klassifiziert)')
        avg_d = strength_delta_sum / strength_delta_n if strength_delta_n else 0.0
        w(f'    Ø Stärkeänderung   : {avg_d:+.2f}  (negativ = schwächerer Einwechsler)')

        if verbose:
            w(f'\n    Bedingungsverteilung:')
            for cond in sorted(cond_counts):
                n_in = cond_counts[cond]; n_ex = cond_exec.get(cond, 0)
                w(f'      {cond:>14}  aufgest.: {n_in:>7}  ausgeführt: {n_ex:>7}  '
                  f'Quote: {_pct(n_ex, n_in)}')

        if sub_minutes:
            w(f'\n    Wechsel-Timing:')
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

        # ════════════════════════════════════════════════════════════════════
        # SEKTION E — VERLETZUNGEN, FRISCHE, TICKER
        # ════════════════════════════════════════════════════════════════════
        w(f'\n{HR}')
        w('  E  VERLETZUNGEN, FRISCHE, TICKER-INTEGRITÄT')
        w(HR)

        # Verletzungen
        inj_total = inj_ingame + inj_postmatch
        w(f'  Verletzungen gesamt            : {inj_total}  ({inj_total/N:.3f}/Spiel, Ziel 0.15–0.22)')
        w(f'    davon in-game Wechsel        : {inj_ingame}  '
          f'(V1 = 0 erwartet — nur post-match)')
        w(f'    davon post-match             : {inj_postmatch}  ({inj_postmatch/N:.3f}/Spiel)')
        if inj_total:
            w(f'    Leicht (≤7 Tage)           : {inj_light}  ({_pct(inj_light,inj_total)})')
            w(f'    Mittel (8–21 T.)           : {inj_mid}  ({_pct(inj_mid,inj_total)})')
            w(f'    Schwer (22–56 T.)          : {inj_heavy}  ({_pct(inj_heavy,inj_total)})')
            w(f'    Extrem (>56 T.)            : {inj_extreme}')
            if inj_days_n:
                w(f'    Ø Ausfalltage              : {inj_days_sum/inj_days_n:.1f}')
        inj_alarm = _alarm('Verletzungen/Spiel', inj_total/N, BASELINE['inj_per_game'], ALARM['inj'])
        if inj_alarm:
            w(inj_alarm)

        # Frische
        if fr_start_list and fr_end_list:
            avg_start = _mean(fr_start_list)
            avg_end   = _mean(fr_end_list)
            std_start = _std(fr_start_list)
            under80 = sum(1 for f in fr_end_list if f < 80)
            under70 = sum(1 for f in fr_end_list if f < 70)
            under60 = sum(1 for f in fr_end_list if f < 60)
            w(f'\n  Frische (Starter, vor Spiel):')
            w(f'    Ø beim Anpfiff : {avg_start:.1f}%  σ={std_start:.1f}')
            w(f'    Ø nach Spiel   : {avg_end:.1f}%')
            w(f'    Unter 80%      : {_pct(under80, len(fr_end_list))}')
            w(f'    Unter 70%      : {_pct(under70, len(fr_end_list))}')
            w(f'    Unter 60%      : {_pct(under60, len(fr_end_list))}')
            w(f'    (Liga-only: Stammelf sollte ~ 88–96% pendeln)')

        # Ticker-Integrität
        w(f'\n  TICKER-INTEGRITÄT:')
        try:
            ticker_result = _check_ticker_integrity()
            if ticker_result['ok']:
                w('    ✓ Alle Basis-Invarianten bestanden (Stabilität, Anti-Repetition, Score-Format)')
            else:
                for err in ticker_result['errors']:
                    w(f'    ✗ {err}')
        except Exception as exc:
            w(f'    ! Ticker-Test fehlgeschlagen: {exc}')

        # ════════════════════════════════════════════════════════════════════
        # SEKTION F — PERFORMANCE
        # ════════════════════════════════════════════════════════════════════
        w(f'\n{HR}')
        w('  F  LAUFZEIT UND PERFORMANCE')
        w(HR)
        w(f'  Gesamtlaufzeit     : {elapsed:.2f} s')
        w(f'  ms/Spiel           : {elapsed/max(1,total_games)*1000:.2f}')
        w(f'  Spiele gesamt      : {total_games}')
        w(f'  Fehler gesamt      : {errors}')
        w(f'{HR}\n')

        # ── CSV/JSON-Export ──────────────────────────────────────────────────
        if out_dir:
            self._export(out_dir, n_seas, total_games, elapsed,
                         club_seasons, championship, top4, bottom3,
                         pts_by_pos, gpg, hw, drw, aw, ypg, rpg, spg,
                         r_xgd_pts, r_str_pos, r_str_pts,
                         integrity_ok,
                         {'double_sub': v_double_sub, 'post_sub_goal': v_post_sub_goal,
                          'post_dis_goal': v_post_dis_goal, 'neg_xg': v_neg_xg,
                          'invalid_poss': v_invalid_poss, 'over5subs': v_over_5_subs},
                         w)

    # ── Export ───────────────────────────────────────────────────────────────

    def _export(self, out_dir, n_seas, total_games, elapsed,
                club_seasons, championship, top4, bottom3,
                pts_by_pos, gpg, hw, drw, aw, ypg, rpg, spg,
                r_xgd_pts, r_str_pos, r_str_pts, integrity_ok, violations, w):
        os.makedirs(out_dir, exist_ok=True)

        # summary.json
        summary = {
            'seasons': n_seas, 'games': total_games, 'elapsed_s': round(elapsed, 2),
            'ms_per_game': round(elapsed / max(1, total_games) * 1000, 2),
            'integrity_ok': integrity_ok, 'violations': violations,
            'goals_per_game': round(gpg, 4),
            'home_win_pct': round(hw, 4), 'draw_pct': round(drw, 4), 'away_win_pct': round(aw, 4),
            'yellow_per_game': round(ypg, 4), 'red_per_game': round(rpg, 5),
            'shots_per_game': round(spg, 2),
            'r_xgd_pts': round(r_xgd_pts, 4),
            'r_str_pos': round(r_str_pos, 4),
            'r_str_pts': round(r_str_pts, 4),
        }
        with open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # club_averages.csv
        with open(os.path.join(out_dir, 'club_averages.csv'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['club', 'strength', 'avg_pts', 'avg_pos', 'avg_gf', 'avg_ga',
                             'championships', 'top4', 'bottom3'])
            for c in CLUBS:
                cid  = c['id']
                seass = club_seasons[cid]
                if not seass:
                    continue
                writer.writerow([
                    c['name'], c['strength'],
                    round(_mean([s['pts'] for s in seass]), 2),
                    round(_mean([s['pos'] for s in seass]), 2),
                    round(_mean([s['gf']  for s in seass]), 2),
                    round(_mean([s['ga']  for s in seass]), 2),
                    championship.get(cid, 0),
                    top4.get(cid, 0),
                    bottom3.get(cid, 0),
                ])

        # league_metrics.csv (Ø Punkte je Position)
        with open(os.path.join(out_dir, 'league_metrics.csv'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['position', 'avg_pts', 'min_pts', 'max_pts', 'std_pts'])
            for pos_i, lst in enumerate(pts_by_pos):
                if lst:
                    writer.writerow([pos_i+1, round(_mean(lst),2), min(lst), max(lst), round(_std(lst),2)])

        # integrity_errors.csv
        with open(os.path.join(out_dir, 'integrity_errors.csv'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['check', 'count'])
            for k, v in violations.items():
                writer.writerow([k, v])

        w(f'  Export: {out_dir}  (summary.json, club_averages.csv, league_metrics.csv, integrity_errors.csv)')

    # ── Schnellmodus (V1-kompatibel) ─────────────────────────────────────────

    def _run_quick_mode(self, N: int, seed0: int, verbose: bool):
        w  = self.stdout.write
        HR = '─' * 62
        rng = random.Random(seed0)
        errors = fallbacks = 0
        total_goals = home_wins = draws = away_wins = 0
        total_yellow = total_red = 0
        fav_wins = fav_draws = fav_losses = 0
        total_subs_exec = total_planned_exec = total_inj_subs = total_planned_in = 0
        hp_count = np_count = fp_count = 0
        strength_delta_sum = 0.0; strength_delta_n = 0
        cond_counts: dict[str, int] = {}; cond_exec: dict[str, int] = {}
        sub_minutes: list[int] = []
        poss_list: list[int] = []
        xg_home_sum = xg_away_sum = 0.0; xg_n = 0
        shots_sum = shots_on_sum = corners_sum = fouls_sum = 0; shots_n = 0
        goals_phase = [0, 0, 0]
        scores: dict[str, int] = {}
        double_sub_violations = post_sub_goal_violations = 0
        t0 = time.time()

        for game_i in range(N):
            game_seed = seed0 * 10000 + game_i
            h_str = 60.0 + rng.random() * 25.0
            a_str = 60.0 + rng.random() * 25.0
            use_h = (game_i % 5 != 0); use_a = (game_i % 5 not in (0, 1))
            h_pid_base = game_seed * 2 * 200
            a_pid_base = (game_seed * 2 + 1) * 200
            h_bench = [h_pid_base + 11 + j for j in range(len(BENCH_POS))]
            a_bench = [a_pid_base + 11 + j for j in range(len(BENCH_POS))]
            h_psubs = _make_subs_v1(game_seed,     h_pid_base, h_bench, 3) if use_h else []
            a_psubs = _make_subs_v1(game_seed + 1, a_pid_base, a_bench, 2) if use_a else []
            for ps in h_psubs + a_psubs:
                c = ps.get('condition', 'immer')
                cond_counts[c] = cond_counts.get(c, 0) + 1
            total_planned_in += len(h_psubs) + len(a_psubs)
            home = _make_team_v1(game_seed * 2,     h_str, h_psubs)
            away = _make_team_v1(game_seed * 2 + 1, a_str, a_psubs)
            try:
                sim = _simulate_match_minutes(home, away)
            except Exception as exc:
                errors += 1
                self.stderr.write(f'  ERROR {game_i}: {exc}')
                continue
            hg, ag = sim['home_goals'], sim['away_goals']
            total_goals += hg + ag
            scores[f'{hg}:{ag}'] = scores.get(f'{hg}:{ag}', 0) + 1
            if hg > ag:    home_wins += 1
            elif hg == ag: draws     += 1
            else:          away_wins += 1
            if h_str > a_str + 3:
                if hg > ag:    fav_wins   += 1
                elif hg == ag: fav_draws  += 1
                else:          fav_losses += 1
            elif a_str > h_str + 3:
                if ag > hg:    fav_wins   += 1
                elif ag == hg: fav_draws  += 1
                else:          fav_losses += 1
            ms_ = sim.get('match_stats', {}) or {}
            total_yellow += ms_.get('home_yellow', 0) + ms_.get('away_yellow', 0)
            total_red    += ms_.get('home_red', 0) + ms_.get('away_red', 0)
            poss_list.append(ms_.get('home_possession', 50) or 50)
            shots_sum    += ms_.get('home_shots', 0) + ms_.get('away_shots', 0)
            shots_on_sum += ms_.get('home_shots_on_target', 0) + ms_.get('away_shots_on_target', 0)
            corners_sum  += ms_.get('home_corners', 0) + ms_.get('away_corners', 0)
            fouls_sum    += ms_.get('home_fouls', 0) + ms_.get('away_fouls', 0)
            shots_n += 1
            hxg = sim.get('home_xg', 0.0) or 0.0; axg = sim.get('away_xg', 0.0) or 0.0
            xg_home_sum += hxg; xg_away_sum += axg; xg_n += 1
            for ge in sim.get('goal_events', []):
                m = ge.get('minute', 45)
                if m <= 30: goals_phase[0] += 1
                elif m <= 60: goals_phase[1] += 1
                else: goals_phase[2] += 1
            h_evts = sim.get('h_sim_sub_events', [])
            a_evts = sim.get('a_sim_sub_events', [])
            for side_evts, side_t in ((h_evts, home), (a_evts, away)):
                pid_str_map = {p['id']: p['final_strength'] for p in side_t['players']}
                pid_str_map.update({pid: p['final_strength']
                                    for pid, p in side_t['bench_player_data'].items()})
                in_pids = []
                for evt in side_evts:
                    total_subs_exec += 1
                    cond = evt.get('condition', 'immer')
                    rel  = evt.get('position_relation', '')
                    if cond == 'verletzung': total_inj_subs += 1
                    else:
                        total_planned_exec += 1
                        cond_exec[cond] = cond_exec.get(cond, 0) + 1
                    if rel == 'HP': hp_count += 1
                    elif rel == 'NP': np_count += 1
                    elif rel == 'FP': fp_count += 1
                    in_p = evt.get('in'); out_p = evt.get('out')
                    if in_p and out_p:
                        strength_delta_sum += pid_str_map.get(in_p, 0) - pid_str_map.get(out_p, 0)
                        strength_delta_n += 1
                    if in_p: in_pids.append(in_p)
                    if evt.get('minute'): sub_minutes.append(evt['minute'])
                if len(in_pids) != len(set(in_pids)): double_sub_violations += 1
            h_out = {e['out']: e['minute'] for e in h_evts if e.get('out')}
            a_out = {e['out']: e['minute'] for e in a_evts if e.get('out')}
            for ge in sim.get('goal_events', []):
                sid = ge.get('scorer_id'); gmin = ge.get('minute', 0)
                side = ge.get('team', '')
                out_m = h_out if side == 'home' else a_out
                if sid and sid in out_m and gmin > out_m[sid]:
                    post_sub_goal_violations += 1

        elapsed = time.time() - t0
        def pct(n, d): return f'{100*n/d:.1f}%' if d else 'n/a'
        def bar(v, lo, hi, w2=20): return '█'*int(round((v-lo)/(hi-lo+1e-9)*w2)) + '·'*(w2-int(round((v-lo)/(hi-lo+1e-9)*w2)))
        seasons = N / 34
        w(f'\n{HR}')
        w(f'  Schnellmodus  ({N} Spiele ≈ {seasons:.0f} Saisons)')
        w(HR)
        w(f'  Laufzeit   : {elapsed:.2f} s  ({elapsed/N*1000:.1f} ms/Spiel)')
        w(f'  Fehler     : {errors}')
        w(f'  Tore/Spiel : {total_goals/N:.3f}  (xG H:{xg_home_sum/xg_n:.2f} A:{xg_away_sum/xg_n:.2f})')
        w(f'  H/R/A      : {home_wins}/{draws}/{away_wins}  ({pct(home_wins,N)}/{pct(draws,N)}/{pct(away_wins,N)})')
        fav_t = fav_wins + fav_draws + fav_losses
        w(f'  Fav-Siege  : {pct(fav_wins,fav_t)}  (N={fav_t})')
        w(f'  Gelb/Spiel : {total_yellow/N:.2f}   Rot/Spiel: {total_red/N:.4f}')
        w(f'  Schüsse/Sp : {shots_sum/N:.1f}')
        if poss_list:
            avg_p = sum(poss_list)/len(poss_list); std_p = _std(poss_list)
            w(f'  Ballbesitz : Ø {avg_p:.1f}%  σ={std_p:.1f}  [{min(poss_list)}–{max(poss_list)}%]')
        ok_ds = '✓' if double_sub_violations == 0 else f'✗ ({double_sub_violations})'
        ok_pg = '✓' if post_sub_goal_violations == 0 else f'✗ ({post_sub_goal_violations})'
        w(f'  Doppel-Sub : {ok_ds}   Post-Sub-Tore: {ok_pg}')
        w(HR)
