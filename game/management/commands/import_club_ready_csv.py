"""Import einer „import_ready"-CSV (Verein + Spieler) über den Importdienst.

Nicht-destruktiver Adapter auf ``import_service``: legt einen Importauftrag mit
vorbefüllten ``normalized_data``-Kandidaten an (Update-or-Create, pro Zeile
atomar, NULL-nie-0) und ruft ``import_selected_candidates``. Bestehende Spieler
werden aktualisiert, neue angelegt; es wird NIE ein Kader gelöscht.

Beispiel:
    python manage.py import_club_ready_csv \\
        --csv attached_assets/HSV_import_ready_2025_26_1781684117479.csv
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.club_import.import_ready_csv import parse_import_ready_csv
from game.club_import.import_service import import_selected_candidates
from game.club_import.season import get_current_tm_season_id, season_label

# Stand-Anteile, abgeleitet aus den vorhandenen Bundesliga-Stadien
# (z. B. Deutsche Bank Park 58.000) — proportional auf jede Kapazität anwendbar.
STADIUM_STAND_RATIOS = {
    'nord_standing': 0.175,
    'nord_seating': 0.075,
    'ost_seating': 0.25,
    'sued_standing': 0.0375,
    'sued_seating': 0.2125,
    'west_seating': 0.205,
    'west_vip': 0.045,
}


class Command(BaseCommand):
    help = (
        'Importiert eine import_ready-CSV (Vereinsprofil + Spieler) '
        'nicht-destruktiv über den bestehenden Importdienst.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--csv', required=True, help='Pfad zur CSV-Datei.')
        parser.add_argument(
            '--tm-club-id', type=int, default=None,
            help='Überschreibt die in der CSV genannte Transfermarkt-Vereins-ID.',
        )
        parser.add_argument(
            '--club-name', default=None,
            help='Alternative Vereinsauflösung per Name (statt TM-ID).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur analysieren und Plan ausgeben — nichts schreiben.',
        )
        parser.add_argument(
            '--no-recalculate', action='store_true',
            help='Stärkeprofile nach dem Import NICHT neu berechnen.',
        )

    # ── Vereinsauflösung ────────────────────────────────────────────────────
    def _resolve_club(self, profile, tm_override, name_override):
        from game.models import Club

        tm_id = tm_override or profile.get('tm_club_id')
        name = name_override or profile.get('club_name')

        club = None
        if tm_id:
            club = Club.objects.filter(transfermarkt_id=tm_id).first()
        if club is None and name:
            matches = Club.objects.filter(name__iexact=name)
            if matches.count() > 1:
                raise CommandError(
                    f'Vereinsname „{name}" ist mehrdeutig ({matches.count()} '
                    f'Treffer) — bitte --tm-club-id angeben.'
                )
            club = matches.first()
        if club is None:
            raise CommandError(
                f'Kein Verein gefunden (TM-ID={tm_id}, Name={name!r}). '
                f'Dieser Import legt keine neuen Vereine an.'
            )
        if club.is_import_placeholder:
            raise CommandError(
                f'Verein „{club.name}" ist ein Import-Platzhalter — Abbruch.'
            )
        return club

    # ── Profil-/Stadionvervollständigung (fill-if-empty) ────────────────────
    def _complete_club(self, club, profile, dry_run):
        notes = []

        # Gründungsjahr: CSV ist maßgeblich; offensichtliche Altfehler werden
        # korrigiert (z. B. 1987 → 1887), sonst nur gesetzt, wenn leer.
        csv_year = profile.get('founded_year')
        if csv_year and club.founded_year != csv_year:
            notes.append(f'founded_year {club.founded_year} → {csv_year}')
            if not dry_run:
                club.founded_year = csv_year

        if profile.get('fmi_club_id') and not club.fm_inside_id:
            notes.append(f"fm_inside_id → {profile['fmi_club_id']}")
            if not dry_run:
                club.fm_inside_id = profile['fmi_club_id']

        if not dry_run:
            club.save()

        notes += self._complete_public_profile(club, profile, dry_run)
        notes += self._complete_stadium(club, profile, dry_run)
        return notes

    def _complete_public_profile(self, club, profile, dry_run):
        from game.models import ClubPublicProfile

        notes = []
        pp = getattr(club, 'public_profile', None)
        if pp is None:
            notes.append('public_profile angelegt')
            pp = ClubPublicProfile(club=club)

        fields = {
            'stadium_name': profile.get('stadium_name'),
            'city_name': profile.get('club_city'),
            'city_country': profile.get('country'),
            'stadium_capacity': profile.get('stadium_capacity'),
            'map_lat': profile.get('latitude'),
            'map_lng': profile.get('longitude'),
        }
        for field, value in fields.items():
            if not value:
                continue
            current = getattr(pp, field, None)
            if not current:  # leer / 0 / None → füllen
                notes.append(f'profile.{field} → {value}')
                if not dry_run:
                    setattr(pp, field, value)
        if not dry_run:
            pp.save()
        return notes

    def _complete_stadium(self, club, profile, dry_run):
        from game.models import Stadium

        if getattr(club, 'stadium', None) is not None:
            return []

        capacity = profile.get('stadium_capacity')
        name = profile.get('stadium_name')
        if not capacity or not name:
            return []

        stands = {
            field: int(round(capacity * ratio))
            for field, ratio in STADIUM_STAND_RATIOS.items()
        }
        # Rundungsdifferenz auf den größten Block (Ost-Sitzplätze) legen.
        diff = capacity - sum(stands.values())
        stands['ost_seating'] += diff

        note = (
            f'Stadion „{name}" ({profile.get("stadium_city") or ""}) '
            f'angelegt, Kapazität {capacity}'
        )
        if not dry_run:
            Stadium.objects.create(
                club=club,
                name=name,
                city=profile.get('stadium_city') or profile.get('club_city') or '',
                **stands,
            )
        return [note]

    # ── Hauptablauf ─────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        path = options['csv']
        dry_run = options['dry_run']
        recalculate = not options['no_recalculate']

        try:
            with open(path, encoding='utf-8-sig') as fh:
                text = fh.read()
        except OSError as exc:
            raise CommandError(f'CSV konnte nicht gelesen werden: {exc}')

        parsed = parse_import_ready_csv(text)
        profile = parsed['club']
        players = parsed['players']

        for warning in parsed['warnings']:
            self.stdout.write(self.style.WARNING(f'  ⚠ {warning}'))

        club = self._resolve_club(
            profile, options['tm_club_id'], options['club_name']
        )
        self.stdout.write(
            f'Zielverein: {club.name} (#{club.id}, TM {club.transfermarkt_id})'
        )

        profile_notes = self._complete_club(club, profile, dry_run)
        for note in profile_notes:
            self.stdout.write(f'  Profil: {note}')

        self.stdout.write(
            f'{len(players)} Spielerzeilen gelesen '
            f'({"DRY-RUN" if dry_run else "Import"}).'
        )

        if dry_run:
            for p in players:
                nd = p['normalized_data']
                self.stdout.write(
                    f"  · {p['display_name']:28} "
                    f"[{p['squad_status'] or '-':10}] "
                    f"pos={','.join(nd['main_positions']) or '-':8} "
                    f"nat={nd['nationalities']}"
                )
            self.stdout.write(self.style.NOTICE('DRY-RUN — nichts geschrieben.'))
            return

        stats = self._run_import(club, profile, players, recalculate)
        self.stdout.write(self.style.SUCCESS(
            "Fertig: {created} neu, {updated} aktualisiert, "
            "{skipped} übersprungen, {failed} fehlgeschlagen.".format(**stats)
        ))

    def _run_import(self, club, profile, players, recalculate):
        from game.models import ClubPlayerImportJob, PlayerImportCandidate

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

        seen = set()
        for p in players:
            tm_pid = p['tm_player_id']
            if tm_pid is None or tm_pid in seen:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ {p['display_name']}: fehlende/doppelte TM-ID — "
                    f"übersprungen."
                ))
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

        result = import_selected_candidates(job, recalculate=recalculate)

        job.status = ClubPlayerImportJob.STATUS_COMPLETED
        job.save(update_fields=['status', 'updated_at'])
        return result['stats']
