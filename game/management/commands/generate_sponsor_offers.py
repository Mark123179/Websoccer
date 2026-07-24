"""Sponsor-Angebote (V2) für alle Ligavereine generieren.

Idempotent: Vereine mit bereits vollständigen offenen V2-Angeboten
werden übersprungen.

Läuft automatisch zu Saisonbeginn (via Celery Beat / finance_season_open).
Kann manuell für einzelne Vereine oder eine explizite Saison aufgerufen werden.
"""
import logging

from django.core.management.base import BaseCommand

from game.economy.params import current_season

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'V2-Sponsor-Angebote für alle Ligavereine generieren (idempotent).'

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
            help='Nur auflisten wie viele Angebote fehlen, nicht schreiben',
        )

    def handle(self, *args, **options):
        from game.economy.sponsors import SLOTS, generate_offers_v2
        from game.models import Club, SponsorOffer

        saison = options['saison'] or current_season()
        dry = options['dry_run']
        club_filter = options['club']

        qs = Club.objects.filter(league__isnull=False)
        if club_filter:
            qs = qs.filter(pk=club_filter)

        total_clubs = 0
        total_offers = 0

        for club in qs:
            # Schnell-Check: Hat der Verein schon offene Angebote für alle Slots?
            vorhandene_slots = set(
                SponsorOffer.objects.filter(
                    club=club, saison=saison, status='offen',
                ).values_list('slot', flat=True).distinct()
            )
            fehlende = [s for s in SLOTS if s not in vorhandene_slots]
            if not fehlende:
                continue

            total_clubs += 1
            if dry:
                self.stdout.write(
                    f'  {club.name}: {len(fehlende)} Slots ohne offene Angebote'
                )
                total_offers += len(fehlende) * 2  # Schätzung
                continue

            try:
                result = generate_offers_v2(club, saison)
                n_new = sum(len(v) for v in result.values())
                total_offers += n_new
                self.stdout.write(f'  {club.name}: {n_new} Angebote generiert')
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f'  FEHLER {club.name}: {exc}')
                )
                logger.exception('generate_offers_v2 für %s fehlgeschlagen', club)

        if dry:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN: {total_clubs} Vereine, ca. {total_offers} neue Angebote.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Abgeschlossen: {total_clubs} Vereine, {total_offers} Angebote '
                f'(Saison {saison}).'
            ))
