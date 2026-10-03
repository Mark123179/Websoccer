"""Narrative Schicht: Was passiert gerade in diesem Spiel?

Aus Budget (Schüsse/Ecken je Block), Toren, Plänen, Pressing und Ballbesitz wird je 15-Minuten-Fenster
ein Zustand bestimmt. Der Zustand liefert (a) eine Phasenzeile beim Wechsel und (b) Kontext-Tags für
jede Sequenz im Fenster.
"""

WINDOW = 15

PHASES = ('abtasten', 'ruhig', 'kontrolle', 'druck', 'schlagabtausch', 'verwalten', 'schlussoffensive', 'pressing', 'zerfahren')


def _short(name):
    """Sprechname eines Vereins für Fließtext: 'FC Bayern München' -> 'Bayern'."""
    special = {'Bayern': 'Bayern', 'Mönchengladbach': 'Gladbach', 'Borussia Dortmund': 'Dortmund'}
    for k, v in special.items():
        if k in name:
            return v
    stop = {'fc', 'sv', 'tsg', 'vfb', 'vfl', 'sc', 'rb', 'fsv', '1.', 'e.v.', 'ii', 'u21', 'borussia', 'eintracht', 'hamburger', 'werder'}
    words = [w for w in name.replace('1899', '').replace('1846', '').split() if w.lower() not in stop and not w.isdigit()]
    if not words:
        words = name.split()
    if 'Hamburger' in name: return 'HSV'
    if 'Werder' in name: return 'Werder'
    if 'Eintracht' in name and len(words) == 1: return words[0]
    return words[-1]


def classify(ctx, budget):
    """Gibt Liste von Fenstern zurück: dict(from, to, phase, side, tags, numbers)."""
    fm = ctx.final_minute
    windows = []
    prev = None
    for w0 in range(0, fm, WINDOW):
        w1 = min(w0 + WINDOW, fm)
        num = {}
        for side in ('home', 'away'):
            segs = [b for b in budget[side] if b['from'] >= w0 and b['to'] <= w1]
            num[side] = {'shots': sum(b['shots'] for b in segs), 'ot': sum(b['on_target'] for b in segs),
                         'corners': sum(b['corners'] for b in segs), 'fouls': sum(b['fouls'] for b in segs)}
        goals_in = [g for g in ctx.goals if w0 < g['minute'] <= w1]
        score_before = {'home': len([g for g in ctx.goals if g['team'] == 'home' and g['minute'] <= w0]),
                        'away': len([g for g in ctx.goals if g['team'] == 'away' and g['minute'] <= w0])}
        plans = {}
        for side in ('home', 'away'):
            acts = [a for a in ctx.plan_activations if a['side'] == side and a['minute'] <= w0 + 4]
            plans[side] = acts[-1]['plan'] if acts else None
        h, a = num['home'], num['away']
        th = h['shots'] + h['corners'] * 0.5
        ta = a['shots'] + a['corners'] * 0.5
        phase, side = 'ruhig', None
        lead = 'home' if score_before['home'] > score_before['away'] else ('away' if score_before['away'] > score_before['home'] else None)
        trail = 'away' if lead == 'home' else ('home' if lead == 'away' else None)
        if w0 == 0 and th + ta <= 3:
            phase = 'abtasten'
        elif trail and plans[trail] in ('aggressiv_risiko', 'schlussangriff') and (th if trail == 'home' else ta) >= 2:
            phase, side = 'schlussoffensive', trail
        elif lead and plans[lead] in ('zeitspiel', 'kompakt_sichern', 'kontrolle_ballbesitz'):
            phase, side = 'verwalten', lead
        elif th >= 3 and ta >= 3:
            phase = 'schlagabtausch'
        elif th >= 2.5 and th >= 2 * max(ta, 0.5):
            phase, side = 'druck', 'home'
        elif ta >= 2.5 and ta >= 2 * max(th, 0.5):
            phase, side = 'druck', 'away'
        elif th + ta <= 1.5:
            poss = ctx.home.stats.get('possession', 50)
            if abs(poss - 50) >= 8:
                phase, side = 'kontrolle', 'home' if poss > 50 else 'away'
            else:
                phase = 'ruhig'
        else:
            poss = ctx.home.stats.get('possession', 50)
            if abs(poss - 50) >= 10:
                phase, side = 'kontrolle', 'home' if poss > 50 else 'away'
            else:
                phase = 'zerfahren'
        # Pressing als Zusatz: Team mit hohem Pressing-Index und Ballgewinnen
        pressing_side = None
        for s in ('home', 'away'):
            t = ctx.team(s).tactic
            if t.pressing_level in ('intensiv', 'hoch') and ctx.team(s).stats.get('pressing_ball_wins', 0) >= 4:
                pressing_side = s
        tags = {'phase_' + phase}
        if side: tags.add('phase_side_' + side)
        if pressing_side: tags.add('pressing_' + pressing_side)
        win = {'from': w0, 'to': w1, 'phase': phase, 'side': side, 'pressing_side': pressing_side, 'tags': tags,
               'numbers': num, 'score_before': score_before, 'changed': prev is None or (prev['phase'], prev['side']) != (phase, side),
               'plans': plans}
        windows.append(win)
        prev = win
    return windows


def window_for(windows, minute):
    for w in windows:
        if w['from'] < minute <= w['to'] or (minute == 0 and w['from'] == 0):
            return w
    return windows[-1]
