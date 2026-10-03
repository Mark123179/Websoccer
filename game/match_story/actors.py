"""Akteurwahl (E-T07): Position + Note, Engine-Ereignisse zählen nie gegen einen Deckel."""
import random

# Rollengruppen je Beat-Rolle. Reihenfolge = Präferenz.
ROLE_GROUPS = {
    'aufbau':    (('DEF', 'MID'), ('AMID',)),
    'mittelfeld': (('MID', 'AMID'), ('DEF',)),
    'fluegel':   (('AMID', 'DEF'), ('ATT',)),      # Außenspieler werden zusätzlich nach Seite gefiltert
    'kreativ':   (('AMID', 'MID'), ('ATT',)),
    'abschluss': (('ATT', 'AMID'), ('MID',)),
    'kopfball':  (('ATT', 'DEF'), ('MID', 'AMID')),
    'verteidiger': (('DEF', 'MID'), ('AMID',)),
    'block':     (('DEF',), ('MID',)),
    'keeper':    (('GK',), ()),
    'zweikampf_off': (('AMID', 'ATT', 'MID'), ('DEF',)),
    'zweikampf_def': (('DEF', 'MID'), ('AMID',)),
    'pressing':  (('ATT', 'AMID', 'MID'), ('DEF',)),
    'beliebig':  (('DEF', 'MID', 'AMID', 'ATT'), ()),
}

def _rating_weight(p, good):
    """good=True: gute Noten bevorzugen (Note 1.0 -> hoch), good=False: schlechte."""
    r = max(1.0, min(6.0, p.rating))
    if good is None:
        return 1.0
    return (6.5 - r) if good else (r - 0.5)


class ActorPicker:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.pairs = {}   # (mann-deckung) verteidiger-id -> angreifer-id

    def pick(self, team, minute, role, good=None, exclude=(), side=None, prefer_fresh=True):
        prim, sec = ROLE_GROUPS[role]
        cands = [p for p in team.on_pitch(minute) if p.group in prim and p.id not in exclude]
        if side and role in ('fluegel',):
            sided = [p for p in cands if p.side == side]
            if sided:
                cands = sided
        if not cands:
            cands = [p for p in team.on_pitch(minute) if p.group in sec and p.id not in exclude]
        if not cands and role != 'keeper':
            cands = [p for p in team.on_pitch(minute) if p.id not in exclude and p.group != 'GK']
        if not cands and role != 'keeper':
            cands = [p for p in team.on_pitch(minute) if p.group in prim] or [p for p in team.on_pitch(minute) if p.group != 'GK']
        if not cands:
            return None
        weights = []
        for p in cands:
            w = _rating_weight(p, good)
            if prefer_fresh:
                w *= 1.0 / (1.0 + 0.7 * p.load)       # Lastausgleich nur im Bindegewebe
            weights.append(max(w, 0.05))
        p = self.rng.choices(cands, weights=weights, k=1)[0]
        if prefer_fresh:
            p.load += 1
        return p

    def opponent(self, ctx, attacker, minute, role='zweikampf_def', good=None):
        """Gegenspieler: Manndeckung -> feste Paare, sonst gleiche Seite bevorzugt."""
        opp = ctx.opp(attacker.team)
        if opp.tactic.deckung == 'mann':
            for d_id, a_id in self.pairs.items():
                if a_id == attacker.id and d_id in opp.players and opp.players[d_id].on_pitch(minute):
                    return opp.players[d_id]
            d = self.pick(opp, minute, role, good=good, prefer_fresh=False)
            if d:
                self.pairs[d.id] = attacker.id
            return d
        cands = [p for p in opp.on_pitch(minute) if p.group in ('DEF', 'MID')]
        sided = [p for p in cands if p.side == attacker.side]
        pool = sided or cands or opp.on_pitch(minute)
        if not pool:
            return None
        weights = [max(_rating_weight(p, good) / (1.0 + 0.2 * p.load), 0.05) for p in pool]
        p = self.rng.choices(pool, weights=weights, k=1)[0]
        p.load += 1
        return p

    def taker(self, team, minute, kind, fallback_role):
        """Standardschütze aus der Taktik, falls auf dem Platz; sonst Rolle."""
        pid = (team.tactic.standards or {}).get(kind)
        if pid and pid in team.players and team.players[pid].on_pitch(minute):
            return team.players[pid]
        return self.pick(team, minute, fallback_role, good=True, prefer_fresh=False)
