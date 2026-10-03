"""Read-only fixed-seed report/RNG parity against a saved pre-change engine.

Usage: python scripts/check_live_ticker_engine_parity.py --before /tmp/engine_before.py
The baseline can be exported with git show <baseline>:game/match_engine.py.
Both sides run in rolled-back transactions, including default-tactic writes.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from django.db import transaction
from game.models import Club, Player
from game import match_engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', required=True)
    parser.add_argument('--home', type=int)
    parser.add_argument('--away', type=int)
    parser.add_argument('--output')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('game._engine_parity_baseline', args.before)
    before = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before)
    if args.home and args.away:
        clubs = [Club.objects.get(pk=pk) for pk in (args.home, args.away)]
    else:
        clubs = []
        for club in Club.objects.order_by('pk'):
            if Player.objects.filter(club=club).count() >= 18:
                clubs.append(club)
            if len(clubs) == 2:
                break
    if len(clubs) != 2:
        raise RuntimeError('Need two clubs with playable squads')

    def run(engine, seed, cup):
        random.seed(seed)
        with transaction.atomic():
            home, away = [Club.objects.get(pk=club.pk) for club in clubs]
            report = engine.simulate_match(home, away, is_cup=cup)
            rng_state = random.getstate()
            transaction.set_rollback(True)
        return report, rng_state

    checks = []
    for seed in range(71000, 71012):
        for cup in (False, True):
            original, old_rng = run(before, seed, cup)
            observed, new_rng = run(match_engine, seed, cup)
            observed = deepcopy(observed)
            segments = observed.pop('segment_log')
            original.pop('segment_log', None)
            # Equality of the whole report includes every player's ratings,
            # events, all totals, ET and shootout. Hash exact serialization too.
            serialize = lambda report: json.dumps(
                report, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
            assert serialize(original) == serialize(observed), (seed, cup, 'report drift')
            assert old_rng == new_rng, (seed, cup, 'RNG drift')
            checks.append({
                'seed': seed, 'cup': cup,
                'goals': [observed['home_goals'], observed['away_goals']],
                'segments': len(segments), 'decided_by': observed.get('decided_by'),
                'report_sha256': hashlib.sha256(serialize(observed)).hexdigest(),
                'report_equal': True, 'rng_equal': True,
            })
    result = json.dumps({'checks': len(checks), 'passed': True, 'results': checks}, indent=2)
    print(result)
    if args.output:
        Path(args.output).write_text(result + '\n')


if __name__ == '__main__':
    main()