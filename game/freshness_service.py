"""Frische-/Belastungsmodell V1.

Konstanten eingefroren. Änderung nur mit Evidenz aus ≥10 Saisons + expliziter
Nutzer-Freigabe (analog zum Match-Engine-V2-Freeze).

Wichtige Designentscheidungen:
- fatigue_cost stammt aus dem Taktik-Compiler (0.80–1.50); er enthält bereits
  Pressing, Tempo, Attack-Focus und Condition-Plan-Gewichtung → keine
  Doppel-Implementierung.
- Ausdauer reduziert den Frischeverlust (je besser, desto weniger Verlust).
- Trainingsgelände reduziert Verlust (Stufe ≥ 2) und erhöht Regeneration (Stufe 3).
- Medizinzentrum senkt das Verletzungsrisiko, beeinflusst Frische NICHT.
- Frische-Leistungsmalus greift erst unter 80 — ein müder Star schlägt
  meistens noch einen frischen Durchschnittsspieler.
"""
from __future__ import annotations

from decimal import Decimal

# ── V1-Konstanten (eingefroren) ───────────────────────────────────────────────
BASE_MATCH_FITNESS_LOSS: float = 9.0
BASE_DAILY_RECOVERY: float = 4.0
MATCHDAY_REST_BONUS: float = 2.0          # kein Einsatz am Spieltag
SHORT_APPEARANCE_REST_BONUS: float = 1.0   # ≤ 30 Minuten gespielt
TRAINING_GROUND_S2_LOSS_REDUCTION: float = 1.5
TRAINING_GROUND_S3_DAILY_RECOVERY: float = 1.5
BASE_INJURY_RISK_PER_90: float = 0.009

MIN_FRESHNESS: int = 0
MAX_FRESHNESS: int = 100
INJURY_COMEBACK_FRESHNESS: int = 40   # Frische nach Verletzungsende (Mindestwert beim Comeback)

# ── Positionsfaktoren ─────────────────────────────────────────────────────────
_POSITION_LOSS_FACTOR: dict[str, float] = {
    'TW':  0.45,
    'IV':  0.85,
    'LV':  1.05, 'RV':  1.05,
    'LOV': 1.12, 'ROV': 1.12,
    'DM':  1.00,
    'ZM':  1.08,
    'OM':  1.08,
    'LM':  1.10, 'RM':  1.10,
    'LF':  1.12, 'RF':  1.12,
    'ST':  0.98,
}

# ── Frische → Verletzungsrisiko-Multiplikator ─────────────────────────────────
# Format: (min_freshness_inclusive, max_freshness_inclusive, factor)
_FRESHNESS_INJURY_TIERS: list[tuple[int, int, float]] = [
    (90, 100, 1.00),
    (80,  89, 1.05),
    (70,  79, 1.15),
    (60,  69, 1.35),
    (50,  59, 1.70),
    ( 0,  49, 2.30),
]

# ── Medizin-Stufe → Verletzungsrisiko-Multiplikator ───────────────────────────
MEDIZIN_INJURY_FACTOR: dict[int, float] = {
    0: 1.00,
    1: 0.95,
    2: 0.90,
    3: 0.80,
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def freshness_injury_multiplier(freshness: int) -> float:
    """Verletzungsrisiko-Multiplikator basierend auf aktueller Frische."""
    for lo, hi, factor in _FRESHNESS_INJURY_TIERS:
        if lo <= freshness <= hi:
            return factor
    return 2.30


def freshness_performance_factor(freshness: int) -> float:
    """Leistungs-Multiplikator für _draw_match_strength.

    Frische ≥ 80 → kein Malus.
    Erst unter 80 spürbar, damit ein müder Star im Normalfall noch besser ist
    als ein frischer Durchschnittsspieler.
    """
    if freshness >= 80:
        return 1.00
    if freshness >= 70:
        return 0.985   # -1.5 % (Mitte des 1–2 %-Bandes)
    if freshness >= 60:
        return 0.96    # -4 %
    if freshness >= 50:
        return 0.93    # -7 %
    return 0.88        # -12 %


def _ausdauer_factor(ausdauer: int | None) -> float:
    """Ausdauer → Frischeverlust-Faktor.

    Formel: clamp(1 − ((ausdauer − 70) × 0.005), 0.86, 1.12)
    Ausdauer 70 = neutral (1.0), 100 ≈ 0.85, 40 ≈ 1.15.
    """
    if ausdauer is None:
        return 1.0
    return max(0.86, min(1.12, 1.0 - ((ausdauer - 70) * 0.005)))


def compute_single_player_loss(
    position: str,
    ausdauer: int | None,
    fatigue_cost: float,
    training_level: int,
    minutes: int = 90,
) -> float:
    """Frischeverlust für einen Spieler nach einem Spiel.

    Args:
        position:       Slot-Code (z.B. 'ZM', 'IV', 'TW')
        ausdauer:       Spieler-Ausdauerwert (0–99), None = neutral
        fatigue_cost:   Taktik-Compilers fatigue_cost (1.0 = normal)
        training_level: Club.training_level (0–3)
        minutes:        Gespielte Minuten (0–120+)

    Returns:
        Frischeverlust als positive Zahl. 0.0 wenn minutes == 0.
    """
    minute_factor = max(0.0, minutes / 90.0)
    if minute_factor == 0.0:
        return 0.0

    pos_factor = _POSITION_LOSS_FACTOR.get(position, 1.0)
    aud_factor = _ausdauer_factor(ausdauer)

    loss = BASE_MATCH_FITNESS_LOSS * minute_factor * pos_factor * aud_factor * fatigue_cost

    if training_level >= 2:
        loss -= TRAINING_GROUND_S2_LOSS_REDUCTION

    is_gk = (position == 'TW')
    loss = max(1.0 if is_gk else 3.0, loss)
    loss = min(18.0, loss)

    return round(loss, 2)


def _stadium_level(club, attr: str) -> int:
    """Gibt club.stadium.<attr> zurück, 0 bei fehlendem Stadium."""
    try:
        return int(getattr(club.stadium, attr, 0) or 0)
    except Exception:
        return 0


def apply_match_freshness_losses(
    home_players: list[dict],
    away_players: list[dict],
    home_club,
    away_club,
    fatigue_cost_home: float = 1.0,
    fatigue_cost_away: float = 1.0,
) -> None:
    """Schreibt Frischeverlust nach einem Spiel auf alle beteiligten Spieler.

    home_players / away_players: Liste aus report_data (aus _player_row).
    Jeder Eintrag hat mindestens 'id' und 'position'.
    Verletzt keine Frische-Untergrenze unter 0.
    """
    from .models import Player, PlayerStrengthProfile

    def _collect_losses(
        players: list[dict],
        club,
        fatigue_cost: float,
    ) -> dict[int, float]:
        from .models import PlayerSourceRating
        training_level = _stadium_level(club, 'training_level')
        pids = [p['id'] for p in players if p.get('id')]
        if not pids:
            return {}
        # Ausdauer aus PlayerSourceRating (EA bevorzugt, FM als Fallback, None = 70 neutral)
        ausdauer_qs = (
            PlayerSourceRating.objects
            .filter(player_id__in=pids, ausdauer__isnull=False)
            .values('player_id', 'ausdauer', 'source')
        )
        ausdauer_map: dict[int, int] = {}
        for row in ausdauer_qs:
            pid = row['player_id']
            if pid not in ausdauer_map or row['source'] == 'EA':
                ausdauer_map[pid] = int(row['ausdauer'])

        losses: dict[int, float] = {}
        for p in players:
            pid = p.get('id')
            if not pid:
                continue
            position = p.get('position') or 'ZM'
            ausdauer = ausdauer_map.get(pid)   # None → neutral in compute_single_player_loss
            minutes = int(p.get('minutes_played', 90) or 90)
            losses[pid] = compute_single_player_loss(
                position=position,
                ausdauer=ausdauer,
                fatigue_cost=fatigue_cost,
                training_level=training_level,
                minutes=minutes,
            )
        return losses

    home_losses = _collect_losses(home_players, home_club, fatigue_cost_home)
    away_losses = _collect_losses(away_players, away_club, fatigue_cost_away)
    all_losses: dict[int, float] = {**home_losses, **away_losses}

    if not all_losses:
        return

    profiles = list(
        PlayerStrengthProfile.objects.filter(player_id__in=all_losses.keys())
    )

    updates: list[PlayerStrengthProfile] = []
    for sp in profiles:
        loss = all_losses.get(sp.player_id, 0.0)
        if loss <= 0.0:
            continue
        current = sp.freshness if sp.freshness is not None else Decimal('100.00')
        new_freshness = max(
            Decimal(str(MIN_FRESHNESS)),
            current - Decimal(str(loss)),
        )
        if new_freshness != current:
            sp.freshness = new_freshness
            updates.append(sp)

    if updates:
        PlayerStrengthProfile.objects.bulk_update(updates, ['freshness'])


def daily_recovery_amount(current_freshness: float, training_level: int = 0) -> float:
    """Tägliche Regenerationsmenge abhängig von aktueller Frische.

    Hohe Frische → gedämpfte Regeneration (natürlicher Sättigungseffekt):
      90–100: 50 % der Basisregeneration
      80– 89: 75 % der Basisregeneration
       0– 79: 100 % der Basisregeneration (volle Erholung bei Erschöpfung)

    Trainingsgelände S3 addiert TRAINING_GROUND_S3_DAILY_RECOVERY auf die
    bereits gedämpfte Menge (Bonus greift immer voll, unabhängig von Frische).
    """
    base = BASE_DAILY_RECOVERY
    if current_freshness >= 90:
        recovery = base * 0.50
    elif current_freshness >= 80:
        recovery = base * 0.75
    else:
        recovery = base

    if training_level >= 3:
        recovery += TRAINING_GROUND_S3_DAILY_RECOVERY

    return round(recovery, 4)


def apply_daily_recovery() -> int:
    """Tägliche Frische-Regeneration für alle nicht-verletzten Spieler.

    Skippt Spieler mit Frische = 100 (bereits voll).
    Berücksichtigt Club.training_level für den Regenerationsbonus.
    Verwendet daily_recovery_amount() — gedämpfte Regeneration bei hoher Frische.

    Returns:
        Anzahl aktualisierter PlayerStrengthProfile-Einträge.
    """
    from .models import PlayerStrengthProfile

    profiles = list(
        PlayerStrengthProfile.objects
        .filter(player__ws_injury_days_remaining__lte=0)
        .exclude(freshness__gte=Decimal(str(MAX_FRESHNESS)))
        .select_related('player__club__stadium')
    )

    updates: list[PlayerStrengthProfile] = []
    for sp in profiles:
        club = getattr(sp.player, 'club', None)
        t_level = _stadium_level(club, 'training_level') if club else 0

        current = sp.freshness if sp.freshness is not None else Decimal('0.00')
        recovery = Decimal(str(daily_recovery_amount(float(current), t_level)))
        new_freshness = min(Decimal(str(MAX_FRESHNESS)), current + recovery)
        if new_freshness != current:
            sp.freshness = new_freshness
            updates.append(sp)

    if updates:
        PlayerStrengthProfile.objects.bulk_update(updates, ['freshness'])

    return len(updates)


def apply_injury_countdown() -> tuple[int, int]:
    """Täglicher Verletzungs-Countdown: dekrementiert ws_injury_days_remaining.

    Für jeden verletzten Spieler (ws_injury_days_remaining > 0):
    - ws_injury_days_remaining wird um 1 reduziert.
    - Erreicht der Wert 0, wird die Verletzung gelöscht (ws_injury_type='')
      und die Frische auf INJURY_COMEBACK_FRESHNESS gesetzt, sofern sie darunter liegt.

    Returns:
        (decremented, healed) — Anzahl dekrementierter Spieler, davon genesen.
    """
    from .models import Player, PlayerStrengthProfile

    injured_players = list(
        Player.objects.filter(ws_injury_days_remaining__gt=0)
        .only('id', 'ws_injury_days_remaining', 'ws_injury_type')
    )

    if not injured_players:
        return 0, 0

    decremented = 0
    healed_ids: list[int] = []
    player_updates: list[Player] = []

    for player in injured_players:
        new_days = player.ws_injury_days_remaining - 1
        player.ws_injury_days_remaining = new_days
        decremented += 1
        if new_days <= 0:
            player.ws_injury_days_remaining = 0
            player.ws_injury_type = ''
            healed_ids.append(player.pk)
        player_updates.append(player)

    Player.objects.bulk_update(
        player_updates,
        ['ws_injury_days_remaining', 'ws_injury_type'],
    )

    if healed_ids:
        comeback_threshold = Decimal(str(INJURY_COMEBACK_FRESHNESS))
        profiles = list(
            PlayerStrengthProfile.objects.filter(player_id__in=healed_ids)
        )
        profile_updates: list[PlayerStrengthProfile] = []
        for sp in profiles:
            current = sp.freshness if sp.freshness is not None else Decimal('0.00')
            if current < comeback_threshold:
                sp.freshness = comeback_threshold
                profile_updates.append(sp)
        if profile_updates:
            PlayerStrengthProfile.objects.bulk_update(profile_updates, ['freshness'])

    return decremented, len(healed_ids)
