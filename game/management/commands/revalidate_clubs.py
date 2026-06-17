"""Validiert bestehende Vereine/Spieler gegen das CSV-Import-Regelwerk.

Nutzt dasselbe Regelwerk wie der Import (:mod:`game.club_import.validation`),
prüft aber den DB-Bestand statt einer CSV. Optional repariert es typische
Lücken nicht-destruktiv:

* ``--repair``        Potential = Rating (wo fehlend/zu klein) und initiale
                      Stadion-Kapazitätsverteilung aus dem öffentlichen Profil.
* ``--repair --csv``  zusätzlich Attribute via Aktualisierungs-Import nachziehen.
* ``--dry-run``       nur anzeigen, nichts schreiben.
* ``--strict``        Warnungen als Exit-Code 2 melden.

Exit-Codes: 0 = ok, 1 = harte Fehler verbleiben, 2 = nur Warnungen (strict).
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.club_import import validation
from game.club_import.club_reconcile import distribute_capacity


class Command(BaseCommand):
    help = (
        'Validiert (und repariert optional) bestehende Vereine/Spieler gegen '
        'das gemeinsame Import-Regelwerk.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--club', default=None, help='Nur diesen Verein (Name, exakt/iexact).')
        parser.add_argument('--repair', action='store_true', help='Lücken nicht-destruktiv reparieren.')
        parser.add_argument('--csv', default=None, help='CSV für Attribut-Nachzug (mit --repair).')
        parser.add_argument('--dry-run', action='store_true', help='Reparaturen nur anzeigen.')
        parser.add_argument('--strict', action='store_true', help='Warnungen → Exit-Code 2.')

    def handle(self, *args, **options):
        from game.models import Club

        clubs = Club.objects.all().order_by('name')
        if options['club']:
            clubs = clubs.filter(name__iexact=options['club'])
            if not clubs.exists():
                raise CommandError(f'Kein Verein „{options["club"]}".')

        if options['repair'] and options['csv']:
            self._repair_via_csv(options)

        all_issues = []
        for club in clubs:
            if options['repair']:
                for note in self._repair_club(club, options['dry_run']):
                    self.stdout.write(f'  Reparatur [{club.name}]: {note}')

            issues = validation.validate_db_club_full(club)
            all_issues.extend(issues)
            self._print_issues(club, issues)

        errors, warnings = validation.count_levels(all_issues)
        self.stdout.write(
            f'Geprüft: {clubs.count()} Vereine — {errors} Fehler, {warnings} Warnungen.'
        )
        raise SystemExit(validation.exit_code(all_issues, strict=options['strict']))

    # ── Reparatur ─────────────────────────────────────────────────────────────
    def _repair_club(self, club, dry_run):
        notes = []
        notes += self._repair_potentials(club, dry_run)
        notes += self._repair_stadium(club, dry_run)
        return notes

    def _repair_potentials(self, club, dry_run):
        from game.models import PlayerSourceRating

        notes = []
        rows = PlayerSourceRating.objects.filter(
            player__club=club, rating__isnull=False,
        )
        for row in rows:
            if row.potential is None or row.potential < row.rating:
                notes.append(
                    f'{row.player} [{row.source}] potential '
                    f'{row.potential} → {row.rating}'
                )
                if not dry_run:
                    row.potential = row.rating
                    row.save(update_fields=['potential', 'updated_at'])
        return notes

    def _repair_stadium(self, club, dry_run):
        stadium = getattr(club, 'stadium', None)
        pp = getattr(club, 'public_profile', None)
        if stadium is None or pp is None:
            return []
        if stadium.capacity_total > 0:
            return []
        capacity = pp.stadium_capacity
        if not capacity:
            return []
        notes = [f'Stadion-Kapazität initial verteilt auf {capacity}']
        if not dry_run:
            for field, value in distribute_capacity(capacity).items():
                setattr(stadium, field, value)
            stadium.save()
        return notes

    def _repair_via_csv(self, options):
        from game.club_import.club_csv_import import import_club_csv

        try:
            with open(options['csv'], encoding='utf-8-sig') as fh:
                text = fh.read()
        except OSError as exc:
            raise CommandError(f'CSV konnte nicht gelesen werden: {exc}')

        with transaction.atomic():
            result = import_club_csv(text, mode='update', dry_run=options['dry_run'])
            if options['dry_run']:
                transaction.set_rollback(True)
        self.stdout.write(
            f"  Attribut-Nachzug [{result['club'].name}]: "
            f"{result['stats'] or 'DRY-RUN'}"
        )

    # ── Ausgabe ────────────────────────────────────────────────────────────────
    def _print_issues(self, club, issues):
        if not issues:
            return
        self.stdout.write(f'  {club.name}:')
        for issue in issues:
            style = self.style.ERROR if issue['level'] == 'error' else self.style.WARNING
            ref = f" ({issue['ref']})" if issue['ref'] else ''
            self.stdout.write(style(
                f"    [{issue['level']}] {issue['message']}{ref}"
            ))
