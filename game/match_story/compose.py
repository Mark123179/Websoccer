"""Komposition: aus den Beats einer Sequenz werden Textzeilen.

Beats bleiben vollständig erhalten (für 2D). Der Text fasst zusammen:
  Zeile A  = Start + Aufbau in einem Satz            (Ebene 1–2)
  Zeile B  = gefährlicher Einstieg, falls vorhanden  (Ebene 3)
  Zeile C  = Ende: Abschluss / Abbruch / Standard    (Ebene 3–5)
Standards und Karten werden mit ihrer Vorbereitung zu einer Zeile verschmolzen.
"""
from .model import Line

START_KINDS = {'ballgewinn', 'pressing_ballgewinn', 'abgefangen', 'einwurf', 'abstoss', 'nachsetzen'}
BUILD_KINDS = {'aufbau_pass', 'langer_ball', 'ballzirkulation', 'verlagerung', 'steilpass', 'doppelpass', 'zielspieler', 'tiefenlauf', 'flanke', 'dribbling'}
ENTRY_KINDS = {'steilpass', 'tiefenlauf', 'flanke', 'dribbling', 'doppelpass', 'zielspieler'}   # Ebene 3, wenn letzter Aufbau-Beat
END_LEVEL = {
    'tor': 5, 'tor_kopfball': 5, 'tor_konter': 5, 'eigentor': 5, 'elfmeter_tor': 5,
    'schuss_gehalten': 4, 'schuss_gehalten_ecke': 4, 'schuss_pfosten': 4, 'ecke_kopfball_gehalten': 4, 'freistoss_direkt_gehalten': 4,
    'schuss_vorbei': 3, 'schuss_geblockt': 3, 'ecke_kopfball_vorbei': 3, 'ecke_kopfball_geblockt': 3, 'torwart_klaert': 3,
    'freistoss_direkt_vorbei': 3, 'freistoss_direkt_mauer': 3, 'freistoss_flanke_kopfball_vorbei': 3,
}


def _merge(beats, kind, cls, level, visible=True, first_wins=False, silent_beats=()):
    """Neue Textzeile aus mehreren Beats. silent_beats: vorangestellte Beats ohne eigenen Text (nur Bild)."""
    beats = list(silent_beats) + list(beats)
    first = beats[len(silent_beats)]
    ln = Line(seq=first.seq, beat=first.beat, minute=first.minute, added=first.added, team=first.team,
              kind=kind, cls=cls, visible=visible, actors={}, tags=list(first.tags))
    ln.payload = {'level': level, 'beats': [{'kind': b.kind, 'cls': b.cls, 'actors': {k: (v.id if v else None) for k, v in b.actors.items()},
                                             'actor_names': {k: (v.name if v else None) for k, v in b.actors.items()},
                                             'payload': {k: v for k, v in b.payload.items() if k != 'elastic'},
                                             'elastic': bool(b.payload.get('elastic'))} for b in beats]}
    ln.payload['elastic'] = all(b.payload.get('elastic') for b in beats)
    # Akteure: Vereinigung; spätere Beats überschreiben (oder der erste gewinnt)
    for b in (reversed(beats) if first_wins else beats):
        for k, v in b.actors.items():
            if v is not None:
                ln.actors[k] = v
    ln.payload['silent'] = len(silent_beats)
    # bei Standards zählt der Ausgangs-Beat (Bild), Kopie wichtiger Payload-Felder
    for key in ('score', 'zone', 'on_target', 'card', 'from_corner', 'in', 'out', 'round', 'tally', 'plan', 'label', 'goal_ctx', 'minute', 'referee', 'weather', 'changes', 'teams', 'shots', 'corners', 'possession', 'zones', 'phase', 'side'):
        for b in beats:
            if key in b.payload and key not in ln.payload:
                ln.payload[key] = b.payload[key]
    if len(beats) == 1:
        for k, v in beats[0].payload.items():
            if k != 'elastic':
                ln.payload.setdefault(k, v)
    ln.payload['n_beats'] = len(beats)
    return ln


def compose(beats_all):
    """beats_all: Liste Beat-Lines (Ausgabe des Erzählers). Rückgabe: Textzeilen."""
    by_seq = {}
    order = []
    for b in beats_all:
        if b.seq not in by_seq:
            order.append(b.seq)
        by_seq.setdefault(b.seq, []).append(b)
    out = []
    for seq in order:
        beats = by_seq[seq]
        kinds = [b.kind for b in beats]
        # Rahmen/Analyse/Wechsel/Phase: 1 Beat = 1 Zeile
        if all(b.cls in ('analysis', 'kickoff', 'halftime', 'fulltime', 'sub', 'injury', 'phase', 'shootout_start', 'shootout_kick') for b in beats):
            for b in beats:
                lvl = 1 if b.cls in ('phase', 'analysis') else 2
                out.append(_merge([b], b.kind, b.cls, lvl, visible=b.visible))
            continue
        i = 0
        # A: Start + Aufbau
        pre = []
        while i < len(beats) and (beats[i].kind in START_KINDS or beats[i].kind in BUILD_KINDS):
            pre.append(beats[i]); i += 1
        entry = None
        if pre and pre[-1].kind in ENTRY_KINDS and len(pre) >= 2:
            entry = pre.pop()
        carry = []
        # Flanke als Einstieg vor "Flanke abgeblockt -> Ecke": kein doppelter Satz
        if entry and entry.kind == 'flanke' and i < len(beats) and beats[i].kind == 'abbruch_aus_ecke':
            pre.append(entry); entry = None
            if len(pre) > 1:
                carry = [pre.pop()]
        if pre and len(pre) == 1 and pre[0].kind in ('einwurf', 'abstoss'):
            carry = pre + carry    # nur Bild, kein eigener Satz
        elif pre:
            silent = []
            while len(pre) > 2:
                silent.append(pre.pop(0))
            two_named = {'verlagerung', 'steilpass', 'doppelpass', 'tiefenlauf', 'zielspieler', 'dribbling', 'ballgewinn', 'pressing_ballgewinn', 'abgefangen'}
            if len(pre) == 2 and pre[0].kind in two_named and pre[1].kind in two_named and pre[1].kind not in ('ballgewinn', 'pressing_ballgewinn', 'abgefangen'):
                silent.append(pre.pop(0))
            out.append(_merge(pre, 'aufbau', 'buildup', 2 if len(pre) > 1 else 1, silent_beats=silent))
        if entry:
            out.append(_merge([entry], 'einstieg_' + entry.kind, 'buildup', 3, silent_beats=carry)); carry = []
        # C: Rest — Ende + Verkettungen
        while i < len(beats):
            b = beats[i]
            grp = [b]
            nachsetzen = False
            if b.kind == 'nachsetzen' and i + 1 < len(beats):
                nachsetzen = True
                grp = [b, beats[i + 1]]
                b = beats[i + 1]
                i += 1
            # Foul + Karte verschmelzen, Foul + kurzer Freistoß verschmelzen
            fw = False
            if b.kind == 'foul' and i + 1 < len(beats) and beats[i + 1].cls == 'card':
                grp.append(beats[i + 1]); fw = True
            elif b.kind == 'foul' and i + 1 < len(beats) and beats[i + 1].kind == 'freistoss_kurz':
                grp.append(beats[i + 1]); fw = True
            fw = fw or nachsetzen
            # Tor + Anstoß verschmelzen
            if b.cls == 'goal' and i + 1 < len(beats) and beats[i + 1].kind == 'anstoss_nach_tor':
                grp.append(beats[i + 1])
            # Ecke: Ausführung + Ausgang verschmelzen
            if b.kind == 'ecke_ausfuehrung' and i + 1 < len(beats):
                grp.append(beats[i + 1])
                if beats[i + 1].cls == 'goal' and i + 2 < len(beats) and beats[i + 2].kind == 'anstoss_nach_tor':
                    grp.append(beats[i + 2])
            main = grp[-1] if b.kind == 'ecke_ausfuehrung' else b
            if b.kind == 'ecke_ausfuehrung' and grp[-1].kind == 'anstoss_nach_tor':
                main = grp[-2]
            level = END_LEVEL.get(main.kind, 2)
            if main.cls == 'goal': level = 5
            if main.cls == 'card': level = 3
            ln = _merge(grp, main.kind if b.kind != 'ecke_ausfuehrung' else 'ecke_' + main.kind.replace('ecke_', ''), main.cls, level, first_wins=fw, silent_beats=carry); carry = []
            if fw and grp[-1].kind == 'freistoss_kurz':
                ln.kind = 'foul_freistoss_kurz'; ln.actors['a'] = grp[-1].actors.get('p')
            if nachsetzen:
                ln.payload['nachsetzen'] = True
                if 'nachsetzen' not in ln.tags: ln.tags.append('nachsetzen')
                i -= 1
            if b.kind == 'ecke_ausfuehrung':
                ln.kind = main.kind
                ln.payload['corner_taker'] = b.actors.get('p').name if b.actors.get('p') else None
                ln.actors['a'] = b.actors.get('p') or ln.actors.get('a')
            out.append(ln)
            i += len(grp)
    return out
