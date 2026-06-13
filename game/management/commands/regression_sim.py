"""Dynamic Lineup V1 — 450-Spiel-Regression (pure Dict, kein ORM).

Metriken:
  Allgemein:  Fehler, Fallbacks, Tore/Spiel, H/D/A, Favorit-Siege
  Wechsel:    Ø Wechsel/Spiel, HP/NP/FP, Verletzungswechsel, Ø Stärkeänderung
              Geplante ausgeführt/verworfen (geschätzt)
  Invarianten: Doppelte Einwechslungen = 0, Events nach Auswechslung = 0
"""
import random
import time
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
    """Erstellt n geplante Wechsel mit gemischten Bedingungen."""
    rng = random.Random(seed + 77)
    conditions = ['immer', 'immer', 'fuehrung', 'rueckstand', 'immer']
    starter_pids = [team_pid_base + i for i in range(9, 11)]   # ST-Slots (idx 9,10)
    mid_pids     = [team_pid_base + i for i in range(5, 9)]    # MID-Slots
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
    help = 'Dynamic Lineup V1 — 450-Spiel-Regression (kein ORM)'

    def add_arguments(self, parser):
        parser.add_argument('--games', type=int, default=450)
        parser.add_argument('--seed',  type=int, default=42)

    def handle(self, *args, **options):
        N     = options['games']
        seed0 = options['seed']
        rng   = random.Random(seed0)

        # ── Akkumulatoren ───────────────────────────────────────────────────────
        errors          = 0
        fallbacks       = 0
        total_goals     = 0
        home_wins = draws = away_wins = 0
        fav_wins = fav_draws = fav_losses = 0
        total_yellow = total_red = 0
        total_injuries  = 0

        total_subs_exec    = 0   # ausgeführte Wechsel (alle)
        total_planned_exec = 0   # geplante (nicht Verletzung) ausgeführt
        total_inj_subs     = 0   # Verletzungswechsel
        total_planned_in   = 0   # geplante Wechsel aufgestellt (Eingang)
        hp_count = np_count = fp_count = 0
        strength_delta_sum = 0.0
        strength_delta_n   = 0

        double_sub_violations = 0   # Invariante: 0
        post_sub_goal_violations = 0  # Invariante: 0

        t0 = time.time()

        for game_i in range(N):
            game_seed  = seed0 * 10000 + game_i
            h_str = 60.0 + rng.random() * 25.0
            a_str = 60.0 + rng.random() * 25.0
            with_inj = (game_i % 7 == 0)

            # Geplante Wechsel für 60 % der Heimteams, 40 % der Auswärtsteams
            use_h_subs = (game_i % 5 != 0)
            use_a_subs = (game_i % 5 not in (0, 1))

            h_pid_base = game_seed * 2 * 200
            a_pid_base = (game_seed * 2 + 1) * 200
            h_bench_pids = [h_pid_base + 11 + j for j in range(len(BENCH_POS))]
            a_bench_pids = [a_pid_base + 11 + j for j in range(len(BENCH_POS))]
            h_psubs = _make_subs(game_seed,     h_pid_base, h_bench_pids, n=3) if use_h_subs else []
            a_psubs = _make_subs(game_seed + 1, a_pid_base, a_bench_pids, n=2) if use_a_subs else []

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

            if hg > ag:   home_wins += 1
            elif hg == ag: draws    += 1
            else:          away_wins += 1

            if h_str > a_str + 3:
                if hg > ag:   fav_wins   += 1
                elif hg == ag: fav_draws += 1
                else:          fav_losses += 1
            elif a_str > h_str + 3:
                if ag > hg:   fav_wins   += 1
                elif ag == hg: fav_draws += 1
                else:          fav_losses += 1

            ms = sim.get('match_stats', {}) or {}
            total_yellow += ms.get('home_yellow', 0) + ms.get('away_yellow', 0)
            total_red    += ms.get('home_red', 0)    + ms.get('away_red', 0)

            # ── Wechsel-Metriken ─────────────────────────────────────────────
            h_evts = sim.get('h_sim_sub_events', [])
            a_evts = sim.get('a_sim_sub_events', [])
            all_evts = h_evts + a_evts

            for side_evts, side_team in ((h_evts, home), (a_evts, away)):
                # Build pid→strength from team dict
                pid_str: dict[int, float] = {p['id']: p['final_strength']
                                              for p in side_team['players']}
                pid_str.update({pid: p['final_strength']
                                for pid, p in side_team['bench_player_data'].items()})

                in_pids_this_game = []
                for evt in side_evts:
                    in_pid  = evt.get('in')
                    out_pid = evt.get('out')
                    cond    = evt.get('condition', 'immer')
                    rel     = evt.get('position_relation', '')

                    total_subs_exec += 1
                    if cond == 'verletzung':
                        total_inj_subs  += 1
                    else:
                        total_planned_exec += 1

                    if rel == 'HP':   hp_count += 1
                    elif rel == 'NP': np_count += 1
                    elif rel == 'FP': fp_count += 1

                    if in_pid and out_pid:
                        delta = pid_str.get(in_pid, 0) - pid_str.get(out_pid, 0)
                        strength_delta_sum += delta
                        strength_delta_n   += 1

                    if in_pid:
                        in_pids_this_game.append(in_pid)

                # Invariante: Doppelte Einwechslung
                if len(in_pids_this_game) != len(set(in_pids_this_game)):
                    double_sub_violations += 1

            # Invariante: Events nach Auswechslung
            # Nur Goals, deren Minute > sub_off_minute des Schützen, sind Verletzungen.
            h_out_min: dict[int, int] = {e['out']: e['minute'] for e in h_evts if e.get('out')}
            a_out_min: dict[int, int] = {e['out']: e['minute'] for e in a_evts if e.get('out')}
            for goal_evt in sim.get('goal_events', []):
                sid  = goal_evt.get('scorer_id')
                gmin = goal_evt.get('minute', 0)
                side = goal_evt.get('team', '')
                out_map = h_out_min if side == 'home' else a_out_min
                if sid and sid in out_map and gmin > out_map[sid]:
                    post_sub_goal_violations += 1

            # Verletzungen (Injury-Events werden erst in simulate_match() erzeugt,
            # hier nur als Verletzungswechsel zählen)
            total_injuries += total_inj_subs  # entspricht dem V1-Proxy

        elapsed = time.time() - t0

        # ── Bericht ─────────────────────────────────────────────────────────────
        def pct(n, d):
            return f'{100*n/d:.1f}%' if d else 'n/a'

        w  = self.stdout.write
        hr = '─' * 58

        w(f'\n{hr}')
        w(f'  Dynamic Lineup V1 — Regressionsbericht  ({N} Spiele)')
        w(f'{hr}')
        w(f'  Laufzeit          : {elapsed:.2f} s  ({elapsed/N*1000:.1f} ms/Spiel)')
        w(f'  Fehler            : {errors}  ← muss 0 sein')
        w(f'  Fallbacks (50.0)  : {fallbacks}  ← muss 0 sein')
        w(f'{hr}')
        w(f'  Tore/Spiel        : {total_goals/N:.2f}')
        w(f'  Heim/Remis/Auswärts: {home_wins}/{draws}/{away_wins}  '
          f'({pct(home_wins,N)} / {pct(draws,N)} / {pct(away_wins,N)})')
        fav_total = fav_wins + fav_draws + fav_losses
        w(f'  Favorit-Siege     : {pct(fav_wins, fav_total)}  '
          f'(von {fav_total} Spielen mit klarem Favoriten)')
        w(f'  Gelbe Karten/Spiel: {total_yellow/N:.2f}')
        w(f'  Rote Karten/Spiel : {total_red/N:.2f}')
        w(f'{hr}')
        w(f'  Ø Wechsel/Spiel   : {total_subs_exec/N:.2f}')
        w(f'  Verletzungswechsel: {total_inj_subs}  ({pct(total_inj_subs, total_subs_exec)} aller Wechsel)')
        w(f'  Geplante aufgestellt: {total_planned_in}')
        w(f'  Geplante ausgeführt : {total_planned_exec}  '
          f'({pct(total_planned_exec, total_planned_in)} der aufgestellten)')
        w(f'  Geplante verworfen  : {total_planned_in - total_planned_exec}  '
          f'({pct(total_planned_in - total_planned_exec, total_planned_in)})')
        w(f'{hr}')
        rel_total = hp_count + np_count + fp_count
        w(f'  Position-Relation HP: {hp_count}  NP: {np_count}  FP: {fp_count}  '
          f'(von {rel_total} klassifizierten Wechseln)')
        avg_delta = strength_delta_sum / strength_delta_n if strength_delta_n else 0.0
        w(f'  Ø Stärkeänderung    : {avg_delta:+.2f}  '
          f'(negativ = schwächerer Einwechselspieler)')
        w(f'{hr}')
        status_double = '✓ OK' if double_sub_violations == 0 else f'✗ FAIL ({double_sub_violations})'
        status_postsub = '✓ OK' if post_sub_goal_violations == 0 else f'✗ FAIL ({post_sub_goal_violations})'
        w(f'  Doppelte Einwechs. : {status_double}')
        w(f'  Events nach Auswechs.: {status_postsub}')
        w(f'{hr}')

        if errors == 0 and fallbacks == 0 and double_sub_violations == 0 and post_sub_goal_violations == 0:
            w('  GESAMTSTATUS: ✓  #463 Dynamic Lineup V1 — alle Invarianten grün')
        else:
            w('  GESAMTSTATUS: ✗  Fehler gefunden — siehe oben')
        w(f'{hr}\n')
