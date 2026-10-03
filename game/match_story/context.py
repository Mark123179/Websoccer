"""Aus report_data (+ optionalem TacticSetup-Dump) den Erzählkontext bauen."""
from dataclasses import dataclass, field
from .model import Player

ZONE_KEYS = ('left', 'center', 'right')

@dataclass
class Tactic:
    attack_focus: str = 'ausgewogen'
    buildup_defense: str = 'standard'
    buildup_midfield: str = 'standard'
    buildup_attack: str = 'standard'
    deckung: str = 'hybrid'
    zweikampf: str = 'normal'
    breite: str = 'standard'
    umschalten: str = 'ausgewogen'
    pressing: dict = field(default_factory=lambda: {'defense': 'normal', 'midfield': 'normal', 'attack': 'normal'})
    pressing_triggers: list = field(default_factory=list)
    halves: dict = field(default_factory=dict)      # first_half/second_half: defense/midfield/attack/effort
    standards: dict = field(default_factory=dict)   # penalty/free_kick/corner/captain -> player id (oder '')
    plans: list = field(default_factory=list)       # Bedingungen
    tempo: float = 50.0
    pressing_index: float = 0.0

    @property
    def pressing_level(self) -> str:
        lv = [self.pressing.get(k, 'normal') for k in ('defense', 'midfield', 'attack')]
        order = ['passiv', 'normal', 'intensiv', 'hoch']
        return max(lv, key=lambda x: order.index(x) if x in order else 1)

@dataclass
class Team:
    side: str
    name: str
    short: str
    players: dict            # id -> Player (inkl. Bank)
    formation: str
    stats: dict              # shots, shots_on_target, corners, fouls, yellow, red, possession, attacks_*, pressing_*
    xg: float
    tactic: Tactic
    zone_strengths: dict

    def on_pitch(self, minute):
        return [p for p in self.players.values() if p.on_pitch(minute)]

    def by_group(self, minute, *groups):
        return [p for p in self.on_pitch(minute) if p.group in groups]

    def keeper(self, minute):
        gk = [p for p in self.on_pitch(minute) if p.group == 'GK']
        return gk[0] if gk else None

    @property
    def attacks_total(self):
        return sum(self.stats.get(f'attacks_{z}', 0) for z in ZONE_KEYS)

@dataclass
class MatchContext:
    match_id: int
    match_type: str
    home: Team
    away: Team
    goals: list
    cards: list
    dismissals: list
    subs: dict               # side -> list
    injuries: list
    near_misses: list
    plan_activations: list
    penalty_events: list
    decided_by: str
    goals_90: dict
    goals_et: dict
    referee: str
    weather: dict
    plan_seg_stats: dict
    raw: dict

    def team(self, side): return self.home if side == 'home' else self.away
    def opp(self, side): return self.away if side == 'home' else self.home
    def player(self, pid):
        return self.home.players.get(pid) or self.away.players.get(pid)

    @property
    def has_extra_time(self):
        return self.decided_by in ('extra_time', 'penalties')

    @property
    def final_minute(self):
        return 120 if self.has_extra_time else 90


def _team_from(rd, side, tac_dump, subs, goals, cards, dismissals, injuries, final_minute):
    players = {}
    ratings = {r['id']: r.get('rating', 3.5) for r in rd.get(f'{side}_ratings', [])}
    for p in rd.get(f'{side}_players', []):
        pl = Player(id=p['id'], name=p['name'], position=p.get('position') or 'ZM', team=side,
                    rating=ratings.get(p['id'], 3.5), on_minute=p.get('on_minute', 0),
                    off_minute=p.get('off_minute', final_minute) or final_minute)
        players[pl.id] = pl
    for b in rd.get(f'{side}_bench', []):
        if b['id'] not in players:
            players[b['id']] = Player(id=b['id'], name=b['name'], position=b.get('position') or 'ZM',
                                      team=side, rating=ratings.get(b['id'], 3.5),
                                      on_minute=999, off_minute=999, is_sub=True)
    # Wechsel korrigieren (on/off der Bankspieler kommen nicht immer aus *_players)
    for s in subs:
        m = s['minute']
        if s['out'] in players:
            players[s['out']].off_minute = min(players[s['out']].off_minute, m)
            players[s['out']].subbed_off = True
        if s['in'] in players:
            players[s['in']].on_minute = m
            players[s['in']].off_minute = final_minute if players[s['in']].off_minute >= 999 else players[s['in']].off_minute
            players[s['in']].is_sub = True
    for d in dismissals:
        if d.get('club_side') == side and d.get('player_id') in players:
            players[d['player_id']].off_minute = min(players[d['player_id']].off_minute, d['minute'])
    for c in cards:
        if c.get('card_type') in ('red', 'yellow_red') and c.get('club_side') == side and c.get('player_id') in players:
            players[c['player_id']].off_minute = min(players[c['player_id']].off_minute, c['minute'])
    for i in injuries:
        if i.get('club_side', i.get('team')) == side and i.get('player_id') in players:
            players[i['player_id']].off_minute = min(players[i['player_id']].off_minute, i['minute'])

    ms = rd.get('match_stats') or {}
    stats = {k[len(side) + 1:]: v for k, v in ms.items() if k.startswith(side + '_')}

    comp = rd.get(f'{side}_compiled_tactic') or {}
    dbg = comp.get('debug') or {}
    tac = Tactic()
    tac.attack_focus = dbg.get('attack_focus', 'ausgewogen')
    tac.tempo = float(dbg.get('tempo', comp.get('tempo', 50.0)) or 50.0)
    tac.pressing_index = float(dbg.get('pressing_index', 0.0) or 0.0)
    tac.pressing_triggers = list(dbg.get('active_triggers') or [])
    tac.halves = rd.get(f'{side}_tactic_halves') or {}
    if tac_dump:
        instr = tac_dump.get('instructions') or {}
        bu = instr.get('buildup') or {}
        df = instr.get('defending') or {}
        tac.buildup_defense = bu.get('defense', 'standard')
        tac.buildup_midfield = bu.get('midfield', 'standard')
        tac.buildup_attack = bu.get('attack', 'standard')
        if instr.get('attack_focus') and not dbg.get('attack_focus'):
            tac.attack_focus = instr['attack_focus']
        tac.deckung = df.get('deckung', 'hybrid')
        tac.zweikampf = df.get('zweikampf', 'normal')
        tac.breite = df.get('breite', 'standard')
        tac.umschalten = df.get('umschalten', 'ausgewogen')
        tac.pressing = instr.get('pressing') or tac.pressing
        st = tac_dump.get('standards') or {}
        tac.standards = {k: (int(v) if str(v).isdigit() else None) for k, v in st.items()}
        tac.plans = tac_dump.get('conditions') or []

    return Team(side=side, name=rd.get(f'{side}_club_name', side), short=rd.get(f'{side}_club_short', side[:3].upper()),
                players=players, formation=rd.get(f'{side}_formation', ''), stats=stats,
                xg=float(rd.get(f'{side}_xg', 0.0) or 0.0), tactic=tac,
                zone_strengths=rd.get(f'{side}_zone_strengths') or {})


def build_context(export: dict) -> MatchContext:
    rd = export['report_data']
    m = export.get('match') or {}
    decided = rd.get('decided_by', 'regular_time')
    final_minute = 120 if decided in ('extra_time', 'penalties') else 90
    subs = {'home': rd.get('home_substitutions') or [], 'away': rd.get('away_substitutions') or []}
    goals = sorted(rd.get('goal_events') or [], key=lambda g: g['minute'])
    cards = sorted(rd.get('card_events') or [], key=lambda c: c['minute'])
    dism = rd.get('dismissal_events') or []
    inj = rd.get('injury_events') or []
    home = _team_from(rd, 'home', export.get('home_tactic'), subs['home'], goals, cards, dism, inj, final_minute)
    away = _team_from(rd, 'away', export.get('away_tactic'), subs['away'], goals, cards, dism, inj, final_minute)
    cd = rd.get('condition_debug') or {}
    return MatchContext(
        match_id=int(m.get('id', 0)), match_type=m.get('match_type', rd.get('match_type', 'liga')),
        home=home, away=away, goals=goals, cards=cards, dismissals=dism, subs=subs, injuries=inj,
        near_misses=rd.get('sp_near_miss_events') or [], plan_activations=rd.get('plan_activations') or [],
        penalty_events=rd.get('penalty_events') or [], decided_by=decided,
        goals_90={'home': rd.get('home_goals_90', rd.get('home_goals')), 'away': rd.get('away_goals_90', rd.get('away_goals'))},
        goals_et={'home': rd.get('home_goals_et', 0), 'away': rd.get('away_goals_et', 0)},
        referee=m.get('referee') or '', weather=rd.get('weather') or {},
        plan_seg_stats=cd.get('plan_seg_stats') or {}, raw=rd,
    )
