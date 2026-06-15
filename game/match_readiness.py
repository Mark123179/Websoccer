"""Match-Readiness: Taktik & Stärke

Dieses Modul stellt vier Hauptfunktionen bereit:

- ensure_default_tactic(club)       — legt/repariert TacticSetup mit 11 Slots (nur trainerlose Vereine)
- patch_managed_lineup(club, setup) — flickt Verletzungen/Sperren/Abgänge in Aufstellung gemanagter Vereine
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

    Gibt (filled, hp_count, np_count, effective_strength) zurück.
    Tupel-Vergleich wählt die beste Formation:
      1. maximale Slot-Abdeckung
      2. maximale HP-Besetzung
      3. maximale NP-Besetzung
      4. höchste positionsgewichtete Gesamtstärke (Tiebreaker)

    effective_strength: Summe der Spielerstärken gewichtet nach Positions-Match
        HP-Slot → base_strength × 1.0
        NP-Slot → base_strength × 0.9
    """
    slots_to_fill = [('TW', 'goalkeeper')]
    for part in FORMATION_ORDER:
        code = formation_dict[part]
        slots_to_fill.extend((pos, part) for pos in FORMATION_PARTS[part][code])

    used = set()
    filled = hp = np_ = 0
    effective_strength = 0.0
    for slot_code, _group in slots_to_fill:
        for p in players:
            if p.pk not in used and slot_code in p.main_positions:
                used.add(p.pk)
                filled += 1
                hp += 1
                effective_strength += float(_player_base_strength(p))
                break
        else:
            for p in players:
                if p.pk not in used and slot_code in p.secondary_positions:
                    used.add(p.pk)
                    filled += 1
                    np_ += 1
                    effective_strength += float(_player_base_strength(p)) * 0.9
                    break
    return (filled, hp, np_, effective_strength)


# ── Positionsgruppen für Bank-Vielfalt ───────────────────────────────────────
# Primärposition → Vielfalt-Kategorie ('goalkeeper'|'defense'|'midfield'|'attack')
_POS_CATEGORY = {
    'TW':  'goalkeeper',
    'IV':  'defense',  'LV': 'defense',  'RV':  'defense',
    'LOV': 'defense',  'ROV': 'defense',
    'DM':  'midfield', 'ZM': 'midfield', 'LM':  'midfield',
    'RM':  'midfield', 'LA': 'midfield', 'RA':  'midfield',
    'OM':  'midfield',
    'ST':  'attack',   'LF': 'attack',   'RF':  'attack',
    'MS':  'attack',
}

_DIVERSITY_GROUPS = ('defense', 'midfield', 'attack')


def _has_valid_bench(bench, squad_pks, injured_pks):
    """Prüft ob die Bank noch valide ist.

    Valide wenn:
    - Nicht leer
    - Alle PKs gehören noch zum Kader des Vereins
    - Kein Bankspieler ist verletzt (ws_injured)

    Args:
        bench:        Liste von Player-PKs (TacticSetup.bench)
        squad_pks:    Menge aller Spieler-PKs des Vereins
        injured_pks:  Menge der verletzten Spieler-PKs des Vereins

    Returns:
        True  → Bank ist gültig, manuell gesetzte Bänke bleiben unberührt
        False → Bank muss neu aufgebaut werden
    """
    if not bench:
        return False
    bench_set = set(bench)
    if not bench_set.issubset(squad_pks):
        return False
    if bench_set & injured_pks:
        return False
    return True


def _build_bench(players, used_pks, max_bench=7):
    """Wählt Bankspieler aus nicht gestarteten Spielern.

    Strategie (Reihenfolge):
      1. 1 Ersatztorwart (falls vorhanden)
      2. Je 1 Spieler aus Abwehr, Mittelfeld, Angriff (Positionsvielfalt)
      3. Restliche Plätze nach Stärke auffüllen (bis max_bench)

    Args:
        players:   Alle Spieler des Vereins, absteigend nach Stärke sortiert.
        used_pks:  Menge der PKs, die bereits in der Startelf stehen.
        max_bench: Maximale Bankgröße (Standard 7).

    Returns:
        Liste von Player-PKs für die Bank (ohne Duplikate, ohne Starter).
    """
    reserves = [p for p in players if p.pk not in used_pks]
    bench_pks: list[int] = []
    bench_set: set[int] = set()

    def _add(pk):
        bench_pks.append(pk)
        bench_set.add(pk)

    # 1. Ersatztorwart
    for p in reserves:
        if len(bench_pks) >= max_bench:
            break
        cat = _POS_CATEGORY.get(getattr(p, 'primary_position', '') or '', '')
        if cat == 'goalkeeper':
            _add(p.pk)
            break

    # 2. Positionsvielfalt: je 1 Abwehr, Mittelfeld, Angriff
    for group in _DIVERSITY_GROUPS:
        if len(bench_pks) >= max_bench:
            break
        for p in reserves:
            if p.pk in bench_set:
                continue
            cat = _POS_CATEGORY.get(getattr(p, 'primary_position', '') or '', '')
            if cat == group:
                _add(p.pk)
                break

    # 3. Restliche Plätze nach Stärke (Reihenfolge der reserves = absteigend)
    for p in reserves:
        if len(bench_pks) >= max_bench:
            break
        if p.pk not in bench_set:
            _add(p.pk)

    return bench_pks


def ensure_default_tactic(club):
    """Legt TacticSetup (Pro-Kader) an oder repariert ihn.

    Formationsauswahl: alle gültigen 11-Spieler-Formationen werden bewertet.
    Scoring: maximale HP-Besetzung, dann maximale NP-Besetzung.
    Positionsfremd (FP) wird nie zugewiesen.
    Bank: bester Ersatztorwart + je 1 Abwehr/Mittelfeld/Angriff + Stärke-Füller.

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

    all_players = list(
        Player.objects.filter(club=club).select_related('strength_profile')
    )
    # Verletzte Spieler sind nicht aufstellbar
    players = [p for p in all_players if not p.is_ws_injured]
    if len(players) < 11:
        return tactic, False

    players.sort(key=_player_base_strength, reverse=True)

    # 1. Beste Formation nach HP/NP-Abdeckung wählen (Tiebreaker: effektive Stärke)
    best_formation = default_formation()
    best_score = (-1, -1, -1, -1.0)
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

    # 3. Bank mit besten Reservespielern füllen (Vielfalt + Stärke)
    bench = _build_bench(players, used)

    tactic.formation = best_formation
    tactic.lineup = assigned
    tactic.bench = bench
    tactic.save(update_fields=['formation', 'lineup', 'bench', 'updated_at'])
    return tactic, True


def ensure_default_bench(setup):
    """Füllt die Bank automatisch, wenn sie noch leer ist.

    Nutzt die bereits gespeicherte Aufstellung als Basis für die used_pks,
    damit kein Startelfspieler auf der Bank landet.
    Berührt die Aufstellung (lineup) nicht.

    Args:
        setup: TacticSetup-Instanz (wird ggf. in-place geändert und gespeichert)

    Returns:
        True wenn die Bank neu befüllt wurde, False wenn sie bereits Einträge hat
        oder keine Spieler verfügbar sind.
    """
    if setup.bench:
        return False

    club = setup.club
    from .models import Player

    players = list(
        Player.objects.filter(club=club).select_related('strength_profile')
    )
    if not players:
        return False

    players.sort(key=_player_base_strength, reverse=True)

    used_pks = {pk for pk in (setup.lineup or {}).values() if pk}
    bench = _build_bench(players, used_pks)

    if not bench:
        return False

    setup.bench = bench
    setup.save(update_fields=['bench', 'updated_at'])
    return True


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


def _compute_zone_strengths_for_setup(tactic_setup) -> dict:
    """Baut ein minimales Team-Dict und berechnet Zonenstärken (links/mitte/rechts).

    Verwendet base_strength als Annäherung an final_strength (keine Tagesform).
    Gibt das Resultat von calculate_zone_strengths zurück.
    """
    from .models import PlayerStrengthProfile
    from .tactic_compiler import calculate_zone_strengths

    lineup_map = tactic_setup.lineup or {}
    formation  = tactic_setup.formation or default_formation()
    slots      = formation_slots(formation)

    player_ids = [lineup_map.get(s['key']) for s in slots if lineup_map.get(s['key'])]

    profiles: dict = {}
    if player_ids:
        for sp in PlayerStrengthProfile.objects.filter(
            player_id__in=player_ids
        ).only('player_id', 'base_strength'):
            profiles[sp.player_id] = float(sp.base_strength or 50.0)

    players_list = [
        {'id': pid, 'final_strength': profiles.get(pid, 50.0)}
        for pid in dict.fromkeys(player_ids)   # preserves order, deduplicates
        if pid
    ]
    lineup_list = [
        {'player_id': lineup_map.get(s['key']), 'position': s['code']}
        for s in slots if lineup_map.get(s['key'])
    ]
    return calculate_zone_strengths({'players': players_list, 'lineup': lineup_list})


def apply_default_tactic_settings(own_setup, opp_setup) -> str:
    """Setzt first_half, second_half, instructions, conditions via Default-Taktik V1.

    Nur für trainerlose Vereine aufzurufen (nach ensure_default_tactic).
    Gibt die ermittelte Kategorie zurück ('clear_underdog' … 'clear_favorite').

    Args:
        own_setup: TacticSetup-Instanz des eigenen Vereins (wird gespeichert)
        opp_setup: TacticSetup-Instanz des Gegners (nur gelesen)
    """
    from .default_tactics import generate_default_tactic

    own_str_raw = calculate_lineup_strength(
        own_setup.lineup or {}, own_setup.formation or default_formation()
    )
    opp_str_raw = calculate_lineup_strength(
        opp_setup.lineup or {}, opp_setup.formation or default_formation()
    )
    own_str = {k: float(v) for k, v in own_str_raw.items()}
    opp_str = {k: float(v) for k, v in opp_str_raw.items()}

    own_zones = _compute_zone_strengths_for_setup(own_setup)
    opp_zones = _compute_zone_strengths_for_setup(opp_setup)

    result = generate_default_tactic(own_str, opp_str, own_zones, opp_zones)

    own_setup.first_half   = result['first_half']
    own_setup.second_half  = result['second_half']
    own_setup.instructions = result['instructions']
    own_setup.conditions   = result['conditions']
    own_setup.save(update_fields=['first_half', 'second_half', 'instructions', 'conditions', 'updated_at'])

    return result['category']


def patch_managed_lineup(club, setup) -> tuple:
    """Flickt die Aufstellung eines gemanagten Vereins für den Spieltag.

    Entfernt Spieler die nicht mehr verfügbar sind (Abgang, Verletzung oder
    Sperre) und ersetzt Lücken mit dem besten verfügbaren Alternativspieler
    (HP-Priorität → NP-Priorität → Stärkster Verbleibender).
    Formation und Taktikvorgaben des Trainers bleiben unverändert.

    Wird sowohl für Nichtaufstellungen (mit Stärkemalus) als auch für das
    stille Patchen gültiger Aufstellungen vor einem Spieltag verwendet.

    Returns (setup, was_patched: bool).
    """
    from .models import Player

    all_players = list(
        Player.objects.filter(club=club).select_related('strength_profile')
    )
    squad_pks = {p.pk for p in all_players}
    unavailable_pks = {
        p.pk for p in all_players
        if p.is_ws_injured or p.is_ws_suspended
    }
    all_players.sort(key=_player_base_strength, reverse=True)
    available = [p for p in all_players if p.pk not in unavailable_pks]

    lineup = dict(setup.lineup or {})
    formation = setup.formation or default_formation()
    slots = formation_slots(formation)

    # Welche Spieler sind aktuell korrekt im Lineup (im Kader, verfügbar, kein Duplikat)?
    used: set[int] = set()
    first_seen: dict[int, str] = {}
    for slot in slots:
        key = slot['key']
        pid = lineup.get(key)
        if pid and pid in squad_pks and pid not in unavailable_pks and pid not in first_seen:
            used.add(pid)
            first_seen[pid] = key

    was_patched = False

    for slot in slots:
        key = slot['key']
        code = slot['code']
        current_pid = lineup.get(key)

        # Spieler gültig (im Kader, verfügbar, nicht doppelt)?
        if (
            current_pid
            and current_pid in squad_pks
            and current_pid not in unavailable_pks
            and first_seen.get(current_pid) == key
        ):
            continue

        # Ersatz finden: HP → NP → Stärkster
        chosen = None
        for p in available:
            if p.pk not in used and code in p.main_positions:
                chosen = p
                break
        if chosen is None:
            for p in available:
                if p.pk not in used and code in p.secondary_positions:
                    chosen = p
                    break
        if chosen is None:
            for p in available:
                if p.pk not in used:
                    chosen = p
                    break

        new_pid = chosen.pk if chosen else None
        lineup[key] = new_pid
        if new_pid:
            used.add(new_pid)
            first_seen[new_pid] = key
        was_patched = True

    if was_patched:
        setup.lineup = lineup
        setup.save(update_fields=['lineup', 'updated_at'])

    return setup, was_patched


# ── Matchday-Hook ────────────────────────────────────────────────────────────

def prepare_matchday_lineups(league, matchday, season):
    """Prüft alle Vereine eines Spieltags und stellt Spielbereitschaft her.

    Regelwerk:
    - Trainerloser Verein ohne Aufstellung → ensure_default_tactic (automatisch optimal)
    - Gemanagter Verein mit gültiger Aufstellung → patch_managed_lineup (still, kein Malus)
    - Gemanagter Verein ohne gültige Aufstellung (Nichtaufstellung) →
        patch_managed_lineup auf letzte Aufstellung + InactivityRecord + Stärkemalus

    Zusätzlich wird bei jedem Spieltag die Bank jedes Vereins geprüft:
    - Leere Bänke oder Bänke mit Spielern, die nicht mehr im Kader sind oder
      verletzt sind (ws_injured), werden automatisch via _build_bench neu befüllt.
    - Manuell gesetzte Bänke mit ausschließlich gültigen Spielern bleiben unberührt.

    Returns:
        dict {
          'total':         Anzahl geprüfte Fixtures,
          'filled':        Anzahl gesamt gefüllte/reparierte Aufstellungen,
          'penalized':     Anzahl bestrafter Manager (Nichtaufstellung),
          'skipped':       Anzahl Vereine mit <11 Spielern (nicht füllbar),
          'bench_rebuilt': Anzahl Bänke, die automatisch neu aufgebaut wurden,
        }
    """
    from .models import InactivityRecord, Player, SeasonFixture, TacticSetup

    fixtures = list(
        SeasonFixture.objects.filter(
            league=league,
            matchday=matchday,
            season=season,
            is_played=False,
        ).select_related('home_club__managed_by', 'away_club__managed_by')
    )

    stats = {'total': len(fixtures), 'filled': 0, 'penalized': 0, 'skipped': 0, 'bench_rebuilt': 0}

    for fixture in fixtures:
        fixture_dirty = False

        for side, club, malus_attr, lineup_attr in (
            ('home', fixture.home_club, 'home_lineup_malus', 'home_lineup_set'),
            ('away', fixture.away_club, 'away_lineup_malus', 'away_lineup_set'),
        ):
            setup = None
            try:
                setup = TacticSetup.objects.get(club=club, squad_scope=SQUAD_PRO)
                valid = has_valid_lineup(setup, club=club)
            except TacticSetup.DoesNotExist:
                valid = False

            if valid:
                setattr(fixture, lineup_attr, True)
                fixture_dirty = True

                # Bank-Validierung: ungültige/leere Bänke automatisch neu aufbauen.
                # Manuell gesetzte Bänke mit ausschließlich gültigen Spielern bleiben unberührt.
                squad_qs = Player.objects.filter(club=club)
                squad_pks = set(squad_qs.values_list('pk', flat=True))
                injured_pks = set(
                    squad_qs.filter(
                        ws_injury_type__isnull=False,
                        ws_injury_days_remaining__gt=0,
                    ).exclude(ws_injury_type='').values_list('pk', flat=True)
                )
                if not _has_valid_bench(setup.bench or [], squad_pks, injured_pks):
                    all_players = list(
                        squad_qs.select_related('strength_profile')
                    )
                    all_players.sort(key=_player_base_strength, reverse=True)
                    # Verletzte Spieler aus dem Kandidaten-Pool ausschließen,
                    # damit die neu aufgebaute Bank garantiert keine Verletzten enthält.
                    available_players = [p for p in all_players if p.pk not in injured_pks]
                    used_pks = set((setup.lineup or {}).values())
                    setup.bench = _build_bench(available_players, used_pks)
                    setup.save(update_fields=['bench', 'updated_at'])
                    stats['bench_rebuilt'] += 1

                continue

            # ── Aufstellung fehlt oder ungültig ──────────────────────────────
            manager = club.managed_by

            if manager is None:
                # Trainerloser Verein: optimal auto-auffüllen, kein Strafpunkt.
                _, changed = ensure_default_tactic(club)
                if not changed:
                    stats['skipped'] += 1
                    continue
            else:
                # Gemanagter Verein (Nichtaufstellung): letzte Aufstellung patchen.
                # Kein ensure_default_tactic — Trainer muss selbst aufstellen.
                if setup is None:
                    setup, _ = TacticSetup.objects.get_or_create(
                        club=club,
                        squad_scope=SQUAD_PRO,
                        defaults={
                            'formation': default_formation(),
                            'lineup': {},
                            'bench': [],
                        },
                    )
                patch_managed_lineup(club, setup)

                # Sportgericht-Strafpunkt + Stärkemalus (30 %)
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

            stats['filled'] += 1
            setattr(fixture, lineup_attr, True)
            fixture_dirty = True

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
