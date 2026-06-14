"""Dynamic Lineup V1 — Regressionsbericht (pure Dict, kein ORM).

--games N  Anzahl Spiele (Default 3400 ≈ 100 Saisons à 34 Spiele)
--seed  S  RNG-Seed
--verbose  Aktiviert Extra-Sektionen (Ballbesitz, Phasen, Bedingungen)
"""
import random
import time
import math
from django.core.management.base import BaseCommand
from game.match_engine import _simulate_match_minutes, MAX_SUBSTITUTIONS


FALLBACK_STRENGTH = 50.0

SLOTS = [
    ('TW', 'goalkeeper'),
    ('LV', 'defense'), ('IV', 'defense'), ('IV', 'defense'), ('RV', 'defense'),
    ('LM', 'midfield'), ('ZM', 'midfield'), ('ZM', 'midfield'), ('RM', 'midfield'),
    ('ST', 'attack'), ('ST', 'attack'),
]
BENCH_POS = ['ST', 'ZM', 'LV', 'ZM', 'ST', 'IV', 'LM']


def _make_team(seed: int, strength: float, planned_subs: list | None = None,
               with_injured: bool = False) -> dict:
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
            'is_ws_injured': (with_injured and i == 10),
        })
        lineup.append({'player_id': pid, 'position': pos, 'group': grp})

    bench: dict = {}
    bench_pids = []
    for j, pos in enumerate(BENCH_POS):
        pid = pid_base + 11 + j
        bench[pid] = {
            'id': pid, 'name': f'B{pid}',
            'final_strength': max(30.0, strength - 6 + rng.gauss(0, 4)),
            'main_positions': [pos], 'secondary_positions': [],
            'teamwork': 4, 'freshness': 75 + rng.randint(0, 15),
            'is_ws_injured': False,
        }
        bench_pids.append(pid)

    return {
        'team': {'name': f'Team-{seed}', 'id': seed},
        'players': players,
        'lineup': lineup,
        'tactic': {},
        'bench_player_data': bench,
        'planned_substitutions': planned_subs or [],
    }


def _make_subs(seed: int, team_pid_base: int, bench_pids: list[int],
               n: int = 3) -> list[dict]:
    rng = random.Random(seed + 77)
    conditions = ['immer', 'immer', 'fuehrung', 'rueckstand', 'immer']
    starter_pids = [team_pid_base + i for i in range(9, 11)]
    mid_pids     = [team_pid_base + i for i in range(5, 9)]
    targets      = starter_pids + mid_pids
    rng.shuffle(targets)
    result = []
    used_out = set()
    for k in range(min(n, len(bench_pids), len(targets))):
        out_pid = targets[k]
        if out_pid in used_out:
            continue
        used_out.add(out_pid)
        result.append({
            'in':        bench_pids[k],
            'out':       out_pid,
            'minute':    55 + k * 10,
            'condition': conditions[k % len(conditions)],
        })
    return result


class Command(BaseCommand):
    help = 'Regressionsbericht — 100 Saisons (kein ORM)'

    def add_arguments(self, parser):
        parser.add_argument('--games',   type=int, default=3400)
        parser.add_argument('--seed',    type=int, default=42)
        parser.add_argument('--verbose', action='store_true', default=True)

    def handle(self, *args, **options):
        N     = options['games']
        seed0 = options['seed']
        verbose = options['verbose']
        rng   = random.Random(seed0)

        # ── Akkumulatoren ───────────────────────────────────────────────────────
        errors = fallbacks = 0
        total_goals = home_wins = draws = away_wins = 0
        fav_wins = fav_draws = fav_losses = 0
        total_yellow = total_red = 0

        total_subs_exec = total_planned_exec = total_inj_subs = total_planned_in = 0
        hp_count = np_count = fp_count = 0
        strength_delta_sum = 0.0
        strength_delta_n   = 0

        # Bedingungsverteilung
        cond_counts: dict[str, int] = {}
        cond_exec:   dict[str, int] = {}

        # Wechsel-Timing
        sub_minutes: list[int] = []

        # Ballbesitz
        poss_list: list[int] = []   # Heimballbesitz pro Spiel

        # Tore nach Phase (0-30, 31-60, 61-90)
        goals_phase = [0, 0, 0]

        # xG
        xg_home_sum = xg_away_sum = 0.0
        xg_n = 0

        # Schüsse / Ecken / Fouls
        shots_sum = shots_on_sum = corners_sum = fouls_sum = 0
        shots_n = 0

        # Torverteilung
        scores: dict[str, int] = {}

        double_sub_violations = post_sub_goal_violations = 0

        t0 = time.time()

        for game_i in range(N):
            game_seed  = seed0 * 10000 + game_i
            h_str = 60.0 + rng.random() * 25.0
            a_str = 60.0 + rng.random() * 25.0
            with_inj = (game_i % 7 == 0)
            use_h_subs = (game_i % 5 != 0)
            use_a_subs = (game_i % 5 not in (0, 1))

            h_pid_base = game_seed * 2 * 200
            a_pid_base = (game_seed * 2 + 1) * 200
            h_bench_pids = [h_pid_base + 11 + j for j in range(len(BENCH_POS))]
            a_bench_pids = [a_pid_base + 11 + j for j in range(len(BENCH_POS))]
            h_psubs = _make_subs(game_seed,     h_pid_base, h_bench_pids, n=3) if use_h_subs else []
            a_psubs = _make_subs(game_seed + 1, a_pid_base, a_bench_pids, n=2) if use_a_subs else []

            # Geplante Wechsel erfassen (Bedingungen)
            for ps in h_psubs + a_psubs:
                c = ps.get('condition', 'immer')
                cond_counts[c] = cond_counts.get(c, 0) + 1
            total_planned_in += len(h_psubs) + len(a_psubs)

            home = _make_team(game_seed * 2,     h_str, h_psubs, with_injured=with_inj)
            away = _make_team(game_seed * 2 + 1, a_str, a_psubs)

            try:
                sim = _simulate_match_minutes(home, away)
            except Exception as exc:
                errors += 1
                self.stderr.write(f'  ERROR game {game_i}: {exc}')
                continue

            hg, ag = sim['home_goals'], sim['away_goals']
            total_goals += hg + ag

            key = f'{hg}:{ag}'
            scores[key] = scores.get(key, 0) + 1

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

            ms = sim.get('match_stats', {}) or {}
            total_yellow += ms.get('home_yellow', 0) + ms.get('away_yellow', 0)
            total_red    += ms.get('home_red', 0)    + ms.get('away_red', 0)

            if verbose:
                hp = ms.get('home_possession', 50) or 50
                poss_list.append(hp)
                shots_sum     += ms.get('home_shots', 0) + ms.get('away_shots', 0)
                shots_on_sum  += ms.get('home_shots_on_target', 0) + ms.get('away_shots_on_target', 0)
                corners_sum   += ms.get('home_corners', 0) + ms.get('away_corners', 0)
                fouls_sum     += ms.get('home_fouls', 0) + ms.get('away_fouls', 0)
                shots_n       += 1

            # xG
            hxg = sim.get('home_xg', 0.0) or 0.0
            axg = sim.get('away_xg', 0.0) or 0.0
            xg_home_sum += hxg; xg_away_sum += axg; xg_n += 1

            # Tore nach Phase
            for ge in sim.get('goal_events', []):
                m = ge.get('minute', 45)
                if m <= 30:   goals_phase[0] += 1
                elif m <= 60: goals_phase[1] += 1
                else:         goals_phase[2] += 1

            # Wechsel-Metriken
            h_evts = sim.get('h_sim_sub_events', [])
            a_evts = sim.get('a_sim_sub_events', [])

            for side_evts, side_team in ((h_evts, home), (a_evts, away)):
                pid_str = {p['id']: p['final_strength'] for p in side_team['players']}
                pid_str.update({pid: p['final_strength']
                                for pid, p in side_team['bench_player_data'].items()})

                in_pids_game = []
                for evt in side_evts:
                    in_pid  = evt.get('in')
                    out_pid = evt.get('out')
                    cond    = evt.get('condition', 'immer')
                    rel     = evt.get('position_relation', '')
                    minute  = evt.get('minute', 0)

                    total_subs_exec += 1
                    if cond == 'verletzung':
                        total_inj_subs += 1
                    else:
                        total_planned_exec += 1
                        cond_exec[cond] = cond_exec.get(cond, 0) + 1

                    if rel == 'HP':   hp_count += 1
                    elif rel == 'NP': np_count += 1
                    elif rel == 'FP': fp_count += 1

                    if in_pid and out_pid:
                        delta = pid_str.get(in_pid, 0) - pid_str.get(out_pid, 0)
                        strength_delta_sum += delta
                        strength_delta_n   += 1

                    if in_pid:
                        in_pids_game.append(in_pid)
                    if minute:
                        sub_minutes.append(minute)

                if len(in_pids_game) != len(set(in_pids_game)):
                    double_sub_violations += 1

            h_out_min = {e['out']: e['minute'] for e in h_evts if e.get('out')}
            a_out_min = {e['out']: e['minute'] for e in a_evts if e.get('out')}
            for goal_evt in sim.get('goal_events', []):
                sid  = goal_evt.get('scorer_id')
                gmin = goal_evt.get('minute', 0)
                side = goal_evt.get('team', '')
                out_map = h_out_min if side == 'home' else a_out_min
                if sid and sid in out_map and gmin > out_map[sid]:
                    post_sub_goal_violations += 1

        elapsed = time.time() - t0

        # ── Ausgabe ──────────────────────────────────────────────────────────────
        def pct(n, d):
            return f'{100*n/d:.1f}%' if d else 'n/a'

        def bar(val, lo, hi, width=20, symbol='█'):
            if hi <= lo:
                return ''
            filled = int(round((val - lo) / (hi - lo) * width))
            filled = max(0, min(width, filled))
            return symbol * filled + '·' * (width - filled)

        w  = self.stdout.write
        HR = '─' * 62

        seasons = N / 34
        w(f'\n{HR}')
        w(f'  Regressionsbericht  ({N} Spiele ≈ {seasons:.0f} Saisons)')
        w(f'{HR}')
        w(f'  Laufzeit    : {elapsed:.2f} s  ({elapsed/N*1000:.1f} ms/Spiel)')
        w(f'  Fehler      : {errors}  ← muss 0 sein')
        w(f'  Fallbacks   : {fallbacks}  ← muss 0 sein')

        # ── Ergebnisse ───────────────────────────────────────────────────────────
        w(f'\n{HR}')
        w(f'  SPIELERGEBNISSE')
        w(f'{HR}')
        w(f'  Tore/Spiel        : {total_goals/N:.2f}  '
          f'(Heim {xg_home_sum/xg_n:.2f} xG  /  Auswärts {xg_away_sum/xg_n:.2f} xG)')
        w(f'  Heim / Remis / Aus: {home_wins}/{draws}/{away_wins}  '
          f'({pct(home_wins,N)} / {pct(draws,N)} / {pct(away_wins,N)})')
        fav_total = fav_wins + fav_draws + fav_losses
        w(f'  Favorit-Siege     : {pct(fav_wins, fav_total)}  '
          f'(von {fav_total} Spielen mit ≥3 Stärkedifferenz)')

        # Top-10 häufigste Ergebnisse
        top_scores = sorted(scores.items(), key=lambda x: -x[1])[:10]
        w(f'\n  Häufigste Ergebnisse:')
        for sc, cnt in top_scores:
            w(f'    {sc:>5}  {cnt:>5}×  {bar(cnt, 0, top_scores[0][1])}  {pct(cnt, N)}')

        # Tore nach Phase
        gp_total = sum(goals_phase) or 1
        w(f'\n  Tore nach Spielphase:')
        w(f'    1–30 min : {goals_phase[0]:>5}  ({pct(goals_phase[0], gp_total)})  {bar(goals_phase[0], 0, gp_total/2)}')
        w(f'   31–60 min : {goals_phase[1]:>5}  ({pct(goals_phase[1], gp_total)})  {bar(goals_phase[1], 0, gp_total/2)}')
        w(f'   61–90 min : {goals_phase[2]:>5}  ({pct(goals_phase[2], gp_total)})  {bar(goals_phase[2], 0, gp_total/2)}')

        # ── Karten ───────────────────────────────────────────────────────────────
        w(f'\n{HR}')
        w(f'  KARTEN')
        w(f'{HR}')
        w(f'  Gelb/Spiel : {total_yellow/N:.2f}')
        w(f'  Rot/Spiel  : {total_red/N:.3f}')

        # ── Ballbesitz ───────────────────────────────────────────────────────────
        if verbose and poss_list:
            avg_p = sum(poss_list) / len(poss_list)
            std_p = math.sqrt(sum((x - avg_p) ** 2 for x in poss_list) / len(poss_list))
            min_p = min(poss_list)
            max_p = max(poss_list)
            buckets = [0] * 8
            for p in poss_list:
                idx = min(7, (p - 30) // 5)
                if 0 <= idx < 8:
                    buckets[idx] += 1
            w(f'\n{HR}')
            w(f'  BALLBESITZ (Heimteam)')
            w(f'{HR}')
            w(f'  Ø {avg_p:.1f}%   σ={std_p:.1f}   Min {min_p}%   Max {max_p}%')
            labels = ['30-35','35-40','40-45','45-50','50-55','55-60','60-65','65-70']
            w(f'  Verteilung (Heimballbesitz):')
            for lbl, cnt in zip(labels, buckets):
                w(f'    {lbl}%  {bar(cnt, 0, max(buckets))}  {cnt}×  {pct(cnt, N)}')

        # ── Statistiken ──────────────────────────────────────────────────────────
        if verbose and shots_n:
            w(f'\n{HR}')
            w(f'  SPIELSTATISTIKEN (pro Spiel, beide Teams)')
            w(f'{HR}')
            w(f'  Schüsse gesamt    : {shots_sum/shots_n:.1f}')
            w(f'  Schüsse aufs Tor  : {shots_on_sum/shots_n:.1f}  '
              f'({pct(shots_on_sum, shots_sum)} Trefferquote)')
            w(f'  Ecken             : {corners_sum/shots_n:.1f}')
            w(f'  Fouls             : {fouls_sum/shots_n:.1f}')

        # ── Wechsel ──────────────────────────────────────────────────────────────
        w(f'\n{HR}')
        w(f'  WECHSEL')
        w(f'{HR}')
        w(f'  Ø Wechsel/Spiel   : {total_subs_exec/N:.2f}')
        w(f'  Verletzungswechsel: {total_inj_subs}  ({pct(total_inj_subs, total_subs_exec)})')
        w(f'  Geplante aufgest. : {total_planned_in}')
        w(f'  Geplante ausgeführt: {total_planned_exec}  '
          f'({pct(total_planned_exec, total_planned_in)})')
        w(f'  Geplante verworfen : {total_planned_in - total_planned_exec}  '
          f'({pct(total_planned_in - total_planned_exec, total_planned_in)})')
        rel_total = hp_count + np_count + fp_count
        w(f'  Position HP/NP/FP : {hp_count}/{np_count}/{fp_count}  '
          f'(von {rel_total} klassifiziert)')
        avg_delta = strength_delta_sum / strength_delta_n if strength_delta_n else 0.0
        w(f'  Ø Stärkeänderung  : {avg_delta:+.2f}  (negativ = schwächerer Einwechselspieler)')

        # Bedingungsauswertung
        if verbose and cond_counts:
            w(f'\n  Bedingungsverteilung (aufgestellt → ausgeführt → Quote):')
            for cond in sorted(cond_counts):
                n_in  = cond_counts[cond]
                n_ex  = cond_exec.get(cond, 0)
                w(f'    {cond:>12}  aufgest.: {n_in:>6}  ausgeführt: {n_ex:>6}  '
                  f'Quote: {pct(n_ex, n_in)}')

        # Wechsel-Timing-Verteilung
        if verbose and sub_minutes:
            w(f'\n  Wechsel-Timing (Minutenverteilung):')
            t_buckets = {'45-55': 0, '56-65': 0, '66-75': 0, '76-85': 0, '86-90': 0}
            for m in sub_minutes:
                if m <= 55:   t_buckets['45-55'] += 1
                elif m <= 65: t_buckets['56-65'] += 1
                elif m <= 75: t_buckets['66-75'] += 1
                elif m <= 85: t_buckets['76-85'] += 1
                else:         t_buckets['86-90'] += 1
            mx = max(t_buckets.values()) or 1
            for lbl, cnt in t_buckets.items():
                w(f'    {lbl} min  {bar(cnt, 0, mx)}  {cnt}×  {pct(cnt, len(sub_minutes))}')

        # ── Invarianten ──────────────────────────────────────────────────────────
        w(f'\n{HR}')
        w(f'  INVARIANTEN')
        w(f'{HR}')
        ok_double  = '✓ OK' if double_sub_violations    == 0 else f'✗ FAIL ({double_sub_violations})'
        ok_postsub = '✓ OK' if post_sub_goal_violations == 0 else f'✗ FAIL ({post_sub_goal_violations})'
        w(f'  Doppelte Einwechslungen : {ok_double}')
        w(f'  Goals nach Auswechslung : {ok_postsub}')
        w(f'{HR}')

        if errors == 0 and fallbacks == 0 and double_sub_violations == 0 and post_sub_goal_violations == 0:
            w('  GESAMTSTATUS: ✓  alle Invarianten grün')
        else:
            w('  GESAMTSTATUS: ✗  Fehler gefunden — siehe oben')
        w(f'{HR}\n')
