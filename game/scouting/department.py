"""Ausbaustufen-Logik der Scoutingabteilung + Kaderlimit-Helfer."""

from .constants import DEPARTMENT_LEVELS, MAX_DEPARTMENT_LEVEL


def level_info(level):
    level = max(0, min(int(level or 0), MAX_DEPARTMENT_LEVEL))
    return DEPARTMENT_LEVELS[level]


def order_cost(level):
    return level_info(level)['order_cost']


def order_duration(level):
    return level_info(level)['duration_days']


def precision(level):
    return level_info(level)['precision']


def can_upgrade(level):
    return int(level or 0) < MAX_DEPARTMENT_LEVEL


def upgrade_cost(level):
    """Kosten, um von ``level`` auf die nächste Stufe auszubauen (None wenn max)."""
    if not can_upgrade(level):
        return None
    return DEPARTMENT_LEVELS[int(level) + 1]['upgrade_cost']


def get_or_create_department(club):
    from game.models import ScoutingDepartment
    dept, _ = ScoutingDepartment.objects.get_or_create(club=club)
    return dept


def effective_squad_limit(club):
    """Kaderlimit des Vereins (delegiert an die Single Source in economy.kader)."""
    from game.economy.kader import effective_squad_limit as _limit
    return _limit(club)
