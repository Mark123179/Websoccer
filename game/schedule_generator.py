"""Round-Robin Spielplan-Generator.

Portiert vom Original-OpenWebSoccer-PHP-Algorithmus nach Python/Django.
Gibt einen vollständigen Spielplan als dict zurück:
    {spieltag: [(home_club_id, away_club_id), ...], ...}

Ungerade Vereinszahl: Dummy-Team (None) für spielfreie Runden.
Rückrunde: Heimrecht komplett getauscht.
"""

import random


def create_round_robin_schedule(team_ids, rounds=2):
    """Erstellt einen Round-Robin-Spielplan für die gegebenen Team-IDs.

    Args:
        team_ids: Iterable von Club-PKs (mind. 2).
        rounds:   Anzahl Durchgänge (1 = Hinrunde, 2 = Hin- + Rückrunde, ...).

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

    # Für Abwechslung die Startaufstellung mischen
    random.shuffle(teams)

    n = len(teams)

    # Ungerade Teamzahl → Dummy-Team (None) als Freirunde einfügen
    has_dummy = (n % 2 == 1)
    if has_dummy:
        teams.append(None)
        n += 1

    half = n // 2
    matchdays_per_round = n - 1   # Bei gerader Teamzahl (nach ggf. Dummy)

    # ── Hinrunde-Paarungen per Kreis-Algorithmus ──────────────────────────────
    # teams[0] bleibt fix. teams[1..n-1] rotieren nach rechts (letzter → vorne).

    fixed = teams[0]
    rotating = list(teams[1:])
    hinrunde = {}

    for md in range(matchdays_per_round):
        circle = [fixed] + rotating
        pairs = []
        for i in range(half):
            home = circle[i]
            away = circle[n - 1 - i]
            if home is not None and away is not None:
                pairs.append((home, away))
        hinrunde[md + 1] = pairs
        # Rotation: letztes Element nach vorne schieben
        rotating = [rotating[-1]] + rotating[:-1]

    # ── Vollständigen Spielplan aufbauen ──────────────────────────────────────
    schedule = {}

    for round_num in range(rounds):
        offset = round_num * matchdays_per_round
        if round_num % 2 == 0:
            # Gerade Runde (0, 2, …): Hinrunde-Paarungen
            for md, pairs in hinrunde.items():
                schedule[offset + md] = list(pairs)
        else:
            # Ungerade Runde (1, 3, …): Rückrunde — Heimrecht tauschen
            for md, pairs in hinrunde.items():
                schedule[offset + md] = [(away, home) for home, away in pairs]

    return schedule


def matchday_date(spieltag, start_date, day_interval, matchdays_per_round, round_break):
    """Berechnet das Datum für einen Spieltag.

    Args:
        spieltag:          Spieltagnummer (1-basiert).
        start_date:        datetime.date des ersten Spieltags.
        day_interval:      Tage zwischen Spieltagen.
        matchdays_per_round: Spieltage pro Runde (Hinrunde).
        round_break:       Extra-Tage Pause zwischen Runden.

    Returns:
        datetime.date
    """
    from datetime import timedelta

    round_index = (spieltag - 1) // matchdays_per_round   # 0 = Hinrunde, 1 = Rückrunde, …
    md_in_round = (spieltag - 1) % matchdays_per_round    # Position innerhalb der Runde

    offset_days = (
        round_index * (matchdays_per_round * day_interval + round_break)
        + md_in_round * day_interval
    )
    return start_date + timedelta(days=offset_days)
