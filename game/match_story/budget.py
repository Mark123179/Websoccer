"""Budget je Team und 5-Minuten-Block.

Sobald die Engine das Segment-Log liefert (E-T11), ersetzt `from_segment_log`
die Ersatzverteilung `distribute` — der Rest des Erzählers bleibt gleich.
"""
import random

SEG_LEN = 5

def segments_for(final_minute):
    return [(s, s + SEG_LEN) for s in range(0, final_minute, SEG_LEN)]

def seg_index(minute, final_minute):
    m = max(1, min(minute, final_minute))
    return min((m - 1) // SEG_LEN, final_minute // SEG_LEN - 1)


def _weights(ctx, side, segs):
    team = ctx.team(side)
    poss = team.stats.get('possession', 50) / 50.0
    w = []
    active_plan = None
    plan_ups = {'aggressiv_risiko': 1.6, 'schlussangriff': 1.9, 'kontrolle_ballbesitz': 1.1,
                'kompakt_sichern': 0.6, 'zeitspiel': 0.45, 'unterzahl_kompakt': 0.5, 'ausgewogen': 1.0}
    acts = sorted([a for a in ctx.plan_activations if a.get('side') == side], key=lambda a: a['minute'])
    goal_minutes = [g['minute'] for g in ctx.goals if g['team'] == side]
    for i, (a, b) in enumerate(segs):
        base = 1.0 * poss
        for act in acts:
            if act['minute'] <= a:
                active_plan = act['plan']
        base *= plan_ups.get(active_plan, 1.0)
        if b > 75 and b <= 90: base *= 1.15          # Schlussphase
        if a >= 90: base *= 0.8                        # Verlängerung
        if any(a < gm <= b for gm in goal_minutes): base *= 1.6   # Drangphase um das Tor
        if a == 0: base *= 0.7                         # Abtasten
        w.append(base)
    return w


def _spread(total, weights, rng, minimums):
    """Verteilt `total` auf len(weights) Blöcke, hält `minimums` je Block ein."""
    n = len(weights)
    counts = list(minimums)
    rest = total - sum(counts)
    if rest <= 0:
        return counts
    ws = [max(w, 0.05) for w in weights]
    s = sum(ws)
    for _ in range(rest):
        # gewichtete Ziehung mit Zufall statt starrer Rundung
        r = rng.random() * s
        acc = 0.0
        for i, w in enumerate(ws):
            acc += w
            if r <= acc:
                counts[i] += 1
                break
        else:
            counts[n - 1] += 1
    return counts


def distribute(ctx, rng: random.Random):
    """Ersatzverteilung: Summen -> Blöcke. Anker (Tore, Eckentore, Ecken-Fastchancen, Karten) zuerst."""
    fm = ctx.final_minute
    segs = segments_for(fm)
    n = len(segs)
    out = {}
    for side in ('home', 'away'):
        st = ctx.team(side).stats
        goals = [g for g in ctx.goals if g['team'] == side]
        min_shots = [0] * n
        min_ontarget = [0] * n
        min_corners = [0] * n
        min_fouls = [0] * n
        nm_shots = [0] * n          # Ecken-Fastchancen: Schuss, aber nie aufs Tor
        for g in goals:
            i = seg_index(g['minute'], fm)
            min_shots[i] += 1
            min_ontarget[i] += 1
            if g.get('goal_type') == 'corner':
                min_corners[i] += 1
        for nm in ctx.near_misses:
            if nm.get('team') == side:
                i = seg_index(nm['minute'], fm)
                if nm.get('type', '').startswith('corner'):
                    min_corners[i] += 1
                    min_shots[i] += 1
                    nm_shots[i] += 1
        for c in ctx.cards:
            if c.get('club_side') == side:
                min_fouls[seg_index(c['minute'], fm)] += 1
        w = _weights(ctx, side, segs)
        shots_total = max(int(st.get('shots', 0)), sum(min_shots))
        ot_total = max(int(st.get('shots_on_target', 0)), sum(min_ontarget))
        ot_total = min(ot_total, shots_total)
        corners_total = max(int(st.get('corners', 0)), sum(min_corners))
        fouls_total = max(int(st.get('fouls', 0)), sum(min_fouls))
        shots = _spread(shots_total, w, rng, min_shots)
        # aufs Tor: Teilmenge der Schüsse je Block
        # Kapazität je Block: Schüsse minus Ecken-Fastchancen (die sind nie aufs Tor).
        # Ohne diesen Abzug landet ein Schuss aufs Tor in einem Block, der ihn nicht erzählen kann.
        ot = list(min_ontarget)
        cap = [max(shots[i] - nm_shots[i], ot[i]) for i in range(n)]
        pool = [i for i in range(n) for _ in range(max(0, cap[i] - ot[i]))]
        rng.shuffle(pool)
        for i in pool[:max(0, ot_total - sum(ot))]:
            ot[i] += 1
        # Reicht die Kapazität nicht (Engine-Daten inkonsistent), Rest in Bloecke mit freien Schuessen
        rest = ot_total - sum(ot)
        if rest > 0:
            spare = [i for i in range(n) for _ in range(max(0, shots[i] - ot[i]))]
            rng.shuffle(spare)
            for i in spare[:rest]:
                ot[i] += 1
        corners = _spread(corners_total, w, rng, min_corners)
        # Fouls: leicht Richtung Gegner-Ballbesitz gewichtet (wer nicht den Ball hat, foult)
        w_f = [x * (1.0 if ctx.team(side).stats.get('possession', 50) >= 50 else 1.2) for x in w]
        fouls = _spread(fouls_total, w_f, rng, min_fouls)
        out[side] = [{'from': a, 'to': b, 'shots': shots[i], 'on_target': ot[i], 'corners': corners[i], 'fouls': fouls[i]}
                     for i, (a, b) in enumerate(segs)]
    return out


def from_segment_log(ctx):
    """Platzhalter für E-T11: nimmt `report_data['segment_log']`, sobald vorhanden."""
    log = ctx.raw.get('segment_log')
    if not log:
        return None
    out = {'home': [], 'away': []}
    for seg in log:
        for side in ('home', 'away'):
            s = seg.get(side) or {}
            out[side].append({'from': seg['minute_from'], 'to': seg['minute_to'],
                              'shots': s.get('shots', 0), 'on_target': s.get('shots_on_target', 0),
                              'corners': s.get('corners', 0), 'fouls': s.get('fouls', 0)})
    return out
