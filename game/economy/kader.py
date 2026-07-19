"""Kaderlimit-Regeln (Spec Kap. 9.1) — Single Source für Max-/Mindestkader.

Kaderlimit = KADER_MAX_BASIS (EconomyParameter) + NLZ-Aufschlag aus dem
Stadionumfeld-Ausbau (Stadium.nlz_level). Mindestkader = KADER_MIN.
Beides gilt für Manager wie KI (Kaderplatz-Voraussetzung bei Käufen,
Mindestkader-Sperre bei Verkäufen).
"""
from .params import get_param

# Kaderplatz-Aufschlag je NLZ-Stufe (historisch SQUAD_LIMIT_BY_NLZ:
# {0: 60, 1: 63, 2: 66, 3: 70} bei Basis 60).
NLZ_AUFSCHLAG = {0: 0, 1: 3, 2: 6, 3: 10}


def effective_squad_limit(club, saison=None):
    """Maximale Kadergröße des Vereins (Basis + Umfeld-Erweiterung)."""
    basis = int(get_param('KADER_MAX_BASIS', saison))
    stadium = getattr(club, 'stadium', None)
    nlz_level = int(getattr(stadium, 'nlz_level', 0) or 0)
    return basis + NLZ_AUFSCHLAG.get(nlz_level, NLZ_AUFSCHLAG[max(NLZ_AUFSCHLAG)])


def min_squad_size(saison=None):
    """Mindestkader (Verkäufe darunter sind blockiert — Manager wie KI)."""
    return int(get_param('KADER_MIN', saison))


def squad_count(club):
    """Aktuelle Kadergröße (Spieler mit diesem WSC-Verein)."""
    from game.models import Player
    return Player.objects.filter(club=club).count()
