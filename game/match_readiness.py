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
    SQUAD_PRO,
    default_bench,
    default_formation,
    default_half_tactic,
    default_standards,
    default_substitutions,
    formation_slots,
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

def ensure_default_tactic(club):
    """Legt TacticSetup (Pro-Kader) an oder repariert ihn auf 11 Slots.

    Gibt (tactic_setup, was_changed) zurück.
    Falls der Kader < 11 Spieler hat, wird nichts geändert (was_changed=False).
    """
    from .models import Player, PlayerStrengthProfile, TacticSetup

    formation = default_formation()

    tactic, created = TacticSetup.objects.get_or_create(
        club=club,
        squad_scope=SQUAD_PRO,
        defaults={
            'formation': formation,
            'lineup': {},
            'bench': default_bench(),
            'standards': default_standards(),
            'substitutions': default_substitutions(),
            'first_half': default_half_tactic(),
            'second_half': default_half_tactic(),
        },
    )

    players = list(
        Player.objects.filter(club=club).prefetch_related('strength_profile')
    )

    if len(players) < 11:
        return tactic, False

    # Spieler nach Stärke sortieren (stärkster zuerst)
    players.sort(key=_player_base_strength, reverse=True)

    slots = formation_slots(formation)  # 11 Slots
    tw_slots = [s for s in slots if s['code'] == 'TW']
    field_slots = [s for s in slots if s['code'] != 'TW']

    assigned = {}
    used = set()

    # 1. Torwart-Slot(s) — bevorzugt echte Torhüter
    for slot in tw_slots:
        candidates = [
            p for p in players
            if p.pk not in used and 'TW' in (p.main_positions + p.secondary_positions)
        ]
        if not candidates:
            candidates = [p for p in players if p.pk not in used]
        if candidates:
            chosen = candidates[0]
            assigned[slot['key']] = chosen.pk
            used.add(chosen.pk)

    # 2. Feldspieler — Hauptposition → Nebenposition → beliebiger
    for slot in field_slots:
        code = slot['code']
        candidates = [p for p in players if p.pk not in used and code in p.main_positions]
        if not candidates:
            candidates = [p for p in players if p.pk not in used and code in p.secondary_positions]
        if not candidates:
            candidates = [p for p in players if p.pk not in used]
        if candidates:
            chosen = candidates[0]
            assigned[slot['key']] = chosen.pk
            used.add(chosen.pk)

    tactic.formation = formation
    tactic.lineup = assigned
    tactic.save(update_fields=['formation', 'lineup', 'updated_at'])
    return tactic, True


def calculate_lineup_strength(lineup, formation, malus=Decimal('1.0')):
    """Berechnet Stärken der Startelf nach Linien.

    Args:
        lineup:    dict {slot_key: player_id}
        formation: Formation-Dict
        malus:     Multiplikator (0.80 für -20 %-Strafe)

    Returns:
        dict {goalkeeper, defense, midfield, attack, overall}
        Alle Werte gerundet auf 2 Dezimalstellen.
    """
    from .models import PlayerStrengthProfile

    if not lineup:
        return {k: DUMMY_STRENGTH for k in ('goalkeeper', 'defense', 'midfield', 'attack', 'overall')}

    player_ids = [v for v in lineup.values() if v]
    profiles = {
        p.player_id: p.base_strength or DUMMY_STRENGTH
        for p in PlayerStrengthProfile.objects.filter(player_id__in=player_ids)
    }

    slots = formation_slots(formation)
    groups = {'goalkeeper': [], 'defense': [], 'midfield': [], 'attack': []}

    for slot in slots:
        player_id = lineup.get(slot['key'])
        strength = profiles.get(player_id, DUMMY_STRENGTH) if player_id else DUMMY_STRENGTH
        key = _GROUP_KEY.get(slot['group'], 'midfield')
        groups[key].append(strength)

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
