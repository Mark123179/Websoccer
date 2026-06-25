"""Wiederverwendbares Validierungsregelwerk für den CSV-Import.

Kein reiner CLI-Code: Dieselben Regeln werden von Dry-Run, Vollanlage,
Aktualisierung, Batch-Import und DB-Revalidate genutzt. Die kleinsten Bausteine
sind reine Wertprädikate; darauf setzen Validatoren für DB-Objekte (Revalidate)
und für geparste ``normalized_data`` (Dry-Run vor dem Schreiben) auf.

Geprüfte Regeln:
* Stadion-Kapazität > 0
* Geodaten (Breiten-/Längengrad) gesetzt
* Jeder Spieler mit Quell-Rating hat Attribute
* Starker Fuß gesetzt
* Potential ≥ Rating (Quell-Ratings)

Schweregrade: ``error`` (harte Lücke) / ``warning`` (Hinweis).
Exit-Codes: 0 = ok, 1 = harte Fehler, 2 = nur Warnungen (nur bei ``strict``).
"""

LEVEL_ERROR = 'error'
LEVEL_WARNING = 'warning'

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_WARNINGS = 2


def _issue(level, code, message, ref=''):
    return {'level': level, 'code': code, 'message': message, 'ref': ref}


# ── Reine Wertprädikate ──────────────────────────────────────────────────────

def check_capacity(capacity_total, ref=''):
    """Stadion-Gesamtkapazität muss > 0 sein."""
    if not capacity_total or capacity_total <= 0:
        return _issue(LEVEL_ERROR, 'stadium_capacity_zero',
                      'Stadion-Gesamtkapazität ist 0.', ref)
    return None


def check_geo(lat, lng, ref=''):
    """Karten-Koordinaten sollten gesetzt sein."""
    if lat is None or lng is None:
        return _issue(LEVEL_WARNING, 'geo_missing',
                      'Geodaten (Breiten-/Längengrad) fehlen.', ref)
    return None


def check_foot(strong_foot, ref=''):
    """Starker Fuß sollte gesetzt sein."""
    if not (strong_foot or '').strip():
        return _issue(LEVEL_WARNING, 'foot_missing',
                      'Starker Fuß nicht gesetzt.', ref)
    return None


def check_potential_raw(raw_value, ref=''):
    """Warnung wenn Potential ein nicht-numerischer Sonderwert ist (z.B. 'DYNAMIC').

    FM verwendet 'DYNAMIC' für Spieler mit Bereichs-Potential (z.B. 75–90).
    FMInside exportiert diesen Wert als Text. Der Import fällt auf Rating als
    Fallback zurück — das Upside-Potenzial geht verloren. Diese Warnung macht
    den stillen Datenverlust sichtbar.
    """
    if not raw_value:
        return None
    return _issue(LEVEL_WARNING, 'potential_dynamic',
                  f"Potential '{raw_value}' ist nicht numerisch (FM-Sonderwert, "
                  f"z.B. Bereichs-Potential). Fallback: Potential = Rating.", ref)


def check_potential(rating, potential, ref='', allow_missing=False):
    """Potential muss bei vorhandenem Rating ≥ Rating sein.

    ``allow_missing`` lockert die Regel für die Prüfung *geparster* CSV-Daten:
    Dort ist ein fehlendes Potential unkritisch, weil der Import zentral
    ``potential = rating`` setzt. Nach dem Import (DB-Prüfung) ist ein fehlendes
    Potential dagegen ein Defekt (Fallback hätte greifen müssen).
    """
    if rating is None:
        return None
    if potential is None:
        if allow_missing:
            return None
        return _issue(LEVEL_ERROR, 'potential_missing',
                      'Rating vorhanden, aber kein Potential.', ref)
    if potential < rating:
        return _issue(LEVEL_ERROR, 'potential_below_rating',
                      f'Potential {potential} < Rating {rating}.', ref)
    return None


def check_attrs(rating, has_attrs, ref=''):
    """Bei vorhandenem Rating müssen Attribute vorhanden sein."""
    if rating is not None and not has_attrs:
        return _issue(LEVEL_ERROR, 'rating_without_attrs',
                      'Rating vorhanden, aber keine Attribute.', ref)
    return None


# ── DB-Objekt-Validatoren (Revalidate / Nachkontrolle) ───────────────────────

def validate_db_club(club):
    """Prüft einen Verein samt Stadion und öffentlichem Profil (DB-Objekte)."""
    issues = []
    ref = club.name

    stadium = getattr(club, 'stadium', None)
    if stadium is None:
        issues.append(_issue(LEVEL_ERROR, 'stadium_missing',
                             'Kein Stadion vorhanden.', ref))
    else:
        cap = check_capacity(stadium.capacity_total, ref)
        if cap:
            issues.append(cap)

    pp = getattr(club, 'public_profile', None)
    lat = getattr(pp, 'map_lat', None) if pp else None
    lng = getattr(pp, 'map_lng', None) if pp else None
    geo = check_geo(lat, lng, ref)
    if geo:
        issues.append(geo)

    return issues


def validate_db_player(player):
    """Prüft einen Spieler samt Quell-Ratings (DB-Objekte)."""
    from .import_service import PSR_ATTR_FIELDS

    issues = []
    ref = f'{player.first_name} {player.last_name}'.strip() or str(player.pk)

    foot = check_foot(player.strong_foot, ref)
    if foot:
        issues.append(foot)

    for row in player.source_ratings.all():
        rref = f'{ref} [{row.source}]'
        has_attrs = any(getattr(row, f, None) is not None for f in PSR_ATTR_FIELDS)
        attrs = check_attrs(row.rating, has_attrs, rref)
        if attrs:
            issues.append(attrs)
        pot = check_potential(row.rating, row.potential, rref)
        if pot:
            issues.append(pot)

    return issues


def validate_db_club_full(club, players=None):
    """Aggregierte DB-Validierung eines Vereins inkl. seiner Spieler."""
    issues = list(validate_db_club(club))
    if players is None:
        players = list(club.player_set.all())
    for player in players:
        issues.extend(validate_db_player(player))
    return issues


# ── Parsed-Validatoren (Dry-Run vor dem Schreiben) ───────────────────────────

def validate_parsed_club(club_profile):
    """Prüft die geparsten (redundanten) Vereinsfelder einer CSV."""
    issues = []
    ref = club_profile.get('club_name') or ''
    cap = check_capacity(club_profile.get('stadium_capacity'), ref)
    if cap:
        issues.append(cap)
    geo = check_geo(club_profile.get('latitude'), club_profile.get('longitude'), ref)
    if geo:
        issues.append(geo)
    return issues


def validate_parsed_player(nd):
    """Prüft eine geparste Spielerzeile (``normalized_data``)."""
    issues = []
    ref = f"{nd.get('first_name', '')} {nd.get('last_name', '')}".strip()

    foot = check_foot(nd.get('strong_foot'), ref)
    if foot:
        issues.append(foot)

    for key, label in (('fmi_ratings', 'FM'), ('sofifa_ratings', 'CMTracker')):
        block = nd.get(key)
        if not block:
            continue
        rref = f'{ref} [{label}]'
        rating = block.get('rating')
        has_attrs = bool(block.get('attrs'))
        attrs = check_attrs(rating, has_attrs, rref)
        if attrs:
            issues.append(attrs)
        pot_raw = check_potential_raw(block.get('potential_raw'), rref)
        if pot_raw:
            issues.append(pot_raw)
        pot = check_potential(rating, block.get('potential'), rref, allow_missing=True)
        if pot:
            issues.append(pot)

    return issues


def validate_parsed(club_profile, players):
    """Aggregierte Validierung der geparsten CSV (Verein + Spielerzeilen)."""
    issues = list(validate_parsed_club(club_profile))
    for p in players:
        nd = p['normalized_data'] if 'normalized_data' in p else p
        issues.extend(validate_parsed_player(nd))
    return issues


# ── Zusammenfassung & Exit-Code ──────────────────────────────────────────────

def count_levels(issues):
    """Gibt ``(errors, warnings)`` zurück."""
    errors = sum(1 for i in issues if i['level'] == LEVEL_ERROR)
    warnings = sum(1 for i in issues if i['level'] == LEVEL_WARNING)
    return errors, warnings


def exit_code(issues, strict=False):
    """0 = ok, 1 = harte Fehler, 2 = nur Warnungen (nur bei ``strict``)."""
    errors, warnings = count_levels(issues)
    if errors:
        return EXIT_ERRORS
    if warnings and strict:
        return EXIT_WARNINGS
    return EXIT_OK
