"""Reconcile-Upsert für die Vollanlage eines Vereins (idempotent).

Schreibt Vereins-Stammdaten aus der CSV **nicht-destruktiv** in Club,
ClubPublicProfile und Stadium. Leitsätze:

* **Stammdaten** (Name, Kurzname, Gründungsjahr, Stadionname/-stadt, Geodaten,
  Bildpfade): nicht-leerer CSV-Wert überschreibt — leer lässt den Bestand in Ruhe.
* **Unique Identitäts-IDs** (fm_inside_id, transfermarkt_id, TM-Link): nur füllen,
  wenn leer (vermeidet Integritätskonflikte beim erneuten Import).
* **Stadionkapazität**: Anfangs-Verteilung auf die Ränge nur, wenn noch keine
  Kapazität existiert (capacity_total == 0). Weicht eine bestehende Kapazität von
  der CSV ab, wird **gewarnt statt überschrieben** — sonst würden spielintern
  ausgebaute Tribünen plattgemacht.
* **Spielstand / Ökonomie** (Budget, Liga, Trainer, Ticketpreise, Ausbaustufen,
  Zuschauerschnitt, Partnerverein …) wird **nie** angefasst.

Damit ist ein erneuter Import idempotent: dieselbe CSV erzeugt keine Drift.
"""

# Stand-Anteile, abgeleitet aus vorhandenen Bundesliga-Stadien — proportional
# auf jede Gesamtkapazität anwendbar (Summe der Anteile = 1.0).
STADIUM_STAND_RATIOS = {
    'nord_standing': 0.175,
    'nord_seating': 0.075,
    'ost_seating': 0.25,
    'sued_standing': 0.0375,
    'sued_seating': 0.2125,
    'west_seating': 0.205,
    'west_vip': 0.045,
}


def distribute_capacity(capacity):
    """Verteilt eine Gesamtkapazität auf die Rang-Felder (Rest auf Ost-Sitz)."""
    stands = {
        field: int(round(capacity * ratio))
        for field, ratio in STADIUM_STAND_RATIOS.items()
    }
    diff = capacity - sum(stands.values())
    stands['ost_seating'] += diff
    return stands


def _set_overwrite(obj, field, value, notes, label):
    """Nicht-leerer Wert überschreibt; leer lässt den Bestand unangetastet."""
    if value in (None, '', 0):
        return
    if getattr(obj, field, None) != value:
        notes.append(f'{label}.{field}: {getattr(obj, field, None)!r} → {value!r}')
        setattr(obj, field, value)


def _set_fill(obj, field, value, notes, label):
    """Nur füllen, wenn Zielfeld leer (für unique Identitäts-IDs)."""
    if value in (None, '', 0):
        return
    if not getattr(obj, field, None):
        notes.append(f'{label}.{field} → {value!r}')
        setattr(obj, field, value)


def reconcile_club(club, profile, dry_run=False):
    """Gleicht Verein, Profil und Stadion mit den CSV-Stammdaten ab.

    Returns:
        dict {notes:[...], warnings:[...]}
    """
    from ..models import ClubPublicProfile, Stadium

    notes = []
    warnings = []

    # ── Club ────────────────────────────────────────────────────────────────
    _set_overwrite(club, 'name', (profile.get('club_name') or '').strip(), notes, 'club')
    short = (profile.get('club_short_name') or '').strip()
    if short:
        _set_overwrite(club, 'short_name', short[:20], notes, 'club')
    _set_overwrite(club, 'founded_year', profile.get('founded_year'), notes, 'club')
    _set_fill(club, 'fm_inside_id', profile.get('fmi_club_id'), notes, 'club')
    _set_fill(club, 'transfermarkt_id', profile.get('tm_club_id'), notes, 'club')
    _set_fill(club, 'transfermarkt_profile_url',
              (profile.get('club_tm_url') or '').strip(), notes, 'club')
    if not dry_run:
        club.save()

    # ── ClubPublicProfile ─────────────────────────────────────────────────────
    pp = getattr(club, 'public_profile', None)
    if pp is None:
        notes.append('public_profile angelegt')
        pp = ClubPublicProfile(club=club)
    _set_overwrite(pp, 'stadium_name', (profile.get('stadium_name') or '').strip(), notes, 'profile')
    _set_overwrite(pp, 'city_name', (profile.get('club_city') or '').strip(), notes, 'profile')
    _set_overwrite(pp, 'city_country', (profile.get('country') or '').strip(), notes, 'profile')
    _set_overwrite(pp, 'stadium_capacity', profile.get('stadium_capacity'), notes, 'profile')
    _set_overwrite(pp, 'map_lat', profile.get('latitude'), notes, 'profile')
    _set_overwrite(pp, 'map_lng', profile.get('longitude'), notes, 'profile')
    _set_overwrite(pp, 'stadium_image_static_path',
                   (profile.get('stadium_image_static_path') or '').strip(), notes, 'profile')
    _set_overwrite(pp, 'city_image_static_path',
                   (profile.get('city_image_static_path') or '').strip(), notes, 'profile')
    if not dry_run:
        pp.save()

    # ── Stadium ───────────────────────────────────────────────────────────────
    capacity = profile.get('stadium_capacity')
    stadium = getattr(club, 'stadium', None)
    if stadium is None:
        name = (profile.get('stadium_name') or '').strip()
        if capacity and name:
            stands = distribute_capacity(capacity)
            notes.append(f'Stadion „{name}" angelegt, Kapazität {capacity}')
            if not dry_run:
                Stadium.objects.create(
                    club=club,
                    name=name,
                    city=(profile.get('stadium_city') or profile.get('club_city') or '').strip(),
                    **stands,
                )
        elif capacity or name:
            warnings.append(
                'Stadion nicht angelegt — Name oder Kapazität fehlt '
                f'(name={name!r}, capacity={capacity!r}).'
            )
    else:
        _set_overwrite(stadium, 'name', (profile.get('stadium_name') or '').strip(), notes, 'stadium')
        _set_overwrite(stadium, 'city', (profile.get('stadium_city') or '').strip(), notes, 'stadium')
        if capacity:
            current = stadium.capacity_total
            if current == 0:
                stands = distribute_capacity(capacity)
                for field, value in stands.items():
                    setattr(stadium, field, value)
                notes.append(f'Stadion-Kapazität initial verteilt auf {capacity}')
            elif current != capacity:
                warnings.append(
                    f'Stadion-Kapazität {current} weicht von CSV {capacity} ab — '
                    f'bestehende Tribünenaufteilung bleibt unverändert (Spielstand).'
                )
        if not dry_run:
            stadium.save()

    return {'notes': notes, 'warnings': warnings}
