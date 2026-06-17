"""Serverseitiger, verbindlicher Datenbankimport (Spec §16–§22).

Konsumiert ``PlayerImportCandidate.normalized_data`` und schreibt Spieler,
Vereine (Platzhalter), Quell-Ratings und Stärkeprofile. Pro Kandidat in einer
eigenen ``transaction.atomic``-Klammer — ein einzelner Fehler bricht den Stapel
nicht ab.

NULL-Erhalt: Fehlende Werte bleiben ``None`` / ``''`` — niemals ``0``. Beim
Überschreiben werden alte Quellwerte vollständig ersetzt bzw. auf ``None``
gesetzt (oder die Quellzeile gelöscht), damit keine Altwerte zurückbleiben.

``normalized_data``-Schema (von API/lokalem Importer befüllt):
    tm_player_id, transfermarkt_profile_url
    first_name, last_name, date_of_birth ("YYYY-MM-DD")
    height_cm, strong_foot, primary_nationality, nationalities, market_value
    profile_position, main_positions[], secondary_positions[]
    fm_inside_id, sofifa_id, sofifa_profile_url
    real_club / loaned_from: {tm_id, name, profile_url} | None
    fmi_ratings / sofifa_ratings: {rating, potential, attrs:{feld:wert}} | None
"""

from datetime import date, datetime
from decimal import Decimal

from django.db import transaction

from .normalization import normalize_name
from .matching import find_existing_player
from .season import BERLIN_TZ

# Alle Attributfelder von PlayerSourceRating (ohne rating/potential).
# Beim Schreiben werden ALLE gesetzt; fehlende → None (löscht Altwerte).
PSR_ATTR_FIELDS = [
    'tempo', 'ausdauer', 'kraft', 'technik', 'dribbling', 'passspiel',
    'flanken', 'abschluss', 'kopfball', 'zweikampf', 'defensivstellung',
    'uebersicht', 'teamwork', 'ecken', 'freistoss', 'elfmeter',
    'tw_reflexe', 'tw_fangsicherheit', 'tw_eins_gegen_eins',
    'tw_stellungsspiel', 'tw_passen',
]

ACTION_CREATED = 'created'
ACTION_UPDATED = 'updated'
ACTION_SKIPPED = 'skipped'
ACTION_FAILED = 'failed'


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _compute_age(dob):
    if not dob:
        return None
    today = datetime.now(BERLIN_TZ).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _placeholder_league():
    from ..models import League
    league, _ = League.objects.get_or_create(
        name='Platzhalter (Import)',
        defaults={'country': 'Unbekannt'},
    )
    return league


def get_or_create_club(club_ref):
    """Findet oder erstellt einen (Platzhalter-)Verein für einen TM-Vereinsbezug.

    Dedup-Priorität: Club.transfermarkt_id, danach normalisierter Name. Neu
    angelegte Vereine sind Minimal-Platzhalter (``is_import_placeholder=True``).
    """
    from ..models import Club

    if not club_ref:
        return None

    tm_id = club_ref.get('tm_id')
    name = (club_ref.get('name') or '').strip()

    if tm_id:
        existing = Club.objects.filter(transfermarkt_id=tm_id).first()
        if existing:
            return existing

    if name:
        target = normalize_name(name)
        if target:
            for club in Club.objects.all():
                if normalize_name(club.name) == target:
                    return club

    display_name = name or (f'TM-Verein {tm_id}' if tm_id else 'Unbekannter Verein')
    return Club.objects.create(
        transfermarkt_id=tm_id or None,
        transfermarkt_profile_url=club_ref.get('profile_url', '') or '',
        is_import_placeholder=True,
        name=display_name,
        short_name=display_name[:20],
        founded_year=0,
        budget=Decimal('0'),
        league=_placeholder_league(),
    )


def create_or_promote_target_club(tm_club_id, name, league, profile_url=''):
    """Legt einen echten WS-Zielverein für einen Import an (oder stuft ihn hoch).

    Wird beim Anlegen eines Importauftrags für einen im WS noch nicht
    existierenden Verein verwendet. Im Gegensatz zu :func:`get_or_create_club`
    entsteht ein **echter** Verein (``is_import_placeholder=False``) in der
    angegebenen, real existierenden Liga.

    Dedup-Priorität: ``Club.transfermarkt_id``, danach normalisierter Name.

    Rückgabe: ``(club, status)`` mit ``status`` ∈
    ``{'created', 'promoted', 'exists', 'conflict'}``. ``'promoted'`` bedeutet,
    dass ein bereits vorhandener Platzhalterverein (z. B. früher als Leihgeber
    angelegt) zum echten Verein hochgestuft wurde. ``'exists'`` bedeutet, dass
    bereits ein echter (nicht-Platzhalter-)Verein existiert. ``'conflict'``
    bedeutet, dass ein Namenstreffer eine **abweichende** Transfermarkt-ID
    trägt (Identitätskonflikt). In beiden Fällen soll der Aufrufer mit einem
    Hinweis abbrechen, statt ein Duplikat oder einen widersprüchlichen Verein zu
    erzeugen.
    """
    from django.db import IntegrityError, transaction
    from ..models import Club

    name = (name or '').strip()

    def _resolve_existing():
        """Gibt ``(club, matched_by)`` zurück, ``matched_by`` ∈ {'tm','name',None}."""
        if tm_club_id:
            club = Club.objects.filter(transfermarkt_id=tm_club_id).first()
            if club:
                return club, 'tm'
        target = normalize_name(name)
        if target:
            for club in Club.objects.all():
                if normalize_name(club.name) == target:
                    return club, 'name'
        return None, None

    def _promote(existing):
        existing.is_import_placeholder = False
        existing.league = league
        if name:
            existing.name = name
            existing.short_name = name[:20]
        if tm_club_id and not existing.transfermarkt_id:
            existing.transfermarkt_id = tm_club_id
        if profile_url and not existing.transfermarkt_profile_url:
            existing.transfermarkt_profile_url = profile_url
        # Manuell eingegebener Name → später per TM-Name bestätigen/aktualisieren.
        existing.import_name_provisional = True
        existing.save()
        return existing

    def _classify(existing, matched_by):
        # Namenstreffer mit gesetzter, abweichender TM-ID → Identitätskonflikt.
        if (matched_by == 'name' and existing.transfermarkt_id
                and tm_club_id and existing.transfermarkt_id != tm_club_id):
            return existing, 'conflict'
        if not existing.is_import_placeholder:
            return existing, 'exists'
        return _promote(existing), 'promoted'

    existing, matched_by = _resolve_existing()
    if existing is not None:
        return _classify(existing, matched_by)

    try:
        with transaction.atomic():
            club = Club.objects.create(
                transfermarkt_id=tm_club_id or None,
                transfermarkt_profile_url=profile_url or '',
                is_import_placeholder=False,
                import_name_provisional=True,
                name=name,
                short_name=name[:20],
                founded_year=0,
                budget=Decimal('0'),
                league=league,
            )
        return club, 'created'
    except IntegrityError:
        # Nebenläufiger Insert mit gleicher TM-ID — erneut auflösen statt 500.
        existing, matched_by = _resolve_existing()
        if existing is None:
            raise
        return _classify(existing, matched_by)


def _write_source_rating(player, source, ratings):
    """Schreibt eine PlayerSourceRating-Zeile (Quelle FM/EA) oder löscht sie.

    ``ratings`` = {rating, potential, attrs:{feld:wert}} oder ``None``/leer.
    Bei vorhandenem Rating werden ALLE Attributfelder gesetzt (fehlende → None),
    sodass keine Altwerte zurückbleiben. Ohne neue Daten wird die Zeile gelöscht.
    """
    from ..models import PlayerSourceRating

    if not ratings or ratings.get('rating') is None:
        PlayerSourceRating.objects.filter(player=player, source=source).delete()
        return False

    attrs = ratings.get('attrs') or {}
    defaults = {
        'rating': ratings['rating'],
        'potential': ratings.get('potential'),
    }
    for field in PSR_ATTR_FIELDS:
        defaults[field] = attrs.get(field)

    PlayerSourceRating.objects.update_or_create(
        player=player, source=source, defaults=defaults,
    )
    return True


def _apply_sofifa_external_id(player, sofifa_id, profile_url):
    from ..models import DataSource, PlayerExternalId

    if sofifa_id:
        source, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_SOFIFA,
            defaults={'name': 'SoFIFA'},
        )
        PlayerExternalId.objects.update_or_create(
            player=player, source=source,
            defaults={
                'external_id': str(sofifa_id),
                'profile_url': profile_url or '',
            },
        )
    else:
        source = DataSource.objects.filter(code=DataSource.CODE_SOFIFA).first()
        if source:
            PlayerExternalId.objects.filter(player=player, source=source).delete()


def _recalculate_strength(player):
    """Berechnet und persistiert das Stärkeprofil (wie calculate_player_strengths)."""
    from ..models import PlayerStrengthProfile
    from ..strength_service import compute_strength_for_player

    result = compute_strength_for_player(player)
    if not result.get('computable'):
        return
    new_base = result['base_strength']
    profile = getattr(player, 'strength_profile', None)
    if profile is None:
        PlayerStrengthProfile.objects.update_or_create(
            player=player,
            defaults={
                'base_strength': new_base,
                'form_modifier': Decimal('0.00'),
                'freshness': Decimal('100.00'),
            },
        )
    else:
        profile.base_strength = new_base
        profile.save(update_fields=['base_strength'])


def validate_candidate(nd):
    """Pflichtfeld-Validierung vor dem DB-Import. Gibt Fehlerliste zurück."""
    errors = []
    if not (nd.get('first_name') or '').strip() and not (nd.get('last_name') or '').strip():
        errors.append('Kein Spielername vorhanden.')
    if not (nd.get('main_positions') or []):
        errors.append('Keine Hauptposition bestimmt.')
    return errors


def import_candidate(candidate, user=None, recalculate=True):
    """Importiert genau einen Kandidaten in einer eigenen Transaktion.

    Returns:
        dict {candidate, action, player, errors}
    """
    from ..models import Player, PlayerEditLog, PlayerSourceRating

    nd = candidate.normalized_data or {}

    errors = validate_candidate(nd)
    if errors:
        candidate.status = candidate.STATUS_INVALID
        candidate.validation_errors = errors
        candidate.save(update_fields=['status', 'validation_errors', 'updated_at'])
        return {'candidate': candidate.pk, 'action': ACTION_FAILED,
                'player': None, 'errors': errors}

    job = candidate.job
    ws_club = job.ws_club

    dob = _parse_date(nd.get('date_of_birth'))
    match = find_existing_player(
        tm_player_id=nd.get('tm_player_id'),
        fm_inside_id=nd.get('fm_inside_id'),
        sofifa_id=nd.get('sofifa_id'),
        name=f"{nd.get('first_name', '')} {nd.get('last_name', '')}",
        date_of_birth=dob,
    )
    existing = match['player'] if match['is_strong'] else None

    if existing is None and match['player'] is not None and not candidate.overwrite_existing:
        # Schwache Namens-/Geburtsdatum-Dublette ohne ausdrückliches Überschreiben.
        candidate.existing_player = match['player']
        candidate.status = candidate.STATUS_EXISTING_CHANGED
        candidate.save(update_fields=['existing_player', 'status', 'updated_at'])
        return {'candidate': candidate.pk, 'action': ACTION_SKIPPED,
                'player': match['player'].pk, 'errors': []}

    if existing is not None and not candidate.overwrite_existing:
        candidate.existing_player = existing
        candidate.status = candidate.STATUS_EXISTING_UNCHANGED
        candidate.save(update_fields=['existing_player', 'status', 'updated_at'])
        return {'candidate': candidate.pk, 'action': ACTION_SKIPPED,
                'player': existing.pk, 'errors': []}

    with transaction.atomic():
        is_new = existing is None
        player = existing if existing is not None else Player()

        player.first_name = (nd.get('first_name') or '').strip()
        player.last_name = (nd.get('last_name') or '').strip()
        player.date_of_birth = dob

        age = _compute_age(dob)
        if age is not None:
            player.age = age
        elif is_new:
            player.age = 0

        player.height_cm = nd.get('height_cm')
        player.strong_foot = nd.get('strong_foot') or ''
        player.nationalities = nd.get('nationalities') or ''
        player.market_value = nd.get('market_value')

        player.transfermarkt_id = nd.get('tm_player_id') or None
        player.transfermarkt_profile_url = nd.get('transfermarkt_profile_url') or ''
        player.fm_inside_id = nd.get('fm_inside_id') or None

        mains = nd.get('main_positions') or []
        secs = nd.get('secondary_positions') or []
        player.main_position_1 = mains[0] if len(mains) > 0 else ''
        player.main_position_2 = mains[1] if len(mains) > 1 else ''
        player.main_position_3 = mains[2] if len(mains) > 2 else ''
        player.secondary_position_1 = secs[0] if len(secs) > 0 else ''
        player.secondary_position_2 = secs[1] if len(secs) > 1 else ''
        player.secondary_position_3 = secs[2] if len(secs) > 2 else ''
        if mains:
            player.position = mains[0]
            player.primary_position = mains[0]

        # Vereins-/Leihlogik (Spec §10).
        # ``loan_status`` ist optional (rückwärtskompatibel): ist es nicht
        # gesetzt, ergibt sich der Status implizit aus loaned_from/real_club.
        loan_ref = nd.get('loaned_from')
        real_ref = nd.get('real_club')
        loan_status = nd.get('loan_status')
        if loan_status == 'loaned_out':
            # Eigentum des Auftragsvereins, spielt aber anderswo → im Spiel
            # vereinslos (club=None), Eigentümer = real_life_club.
            player.club = None
            player.real_life_club = get_or_create_club(real_ref) if real_ref else ws_club
            player.loan_partner_club = None
            player.loan_status = 'loaned_out'
        elif loan_ref:
            parent = get_or_create_club(loan_ref)
            player.club = ws_club
            player.real_life_club = parent
            player.loan_partner_club = parent
            player.loan_status = 'loaned_in'
        elif real_ref:
            player.club = ws_club
            player.real_life_club = get_or_create_club(real_ref)
            player.loan_partner_club = None
            player.loan_status = 'none'
        else:
            player.club = ws_club
            player.real_life_club = ws_club
            player.loan_partner_club = None
            player.loan_status = 'none'

        player.save()

        _apply_sofifa_external_id(
            player, nd.get('sofifa_id'), nd.get('sofifa_profile_url'),
        )

        _write_source_rating(player, PlayerSourceRating.SOURCE_FM, nd.get('fmi_ratings'))
        _write_source_rating(player, PlayerSourceRating.SOURCE_EA, nd.get('sofifa_ratings'))

        action = ACTION_CREATED if is_new else ACTION_UPDATED
        PlayerEditLog.objects.create(
            player=player,
            changed_by=(user if (user is not None and getattr(user, 'is_authenticated', False)) else None),
            category=PlayerEditLog.CATEGORY_SYSTEM,
            summary=(
                f'Spielerimport ({"neu" if is_new else "aktualisiert"}) — '
                f'Auftrag #{job.pk}, TM {nd.get("tm_player_id")}.'
            ),
        )

        # Stärkeprofil im selben Transaktionsrahmen — Import ist all-or-nothing.
        if recalculate:
            _recalculate_strength(player)

        candidate.existing_player = player
        candidate.status = candidate.STATUS_IMPORTED
        candidate.save(update_fields=['existing_player', 'status', 'updated_at'])

    return {'candidate': candidate.pk, 'action': action,
            'player': player.pk, 'errors': []}


def import_selected_candidates(job, user=None, recalculate=True):
    """Importiert alle ausgewählten Kandidaten eines Auftrags.

    Jeder Kandidat läuft in eigener Transaktion; ein einzelner Fehler bricht den
    Stapel nicht ab (er wird als ``failed`` protokolliert).

    Returns:
        dict {stats:{created,updated,skipped,failed}, results:[...]}
    """
    stats = {ACTION_CREATED: 0, ACTION_UPDATED: 0,
             ACTION_SKIPPED: 0, ACTION_FAILED: 0}
    results = []

    candidates = job.candidates.filter(selected_for_import=True)
    for candidate in candidates:
        try:
            result = import_candidate(candidate, user=user, recalculate=recalculate)
        except Exception as exc:  # noqa: BLE001 — ein Fehler darf den Stapel nicht abbrechen
            candidate.status = candidate.STATUS_SOURCE_ERROR
            candidate.validation_errors = list(candidate.validation_errors or []) + [str(exc)]
            candidate.save(update_fields=['status', 'validation_errors', 'updated_at'])
            stats[ACTION_FAILED] += 1
            results.append({'candidate': candidate.pk, 'action': ACTION_FAILED,
                            'player': None, 'errors': [str(exc)]})
            continue
        stats[result['action']] = stats.get(result['action'], 0) + 1
        results.append(result)

    return {'stats': stats, 'results': results}
