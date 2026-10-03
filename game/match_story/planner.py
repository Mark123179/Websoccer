"""Prioritätsplaner (E-T05): 15 Minuten fest, Mindestdauern je Klasse, Aufbau elastisch."""

REAL_SECONDS_90 = 900.0
REAL_SECONDS_ET = 300.0      # 30 Minuten Verlängerung proportional
SHOOTOUT_KICK_S = 8.0

# Mindestdauer je Planer-Klasse (Startwerte, werden an abgenommenen 2D-Szenen kalibriert)
MIN_S = {
    'goal': 22.0, 'kickoff_after_goal': 3.0, 'shot': 8.0, 'corner': 4.0, 'corner_end': 4.0, 'freekick': 6.0,
    'gk_clear': 6.0, 'card': 4.0, 'foul': 3.0, 'sub': 3.0, 'injury': 5.0, 'abort': 4.0,
    'kickoff': 6.0, 'halftime': 10.0, 'fulltime': 8.0, 'shootout_start': 6.0, 'shootout_kick': SHOOTOUT_KICK_S,
    'analysis': 0.0, 'flow': 0.0, 'buildup': 0.0,
}
# Elastische Beats: Wunschdauer, wenn Zeit da ist
ELASTIC_TARGET_S = 5.0
ELASTIC_MIN_S = 3.0
# Gewicht je Sequenz-Klasse für die Verteilung der Restzeit auf den Aufbau
SEQ_WEIGHT = {'goal': 3.0, 'shot': 2.0, 'corner': 1.5, 'freekick': 1.5, 'gk_clear': 1.2, 'foul': 1.0, 'abort': 1.0}


def _seq_class(lines_of_seq):
    classes = [l.cls for l in lines_of_seq]
    for c in ('goal', 'shot', 'corner', 'freekick', 'gk_clear', 'foul', 'abort'):
        if c in classes:
            return c
    return classes[-1] if classes else 'flow'


def plan(lines, ctx):
    budget = REAL_SECONDS_90 + (REAL_SECONDS_ET if ctx.has_extra_time else 0.0)
    kicks = [l for l in lines if l.cls == 'shootout_kick']
    budget += len(kicks) * SHOOTOUT_KICK_S + (MIN_S['shootout_start'] + MIN_S['fulltime'] if kicks else 0.0)

    # 1) Minima vergeben: Summe der Minima aller nicht-elastischen Beats einer Zeile
    fixed = 0.0
    for l in lines:
        beats = l.payload.get('beats') or [{'cls': l.cls, 'elastic': l.payload.get('elastic', False)}]
        l.duration_s = sum(MIN_S.get(b['cls'], 0.0) for b in beats if not b.get('elastic')) if l.visible else 0.0
        fixed += l.duration_s
    # 2) Restzeit auf elastische Beats verteilen
    rest = budget - fixed
    by_seq = {}
    for l in lines:
        by_seq.setdefault(l.seq, []).append(l)
    elastic = []
    for seq, ls in by_seq.items():
        w = SEQ_WEIGHT.get(_seq_class(ls), 1.0)
        for l in ls:
            if l.payload.get('elastic') and l.visible:
                elastic.append((l, w * l.payload.get('n_beats', 1)))
    total_w = sum(w for _, w in elastic) or 1.0
    if rest > 0 and elastic:
        per_w = rest / total_w
        # je Sequenz: Anteil vom Ende her auf ganze Beats legen (mind. 3 s), frühe Beats fallen auf Textzeile
        for seq, ls in by_seq.items():
            el = [l for l in ls if l.payload.get('elastic') and l.visible]
            if not el:
                continue
            w = SEQ_WEIGHT.get(_seq_class(ls), 1.0)
            n_beats = sum(l.payload.get('n_beats', 1) for l in el)
            share = per_w * w * n_beats
            for l in reversed(el):
                nb = l.payload.get('n_beats', 1)
                if share >= ELASTIC_MIN_S:
                    d = min(ELASTIC_TARGET_S * nb, share)
                    l.duration_s = d
                    share -= d
                else:
                    l.duration_s = 0.0
    else:
        for l, _ in elastic:
            l.duration_s = 0.0
        if rest < 0:
            # Notbremse: Minima proportional stauchen (sollte praktisch nie greifen)
            f = budget / fixed if fixed else 1.0
            for l in lines:
                l.duration_s *= f
    # 2b) Restzeit, die der Aufbau nicht aufnehmen konnte, streckt die sichtbaren Szenen (bis 2x Minimum)
    used = sum(l.duration_s for l in lines)
    left = budget - used
    if left > 1.0:
        stretchable = [l for l in lines if l.visible and l.duration_s > 0 and l.cls not in ('analysis',)]
        cap = [(l.duration_s * 2.0 if not l.payload.get('elastic') else ELASTIC_TARGET_S * 1.6 * l.payload.get('n_beats', 1)) for l in stretchable]
        room = sum(max(0.0, c - l.duration_s) for l, c in zip(stretchable, cap)) or 1.0
        f = min(1.0, left / room)
        for l, c in zip(stretchable, cap):
            l.duration_s += max(0.0, c - l.duration_s) * f
    # 3) Offsets
    t = 0.0
    for l in lines:
        l.offset_s = round(t, 2)
        t += l.duration_s
        l.duration_s = round(l.duration_s, 2)
    return {'budget_s': budget, 'used_s': round(t, 1), 'fixed_s': round(fixed, 1), 'elastic_beats': len(elastic)}
