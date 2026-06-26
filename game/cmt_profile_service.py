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
    PlayerStrengthProfile,
)

# ── CMT-Position → WS-Positionscode ─────────────────────────────────────────
# CMT liefert EA-typische Strings (GK, CB, LB, CDM, CM, CAM, LW, ST …).
# Normalisierung: lowercase, Leerzeichen/Unterstriche/Bindestriche entfernt.
# Kurzformen (CDM, CM, RB …) haben Vorrang gegenüber langen Labels.
_CMT_TO_WS_POSITION = {
    # Torwart
    'gk': 'TW', 'gkp': 'TW', 'goalkeeper': 'TW',
    # Innenverteidiger
    'cb': 'IV', 'dc': 'IV',
    'centreback': 'IV', 'centerback': 'IV', 'centrebackdefender': 'IV',
    # Linker Verteidiger / Wing Back
    'lb': 'LV', 'lwb': 'LV',
    'leftback': 'LV', 'leftwingback': 'LV',
    # Rechter Verteidiger / Wing Back
    'rb': 'RV', 'rwb': 'RV',
    'rightback': 'RV', 'rightwingback': 'RV',
    # Defensives Mittelfeld — kurze UND lange Formen
    'cdm': 'DM', 'dm': 'DM',
    'defensivemidfield': 'DM',
    'centredefensivemidfield': 'DM',
    'centraldefensivemidfield': 'DM',
    'defensivemid': 'DM',
    # Zentrales Mittelfeld
    'cm': 'ZM', 'mc': 'ZM',
    'centralmidfield': 'ZM', 'centremidfield': 'ZM', 'centralmid': 'ZM',
    # Offensives Mittelfeld
    'cam': 'OM', 'am': 'OM',
    'attackingmidfield': 'OM', 'attackingmid': 'OM',
    # Linkes Mittelfeld / Flügel
    'lm': 'LM', 'lw': 'LM',
    'leftmidfield': 'LM', 'leftwing': 'LM', 'leftmid': 'LM',
    # Rechtes Mittelfeld / Flügel
    'rm': 'RM', 'rw': 'RM',
    'rightmidfield': 'RM', 'rightwing': 'RM', 'rightmid': 'RM',
    # Linker Flügel-Stürmer
    'lf': 'LF', 'leftwingforward': 'LF', 'leftforward': 'LF',
    # Rechter Flügel-Stürmer
    'rf': 'RF', 'rightwingforward': 'RF', 'rightforward': 'RF',
    # Stürmer / Mittelstürmer
    'cf': 'ST', 'ss': 'ST',
    'centreforward': 'ST', 'centerforward': 'ST',
    'st': 'ST', 'fw': 'ST', 'striker': 'ST', 'forward': 'ST',
}


def _normalize_pos_key(s):
    """Normalisiert eine Positionsbezeichnung für den Map-Lookup."""
    return str(s).lower().replace(' ', '').replace('_', '').replace('-', '')


def _cmt_position_to_ws(raw):
    """Mappt CMT-Positionsstring auf WS-Positionscode.

    Probiert mehrere bekannte Pfade. Kurzformen (shortlabel, abbr, short)
    haben Vorrang vor langen Labels um Fehlmappings zu vermeiden.

    Returns
    -------
    tuple[str, str]
        (ws_code, raw_label) — ws_code ist der WS-Positionscode (z. B. 'DM'),
        raw_label ist der unverarbeitete CMT-String für Diagnose-Ausgaben.
        Standard-Fallback: ('ST', '').
    """
    def _lookup(candidate):
        """Gibt (ws_code, candidate) zurück oder (None, None) wenn kein Treffer."""
        if not candidate or not isinstance(candidate, str):
            return None, None
        ws = _CMT_TO_WS_POSITION.get(_normalize_pos_key(candidate))
        return (ws, candidate) if ws else (None, None)

    for path in ('info.preferredposition', 'info.mainposition', 'info.position'):
        val = _dig(raw, path)
        if val is None:
            continue

        if isinstance(val, dict):
            # Kurzformen zuerst — viele EA-Antworten haben 'shortlabel' oder 'abbr'
            for key in ('shortlabel', 'abbr', 'short', 'label', 'name', 'title'):
                ws, raw_label = _lookup(val.get(key))
                if ws:
                    return ws, raw_label
            # Dict aber kein bekannter Kurzform-Key → ersten String-Wert probieren
            for v in val.values():
                if isinstance(v, str) and v:
                    ws, raw_label = _lookup(v)
                    if ws:
                        return ws, raw_label
            # Dict-Rohdarstellung für Diagnose merken, weiter mit nächstem Pfad
            continue

        if isinstance(val, str) and val:
            ws, raw_label = _lookup(val)
            if ws:
                return ws, raw_label

    # GK-Erkennung via Attributwerte als letzter Ausweg
    gk_ref = _int(_dig(raw, 'attributes.gkreflexes'))
    gk_div = _int(_dig(raw, 'attributes.gkdiving'))
    if (gk_ref is not None and gk_div is not None
            and gk_ref > 60 and gk_div > 60):
        return 'TW', 'gk_attrs'

    # Rohwert für Diagnose sammeln (wird im Dry-Run angezeigt)
    for path in ('info.preferredposition', 'info.mainposition', 'info.position'):
        val = _dig(raw, path)
        if isinstance(val, dict):
            raw_label = str(next(iter(val.values()), ''))[:30]
            return 'ST', raw_label
        if val:
            return 'ST', str(val)[:30]

    return 'ST', ''  # sicherer Default


def _compute_age(dob):
    """Berechnet das aktuelle Alter aus dem Geburtsdatum."""
    if not dob:
        return 25  # Plausibles Default falls DOB fehlt
    today = date.today()
    return today.year - dob.year - (
        (today.month, today.day) < (dob.month, dob.day)
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

def store_player_profiles(players, db_slug, dry_run=False, fetched_at=None,
                           ws_club=None):
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
    ws_club : Club | None
        Wenn gesetzt, werden nur Profile für Spieler dieses WS-Clubs geschrieben.
        Spieler anderer Vereine werden übersprungen (out_of_scope).
        Verhindert club-übergreifende Profil-Kontamination bei Team-Import.

    Returns
    -------
    dict
        stats: {'matched': int, 'new': int, 'updated': int,
                'unchanged': int, 'unmatched': int,
                'out_of_scope': int,
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

    stats = {
        'matched': 0, 'new': 0, 'updated': 0, 'unchanged': 0,
        'unmatched': 0, 'out_of_scope': 0,
    }
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

        # Club-Scope-Check: bei Team-Import nur Spieler des WS-Clubs bearbeiten.
        # Spieler anderer Vereine (z. B. Freiburg-Profil bei Leverkusen-Import)
        # werden übersprungen — kein Profil, kein Attribut-Update.
        if ws_club is not None and player.club_id != ws_club.id:
            stats['out_of_scope'] += 1
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


# ── Auto-Create: Spieler aus CMT-Rohdaten anlegen ───────────────────────────

def create_player_from_cmt_raw(raw, db_slug, ws_club=None, dry_run=False,
                                tm_position=None):
    """Legt einen Spieler aus CMT-Rohdaten an (Auto-Create bei not_in_ws).

    Positionsquellen-Regel:
      TM.de ist die ausschließliche Quelle für WS-Positionen (Player.position,
      main_position_1, secondary_position_*). CMT-Positionsdaten werden NUR
      als Diagnose (cmt_pos_raw) gespeichert und NIEMALS in WS-Positionsfelder
      geschrieben.

      Ohne ``tm_position`` (Pflichtparameter aus einem TM-Import) wird
      status='blocked' zurückgegeben und kein aktiver Spieler angelegt.

    CMT-Semantik (EA FC):
      info.teams.club_team.name  — aktiver Verein des Spielers (wo er spielt)
      info.teams.loan_team.name  — Leihgeber (von dem er geliehen ist;
                                   leer = kein aktives Leihverhältnis)

    Entscheidungsmatrix (Verein/Leihstatus):
      ws_club gegeben + loan_team.name → club=ws_club,  loan_status='loaned_in'
      ws_club gegeben + kein loan_team → club=ws_club,  loan_status='none'
      ws_club=None   + loan_team.name  → club=None,     loan_status='extern_loan'
      ws_club=None   + kein loan_team  → club=None,     loan_status='none'

    Args:
      raw:          Rohpayload aus CMT-API (dict).
      db_slug:      CMT-DB-Bezeichner, z. B. '26062400'.
      ws_club:      Websoccer-Club-Instanz des importierten Teams (oder None).
      dry_run:      Wenn True, werden keine DB-Änderungen geschrieben.
      tm_position:  WS-Positionscode aus TM-Import (z. B. 'DM', 'RV', 'TW').
                    Pflicht für aktive Spieleranlage. Fehlt dieser Wert, wird
                    status='blocked' zurückgegeben.

    Returns dict mit:
      status            'created' | 'blocked' | 'skipped' | 'error'
      player            Player-Instanz (None bei blocked/dry_run/Fehler)
      cmt_id            str
      name              str
      cmt_pos_raw       str  — CMT-Rohpositionslabel (nur Diagnose, kein WS-Feld)
      position          str  — WS-Positionscode (= tm_position, nur wenn not blocked)
      overall           int
      dob               date | None
      club_team_name    str — CMT aktiver Verein
      loan_team_name    str — CMT Leihgeber (leer = kein Leihverhältnis)
      decided_status    'loaned_in' | 'extern_loan' | 'none'
      target_club       Club-Instanz | None
      decision_reason   str — menschenlesbare Begründung
      reason            str (nur bei 'blocked'/'skipped'/'error')
    """
    cmt_id = _str(_dig(raw, 'info.playerid'))
    if not cmt_id:
        return {'status': 'error', 'cmt_id': None, 'player': None,
                'name': '?', 'reason': 'Kein CMT-playerid im Payload'}

    first_name = _str(_dig(raw, 'info.name.firstname') or
                      _dig(raw, 'info.name.knownas') or '') or '?'
    last_name  = _str(_dig(raw, 'info.name.lastname')  or
                      _dig(raw, 'info.name.knownas') or '') or '?'
    display_name = (
        _str(_dig(raw, 'info.name.knownas')) or
        f'{first_name} {last_name}'.strip()
    )

    # Geburtsdatum
    dob = None
    dob_raw = _dig(raw, 'info.birthdate')
    if dob_raw:
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y'):
            try:
                dob = datetime.strptime(str(dob_raw), fmt).date()
                break
            except ValueError:
                continue

    overall   = _int(_dig(raw, 'info.overallrating')) or 50
    potential = _int(_dig(raw, 'info.potential')) or overall

    # CMT-Position NUR als Diagnose — niemals für WS-Positionsfelder verwenden.
    # Primärquelle: roles[0].pos (EA-FC-Rollenarray).
    # Fallback:     info.preferredposition (shortlabel / label).
    _, pref_pos_raw = _cmt_position_to_ws(raw)
    _roles = _list(_dig(raw, 'roles'))
    _roles_pos = (
        _str(_roles[0].get('pos', ''))
        if _roles and isinstance(_roles[0], dict)
        else ''
    )
    cmt_pos_raw = _roles_pos or pref_pos_raw

    # ── CMT Leih-Semantik ────────────────────────────────────────────────────
    club_team_name = _str(_dig(raw, 'info.teams.club_team.name') or '')
    loan_team_name = _str(_dig(raw, 'info.teams.loan_team.name') or '')
    is_on_loan     = bool(loan_team_name)

    # ── Entscheidungsmatrix (Verein/Leihstatus) ──────────────────────────────
    if ws_club is not None:
        target_club = ws_club
        if is_on_loan:
            decided_status  = 'loaned_in'
            decision_reason = (
                f'Leihspieler im WS-Verein "{ws_club.name}" '
                f'(Leihgeber: {loan_team_name})'
            )
        else:
            decided_status  = 'none'
            decision_reason = f'Stammspieler im WS-Verein "{ws_club.name}"'
    else:
        target_club = None
        if is_on_loan:
            decided_status  = 'extern_loan'
            decision_reason = (
                f'Leihspieler, Zielverein außerhalb WS '
                f'(Leihgeber: {loan_team_name}; '
                f'aktiver Verein: {club_team_name or "?"})'
            )
        else:
            decided_status  = 'none'
            decision_reason = (
                'Kein WS-Club-Kontext, kein Leihverhältnis → vereinslos'
            )

    wsc_id = f'CMT{cmt_id}'

    # ── Sicherheitssperre: kein aktiver Auto-Create ohne TM-Position ─────────
    # Positionen kommen ausschließlich aus TM.de (CSV/Import). CMT liefert nur
    # Ratings, Attribute und Diagnose-Daten. Ohne TM-Quelle darf kein aktiver
    # Kaderspieler angelegt werden.
    if tm_position is None:
        return {
            'status': 'blocked',
            'player': None,
            'cmt_id': cmt_id,
            'name': display_name,
            'cmt_pos_raw': cmt_pos_raw,
            'overall': overall,
            'dob': dob,
            'club_team_name': club_team_name,
            'loan_team_name': loan_team_name,
            'decided_status': decided_status,
            'target_club': target_club,
            'decision_reason': decision_reason,
            'reason': (
                'TM-Position fehlt → kein aktiver Auto-Create möglich. '
                'Spieler bitte zuerst via TM-Import/CSV anlegen '
                f'(CMT-Diagnose: {cmt_pos_raw or "unbekannt"}).'
            ),
        }

    # ── Idempotenz-Check ─────────────────────────────────────────────────────
    if not dry_run:
        try:
            cmt_source = DataSource.objects.get(code='CMTRACKER')
        except DataSource.DoesNotExist:
            return {'status': 'error', 'cmt_id': cmt_id, 'player': None,
                    'name': display_name, 'reason': 'DataSource CMTRACKER fehlt'}

        existing_ext = PlayerExternalId.objects.filter(
            source=cmt_source, external_id=cmt_id
        ).first()
        if existing_ext:
            return {'status': 'skipped', 'cmt_id': cmt_id,
                    'player': existing_ext.player, 'name': display_name,
                    'cmt_pos_raw': cmt_pos_raw,
                    'position': tm_position,
                    'club_team_name': club_team_name,
                    'loan_team_name': loan_team_name,
                    'decided_status': decided_status,
                    'target_club': target_club,
                    'decision_reason': decision_reason,
                    'reason': 'PlayerExternalId bereits vorhanden'}

        if Player.objects.filter(wsc_player_id=wsc_id).exists():
            return {'status': 'skipped', 'cmt_id': cmt_id, 'player': None,
                    'name': display_name,
                    'cmt_pos_raw': cmt_pos_raw,
                    'position': tm_position,
                    'club_team_name': club_team_name,
                    'loan_team_name': loan_team_name,
                    'decided_status': decided_status,
                    'target_club': target_club,
                    'decision_reason': decision_reason,
                    'reason': 'wsc_player_id bereits vergeben'}

    _base_result = {
        'cmt_id': cmt_id,
        'name': display_name,
        'position': tm_position,       # WS-Position aus TM-Quelle
        'cmt_pos_raw': cmt_pos_raw,    # CMT-Diagnose, kein WS-Feld
        'overall': overall,
        'dob': dob,
        'club_team_name': club_team_name,
        'loan_team_name': loan_team_name,
        'decided_status': decided_status,
        'target_club': target_club,
        'decision_reason': decision_reason,
    }

    if dry_run:
        return {'status': 'created', 'player': None, **_base_result}

    # ── Anlegen mit TM-Position ──────────────────────────────────────────────
    with transaction.atomic():
        player = Player.objects.create(
            first_name=first_name,
            last_name=last_name,
            wsc_player_id=wsc_id,
            date_of_birth=dob,
            age=_compute_age(dob),
            main_position_1=tm_position,   # TM-Quelle, niemals CMT
            position=tm_position,           # TM-Quelle, niemals CMT
            potential=max(potential, overall),
            loan_status=decided_status,
            club=target_club,
        )

        PlayerExternalId.objects.create(
            player=player,
            source=cmt_source,
            external_id=cmt_id,
            db_slug=db_slug,
            last_seen_at=timezone.now(),
        )

        PlayerStrengthProfile.objects.create(
            player=player,
            base_strength=overall,
        )

    # PlayerCMTProfile + Attribute automatisch speichern
    try:
        store_player_profiles(players=[raw], db_slug=db_slug, dry_run=False)
    except Exception:
        pass  # Profil ist optional — Player-Anlage bleibt gültig

    return {'status': 'created', 'player': player, **_base_result}
