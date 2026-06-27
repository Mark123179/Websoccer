"""Scoutbarkeit, Abdeckung und Karten-Datenvertrag.

KARTEN-DATENVERTRAG (Backend → Frontend): pro Land NUR
``iso2, name, continent, region, status, coverage_percent, coverage_label, hint``.
NIEMALS ``pool_count`` oder echte Spielerzahlen. ``coverage_percent`` wird
ausschließlich aus Community-/Aktivitätspunkten abgeleitet, damit die verborgene
Poolgröße nicht rückgerechnet werden kann.
"""

from .constants import (
    COUNTRIES,
    COUNTRY_THRESHOLD,
    REGION_THRESHOLD,
    NEAR_UNLOCK_RATIO,
    CONTINENTS,
    REGIONS,
    region_iso_codes,
)
from .geo import nationality_to_iso2

# Skalierungskonstante der Abdeckungs-Sättigung (kalibrierbar).
_COVERAGE_SATURATION_K = 40

STATUS_SCOUTABLE = 'scoutable'
STATUS_BUILDING = 'building'
STATUS_LOCKED = 'locked'
STATUS_UNAVAILABLE = 'unavailable'


# ── Verborgene Pool-Zählung (NIE serialisieren) ──────────────────────────────
def pool_counts_by_country():
    """Dict ISO2 → Anzahl scoutbarer Poolspieler (primäre Nationalität).

    Ergebnis ist serverseitig; es darf nie ans Frontend gegeben werden.
    """
    from game.models import Player
    counts = {}
    qs = (
        Player.objects
        .filter(club__isnull=True, pool_status=Player.POOL_STATUS_SCOUTABLE)
        .exclude(loan_status='extern_loan')
        .values_list('nationalities', flat=True)
    )
    for nats in qs:
        if not nats:
            continue
        iso = nationality_to_iso2(nats.split(',')[0].strip())
        if iso:
            counts[iso] = counts.get(iso, 0) + 1
    return counts


def networks_by_iso():
    from game.models import CountryNetwork
    return {n.iso2.upper(): n for n in CountryNetwork.objects.all()}


# ── Scoutbarkeit ─────────────────────────────────────────────────────────────
def is_country_scoutable(iso2, counts=None, network=None):
    iso2 = (iso2 or '').upper()
    if iso2 not in COUNTRIES:
        return False
    if network is not None and network.is_paused:
        return False
    counts = pool_counts_by_country() if counts is None else counts
    return counts.get(iso2, 0) >= COUNTRY_THRESHOLD


def is_region_scoutable(region_key, counts=None):
    if region_key not in REGIONS:
        return False
    counts = pool_counts_by_country() if counts is None else counts
    total = sum(counts.get(iso, 0) for iso in region_iso_codes(region_key))
    return total >= REGION_THRESHOLD


def is_scope_scoutable(scope_type, scope_key, counts=None, networks=None):
    counts = pool_counts_by_country() if counts is None else counts
    if scope_type == 'region':
        return is_region_scoutable(scope_key, counts=counts)
    networks = networks_by_iso() if networks is None else networks
    return is_country_scoutable(scope_key, counts=counts, network=networks.get((scope_key or '').upper()))


# ── Abdeckung & Status ───────────────────────────────────────────────────────
def coverage_percent(network):
    """0–100, nur aus Community-/Aktivitätspunkten (leckt NIE die Poolgröße)."""
    if network is None:
        return 0
    pts = (network.community_points or 0) + (network.activity_points or 0)
    if pts <= 0:
        return 0
    return min(100, round(100 * pts / (pts + _COVERAGE_SATURATION_K)))


def precision_factor(network):
    """0..1 Abdeckungs-Faktor für die Kandidatengewichtung."""
    return coverage_percent(network) / 100.0


def country_status(iso2, counts=None, network=None):
    iso2 = (iso2 or '').upper()
    if iso2 not in COUNTRIES:
        return STATUS_UNAVAILABLE
    if network is not None and network.is_paused:
        return STATUS_LOCKED
    counts = pool_counts_by_country() if counts is None else counts
    if counts.get(iso2, 0) >= COUNTRY_THRESHOLD:
        return STATUS_SCOUTABLE
    if network is not None:
        return STATUS_BUILDING
    return STATUS_UNAVAILABLE


def coverage_label(status, percent):
    if status == STATUS_UNAVAILABLE:
        return 'nicht verfügbar'
    if status == STATUS_LOCKED:
        return 'gesperrt'
    if status == STATUS_BUILDING:
        return 'kurz vor Freischaltung' if percent >= round(NEAR_UNLOCK_RATIO * 100) else 'Netzwerk im Aufbau'
    # scoutable → Präzisionsstufe
    if percent < 40:
        return 'grobe Suche'
    if percent < 65:
        return 'normale Suche'
    if percent < 85:
        return 'gute Suche'
    return 'sehr genaue Suche'


def country_hint(status, name):
    if status == STATUS_SCOUTABLE:
        return f'{name} ist scoutbar. Wähle es als Suchgebiet aus.'
    if status == STATUS_BUILDING:
        return f'{name}: Netzwerk im Aufbau – wird nach weiterem Ausbau freigeschaltet.'
    if status == STATUS_LOCKED:
        return f'{name} ist derzeit gesperrt.'
    return f'{name} ist aktuell nicht verfügbar.'


# ── Karten-Datenvertrag ──────────────────────────────────────────────────────
ALLOWED_CONTRACT_KEYS = {
    'iso2', 'name', 'continent', 'region', 'status', 'coverage_percent', 'coverage_label', 'hint',
}


def map_country_contract(iso2, counts=None, networks=None):
    iso2 = iso2.upper()
    rec = COUNTRIES[iso2]
    networks = networks_by_iso() if networks is None else networks
    counts = pool_counts_by_country() if counts is None else counts
    network = networks.get(iso2)
    status = country_status(iso2, counts=counts, network=network)
    percent = coverage_percent(network)
    return {
        'iso2': iso2,
        'name': rec['name'],
        'continent': rec['continent'],
        'region': rec['region'],
        'status': status,
        'coverage_percent': percent,
        'coverage_label': coverage_label(status, percent),
        'hint': country_hint(status, rec['name']),
    }


def map_data():
    """Vollständiger Karten-Datenvertrag (ohne jede Spielerzahl)."""
    counts = pool_counts_by_country()
    networks = networks_by_iso()
    countries = [map_country_contract(iso, counts=counts, networks=networks) for iso in COUNTRIES]
    countries.sort(key=lambda c: c['name'])
    regions = [
        {'key': key, 'name': rec['name'], 'continent': rec['continent']}
        for key, rec in REGIONS.items()
    ]
    return {
        'countries': countries,
        'continents': [{'key': k, 'name': v} for k, v in CONTINENTS.items()],
        'regions': regions,
    }
