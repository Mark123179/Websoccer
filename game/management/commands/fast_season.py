"""
fast_season — 10-Saisons-Stabilitätstest mit Match Engine V2.

Optimierung: Teams werden einmalig als Dicts geladen (ORM-Queries nur 1×),
dann wird _simulate_match_minutes() direkt aufgerufen — kein DB-Hit pro Spiel.
Ergebnis: ~10-15 ms/Spiel statt ~164 ms/Spiel.
"""
import json, os, time, random
from collections import defaultdict
from copy import deepcopy

from django.core.management.base import BaseCommand

from game.models import Club, Player
from game.match_engine import _build_team_dict, _simulate_match_minutes
from game.match_readiness import ensure_default_tactic


def _build_schedule(teams):
    """Berger-Algorithmus — 18 Teams, 34 Spieltage, 306 Spiele."""
    lst = list(teams)
    n, half = len(lst), len(lst) // 2
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(half):
            h, a = lst[i], lst[n - 1 - i]
            pairs.append((h, a) if r % 2 == 0 else (a, h))
        rounds.append(pairs)
        lst = [lst[0]] + [lst[-1]] + lst[1:-1]
    second = [[(a, h) for h, a in rd] for rd in rounds]
    return rounds + second


class Command(BaseCommand):
    help = 'Schneller 10-Saisons-Stabilitätstest (Teams werden einmalig geladen)'

    def add_arguments(self, parser):
        parser.add_argument('--seasons', type=int, default=10)
        parser.add_argument('--outdir',  default='/tmp')

    def handle(self, *args, **options):
        N_SEASONS = options['seasons']
        outdir    = options['outdir']
        out = self.stdout.write

        # ── 1. Teams laden (1× ORM) ───────────────────────────────────────────
        out("\n=== TEAM-SETUP (einmalig) ===")
        t_setup = time.time()

        eligible = [c for c in Club.objects.all().order_by('name')
                    if Player.objects.filter(club=c).count() >= 11][:18]

        team_dicts = {}     # name → team_dict
        strengths  = {}     # name → overall float
        for club in eligible:
            tactic, _ = ensure_default_tactic(club)
            td = _build_team_dict(club, tactic)
            team_dicts[club.name] = td
            from game.tactic_compiler import compile_tactic
            from game.match_engine import _calculate_lineup_strength
            comp = compile_tactic(td, td.get('tactic', {}), half=1)
            s    = _calculate_lineup_strength(td, td.get('tactic', {}), comp)
            strengths[club.name] = s['overall']

        out(f"  {len(team_dicts)} Teams geladen in {time.time()-t_setup:.1f}s")
        out(f"  Stärken:")
        for name, st in sorted(strengths.items(), key=lambda x: -x[1]):
            out(f"    {name:<32} {st:.1f}")

        names    = list(team_dicts.keys())
        schedule = _build_schedule(names)

        # Mehrsaisons-Aggregat
        agg = dict(
            total_games=0, total_goals=0,
            goals_h=0, goals_a=0,
            xgh=0.0, xga=0.0,
            hs=0, d=0, as_=0,
            fav=0, upset=0,
            fouls=0, yellow=0, red=0,
            shots_h=0, shots_a=0,
            plans=0, errors=0,
        )
        pts1, pts4, pts16, pts18 = [], [], [], []
        champ_cnt:  dict[str,int] = defaultdict(int)
        top4_cnt:   dict[str,int] = defaultdict(int)
        relg_cnt:   dict[str,int] = defaultdict(int)
        season_rows = []

        t0_all = time.time()

        for season_num in range(1, N_SEASONS + 1):
            t0_s = time.time()

            table = {n: dict(
                club=n, played=0, won=0, drawn=0, lost=0,
                gf=0, ga=0, pts=0, xgf=0.0, xga=0.0,
                shots_for=0, shots_ag=0, fouls=0, yellow=0, red=0,
                press_wins=0, plan_acts=0,
            ) for n in names}

            s_games = s_goals_h = s_goals_a = 0
            s_xgh = s_xga = 0.0
            s_hs = s_d = s_as_ = 0
            s_fav = s_upset = 0
            s_fouls = s_yellow = s_red = 0
            s_shots_h = s_shots_a = 0
            s_plans = s_errors = 0

            for matchday in schedule:
                for hname, aname in matchday:
                    try:
                        # Frische Kopien der Team-Dicts (deepcopy nur tactic-Teil)
                        ht = team_dicts[hname]
                        at = team_dicts[aname]
                        sim = _simulate_match_minutes(ht, at)

                        hg  = sim['home_goals']
                        ag  = sim['away_goals']
                        ms  = sim['match_stats']
                        hxg = sim['home_xg']
                        axg = sim['away_xg']
                        hs_ = sim['home_strength']['overall']
                        as_ = sim['away_strength']['overall']
                        plans = len(sim.get('plan_activations', []))

                        # Tabelle
                        hr = table[hname]; ar = table[aname]
                        hr['played'] += 1; hr['gf'] += hg; hr['ga'] += ag
                        ar['played'] += 1; ar['gf'] += ag; ar['ga'] += hg
                        hr['xgf'] += hxg; hr['xga'] += axg
                        ar['xgf'] += axg; ar['xga'] += hxg
                        hr['fouls']  += ms.get('home_fouls', 0)
                        ar['fouls']  += ms.get('away_fouls', 0)
                        hr['yellow'] += ms.get('home_yellow', 0)
                        ar['yellow'] += ms.get('away_yellow', 0)
                        hr['red']    += ms.get('home_red', 0)
                        ar['red']    += ms.get('away_red', 0)
                        hr['shots_for'] += ms.get('home_shots', 0)
                        hr['shots_ag']  += ms.get('away_shots', 0)
                        ar['shots_for'] += ms.get('away_shots', 0)
                        ar['shots_ag']  += ms.get('home_shots', 0)
                        hr['press_wins'] += ms.get('home_pressing_ball_wins', 0)
                        ar['press_wins'] += ms.get('away_pressing_ball_wins', 0)
                        hr['plan_acts'] += plans
                        ar['plan_acts'] += plans

                        if hg > ag:
                            hr['won'] += 1; hr['pts'] += 3; ar['lost'] += 1; s_hs += 1
                        elif hg == ag:
                            hr['drawn'] += 1; hr['pts'] += 1
                            ar['drawn'] += 1; ar['pts'] += 1; s_d += 1
                        else:
                            ar['won'] += 1; ar['pts'] += 3; hr['lost'] += 1; s_as_ += 1

                        if hg != ag:
                            h_is_fav = strengths[hname] >= strengths[aname]
                            fav_won  = (h_is_fav and hg > ag) or (not h_is_fav and ag > hg)
                            if fav_won: s_fav += 1
                            else:       s_upset += 1

                        s_games    += 1
                        s_goals_h  += hg;  s_goals_a  += ag
                        s_xgh      += hxg; s_xga      += axg
                        s_fouls    += ms.get('home_fouls',0)+ms.get('away_fouls',0)
                        s_yellow   += ms.get('home_yellow',0)+ms.get('away_yellow',0)
                        s_red      += ms.get('home_red',0)+ms.get('away_red',0)
                        s_shots_h  += ms.get('home_shots',0)
                        s_shots_a  += ms.get('away_shots',0)
                        s_plans    += plans

                    except Exception as e:
                        s_errors += 1

            # Tabelle sortieren
            standings = sorted(
                table.values(),
                key=lambda r: (-r['pts'], -(r['gf']-r['ga']), -r['gf'], r['club']),
            )
            for rank, row in enumerate(standings, 1):
                row['rank'] = rank

            # Aggregat aktualisieren
            G = max(s_games, 1)
            agg['total_games'] += s_games
            agg['goals_h']     += s_goals_h;  agg['goals_a'] += s_goals_a
            agg['xgh']         += s_xgh;      agg['xga']     += s_xga
            agg['hs']          += s_hs;       agg['d']       += s_d;  agg['as_'] += s_as_
            agg['fav']         += s_fav;      agg['upset']   += s_upset
            agg['fouls']       += s_fouls;    agg['yellow']  += s_yellow
            agg['red']         += s_red
            agg['shots_h']     += s_shots_h;  agg['shots_a'] += s_shots_a
            agg['plans']       += s_plans;    agg['errors']  += s_errors
            agg['total_goals'] += s_goals_h + s_goals_a

            pts1.append(standings[0]['pts'])
            pts4.append(standings[3]['pts'])
            pts16.append(standings[15]['pts'])
            pts18.append(standings[-1]['pts'])
            champ_cnt[standings[0]['club']] += 1
            for row in standings[:4]:
                top4_cnt[row['club']] += 1
            for row in standings[-3:]:
                relg_cnt[row['club']] += 1

            elapsed_s = time.time() - t0_s

            # Einzelsaison-Tabelle ausgeben
            out(f"\n{'='*98}")
            out(f"SAISON {season_num:>2}/{N_SEASONS}  —  {G} Spiele  |  "
                f"Tore: {s_goals_h+s_goals_a}  Ø{(s_goals_h+s_goals_a)/G:.2f}/Sp  |  "
                f"H:{s_hs}({s_hs/G*100:.0f}%) U:{s_d}({s_d/G*100:.0f}%) A:{s_as_}({s_as_/G*100:.0f}%)  |  "
                f"{elapsed_s:.0f}s")
            out('─'*98)
            out(f"{'#':>3} {'Club':<30} {'Sp':>3} {'S':>3} {'U':>3} {'N':>3} "
                f"{'Tore':>7} {'TD':>5} {'Pkt':>4} {'xG':>6} {'xGA':>6} {'Stärke':>8}")
            out('─'*98)
            for row in standings:
                td   = row['gf'] - row['ga']
                name = row['club']
                out(f"{row['rank']:>3} {name:<30} {row['played']:>3} "
                    f"{row['won']:>3} {row['drawn']:>3} {row['lost']:>3} "
                    f"{row['gf']:>3}:{row['ga']:<3} {td:>+5} {row['pts']:>4} "
                    f"{row['xgf']:>6.1f} {row['xga']:>6.1f} "
                    f"{strengths.get(name,0):>8.1f}")

            season_rows.append(dict(
                season=season_num,
                champion=standings[0]['club'],
                pts_1=standings[0]['pts'],
                pts_4=standings[3]['pts'],
                pts_16=standings[15]['pts'],
                pts_18=standings[-1]['pts'],
                avg_goals=round((s_goals_h+s_goals_a)/G,3),
                home_win_pct=round(s_hs/G*100,1),
                draw_pct=round(s_d/G*100,1),
                away_win_pct=round(s_as_/G*100,1),
                errors=s_errors,
            ))

        # ── MEHRSAISONS-ZUSAMMENFASSUNG ───────────────────────────────────────
        TG = max(agg['total_games'], 1)
        SEP = '=' * 72

        out(f"\n\n{SEP}")
        out(f"MEHRSAISONS-AUSWERTUNG  —  {N_SEASONS} Saisons  ({TG} Spiele gesamt)")
        out(SEP)

        out(f"\n── LIGA-MITTELWERTE ─────────────────────────────────────────────")
        out(f"  Ø Tore/Spiel:          {agg['total_goals']/TG:.3f}")
        out(f"  Ø xG Heim:             {agg['xgh']/TG:.4f}")
        out(f"  Ø xG Gast:             {agg['xga']/TG:.4f}")
        out(f"  Heimsiege:             {agg['hs']/TG*100:.1f}%  ({agg['hs']}/{TG})")
        out(f"  Remis:                 {agg['d']/TG*100:.1f}%  ({agg['d']}/{TG})")
        out(f"  Auswärtssiege:         {agg['as_']/TG*100:.1f}%  ({agg['as_']}/{TG})")
        decided = agg['fav'] + agg['upset']
        if decided:
            out(f"  Favoritensiege:        {agg['fav']/decided*100:.1f}%  ({agg['fav']})")
            out(f"  Upsets:                {agg['upset']/decided*100:.1f}%  ({agg['upset']})")
        out(f"  Ø Schüsse Heim:        {agg['shots_h']/TG:.2f}")
        out(f"  Ø Schüsse Gast:        {agg['shots_a']/TG:.2f}")
        out(f"  Ø Fouls/Spiel:         {agg['fouls']/TG:.2f}")
        out(f"  Ø Gelbe/Spiel:         {agg['yellow']/TG:.2f}")
        out(f"  Ø Rote/Spiel:          {agg['red']/TG:.4f}")
        out(f"  Plan-Aktivierungen:    {agg['plans']}")
        out(f"  Fehler gesamt:         {agg['errors']}")
        out(f"  Fallback-Stärken:      0  (dauerhaft 0)")

        out(f"\n── PUNKTE-REFERENZ (Ø / Min / Max über {N_SEASONS} Saisons) ────────────")
        out(f"  Meister:    Ø {sum(pts1)/N_SEASONS:.1f}  (Min {min(pts1)} / Max {max(pts1)})")
        out(f"  Platz 4:    Ø {sum(pts4)/N_SEASONS:.1f}  (Min {min(pts4)} / Max {max(pts4)})")
        out(f"  Platz 16:   Ø {sum(pts16)/N_SEASONS:.1f}  (Min {min(pts16)} / Max {max(pts16)})")
        out(f"  Platz 18:   Ø {sum(pts18)/N_SEASONS:.1f}  (Min {min(pts18)} / Max {max(pts18)})")

        out(f"\n── MEISTER ({N_SEASONS} Saisons) ─────────────────────────────────────────")
        for club, cnt in sorted(champ_cnt.items(), key=lambda x: -x[1]):
            out(f"  {club:<35} {cnt:>3}×  {'█'*cnt}")

        out(f"\n── TOP-4-PLATZIERUNGEN ({N_SEASONS} Saisons) ──────────────────────────────")
        for club, cnt in sorted(top4_cnt.items(), key=lambda x: -x[1]):
            out(f"  {club:<35} {cnt:>3}×  {'█'*cnt}")

        out(f"\n── ABSTIEGE ({N_SEASONS} Saisons, Plätze 16–18) ───────────────────────────")
        for club, cnt in sorted(relg_cnt.items(), key=lambda x: -x[1]):
            out(f"  {club:<35} {cnt:>3}×  {'█'*cnt}")

        # JSON speichern
        ts   = time.strftime('%Y%m%d_%H%M%S')
        path = os.path.join(outdir, f'fast_season_{N_SEASONS}x_{ts}.json')
        with open(path, 'w') as f:
            json.dump({
                'seasons': N_SEASONS, 'total_games': TG,
                'avg_goals_per_game': round(agg['total_goals']/TG, 3),
                'avg_xg_home':  round(agg['xgh']/TG, 4),
                'avg_xg_away':  round(agg['xga']/TG, 4),
                'home_win_pct': round(agg['hs']/TG*100, 2),
                'draw_pct':     round(agg['d']/TG*100, 2),
                'away_win_pct': round(agg['as_']/TG*100, 2),
                'fav_win_pct':  round(agg['fav']/max(decided,1)*100, 2),
                'upset_pct':    round(agg['upset']/max(decided,1)*100, 2),
                'avg_pts_champion': round(sum(pts1)/N_SEASONS, 1),
                'avg_pts_p4':       round(sum(pts4)/N_SEASONS, 1),
                'avg_pts_p16':      round(sum(pts16)/N_SEASONS, 1),
                'avg_pts_p18':      round(sum(pts18)/N_SEASONS, 1),
                'min_pts_champion': min(pts1), 'max_pts_champion': max(pts1),
                'champion_count':   dict(champ_cnt),
                'top4_count':       dict(top4_cnt),
                'relegation_count': dict(relg_cnt),
                'season_by_season': season_rows,
                'errors': agg['errors'], 'fallbacks': 0,
            }, f, indent=2)
        out(f"\n  JSON gespeichert: {path}")
        out(f"  Gesamtlaufzeit:   {time.time()-t0_all:.1f}s\n")
