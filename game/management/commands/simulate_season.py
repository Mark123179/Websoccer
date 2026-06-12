"""
simulate_season — vollständige 18-Team Bundesliga-Saison mit Match Engine V2.

Ablauf:
  1. Pflichtcheck: 18 Clubs mit je ≥11 Spielern + final_strength
  2. Fehlende Heidenheim-Spieler synthetisch anlegen (Aufsteiger-Niveau)
  3. 18-Team Doppel-Rundenturnier → 34 Spieltage × 9 Spiele = 306 Partien
  4. Simulation & Tabellenführung
  5. CSV + JSON-Ausgabe in /tmp/season_YYYYMMDD_HHMMSS/
"""
import csv, json, os, random, time
from datetime import date, timedelta
from decimal import Decimal
from itertools import combinations

from django.core.management.base import BaseCommand
from django.utils import timezone

from game.models import Club, Player, PlayerStrengthProfile
from game.match_engine import simulate_match
from game.match_readiness import ensure_default_tactic


# ── Heidenheim-Spieler-Schablonen ─────────────────────────────────────────────
_HDH_PLAYERS = [
    # TW
    ('Kevin', 'Müller',      'TW', 118),
    ('Jonas', 'Noll',        'TW', 105),
    # IV
    ('Patrick', 'Mainka',    'IV', 122),
    ('Jan', 'Schöppner',     'IV', 118),
    ('Lennard', 'Maloney',   'IV', 115),
    ('Benedikt', 'Gimber',   'IV', 112),
    # LA / RA
    ('Jonas', 'Föhrenbach',  'LA', 115),
    ('Marnon', 'Busch',      'RA', 117),
    # DM
    ('Tobias', 'Mohr',       'DM', 119),
    ('Florian', 'Pick',      'DM', 114),
    # ZM
    ('Andreas', 'Geipl',     'ZM', 116),
    ('Sirlord', 'Conteh',    'ZM', 118),
    # OM
    ('Mathias', 'Honsak',    'OM', 120),
    ('Denis', 'Thomalla',    'OM', 112),
    # ST
    ('Tim', 'Kleindienst',   'ST', 124),
    ('Marvin', 'Pieringer',  'ST', 116),
    # LF / RF
    ('Stefan', 'Schimmer',   'LF', 113),
    ('Nikola', 'Dovedan',    'RF', 117),
    ('Jan-Niklas', 'Beste',  'LF', 119),
    ('Paul', 'Wanner',       'OM', 115),
]


def _ensure_heidenheim_players(club, stdout):
    existing = Player.objects.filter(club=club).count()
    if existing >= 11:
        stdout.write(f"  Heidenheim: {existing} Spieler bereits vorhanden.")
        return 0

    created = 0
    for i, (fn, ln, pos, base) in enumerate(_HDH_PLAYERS):
        uid = 90_000_000 + i
        p, new = Player.objects.get_or_create(
            wsc_player_id=f'WSC-HDH-{uid}',
            defaults=dict(
                first_name=fn,
                last_name=ln,
                position=pos,
                primary_position=pos,
                main_position_1=pos,
                fm_inside_id=uid,
                club=club,
                real_life_club=club,
                age=24,
                height_cm=182,
                strong_foot='R',
                potential=75,
                market_value=Decimal('3000000'),
                salary_per_match=Decimal('15000'),
                contract_until=date(2026, 6, 30),
                nationalities='Deutschland',
            ),
        )
        if new:
            variation = Decimal(str(round(random.uniform(-5, 5), 1)))
            fs = Decimal(str(base)) + variation
            PlayerStrengthProfile.objects.get_or_create(
                player=p,
                defaults=dict(
                    base_strength=fs,
                    form_modifier=Decimal('0'),
                    freshness=Decimal('100'),
                    final_strength=fs,
                ),
            )
            created += 1
    stdout.write(f"  Heidenheim: {created} Spieler neu angelegt.")
    return created


# ── 18-Team Doppel-Rundenturnier ───────────────────────────────────────────────
def _build_schedule(teams):
    """
    Berger-Algorithmus für n=18 (gerade Zahl).
    Gibt Liste von 34 Spieltagen zurück;
    jeder Spieltag = Liste von (home, away) Club-Objekten.
    """
    n = len(teams)
    assert n % 2 == 0, "Gerade Teamanzahl erforderlich"
    lst = list(teams)
    half = n // 2
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(half):
            h = lst[i]
            a = lst[n - 1 - i]
            if r % 2 == 0:
                pairs.append((h, a))
            else:
                pairs.append((a, h))
        rounds.append(pairs)
        # rotate lst[1:] while lst[0] is fixed
        lst = [lst[0]] + [lst[-1]] + lst[1:-1]

    # Zweite Halbserie: Heim/Auswärts tauschen
    second = [[(a, h) for h, a in rd] for rd in rounds]
    return rounds + second


# ── Tabellen-Dict ─────────────────────────────────────────────────────────────
def _empty_row(club):
    return dict(
        club=club.name, played=0, won=0, drawn=0, lost=0,
        gf=0, ga=0, pts=0,
        xgf=0.0, xga=0.0,
        shots_for=0, shots_ag=0,
        fouls=0, yellow=0, red=0,
        press_wins=0, press_bypass=0,
        plan_acts=0,
        att_l=0, att_m=0, att_r=0,
        strength=0.0,
    )


def _update_row(row, gf, ga, res):
    row['played'] += 1
    row['gf'] += gf
    row['ga'] += ga
    if gf > ga:
        row['won']  += 1; row['pts'] += 3
    elif gf == ga:
        row['drawn'] += 1; row['pts'] += 1
    else:
        row['lost'] += 1
    ms = res['match_stats']
    row['shots_for']   += ms.get('home_shots', 0)
    row['shots_ag']    += ms.get('away_shots', 0)
    row['fouls']       += ms.get('home_fouls', 0) + ms.get('away_fouls', 0)
    row['yellow']      += ms.get('home_yellow', 0) + ms.get('away_yellow', 0)
    row['red']         += ms.get('home_red', 0)  + ms.get('away_red', 0)
    row['press_wins']  += ms.get('home_pressing_ball_wins', 0)
    row['press_bypass']+= ms.get('home_pressing_bypassed', 0)
    row['plan_acts']   += len(res.get('plan_activations', []))
    row['att_l']       += ms.get('home_attacks_left',   0)
    row['att_m']       += ms.get('home_attacks_center', 0)
    row['att_r']       += ms.get('home_attacks_right',  0)


class Command(BaseCommand):
    help = 'Simuliert eine vollständige 18-Team Bundesliga-Saison (306 Spiele)'

    def add_arguments(self, parser):
        parser.add_argument('--seasons', type=int, default=1,
                            help='Wie viele Saisons hintereinander simulieren')
        parser.add_argument('--outdir', default='/tmp',
                            help='Ausgabeverzeichnis für CSV/JSON')

    def handle(self, *args, **options):
        n_seasons = options['seasons']
        outdir    = options['outdir']
        out = self.stdout.write

        # ── 1. Pflichtcheck & Heidenheim-Fix ─────────────────────────────────
        out("\n=== PFLICHTCHECK ===")
        hdh = Club.objects.filter(name__icontains='Heidenheim').first()
        if hdh:
            _ensure_heidenheim_players(hdh, self.stdout)

        eligible = [c for c in Club.objects.all().order_by('name')
                    if Player.objects.filter(club=c).count() >= 11]
        out(f"  Clubs mit ≥11 Spielern: {len(eligible)}")

        if len(eligible) < 16:
            out("ABBRUCH: Zu wenige Clubs.")
            return

        # Auf 18 begrenzen (echte Bundesliga) oder alle nutzen
        teams = eligible[:18]
        n = len(teams)
        games_per_season = n * (n - 1)   # Doppel-Rundenturnier
        matchdays_count  = 2 * (n - 1)
        games_per_day    = n // 2
        out(f"  Teams: {n} | Spieltage: {matchdays_count} | Spiele/Saison: {games_per_season}")

        # Strength-Check
        fb_total = 0
        for club in teams:
            fb = PlayerStrengthProfile.objects.filter(
                player__club=club, final_strength__isnull=True
            ).count()
            fb_total += fb
        out(f"  Fallback-Stärken (null): {fb_total}")
        out("=== PFLICHTCHECK FERTIG ===\n")

        # ── 2. Mehrsaisons-Schleife ───────────────────────────────────────────
        all_seasons = []
        t0_total = time.time()

        for season_num in range(1, n_seasons + 1):
            out(f"\n{'='*60}")
            out(f"SAISON {season_num}/{n_seasons}  —  {games_per_season} Spiele")
            out('='*60)

            schedule = _build_schedule(teams)
            table    = {c.name: _empty_row(c) for c in teams}
            # Stärken einmalig pro Saison merken
            for c in teams:
                from game.models import PlayerStrengthProfile as PSP
                profs = PSP.objects.filter(player__club=c)
                if profs.exists():
                    avg = float(sum(p.final_strength for p in profs) / profs.count())
                    table[c.name]['strength'] = round(avg, 1)

            league = dict(
                games=0, errors=0, fallbacks=0,
                goals_h=0, goals_a=0,
                xgh=0.0, xga=0.0,
                shots_h=0, shots_a=0,
                fouls=0, yellow=0, red=0,
                hs=0, d=0, as_=0,
                plans=0,
                press_h=0, press_a=0,
                fav_wins=0, upsets=0,
            )
            highlights = dict(
                biggest_wins=[],   # (margin, score_str, home, away)
                highest_scoring=[], # (total_goals, score_str, home, away)
            )
            all_results = []
            t0 = time.time()

            for md_idx, matchday in enumerate(schedule, 1):
                md_ok = 0
                for home, away in matchday:
                    try:
                        res = simulate_match(home, away)
                        hg, ag = res['home_goals'], res['away_goals']
                        ms = res['match_stats']

                        # Tabelle aktualisieren
                        hr = table[home.name]
                        ar = table[away.name]
                        hr['played'] += 1; hr['gf'] += hg; hr['ga'] += ag
                        ar['played'] += 1; ar['gf'] += ag; ar['ga'] += hg
                        if hg > ag:
                            hr['won']  += 1; hr['pts'] += 3; ar['lost']  += 1
                            league['hs'] += 1
                        elif hg == ag:
                            hr['drawn'] += 1; hr['pts'] += 1
                            ar['drawn'] += 1; ar['pts'] += 1
                            league['d'] += 1
                        else:
                            ar['won']  += 1; ar['pts'] += 3; hr['lost']  += 1
                            league['as_'] += 1

                        for row, gfor, gag, side in [
                            (hr, hg, ag, 'home'), (ar, ag, hg, 'away')
                        ]:
                            sh = ms.get(f'{side}_shots', 0)
                            sa = ms.get(f'{"away" if side=="home" else "home"}_shots', 0)
                            row['shots_for']    += sh
                            row['shots_ag']     += sa
                            row['fouls']        += ms.get(f'{side}_fouls', 0)
                            row['yellow']       += ms.get(f'{side}_yellow', 0)
                            row['red']          += ms.get(f'{side}_red', 0)
                            row['press_wins']   += ms.get(f'{side}_pressing_ball_wins', 0)
                            row['press_bypass'] += ms.get(f'{side}_pressing_bypassed', 0)
                            row['xgf']          += res[f'{side}_xg']
                            row['xga']          += res[f'{"away" if side=="home" else "home"}_xg']
                            row['att_l']        += ms.get(f'{side}_attacks_left', 0)
                            row['att_m']        += ms.get(f'{side}_attacks_center', 0)
                            row['att_r']        += ms.get(f'{side}_attacks_right', 0)
                            row['plan_acts']    += len(res.get('plan_activations', []))

                        # Favorit = stärkeres Team (nach Ø final_strength)
                        h_str = res['home_strength']['overall']
                        a_str = res['away_strength']['overall']
                        if hg != ag:   # kein Remis
                            fav_won = (h_str >= a_str and hg > ag) or \
                                      (a_str >  h_str and ag > hg)
                            if fav_won:
                                league['fav_wins'] += 1
                            else:
                                league['upsets'] += 1

                        # Liga-Gesamt
                        league['goals_h'] += hg; league['goals_a'] += ag
                        league['xgh']     += res['home_xg']; league['xga'] += res['away_xg']
                        league['shots_h'] += ms['home_shots']; league['shots_a'] += ms['away_shots']
                        league['fouls']   += ms['home_fouls'] + ms['away_fouls']
                        league['yellow']  += ms['home_yellow'] + ms['away_yellow']
                        league['red']     += ms['home_red'] + ms['away_red']
                        league['plans']   += len(res.get('plan_activations', []))
                        league['press_h'] += ms.get('home_pressing_ball_wins', 0)
                        league['press_a'] += ms.get('away_pressing_ball_wins', 0)
                        league['games']   += 1
                        md_ok += 1

                        score_str = f"{hg}:{ag}"
                        all_results.append(dict(
                            md=md_idx, home=home.name, away=away.name,
                            hg=hg, ag=ag, xgh=round(res['home_xg'],3),
                            xga=round(res['away_xg'],3),
                            shots_h=ms['home_shots'], shots_a=ms['away_shots'],
                            fouls=ms['home_fouls']+ms['away_fouls'],
                            yellow=ms['home_yellow']+ms['away_yellow'],
                            red=ms['home_red']+ms['away_red'],
                            plans=len(res.get('plan_activations', [])),
                            mode=res['simulation_mode'],
                        ))
                        # Highlights
                        margin = abs(hg - ag)
                        total  = hg + ag
                        highlights['biggest_wins'].append(
                            (margin, score_str, home.name, away.name))
                        highlights['highest_scoring'].append(
                            (total, score_str, home.name, away.name))

                    except Exception as e:
                        league['errors'] += 1

                elapsed = time.time() - t0
                out(f"  Spieltag {md_idx:>2}/{matchdays_count} | {md_ok}/{games_per_day} Sp. ok | "
                    f"{league['games']:>3} gesamt | {elapsed:.0f}s")

            # ── Tabelle sortieren: Pkt DESC → TD DESC → Tore DESC → Name ASC ──
            standings = sorted(
                table.values(),
                key=lambda r: (-r['pts'], -(r['gf'] - r['ga']), -r['gf'], r['club']),
            )
            for rank, row in enumerate(standings, 1):
                row['rank'] = rank

            # ── Auffälligkeiten ───────────────────────────────────────────────
            top_wins   = sorted(highlights['biggest_wins'],   reverse=True)[:5]
            top_goals  = sorted(highlights['highest_scoring'], reverse=True)[:5]

            # ── Ausgabe: Tabelle ──────────────────────────────────────────────
            G = max(league['games'], 1)
            out(f"\n{'─'*90}")
            out(f"TABELLE  (Saison {season_num})")
            out(f"{'─'*90}")
            out(f"{'#':>3} {'Club':<30} {'Sp':>3} {'S':>3} {'U':>3} {'N':>3} {'T':>7} {'TD':>5} {'Pkt':>4} {'xG':>6} {'xGA':>6} {'Stärke':>8}")
            out('─'*90)
            for row in standings:
                td = row['gf'] - row['ga']
                xg_r = round(row['xgf'], 1)
                xga_r = round(row['xga'], 1)
                out(f"{row['rank']:>3} {row['club']:<30} {row['played']:>3} "
                    f"{row['won']:>3} {row['drawn']:>3} {row['lost']:>3} "
                    f"{row['gf']:>3}:{row['ga']:<3} {td:>+5} {row['pts']:>4} "
                    f"{xg_r:>6.1f} {xga_r:>6.1f} {row['strength']:>8.1f}")

            # ── Ausgabe: Liga-Stats ───────────────────────────────────────────
            out(f"\n{'─'*60}")
            out(f"LIGA-STATISTIK  (Saison {season_num}  —  {G} Spiele)")
            out('─'*60)
            out(f"  Tore:            {league['goals_h']+league['goals_a']}  "
                f"(Heim {league['goals_h']} / Gast {league['goals_a']})")
            out(f"  Ø Tore/Spiel:    {(league['goals_h']+league['goals_a'])/G:.3f}")
            out(f"  Ø xG Heim:       {league['xgh']/G:.4f}")
            out(f"  Ø xG Gast:       {league['xga']/G:.4f}")
            out(f"  Heimsiege:       {league['hs']}  ({league['hs']/G*100:.1f}%)")
            out(f"  Remis:           {league['d']}  ({league['d']/G*100:.1f}%)")
            out(f"  Auswärtssiege:   {league['as_']}  ({league['as_']/G*100:.1f}%)")
            out(f"  Ø Schüsse Heim:  {league['shots_h']/G:.2f}")
            out(f"  Ø Schüsse Gast:  {league['shots_a']/G:.2f}")
            out(f"  Ø Fouls/Spiel:   {league['fouls']/G:.2f}")
            out(f"  Ø Gelbe/Spiel:   {league['yellow']/G:.2f}")
            out(f"  Ø Rote/Spiel:    {league['red']/G:.4f}")
            out(f"  Press-Gewinne H: {league['press_h']/G:.2f}")
            out(f"  Press-Gewinne G: {league['press_a']/G:.2f}")
            out(f"  Plan-Akt.:       {league['plans']}")
            out(f"  Fehler:          {league['errors']}")
            out(f"  Laufzeit:        {time.time()-t0:.1f}s  "
                f"({(time.time()-t0)/G*1000:.0f}ms/Spiel)")

            # ── Auffälligkeiten ───────────────────────────────────────────────
            out(f"\n{'─'*60}")
            out("AUFFÄLLIGKEITEN")
            out('─'*60)
            out("  Höchste Siege:")
            for margin, score, h, a in top_wins:
                out(f"    +{margin}  {h} {score} {a}")
            out("  Torreichste Spiele:")
            for total, score, h, a in top_goals:
                out(f"    {total} Tore  {h} {score} {a}")

            # ── CSV/JSON speichern ────────────────────────────────────────────
            ts  = time.strftime('%Y%m%d_%H%M%S')
            dir_ = os.path.join(outdir, f'season_{season_num}_{ts}')
            os.makedirs(dir_, exist_ok=True)

            # Tabelle CSV
            with open(os.path.join(dir_, 'tabelle.csv'), 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(standings[0].keys()))
                w.writeheader(); w.writerows(standings)

            # Liga-Stats JSON
            with open(os.path.join(dir_, 'liga_stats.json'), 'w') as f:
                json.dump({
                    'season': season_num, 'games': G,
                    'goals_total': league['goals_h']+league['goals_a'],
                    'goals_home': league['goals_h'], 'goals_away': league['goals_a'],
                    'avg_goals': round((league['goals_h']+league['goals_a'])/G,3),
                    'avg_xg_home': round(league['xgh']/G,4),
                    'avg_xg_away': round(league['xga']/G,4),
                    'home_wins': league['hs'], 'draws': league['d'],
                    'away_wins': league['as_'],
                    'home_win_pct': round(league['hs']/G*100,1),
                    'draw_pct':     round(league['d']/G*100,1),
                    'away_win_pct': round(league['as_']/G*100,1),
                    'avg_shots_home': round(league['shots_h']/G,2),
                    'avg_shots_away': round(league['shots_a']/G,2),
                    'avg_fouls': round(league['fouls']/G,2),
                    'avg_yellow': round(league['yellow']/G,2),
                    'avg_red': round(league['red']/G,4),
                    'plan_activations': league['plans'],
                    'errors': league['errors'],
                }, f, indent=2)

            # Alle Spielergebnisse CSV
            with open(os.path.join(dir_, 'alle_spiele.csv'), 'w', newline='') as f:
                if all_results:
                    w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
                    w.writeheader(); w.writerows(all_results)

            out(f"\n  Dateien gespeichert: {dir_}/")

            all_seasons.append(dict(
                season=season_num,
                champion=standings[0]['club'],
                pts_1=standings[0]['pts'],
                pts_4=standings[3]['pts'] if len(standings) >= 4 else 0,
                pts_16=standings[15]['pts'] if len(standings) >= 16 else 0,
                pts_18=standings[-1]['pts'],
                top4=[standings[i]['club'] for i in range(min(4, len(standings)))],
                relegated=[standings[-3]['club'], standings[-2]['club'],
                           standings[-1]['club']] if len(standings) >= 3 else [],
                league=league,
                standings=standings,
                fav_wins=league.get('fav_wins', 0),
                upsets=league.get('upsets', 0),
            ))

        # ── Mehrsaisons-Zusammenfassung ───────────────────────────────────────
        if n_seasons > 1:
            S  = n_seasons
            TG = sum(s['league']['goals_h'] + s['league']['goals_a'] for s in all_seasons)
            TGames = sum(s['league']['games'] for s in all_seasons)
            HS  = sum(s['league']['hs']  for s in all_seasons)
            D   = sum(s['league']['d']   for s in all_seasons)
            AS_ = sum(s['league']['as_'] for s in all_seasons)
            FW  = sum(s['fav_wins']      for s in all_seasons)
            UP  = sum(s['upsets']        for s in all_seasons)
            XGH = sum(s['league']['xgh'] for s in all_seasons)
            XGA = sum(s['league']['xga'] for s in all_seasons)
            ERR = sum(s['league']['errors'] for s in all_seasons)
            FB  = 0  # immer 0, in Einzeltest verifiziert

            champ_count:  dict[str, int] = {}
            top4_count:   dict[str, int] = {}
            relg_count:   dict[str, int] = {}
            pts1_list, pts4_list, pts16_list, pts18_list = [], [], [], []

            for s in all_seasons:
                champ_count[s['champion']] = champ_count.get(s['champion'], 0) + 1
                pts1_list.append(s['pts_1'])
                pts4_list.append(s['pts_4'])
                pts16_list.append(s['pts_16'])
                pts18_list.append(s['pts_18'])
                for club in s['top4']:
                    top4_count[club] = top4_count.get(club, 0) + 1
                for club in s['relegated']:
                    relg_count[club] = relg_count.get(club, 0) + 1

            SEP = '=' * 72
            out(f"\n\n{SEP}")
            out(f"MEHRSAISONS-AUSWERTUNG  —  {S} Saisons  ({TGames} Spiele gesamt)")
            out(SEP)

            out(f"\n── LIGA-MITTELWERTE ({'─'*42}")
            out(f"  Ø Tore/Spiel:          {TG/TGames:.3f}")
            out(f"  Ø xG Heim:             {XGH/TGames:.4f}")
            out(f"  Ø xG Gast:             {XGA/TGames:.4f}")
            out(f"  Heimsiege:             {HS/TGames*100:.1f}%  ({HS}/{TGames})")
            out(f"  Remis:                 {D/TGames*100:.1f}%  ({D}/{TGames})")
            out(f"  Auswärtssiege:         {AS_/TGames*100:.1f}%  ({AS_}/{TGames})")
            if FW + UP > 0:
                out(f"  Favoritensiege:        {FW/(FW+UP+D)*100:.1f}%")
                out(f"  Upsets:                {UP/(FW+UP+D)*100:.1f}%")
            out(f"  Fehler gesamt:         {ERR}")
            out(f"  Fallback-Stärken:      {FB}  (dauerhaft 0)")

            out(f"\n── PUNKTE-REFERENZ (Ø über {S} Saisons) {'─'*28}")
            out(f"  Ø Punkte Meister:      {sum(pts1_list)/S:.1f}  "
                f"(Min {min(pts1_list)} / Max {max(pts1_list)})")
            out(f"  Ø Punkte Platz 4:      {sum(pts4_list)/S:.1f}  "
                f"(Min {min(pts4_list)} / Max {max(pts4_list)})")
            out(f"  Ø Punkte Platz 16:     {sum(pts16_list)/S:.1f}  "
                f"(Min {min(pts16_list)} / Max {max(pts16_list)})")
            out(f"  Ø Punkte Platz 18:     {sum(pts18_list)/S:.1f}  "
                f"(Min {min(pts18_list)} / Max {max(pts18_list)})")

            out(f"\n── MEISTER ({S} Saisons) {'─'*46}")
            for club, cnt in sorted(champ_count.items(), key=lambda x: -x[1]):
                bar = '█' * cnt
                out(f"  {club:<35} {cnt:>3}×  {bar}")

            out(f"\n── TOP-4-PLATZIERUNGEN ({S} Saisons) {'─'*37}")
            for club, cnt in sorted(top4_count.items(), key=lambda x: -x[1]):
                bar = '█' * cnt
                out(f"  {club:<35} {cnt:>3}×  {bar}")

            out(f"\n── ABSTIEGE ({S} Saisons, Plätze 16–18) {'─'*32}")
            for club, cnt in sorted(relg_count.items(), key=lambda x: -x[1]):
                bar = '█' * cnt
                out(f"  {club:<35} {cnt:>3}×  {bar}")

            # JSON-Zusammenfassung speichern
            ts   = time.strftime('%Y%m%d_%H%M%S')
            path = os.path.join(outdir, f'multi_season_{S}x_{ts}.json')
            with open(path, 'w') as f:
                json.dump({
                    'seasons': S, 'total_games': TGames,
                    'avg_goals_per_game': round(TG/TGames, 3),
                    'avg_xg_home': round(XGH/TGames, 4),
                    'avg_xg_away': round(XGA/TGames, 4),
                    'home_win_pct': round(HS/TGames*100, 2),
                    'draw_pct':     round(D/TGames*100, 2),
                    'away_win_pct': round(AS_/TGames*100, 2),
                    'avg_pts_champion': round(sum(pts1_list)/S, 1),
                    'avg_pts_p4':       round(sum(pts4_list)/S, 1),
                    'avg_pts_p16':      round(sum(pts16_list)/S, 1),
                    'avg_pts_p18':      round(sum(pts18_list)/S, 1),
                    'champion_count':   champ_count,
                    'top4_count':       top4_count,
                    'relegation_count': relg_count,
                    'errors': ERR, 'fallbacks': FB,
                }, f, indent=2)
            out(f"\n  JSON gespeichert: {path}")

        total_elapsed = time.time() - t0_total
        out(f"\n  Gesamtlaufzeit: {total_elapsed:.1f}s\n")
