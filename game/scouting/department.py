"""Ausbaustufen-Logik der Scoutingabteilung + Kaderlimit-Helfer."""

from .constants import DEPARTMENT_LEVELS, MAX_DEPARTMENT_LEVEL

# Kaderlimit nach NLZ-Stufe (siehe FACILITY_DATA in views_management.py).
SQUAD_LIMIT_BY_NLZ = {0: 60, 1: 63, 2: 66, 3: 70}


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
    """Kaderlimit des Vereins anhand der NLZ-Stufe."""
    stadium = getattr(club, 'stadium', None)
    nlz_level = getattr(stadium, 'nlz_level', 0) or 0
    return SQUAD_LIMIT_BY_NLZ.get(int(nlz_level), 60)
