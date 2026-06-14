"""
Management-Command: Alle Pokal-Runden terminieren.

Legt fehlende CupRound-Einträge (Runden 2-5) an und setzt
scheduled_date für alle Runden via auto_schedule_cup_season().

Aufruf:
    python manage.py schedule_cup_rounds
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Alle Pokal-Runden terminieren (fehlende anlegen + Datum setzen)'

    def handle(self, *args, **options):
        from game.models import CupSeason, CupRound, SeasonFixture
        from game.cup_service import auto_schedule_cup_season

        cs = CupSeason.objects.filter(
            competition__competition_type='cup'
        ).select_related('competition').first()

        if not cs:
            self.stderr.write('Keine CupSeason gefunden.')
            return

        self.stdout.write(f'CupSeason: {cs.competition.name} {cs.season}')
        self.stdout.write(f'Teilnehmer: {cs.participants.count()}')

        # Liga-Termine aus der 1. Bundesliga holen
        liga_dates = sorted(set(
            SeasonFixture.objects
            .filter(league__name='1. Bundesliga', scheduled_date__isnull=False)
            .values_list('scheduled_date', flat=True)
        ))
        self.stdout.write(f'Liga-Termine: {len(liga_dates)} gefunden')

        # Terminvorschläge berechnen
        proposals = auto_schedule_cup_season(cs, liga_dates)

        if not proposals:
            self.stderr.write('Keine Vorschläge generiert.')
            return

        with transaction.atomic():
            for p in proposals:
                if p['is_future']:
                    # Neue Runde anlegen
                    cr = CupRound.objects.create(
                        cup_season=cs,
                        round_number=p['round_number'],
                        round_code=p['round_code'],
                        status=CupRound.STATUS_SCHEDULED,
                        scheduled_date=p['proposed_date'],
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  + Runde {p["round_number"]} angelegt: '
                            f'{p["round_code"]} → {p["proposed_date"]}'
                        )
                    )
                else:
                    CupRound.objects.filter(pk=p['round_id']).update(
                        scheduled_date=p['proposed_date'],
                        status=CupRound.STATUS_SCHEDULED,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Runde {p["round_number"]} terminiert: '
                            f'{p["round_code"]} → {p["proposed_date"]}'
                        )
                    )

        self.stdout.write(self.style.SUCCESS(
            f'\n{len(proposals)} Runden terminiert.'
        ))
