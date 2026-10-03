"""Narrative Memory (A) und Segment-Log der Erzählung (B).

`MatchState` ist der explizite Spielzustand, den der Erzähler mitführt. `build_segments` erzeugt
nach dem Lauf die maschinenlesbare Geschichte oberhalb der Textzeilen – je 15-Minuten-Fenster ein
Eintrag mit dominierender Seite, Intensität, Chancen, Ereigniskette und Phasensatz.
"""
from dataclasses import dataclass, field, asdict


@dataclass
class MatchState:
    score: dict = field(default_factory=lambda: {'home': 0, 'away': 0})
    last_goal_team: str = None
    last_goal_minute: int = -99
    last_goal_ctx: str = None
    unanswered_goals: int = 0          # Tore des letzten Torschützen-Teams in Folge
    response_pending: str = None       # Seite, die auf ein Gegentor noch nicht geantwortet hat
    comeback_chain: list = field(default_factory=list)   # Abfolge der Spielstände
    last_phase_team: str = None
    last_phase: str = None
    last_phase_level: int = 0
    last_phase_minute: int = -99
    pressure_team: str = None
    pressure_streak: int = 0
    previous_event_type: str = None
    late_game: bool = False
    defensive_plan_active: dict = field(default_factory=lambda: {'home': None, 'away': None})

    def as_dict(self):
        return asdict(self)


def build_segments(narrator):
    """Segment-Log der Erzählung aus Fenstern + erzählten Zeilen."""
    ctx = narrator.ctx
    out = []
    windows = narrator.windows or []
    beats = narrator.beats
    for w in windows:
        a, b = w['from'], w['to']
        in_w = [l for l in beats if a < l.minute <= b]
        chances = {'home': 0, 'away': 0}
        chain = []
        seen_seq = set()
        for l in in_w:
            if l.cls in ('shot', 'goal') and l.team:
                chances[l.team] += 1
            if l.cls in ('goal', 'shot', 'corner', 'card', 'sub', 'phase', 'gk_clear') and l.seq not in seen_seq:
                seen_seq.add(l.seq)
                tag = {'goal': 'goal', 'shot': 'chance', 'corner': 'corner', 'card': 'card', 'sub': 'sub', 'phase': 'phase', 'gk_clear': 'chance'}[l.cls]
                chain.append(f"{l.clock} {ctx.team(l.team).short if l.team else ''} {tag}" + (f":{l.payload.get('goal_ctx')}" if l.cls == 'goal' and l.payload.get('goal_ctx') else '') + (f":{l.payload.get('phase')}" if l.cls == 'phase' else ''))
        phase_lines = [l for l in in_w if l.cls == 'phase' and l.payload.get('phase') not in ('pressing_note',)]
        dominant = phase_lines[-1].team if phase_lines and phase_lines[-1].team else None
        intensity = max([l.payload.get('phase_level', 0) for l in phase_lines] or [0])
        phase = phase_lines[-1].payload.get('phase') if phase_lines else ('balanced' if chances['home'] == chances['away'] else 'lean')
        goals = [l for l in in_w if l.cls == 'goal']
        narrative = ' → '.join([f"{ctx.team(l.team).short} {l.payload.get('score')} ({l.payload.get('goal_ctx')})" for l in goals]) or None
        out.append({'from': a, 'to': b, 'dominant': dominant, 'phase': phase, 'intensity': intensity,
                    'chances': chances, 'events': len(seen_seq), 'chain': chain, 'narrative': narrative,
                    'score_at_end': narrator.score_history.get(b, None), 'plans': w.get('plans')})
    return out
