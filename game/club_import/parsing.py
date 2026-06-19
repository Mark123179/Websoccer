"""Wert-Parsing für Transfermarkt-Rohtexte (Spec §9.1).

Wandelt formatierte Transfermarkt-Texte in saubere DB-Werte um:
    "1,93 m"        → 193   (Zentimeter)
    "35,00 Mio. €"  → 35000000  (ganzzahliger Euro)
    "500 Tsd. €"    → 500000
    "linksfuß"      → "L"

Wichtig: Fehlende/unparsbare Werte ergeben ``None`` bzw. ``''`` — niemals ``0``.
Eine ``0`` wäre ein echter Wert und würde den Stärke-Rechner verfälschen.
"""

import re

_MULTIPLIERS = (
    ('mrd', 1_000_000_000),
    ('mio', 1_000_000),
    ('tsd', 1_000),
)


def parse_height(value):
    """"1,93 m" / "193 cm" / "193" → 193 (cm-Integer). Sonst ``None``."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(round(value)) if value else None
    s = str(value).strip().lower().replace('\xa0', ' ')
    if not s:
        return None
    # Meterangabe mit Dezimaltrenner, z. B. "1,93" oder "1.93".
    m = re.search(r'(\d+)[.,](\d+)', s)
    if m:
        meters = float(f'{m.group(1)}.{m.group(2)}')
        return int(round(meters * 100))
    m = re.search(r'(\d+)', s)
    if m:
        n = int(m.group(1))
        return n if n >= 100 else None
    return None


def parse_market_value(value):
    """"35,00 Mio. €" → 35000000, "500 Tsd. €" → 500000. Sonst ``None``.

    Niemals ``0`` als Fallback — ein fehlender Marktwert bleibt ``None``.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(round(value))
    s = str(value).strip().lower().replace('€', '').replace('\xa0', ' ')
    if not s:
        return None

    multiplier = 1
    for token, factor in _MULTIPLIERS:
        if token in s:
            multiplier = factor
            s = s.split(token)[0]
            break

    s = s.strip()
    if not s:
        return None

    if multiplier > 1:
        # Dezimalwert: Tausenderpunkte entfernen, Komma → Dezimalpunkt.
        s = s.replace('.', '').replace(',', '.')
        try:
            return int(round(float(s) * multiplier))
        except ValueError:
            return None

    # Reiner Eurobetrag: Tausenderpunkte entfernen, Komma → Dezimalpunkt.
    s = s.replace('.', '').replace(',', '.')
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def parse_foot(value):
    """Normalisiert die Fußangabe auf 'L' / 'R' / 'B'. Sonst ''.

    Akzeptiert deutsch (links/rechts/beidfüßig) und englisch (left/right/both)
    sowie Rohwerte 'L', 'R', 'B'.
    """
    if not value:
        return ''
    s = str(value).strip().lower()
    if s in ('b', 'both') or 'beid' in s:
        return 'B'
    if s in ('l', 'left') or 'link' in s:
        return 'L'
    if s in ('r', 'right') or 'recht' in s:
        return 'R'
    return ''


def parse_nationalities(value):
    """Normalisiert Nationalitäten.

    Args:
        value: Liste von Strings oder kommagetrennter String.

    Returns:
        (primary_nationality, comma_joined) — beide '' wenn leer.
    """
    if not value:
        return '', ''
    if isinstance(value, str):
        items = [v.strip() for v in value.split(',') if v.strip()]
    else:
        items = [str(v).strip() for v in value if str(v).strip()]
    if not items:
        return '', ''
    # Reihenfolge erhalten, Duplikate entfernen.
    seen = set()
    unique = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[0], ', '.join(unique)
