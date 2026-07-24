"""Fehlende Sponsor-Verträge automatisch abschließen (Auto-Pick).

Läuft normalerweise automatisch im ersten Finanzlauf der Saison.
Dieser Befehl ist der manuelle Pfad (z. B. nach finance_season_open,
vor dem ersten Spieltag).

Für jeden Ligaverein ohne vollständige Slots wird das Sicherheits-
Angebot des jeweiligen Slots angenommen.

Idempotent: Vereine mit bereits vollständigen Verträgen werden
übersprungen.
"""
import logging

from django.core.management.base import BaseCommand

from game.economy.params import current_season

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Auto-Pick fehlende Sponsoring-Verträge für alle Ligavereine.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--saison', default=None,
            help='Saison-String (Default: aktuelle Sim-Saison)',
        )
        parser.add_argument(
            '--club', type=int, default=None,
            help='Nur diesen Verein (Club-ID) verarbeiten',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur auflisten, nicht schreiben',
        )

    def handle(self, *args, **options):
        from game.economy.sponsors import SLOT_LABELS, SLOTS, finalize_contracts_for_club
        from game.models import Club, SponsorContract

        saison = options['saison'] or current_season()
        dry = options['dry_run']
        club_filter = options['club']

        qs = Club.objects.filter(league__isnull=False).select_related('league')
        if club_filter:
            qs = qs.filter(pk=club_filter)

        total_new = 0
        total_clubs = 0

        for club in qs:
            belegt = set(
                SponsorContract.objects.filter(
                    club=club, saison=saison, abgelaufen=False,
                ).values_list('slot', flat=True)
            )
            fehlend = [s for s in SLOTS if s not in belegt]
            if not fehlend:
                continue

            total_clubs += 1
            if dry:
                self.stdout.write(
                    f'  {club.name}: fehlende Slots = '
                    f'{", ".join(SLOT_LABELS.get(s, s) for s in fehlend)}'
                )
                total_new += len(fehlend)
                continue

            try:
                new = finalize_contracts_for_club(club, saison)
                total_new += len(new)
                if new:
                    slot_names = ', '.join(
                        SLOT_LABELS.get(c.slot, c.slot) for c in new
                    )
                    self.stdout.write(f'  {club.name}: {len(new)} Verträge ({slot_names})')
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f'  FEHLER {club.name}: {exc}')
                )
                logger.exception('finalize_contracts für %s fehlgeschlagen', club)

        if dry:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN: {total_clubs} Vereine, {total_new} Verträge würden angelegt.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Abgeschlossen: {total_clubs} Vereine, {total_new} neue Verträge '
                f'(Saison {saison}).'
            ))
