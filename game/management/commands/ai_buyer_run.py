"""Manueller KI-Käufer-Prüflauf (Phase 6, Spec Kap. 9.3).

Beispiele:
  python manage.py ai_buyer_run                      # alle Ligen
  python manage.py ai_buyer_run --league 1           # eine Liga
  python manage.py ai_buyer_run --club 915           # ein Verein
  python manage.py ai_buyer_run --report             # letzte Reports zeigen
"""
import json

from django.core.management.base import BaseCommand, CommandError

from game.economy.ai_buyer import run_ai_buyer_matchday, run_club_pruflauf
from game.finance import current_sim_season
from game.models import AIBuyerRun, Club, League


class Command(BaseCommand):
    help = 'KI-Käufer-Prüflauf manuell starten (Trigger: manuell).'

    def add_arguments(self, parser):
        parser.add_argument('--league', type=int, help='Liga-ID')
        parser.add_argument('--club', type=int, help='Club-ID (nur dieser Verein)')
        parser.add_argument('--spieltag', type=int, default=0,
                            help='Spieltag fürs Protokoll (Default 0)')
        parser.add_argument('--report', action='store_true',
                            help='Letzte Prüflauf-Reports anzeigen')

    def handle(self, *args, **opts):
        saison = current_sim_season() or '0'

        if opts['report']:
            self._zeige_reports(opts)
            return

        if opts['club']:
            try:
                club = Club.objects.get(pk=opts['club'])
            except Club.DoesNotExist:
                raise CommandError(f'Club {opts["club"]} nicht gefunden.')
            if club.managed_by_id is not None:
                raise CommandError(f'{club.name} wird von einem Manager geführt.')
            run = run_club_pruflauf(
                club, saison=saison, spieltag=opts['spieltag'],
                trigger=AIBuyerRun.TRIGGER_MANUELL,
            )
            self.stdout.write(self.style.SUCCESS(f'Prüflauf: {club.name}'))
            self.stdout.write(json.dumps(run.report, indent=2, ensure_ascii=False))
            return

        leagues = League.objects.all()
        if opts['league']:
            leagues = leagues.filter(pk=opts['league'])
            if not leagues.exists():
                raise CommandError(f'Liga {opts["league"]} nicht gefunden.')

        for league in leagues:
            ergebnis = run_ai_buyer_matchday(
                league, saison=saison, spieltag=opts['spieltag'],
                trigger=AIBuyerRun.TRIGGER_MANUELL,
            )
            self.stdout.write(self.style.SUCCESS(
                f'{league.name}: {ergebnis["laeufe"]} Läufe, '
                f'{ergebnis["uebersprungen"]} übersprungen, '
                f'Governor {ergebnis["governor"]["anteil"]}'
            ))

    def _zeige_reports(self, opts):
        qs = AIBuyerRun.objects.select_related('club').order_by('-run_at')
        if opts['club']:
            qs = qs.filter(club_id=opts['club'])
        for run in qs[:10]:
            self.stdout.write(self.style.HTTP_INFO(str(run)))
            self.stdout.write(json.dumps(run.report, indent=2, ensure_ascii=False))
