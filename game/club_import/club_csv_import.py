"""Kanonische Orchestrierung des CSV-Imports (Datei → Verein → Spieler).

Eine Funktion, zwei Modi:

* **Vollanlage** (``mode='full'``) — etabliert einen Verein einmal vollständig:
  Reconcile-Upsert der Stammdaten (Verein/Profil/Stadion) + voller Spielerimport
  (Identität, Ratings, alles). Idempotent: erneuter Lauf erzeugt keine Drift.
* **Aktualisierung** (``mode='update'``) — frischt nur volatile Echtweltdaten auf
  (Ratings/Potential/Attribute, Marktwert, Positionen, Verein/Leihstatus). Keine
  neuen Spieler, keine Stammdaten-/Stadionänderungen.

Spielstand/Ökonomie wird in **keinem** Modus angefasst. Validierung läuft über
das gemeinsame :mod:`game.club_import.validation`-Regelwerk.
"""

from .club_reconcile import reconcile_club
from .import_ready_csv import parse_import_ready_csv
from .import_service import import_selected_candidates
from .season import get_current_tm_season_id, season_label
from . import validation

MODE_FULL = 'full'
MODE_UPDATE = 'update'


class ClubImportError(Exception):
    """Fachlicher Importfehler (z. B. Verein nicht auflösbar)."""


def resolve_club(profile, tm_override=None, name_override=None):
    """Löst den Zielverein über TM-ID oder Name auf. Legt nie neue Vereine an."""
    from ..models import Club

    tm_id = tm_override or profile.get('tm_club_id')
    name = name_override or profile.get('club_name')

    club = None
    if tm_id:
        club = Club.objects.filter(transfermarkt_id=tm_id).first()
    if club is None and name:
        matches = Club.objects.filter(name__iexact=name)
        if matches.count() > 1:
            raise ClubImportError(
                f'Vereinsname „{name}" ist mehrdeutig ({matches.count()} '
                f'Treffer) — bitte TM-Vereins-ID angeben.'
            )
        club = matches.first()
    if club is None:
        raise ClubImportError(
            f'Kein Verein gefunden (TM-ID={tm_id}, Name={name!r}). '
            f'Dieser Import legt keine neuen Vereine an.'
        )
    if club.is_import_placeholder:
        raise ClubImportError(
            f'Verein „{club.name}" ist ein Import-Platzhalter — Abbruch.'
        )
    return club


def _create_job_with_candidates(club, profile, players):
    """Legt Importauftrag + Kandidaten an (TM-ID-Dedup, NULL-nie-0)."""
    from ..models import ClubPlayerImportJob, PlayerImportCandidate

    season_id = profile.get('season_id') or get_current_tm_season_id()
    label = profile.get('season_label') or season_label(season_id)
    tm_club_id = club.transfermarkt_id or profile.get('tm_club_id') or 0

    job = ClubPlayerImportJob.objects.create(
        ws_club=club,
        tm_club_id=tm_club_id,
        tm_club_name=profile.get('club_name') or '',
        tm_season_id=season_id,
        season_label=label,
        status=ClubPlayerImportJob.STATUS_IMPORTING,
        progress_total=len(players),
    )

    skipped = []
    seen = set()
    for p in players:
        tm_pid = p['tm_player_id']
        if tm_pid is None or tm_pid in seen:
            skipped.append(p['display_name'])
            continue
        seen.add(tm_pid)
        PlayerImportCandidate.objects.create(
            job=job,
            tm_player_id=tm_pid,
            normalized_data=p['normalized_data'],
            status=PlayerImportCandidate.STATUS_READY,
            selected_for_import=True,
            overwrite_existing=True,
        )
    return job, skipped


def import_club_csv(text, *, mode=MODE_FULL, tm_override=None, name_override=None,
                    recalculate=True, dry_run=False, strict=False, user=None):
    """Importiert eine import_ready-CSV in einem der beiden Modi.

    Returns:
        dict mit Schlüsseln club, parse_warnings, validation_issues, exit_code,
        reconcile_notes, reconcile_warnings, stats, skipped_players, players.
    """
    if mode not in (MODE_FULL, MODE_UPDATE):
        raise ClubImportError(f'Unbekannter Modus: {mode!r}.')

    parsed = parse_import_ready_csv(text)
    profile = parsed['club']
    players = parsed['players']

    club = resolve_club(profile, tm_override, name_override)

    issues = validation.validate_parsed(profile, players)
    code = validation.exit_code(issues, strict=strict)

    result = {
        'club': club,
        'mode': mode,
        'parse_warnings': parsed['warnings'],
        'validation_issues': issues,
        'exit_code': code,
        'reconcile_notes': [],
        'reconcile_warnings': [],
        'stats': None,
        'skipped_players': [],
        'players': players,
    }

    if dry_run:
        return result

    # Vollanlage: Stammdaten erst abgleichen (idempotent, Spielstand unberührt).
    if mode == MODE_FULL:
        rec = reconcile_club(club, profile, dry_run=False)
        result['reconcile_notes'] = rec['notes']
        result['reconcile_warnings'] = rec['warnings']

    job, skipped = _create_job_with_candidates(club, profile, players)
    result['skipped_players'] = skipped

    import_result = import_selected_candidates(
        job, user=user, recalculate=recalculate,
        update_only=(mode == MODE_UPDATE),
    )
    result['stats'] = import_result['stats']

    job.status = job.STATUS_COMPLETED
    job.save(update_fields=['status', 'updated_at'])
    return result
