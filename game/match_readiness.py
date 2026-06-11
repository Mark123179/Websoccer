"""Match-Readiness: Taktik & Stärke

Dieses Modul stellt drei Hauptfunktionen bereit:

- ensure_default_tactic(club)       — legt/repariert TacticSetup mit 11 Slots
- calculate_lineup_strength(...)    — Stärke-Dict {goalkeeper, defense, midfield, attack, overall}
- prepare_matchday_lineups(...)     — Matchday-Hook: alle Vereine prüfen & auffüllen
"""

from decimal import Decimal

from django.utils import timezone

from .tactics import (
    DEFAULT_FORMATION,
    FORMATION_ORDER,
    FORMATION_PARTS,
    SQUAD_PRO,
    default_bench,
    default_conditions,
    default_formation,
    default_half_tactic,
    default_instructions,
    default_standards,
    default_substitutions,
    formation_slots,
    slot_key_for,
)

DUMMY_STRENGTH = Decimal('50.00')
LINEUP_MALUS_FACTOR = Decimal('0.80')

# formation_slot group → Stärke-Kategorie
_GROUP_KEY = {
    'goalkeeper': 'goalkeeper',
    'defense': 'defense',
    'defensive_midfield': 'midfield',
    'midfield': 'midfield',
    'offensive_midfield': 'midfield',
    'attack': 'attack',
}


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _player_base_strength(player):
    """Stärke eines Spielers; Dummy-50 wenn kein Profil vorhanden."""
    try:
        return player.strength_profile.base_strength or DUMMY_STRENGTH
    except Exception:
        return DUMMY_STRENGTH


def has_valid_lineup(tactic_setup, club=None):
    """Strikte Prüfung: alle Formations-Slots belegt, eindeutige IDs, TW vorhanden.

    Checks (in Reihenfolge):
    1. tactic_setup existiert und hat eine lineup-Dict
    2. Alle erwarteten Formations-Slot-Keys sind vorhanden
    3. Jeder Slot hat eine nicht-leere Player-ID
    4. Alle Player-IDs sind eindeutig (kein Spieler doppelt)
    5. Mindestens ein TW-Slot ist belegt
    6. (Optional) Alle Player-IDs gehören zum übergebenen Verein

    Args:
        tactic_setup: TacticSetup-Instanz oder None
        club:         Club-Instanz für Kader-Zugehörigkeitsprüfung (optional)
    """
    if not tactic_setup:
        return False
    lineup = tactic_setup.lineup or {}
    if not lineup:
        return False

    formation = tactic_setup.formation or default_formation()
    slots = formation_slots(formation)
    expected_keys = {s['key'] for s in slots}

    # 1. Alle erwarteten Slot-Keys vorhanden?
    if not expected_keys.issubset(set(lineup.keys())):
        return False

    # 2. Alle Slots haben eine nicht-leere Player-ID?
    filled_ids = [lineup[k] for k in expected_keys]
    if not all(filled_ids):
        return False

    # 3. Keine Duplikate?
    if len(set(filled_ids)) != len(filled_ids):
        return False

    # 4. Mindestens ein TW-Slot belegt?
    tw_keys = [s['key'] for s in slots if s['code'] == 'TW']
    if not any(lineup.get(k) for k in tw_keys):
        return False

    # 5. Club-Zugehörigkeit: alle Player-IDs im Kader des Vereins?
    if club is not None:
        from .models import Player
        valid_ids = set(
            Player.objects.filter(club=club, pk__in=filled_ids).values_list('pk', flat=True)
        )
        if valid_ids != set(filled_ids):
            return False

    return True


# ── Kernfunktionen ───────────────────────────────────────────────────────────

def _all_valid_formations():
    """Alle Formationskombinationen mit genau 10 Feldspielern (ohne TW)."""
    from itertools import product as iproduct
    results = []
    keys = [list(FORMATION_PARTS[p].keys()) for p in FORMATION_ORDER]
    for combo in iproduct(*keys):
        total = sum(len(FORMATION_PARTS[FORMATION_ORDER[i]][c]) for i, c in enumerate(combo))
        if total == 10:
            results.append(dict(zip(FORMATION_ORDER, combo)))
    return results


def _score_formation(formation_dict, players):
    """Simuliert gieriges HP→NP-Füllen ohne FP.

    Gibt (filled, hp_count, np_count) zurück — Tupel-Vergleich wählt das Beste.
    """
    slots_to_fill = [('TW', 'goalkeeper')]
    for part in FORMATION_ORDER:
        code = formation_dict[part]
        slots_to_fill.extend((pos, part) for pos in FORMATION_PARTS[part][code])

    used = set()
    filled = hp = np_ = 0
    for slot_code, _group in slots_to_fill:
        for p in players:
            if p.pk not in used and slot_code in p.main_positions:
                used.add(p.pk)
                filled += 1
                hp += 1
                break
        else:
            for p in players:
                if p.pk not in used and slot_code in p.secondary_positions:
                    used.add(p.pk)
                    filled += 1
                    np_ += 1
                    break
    return (filled, hp, np_)


def ensure_default_tactic(club):
    """Legt TacticSetup (Pro-Kader) an oder repariert ihn.

    Formationsauswahl: alle gültigen 11-Spieler-Formationen werden bewertet.
    Scoring: maximale HP-Besetzung, dann maximale NP-Besetzung.
    Positionsfremd (FP) wird nie zugewiesen.

    Gibt (tactic_setup, was_changed) zurück.
    Falls der Kader < 11 Spieler hat, wird nichts geändert (was_changed=False).
    """
    from .models import Player, TacticSetup

    tactic, _created = TacticSetup.objects.get_or_create(
        club=club,
        squad_scope=SQUAD_PRO,
        defaults={
            'formation': default_formation(),
            'lineup': {},
            'bench': default_bench(),
            'standards': default_standards(),
            'substitutions': default_substitutions(),
            'first_half': default_half_tactic(),
            'second_half': default_half_tactic(),
            'instructions': default_instructions(),
            'conditions': default_conditions(),
        },
    )

    # Repair: bestehende Taktiken ohne conditions/instructions befüllen
    repair_fields = []
    if not tactic.conditions:
        tactic.conditions = default_conditions()
        repair_fields.append('conditions')
    if not tactic.instructions:
        tactic.instructions = default_instructions()
        repair_fields.append('instructions')
    if repair_fields:
        tactic.save(update_fields=repair_fields)

    players = list(
        Player.objects.filter(club=club).select_related('strength_profile')
    )
    if len(players) < 11:
        return tactic, False

    players.sort(key=_player_base_strength, reverse=True)

    # 1. Beste Formation nach HP/NP-Abdeckung wählen
    best_formation = default_formation()
    best_score = (-1, -1, -1)
    for f in _all_valid_formations():
        score = _score_formation(f, players)
        if score > best_score:
            best_score = score
            best_formation = f

    # 2. Aufstellung mit der besten Formation füllen (HP → NP, nie FP)
    slots = formation_slots(best_formation)
    assigned = {}
    used = set()

    for slot in slots:
        code = slot['code']
        chosen = None
        for p in players:
            if p.pk not in used and code in p.main_positions:
                chosen = p
                break
        if chosen is None:
            for p in players:
                if p.pk not in used and code in p.secondary_positions:
                    chosen = p
                    break
        if chosen is not None:
            assigned[slot['key']] = chosen.pk
            used.add(chosen.pk)

    tactic.formation = best_formation
    tactic.lineup = assigned
    tactic.save(update_fields=['formation', 'lineup', 'updated_at'])
    return tactic, True


def calculate_lineup_strength(lineup, formation, malus=Decimal('1.0')):
    """Berechnet Stärken der Startelf nach Linien mit Per-Spieler-Positionsmalus.

    HP  (Hauptposition)  → 100 % der Basisstärke
    NP  (Nebenposition)  →  90 % der Basisstärke
    FP  (Fremdposition)  →  80 % der Basisstärke  (= LINEUP_MALUS_FACTOR)

    Args:
        lineup:    dict {slot_key: player_id}
        formation: Formation-Dict
        malus:     Zusatz-Multiplikator (z. B. 0.80 für Aufstellungsstrafe)

    Returns:
        dict {goalkeeper, defense, midfield, attack, overall}
        Alle Werte gerundet auf 2 Dezimalstellen.
    """
    from .models import Player, PlayerStrengthProfile

    if not lineup:
        return {k: DUMMY_STRENGTH for k in ('goalkeeper', 'defense', 'midfield', 'attack', 'overall')}

    player_ids = [v for v in lineup.values() if v]

    profiles = {
        p.player_id: p.base_strength or DUMMY_STRENGTH
        for p in PlayerStrengthProfile.objects.filter(player_id__in=player_ids)
    }

    players_pos = {
        p.pk: p
        for p in Player.objects.filter(pk__in=player_ids).only(
            'pk',
            'main_position_1', 'main_position_2', 'main_position_3',
            'secondary_position_1', 'secondary_position_2', 'secondary_position_3',
        )
    }

    slots = formation_slots(formation)
    groups = {'goalkeeper': [], 'defense': [], 'midfield': [], 'attack': []}

    for slot in slots:
        player_id = lineup.get(slot['key'])
        base = profiles.get(player_id, DUMMY_STRENGTH) if player_id else DUMMY_STRENGTH

        if player_id and player_id in players_pos:
            p = players_pos[player_id]
            code = slot['code']
            if code in p.main_positions:
                factor = Decimal('1.0')
            elif code in p.secondary_positions:
                factor = Decimal('0.90')
            else:
                factor = LINEUP_MALUS_FACTOR
        else:
            factor = Decimal('1.0')

        key = _GROUP_KEY.get(slot['group'], 'midfield')
        groups[key].append(base * factor)

    def avg(values):
        if not values:
            return DUMMY_STRENGTH
        return sum(values, Decimal('0')) / len(values)

    result = {k: (avg(v) * malus).quantize(Decimal('0.01')) for k, v in groups.items()}
    all_values = [s for values in groups.values() for s in values]
    result['overall'] = (avg(all_values) * malus).quantize(Decimal('0.01'))
    return result


def calculate_team_strength(club, malus=Decimal('1.0')):
    """Stärke-Berechnung aus der aktuellen TacticSetup des Vereins.

    Returns dict {goalkeeper, defense, midfield, attack, overall} oder
    lauter DUMMY_STRENGTH wenn kein Setup vorhanden.
    """
    from .models import TacticSetup

    empty = {k: DUMMY_STRENGTH for k in ('goalkeeper', 'defense', 'midfield', 'attack', 'overall')}
    try:
        setup = TacticSetup.objects.get(club=club, squad_scope=SQUAD_PRO)
    except TacticSetup.DoesNotExist:
        return empty

    return calculate_lineup_strength(setup.lineup or {}, setup.formation or default_formation(), malus)


# ── Matchday-Hook ────────────────────────────────────────────────────────────

def prepare_matchday_lineups(league, matchday, season):
    """Prüft alle Vereine eines Spieltags und füllt fehlende Aufstellungen auf.

    Für Vereine mit Manager aber ohne Aufstellung:
    - Auto-Aufstellung via ensure_default_tactic
    - InactivityRecord anlegen (Sportgericht)
    - home_lineup_malus / away_lineup_malus auf SeasonFixture setzen

    Returns:
        dict {
          'total':    Anzahl geprüfte Fixtures,
          'filled':   Anzahl gesamt gefüllte/reparierte Aufstellungen,
          'penalized': Anzahl bestrafter Manager,
          'skipped':  Anzahl Vereine mit <11 Spielern (nicht füllbar),
        }
    """
    from .models import InactivityRecord, SeasonFixture, TacticSetup

    fixtures = list(
        SeasonFixture.objects.filter(
            league=league,
            matchday=matchday,
            season=season,
            is_played=False,
        ).select_related('home_club__managed_by', 'away_club__managed_by')
    )

    stats = {'total': len(fixtures), 'filled': 0, 'penalized': 0, 'skipped': 0}

    for fixture in fixtures:
        fixture_dirty = False

        for side, club, malus_attr, lineup_attr in (
            ('home', fixture.home_club, 'home_lineup_malus', 'home_lineup_set'),
            ('away', fixture.away_club, 'away_lineup_malus', 'away_lineup_set'),
        ):
            try:
                setup = TacticSetup.objects.get(club=club, squad_scope=SQUAD_PRO)
                valid = has_valid_lineup(setup, club=club)
            except TacticSetup.DoesNotExist:
                valid = False

            if valid:
                setattr(fixture, lineup_attr, True)
                fixture_dirty = True
                continue

            # Aufstellung fehlt — auffüllen
            _, changed = ensure_default_tactic(club)

            if not changed:
                stats['skipped'] += 1
                continue

            stats['filled'] += 1
            setattr(fixture, lineup_attr, True)
            fixture_dirty = True

            # Strafpunkt + Malus nur für gemanagte Vereine
            manager = club.managed_by
            if manager is not None:
                _, created = InactivityRecord.objects.get_or_create(
                    manager=manager,
                    club=club,
                    squad_scope=SQUAD_PRO,
                    season=str(season),
                    matchday_label=f'Spieltag {matchday}',
                )
                if created:
                    setattr(fixture, malus_attr, True)
                    stats['penalized'] += 1

        if fixture_dirty:
            fixture.save(
                update_fields=[
                    'home_lineup_set', 'away_lineup_set',
                    'home_lineup_malus', 'away_lineup_malus',
                ]
            )

    return stats


def club_readiness_status(club):
    """Schnellcheck für Admin-Übersicht.

    Returns dict:
        player_count, has_tactic, valid_lineup, has_goalkeeper,
        team_strength (overall float), status ('ok'|'warn'|'error')
    """
    from .models import Player, TacticSetup

    player_count = Player.objects.filter(club=club).count()

    try:
        setup = TacticSetup.objects.get(club=club, squad_scope=SQUAD_PRO)
        has_tactic = True
        valid = has_valid_lineup(setup, club=club)
        # TW-Slot direkt aus Lineup ableiten (has_valid_lineup hat schon alle Checks)
        slots = formation_slots(setup.formation or default_formation())
        tw_keys = [s['key'] for s in slots if s['code'] == 'TW']
        has_gk = any(setup.lineup.get(k) for k in tw_keys) if setup.lineup else False
    except TacticSetup.DoesNotExist:
        has_tactic = False
        valid = False
        has_gk = False

    strength = calculate_team_strength(club)
    overall = float(strength.get('overall', DUMMY_STRENGTH))

    if valid and has_gk:
        status = 'ok'
    elif has_tactic:
        status = 'warn'
    else:
        status = 'error'

    return {
        'player_count': player_count,
        'has_tactic': has_tactic,
        'valid_lineup': valid,
        'has_goalkeeper': has_gk,
        'team_strength': round(overall, 1),
        'status': status,
    }
