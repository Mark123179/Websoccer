"""CMTracker-Profil-Service.

Speichert normalisierte CMT-Spieler- und Vereinsprofile aus rohen API-Payloads.
Rohdaten werden immer vollständig überschrieben (keine Override-Sperre in V1).

Matching-Strategie für Spieler:
  1. PlayerExternalId(source__code=CMTRACKER, external_id=<cmt_player_id>)
  2. Kein Fallback in V1 — Matching ist Aufgabe von run_sofifa_import.

API-Key wird nie in Logs ausgegeben.
Kein echter Import ohne vorheriges Backup + Dry-Run (Aufruf-Verantwortung liegt
beim Aufrufer / Management-Command).
"""

import hashlib
import json
from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from game.cmtracker_api import _dig
from game.models import (
    Club,
    ClubCMTProfile,
    ClubExternalId,
    DataSource,
    Player,
    PlayerCMTAttributeProfile,
    PlayerCMTProfile,
    PlayerExternalId,
)


def _hash(payload):
    """SHA-256 über den kanonisch sortierten JSON-String."""
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _int(val):
    """Konvertiert sicher nach int; None bei Fehler."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _str(val):
    return '' if val is None else str(val).strip()


def _list(val):
    return val if isinstance(val, list) else []


def _dob(val):
    """Parst Geburtsdatum aus ISO-String oder date-Objekt."""
    if isinstance(val, date):
        return val
    if not val:
        return None
    raw = str(val)[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


# ── Spieler-Matching ─────────────────────────────────────────────────────────

def _find_player_by_cmt_id(cmt_player_id, cmt_source):
    """Sucht einen Player via PlayerExternalId (CMT-Quelle)."""
    try:
        ext = PlayerExternalId.objects.select_related('player').get(
            source=cmt_source,
            external_id=str(cmt_player_id),
        )
        return ext.player
    except PlayerExternalId.DoesNotExist:
        return None


# ── Attribute-Mapping ────────────────────────────────────────────────────────

_ATTR_MAP = {
    'acceleration':   'attributes.acceleration',
    'sprint_speed':   'attributes.sprintspeed',
    'agility':        'attributes.agility',
    'balance':        'attributes.balance',
    'jumping':        'attributes.jumping',
    'stamina':        'attributes.stamina',
    'strength':       'attributes.strength',
    'reactions':      'attributes.reactions',
    'aggression':     'attributes.aggression',
    'composure':      'attributes.composure',
    'interceptions':  'attributes.interceptions',
    'positioning':    'attributes.positioning',
    'vision':         'attributes.vision',
    'ball_control':   'attributes.ballcontrol',
    'crossing':       'attributes.crossing',
    'dribbling':      'attributes.dribbling',
    'finishing':      'attributes.finishing',
    'freekick_accuracy': 'attributes.freekickaccuracy',
    'heading_accuracy':  'attributes.headingaccuracy',
    'long_passing':   'attributes.longpassing',
    'short_passing':  'attributes.shortpassing',
    'marking':        'attributes.marking',
    'shot_power':     'attributes.shotpower',
    'long_shots':     'attributes.longshots',
    'standing_tackle': 'attributes.standingtackle',
    'sliding_tackle': 'attributes.slidingtackle',
    'volleys':        'attributes.volleys',
    'curve':          'attributes.curve',
    'penalties':      'attributes.penalties',
    'gk_diving':      'attributes.gkdiving',
    'gk_handling':    'attributes.gkhandling',
    'gk_kicking':     'attributes.gkkicking',
    'gk_reflexes':    'attributes.gkreflexes',
    'gk_positioning': 'attributes.gkpositioning',
}

_CARD_MAP = {
    'pac': 'card_attrs.pac',
    'sho': 'card_attrs.sho',
    'pas': 'card_attrs.pas',
    'dri': 'card_attrs.dri',
    'def_rating': 'card_attrs.def',
    'phy': 'card_attrs.phy',
}


# ── Haupt-Funktion: Spielerprofile speichern ─────────────────────────────────

def store_player_profiles(players, db_slug, dry_run=False, fetched_at=None):
    """Speichert/aktualisiert PlayerCMTProfile + PlayerCMTAttributeProfile.

    Parameters
    ----------
    players : list[dict]
        Rohe CMT-API-Spieler-Dicts (aus iter_players).
    db_slug : str
        Datenbank-Slug (z. B. '26062400').
    dry_run : bool
        Wenn True, werden keine Änderungen in die DB geschrieben.
    fetched_at : datetime | None
        Zeitpunkt des API-Abrufs; Standard: jetzt.

    Returns
    -------
    dict
        stats: {'matched': int, 'new': int, 'updated': int,
                'unchanged': int, 'unmatched': int,
                'unmatched_ids': list[str]}
    """
    if fetched_at is None:
        fetched_at = timezone.now()

    try:
        cmt_source = DataSource.objects.get(code=DataSource.CODE_CMTRACKER)
    except DataSource.DoesNotExist:
        return {
            'matched': 0, 'new': 0, 'updated': 0,
            'unchanged': 0, 'unmatched': len(players),
            'unmatched_ids': [],
            'error': 'DataSource CMTRACKER nicht gefunden — bitte Migrationen prüfen.',
        }

    stats = {'matched': 0, 'new': 0, 'updated': 0, 'unchanged': 0, 'unmatched': 0}
    unmatched_ids = []
    now = timezone.now()

    for raw in players:
        cmt_id = _str(_dig(raw, 'info.playerid'))
        if not cmt_id:
            stats['unmatched'] += 1
            continue

        player = _find_player_by_cmt_id(cmt_id, cmt_source)
        if player is None:
            stats['unmatched'] += 1
            unmatched_ids.append(cmt_id)
            continue

        stats['matched'] += 1

        if dry_run:
            exists = PlayerCMTProfile.objects.filter(player=player).exists()
            if exists:
                stats['updated'] += 1
            else:
                stats['new'] += 1
            continue

        _upsert_player_profile(player, raw, cmt_id, db_slug, cmt_source, fetched_at, now, stats)

    stats['unmatched_ids'] = unmatched_ids[:50]
    return stats


@transaction.atomic
def _upsert_player_profile(player, raw, cmt_id, db_slug, cmt_source,
                            fetched_at, now, stats):
    new_hash = _hash(raw)

    profile, created = PlayerCMTProfile.objects.get_or_create(
        player=player,
        defaults={'db_slug': db_slug, 'cmt_player_id': cmt_id,
                  'raw_payload': raw, 'payload_hash': new_hash,
                  'fetched_at': fetched_at},
    )

    if not created and profile.payload_hash == new_hash:
        profile.last_verified_at = now
        profile.save(update_fields=['last_verified_at'])
        stats['unchanged'] += 1
        return

    _fill_player_profile(profile, raw, cmt_id, db_slug, new_hash, fetched_at, now, created)
    profile.save()

    _upsert_attribute_profile(player, raw, db_slug, new_hash, fetched_at)

    PlayerExternalId.objects.filter(source=cmt_source, player=player).update(
        db_slug=db_slug,
        last_seen_at=now,
    )

    if created:
        stats['new'] += 1
    else:
        stats['updated'] += 1


def _fill_player_profile(profile, raw, cmt_id, db_slug, new_hash, fetched_at, now, created):
    profile.db_slug = db_slug
    profile.cmt_player_id = cmt_id
    profile.first_name = _str(_dig(raw, 'info.name.firstname'))
    profile.last_name = _str(_dig(raw, 'info.name.lastname'))
    profile.known_as = _str(_dig(raw, 'info.name.knownas'))
    profile.display_name = _str(_dig(raw, 'info.name.displayname') or _dig(raw, 'info.name.knownas'))
    profile.nationality = _str(_dig(raw, 'info.nationality.label') or _dig(raw, 'info.nationality'))
    profile.second_nationality = _str(_dig(raw, 'info.secondnationality.label') or _dig(raw, 'info.secondnationality'))
    profile.date_of_birth = _dob(_dig(raw, 'info.birthdate'))
    profile.overall = _int(_dig(raw, 'info.overallrating'))
    profile.potential = _int(_dig(raw, 'info.potential'))
    profile.height_cm = _int(_dig(raw, 'info.height'))
    profile.weight_kg = _int(_dig(raw, 'info.weight'))
    profile.preferred_foot = _str(_dig(raw, 'info.preferredfoot.label') or _dig(raw, 'info.preferredfoot'))
    profile.body_type = _str(_dig(raw, 'info.bodytype.label') or _dig(raw, 'info.bodytype'))
    profile.emotion = _str(_dig(raw, 'info.emotion') or '')
    profile.real_life_club = _str(
        _dig(raw, 'info.teams.club_team.name') or
        _dig(raw, 'info.club') or ''
    )
    profile.on_loan_from_club = _str(_dig(raw, 'info.teams.loan_team.name') or '')
    profile.playstyles = _list(_dig(raw, 'info.playstyles'))
    profile.playstyles_plus = _list(_dig(raw, 'info.playstylesplus'))
    profile.roles = _list(_dig(raw, 'info.roles'))
    profile.role_plus = _list(_dig(raw, 'info.roleplus'))
    profile.role_plus_plus = _list(_dig(raw, 'info.roleplusplus'))
    profile.player_image_url = _str(_dig(raw, 'info.imageurl') or _dig(raw, 'info.image_url') or '')
    profile.raw_payload = raw
    profile.payload_hash = new_hash
    profile.fetched_at = fetched_at
    profile.last_imported_at = now
    if not created:
        pass  # imported_at bleibt auto_now_add


def _upsert_attribute_profile(player, raw, db_slug, payload_hash, fetched_at):
    attr_data = {}
    for field, path in _ATTR_MAP.items():
        attr_data[field] = _int(_dig(raw, path))
    for field, path in _CARD_MAP.items():
        attr_data[field] = _int(_dig(raw, path))

    PlayerCMTAttributeProfile.objects.update_or_create(
        player=player,
        defaults={
            'db_slug': db_slug,
            **attr_data,
            'raw_attributes': {
                p: _dig(raw, p)
                for p in list(_ATTR_MAP.values()) + list(_CARD_MAP.values())
            },
            'fetched_at': fetched_at,
            'payload_hash': payload_hash,
        },
    )


# ── Vereinsprofile speichern ─────────────────────────────────────────────────

def store_club_profile(club, team_data, db_slug, dry_run=False):
    """Speichert/aktualisiert ClubCMTProfile + ClubExternalId.

    Parameters
    ----------
    club : Club
        Unser WS-Verein-Objekt.
    team_data : dict
        Rohdaten des CMT-Teams aus der Filters-Antwort.
    db_slug : str
        Datenbank-Slug.
    dry_run : bool

    Returns
    -------
    str
        'new' | 'updated' | 'unchanged'
    """
    try:
        cmt_source = DataSource.objects.get(code=DataSource.CODE_CMTRACKER)
    except DataSource.DoesNotExist:
        return 'error'

    team_id = _str(
        team_data.get('id') or team_data.get('teamid') or
        team_data.get('team_id') or team_data.get('clubid') or ''
    )

    if dry_run:
        exists = ClubCMTProfile.objects.filter(club=club).exists()
        return 'updated' if exists else 'new'

    new_hash = _hash(team_data)
    now = timezone.now()

    profile, created = ClubCMTProfile.objects.get_or_create(
        club=club,
        defaults={'db_slug': db_slug, 'raw_payload': team_data, 'payload_hash': new_hash},
    )

    if not created and profile.payload_hash == new_hash:
        profile.last_verified_at = now
        profile.save(update_fields=['last_verified_at'])
        _upsert_club_external_id(club, cmt_source, team_id, db_slug, now)
        return 'unchanged'

    profile.db_slug = db_slug
    profile.team_id = team_id
    profile.league_id = _str(team_data.get('league_id') or team_data.get('leagueid') or '')
    profile.name = _str(team_data.get('name') or team_data.get('club_name') or '')
    profile.league_name = _str(team_data.get('league_name') or team_data.get('league') or '')
    profile.nation = _str(team_data.get('nation') or team_data.get('nationality') or '')
    profile.country = _str(team_data.get('country') or '')
    profile.foundation_year = _int(team_data.get('foundation_year') or team_data.get('founded'))
    profile.popularity = _int(team_data.get('popularity'))
    profile.domestic_prestige = _int(team_data.get('domesticprestige') or team_data.get('domestic_prestige'))
    profile.international_prestige = _int(team_data.get('internationalprestige') or team_data.get('international_prestige'))
    profile.profitability = _int(team_data.get('profitability'))
    profile.home_kit = team_data.get('homekit') or team_data.get('home_kit') or {}
    profile.away_kit = team_data.get('awaykit') or team_data.get('away_kit') or {}
    profile.third_kit = team_data.get('thirdkit') or team_data.get('third_kit') or {}
    profile.raw_payload = team_data
    profile.payload_hash = new_hash
    profile.last_imported_at = now
    profile.save()

    _upsert_club_external_id(club, cmt_source, team_id, db_slug, now)

    return 'new' if created else 'updated'


def _upsert_club_external_id(club, cmt_source, team_id, db_slug, now):
    if not team_id:
        return
    ClubExternalId.objects.update_or_create(
        club=club,
        source=cmt_source,
        defaults={
            'external_id': team_id,
            'db_slug': db_slug,
            'last_seen_at': now,
        },
    )
