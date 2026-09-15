import logging

from django.core.management.base import BaseCommand

from game.models import (
    CupFixture,
    CupRound,
    ManagerCareerEntry,
    ManagerTimelineEntry,
)
from game.manager_timeline_service import (
    create_career_end_event,
    create_final_events,
)


class Command(BaseCommand):
    help = (
        'Legt fehlende automatische Manager-Timeline-Ereignisse für '
        'historische Amtszeitenden und zuverlässig abgeschlossene Finals an.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-youth-evidence',
            action='store_true',
            help='Prüft optionale Jugenddaten und protokolliert fehlende Nachweise.',
        )

    def handle(self, *args, **options):
        logger = logging.getLogger(__name__)
        career_created = 0
        career_skipped = 0
        for entry in ManagerCareerEntry.objects.filter(
            active=False, ended_at__isnull=False
        ).select_related('club'):
            before = entry.manager.timeline_entries.filter(
                source_type='career_end',
                source_key=f'career_end:{entry.pk}',
            ).exists()
            create_career_end_event(entry)
            if before:
                career_skipped += 1
            else:
                career_created += 1

        final_created = 0
        final_skipped = 0
        finals = CupFixture.objects.filter(
            cup_round__round_code='final',
            cup_round__status=CupRound.STATUS_COMPLETED,
            status=CupFixture.STATUS_PLAYED,
            winner_club__isnull=False,
        ).select_related(
            'cup_round__cup_season__competition',
            'home_club', 'away_club',
            'home_manager', 'away_manager',
            'simulated_match',
        )
        for fixture in finals:
            before_count = ManagerTimelineEntry.objects.filter(
                source_type='cup_final',
                source_key__startswith=f'cup_final:{fixture.pk}:manager:',
            ).count()
            events = create_final_events(fixture)
            after_count = ManagerTimelineEntry.objects.filter(
                source_type='cup_final',
                source_key__startswith=f'cup_final:{fixture.pk}:manager:',
            ).count()
            created_count = after_count - before_count
            if created_count:
                final_created += created_count
            else:
                final_skipped += 1
            if not events:
                logger.warning(
                    'Finale %s übersprungen: historische Managerzuordnung fehlt.',
                    fixture.pk,
                )
                self.stdout.write(
                    self.style.WARNING(
                        f'Finale {fixture.pk} übersprungen (Manager fehlt).'
                    )
                )

        if options['include_youth_evidence']:
            # Player age/current club is not a transition record.  Deliberately
            # do not infer a promotion from it.
            logger.warning(
                'Jugend-Backfill übersprungen: kein persistierter '
                'Jugend-zu-Pro-Übergang vorhanden.'
            )
            self.stdout.write(self.style.WARNING(
                'Jugend-Backfill übersprungen (kein belastbarer Übergangsnachweis).'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'Amtsenden: {career_created} angelegt, {career_skipped} vorhanden; '
            f'Finals: {final_created} angelegt, {final_skipped} übersprungen/vorhanden.'
        ))