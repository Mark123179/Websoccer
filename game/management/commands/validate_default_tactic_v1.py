"""
validate_default_tactic_v1.py — Masse-Verhaltenstest Default-Taktik V1

Szenarien A–E:
  A — Symmetrisch      70 vs 70   (balanced, ≈ 0 %)
  B — Außenseiter      68 vs 72   (≈ −5.7 %)
  C — Klarer AU        65 vs 72   (≈ −10.2 %)
  D — Favorit          72 vs 68   (≈ +5.7 %)
  E — Klarer Favorit   75 vs 68   (≈ +9.8 %)

Beide Vereine trainerlos → Default-Taktik greift auf beiden Seiten.
Jedes Szenario läuft N Mal in jede Richtung (2 N Spiele gesamt).

Verwendung:
  python manage.py validate_default_tactic_v1
  python manage.py validate_default_tactic_v1 --games 500
"""
from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from game.match_engine import simulate_match
from game.match_readiness import ensure_default_tactic
from game.models import Club, League, Player, PlayerStrengthProfile, TacticSetup
from game.tactics import SQUAD_PRO, default_formation, formation_slots

_TAG_PREFIX = '__DTV__'
_LEAGUE_TAG = '__DTaktikVal__'
_POSITIONS = ['TW', 'LV', 'IV', 'IV', 'RV', 'DM', 'ZM', 'ZM', 'OM', 'ST', 'ST']


def _cleanup_stale() -> None:
    """Löscht Überbleibsel vorheriger (abgebrochener) Läufe."""
    Club.objects.filter(name__startswith=_TAG_PREFIX).delete()
    League.objects.filter(name=_LEAGUE_TAG).delete()


def _make_club(league: League, tag: str, strength: int, run_id: str) -> Club:
    club = Club.objects.create(
        name=f'{_TAG_PREFIX}{tag}_s{strength}',
        short_name=(f'D{strength}')[:5],
        founded_year=2000,
        budget=Decimal('5000000'),
        league=league,
    )
    formation = default_formation()
    slots = formation_slots(formation)[:len(_POSITIONS)]
    lineup: dict = {}
    for i, slot in enumerate(slots):
        pos = _POSITIONS[i]
        p = Player.objects.create(
            first_name=f'P{i}',
            last_name=tag[:12],
            wsc_player_id=f'{_TAG_PREFIX}{run_id}-{tag}-{i}',
            date_of_birth=date(1995, 1, 1),
            age=29,
            position=pos,
            main_position_1=pos,
            club=club,
        )
        PlayerStrengthProfile.objects.create(
            player=p,
            base_strength=Decimal(str(strength)),
            form_modifier=Decimal('0.00'),
        )
        lineup[slot['key']] = p.id

    TacticSetup.objects.create(
        club=club,
        squad_scope=SQUAD_PRO,
        formation=formation,
        lineup=lineup,
        bench=[],
    )
    return club


def _run_games(club_a: Club, club_b: Club, n: int) -> list[dict]:
    """Läuft je n Spiele in beiden Richtungen; normalisiert auf Club A."""
    results: list[dict] = []
    for _ in range(n):
        r_ab = simulate_match(club_a, club_b)
        results.append({
            'xgf': r_ab.get('home_xg', 0.0),
            'xga': r_ab.get('away_xg', 0.0),
            'gf':  r_ab.get('home_goals', 0),
            'ga':  r_ab.get('away_goals', 0),
        })
        r_ba = simulate_match(club_b, club_a)
        results.append({
            'xgf': r_ba.get('away_xg', 0.0),
            'xga': r_ba.get('home_xg', 0.0),
            'gf':  r_ba.get('away_goals', 0),
            'ga':  r_ba.get('home_goals', 0),
        })
    return results


def _stats(results: list[dict]) -> dict:
    n = len(results)
    wins   = sum(1 for r in results if r['gf'] > r['ga'])
    draws  = sum(1 for r in results if r['gf'] == r['ga'])
    losses = sum(1 for r in results if r['gf'] < r['ga'])
    ppg    = (wins * 3 + draws) / n
    xgf    = sum(r['xgf'] for r in results) / n
    xga    = sum(r['xga'] for r in results) / n
    gf     = sum(r['gf']  for r in results) / n
    ga     = sum(r['ga']  for r in results) / n
    return {
        'n': n,
        'ppg':  ppg,
        'xgd':  xgf - xga,
        'gd':   gf - ga,
        'xgf':  xgf,
        'xga':  xga,
        'gf':   gf,
        'ga':   ga,
        'gpg':  gf + ga,
        'w_pct': wins   / n * 100,
        'd_pct': draws  / n * 100,
        'l_pct': losses / n * 100,
    }


class Command(BaseCommand):
    help = 'Masse-Verhaltenstest Default-Taktik V1 — Szenarien A–E.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--games', type=int, default=500,
            help='Spiele je Richtung pro Szenario (Gesamt = games × 2). Standard: 500.',
        )
        parser.add_argument(
            '--keep', action='store_true',
            help='Test-Clubs nach dem Lauf NICHT löschen (für Debugging).',
        )

    def handle(self, *args, **options):
        n      = options['games']
        keep   = options['keep']

        _cleanup_stale()
        run_id = str(int(time.time()))
        league = League.objects.create(name=_LEAGUE_TAG, country='Deutschland')
        all_stats: dict[str, dict] = {}

        W = self.style.WARNING
        S = self.style.SUCCESS
        E = self.style.ERROR

        self.stdout.write('')
        self.stdout.write('=' * 70)
        self.stdout.write(
            f' Default-Taktik V1 — Verhaltensvalidierung'
            f'  ({n} × 2 Spiele/Szenario)'
        )
        self.stdout.write('=' * 70)

        scenarios = [
            ('A', 'Symmetrisch',      70, 70),
            ('B', 'Außenseiter',       68, 72),
            ('C', 'Klarer Außenseiter', 65, 72),
            ('D', 'Favorit',           72, 68),
            ('E', 'Klarer Favorit',    75, 68),
        ]

        try:
            for code, label, s_a, s_b in scenarios:
                rel_diff = (s_a - s_b) / ((s_a + s_b) / 2.0) * 100
                self.stdout.write(
                    f'\n── Szenario {code}: {label}'
                    f'  ({s_a} vs {s_b}, {rel_diff:+.1f} %)'
                )

                club_a = _make_club(league, f'{code}_A', s_a, run_id)
                club_b = _make_club(league, f'{code}_B', s_b, run_id)

                results = _run_games(club_a, club_b, n)
                st = _stats(results)
                all_stats[code] = st

                self.stdout.write(
                    f'   PPG={st["ppg"]:.3f}  '
                    f'xGD={st["xgd"]:+.3f}  '
                    f'GD={st["gd"]:+.3f}  '
                    f'Goals/Sp={st["gpg"]:.2f}'
                )
                self.stdout.write(
                    f'   W={st["w_pct"]:.1f}%  '
                    f'D={st["d_pct"]:.1f}%  '
                    f'L={st["l_pct"]:.1f}%  '
                    f'xGF={st["xgf"]:.3f}  '
                    f'xGA={st["xga"]:.3f}'
                )

        finally:
            if not keep:
                Club.objects.filter(name__startswith=_TAG_PREFIX).delete()
                League.objects.filter(name=_LEAGUE_TAG).delete()

        self.stdout.write('')
        self.stdout.write('─' * 70)
        self.stdout.write(' ALARM-PRÜFUNGEN')
        self.stdout.write('─' * 70)

        def _chk(label: str, ok: bool, detail: str) -> None:
            mark = S('✓') if ok else E('⚠ ALARM')
            self.stdout.write(f'  {mark}  {label}:  {detail}')

        a = all_stats['A']
        b = all_stats['B']
        c = all_stats['C']
        d = all_stats['D']
        e = all_stats['E']

        # PPG > 1.0 ist bei kleinem N durch Heimvorteil-Effekt normal.
        # E[PPG] = 1 + p_win > 1.0. Relevantes Symmetriemaß ist xGD.
        # Alarm erst bei starker Schieflage (> 0.35 von 1.0).
        _chk(
            'A  PPG kein extremer Heimvorteil-Bias (< 0.35 von 1.0)',
            abs(a['ppg'] - 1.0) < 0.35,
            f"PPG={a['ppg']:.3f}  (xGD={a['xgd']:+.4f} ist der Hauptindikator)",
        )
        _chk(
            'A  xGD symmetrisch ≈ 0',
            abs(a['xgd']) < 0.05,
            f"xGD={a['xgd']:+.4f}",
        )
        _chk(
            'B  Außenseiter xGD negativ',
            b['xgd'] < 0.0,
            f"xGD={b['xgd']:+.3f}",
        )
        _chk(
            'C  Klarer AU schlechter als B (xGD)',
            c['xgd'] < b['xgd'],
            f"C={c['xgd']:+.3f}  B={b['xgd']:+.3f}",
        )
        _chk(
            'C  Klarer AU schlechter als B (PPG)',
            c['ppg'] < b['ppg'],
            f"C={c['ppg']:.3f}  B={b['ppg']:.3f}",
        )
        _chk(
            'D  Favorit xGD positiv',
            d['xgd'] > 0.0,
            f"xGD={d['xgd']:+.3f}",
        )
        _chk(
            'E  Klarer Favorit besser als D (xGD)',
            e['xgd'] > d['xgd'],
            f"E={e['xgd']:+.3f}  D={d['xgd']:+.3f}",
        )
        _chk(
            'B + D xGD-Symmetrie (|Summe| < 0.05)',
            abs(b['xgd'] + d['xgd']) < 0.05,
            f"|{b['xgd']:+.3f} + {d['xgd']:+.3f}| = {abs(b['xgd']+d['xgd']):.4f}",
        )

        outside_corridor = [
            code for code, st in all_stats.items()
            if not (2.3 < st['gpg'] < 3.2)
        ]
        if outside_corridor:
            for code in outside_corridor:
                _chk(
                    f'{code}  Goals/Sp im Produktionskorridor (2.3–3.2)',
                    False,
                    f"{all_stats[code]['gpg']:.2f}",
                )
        else:
            _chk(
                'Alle Goals/Sp im Produktionskorridor (2.3–3.2)',
                True,
                '  '.join(f"{c}={all_stats[c]['gpg']:.2f}" for c in 'ABCDE'),
            )

        self.stdout.write('')
