"""
fast_season — Mehrsaisons-Stabilitätstest mit Match Engine V2.

Optimierung: Teams werden einmalig als Dicts geladen (ORM-Queries nur 1×),
dann wird _simulate_match_minutes() direkt aufgerufen — kein DB-Hit pro Spiel.
Ergebnis: ~10-15 ms/Spiel statt ~164 ms/Spiel.

Exportierte Metriken:
  - Meisterhäufigkeit, Top-4-, Bottom-3-Häufigkeit
  - Ø Punkte / Ø Tabellenplatz je Club
  - Stärke-Rang vs Ø Tabellenplatz / Ø Punkte
  - xG-Differenz vs Punkte (Pearson r je Saison → Mittel)
  - Favoritensiege / Upsets
  - Punkteabstände: Meister↔2., 15.↔16., 16.↔17., 17.↔18.
"""
import json, os, time, math
from collections import defaultdict

from django.core.management.base import BaseCommand

from game.models import Club, Player
from game.match_engine import _build_team_dict, _simulate_match_minutes
from game.match_readiness import ensure_default_tactic


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

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


def _pearson_r(xs, ys):
    """Pearson-Korrelationskoeffizient zweier gleich langer Listen."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx  = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy  = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx * dy else 0.0


# ─── Command ──────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Schneller Mehrsaisons-Stabilitätstest (Teams werden einmalig geladen)'

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

        team_dicts = {}
        strengths  = {}
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
        strength_rank = {}  # name → Stärke-Rang (1 = stärkster)
        for rank_i, (name, st) in enumerate(
                sorted(strengths.items(), key=lambda x: -x[1]), 1):
            strength_rank[name] = rank_i
            out(f"    {rank_i:>2}. {name:<32} {st:.1f}")

        names    = list(team_dicts.keys())
        schedule = _build_schedule(names)

        # ── 2. Mehrsaisons-Aggregate initialisieren ───────────────────────────
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

        # Punkte-Ranglisten je Saison (Platz 1–4 und 15–18)
        pts_by_pos = {p: [] for p in [1, 2, 4, 15, 16, 17, 18]}

        # Per-Club-Akkumulation über alle Saisons
        club_pts_acc  = defaultdict(list)   # name → [pts_s1, pts_s2, …]
        club_rank_acc = defaultdict(list)   # name → [rank_s1, rank_s2, …]
        club_xgd_acc  = defaultdict(list)   # name → [xgd_s1, xgd_s2, …] (für Korrelation)

        # Häufigkeiten
        champ_cnt = defaultdict(int)
        top4_cnt  = defaultdict(int)
        relg_cnt  = defaultdict(int)

        # xGD-Punkte-Korrelation je Saison
        xgd_pts_r_list = []

        season_rows = []
        t0_all = time.time()

        # ── 3. Saisons simulieren ─────────────────────────────────────────────
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
                        ht  = team_dicts[hname]
                        at  = team_dicts[aname]
                        sim = _simulate_match_minutes(ht, at)

                        hg  = sim['home_goals']
                        ag  = sim['away_goals']
                        ms  = sim['match_stats']
                        hxg = sim['home_xg']
                        axg = sim['away_xg']
                        plans = len(sim.get('plan_activations', []))

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

                        s_games   += 1
                        s_goals_h += hg;  s_goals_a  += ag
                        s_xgh     += hxg; s_xga      += axg
                        s_fouls   += ms.get('home_fouls', 0) + ms.get('away_fouls', 0)
                        s_yellow  += ms.get('home_yellow', 0) + ms.get('away_yellow', 0)
                        s_red     += ms.get('home_red', 0) + ms.get('away_red', 0)
                        s_shots_h += ms.get('home_shots', 0)
                        s_shots_a += ms.get('away_shots', 0)
                        s_plans   += plans

                    except Exception:
                        s_errors += 1

            # Tabelle sortieren
            standings = sorted(
                table.values(),
                key=lambda r: (-r['pts'], -(r['gf'] - r['ga']), -r['gf'], r['club']),
            )
            for rank, row in enumerate(standings, 1):
                row['rank'] = rank

            # Per-Club akkumulieren
            for row in standings:
                n = row['club']
                club_pts_acc[n].append(row['pts'])
                club_rank_acc[n].append(row['rank'])
                xgd = row['xgf'] - row['xga']
                club_xgd_acc[n].append(xgd)

            # xGD-Punkte-Korrelation für diese Saison
            season_xgd  = [row['xgf'] - row['xga'] for row in standings]
            season_pts  = [row['pts'] for row in standings]
            r_season    = _pearson_r(season_xgd, season_pts)
            xgd_pts_r_list.append(r_season)

            # Positionen 1, 2, 4, 15, 16, 17, 18
            for pos in [1, 2, 4, 15, 16, 17, 18]:
                pts_by_pos[pos].append(standings[pos - 1]['pts'])

            # Häufigkeiten
            champ_cnt[standings[0]['club']] += 1
            for row in standings[:4]:
                top4_cnt[row['club']] += 1
            for row in standings[-3:]:
                relg_cnt[row['club']] += 1

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

            elapsed_s = time.time() - t0_s

            # Einzelsaison-Tabelle
            out(f"\n{'='*100}")
            out(f"SAISON {season_num:>2}/{N_SEASONS}  —  {G} Spiele  |  "
                f"Tore: {s_goals_h+s_goals_a}  Ø{(s_goals_h+s_goals_a)/G:.2f}/Sp  |  "
                f"H:{s_hs}({s_hs/G*100:.0f}%) U:{s_d}({s_d/G*100:.0f}%) "
                f"A:{s_as_}({s_as_/G*100:.0f}%)  |  r(xGD,Pts)={r_season:.3f}  |  {elapsed_s:.0f}s")
            out('─' * 100)
            out(f"{'#':>3} {'Club':<30} {'Sp':>3} {'S':>3} {'U':>3} {'N':>3} "
                f"{'Tore':>7} {'TD':>5} {'Pkt':>4} {'xGF':>6} {'xGA':>6} "
                f"{'xGD':>6} {'Stärke':>8}")
            out('─' * 100)
            for row in standings:
                td  = row['gf'] - row['ga']
                xgd = row['xgf'] - row['xga']
                nm  = row['club']
                out(f"{row['rank']:>3} {nm:<30} {row['played']:>3} "
                    f"{row['won']:>3} {row['drawn']:>3} {row['lost']:>3} "
                    f"{row['gf']:>3}:{row['ga']:<3} {td:>+5} {row['pts']:>4} "
                    f"{row['xgf']:>6.1f} {row['xga']:>6.1f} {xgd:>+6.1f} "
                    f"{strengths.get(nm, 0):>8.1f}")

            season_rows.append(dict(
                season=season_num,
                champion=standings[0]['club'],
                pts_1=standings[0]['pts'],
                pts_2=standings[1]['pts'],
                pts_4=standings[3]['pts'],
                pts_15=standings[14]['pts'],
                pts_16=standings[15]['pts'],
                pts_17=standings[16]['pts'],
                pts_18=standings[-1]['pts'],
                gap_1_2=standings[0]['pts'] - standings[1]['pts'],
                gap_15_16=standings[14]['pts'] - standings[15]['pts'],
                gap_16_17=standings[15]['pts'] - standings[16]['pts'],
                gap_17_18=standings[16]['pts'] - standings[-1]['pts'],
                avg_goals=round((s_goals_h + s_goals_a) / G, 3),
                home_win_pct=round(s_hs / G * 100, 1),
                draw_pct=round(s_d / G * 100, 1),
                away_win_pct=round(s_as_ / G * 100, 1),
                xgd_pts_r=round(r_season, 4),
                errors=s_errors,
            ))

        # ── 4. MEHRSAISONS-ZUSAMMENFASSUNG ────────────────────────────────────
        TG  = max(agg['total_games'], 1)
        SEP = '=' * 80
        decided = agg['fav'] + agg['upset']

        out(f"\n\n{SEP}")
        out(f"MEHRSAISONS-AUSWERTUNG  —  {N_SEASONS} Saisons  ({TG} Spiele gesamt)")
        out(SEP)

        # ── Liga-Mittelwerte ──
        out(f"\n── LIGA-MITTELWERTE ────────────────────────────────────────────────────")
        out(f"  Ø Tore/Spiel:           {agg['total_goals']/TG:.3f}")
        out(f"  Ø xG Heim:              {agg['xgh']/TG:.4f}")
        out(f"  Ø xG Gast:              {agg['xga']/TG:.4f}")
        out(f"  Heimsiege:              {agg['hs']/TG*100:.1f}%  ({agg['hs']}/{TG})")
        out(f"  Remis:                  {agg['d']/TG*100:.1f}%  ({agg['d']}/{TG})")
        out(f"  Auswärtssiege:          {agg['as_']/TG*100:.1f}%  ({agg['as_']}/{TG})")
        if decided:
            out(f"  Favoritensiege:         {agg['fav']/decided*100:.1f}%  ({agg['fav']}/{decided})")
            out(f"  Upsets:                 {agg['upset']/decided*100:.1f}%  ({agg['upset']}/{decided})")
        out(f"  Ø Schüsse Heim/Spiel:   {agg['shots_h']/TG:.2f}")
        out(f"  Ø Schüsse Gast/Spiel:   {agg['shots_a']/TG:.2f}")
        out(f"  Ø Fouls/Spiel:          {agg['fouls']/TG:.2f}")
        out(f"  Ø Gelbe/Spiel:          {agg['yellow']/TG:.2f}")
        out(f"  Ø Rote/Spiel:           {agg['red']/TG:.4f}")
        out(f"  Plan-Aktivierungen:     {agg['plans']}")
        out(f"  Fehler gesamt:          {agg['errors']}")

        # ── Punkte-Referenz ──
        def _stats(lst):
            return f"Ø {sum(lst)/len(lst):.1f}  Min {min(lst)}  Max {max(lst)}"

        out(f"\n── PUNKTE-REFERENZ (Ø / Min / Max über {N_SEASONS} Saisons) ────────────────────")
        out(f"  Meister  (Platz  1):  {_stats(pts_by_pos[1])}")
        out(f"  Platz  2:             {_stats(pts_by_pos[2])}")
        out(f"  Platz  4:             {_stats(pts_by_pos[4])}")
        out(f"  Platz 15:             {_stats(pts_by_pos[15])}")
        out(f"  Platz 16:             {_stats(pts_by_pos[16])}")
        out(f"  Platz 17:             {_stats(pts_by_pos[17])}")
        out(f"  Platz 18:             {_stats(pts_by_pos[18])}")

        # ── Punkteabstände ──
        gaps_1_2   = [r['gap_1_2']   for r in season_rows]
        gaps_15_16 = [r['gap_15_16'] for r in season_rows]
        gaps_16_17 = [r['gap_16_17'] for r in season_rows]
        gaps_17_18 = [r['gap_17_18'] for r in season_rows]

        out(f"\n── PUNKTEABSTÄNDE (Ø / Min / Max über {N_SEASONS} Saisons) ──────────────────────")
        out(f"  Meister ↔ Platz 2:    {_stats(gaps_1_2)}")
        out(f"  Platz 15 ↔ 16:        {_stats(gaps_15_16)}")
        out(f"  Platz 16 ↔ 17:        {_stats(gaps_16_17)}")
        out(f"  Platz 17 ↔ 18:        {_stats(gaps_17_18)}")

        # ── xGD-Punkte-Korrelation ──
        r_mean = sum(xgd_pts_r_list) / N_SEASONS
        out(f"\n── xG-DIFFERENZ vs PUNKTE (Pearson r) ──────────────────────────────────")
        out(f"  Ø r über {N_SEASONS} Saisons:      {r_mean:.4f}")
        out(f"  Min r:                  {min(xgd_pts_r_list):.4f}")
        out(f"  Max r:                  {max(xgd_pts_r_list):.4f}")
        out(f"  (1.0 = perfekte xGD→Punkte-Vorhersage)")

        # ── Per-Club: Ø Punkte / Ø Rang ──
        out(f"\n── Ø PUNKTE & TABELLENPLATZ je Club ({N_SEASONS} Saisons, sortiert nach Ø Rang) ──")
        out('─' * 80)
        out(f"  {'Club':<32} {'Stärke':>7} {'StRg':>5} {'ØPkt':>6} {'ØRang':>6} {'MinRg':>6} {'MaxRg':>6}")
        out('─' * 80)

        club_summary = []
        for name in names:
            ranks = club_rank_acc[name]
            pts   = club_pts_acc[name]
            club_summary.append(dict(
                name=name,
                strength=strengths[name],
                str_rank=strength_rank[name],
                avg_pts=sum(pts) / len(pts),
                avg_rank=sum(ranks) / len(ranks),
                min_rank=min(ranks),
                max_rank=max(ranks),
                avg_xgd=sum(club_xgd_acc[name]) / len(club_xgd_acc[name]),
            ))
        club_summary.sort(key=lambda x: x['avg_rank'])

        for c in club_summary:
            out(f"  {c['name']:<32} {c['strength']:>7.1f} {c['str_rank']:>5} "
                f"{c['avg_pts']:>6.1f} {c['avg_rank']:>6.2f} "
                f"{c['min_rank']:>6} {c['max_rank']:>6}")

        # ── Stärke-Rang vs Ø Tabellenplatz ──
        out(f"\n── STÄRKE-RANG vs Ø TABELLENPLATZ ({N_SEASONS} Saisons) ──────────────────────")
        out('─' * 70)
        out(f"  {'StRg':>5}  {'Club':<32} {'Stärke':>7}  {'ØRang':>6}  {'Delta':>6}")
        out('─' * 70)
        for c in sorted(club_summary, key=lambda x: x['str_rank']):
            delta = c['avg_rank'] - c['str_rank']
            sign  = '+' if delta >= 0 else ''
            out(f"  {c['str_rank']:>5}  {c['name']:<32} {c['strength']:>7.1f}  "
                f"{c['avg_rank']:>6.2f}  {sign}{delta:>5.2f}")

        # Pearson r zwischen Stärke-Rang und Ø Rang
        str_ranks_list = [c['str_rank']  for c in club_summary]
        avg_ranks_list = [c['avg_rank']  for c in club_summary]
        avg_pts_list   = [c['avg_pts']   for c in club_summary]
        r_rank = _pearson_r(str_ranks_list, avg_ranks_list)
        r_pts  = _pearson_r(str_ranks_list, avg_pts_list)
        out(f"\n  Pearson r(Stärke-Rang, Ø Tabellenplatz): {r_rank:.4f}")

        # ── Stärke-Rang vs Ø Punkte ──
        out(f"\n── STÄRKE-RANG vs Ø PUNKTE ({N_SEASONS} Saisons) ────────────────────────────")
        out('─' * 70)
        out(f"  {'StRg':>5}  {'Club':<32} {'Stärke':>7}  {'ØPkt':>6}")
        out('─' * 70)
        for c in sorted(club_summary, key=lambda x: x['str_rank']):
            out(f"  {c['str_rank']:>5}  {c['name']:<32} {c['strength']:>7.1f}  {c['avg_pts']:>6.1f}")
        out(f"\n  Pearson r(Stärke-Rang, Ø Punkte):         {r_pts:.4f}")
        out(f"  (negativer Wert = höhere Stärke → weniger Punkte; korrekt da Rang 1=stärkst)")

        # ── Meisterhäufigkeit ──
        out(f"\n── MEISTERHÄUFIGKEIT ({N_SEASONS} Saisons) ─────────────────────────────────────")
        for club, cnt in sorted(champ_cnt.items(), key=lambda x: -x[1]):
            bar = '█' * cnt
            out(f"  {club:<35} {cnt:>3}×  {bar}")

        # ── Top-4-Häufigkeit ──
        out(f"\n── TOP-4-HÄUFIGKEIT ({N_SEASONS} Saisons) ──────────────────────────────────────")
        out(f"  {'Club':<35} {'T4':>4}×  {'%':>5}  Bar")
        out('─' * 60)
        for club, cnt in sorted(top4_cnt.items(), key=lambda x: -x[1]):
            pct = cnt / N_SEASONS * 100
            bar = '█' * (cnt // 2)
            out(f"  {club:<35} {cnt:>4}×  {pct:>4.0f}%  {bar}")

        # ── Bottom-3-Häufigkeit ──
        out(f"\n── ABSTIEGS-HÄUFIGKEIT Bottom-3 ({N_SEASONS} Saisons) ───────────────────────────")
        out(f"  {'Club':<35} {'B3':>4}×  {'%':>5}  Bar")
        out('─' * 60)
        for club, cnt in sorted(relg_cnt.items(), key=lambda x: -x[1]):
            pct = cnt / N_SEASONS * 100
            bar = '█' * (cnt // 2)
            out(f"  {club:<35} {cnt:>4}×  {pct:>4.0f}%  {bar}")

        # ── JSON speichern ──
        ts   = time.strftime('%Y%m%d_%H%M%S')
        path = os.path.join(outdir, f'fast_season_{N_SEASONS}x_{ts}.json')
        with open(path, 'w') as f:
            json.dump({
                'seasons':            N_SEASONS,
                'total_games':        TG,
                'avg_goals_per_game': round(agg['total_goals'] / TG, 3),
                'avg_xg_home':        round(agg['xgh'] / TG, 4),
                'avg_xg_away':        round(agg['xga'] / TG, 4),
                'home_win_pct':       round(agg['hs'] / TG * 100, 2),
                'draw_pct':           round(agg['d'] / TG * 100, 2),
                'away_win_pct':       round(agg['as_'] / TG * 100, 2),
                'fav_win_pct':        round(agg['fav'] / max(decided, 1) * 100, 2),
                'upset_pct':          round(agg['upset'] / max(decided, 1) * 100, 2),
                'xgd_pts_pearson_r':  round(r_mean, 4),
                'str_rank_vs_avg_rank_r': round(r_rank, 4),
                'str_rank_vs_avg_pts_r':  round(r_pts, 4),
                'pts_by_position': {
                    str(pos): {
                        'avg': round(sum(pts_by_pos[pos]) / N_SEASONS, 1),
                        'min': min(pts_by_pos[pos]),
                        'max': max(pts_by_pos[pos]),
                    }
                    for pos in [1, 2, 4, 15, 16, 17, 18]
                },
                'gaps': {
                    '1_2':   {'avg': round(sum(gaps_1_2) / N_SEASONS, 1),
                              'min': min(gaps_1_2), 'max': max(gaps_1_2)},
                    '15_16': {'avg': round(sum(gaps_15_16) / N_SEASONS, 1),
                              'min': min(gaps_15_16), 'max': max(gaps_15_16)},
                    '16_17': {'avg': round(sum(gaps_16_17) / N_SEASONS, 1),
                              'min': min(gaps_16_17), 'max': max(gaps_16_17)},
                    '17_18': {'avg': round(sum(gaps_17_18) / N_SEASONS, 1),
                              'min': min(gaps_17_18), 'max': max(gaps_17_18)},
                },
                'club_stats': [
                    {
                        'name':     c['name'],
                        'strength': round(c['strength'], 1),
                        'str_rank': c['str_rank'],
                        'avg_pts':  round(c['avg_pts'], 2),
                        'avg_rank': round(c['avg_rank'], 2),
                        'min_rank': c['min_rank'],
                        'max_rank': c['max_rank'],
                        'avg_xgd':  round(c['avg_xgd'], 2),
                        'champion_count': champ_cnt.get(c['name'], 0),
                        'top4_count':     top4_cnt.get(c['name'], 0),
                        'relegation_count': relg_cnt.get(c['name'], 0),
                    }
                    for c in sorted(club_summary, key=lambda x: x['str_rank'])
                ],
                'champion_count':   dict(champ_cnt),
                'top4_count':       dict(top4_cnt),
                'relegation_count': dict(relg_cnt),
                'season_by_season': season_rows,
                'errors':   agg['errors'],
                'fallbacks': 0,
            }, f, indent=2)

        out(f"\n  JSON gespeichert: {path}")
        out(f"  Gesamtlaufzeit:   {time.time()-t0_all:.1f}s\n")
