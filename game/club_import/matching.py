"""Erkennung bestehender Spieler in der DB (Spec §21).

Priorität:
    1. Transfermarkt-Spieler-ID
    2. FMInside-ID
    3. SoFIFA-ID (über PlayerExternalId)
    4. normalisierter Name + identisches Geburtsdatum → nur Dublettenwarnung

Ein Treffer allein über Name+Geburtsdatum führt NICHT zu automatischem
Überschreiben (``is_strong=False``).
"""

from datetime import date

from .normalization import normalize_name


def _coerce_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def find_existing_player(tm_player_id=None, fm_inside_id=None,
                         sofifa_id=None, name=None, date_of_birth=None):
    """Sucht einen bestehenden Spieler nach ID-Priorität, dann Name+Geburtsdatum.

    Returns:
        dict mit:
            player      — Player-Instanz oder ``None``
            match_type  — 'tm' | 'fmi' | 'sofifa' | 'name_dob' | None
            is_strong   — bool: True bei eindeutigem ID-Treffer (auto-überschreibbar)
    """
    from ..models import DataSource, Player, PlayerExternalId

    if tm_player_id:
        player = Player.objects.filter(transfermarkt_id=tm_player_id).first()
        if player:
            return {'player': player, 'match_type': 'tm', 'is_strong': True}

    if fm_inside_id:
        player = Player.objects.filter(fm_inside_id=fm_inside_id).first()
        if player:
            return {'player': player, 'match_type': 'fmi', 'is_strong': True}

    if sofifa_id:
        ext = (
            PlayerExternalId.objects
            .filter(source__code=DataSource.CODE_SOFIFA,
                    external_id=str(sofifa_id))
            .select_related('player')
            .first()
        )
        if ext and ext.player_id:
            return {'player': ext.player, 'match_type': 'sofifa', 'is_strong': True}

    dob = _coerce_date(date_of_birth)
    if name and dob:
        target = normalize_name(name)
        if target:
            for player in Player.objects.filter(date_of_birth=dob):
                if normalize_name(player.full_name) == target:
                    return {
                        'player': player,
                        'match_type': 'name_dob',
                        'is_strong': False,
                    }

    return {'player': None, 'match_type': None, 'is_strong': False}
