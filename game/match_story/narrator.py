"""Erzähler: baut aus Kontext + Budget die Ereignisliste (Sequenzen aus Beats)."""
import random
from .model import Line
from .context import build_context
from .budget import distribute, from_segment_log, seg_index
from .actors import ActorPicker
from . import planner, render, phases
from .compose import compose
from .state import MatchState, build_segments
from .pools import de as pools

PLAN_LABEL = {
    'ausgewogen': 'ausgewogen', 'aggressiv_risiko': 'aggressiv mit Risiko', 'schlussangriff': 'Schlussangriff',
    'kontrolle_ballbesitz': 'Kontrolle über Ballbesitz', 'kompakt_sichern': 'kompakt absichern',
    'zeitspiel': 'Zeitspiel', 'unterzahl_kompakt': 'Unterzahl kompakt',
}
FOCUS_LABEL = {
    'ausgewogen': 'ausgewogen', 'fluegelspiel': 'über die Flügel', 'ueber_halbraeume': 'über die Halbräume',
    'durch_mitte': 'durch die Mitte', 'ueber_rechts': 'über rechts', 'ueber_links': 'über links',
    'flanke_kopfball': 'mit Flanken auf Kopfballstarke',
}
UMSCHALT_LABEL = {'konter': 'auf Konter', 'ausgewogen': 'ausgewogen im Umschalten', 'ballbesitz': 'auf Ballbesitz'}
PRESSING_LABEL = {'passiv': 'passiv', 'normal': 'mittleres Pressing', 'intensiv': 'intensives Pressing', 'hoch': 'hohes Pressing'}
DECKUNG_LABEL = {'raum': 'Raumdeckung', 'mann': 'Manndeckung', 'hybrid': 'gemischte Deckung'}


class Narrator:
    def __init__(self, export, rng=None):
        self.ctx = build_context(export)
        self.rng = rng or random.Random(self.ctx.match_id * 7919 + 17)
        self.pick = ActorPicker(self.rng)
        self.lines = []
        self.seq_no = 0
        self.issues = []
        self.score = {'home': 0, 'away': 0}
        self.zone_left = {s: dict(left=self.ctx.team(s).stats.get('attacks_left', 0),
                                  center=self.ctx.team(s).stats.get('attacks_center', 0),
                                  right=self.ctx.team(s).stats.get('attacks_right', 0)) for s in ('home', 'away')}
        self.pressing_left = {s: self.ctx.team(s).stats.get('pressing_ball_wins', 0) for s in ('home', 'away')}
        self.windows = []
        self.state = MatchState()
        self.score_history = {}
        self.last_attack = None      # (side, minute)
        self.conceded_at = {'home': -99, 'away': -99}
        self.scored_at = {'home': -99, 'away': -99}
        self.answered = {'home': True, 'away': True}
        self.chances = []            # (minute, side) sichtbare Abschlüsse/Ecken
        self.attacks = []            # (minute, side) alle erzählten Angriffe
        self.streak = {'home': 0, 'away': 0}
        self.was_behind = {'home': False, 'away': False}
        self.turned = {'home': False, 'away': False}

    # ---------- Hilfen ----------
    def _new_seq(self):
        self.seq_no += 1
        return self.seq_no

    def _line(self, seq, beat, minute, kind, cls, team=None, visible=True, actors=None, payload=None, tags=None, added=0):
        ln = Line(seq=seq, beat=beat, minute=minute, added=added, team=team, kind=kind, cls=cls, visible=visible,
                  actors=actors or {}, payload=payload or {}, tags=list(tags or []))
        self.lines.append(ln)
        return ln

    def _zone(self, side):
        z = self.zone_left[side]
        total = sum(max(v, 0) for v in z.values())
        if total <= 0:
            return self.rng.choice(['left', 'center', 'right'])
        pick = self.rng.choices(list(z.keys()), weights=[max(v, 0) + 0.01 for v in z.values()])[0]
        z[pick] -= 1
        return pick

    def _tags(self, side, zone):
        t = self.ctx.team(side).tactic
        o = self.ctx.opp(side).tactic
        tags = {'zone_' + zone, 'umschalten_' + t.umschalten, 'fokus_' + t.attack_focus,
                'gegner_zweikampf_' + o.zweikampf, 'gegner_deckung_' + o.deckung,
                'aufbau_' + t.buildup_defense, 'mittelfeld_' + t.buildup_midfield, 'angriff_' + t.buildup_attack}
        if self.score[side] > self.score['home' if side == 'away' else 'away']: tags.add('fuehrung')
        elif self.score[side] < self.score['home' if side == 'away' else 'away']: tags.add('rueckstand')
        return tags

    def _state_tags(self, side, minute, seq=None):
        tags = set()
        if self.windows:
            w = phases.window_for(self.windows, minute)
            tags |= w['tags']
            if w['side'] == side: tags.add('phase_eigene')
        opp = 'away' if side == 'home' else 'home'
        opp_chance_between = any(c[1] == opp and self.last_attack and c[0] >= self.last_attack[1] for c in self.chances[-3:])
        if not self.answered[side] and minute - self.conceded_at[side] <= 5:
            tags.add('antwort'); self.answered[side] = True
            self.streak[side] = 0
        elif (self.last_attack and self.last_attack[0] == side and minute - self.last_attack[1] <= 3
              and not opp_chance_between):
            self.streak[side] += 1
            if self.streak[side] == 1: tags.add('nachsetzen')
            elif self.streak[side] == 3 and seq is not None and not any(
                    l.cls == 'phase' and l.team == side and minute - 3 <= l.minute <= minute for l in self.lines) and not any(
                    a['side'] == side and a['plan'] in ('kompakt_sichern', 'zeitspiel', 'kontrolle_ballbesitz') and minute - 1 <= a['minute'] <= minute + 3
                    for a in self.ctx.plan_activations):
                ln = self._line(seq - 0.5, 1, minute, 'phase', 'phase', side, visible=False)
                ln.payload = {'phase': 'streak', 'side': side, 'phase_level': 1,
                              'after_goal': minute - self.scored_at[side] <= 8}
        else:
            self.streak[side] = 0
        self.streak[opp] = 0
        self.last_attack = (side, minute)
        self.state.pressure_team, self.state.pressure_streak = (side, self.streak[side]) if self.streak[side] else (None, 0)
        return tags

    def _register_chance(self, side, minute):
        self.chances.append((minute, side))

    def _register_attack(self, side, minute):
        self.attacks.append((minute, side))

    def _goal_context(self, side, minute):
        """Warum jetzt? Klassifikation eines Tores aus dem Spielverlauf (vor dem Hochzählen des Spielstands)."""
        opp = 'away' if side == 'home' else 'home'
        before = (self.score[side], self.score[opp])
        after = (before[0] + 1, before[1])
        recent = [c for c in self.chances if minute - 8 <= c[0] < minute]
        own = len([c for c in recent if c[1] == side]); other = len([c for c in recent if c[1] == opp])
        ratt = [c for c in self.attacks if minute - 8 <= c[0] < minute]
        own_att = len([c for c in ratt if c[1] == side]); other_att = len([c for c in ratt if c[1] == opp])
        recent6 = [c for c in self.chances if minute - 6 <= c[0] < minute]
        other6 = len([c for c in recent6 if c[1] == opp]); own6 = len([c for c in recent6 if c[1] == side])
        late = minute >= 80
        if minute - self.conceded_at[side] <= 5: return 'antwort'
        if minute - self.scored_at[side] <= 4: return 'doppelschlag'
        if self.was_behind[side] and after[0] > after[1] and not self.turned[side]:
            self.turned[side] = True; return 'gedreht'
        if before[1] - before[0] >= 2: return 'anschluss'
        if late and after[0] == after[1]: return 'spaeter_ausgleich'
        if late and after[0] > after[1] and other6 >= 2 and own6 <= 1: return 'zurueckgeschlagen'
        if late and after[0] > after[1]: return 'spaete_fuehrung'
        w = phases.window_for(self.windows, minute) if self.windows else None
        if after[0] > after[1] and ((w and w['side'] == opp and w['phase'] in ('druck', 'schlussoffensive')) or (other6 >= 2 and own6 == 0)):
            return 'gegen_drangphase'
        if other >= 2 and own == 0 and other_att > own_att: return 'aus_dem_nichts'
        if own >= 2 or (own_att >= 3 and own_att >= 2 * max(other_att, 1)): return 'nach_druck'
        return 'normal'

    def _after_goal(self, side, minute, gctx=None):
        opp = 'away' if side == 'home' else 'home'
        st = self.state
        st.score = dict(self.score); st.last_goal_team = side; st.last_goal_minute = minute; st.last_goal_ctx = gctx
        st.unanswered_goals = st.unanswered_goals + 1 if st.last_goal_team == side and st.comeback_chain and st.comeback_chain[-1][0] == side else 1
        st.response_pending = opp
        st.comeback_chain.append((side, f"{self.score['home']}:{self.score['away']}", minute))
        st.previous_event_type = 'goal'
        self.scored_at[side] = minute
        self.conceded_at[opp] = minute; self.answered[opp] = False
        if self.score[side] > self.score[opp]: self.was_behind[opp] = True
        self.streak = {'home': 0, 'away': 0}
        self._register_chance(side, minute)

    # ---------- Sequenz A: Angriff ----------
    def _buildup_plan(self, side, zone, finish_kind):
        t = self.ctx.team(side).tactic
        beats = []
        # Start
        start_opts = ['ballgewinn'] * 4 + ['abgefangen'] * 3 + ['einwurf', 'abstoss']
        if self.pressing_left[side] > 0 and t.pressing_level in ('intensiv', 'hoch'):
            start_opts += ['pressing_ballgewinn'] * 3
        elif self.pressing_left[side] > 0:
            start_opts += ['pressing_ballgewinn']
        if t.umschalten == 'konter':
            start_opts += ['ballgewinn'] * 3
        start = self.rng.choice(start_opts)
        if start == 'pressing_ballgewinn':
            self.pressing_left[side] -= 1
        beats.append(start)
        # Anzahl Aufbau-Beats
        n = 1
        if t.buildup_midfield == 'geduldig' or t.umschalten == 'ballbesitz': n += 1
        if t.umschalten == 'konter' or t.buildup_attack == 'frueher_abschluss': n -= 1
        if t.buildup_defense in ('lange_baelle', 'direkt_vorne'): n -= 1
        n += self.rng.choice([-1, 0, 0, 1])
        n = max(0, min(3, n))
        # Beat-Typen nach Taktik
        stage_def = {'lange_baelle': 'langer_ball', 'direkt_vorne': 'steilpass', 'aus_abwehr': 'aufbau_pass', 'standard': None}[t.buildup_defense]
        stage_mid = {'geduldig': 'ballzirkulation', 'vertikal': 'steilpass', 'seiten_verlagern': 'verlagerung', 'standard': None}[t.buildup_midfield]
        stage_att = {'kombinieren': 'doppelpass', 'tiefenlaeufe': 'tiefenlauf', 'flanken_suchen': 'flanke',
                     'zielspieler_suchen': 'zielspieler', 'frueher_abschluss': None, 'standard': None}[t.buildup_attack]
        wing = zone in ('left', 'right')
        if wing and t.attack_focus in ('fluegelspiel', 'ueber_links', 'ueber_rechts', 'flanke_kopfball'):
            stage_att = stage_att or 'flanke'
        generic = ['aufbau_pass', 'verlagerung', 'steilpass', 'dribbling', 'doppelpass', 'langer_ball']
        if wing: generic += ['flanke', 'dribbling']
        else: generic += ['steilpass', 'doppelpass']
        chosen = []
        stages = [stage_def, stage_mid, stage_att]
        for i in range(n):
            st = stages[i] if i < 3 else None
            if st is None or (i == 0 and n == 1 and stage_att):
                st = stage_att if (i == n - 1 and stage_att) else self.rng.choice(generic)
            chosen.append(st)
        dedup = []
        for c in chosen:
            if c not in dedup:
                dedup.append(c)
        chosen = dedup
        # Kopfball-Abschlüsse brauchen eine Flanke davor
        if finish_kind in ('kopfball',) and 'flanke' not in chosen:
            chosen = (chosen[:-1] if chosen else []) + ['flanke']
        beats += chosen
        return beats

    def _attack(self, side, minute, zone, ending, goal=None, shot_on_target=False, card=None, chain_depth=0, added=0):
        """Eine A-Sequenz. `ending` ∈ schuss_tor|schuss_gehalten|schuss_vorbei|schuss_pfosten|schuss_geblockt|
        abbruch_fehlpass|abbruch_zweikampf|abbruch_abseits|abbruch_aus|abbruch_foul|torwart_klaert.
        Gibt zurück, ob am Ende eine Ecke folgt (Verkettung)."""
        ctx = self.ctx
        team, opp = ctx.team(side), ctx.opp(side)
        seq = self._new_seq()
        tags = self._tags(side, zone) | self._state_tags(side, minute, seq)
        self._register_attack(side, minute)
        finish_style = 'kopfball' if (goal and goal.get('goal_type') == 'corner') else 'schuss'
        plan = self._buildup_plan(side, zone, finish_style)
        excl = set()
        last_player = None
        beat_no = 0
        # Schütze/Vorlagengeber sind Engine-Fakten
        shooter = None
        assister = None
        if goal:
            shooter = ctx.player(goal.get('scorer_id'))
            if shooter is None or not shooter.on_pitch(minute):
                shooter = self.pick.pick(team, minute, 'abschluss', good=True, prefer_fresh=False)
                self.issues.append(f"{minute}': Engine nennt {goal.get('scorer_name')} als Torschütze, der nicht auf dem Platz ist – im Text ersetzt durch {shooter.name if shooter else '?'} (Engine-Ticket)")
            if goal.get('assister_id'):
                assister = ctx.player(goal['assister_id'])
        elif ending.startswith('schuss'):
            good = True if shot_on_target or ending == 'schuss_pfosten' else None
            shooter = self.pick.pick(team, minute, 'abschluss', good=good, prefer_fresh=False)
        if shooter: excl.add(shooter.id)
        if assister: excl.add(assister.id)

        for kind in plan:
            beat_no += 1
            actors = {}
            if kind in ('ballgewinn', 'pressing_ballgewinn'):
                role = 'pressing' if kind == 'pressing_ballgewinn' else 'zweikampf_def'
                p = self.pick.pick(team, minute, role, good=True, exclude=excl)
                o = self.pick.opponent(ctx, p, minute, role='zweikampf_off' if role == 'pressing' else 'zweikampf_off', good=False) if p else None
                actors = {'p': p, 'o': o}
            elif kind == 'abgefangen':
                p = self.pick.pick(team, minute, 'verteidiger', good=True, exclude=excl)
                o = self.pick.pick(opp, minute, 'kreativ', good=False)
                actors = {'p': p, 'o': o}
            elif kind == 'einwurf':
                p = self.pick.pick(team, minute, 'verteidiger', exclude=excl); actors = {'p': p}
            elif kind == 'abstoss':
                p = team.keeper(minute); actors = {'p': p}
            elif kind in ('aufbau_pass', 'langer_ball', 'ballzirkulation'):
                p = self.pick.pick(team, minute, 'aufbau', exclude=excl); actors = {'p': p}
            elif kind in ('verlagerung', 'steilpass', 'doppelpass', 'zielspieler', 'tiefenlauf'):
                p = self.pick.pick(team, minute, 'kreativ', good=True, exclude=excl)
                # Empfänger: bei letztem Beat vor dem Abschluss der Schütze selbst
                r = shooter if (beat_no == len(plan) and shooter and kind in ('steilpass', 'tiefenlauf', 'doppelpass', 'zielspieler')) else \
                    self.pick.pick(team, minute, 'abschluss' if kind in ('zielspieler', 'tiefenlauf') else 'kreativ', exclude=excl | ({p.id} if p else set()))
                actors = {'p': p, 'r': r}
                if r and r is not shooter: excl.add(r.id)
            elif kind == 'flanke':
                p = assister if (assister and beat_no == len(plan)) else self.pick.pick(team, minute, 'fluegel', side=zone if zone != 'center' else None, exclude=excl)
                r = shooter or self.pick.pick(team, minute, 'kopfball', exclude=excl | ({p.id} if p else set()), prefer_fresh=False)
                actors = {'p': p, 'r': r}
            elif kind == 'dribbling':
                p = self.pick.pick(team, minute, 'kreativ', good=True, exclude=excl)
                o = self.pick.opponent(ctx, p, minute, good=False) if p else None
                actors = {'p': p, 'o': o}
            if actors.get('p'):
                if actors['p'].group != 'GK':
                    last_player = actors['p']
                excl.add(actors['p'].id)
            ln = self._line(seq, beat_no, minute, kind, 'buildup', side, actors=actors, tags=tags, added=added)
            ln.payload = {'zone': zone, 'elastic': True}

        # Abschluss / Abbruch
        beat_no += 1
        follow_corner = False
        keeper = opp.keeper(minute)
        if ending == 'schuss_tor':
            gctx = self._goal_context(side, minute)
            self.score[side] += 1
            self._after_goal(side, minute, gctx)
            actors = {'p': shooter, 'a': assister or last_player, 'k': keeper}
            kind = 'tor_kopfball' if finish_style == 'kopfball' else ('tor_konter' if 'umschalten_konter' in tags and plan[0] in ('ballgewinn', 'pressing_ballgewinn') else 'tor')
            if goal and goal.get('goal_type') == 'own_goal': kind = 'eigentor'
            if goal and goal.get('goal_type') == 'penalty': kind = 'elfmeter_tor'
            ln = self._line(seq, beat_no, minute, kind, 'goal', side, actors=actors, tags=tags, added=added)
            ln.payload = {'zone': zone, 'score': f"{self.score['home']}:{self.score['away']}", 'assist': bool(assister),
                          'scorer_id': shooter.id if shooter else None, 'assister_id': assister.id if assister else None,
                          'goal_ctx': gctx, 'minute': minute}
            ln.tags.append('tor_' + gctx)
            self._line(seq, beat_no + 1, minute, 'anstoss_nach_tor', 'kickoff_after_goal', 'away' if side == 'home' else 'home',
                       actors={}, tags=tags, added=added).payload = {'elastic': False}
        elif ending in ('schuss_gehalten', 'schuss_vorbei', 'schuss_pfosten', 'schuss_geblockt'):
            actors = {'p': shooter, 'k': keeper, 'a': last_player}
            if ending == 'schuss_geblockt':
                actors['o'] = self.pick.pick(opp, minute, 'block', good=True, prefer_fresh=False)
            ln = self._line(seq, beat_no, minute, ending, 'shot', side, actors=actors, tags=tags, added=added)
            ln.payload = {'zone': zone, 'on_target': ending == 'schuss_gehalten'}
            self._register_chance(side, minute)
            if ending == 'schuss_geblockt' and chain_depth < 3:
                follow_corner = True
            if ending == 'schuss_gehalten' and self.rng.random() < 0.25 and chain_depth < 3:
                follow_corner = True
                ln.kind = 'schuss_gehalten_ecke'
        elif ending == 'torwart_klaert':
            actors = {'p': shooter or last_player, 'k': keeper}
            self._line(seq, beat_no, minute, 'torwart_klaert', 'gk_clear', side, actors=actors, tags=tags, added=added)
        elif ending == 'abbruch_foul':
            p = last_player or self.pick.pick(team, minute, 'kreativ', exclude=excl)
            if card:
                o = ctx.player(card.get('player_id'))
                if o is None or not o.on_pitch(minute):
                    o = self.pick.opponent(ctx, p, minute, good=False)
                    self.issues.append(f"{minute}': Engine gibt {card.get('player_name')} eine Karte, der nicht auf dem Platz ist – im Text ersetzt durch {o.name if o else '?'} (Engine-Ticket)")
            else:
                o = self.pick.opponent(ctx, p, minute, good=False) if p else None
            actors = {'p': p, 'o': o}
            ln = self._line(seq, beat_no, minute, 'foul', 'foul', side, actors=actors, tags=tags, added=added)
            ln.payload = {'zone': zone}
            if card:
                ct = card.get('card_type', 'yellow')
                kind = {'yellow': 'gelb', 'yellow_red': 'gelbrot', 'red': 'rot'}.get(ct, 'gelb')
                self._line(seq, beat_no + 1, minute, kind, 'card', opp.side, actors={'p': o}, tags=tags, added=added).payload = {'card': ct}
        else:
            # Abbrüche
            if ending == 'abbruch_zweikampf':
                p = last_player or self.pick.pick(team, minute, 'zweikampf_off', good=False, exclude=excl)
                o = self.pick.opponent(ctx, p, minute, good=True) if p else None
                actors = {'p': p, 'o': o}
            elif ending == 'abbruch_fehlpass':
                p = last_player or self.pick.pick(team, minute, 'kreativ', good=False, exclude=excl)
                o = self.pick.pick(opp, minute, 'verteidiger', good=True, prefer_fresh=False)
                actors = {'p': p, 'o': o}
            elif ending == 'abbruch_abseits':
                p = shooter or self.pick.pick(team, minute, 'abschluss', exclude=excl)
                actors = {'p': p, 'a': last_player}
            elif ending == 'abbruch_aus_ecke':
                p = last_player or self.pick.pick(team, minute, 'fluegel', side=zone if zone != 'center' else None, exclude=excl)
                o = self.pick.pick(opp, minute, 'block', good=True, prefer_fresh=False)
                actors = {'p': p, 'o': o}
            else:  # abbruch_aus
                p = last_player or self.pick.pick(team, minute, 'kreativ', good=False, exclude=excl)
                actors = {'p': p}
            ln = self._line(seq, beat_no, minute, ending, 'abort', side, actors=actors, tags=tags, added=added)
            ln.payload = {'zone': zone}
        return seq, follow_corner

    def _continue(self, seq, side, minute, fouls_left):
        """Zweiter Ball: das angreifende Team bleibt dran, endet mit Foul (Freistoß) oder Abbruch."""
        ctx = self.ctx
        team, opp = ctx.team(side), ctx.opp(side)
        tags = self._tags(side, 'center') | {'nachsetzen'}
        b = len([l for l in self.lines if l.seq == seq]) + 1
        p = self.pick.pick(team, minute, 'mittelfeld', good=True)
        self._line(seq, b, minute, 'nachsetzen', 'buildup', side, actors={'p': p}, tags=tags).payload = {'elastic': True}
        fouling = opp.side
        if fouls_left.get(fouling, 0) > 0 and self.rng.random() < 0.6:
            fouls_left[fouling] -= 1
            o = self.pick.opponent(ctx, p, minute, good=False)
            self._line(seq, b + 1, minute, 'foul', 'foul', side, actors={'p': p, 'o': o}, tags=tags)
            taker = self.pick.taker(team, minute, 'free_kick', 'kreativ')
            self._line(seq, b + 2, minute, 'freistoss_kurz', 'freekick', side, actors={'p': taker}, tags=tags)
        else:
            o = self.pick.opponent(ctx, p, minute, good=True)
            self._line(seq, b + 1, minute, 'abbruch_zweikampf', 'abort', side, actors={'p': p, 'o': o}, tags=tags)

    # ---------- Sequenz B: Standards ----------
    def _corner(self, side, minute, outcome, goal=None, near_miss=None, seq=None, beat_start=0, chain_depth=0, added=0):
        ctx = self.ctx
        team, opp = ctx.team(side), ctx.opp(side)
        seq = seq or self._new_seq()
        tags = self._tags(side, 'center') | self._state_tags(side, minute, seq)
        taker = self.pick.taker(team, minute, 'corner', 'kreativ')
        keeper = opp.keeper(minute)
        b = beat_start + 1
        self._line(seq, b, minute, 'ecke_ausfuehrung', 'corner', side, actors={'p': taker}, tags=tags, added=added).payload = {'elastic': False}
        b += 1
        no_taker = {taker.id} if taker else set()
        follow = False
        if goal:
            scorer = ctx.player(goal['scorer_id'])
            if scorer is None or not scorer.on_pitch(minute):
                scorer = self.pick.pick(team, minute, 'kopfball', good=True, exclude=no_taker, prefer_fresh=False)
                self.issues.append(f"{minute}': Engine nennt {goal.get('scorer_name')} als Eckentor-Schütze, der nicht auf dem Platz ist – im Text ersetzt durch {scorer.name if scorer else '?'} (Engine-Ticket)")
            gctx = self._goal_context(side, minute)
            self.score[side] += 1
            self._after_goal(side, minute, gctx)
            ln = self._line(seq, b, minute, 'tor_kopfball', 'goal', side, actors={'p': scorer, 'a': taker, 'k': keeper}, tags=tags + ['tor_' + gctx] if isinstance(tags, list) else list(tags) + ['tor_' + gctx], added=added)
            ln.payload = {'score': f"{self.score['home']}:{self.score['away']}", 'from_corner': True, 'scorer_id': scorer.id, 'assister_id': taker.id if taker else None, 'goal_ctx': gctx, 'minute': minute}
            self._line(seq, b + 1, minute, 'anstoss_nach_tor', 'kickoff_after_goal', opp.side, tags=tags, added=added)
            return seq, False
        if outcome.startswith('kopfball'):
            self._register_chance(side, minute)
        if outcome == 'kopfball_vorbei':
            header = ctx.player(near_miss.get('player_id')) if near_miss and near_miss.get('player_id') else None
            if header is None and near_miss and near_miss.get('player_name'):
                header = next((p for p in team.on_pitch(minute) if p.name == near_miss['player_name']), None)
            if header is not None and header.group == 'GK':
                self.issues.append(f"{minute}': Engine nennt Torwart {header.name} als Kopfballspieler nach Ecke — ersetzt (Engine-Ticket)")
                header = None
            header = header or self.pick.pick(team, minute, 'kopfball', exclude=no_taker, prefer_fresh=False)
            self._line(seq, b, minute, 'ecke_kopfball_vorbei', 'shot', side, actors={'p': header, 'a': taker, 'k': keeper}, tags=tags, added=added).payload = {'on_target': False}
        elif outcome == 'kopfball_gehalten':
            header = self.pick.pick(team, minute, 'kopfball', good=True, exclude=no_taker, prefer_fresh=False)
            ln = self._line(seq, b, minute, 'ecke_kopfball_gehalten', 'shot', side, actors={'p': header, 'a': taker, 'k': keeper}, tags=tags, added=added)
            ln.payload = {'on_target': True}
            if chain_depth < 2 and self.rng.random() < 0.4:
                follow = True
        elif outcome == 'kopfball_geblockt':
            header = self.pick.pick(team, minute, 'kopfball', exclude=no_taker, prefer_fresh=False)
            blocker = self.pick.pick(opp, minute, 'block', good=True, prefer_fresh=False)
            self._line(seq, b, minute, 'ecke_kopfball_geblockt', 'shot', side, actors={'p': header, 'a': taker, 'o': blocker}, tags=tags, added=added).payload = {'on_target': False}
            follow = chain_depth < 2
        elif outcome == 'gefangen':
            self._line(seq, b, minute, 'ecke_gefangen', 'corner_end', side, actors={'k': keeper, 'a': taker}, tags=tags, added=added)
        elif outcome == 'gefaustet':
            self._line(seq, b, minute, 'ecke_gefaustet', 'corner_end', side, actors={'k': keeper, 'a': taker, 'p': self.pick.pick(team, minute, 'kopfball', exclude=no_taker, prefer_fresh=False)}, tags=tags, added=added)
        elif outcome == 'geklaert':
            d = self.pick.pick(opp, minute, 'block', good=True, prefer_fresh=False)
            self._line(seq, b, minute, 'ecke_geklaert', 'corner_end', side, actors={'o': d, 'a': taker, 'p': self.pick.pick(team, minute, 'kopfball', exclude=no_taker, prefer_fresh=False)}, tags=tags, added=added)
        elif outcome == 'kurz':
            self._line(seq, b, minute, 'ecke_kurz', 'corner_end', side, actors={'p': taker, 'r': self.pick.pick(team, minute, 'kreativ', exclude={taker.id} if taker else (), prefer_fresh=False)}, tags=tags, added=added)
        return seq, follow

    def _freekick(self, side, minute, outcome, seq, beat_start, added=0):
        ctx = self.ctx
        team, opp = ctx.team(side), ctx.opp(side)
        tags = self._tags(side, 'center')
        taker = self.pick.taker(team, minute, 'free_kick', 'kreativ')
        keeper = opp.keeper(minute)
        b = beat_start + 1
        kind = {'direkt_gehalten': 'freistoss_direkt_gehalten', 'direkt_vorbei': 'freistoss_direkt_vorbei',
                'direkt_mauer': 'freistoss_direkt_mauer', 'flanke_geklaert': 'freistoss_flanke_geklaert',
                'flanke_kopfball_vorbei': 'freistoss_flanke_kopfball_vorbei', 'kurz': 'freistoss_kurz'}[outcome]
        actors = {'p': taker, 'k': keeper}
        if outcome.startswith('flanke'):
            actors['r'] = self.pick.pick(team, minute, 'kopfball', prefer_fresh=False)
            actors['o'] = self.pick.pick(opp, minute, 'block', good=True, prefer_fresh=False)
        cls = 'shot' if outcome.startswith('direkt') or outcome.endswith('vorbei') else 'freekick'
        ln = self._line(seq, b, minute, kind, cls, side, actors=actors, tags=tags, added=added)
        ln.payload = {'on_target': outcome == 'direkt_gehalten'}
        return outcome == 'direkt_mauer' and self.rng.random() < 0.5

    # ---------- Segment-Erzählung ----------
    def _narrate_segment(self, a, b, bud, fillers_target, half_added):
        ctx = self.ctx
        rng = self.rng
        items = []   # (minute, order, callable)
        counts = {s: dict(bud[s]) for s in ('home', 'away')}
        shots_left = {s: counts[s]['shots'] for s in counts}
        ot_left = {s: counts[s]['on_target'] for s in counts}
        corners_left = {s: counts[s]['corners'] for s in counts}
        fouls_left = {s: counts[s]['fouls'] for s in counts}
        used_minutes = set()

        def minute_in(lo=a + 1, hi=b):
            for _ in range(8):
                m = rng.randint(lo, hi)
                if m not in used_minutes:
                    used_minutes.add(m); return m
            return rng.randint(lo, hi)

        def attack_with_chain(side, minute, ending, **kw):
            depth = 0
            seq, follow = self._attack(side, minute, self._zone(side), ending, chain_depth=depth, **kw)
            if ending == 'schuss_geblockt' and not (follow and corners_left[side] > 0) and rng.random() < 0.4:
                follow = False
                self._continue(seq, side, minute, fouls_left)
            while follow and corners_left[side] > 0 and depth < 3:
                depth += 1
                corners_left[side] -= 1
                outcome = self._corner_outcome(side, shots_left, ot_left)
                seq, follow = self._corner(side, minute, outcome, seq=seq, beat_start=len([l for l in self.lines if l.seq == seq]), chain_depth=depth)
                if outcome.startswith('kopfball') and outcome != 'kopfball_geblockt':
                    pass

        # 1) Tore (Anker)
        for g in [g for g in ctx.goals if a < g['minute'] <= b]:
            side = g['team']
            shots_left[side] -= 1; ot_left[side] -= 1
            if g.get('goal_type') == 'corner':
                corners_left[side] -= 1
                items.append((g['minute'], 0, lambda side=side, g=g: self._corner(side, g['minute'], 'tor', goal=g)))
            else:
                items.append((g['minute'], 0, lambda side=side, g=g: self._attack(side, g['minute'], self._zone(side), 'schuss_tor', goal=g)))
            used_minutes.add(g['minute'])
        # 2) Karten (Anker) -> Foul-Sequenz des gefoulten Teams, danach Freistoß
        for c in [c for c in ctx.cards if a < c['minute'] <= b]:
            fouling = c.get('club_side', 'home')
            side = 'away' if fouling == 'home' else 'home'
            fouls_left[fouling] -= 1
            def _card_seq(side=side, c=c, fouling=fouling):
                seq, _ = self._attack(side, c['minute'], self._zone(side), 'abbruch_foul', card=c)
                beats = len([l for l in self.lines if l.seq == seq])
                outcome = self._freekick_outcome(side, shots_left, ot_left, dangerous=rng.random() < 0.45)
                if outcome:
                    self._freekick(side, c['minute'], outcome, seq, beats)
            items.append((c['minute'], 1, _card_seq))
            used_minutes.add(c['minute'])
        # 3) Ecken-Fastchancen (Anker)
        for nm in [n for n in ctx.near_misses if a < n['minute'] <= b]:
            side = nm['team']
            if corners_left[side] > 0: corners_left[side] -= 1
            if shots_left[side] > 0: shots_left[side] -= 1
            items.append((nm['minute'], 2, lambda side=side, nm=nm: self._corner(side, nm['minute'], 'kopfball_vorbei', near_miss=nm)))
            used_minutes.add(nm['minute'])
        # 4) Restliche Schüsse -> Angriffe mit Abschluss (verkettbar)
        for side in ('home', 'away'):
            while shots_left[side] > 0:
                shots_left[side] -= 1
                if ot_left[side] > 0:
                    ot_left[side] -= 1
                    ending = 'schuss_gehalten'
                    kw = {'shot_on_target': True}
                else:
                    ending = rng.choices(['schuss_vorbei', 'schuss_geblockt', 'schuss_pfosten'], weights=[5, 4, 1])[0]
                    kw = {}
                m = minute_in()
                items.append((m, 3, lambda side=side, m=m, ending=ending, kw=kw: attack_with_chain(side, m, ending, **kw)))
        # 5) Restliche Ecken -> Flanke geblockt -> Ecke
        for side in ('home', 'away'):
            while corners_left[side] > 0:
                corners_left[side] -= 1
                m = minute_in()
                def _corner_seq(side=side, m=m):
                    seq, _ = self._attack(side, m, self._zone(side), 'abbruch_aus_ecke')
                    outcome = self._corner_outcome(side, shots_left, ot_left)
                    self._corner(side, m, outcome, seq=seq, beat_start=len([l for l in self.lines if l.seq == seq]), chain_depth=1)
                items.append((m, 4, _corner_seq))
        # 6) Fouls ohne Karte: höchstens eines je Block als gefährlicher Freistoß, Rest stumm
        for side in ('home', 'away'):
            if fouls_left[side] > 0 and rng.random() < 0.35:
                fouled = 'away' if side == 'home' else 'home'
                fouls_left[side] -= 1
                m = minute_in()
                def _fk(fouled=fouled, m=m):
                    seq, _ = self._attack(fouled, m, self._zone(fouled), 'abbruch_foul')
                    beats = len([l for l in self.lines if l.seq == seq])
                    outcome = self._freekick_outcome(fouled, shots_left, ot_left, dangerous=True)
                    if outcome:
                        self._freekick(fouled, m, outcome, seq, beats)
                items.append((m, 5, _fk))
        # 7) Wechsel, Verletzungen, Plan-Aktivierungen (Anker)
        for side in ('home', 'away'):
            for s in [s for s in ctx.subs[side] if a < s['minute'] <= b]:
                items.append((s['minute'], -0.5, lambda side=side, s=s: self._sub(side, s)))
        for inj in [i for i in ctx.injuries if a < i.get('minute', -1) <= b]:
            items.append((inj['minute'], -0.5, lambda inj=inj: self._injury(inj)))
        for act in [x for x in ctx.plan_activations if a < x['minute'] <= b]:
            items.append((act['minute'], -1, lambda act=act: self._plan_line(act)))
        # 8) Füllsequenzen (Abbrüche) bis zur Zieldichte
        n_events = len([i for i in items if i[1] in (0, 2, 3, 4, 5)])
        for _ in range(max(0, fillers_target - n_events)):
            side = self._attacking_side()
            ending = rng.choices(['abbruch_zweikampf', 'abbruch_fehlpass', 'abbruch_abseits', 'abbruch_aus', 'torwart_klaert'],
                                 weights=[4, 4, 1, 2, 1])[0]
            m = minute_in()
            items.append((m, 7, lambda side=side, m=m, ending=ending: self._attack(side, m, self._zone(side), ending)))
        # Ausführen in Minutenreihenfolge
        for m, order, fn in sorted(items, key=lambda x: (x[0], x[1])):
            fn()
        # nicht erzählte Fouls werden stumm verbraucht (bleiben in der Statistik)

    def _attacking_side(self):
        h = self.ctx.home.stats.get('possession', 50) + self.ctx.home.attacks_total
        a = self.ctx.away.stats.get('possession', 50) + self.ctx.away.attacks_total
        return self.rng.choices(['home', 'away'], weights=[h, a])[0]

    def _corner_outcome(self, side, shots_left, ot_left):
        rng = self.rng
        # Kopfball aufs Tor nur, wenn noch Schüsse im Block sind (Kernzahl exakt)
        opts = ['gefangen', 'gefaustet', 'geklaert', 'geklaert', 'kurz']
        if shots_left[side] > 0:
            if ot_left[side] > 0 and rng.random() < 0.5:
                shots_left[side] -= 1; ot_left[side] -= 1
                return 'kopfball_gehalten'
            if rng.random() < 0.5:
                shots_left[side] -= 1
                return rng.choice(['kopfball_vorbei', 'kopfball_geblockt'])
        return rng.choice(opts)

    def _freekick_outcome(self, side, shots_left, ot_left, dangerous):
        rng = self.rng
        if not dangerous:
            return None if rng.random() < 0.5 else 'kurz'
        if shots_left[side] > 0 and rng.random() < 0.6:
            shots_left[side] -= 1
            if ot_left[side] > 0 and rng.random() < 0.5:
                ot_left[side] -= 1
                return 'direkt_gehalten'
            return rng.choice(['direkt_vorbei', 'direkt_mauer', 'flanke_kopfball_vorbei'])
        return rng.choice(['flanke_geklaert', 'flanke_geklaert', 'kurz'])

    # ---------- C: Unterbrechungen ----------
    def _sub(self, side, s):
        ctx = self.ctx
        seq = self._new_seq()
        p_out, p_in = ctx.player(s['out']), ctx.player(s['in'])
        kind = 'wechsel'
        if p_out and p_out.group == 'GK': kind = 'wechsel_torwart'
        elif p_out and p_out.rating <= 2.5: kind = 'wechsel_applaus'
        elif p_out and p_out.rating >= 4.3: kind = 'wechsel_enttaeuscht'
        elif p_in and p_in.group == 'ATT' and self.score[side] < self.score['home' if side == 'away' else 'away']: kind = 'wechsel_offensiv'
        self._line(seq, 1, s['minute'], kind, 'sub', side, actors={'o': p_out, 'p': p_in}, tags=self._tags(side, 'center')).payload = {'in': s['in'], 'out': s['out']}

    def _injury(self, inj):
        side = inj.get('club_side', inj.get('team', 'home'))
        seq = self._new_seq()
        p = self.ctx.player(inj.get('player_id'))
        self._line(seq, 1, inj['minute'], 'verletzung', 'injury', side, actors={'p': p}, tags=self._tags(side, 'center'))

    def _plan_line(self, act):
        seq = self._new_seq()
        side = act['side']
        ln = self._line(seq, 1, act['minute'], 'plan_' + act['plan'], 'analysis', side, visible=False, tags=self._tags(side, 'center'))
        ln.payload = {'plan': act['plan'], 'label': PLAN_LABEL.get(act['plan'], act['plan']), 'score': act.get('score')}

    def _place_phase(self, w):
        """Phasenzeile aus dem, was im Fenster sichtbar erzählt wurde (nicht aus den Fensterzahlen)."""
        a, b = w['from'], w['to']
        seqs = {}
        for l in self.lines:
            if a < l.minute <= b and l.team and l.cls in ('shot', 'goal', 'corner', 'gk_clear', 'abort', 'foul'):
                seqs.setdefault(l.seq, {'minute': l.minute, 'side': l.team, 'chance': False})
                if l.cls in ('shot', 'goal', 'corner'):
                    seqs[l.seq]['chance'] = True
        ordered = sorted(seqs.values(), key=lambda x: x['minute'])
        ch = {'home': [x for x in ordered if x['side'] == 'home' and x['chance']], 'away': [x for x in ordered if x['side'] == 'away' and x['chance']]}
        att = {'home': len([x for x in ordered if x['side'] == 'home']), 'away': len([x for x in ordered if x['side'] == 'away'])}
        nh, na = len(ch['home']), len(ch['away'])
        phase, side, level = None, None, 1
        lead = 'home' if self.score['home'] > self.score['away'] else ('away' if self.score['away'] > self.score['home'] else None)
        trail = {'home': 'away', 'away': 'home'}.get(lead)
        if nh + na == 0 and att['home'] + att['away'] <= 1:
            phase = 'abtasten' if a == 0 else 'ruhig'
        elif a == 0 and nh + na <= 3 and abs(nh - na) <= 1:
            phase = 'abtasten'
        elif nh >= 2 and na >= 2 and abs(nh - na) <= 1 and nh + na >= 5:
            phase = 'schlagabtausch'
        else:
            dom = 'home' if (nh, att['home']) > (na, att['away']) else 'away'
            other = 'away' if dom == 'home' else 'home'
            nd, no = (nh, na) if dom == 'home' else (na, nh)
            if nd >= 3 and no == 0: level = 3
            elif (nd >= 2 and no == 0) or (nd >= 3 and nd >= 3 * no): level = 2
            elif nd >= 1 and nd > no: level = 1
            else:
                phase = 'zerfahren' if att['home'] + att['away'] >= 3 else 'ruhig'
            if phase is None:
                side = dom
                if trail and w['plans'].get(trail) in ('aggressiv_risiko', 'schlussangriff'):
                    if dom == trail: phase = 'schlussoffensive'
                    else: phase = 'offen_raeume'; side = trail     # Kausalfall: X öffnet, Y bekommt Räume
                elif lead == dom and w['plans'].get(lead) in ('zeitspiel', 'kompakt_sichern', 'kontrolle_ballbesitz'):
                    phase = 'verwalten'
                else:
                    phase = 'druck'
        if phase is None:
            return
        # Position: vor der ersten Sequenz der dominierenden Seite im Fenster, sonst Fensterbeginn
        target = None
        if side and phase != 'offen_raeume':
            # Die Aussage muss durch die unmittelbar folgenden Sequenzen gedeckt sein:
            # Kandidat = jede Sequenz der Seite; bewertet werden die nächsten vier Sequenzen ab dort.
            best = None
            for i_, x in enumerate(ordered):
                if x['side'] != side:
                    continue
                nxt = ordered[i_:i_ + 4]
                c = len([y for y in nxt if y['side'] == side and y['chance']])
                o = len([y for y in nxt if y['side'] != side and y['chance']])
                lv = 3 if (c >= 3 and o == 0) else 2 if (c >= 2 and o == 0) else 1 if (c >= 1 and c > o) or (o == 0) else 0
                if lv == 0:
                    continue
                if best is None or (lv >= level and best[0] < level):
                    best = (lv, x)
                if lv >= level:
                    break
            if best is None:
                return
            level = min(level, best[0])
            target = best[1]
            # Keine Phasenzeile direkt neben einer Streak-Zeile derselben Seite
            if any(l.cls == 'phase' and l.team == side and abs(l.minute - target['minute']) <= 1 for l in self.lines):
                return
        elif phase == 'schlagabtausch':
            firsts = [x for x in ordered if x['chance']]
            if firsts: target = firsts[0]
        if target:
            minute = target['minute']
            seq_key = min(s_ for s_, v in seqs.items() if v is target) - 0.5
        else:
            minute = a + (1 if a not in (0, 45, 90) else 2)
            seq_key = self._new_seq()
        ln = self._line(seq_key, 1, minute, 'phase', 'phase', side, visible=False)
        ln.payload = {'phase': phase, 'side': side, 'level': level, 'phase_level': level}
        st = self.state
        st.last_phase_team, st.last_phase, st.last_phase_level, st.last_phase_minute = side, phase, level, minute
        # Schlussakkord vor dem Abpfiff der regulären Zeit
        if b == 90 and side and phase in ('druck', 'schlussoffensive') and self.score[side] <= self.score['home' if side == 'away' else 'away']:
            lasts = [x for x in ordered if x['side'] == side and x['minute'] >= 85]
            if lasts:
                key = min(s_ for s_, v in seqs.items() if v is lasts[-1]) - 0.5
                l3 = self._line(key, 1, lasts[-1]['minute'], 'phase', 'phase', side, visible=False)
                l3.payload = {'phase': 'schlussdrang', 'side': side, 'phase_level': 1,
                              'ziel': 'den Ausgleich' if self.score[side] < self.score['home' if side == 'away' else 'away'] else 'die Führung'}
        if w['pressing_side'] and a == 0:
            l2 = self._line(seq_key, 2, minute, 'phase', 'phase', w['pressing_side'], visible=False)
            l2.payload = {'phase': 'pressing_note', 'side': w['pressing_side'], 'phase_level': 1}

    # ---------- D: Analyse ----------
    def _kickoff(self):
        seq = self._new_seq()
        ln = self._line(seq, 1, 0, 'anpfiff', 'kickoff', None, visible=True)
        ln.payload = {'referee': self.ctx.referee, 'weather': self.ctx.weather}
        for side in ('home', 'away'):
            t = self.ctx.team(side).tactic
            l2 = self._line(seq, 2 if side == 'home' else 3, 0, 'analyse_ausrichtung', 'analysis', side, visible=False)
            l2.payload = {'formation': self.ctx.team(side).formation, 'fokus': FOCUS_LABEL.get(t.attack_focus, t.attack_focus),
                          'umschalten': UMSCHALT_LABEL.get(t.umschalten, t.umschalten), 'pressing': PRESSING_LABEL.get(t.pressing_level, t.pressing_level),
                          'deckung': DECKUNG_LABEL.get(t.deckung, t.deckung), 'zweikampf': t.zweikampf,
                          'aufbau': t.buildup_defense, 'mittelfeld': t.buildup_midfield, 'angriff': t.buildup_attack}

    def _halftime(self, added):
        seq = self._new_seq()
        h, a = self.ctx.home, self.ctx.away
        ln = self._line(seq, 1, 45, 'halbzeit', 'halftime', None, added=added)
        ln.payload = {'score': f"{self.score['home']}:{self.score['away']}"}
        l2 = self._line(seq, 2, 45, 'analyse_halbzeit', 'analysis', None, visible=False, added=added)
        l2.payload = self._numbers_snapshot(45)
        for side in ('home', 'away'):
            hv = self.ctx.team(side).tactic.halves
            fh, sh = hv.get('first_half') or {}, hv.get('second_half') or {}
            changes = {k: (fh.get(k), sh.get(k)) for k in ('defense', 'midfield', 'attack', 'effort') if fh.get(k) != sh.get(k)}
            if changes:
                l3 = self._line(seq, 3, 46, 'analyse_halbzeitwechsel', 'analysis', side, visible=False)
                l3.payload = {'changes': changes}

    def _numbers_snapshot(self, upto):
        h, a = self.ctx.home, self.ctx.away
        def cnt(side, cls):
            return len([l for l in self.lines if l.team == side and l.cls == cls and l.minute <= upto])
        return {'score': f"{self.score['home']}:{self.score['away']}",
                'shots': (cnt('home', 'shot') + cnt('home', 'goal'), cnt('away', 'shot') + cnt('away', 'goal')),
                'corners': (cnt('home', 'corner'), cnt('away', 'corner')),
                'possession': (h.stats.get('possession', 50), a.stats.get('possession', 50)),
                'zones': ({z: h.stats.get(f'attacks_{z}', 0) for z in ('left', 'center', 'right')},
                          {z: a.stats.get(f'attacks_{z}', 0) for z in ('left', 'center', 'right')})}

    def _fulltime(self, minute, added, kind='abpfiff'):
        seq = self._new_seq()
        ln = self._line(seq, 1, minute, kind, 'fulltime', None, added=added)
        ln.payload = {'score': f"{self.score['home']}:{self.score['away']}"}
        if kind == 'abpfiff':
            l2 = self._line(seq, 2, minute, 'analyse_fazit', 'analysis', None, visible=False, added=added)
            l2.payload = self._fazit_payload()

    def _fazit_payload(self):
        ctx = self.ctx
        out = {'score': f"{self.score['home']}:{self.score['away']}", 'teams': {}}
        for side in ('home', 'away'):
            t = ctx.team(side); st = t.stats
            zones = {z: st.get(f'attacks_{z}', 0) for z in ('left', 'center', 'right')}
            total = max(1, sum(zones.values()))
            focus = t.tactic.attack_focus
            wanted = {'fluegelspiel': ('left', 'right'), 'ueber_links': ('left',), 'ueber_rechts': ('right',),
                      'durch_mitte': ('center',), 'flanke_kopfball': ('left', 'right')}.get(focus)
            share = round(100 * sum(zones[z] for z in wanted) / total) if wanted else None
            plans = ctx.plan_seg_stats.get(side) or {}
            out['teams'][side] = {'name': t.name, 'xg': round(t.xg, 2), 'shots': st.get('shots', 0), 'on_target': st.get('shots_on_target', 0),
                                  'possession': st.get('possession', 50), 'pressing_wins': st.get('pressing_ball_wins', 0),
                                  'pressing_bypassed': st.get('pressing_bypassed', 0), 'fouls': st.get('fouls', 0),
                                  'focus': FOCUS_LABEL.get(focus, focus), 'focus_share': share, 'zones': zones,
                                  'plans': {PLAN_LABEL.get(k, k): v for k, v in plans.items()}}
        return out

    # ---------- Verlängerung / Elfmeterschießen ----------
    def _shootout(self):
        ctx = self.ctx
        seq = self._new_seq()
        self._line(seq, 1, 120, 'elfmeterschiessen_start', 'shootout_start', None).payload = {'score': f"{self.score['home']}:{self.score['away']}"}
        b = 1
        tally = {'home': 0, 'away': 0}
        shot_ids = []
        last_kick = None
        for ev in sorted([e for e in ctx.penalty_events if e.get('team') and e.get('round')], key=lambda e: (e.get('round', 0), 0 if e['team'] == 'home' else 1)):
            b += 1
            p = ctx.player(ev.get('scorer_id'))
            if p is None or not p.on_pitch(120):
                repl = self.pick.pick(ctx.team(ev['team']), 120, 'abschluss', good=True, exclude=set(shot_ids), prefer_fresh=False)
                self.issues.append(f"Elfmeterschießen Runde {ev.get('round')}: Engine nennt {ev.get('scorer_name')}, der nicht auf dem Platz war – im Text ersetzt durch {repl.name if repl else '?'} (Engine-Ticket)")
                p = repl
            elif p.group == 'GK' and ev.get('round', 9) <= 3:
                self.issues.append(f"Elfmeterschießen Runde {ev.get('round')}: Torwart {p.name} schießt – Engine-Reihenfolge prüfen")
            if p: shot_ids.append(p.id)
            k = ctx.opp(ev['team']).keeper(120)
            if ev['type'] == 'penalty_scored':
                tally[ev['team']] += 1
            kind = {'penalty_scored': 'elfer_verwandelt', 'penalty_missed': 'elfer_vergeben', 'penalty_saved': 'elfer_gehalten'}.get(ev['type'], 'elfer_vergeben')
            ktags = []
            if kind != 'elfer_verwandelt' and last_kick and last_kick != 'elfer_verwandelt': ktags.append('auch_vergeben')
            if kind == 'elfer_verwandelt' and last_kick and last_kick != 'elfer_verwandelt': ktags.append('erster_treffer_nach_fehlschuss')
            ln = self._line(seq, b, 120, kind, 'shootout_kick', ev['team'], actors={'p': p, 'k': k}, tags=ktags)
            ln.payload = {'round': ev.get('round'), 'tally': f"{tally['home']}:{tally['away']}"}
            last_kick = kind
        self._line(seq, b + 1, 120, 'elfmeterschiessen_ende', 'fulltime', None).payload = {'tally': f"{tally['home']}:{tally['away']}"}

    # ---------- Hauptlauf ----------
    def run(self):
        ctx = self.ctx
        bud = from_segment_log(ctx) or distribute(ctx, self.rng)
        fm = ctx.final_minute
        n_seg = fm // 5
        # Zieldichte: ~40 Sequenzen je 90 Minuten, ereignisreiche Spiele füllen weniger auf
        self.windows = phases.classify(ctx, bud)
        n_events = sum(ctx.team(s).stats.get('shots', 0) + ctx.team(s).stats.get('corners', 0) for s in ('home', 'away'))
        target_total = max(18, 30 - n_events // 3)
        per_seg = target_total / 18.0
        added_1 = 1 + len([x for x in ctx.cards + [s for s in ctx.subs['home'] + ctx.subs['away']] if 35 < x['minute'] <= 45])
        added_2 = 2 + min(4, len([x for x in ctx.cards + ctx.goals + ctx.subs['home'] + ctx.subs['away'] if 75 < x['minute'] <= 90]) // 2)
        self._kickoff()
        carry = 0.0
        for i in range(n_seg):
            a, b = i * 5, (i + 1) * 5
            if a == 45:
                self._halftime(added_1)
                self._line(self._new_seq(), 1, 46, 'anpfiff_2', 'kickoff', None)
            if a == 90:
                self._fulltime(90, added_2, kind='abpfiff_90')
                self._line(self._new_seq(), 1, 91, 'anpfiff_vl', 'kickoff', None)
            if a == 105:
                self._line(self._new_seq(), 1, 105, 'halbzeit_vl', 'halftime', None)
            w = phases.window_for(self.windows, a + 1)
            quiet = w['phase'] in ('abtasten', 'ruhig', 'verwalten')
            carry += (per_seg if a < 90 else per_seg * 0.7) * (0.6 if quiet else 1.0)
            fillers = int(carry)
            carry -= fillers
            self._narrate_segment(a, b, {'home': bud['home'][i], 'away': bud['away'][i]}, fillers, added_1 if b == 45 else 0)
            self.score_history[b] = f"{self.score['home']}:{self.score['away']}"
            self.state.late_game = b >= 80
            for side_ in ('home', 'away'):
                acts = [x for x in ctx.plan_activations if x['side'] == side_ and x['minute'] <= b]
                self.state.defensive_plan_active[side_] = acts[-1]['plan'] if acts and acts[-1]['plan'] in ('kompakt_sichern', 'zeitspiel', 'kontrolle_ballbesitz', 'unterzahl_kompakt') else None
            if b == w['to']:
                self._place_phase(w)
        if ctx.has_extra_time:
            self._fulltime(120, 0, kind='abpfiff')
            if ctx.decided_by == 'penalties':
                self._shootout()
        else:
            self._fulltime(90, added_2)
        # Nachspielzeit: Zeilen in Minute 45/90 bekommen die Zugabe
        self.lines.sort(key=lambda l: (l.minute + (0.5 if l.added else 0), l.seq, l.beat))
        # Kontrolle Kernzahlen (auf Beat-Ebene)
        self._verify()
        self.beats = self.lines
        self.lines = compose(self.beats)
        planner.plan(self.lines, ctx)
        pools.render_all(self.lines, ctx, self.rng)
        return self.lines

    def _verify(self):
        ctx = self.ctx
        for side in ('home', 'away'):
            st = ctx.team(side).stats
            shots = len([l for l in self.lines if l.team == side and l.cls in ('shot', 'goal')])
            ot = len([l for l in self.lines if l.team == side and (l.cls == 'goal' or (l.cls == 'shot' and l.payload.get('on_target')))])
            corners = len([l for l in self.lines if l.team == side and l.cls == 'corner'])
            cards = len([l for l in self.lines if l.team == side and l.cls == 'card'])
            exp = (st.get('shots', 0), st.get('shots_on_target', 0), st.get('corners', 0), st.get('yellow', 0) + st.get('red', 0))
            got = (shots, ot, corners, cards)
            if exp != got:
                self.issues.append(f"Kernzahlen {side}: erwartet Schüsse/aufs Tor/Ecken/Karten {exp}, erzählt {got}")


def narrate(export):
    n = Narrator(export)
    lines = n.run()
    return {'lines': lines, 'beats': n.beats, 'ctx': n.ctx, 'issues': n.issues, 'score': n.score, 'windows': n.windows,
            'segments': build_segments(n), 'state': n.state.as_dict()}
