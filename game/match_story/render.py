"""Ausgabe: Drehbuch (Markdown) und Ereignisliste (JSON)."""
import json

ICON_OLD = {'goal': '⚽', 'shot': '🎯', 'corner': '🚩', 'corner_end': '🚩', 'freekick': '🥅', 'card': '🟨', 'sub': '🔄',
        'injury': '🚑', 'analysis': '◇', 'kickoff': '▶', 'halftime': '⏸', 'fulltime': '⏹', 'abort': '·', 'buildup': ' ',
        'foul': '!', 'gk_clear': '🧤', 'kickoff_after_goal': '▶', 'shootout_start': '⚽', 'shootout_kick': '⚽'}

def _actor_names(l):
    return {k: (v.name if v else None) for k, v in l.actors.items()}

def to_json(result):
    lines = result['lines']
    return {
        'match_id': result['ctx'].match_id,
        'home': result['ctx'].home.name, 'away': result['ctx'].away.name,
        'final_score': f"{result['score']['home']}:{result['score']['away']}",
        'issues': result['issues'],
        'segments': result.get('segments'), 'state': result.get('state'),
        'lines': [{
            'seq': l.seq, 'beat': l.beat, 'minute': l.minute, 'added': l.added, 'clock': l.clock, 'team': l.team,
            'kind': l.kind, 'cls': l.cls, 'visible': l.visible and l.duration_s > 0, 'text': l.text,
            'actors': {k: (v.id if v else None) for k, v in l.actors.items()}, 'actor_names': _actor_names(l),
            'offset_s': l.offset_s, 'duration_s': l.duration_s, 'payload': {k: v for k, v in l.payload.items() if k != 'elastic'},
        } for l in lines],
    }

def to_markdown(result, plan_info=None):
    ctx = result['ctx']; lines = result['lines']
    h, a = ctx.home, ctx.away
    total = lines[-1].offset_s + lines[-1].duration_s if lines else 0
    vis = [l for l in lines if l.visible and l.duration_s > 0]
    seqs = len(set(l.seq for l in lines))
    out = [f"# Drehbuch: {h.name} – {a.name}  ({result['score']['home']}:{result['score']['away']})",
           f"Spiel-ID {ctx.match_id} · {ctx.match_type} · {ctx.decided_by}  ",
           f"Zeilen {len(lines)} · sichtbar {len(vis)} · Sequenzen {seqs} · Abspieldauer {total/60:.1f} min  ",
           f"Kernzahlen: Schüsse {h.stats.get('shots')}/{a.stats.get('shots')} · aufs Tor {h.stats.get('shots_on_target')}/{a.stats.get('shots_on_target')} · Ecken {h.stats.get('corners')}/{a.stats.get('corners')} · Fouls {h.stats.get('fouls')}/{a.stats.get('fouls')} · Ballbesitz {h.stats.get('possession')}/{a.stats.get('possession')}",
           ""]
    if result['issues']:
        out.append("**Prüfhinweise:**")
        out += [f"- {i}" for i in result['issues']]
        out.append("")
    lv = {1: '·', 2: '··', 3: '▲', 4: '▲▲', 5: '★'}
    out.append("| Min | Team | Ebene | Text | Bild |")
    out.append("|---|---|---|---|---|")
    last_seq = None
    for l in lines:
        team = ctx.team(l.team).short if l.team else ''
        icon = lv.get(l.payload.get('level', 2), '') if l.cls not in ('analysis', 'phase') else '◇'
        nb = l.payload.get('n_beats', 1)
        pic = (f"{l.duration_s:.0f} s" + (f" ({nb} Beats)" if nb > 1 else "")) if (l.visible and l.duration_s > 0) else "—"
        sep = "" if l.seq == last_seq else "**"
        txt = l.text.replace('|', '/')
        out.append(f"| {l.clock} | {team} | {icon} | {sep}{txt}{sep} | {pic} |")
        last_seq = l.seq
    return "\n".join(out)
