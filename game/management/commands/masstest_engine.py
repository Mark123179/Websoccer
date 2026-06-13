import time
from django.core.management.base import BaseCommand
from game.models import Club, Player
from game.match_engine import simulate_match

FALLBACK_STRENGTH = 50.0


class Command(BaseCommand):
    help = 'Liga-Massentest: 8 Paarungen × N Läufe mit Match Engine V2'

    def add_arguments(self, parser):
        parser.add_argument('--runs', type=int, default=50)

    def handle(self, *args, **options):
        RUNS = options['runs']

        eligible = [c for c in Club.objects.all().order_by('name')
                    if Player.objects.filter(club=c).count() >= 11]
        PAIRS = [(eligible[i], eligible[i+1]) for i in range(0, len(eligible)-1, 2)]

        self.stdout.write(f"{len(PAIRS)} Paarungen × {RUNS} Läufe = {len(PAIRS)*RUNS} Spiele\n")

        r = {i: dict(
            home=PAIRS[i][0].name, away=PAIRS[i][1].name,
            hs=0, as_=0, wh=0, d=0, wa=0,
            gh=0, ga=0, xgh=0.0, xga=0.0,
            sh=0, sa=0, fh=0, fa=0, yh=0, ya=0, rh=0, ra=0,
            ph=0, pa=0,
            alh=0, amh=0, arh=0, ala=0, ama=0, ara=0,
            plans=0, err=0,
            injuries=0, fallbacks=0,
        ) for i in range(len(PAIRS))}

        t0 = time.time()
        total = 0

        for run in range(RUNS):
            for idx, (h, a) in enumerate(PAIRS):
                try:
                    res = simulate_match(h, a)
                    ms  = res['match_stats']
                    s   = r[idx]
                    if run == 0:
                        s['hs']  = res['home_strength']['overall']
                        s['as_'] = res['away_strength']['overall']
                    gh, ga = res['home_goals'], res['away_goals']
                    if gh > ga:    s['wh'] += 1
                    elif gh == ga: s['d']  += 1
                    else:          s['wa'] += 1
                    s['gh']  += gh;  s['ga']  += ga
                    s['xgh'] += res['home_xg']; s['xga'] += res['away_xg']
                    s['sh']  += ms['home_shots'];  s['sa']  += ms['away_shots']
                    s['fh']  += ms['home_fouls'];  s['fa']  += ms['away_fouls']
                    s['yh']  += ms['home_yellow']; s['ya']  += ms['away_yellow']
                    s['rh']  += ms['home_red'];    s['ra']  += ms['away_red']
                    s['ph']  += ms.get('home_pressing_ball_wins', 0)
                    s['pa']  += ms.get('away_pressing_ball_wins', 0)
                    s['alh'] += ms.get('home_attacks_left',   0)
                    s['amh'] += ms.get('home_attacks_center', 0)
                    s['arh'] += ms.get('home_attacks_right',  0)
                    s['ala'] += ms.get('away_attacks_left',   0)
                    s['ama'] += ms.get('away_attacks_center', 0)
                    s['ara'] += ms.get('away_attacks_right',  0)
                    s['plans'] += len(res.get('plan_activations', []))

                    # Verletzungen
                    s['injuries'] += len(res.get('injury_events', []))

                    # Fallback-Stärken: final_strength == 50.0 in Spielerlisten
                    for player_list_key in ('home_players', 'away_players'):
                        for p in res.get(player_list_key, []):
                            if float(p.get('final_strength', 0)) == FALLBACK_STRENGTH:
                                s['fallbacks'] += 1

                    total += 1
                except Exception as e:
                    r[idx]['err'] += 1

            if (run + 1) % 10 == 0:
                self.stdout.write(f"  Lauf {run+1:>3}/{RUNS} | {time.time()-t0:.1f}s")

        elapsed = time.time() - t0
        N = RUNS
        G = total
        out = self.stdout.write

        # ── Tabelle 1: Ergebnis-Übersicht ────────────────────────────────────
        SEP = '=' * 122
        out(f"\n{SEP}")
        out(f"LIGA-MASSENTEST  |  {len(PAIRS)} Paarungen × {RUNS} Läufe = {G} Spiele  |  {elapsed:.1f}s  ({elapsed/G*1000:.1f} ms/Spiel)")
        out(SEP)
        out(f"{'Paarung':<48} {'StH':>6} {'StG':>6}  {'H-S%':>5} {'X%':>5} {'A-S%':>5}  {'∅TH':>5} {'∅TG':>5}  {'∅xGH':>6} {'∅xGG':>6}  {'Upsets':>7}")
        out('-' * 122)

        tot = dict(wh=0, d=0, wa=0, gh=0, ga=0, xgh=0.0, xga=0.0,
                   sh=0, sa=0, fh=0, fa=0, yh=0, ya=0, rh=0, ra=0,
                   ph=0, pa=0, plans=0, err=0, fav=0, upsets=0,
                   injuries=0, fallbacks=0)

        for s in r.values():
            ph_   = s['wh'] / N * 100
            pd_   = s['d']  / N * 100
            pa_   = s['wa'] / N * 100
            fav   = s['wh'] if s['hs'] >= s['as_'] else s['wa']
            upset = s['wa'] if s['hs'] >= s['as_'] else s['wh']
            lbl   = f"{s['home'][:22]} vs {s['away'][:22]}"
            out(f"{lbl:<48} {s['hs']:>6.1f} {s['as_']:>6.1f}  "
                f"{ph_:>4.0f}% {pd_:>4.0f}% {pa_:>4.0f}%  "
                f"{s['gh']/N:>5.2f} {s['ga']/N:>5.2f}  "
                f"{s['xgh']/N:>6.3f} {s['xga']/N:>6.3f}  {upset:>7}")
            for k in ('wh','d','wa','gh','ga','sh','sa','fh','fa',
                      'yh','ya','rh','ra','ph','pa','plans','err',
                      'injuries','fallbacks'):
                tot[k] += s[k]
            tot['xgh']   += s['xgh']; tot['xga']    += s['xga']
            tot['fav']   += fav;      tot['upsets']  += upset

        # ── Tabelle 2: Pressing & Zonen ──────────────────────────────────────
        out(f"\n{'='*104}")
        out("PRESSING & ANGRIFFSZONEN (Ø/Spiel)")
        out('=' * 104)
        out(f"{'Paarung':<48} {'∅PrH':>6} {'∅PrG':>6}  {'Att Heim L-M-R':>16} {'Att Gast L-M-R':>16}")
        out('-' * 104)
        for s in r.values():
            lbl   = f"{s['home'][:22]} vs {s['away'][:22]}"
            h_att = f"{s['alh']/N:.1f}-{s['amh']/N:.1f}-{s['arh']/N:.1f}"
            a_att = f"{s['ala']/N:.1f}-{s['ama']/N:.1f}-{s['ara']/N:.1f}"
            out(f"{lbl:<48} {s['ph']/N:>6.1f} {s['pa']/N:>6.1f}  {h_att:>16} {a_att:>16}")

        # ── Tabelle 3: Disziplin ──────────────────────────────────────────────
        out(f"\n{'='*110}")
        out("DISZIPLIN (Ø/Spiel)")
        out('=' * 110)
        out(f"{'Paarung':<48} {'SchH':>6} {'SchG':>6} {'FoulH':>6} {'FoulG':>6} {'GelbH':>6} {'GelbG':>6} {'RotH':>6} {'RotG':>6}")
        out('-' * 110)
        for s in r.values():
            lbl = f"{s['home'][:22]} vs {s['away'][:22]}"
            out(f"{lbl:<48} {s['sh']/N:>6.1f} {s['sa']/N:>6.1f} "
                f"{s['fh']/N:>6.1f} {s['fa']/N:>6.1f} "
                f"{s['yh']/N:>6.2f} {s['ya']/N:>6.2f} "
                f"{s['rh']/N:>6.3f} {s['ra']/N:>6.3f}")

        # ── Tabelle 4: Verletzungen & Fallbacks ───────────────────────────────
        out(f"\n{'='*80}")
        out("VERLETZUNGEN & FALLBACKS (Ø/Spiel)")
        out('=' * 80)
        out(f"{'Paarung':<48} {'∅Verl':>7} {'Fallb':>7}")
        out('-' * 80)
        for s in r.values():
            lbl = f"{s['home'][:22]} vs {s['away'][:22]}"
            out(f"{lbl:<48} {s['injuries']/N:>7.3f} {s['fallbacks']:>7}")

        # ── Gesamt-Auswertung ─────────────────────────────────────────────────
        out(f"\n{'='*70}")
        out(f"GESAMT-AUSWERTUNG  —  {G} Spiele")
        out('=' * 70)
        out(f"  Tore gesamt:              {tot['gh']+tot['ga']}  (Heim {tot['gh']} / Gast {tot['ga']})")
        out(f"  Ø Tore/Spiel:             {(tot['gh']+tot['ga'])/G:.3f}")
        out(f"  Ø xG Heim:                {tot['xgh']/G:.4f}")
        out(f"  Ø xG Gast:                {tot['xga']/G:.4f}")
        out(f"  Heimsiege:                {tot['wh']}  ({tot['wh']/G*100:.1f}%)")
        out(f"  Remis:                    {tot['d']}  ({tot['d']/G*100:.1f}%)")
        out(f"  Auswärtssiege:            {tot['wa']}  ({tot['wa']/G*100:.1f}%)")
        out(f"  Favoritensiege:           {tot['fav']}  ({tot['fav']/G*100:.1f}%)")
        out(f"  Upsets (Außenseiter gew): {tot['upsets']}  ({tot['upsets']/G*100:.1f}%)")
        out(f"  Ø Schüsse Heim:           {tot['sh']/G:.2f}")
        out(f"  Ø Schüsse Gast:           {tot['sa']/G:.2f}")
        out(f"  Ø Fouls/Spiel:            {(tot['fh']+tot['fa'])/G:.2f}")
        out(f"  Ø Gelbe/Spiel:            {(tot['yh']+tot['ya'])/G:.2f}")
        out(f"  Ø Rote/Spiel:             {(tot['rh']+tot['ra'])/G:.5f}")
        out(f"  Ø Verletzungen/Spiel:     {tot['injuries']/G:.4f}")
        out(f"  Fallback-Stärken (50.0):  {tot['fallbacks']}{'  ✓' if tot['fallbacks']==0 else '  ⚠ PRÜFEN!'}")
        out(f"  Ø Pressing-Gewinne Heim:  {tot['ph']/G:.2f}")
        out(f"  Ø Pressing-Gewinne Gast:  {tot['pa']/G:.2f}")
        out(f"  Plan-Aktivierungen:       {tot['plans']}")
        out(f"  Fehler:                   {tot['err']}{'  ✓' if tot['err']==0 else '  ⚠ PRÜFEN!'}")
        out(f"  Laufzeit:                 {elapsed:.1f}s  ({elapsed/G*1000:.1f} ms/Spiel)")
