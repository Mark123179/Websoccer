"""Kanonisches Feldschema des CSV-Imports (Single Source of Truth).

Dieses Modul ist die **eine** verbindliche Quelle dafür, welche CSV-Spalte auf
welches Modellfeld abgebildet wird — getrennt nach:

* **Echtweltdaten** — kommen aus der CSV und werden vom Import geschrieben
  (Identität, Ratings, Stadionkapazität, Geodaten, Bildpfade …).
* **Spielstand / Ökonomie** — leben getrennt und werden vom Import **nie**
  angefasst (Budget, Liga, Trainer, Verträge, Ticketpreise, Ausbaustufen,
  Verletzungen, Transferlisten …).

Damit ist die Grundidee „einmal vollständig anlegen (Vollanlage), danach nur
volatile Felder auffrischen (Aktualisierung)" überhaupt erst sauber möglich.

Das 21-Attribut-Mapping wird **nicht** hier dupliziert, sondern aus
``import_ready_csv`` (``FMI_ATTR_MAP`` / ``SOFIFA_ATTR_MAP``) referenziert.

Aus diesem Schema erzeugt ``dump_import_template`` die kanonische Template-CSV,
damit jede künftige (auch KI-erzeugte) CSV dieselben Spalten liefert.
"""

from .import_ready_csv import FMI_ATTR_MAP, SOFIFA_ATTR_MAP


# ── Vereins-Echtweltdaten: CSV-Spalte → (Modell, Feld, Strategie, Hinweis) ───
# Strategie: 'overwrite' = nicht-leerer CSV-Wert überschreibt; 'fill' = nur wenn
# Zielfeld leer (für unique Identitäts-IDs, um Integritätskonflikte zu vermeiden);
# 'distribute' = Gesamtkapazität wird initial auf die Ränge verteilt.
CLUB_COLUMN_MAP = {
    'club_name':        ('Club', 'name', 'overwrite', 'Voller Vereinsname.'),
    'club_short_name':  ('Club', 'short_name', 'overwrite', 'Kurzname (max. 20).'),
    'founded_year':     ('Club', 'founded_year', 'overwrite', 'Gründungsjahr.'),
    'fmi_club_id':      ('Club', 'fm_inside_id', 'fill', 'FMInside-Vereins-ID (unique).'),
    'tm_club_id':       ('Club', 'transfermarkt_id', 'fill', 'Transfermarkt-Vereins-ID (unique).'),
    'club_tm_url':      ('Club', 'transfermarkt_profile_url', 'fill', 'Optional: TM-Vereinslink.'),
    'club_city':        ('ClubPublicProfile', 'city_name', 'overwrite', 'Standortstadt des Vereins.'),
    'country':          ('ClubPublicProfile', 'city_country', 'overwrite', 'Land.'),
    'latitude':         ('ClubPublicProfile', 'map_lat', 'overwrite', 'Breitengrad (Karte).'),
    'longitude':        ('ClubPublicProfile', 'map_lng', 'overwrite', 'Längengrad (Karte).'),
    'stadium_name':     ('ClubPublicProfile+Stadium', 'stadium_name / name', 'overwrite', 'Stadionname.'),
    'stadium_city':     ('Stadium', 'city', 'overwrite', 'Stadionort (kann von club_city abweichen).'),
    'stadium_capacity': ('ClubPublicProfile+Stadium', 'stadium_capacity / Ränge', 'distribute',
                         'Gesamtkapazität; initiale Verteilung auf Nord/Ost/Süd/West.'),
    'stadium_image_static_path': ('ClubPublicProfile', 'stadium_image_static_path', 'overwrite',
                                  'Optional: statischer Bildpfad Stadion.'),
    'city_image_static_path':    ('ClubPublicProfile', 'city_image_static_path', 'overwrite',
                                  'Optional: statischer Bildpfad Stadt.'),
}

# Reine Saison-Kontextspalten (kein Modellfeld; steuern den Importauftrag).
CLUB_CONTEXT_COLUMNS = ['season_id', 'season_label', 'ws_club']


# ── Spieler-Echtweltdaten ────────────────────────────────────────────────────
# Identität (nur Vollanlage) — im Aktualisierungs-Modus unangetastet.
PLAYER_IDENTITY_COLUMN_MAP = {
    'first_name':       ('Player', 'first_name', 'Vorname.'),
    'last_name':        ('Player', 'last_name', 'Nachname.'),
    'date_of_birth':    ('Player', 'date_of_birth', 'ISO YYYY-MM-DD; age wird daraus berechnet.'),
    'height_cm':        ('Player', 'height_cm', 'Körpergröße in cm.'),
    'preferred_foot':   ('Player', 'strong_foot', 'links/rechts/beidfüßig oder left/right/both → L/R/B.'),
    'primary_nationality': ('Player', 'nationalities (führend)', 'Erste Nationalität.'),
    'nationalities':    ('Player', 'nationalities', '|-getrennt; ins Deutsche normalisiert.'),
    'nt_nationality':   ('Player', 'nt_nationality', 'Optional: NT-Nation fürs Badge.'),
    'fm_unique_id':     ('Player', 'fm_inside_id', 'FMInside-Spieler-ID (unique).'),
    'tm_player_id':     ('Player', 'transfermarkt_id', 'Transfermarkt-Spieler-ID (unique).'),
    'tm_url':           ('Player', 'transfermarkt_profile_url', 'TM-Profillink.'),
    'tm_market_value_url': ('Player', 'transfermarkt_market_value_url', 'Optional: TM-Marktwertlink.'),
    'sofifa_id':        ('PlayerExternalId', 'external_id (SoFIFA)', 'SoFIFA-ID.'),
    'sofifa_url':       ('PlayerExternalId', 'profile_url (SoFIFA)', 'SoFIFA-Profillink.'),
}

# Volatile Felder (Vollanlage UND Aktualisierung).
PLAYER_VOLATILE_COLUMN_MAP = {
    'tm_market_value_eur': ('Player', 'market_value', 'Marktwert in Euro (NULL = unbekannt, nie 0).'),
    'hp_positions':     ('Player', 'main_position_1..3', 'Interne Codes, |-getrennt.'),
    'np_positions':     ('Player', 'secondary_position_1..3', 'Interne Codes, |-getrennt.'),
    'squad_status':     ('Player', 'loan_status / club / real_life_club', 'first_team/loaned_in/loaned_out.'),
    'real_club':        ('Player', 'real_life_club', 'Realer Stammverein.'),
    'loaned_from':      ('Player', 'loan_partner_club', 'Leihgeber (bei loaned_in).'),
}

# Quell-Ratings (je eine Zeile FM bzw. EA in PlayerSourceRating).
RATING_COLUMN_MAP = {
    'fmi_rating':        ('PlayerSourceRating[FM]', 'rating', 'FMInside-Rating.'),
    'fmi_potential':     ('PlayerSourceRating[FM]', 'potential', 'Fehlt → Fallback = rating.'),
    'fmi_source_version': ('PlayerSourceRating[FM]', 'source_version', 'Quellversion.'),
    'fmi_url':           ('PlayerSourceRating[FM]', 'source_url', 'FMInside-Profillink der Quelle.'),
    'sofifa_rating':     ('PlayerSourceRating[EA]', 'rating', 'SoFIFA-Rating.'),
    'sofifa_potential':  ('PlayerSourceRating[EA]', 'potential', 'Fehlt → Fallback = rating.'),
    'sofifa_source_version': ('PlayerSourceRating[EA]', 'source_version', 'Quellversion.'),
    'sofifa_url':        ('PlayerSourceRating[EA]', 'source_url', 'SoFIFA-Profillink der Quelle.'),
    # Gemeinsames Prüfdatum für beide Quellen — eine Zeile, beide PSR-Zeilen bekommen denselben Wert.
    'source_checked_at': ('PlayerSourceRating[FM+EA]', 'checked_at', 'Datum der letzten Quellprüfung.'),
}


# ── Spielstand / Ökonomie — NIE vom Import geschrieben ───────────────────────
PROTECTED_GAME_STATE_FIELDS = {
    'Club': ['budget', 'fan_popularity', 'league', 'job_availability_type', 'managed_by'],
    'ClubPublicProfile': ['average_attendance', 'partner_club'],
    'Stadium': [
        'lawn_quality', 'price_standing', 'price_seating', 'price_vip',
        'nlz_level', 'medizin_level', 'training_level', 'office_level',
        # Einzel-Tribünenkapazitäten (nord_*/ost_*/sued_*/west_*) sind
        # bewusst NICHT hier gelistet: Sie werden ausschließlich bei der
        # Erstanlage bzw. solange capacity_total == 0 aus der CSV-Kapazität
        # verteilt. Existiert bereits eine Kapazität, bleiben sie unberührt
        # (siehe club_reconcile.reconcile_club) — also Spielstand, aber
        # einmalig initialisierbar.
    ],
    'Player': [
        'shirt_number', 'salary_per_match', 'contract_until',
        'ws_injury_type', 'ws_injury_days_remaining',
        'ws_suspension_reason', 'ws_suspension_matches_remaining',
        'is_on_transfer_list', 'is_on_loan_list',
        # potential ist spielintern abgeleitet (Stärke-Engine), kein CSV-Feld.
        'potential',
    ],
}


# ── Kanonische Template-Spaltenreihenfolge ───────────────────────────────────
# Entspricht dem bestätigten 83-Spalten-Export; die FMI-/SoFIFA-Attribute werden
# aus den Maps abgeleitet (keine Duplikation). Optionale, im aktuellen Export
# noch fehlende Spalten sind klar als solche markiert.
_FMI_ATTR_COLUMNS = [f'fmi_{suffix}' for suffix in FMI_ATTR_MAP]
_SOFIFA_ATTR_COLUMNS = [f'sofifa_{suffix}' for suffix in SOFIFA_ATTR_MAP]

# Im aktuellen Export bereits vorhandene Spalten (Reihenfolge wie HSV-CSV).
PRESENT_COLUMNS = [
    'club_name', 'club_short_name', 'founded_year', 'club_city', 'country',
    'latitude', 'longitude', 'fmi_club_id', 'tm_club_id', 'stadium_name',
    'stadium_city', 'stadium_capacity', 'season_id', 'season_label', 'ws_club',
    'real_club', 'loaned_from', 'squad_status', 'fm_unique_id', 'tm_player_id',
    'tm_url', 'fmi_url', 'sofifa_id', 'sofifa_url', 'first_name', 'last_name',
    'display_name', 'date_of_birth', 'height_cm', 'preferred_foot',
    'primary_nationality', 'nationalities', 'tm_market_value_eur',
    'hp_positions', 'np_positions', 'position_method',
    'fmi_rating', 'fmi_potential', *_FMI_ATTR_COLUMNS,
    'sofifa_rating', 'sofifa_potential',
    'sofifa_pace', 'sofifa_stamina', 'sofifa_strength', 'sofifa_dribbling',
    'sofifa_short_passing', 'sofifa_long_passing', 'sofifa_crossing',
    'sofifa_finishing', 'sofifa_heading', 'sofifa_standing_tackle',
    'sofifa_defensive_awareness', 'sofifa_vision', 'sofifa_free_kick',
    'sofifa_penalties', 'sofifa_gk_reflexes', 'sofifa_gk_handling',
    'sofifa_gk_positioning', 'sofifa_gk_passing',
    'fmi_source_version', 'sofifa_source_version',
    'source_checked_at',
    'data_status', 'validation_warning',
]

# Im Schema bestätigt, im aktuellen Export aber (noch) nicht enthalten.
# Der Parser liest sie tolerant aus, wenn vorhanden; sonst No-Op.
OPTIONAL_COLUMNS = [
    'club_tm_url', 'stadium_image_static_path', 'city_image_static_path',
    'nt_nationality', 'tm_market_value_url',
]

# Vollständiges, kanonisches Template (vorhanden + optional).
TEMPLATE_COLUMNS = PRESENT_COLUMNS + OPTIONAL_COLUMNS


def template_header():
    """Kanonische CSV-Kopfzeile (vollständiges Template)."""
    return ','.join(TEMPLATE_COLUMNS)
