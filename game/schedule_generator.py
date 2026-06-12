"""Round-Robin Spielplan-Generator  –  v2 (streak-balanced).

Phasenmodell:
  1. Paarungen  – Kreis-Algorithmus: legt WANN wer gegen wen spielt (kein Heimrecht).
  2. Heimrecht  – Greedy-Zuteilung:  minimiert aufeinanderfolgende Heim/Auswärts-Serien.
  3. Reparatur  – Swap-Schleife:     behebt verbleibende Serien durch Paar-Tausch.

Gibt vollständigen Spielplan zurück:
    {spieltag: [(home_club_id, away_club_id), ...], ...}

Ungerade Vereinszahl: Dummy-Team (None) für spielfreie Runden.
Bilanz garantiert: jedes Team hat genau (n-1) Heimspiele pro Runde.
"""

import random
from collections import defaultdict


# ──────────────────────────────────────────────────────────────────────────────
# Öffentliche API
# ──────────────────────────────────────────────────────────────────────────────

def create_round_robin_schedule(team_ids, rounds=2, max_consecutive=2):
    """Erstellt einen Round-Robin-Spielplan für die gegebenen Team-IDs.

    Args:
        team_ids:        Iterable von Club-PKs (mind. 2).
        rounds:          Anzahl Durchgänge (1 = Hinrunde, 2 = Hin- + Rückrunde).
        max_consecutive: Maximale erlaubte aufeinanderfolgende Heim- oder
                         Auswärtsspiele pro Team (Standard 2; 3 als Fallback).

    Returns:
        dict {spieltag (int, 1-basiert): [(home_id, away_id), ...]}
        Spiele mit Freirunde (bye) sind bereits herausgefiltert.

    Raises:
        ValueError: Bei weniger als 2 Vereinen oder ungültigem rounds-Wert.
    """
    teams = list(team_ids)
    if len(teams) < 2:
        raise ValueError('Mindestens 2 Vereine für einen Spielplan erforderlich.')
    if rounds < 1:
        raise ValueError('rounds muss mindestens 1 sein.')

    random.shuffle(teams)

    n = len(teams)
    if n % 2 == 1:
        teams.append(None)
        n += 1

    half = n // 2
    matchdays_per_round = n - 1

    # ── Phase 1: Rohe Paarungen per Kreis-Algorithmus ─────────────────────────
    # teams[0] bleibt fix; teams[1..n-1] rotieren (letzter → vorne).
    # Ergebnis: raw_by_md = {md: [(a, b), ...]}  (ungeordnete Paare, kein Heimrecht)

    fixed = teams[0]
    rotating = list(teams[1:])
    raw_hinrunde: dict[int, list[tuple]] = {}

    for md in range(matchdays_per_round):
        circle = [fixed] + rotating
        pairs = []
        for i in range(half):
            left  = circle[i]
            right = circle[n - 1 - i]
            if left is not None and right is not None:
                pairs.append((left, right))
        raw_hinrunde[md + 1] = pairs
        rotating = [rotating[-1]] + rotating[:-1]

    # ── Phase 2: Vollständige Rohdaten aller Runden zusammenbauen ─────────────
    raw_all: dict[int, list[tuple]] = {}
    for round_num in range(rounds):
        offset = round_num * matchdays_per_round
        for md, pairs in raw_hinrunde.items():
            raw_all[offset + md] = list(pairs)

    # ── Phase 3: Heimrecht greedy zuweisen ────────────────────────────────────
    schedule = _assign_home_away(raw_all, max_consecutive)

    # ── Phase 4: Verbleibende Serien durch Paar-Swap reparieren ──────────────
    schedule = _repair_streaks(schedule, max_consecutive, max_passes=60)

    return schedule


def matchday_date(spieltag, start_date, day_interval, matchdays_per_round, round_break):
    """Berechnet das Datum für einen Spieltag.

    Args:
        spieltag:            Spieltagnummer (1-basiert).
        start_date:          datetime.date des ersten Spieltags.
        day_interval:        Tage zwischen Spieltagen.
        matchdays_per_round: Spieltage pro Runde (Hinrunde).
        round_break:         Extra-Tage Pause zwischen Runden.

    Returns:
        datetime.date
    """
    from datetime import timedelta

    round_index = (spieltag - 1) // matchdays_per_round
    md_in_round = (spieltag - 1) % matchdays_per_round

    offset_days = (
        round_index * (matchdays_per_round * day_interval + round_break)
        + md_in_round * day_interval
    )
    return start_date + timedelta(days=offset_days)


# ──────────────────────────────────────────────────────────────────────────────
# Interne Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────────────

def _assign_home_away(raw_by_md: dict, max_streak: int) -> dict:
    """Weist Heimrecht greedy zu, um aufeinanderfolgende Serien zu minimieren.

    Für jedes Paar (A, B) wird die zweite Begegnung automatisch als Flip der
    ersten Begegnung gesetzt → Bilanzgleichgewicht bleibt erhalten.

    Args:
        raw_by_md:  {md: [(a, b), ...]}  – ungeordnete Paare
        max_streak: Maximale erlaubte Serie vor Hard-Constraint-Eingriff

    Returns:
        {md: [(home, away), ...]}
    """
    # pair_home[frozenset({a,b})] = team, das in der ERSTEN Begegnung heimgespielt hat
    pair_home: dict[frozenset, int] = {}

    # team_state[t] = {'h': aktuelle Heimserie, 'a': aktuelle Auswärtsserie, 'last': bool|None}
    team_state: dict = defaultdict(lambda: {'h': 0, 'a': 0, 'last': None})

    result: dict[int, list] = {}

    for md in sorted(raw_by_md.keys()):
        assigned = []
        for (ta, tb) in raw_by_md[md]:
            key = frozenset({ta, tb})

            if key in pair_home:
                # Zweite Begegnung: Heimrecht tauschen → Balance garantiert
                first = pair_home[key]
                home, away = (tb, ta) if first == ta else (ta, tb)
            else:
                # Erste Begegnung: greedy entscheiden
                sa = team_state[ta]
                sb = team_state[tb]
                score = _ha_score(sa, sb, max_streak)
                home, away = (ta, tb) if score >= 0 else (tb, ta)
                pair_home[key] = home

            assigned.append((home, away))
            _tick(team_state[home], is_home=True)
            _tick(team_state[away], is_home=False)

        result[md] = assigned

    return result


def _ha_score(sa: dict, sb: dict, max_streak: int) -> int:
    """Positiver Score → ta sollte Heim spielen; negativer → tb.

    Hard-Constraints (±1000) überstimmen Soft-Präferenzen (±1).
    """
    score = 0

    # Hard: erzwinge Wechsel wenn max_streak erreicht
    if sa['last'] is True  and sa['h'] >= max_streak: score -= 1000
    if sb['last'] is True  and sb['h'] >= max_streak: score += 1000
    if sa['last'] is False and sa['a'] >= max_streak: score += 1000
    if sb['last'] is False and sb['a'] >= max_streak: score -= 1000

    # Soft: abwechseln bevorzugen
    if   sa['last'] is True:  score -= 1
    elif sa['last'] is False: score += 1
    if   sb['last'] is True:  score += 1
    elif sb['last'] is False: score -= 1

    return score


def _tick(s: dict, is_home: bool) -> None:
    """Aktualisiert den Serienzähler eines Teams nach einem Spiel."""
    if is_home:
        s['h'] = s['h'] + 1 if s['last'] is True else 1
        s['a'] = 0
        s['last'] = True
    else:
        s['a'] = s['a'] + 1 if s['last'] is False else 1
        s['h'] = 0
        s['last'] = False


def _build_sequences(schedule: dict) -> dict:
    """Gibt {team_id: [(matchday, is_home), ...]} sortiert nach Spieltag zurück."""
    seqs: dict = defaultdict(list)
    for md in sorted(schedule.keys()):
        for home, away in schedule[md]:
            if home is not None: seqs[home].append((md, True))
            if away is not None: seqs[away].append((md, False))
    return dict(seqs)


def _repair_streaks(schedule: dict, max_streak: int, max_passes: int = 60) -> dict:
    """Beseitigt Serien > max_streak per Paar-Tausch.

    Pro Schritt: schlimmste verbleibende Serie lokalisieren → Mittelpunkt-Spieltag
    finden → dieses Spiel H/A tauschen → Gegenstück (gleiche Teams, anderer
    Spieltag) ebenfalls tauschen, um die Bilanz zu erhalten.

    Args:
        schedule:   {md: [(home, away), ...]}
        max_streak: Zielwert
        max_passes: Maximale Reparatur-Iterationen

    Returns:
        Reparierter Spielplan (in-place und als Rückgabe)
    """
    matchdays = sorted(schedule.keys())

    for _ in range(max_passes):
        seqs = _build_sequences(schedule)

        # Schlimmste Verletzung suchen
        worst_run = max_streak          # Nur Verletzungen über Schwelle
        worst_team = None
        worst_md = None

        for team, seq in seqs.items():
            run = 0
            run_start = 0
            for i, (md, is_home) in enumerate(seq):
                if i == 0 or is_home != seq[i - 1][1]:
                    run = 1
                    run_start = i
                else:
                    run += 1
                if run > worst_run:
                    worst_run = run
                    worst_team = team
                    # Mittelpunkt der aktuellen Serie
                    mid = run_start + run // 2
                    worst_md = seq[mid][0]

        if worst_team is None:
            break  # Keine Verletzungen mehr

        # Gegner auf worst_md herausfinden
        opponent = None
        for home, away in schedule[worst_md]:
            if home == worst_team:
                opponent = away
                break
            if away == worst_team:
                opponent = home
                break

        if opponent is None:
            break

        # Dieses Spiel tauschen
        _swap_pair(schedule, worst_md, worst_team, opponent)

        # Gegenstück (gleiche Teams, anderer Spieltag) ebenfalls tauschen
        # → hält H/A-Bilanz perfekt ausgeglichen
        for other_md in matchdays:
            if other_md == worst_md:
                continue
            for home, away in schedule[other_md]:
                if {home, away} == {worst_team, opponent}:
                    _swap_pair(schedule, other_md, worst_team, opponent)
                    break
            else:
                continue
            break

    return schedule


def _swap_pair(schedule: dict, md: int, team_a, team_b) -> None:
    """Tauscht Heim/Auswärts für das Spiel zwischen team_a und team_b an Spieltag md."""
    schedule[md] = [
        (away, home) if {home, away} == {team_a, team_b} else (home, away)
        for home, away in schedule[md]
    ]
