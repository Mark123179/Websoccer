"""Finanz-Spieltagslauf manuell ausführen (Spec Kap. 15).

Normalfall: läuft automatisch als Hook nach der Spieltag-Simulation
(season_service.simulate_matchday / play_matchday). Dieser Befehl ist der
manuelle/Celery-Pfad und für Nachläufe (idempotent je Verein+Spieltag).

Beispiele:
    python manage.py finance_matchday_run --league 2 --matchday 5
    python manage.py finance_matchday_run --league 2            # aktueller Spieltag
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Führt den Finanz-Spieltagslauf (Gehälter, TV-Sockel, Tickets, Betriebskosten) aus.'

    def add_arguments(self, parser):
        parser.add_argument('--league', type=int, required=True,
                            help='League-ID (z. B. 2 = 1. Bundesliga)')
        parser.add_argument('--season', type=str, default=None,
                            help='Saison-String (Default: aktuelle Sim-Saison)')
        parser.add_argument('--matchday', type=int, default=None,
                            help='Spieltag (Default: aktueller Spieltag der Liga)')

    def handle(self, *args, **opts):
        from game.economy.matchday_run import run_matchday_finance
        from game.finance import current_sim_season
        from game.models import League
        from game.season_service import get_season_state

        try:
            league = League.objects.get(pk=opts['league'])
        except League.DoesNotExist:
            raise CommandError(f'Liga {opts["league"]} existiert nicht.')

        season = opts['season'] or current_sim_season() or '0'
        matchday = opts['matchday']
        if matchday is None:
            matchday = get_season_state(league, season).current_matchday

        summary = run_matchday_finance(league, season, matchday)

        booked = [r for r in summary['clubs'] if not r.get('skipped')]
        skipped = [r for r in summary['clubs'] if r.get('skipped')]

        self.stdout.write(
            f'Finanzlauf {league.name}, Saison {season}, Spieltag {matchday}: '
            f'{len(booked)} Vereine gebucht, {len(skipped)} übersprungen (bereits gelaufen).'
        )
        for r in booked:
            tickets = f", Tickets {r['tickets']:,.0f} €" if r.get('tickets') else ''
            self.stdout.write(
                f"  {r['club']}: TV {r.get('tv_sockel', 0):,.0f} €, "
                f"Gehalt {r['gehalt']:,.0f} €{tickets}, Betrieb {r['betrieb']:,.0f} €"
            )
        for err in summary['errors']:
            self.stderr.write(self.style.ERROR(f'  FEHLER: {err}'))

        if summary['errors']:
            raise CommandError(f"{len(summary['errors'])} Verein(e) fehlgeschlagen.")
