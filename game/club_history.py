"""Vereinsstationen-Tracking (Phase 0 des Finanzsystems).

Erfasst pro Spieler, Verein und Saison eine Ausbildungsstation
(``PlayerClubHistory``). Grundlage für die spätere Ausbildungsabgabe
(Spec Finanzsystem) und fürs Datencenter.

Regeln:
- Vereinslose Spieler erzeugen keine Zeile.
- Wechsel zum Pseudo-Verein „Karrierende" (Karriereende) erzeugen keine Zeile.
- Creator-/Admin-Edits sind Datenkorrekturen und erzeugen keine Zeile
  (Unterdrückung via ``player._suppress_club_history = True``).
- Beim Saisonwechsel erhalten alle Spieler mit Verein eine Zeile für die
  neue Saison (Snapshot).
"""

import logging

logger = logging.getLogger(__name__)

# Pseudo-Verein für Karriereenden (siehe sync_squads_tm). In Produktions-DB
# pk=1 — in Test-DBs kann pk=1 aber ein regulärer Verein sein, daher wird
# zusätzlich immer der Name geprüft.
KARRIERENDE_CLUB_ID = 1
_KARRIERENDE_NAMES = {'karrierende', 'karriereende'}


def is_career_end_club_id(club_id):
    """True, wenn die Club-ID der Karrierende-Pseudo-Verein ist."""
    if not club_id:
        return False
    from game.models import Club
    name = (
        Club.objects.filter(pk=club_id)
        .values_list('name', flat=True)
        .first()
    )
    if name is None:
        return False
    return name.strip().lower() in _KARRIERENDE_NAMES


def get_current_season():
    """Aktuelle globale Saisonnummer (0, wenn kein Status existiert)."""
    from game.models import GameSeasonState
    state = GameSeasonState.objects.first()
    return state.current_season if state else 0


def record_club_stint(player_id, club_id, season=None):
    """Erfasst eine Vereinsstation (idempotent).

    Gibt True zurück, wenn eine neue Zeile angelegt wurde.
    """
    if not player_id or not club_id:
        return False
    if is_career_end_club_id(club_id):
        return False
    if season is None:
        season = get_current_season()
    from game.models import PlayerClubHistory
    _, created = PlayerClubHistory.objects.get_or_create(
        player_id=player_id,
        club_id=club_id,
        season=season,
    )
    return created


def snapshot_season(season=None):
    """Erfasst für alle Spieler mit Verein eine Station der Saison.

    Idempotent (bestehende Zeilen bleiben unverändert). Gibt die Anzahl
    neu angelegter Zeilen zurück.
    """
    from game.models import Club, Player, PlayerClubHistory

    if season is None:
        season = get_current_season()

    career_end_ids = list(
        Club.objects.filter(pk=KARRIERENDE_CLUB_ID)
        .values_list('pk', 'name')
    )
    excluded_ids = {
        pk for pk, name in career_end_ids
        if (name or '').strip().lower() in _KARRIERENDE_NAMES
    }
    excluded_ids |= set(
        Club.objects.filter(name__iregex=r'^\s*(karrierende|karriereende)\s*$')
        .values_list('pk', flat=True)
    )

    pairs = (
        Player.objects.filter(club__isnull=False)
        .exclude(club_id__in=excluded_ids)
        .values_list('id', 'club_id')
    )
    rows = [
        PlayerClubHistory(player_id=pid, club_id=cid, season=season)
        for pid, cid in pairs
    ]
    if not rows:
        return 0

    before = PlayerClubHistory.objects.filter(season=season).count()
    PlayerClubHistory.objects.bulk_create(rows, ignore_conflicts=True)
    after = PlayerClubHistory.objects.filter(season=season).count()
    return after - before
