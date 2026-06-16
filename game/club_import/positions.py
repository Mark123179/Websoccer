"""Positions-Mapping und HP/NP-Algorithmus (Spec §12–§14).

Das Mapping (Transfermarkt-Bezeichnung → interne Position) liegt zentral in
``TM_POSITION_MAP``. Unbekannte Bezeichnungen werden NICHT geraten, sondern als
Warnung gemeldet.

``compute_positions`` ist eine reine, vollständig testbare Funktion ohne
DB-Zugriff.
"""

# Transfermarkt-Bezeichnung (kleingeschrieben) → interne Positionskennung.
TM_POSITION_MAP = {
    'torwart': 'TW',
    'innenverteidiger': 'IV',
    'libero': 'IV',
    'linker verteidiger': 'LV',
    'rechter verteidiger': 'RV',
    'defensives mittelfeld': 'DM',
    'zentrales mittelfeld': 'ZM',
    'linkes mittelfeld': 'LM',
    'rechtes mittelfeld': 'RM',
    'offensives mittelfeld': 'OM',
    'linksaußen': 'LF',
    'rechtsaußen': 'RF',
    'hängende spitze': 'ST',
    'mittelstürmer': 'ST',
    'sturm': 'ST',
}

# Abgeleitete Zusatz-HP: beide Ausgangspositionen müssen HP sein.
DERIVED_HP_RULES = [
    (('LV', 'LM'), 'LOV'),
    (('RV', 'RM'), 'ROV'),
    (('LM', 'LF'), 'LOM'),
    (('RM', 'RF'), 'ROM'),
]

HP_MIN_APPEARANCES = 25
NP_MIN_APPEARANCES = 10
MAX_HP = 2
MAX_NP = 2


def map_tm_position(label):
    """Bildet eine Transfermarkt-Positionsbezeichnung auf die interne Kennung ab.

    Returns:
        str interne Kennung oder ``None`` bei unbekannter Bezeichnung.
    """
    if not label:
        return None
    key = ' '.join(str(label).strip().lower().split())
    return TM_POSITION_MAP.get(key)


def compute_positions(performance, profile_position=None):
    """Berechnet Haupt- (HP) und Nebenpositionen (NP) aus Leistungsdaten.

    Args:
        performance: Iterable von ``(tm_label, einsätze)``-Paaren über alle
            Saisons. Mehrere TM-Labels, die auf dieselbe interne Position
            mappen, werden aufsummiert.
        profile_position: TM-Profilposition als Jugend-/Fallbackwert, falls keine
            auswertbaren Leistungsdaten vorliegen.

    Returns:
        dict mit:
            main_positions       — Liste interner HP-Kennungen (inkl. abgeleiteter)
            secondary_positions  — Liste interner NP-Kennungen
            warnings             — Liste von Warntexten (unbekannte Positionen)
            errors               — Liste von Validierungsfehlern (nicht importbereit)
            used_profile_fallback — bool: Profilposition als HP verwendet
    """
    warnings = []
    errors = []

    appearances = {}
    first_seen = []
    for entry in performance or []:
        try:
            label, raw_apps = entry
        except (TypeError, ValueError):
            warnings.append(f'Ungültiger Leistungsdatensatz: {entry!r} — übersprungen.')
            continue
        code = map_tm_position(label)
        if code is None:
            warnings.append(f'Unbekannte Position: {label!r} — übersprungen.')
            continue
        try:
            apps = int(raw_apps)
        except (TypeError, ValueError):
            apps = 0
        if code not in appearances:
            appearances[code] = 0
            first_seen.append(code)
        appearances[code] += max(0, apps)

    # Stabil nach Einsätzen absteigend; bei Gleichstand Reihenfolge des
    # ersten Auftretens (sorted ist stabil).
    ranked = sorted(first_seen, key=lambda c: -appearances[c])

    if not ranked:
        # §13.4 — Jugendspieler: Profilposition als HP.
        fallback = map_tm_position(profile_position)
        if fallback is None:
            errors.append(
                'Keine auswertbaren Positionsdaten und keine mappbare '
                'Profilposition — Spieler nicht importbereit.'
            )
            return {
                'main_positions': [],
                'secondary_positions': [],
                'warnings': warnings,
                'errors': errors,
                'used_profile_fallback': True,
            }
        return {
            'main_positions': [fallback],
            'secondary_positions': [],
            'warnings': warnings,
            'errors': errors,
            'used_profile_fallback': True,
        }

    main = []
    secondary = []

    # §13.1 / §13.5 — reguläre HP: ≥25 Einsätze, maximal zwei.
    for code in ranked:
        if len(main) >= MAX_HP:
            break
        if appearances[code] >= HP_MIN_APPEARANCES:
            main.append(code)

    # §13.3 — immer mindestens eine HP (meistgespielte, auch unter 25).
    if not main:
        main.append(ranked[0])

    # §13.2 — NP: verbleibende Positionen mit ≥10 Einsätzen, maximal zwei.
    for code in ranked:
        if code in main:
            continue
        if len(secondary) >= MAX_NP:
            break
        if appearances[code] >= NP_MIN_APPEARANCES:
            secondary.append(code)

    # §14 — abgeleitete Zusatz-HP (verbraucht keinen NP-Platz).
    hp_set = set(main)
    for (a, b), derived in DERIVED_HP_RULES:
        if a in hp_set and b in hp_set and derived not in main:
            main.append(derived)

    return {
        'main_positions': main,
        'secondary_positions': secondary,
        'warnings': warnings,
        'errors': errors,
        'used_profile_fallback': False,
    }
