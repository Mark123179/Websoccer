"""Gemeinsamer Positionsfit-Service für Startelf, Auto-Aufstellung und Wechsel.

Wird importiert von: match_engine, tactics, auto_lineup, zukünftigen Formationswechseln.
Keine Django-ORM-Abhängigkeiten — rein rechenorientiert.
"""

# ── Positions-Fit-Faktoren (V1 — eingefroren nach erstem Deployment) ─────────
HP_POSITION_FACTOR: float = 1.00   # Hauptposition — kein Malus
NP_POSITION_FACTOR: float = 0.90   # Nebenposition − 10 %
FOREIGN_POSITION_FACTOR: float = 0.70  # Fremdposition − 30 %

# Kanonische Slots (einzige erlaubte Werte in der Engine)
CANONICAL_POSITIONS: frozenset[str] = frozenset({
    'TW',
    'IV', 'LV', 'RV', 'LOV', 'ROV',
    'DM', 'ZM', 'LM', 'RM', 'OM', 'ROM', 'LOM',
    'LF', 'RF', 'ST',
})

# Normalisierungs-Map: nicht-kanonische → kanonische Bezeichnungen
_NORMALIZE_MAP: dict[str, str] = {
    'GK':  'TW',
    'CB':  'IV',
    'LB':  'LV',
    'RB':  'RV',
    'CM':  'ZM',
    'AM':  'OM',
    'LA':  'LF',
    'RA':  'RF',
    'MS':  'ST',
    'WB':  'LV',
    'CAM': 'OM',
    'CDM': 'DM',
}


def normalize_position(pos: str) -> str:
    """Normalisiert eine Positionsbezeichnung auf den kanonischen Slot.

    Beispiel: 'LA' → 'LF', 'GK' → 'TW', 'ST' → 'ST'
    Unbekannte Bezeichnungen werden unverändert zurückgegeben.
    """
    if not pos:
        return ''
    upper = pos.upper().strip()
    if upper in CANONICAL_POSITIONS:
        return upper
    return _NORMALIZE_MAP.get(upper, upper)


def get_position_fit(player_dict: dict, slot_code: str) -> tuple[float, str]:
    """Zentraler Positionsfit-Faktor.

    Konsistent für Startelf, Auto-Aufstellung, geplante Wechsel und
    Verletzungswechsel. Eingehende Positionen werden normalisiert,
    um parallele Bezeichnungen (LA, MS, GK, …) zu vermeiden.

    Returns:
        (factor, label)
        HP → (1.00, 'HP')  — Hauptposition, kein Malus
        NP → (0.90, 'NP')  — Nebenposition, −10 %
        FP → (0.70, 'FP')  — Fremdposition, −30 %
    """
    norm_slot = normalize_position(slot_code)
    main = [normalize_position(p) for p in (player_dict.get('main_positions') or [])]
    secondary = [normalize_position(p) for p in (player_dict.get('secondary_positions') or [])]
    if norm_slot in main:
        return HP_POSITION_FACTOR, 'HP'
    if norm_slot in secondary:
        return NP_POSITION_FACTOR, 'NP'
    return FOREIGN_POSITION_FACTOR, 'FP'
