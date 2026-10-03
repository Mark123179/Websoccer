from collections import Counter
from django.core.management.base import BaseCommand
from django.db import transaction
from game.models import SimulatedMatch
from game.match_story.django_bridge import build_story_for


class Command(BaseCommand):
    help = 'Build frozen v4 match stories; historical games stay released.'

    def add_arguments(self, parser):
        parser.add_argument('--since', type=int, default=0)
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        qs = SimulatedMatch.objects.filter(pk__gte=options['since']).order_by('pk')
        if not options['force']:
            qs = qs.filter(story__isnull=True)
        counts = Counter()
        for sm in qs.iterator(chunk_size=50):
            try:
                with transaction.atomic():
                    story = build_story_for(sm, force=options['force'])
                    counts['matches'] += 1
                    counts['lines'] += story.events.count()
                    counts['issues'] += len(story.issues)
                    for issue in story.issues:
                        counts['failed' if issue.startswith('narrator_failed') else 'diagnostics'] += 1
                        if 'Kernzahlen' in issue:
                            counts['core_issues'] += 1
                        elif 'Engine' in issue:
                            counts['engine_actor_issues'] += 1
                        elif 'duration' in issue:
                            counts['timing_issues'] += 1
                        else:
                            counts['other_issues'] += 1
                    self.stdout.write(
                        f'{sm.pk}: lines={story.events.count()} visible='
                        f'{story.events.filter(visible=True).count()} duration={story.duration_s:.2f}s '
                        f'issues={story.issues}')
                    if options['dry_run']:
                        transaction.set_rollback(True)
            except Exception as exc:
                counts['errors'] += 1
                self.stderr.write(f'{sm.pk}: persistence_error {type(exc).__name__}: {exc}')
        self.stdout.write(f'{"DRY-RUN " if options["dry_run"] else ""}SUMMARY {dict(counts)}')