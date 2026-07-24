"""
Management-Command: assign_referees_to_past_matches

Weist allen SimulatedMatch-Zeilen ohne Referee einen Schiedsrichter zu,
der den Berechtigungsregeln von referee_service.pick_referee() entspricht.

Idempotent: Zeilen mit bereits gesetztem Referee werden nicht überschrieben.
Pool wird einmalig vorgeladen (kein order_by('?') pro Spiel).

Optionen:
  --dry-run   Nur anzeigen, wie viele Spiele aktualisiert würden.
"""

from django.core.management.base import BaseCommand
from game.models import SimulatedMatch, Referee
from game.referee_service import pick_referee, preload_referee_pool


class Command(BaseCommand):
    help = "Weist Spielen ohne Referee rückwirkend einen passenden zu (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        if not Referee.objects.exists():
            self.stdout.write("Keine Referees in der DB — nichts zu tun.")
            return

        qs = SimulatedMatch.objects.filter(referee__isnull=True).select_related(
            'home_club', 'home_club__league',
            'away_club', 'away_club__league',
        )
        total = qs.count()

        if opts['dry_run']:
            self.stdout.write(f"[Dry-Run] {total} Spiele ohne Referee.")
            return

        preloaded = preload_referee_pool()
        updated = 0

        for match in qs.iterator(chunk_size=200):
            league   = None
            matchday = None
            season   = match.season

            try:
                sf = match.season_fixture
                league   = sf.league
                matchday = sf.matchday
            except Exception:
                pass

            cup_fixture = None
            try:
                cf = match.home_club  # CupFixture hat kein direktes reverse auf SimulatedMatch
            except Exception:
                pass

            ref = pick_referee(
                home_club=match.home_club,
                away_club=match.away_club,
                league=league,
                matchday=matchday,
                season=str(season),
                _preloaded=preloaded,
            )
            if ref is not None:
                match.referee = ref
                match.save(update_fields=['referee'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"{updated} Spiele aktualisiert."))
