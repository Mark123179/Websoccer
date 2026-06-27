"""Kalibrierbare Startkonstanten und Geo-Stammdaten des Scouting-Systems.

WICHTIG: Diese Werte sind bewusst als kalibrierbare Startwerte angelegt. Die
Struktur/Formeln sind fix; die Zahlen dürfen später mit echten DB-Daten
nachjustiert werden (siehe economy-design-principles).
"""

# ── Scoutbarkeits-Schwellen (serverseitig, NIE ans Frontend) ─────────────────
COUNTRY_THRESHOLD = 50      # ab so vielen Poolspielern ist ein Land scoutbar
REGION_THRESHOLD = 100      # ab so vielen Poolspielern ist eine Region scoutbar
# Anteil der Schwelle, ab dem ein Land als "kurz vor Freischaltung" gilt.
NEAR_UNLOCK_RATIO = 0.70

# ── Top-Star/Top-Talent-Erkennung (nie über Scouting verpflichtbar) ──────────
TOP_STAR_STRENGTH = 84       # base_strength >= => Top-Star (Auktion)
TOP_TALENT_POTENTIAL = 88    # potential >= bei jungem Spieler => Top-Talent
TOP_TALENT_MAX_AGE = 21

# ── Verpflichtungslimit ──────────────────────────────────────────────────────
BASE_COMMITMENT_SLOTS = 2    # Scouting-Verpflichtungen pro Verein & Saison

# ── Gebots-Vorlauf ───────────────────────────────────────────────────────────
BID_LEAD_DAYS = 7            # ein Gebot zählt erst, wenn es >=7 Tage vor dem Termin liegt

# ── Feste Zuschlagstermine (Monat, Tag) ──────────────────────────────────────
# Sommerpause 03.07., Winterpause 15.01.
WINDOW_DATES = [(7, 3), (1, 15)]

# ── Ausbaustufen der Scoutingabteilung (0–3) ─────────────────────────────────
# precision: 0..1 — höhere Stufe => engere Profil-/Positionspassung der Funde.
# Beeinflusst NIE die Spielerqualität, nur Dauer/Kosten/Trefferpräzision.
DEPARTMENT_LEVELS = {
    0: {
        'label': 'Regional-Scout',
        'desc': 'Einfaches Scoutingbüro. Lange Suchdauer, grobe Trefferpräzision.',
        'upgrade_cost': 0,
        'order_cost': 250_000,
        'duration_days': 18,
        'precision': 0.40,
    },
    1: {
        'label': 'Nationaler Scout',
        'desc': 'Ausgebautes Netzwerk. Kürzere Suchdauer, bessere Trefferpräzision.',
        'upgrade_cost': 2_000_000,
        'order_cost': 400_000,
        'duration_days': 15,
        'precision': 0.60,
    },
    2: {
        'label': 'Internationaler Scout',
        'desc': 'Professionelle Abteilung. Schnelle Suche, hohe Trefferpräzision.',
        'upgrade_cost': 4_000_000,
        'order_cost': 750_000,
        'duration_days': 12,
        'precision': 0.80,
    },
    3: {
        'label': 'Elite-Scoutingnetzwerk',
        'desc': 'Weltweites Elite-Netzwerk. Kürzeste Dauer, sehr genaue Treffer.',
        'upgrade_cost': 7_000_000,
        'order_cost': 1_200_000,
        'duration_days': 9,
        'precision': 1.00,
    },
}
MAX_DEPARTMENT_LEVEL = 3

# ── Preisformel (Mindestgebot) ───────────────────────────────────────────────
# min_bid = market_value * BASE_PREMIUM * age * strength * potential * league
BID_BASE_PREMIUM = 1.6
BID_MIN_FLOOR = 250_000      # Mindest-Mindestgebot
BID_ROUND_TO = 100_000       # Rundungsschritt
# Fallback-Marktwert, falls market_value NULL (unbekannt) ist.
BID_FALLBACK_MARKET_VALUE = 500_000

# ── Suchprofile: Ziel-Stärkeband relativ zur anfragenden Teamstärke ──────────
# (lo, hi) Offsets auf den Team-Durchschnitt; talent ist altersgetrieben.
PROFILE_STRENGTH_BANDS = {
    'backup':     (-14, -6),
    'ergaenzung': (-9, -2),
    'rotation':   (-5, +2),
    'stammkraft': (-1, +7),
    'talent':     (-12, +4),   # weit, da Talente über Potential gezogen werden
}
PROFILE_TALENT_MAX_AGE = 21    # "talent"-Profil bevorzugt Spieler bis zu diesem Alter

# Anzahl der Funde pro Auftrag (Spec: genau 3).
FINDS_PER_ASSIGNMENT = 3

# Beobachter-Zahl (angezeigte Mock-/Community-Größe) — Streubereich.
OBSERVER_MIN = 4
OBSERVER_MAX = 48

# ── Community-Einreichungen ──────────────────────────────────────────────────
COMMUNITY_WEEKLY_LIMIT = 5        # Einreichungen pro Manager & Woche
COMMUNITY_COUNTRY_WEEK_CAP = 3    # Einreichungen pro Manager, Land & Woche
COMMUNITY_ACTIVITY_POINTS = 1     # Punkte bei Einreichung (Aktivität)
COMMUNITY_APPROVE_POINTS = 2      # zusätzliche Punkte bei Freigabe (Community)

# ── Continents (Karten-Fokus-Dropdown) ───────────────────────────────────────
CONTINENTS = {
    'europa': 'Europa',
    'suedamerika': 'Südamerika',
    'afrika': 'Afrika',
    'asien': 'Asien',
}

# ── Regionen (Suchgebiet "Region") ───────────────────────────────────────────
REGIONS = {
    'eu_west':   {'name': 'West-/Südeuropa', 'continent': 'europa'},
    'eu_east':   {'name': 'Ost-/Südosteuropa', 'continent': 'europa'},
    'eu_north':  {'name': 'Nordeuropa', 'continent': 'europa'},
    'sa_all':    {'name': 'Südamerika', 'continent': 'suedamerika'},
    'af_all':    {'name': 'Afrika', 'continent': 'afrika'},
    'as_all':    {'name': 'Asien', 'continent': 'asien'},
}

# ── Länder-Stammdaten: ISO2 → (deutscher Name, Kontinent, Region) ─────────────
COUNTRIES = {
    # West-/Südeuropa
    'DE': {'name': 'Deutschland',   'continent': 'europa', 'region': 'eu_west'},
    'FR': {'name': 'Frankreich',    'continent': 'europa', 'region': 'eu_west'},
    'ES': {'name': 'Spanien',       'continent': 'europa', 'region': 'eu_west'},
    'IT': {'name': 'Italien',       'continent': 'europa', 'region': 'eu_west'},
    'GB': {'name': 'England',       'continent': 'europa', 'region': 'eu_west'},
    'PT': {'name': 'Portugal',      'continent': 'europa', 'region': 'eu_west'},
    'NL': {'name': 'Niederlande',   'continent': 'europa', 'region': 'eu_west'},
    'BE': {'name': 'Belgien',       'continent': 'europa', 'region': 'eu_west'},
    'AT': {'name': 'Österreich',    'continent': 'europa', 'region': 'eu_west'},
    'CH': {'name': 'Schweiz',       'continent': 'europa', 'region': 'eu_west'},
    # Ost-/Südosteuropa
    'TR': {'name': 'Türkei',        'continent': 'europa', 'region': 'eu_east'},
    'BG': {'name': 'Bulgarien',     'continent': 'europa', 'region': 'eu_east'},
    'HR': {'name': 'Kroatien',      'continent': 'europa', 'region': 'eu_east'},
    'RS': {'name': 'Serbien',       'continent': 'europa', 'region': 'eu_east'},
    'PL': {'name': 'Polen',         'continent': 'europa', 'region': 'eu_east'},
    'CZ': {'name': 'Tschechien',    'continent': 'europa', 'region': 'eu_east'},
    'GR': {'name': 'Griechenland',  'continent': 'europa', 'region': 'eu_east'},
    'UA': {'name': 'Ukraine',       'continent': 'europa', 'region': 'eu_east'},
    'RO': {'name': 'Rumänien',      'continent': 'europa', 'region': 'eu_east'},
    # Nordeuropa
    'DK': {'name': 'Dänemark',      'continent': 'europa', 'region': 'eu_north'},
    'SE': {'name': 'Schweden',      'continent': 'europa', 'region': 'eu_north'},
    'NO': {'name': 'Norwegen',      'continent': 'europa', 'region': 'eu_north'},
    # Südamerika
    'BR': {'name': 'Brasilien',     'continent': 'suedamerika', 'region': 'sa_all'},
    'AR': {'name': 'Argentinien',   'continent': 'suedamerika', 'region': 'sa_all'},
    'UY': {'name': 'Uruguay',       'continent': 'suedamerika', 'region': 'sa_all'},
    'CO': {'name': 'Kolumbien',     'continent': 'suedamerika', 'region': 'sa_all'},
    'CL': {'name': 'Chile',         'continent': 'suedamerika', 'region': 'sa_all'},
    'PE': {'name': 'Peru',          'continent': 'suedamerika', 'region': 'sa_all'},
    'EC': {'name': 'Ecuador',       'continent': 'suedamerika', 'region': 'sa_all'},
    'PY': {'name': 'Paraguay',      'continent': 'suedamerika', 'region': 'sa_all'},
    # Afrika
    'NG': {'name': 'Nigeria',       'continent': 'afrika', 'region': 'af_all'},
    'GH': {'name': 'Ghana',         'continent': 'afrika', 'region': 'af_all'},
    'SN': {'name': 'Senegal',       'continent': 'afrika', 'region': 'af_all'},
    'CI': {'name': 'Elfenbeinküste','continent': 'afrika', 'region': 'af_all'},
    'MA': {'name': 'Marokko',       'continent': 'afrika', 'region': 'af_all'},
    'EG': {'name': 'Ägypten',       'continent': 'afrika', 'region': 'af_all'},
    'DZ': {'name': 'Algerien',      'continent': 'afrika', 'region': 'af_all'},
    'CM': {'name': 'Kamerun',       'continent': 'afrika', 'region': 'af_all'},
    'TN': {'name': 'Tunesien',      'continent': 'afrika', 'region': 'af_all'},
    # Asien
    'JP': {'name': 'Japan',         'continent': 'asien', 'region': 'as_all'},
    'KR': {'name': 'Südkorea',      'continent': 'asien', 'region': 'as_all'},
    'SA': {'name': 'Saudi-Arabien', 'continent': 'asien', 'region': 'as_all'},
    'QA': {'name': 'Katar',         'continent': 'asien', 'region': 'as_all'},
    'IR': {'name': 'Iran',          'continent': 'asien', 'region': 'as_all'},
    'CN': {'name': 'China',         'continent': 'asien', 'region': 'as_all'},
    'AU': {'name': 'Australien',    'continent': 'asien', 'region': 'as_all'},
}


def country_name(iso2):
    rec = COUNTRIES.get((iso2 or '').upper())
    return rec['name'] if rec else (iso2 or '')


def region_iso_codes(region_key):
    """Alle ISO2-Codes einer Region."""
    return [iso for iso, rec in COUNTRIES.items() if rec['region'] == region_key]


def continent_iso_codes(continent_key):
    """Alle ISO2-Codes eines Kontinents."""
    return [iso for iso, rec in COUNTRIES.items() if rec['continent'] == continent_key]
