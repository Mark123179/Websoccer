"""Bedarfsrechnung des KI-Käufers (Spec Kap. 9.3, formal).

Reine Lesefunktionen — KEINE Seiteneffekte (ensure_default_tactic schreibt
TacticSetup und wird hier bewusst NICHT benutzt). Die Beste-11 ist die
stärkste formationskonforme Elf nach WAHRER Stärke (PlayerStrengthProfile),
nicht die tatsächlich aufgestellte Startelf.

  Stammlücke  = max(0, Liga_Soll − Stärke des Beste-11-Spielers)
  Backup      = weiterer Positionsspieler mit Stärke ≥ Beste11 − backup_delta
                ODER Potential ≥ Beste-11-Niveau (Talente zählen als Backup)
  Lückenscore = 10 × kritische Tiefenlücke + 1 × Stammlücke
  Akuter Bedarf: kritische Tiefenlücke ODER Lückenscore ≥ Schwellwert.

Liga_Soll = Median der Beste-11-Stärken aller Ligavereine (einmal je
Liga/Prüflauf rechnen und durchreichen).
"""
from decimal import Decimal
from statistics import median

from game.match_readiness import _all_valid_formations, _player_base_strength
from game.tactics import FORMATION_ORDER, FORMATION_PARTS

from ..schmerzgrenze import potential_200


def _slots_der_formation(formation_dict):
    """[('TW', 'goalkeeper'), ('IV', 'defense'), …] für eine Formation."""
    slots = [('TW', 'goalkeeper')]
    for part in FORMATION_ORDER:
        code = formation_dict[part]
        slots.extend((pos, part) for pos in FORMATION_PARTS[part][code])
    return slots


def _greedy_zuordnung(formation_dict, players):
    """Gieriges HP→NP-Füllen (Logik aus match_readiness._score_formation),
    gibt zusätzlich die Zuordnung zurück.

    Returns (score_tuple, zuordnung) mit
      score_tuple = (filled, hp, np, effective_strength)
      zuordnung   = [(slot_code, player | None, 'HP'|'NP'|None), …]
    """
    slots_to_fill = _slots_der_formation(formation_dict)

    used = set()
    filled = hp = np_ = 0
    effective = 0.0
    zuordnung = []
    for slot_code, _group in slots_to_fill:
        gewaehlt = None
        modus = None
        for p in players:
            if p.pk not in used and slot_code in p.main_positions:
                gewaehlt, modus = p, 'HP'
                hp += 1
                effective += float(_player_base_strength(p))
                break
        else:
            for p in players:
                if p.pk not in used and slot_code in p.secondary_positions:
                    gewaehlt, modus = p, 'NP'
                    np_ += 1
                    effective += float(_player_base_strength(p)) * 0.9
                    break
        if gewaehlt is not None:
            used.add(gewaehlt.pk)
            filled += 1
        zuordnung.append((slot_code, gewaehlt, modus))
    return (filled, hp, np_, effective), zuordnung


def beste_elf(players):
    """Stärkste formationskonforme Elf (pure Funktion, keine Schreibzugriffe).

    Args:
        players: Liste von Player-Objekten (mit strength_profile vorab
                 geladen — select_related('strength_profile')).

    Returns dict:
      'formation':  Formations-Dict {part: code}
      'zuordnung':  [(slot_code, player | None, 'HP'|'NP'|None), …]
      'staerken':   [Decimal, …] der besetzten Slots (wahre Stärke)
    oder None bei leerem Kader.
    """
    if not players:
        return None
    # Stärkste zuerst → Greedy besetzt jeden Slot mit dem stärksten
    # verfügbaren Spieler (gleiches Prinzip wie ensure_default_tactic).
    sortiert = sorted(players, key=_player_base_strength, reverse=True)

    best_score, best_formation, best_zuordnung = None, None, None
    for formation in _all_valid_formations():
        score, zuordnung = _greedy_zuordnung(formation, sortiert)
        if best_score is None or score > best_score:
            best_score, best_formation, best_zuordnung = (
                score, formation, zuordnung,
            )

    staerken = [
        Decimal(str(_player_base_strength(p)))
        for _code, p, _m in best_zuordnung if p is not None
    ]
    return {
        'formation': best_formation,
        'zuordnung': best_zuordnung,
        'staerken': staerken,
    }


def _kader(club):
    """Kaderliste mit vorab geladenen Stärkeprofilen + Quellen-Ratings
    (potential_200 im Backup-Check ohne N+1)."""
    from game.models import Player
    return list(
        Player.objects.filter(club=club)
        .select_related('strength_profile')
        .prefetch_related('source_ratings')
    )


def liga_soll(league, *, kader_cache=None):
    """Liga-Soll = Median ALLER Beste-11-Stärken der Ligavereine.

    kader_cache: optionales dict {club_id: [players]} zur Wiederverwendung
    im Prüflauf (ein Spieltag rechnet das Soll genau einmal je Liga).
    """
    from game.models import Club

    werte = []
    for club in Club.objects.filter(league=league):
        players = (kader_cache or {}).get(club.pk)
        if players is None:
            players = _kader(club)
            if kader_cache is not None:
                kader_cache[club.pk] = players
        elf = beste_elf(players)
        if elf and elf['staerken']:
            werte.extend(float(s) for s in elf['staerken'])
    if not werte:
        return Decimal('0')
    return Decimal(str(median(werte)))


def bedarfs_analyse(club, soll, params, *, players=None):
    """Positions-Tiefenanalyse eines Vereins (Spec 9.3, formal).

    Returns dict:
      'elf':       beste_elf-Ergebnis (oder None)
      'positionen': [{'position', 'spieler', 'staerke', 'stammluecke',
                      'backup', 'kritisch', 'score'}, …]
      'akut':      Teilmenge mit akutem Bedarf, absteigend nach score
      'posbester': {slot_code: Decimal} — stärkster HP-Spieler je Position
                   (Basis des Qualitätskaufs)
    """
    backup_delta = Decimal(str(params.get('backup_delta', 25)))
    schwellwert = Decimal(str(params.get('luecken_schwellwert', 15)))
    soll = Decimal(str(soll))

    if players is None:
        players = _kader(club)
    elf = beste_elf(players)
    if elf is None:
        return {'elf': None, 'positionen': [], 'akut': [], 'posbester': {}}

    besetzte_ids = {p.pk for _c, p, _m in elf['zuordnung'] if p is not None}

    positionen = []
    for slot_code, spieler, _modus in elf['zuordnung']:
        if spieler is None:
            # Slot gar nicht besetzbar → maximale kritische Lücke.
            positionen.append({
                'position': slot_code, 'spieler': None,
                'staerke': Decimal('0'), 'stammluecke': soll,
                'backup': False, 'kritisch': True,
                'score': Decimal('10') + soll,
            })
            continue

        staerke = Decimal(str(_player_base_strength(spieler)))
        stammluecke = max(Decimal('0'), soll - staerke)

        backup = False
        for p in players:
            if p.pk == spieler.pk or p.pk in besetzte_ids:
                continue
            if slot_code not in p.all_position_codes:
                continue
            p_staerke = Decimal(str(_player_base_strength(p)))
            p_potential = potential_200(p) or Decimal('0')
            if p_staerke >= staerke - backup_delta or p_potential >= staerke:
                backup = True
                break

        kritisch = not backup  # gilt auch für den 2. TW (TW-Slot ohne Backup)
        score = (Decimal('10') if kritisch else Decimal('0')) + stammluecke
        positionen.append({
            'position': slot_code, 'spieler': spieler, 'staerke': staerke,
            'stammluecke': stammluecke, 'backup': backup,
            'kritisch': kritisch, 'score': score,
        })

    akut = sorted(
        (p for p in positionen if p['kritisch'] or p['score'] >= schwellwert),
        key=lambda p: p['score'], reverse=True,
    )

    posbester = {}
    for p in players:
        staerke = Decimal(str(_player_base_strength(p)))
        for code in p.main_positions:
            if code not in posbester or staerke > posbester[code]:
                posbester[code] = staerke

    return {
        'elf': elf, 'positionen': positionen, 'akut': akut,
        'posbester': posbester,
    }


def dringlichkeit(club, params, *, polster_ok=True):
    """Dringlichkeitsdiskont 0,3–1,0 (Spec 9.3) — Torwächter der Kauftypen.

    1,0 = entspannt (Saisonziel sicher, Polster vorhanden),
    dringlichkeit_min = maximaler Druck. Abstiegskandidaten (unterstes
    Tabellendrittel-Ende bzw. Klassenerhalt-Ziel in Gefahr) tätigen NUR
    Bedarfskäufe.

    Returns dict: {'faktor', 'abstiegskandidat', 'ziel_gefaehrdet',
                   'rank', 'required_max_rank'}.
    """
    from game.models import SeasonGoal
    from game.season_goals import (
        current_season_number,
        rank_clubs_in_league,
        required_max_rank,
        tier_for_rank,
    )

    minimum = Decimal(str(params.get('dringlichkeit_min', 0.3)))

    ranked = rank_clubs_in_league(club.league)
    league_size = len(ranked) or 1
    rank = league_size
    for idx, (c, _s) in enumerate(ranked):
        if c.pk == club.pk:
            rank = idx + 1
            break

    goal = SeasonGoal.objects.filter(
        club=club, season_number=current_season_number(),
    ).first()
    if goal is not None:
        max_rank = goal.required_max_rank
        tier = goal.goal_tier
    else:
        tier = tier_for_rank(rank, league_size)
        max_rank = required_max_rank(tier, league_size)

    rueckstand = max(0, rank - max_rank)
    ziel_gefaehrdet = rueckstand > 0
    abstiegskandidat = (
        rank > league_size - 3
        or (tier == SeasonGoal.TIER_KLASSENERHALT and ziel_gefaehrdet)
    )

    faktor = Decimal('1.0') - Decimal('0.1') * rueckstand
    if not polster_ok:
        faktor -= Decimal('0.2')
    faktor = max(minimum, min(Decimal('1.0'), faktor))

    return {
        'faktor': faktor,
        'abstiegskandidat': abstiegskandidat,
        'ziel_gefaehrdet': ziel_gefaehrdet,
        'rank': rank,
        'required_max_rank': max_rank,
    }
