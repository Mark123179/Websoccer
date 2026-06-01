from django.core.management.base import BaseCommand, CommandError

from game.models import Club, ClubTrophy


class Command(BaseCommand):
    help = (
        'Update the trophy count for a club and competition. '
        'Usage: update_trophy_count <club_name> <competition_name> <new_count>'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'club_name',
            type=str,
            help='Exact name of the club (case-sensitive).',
        )
        parser.add_argument(
            'competition_name',
            type=str,
            help='Exact competition name as stored in ClubTrophy (case-sensitive).',
        )
        parser.add_argument(
            'new_count',
            type=int,
            help='New trophy count (must be >= 0).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would change without saving.',
        )

    def handle(self, *args, **options):
        club_name = options['club_name']
        competition_name = options['competition_name']
        new_count = options['new_count']
        dry_run = options['dry_run']

        if new_count < 0:
            raise CommandError('new_count must be >= 0.')

        try:
            club = Club.objects.get(name=club_name)
        except Club.DoesNotExist:
            similar = list(
                Club.objects.filter(name__icontains=club_name).values_list('name', flat=True)[:5]
            )
            hint = f' Similar clubs: {", ".join(similar)}' if similar else ''
            raise CommandError(f'Club "{club_name}" not found.{hint}')

        try:
            trophy = ClubTrophy.objects.get(club=club, competition_name=competition_name)
        except ClubTrophy.DoesNotExist:
            existing = list(
                ClubTrophy.objects.filter(club=club).values_list('competition_name', flat=True)
            )
            hint = f' Existing competitions for this club: {", ".join(existing)}' if existing else ''
            raise CommandError(
                f'No ClubTrophy record found for club "{club_name}" and competition "{competition_name}".{hint}'
            )

        old_count = trophy.count

        if old_count == new_count:
            self.stdout.write(
                self.style.WARNING(
                    f'Count is already {old_count} for {club_name} / {competition_name}. No change.'
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f'[dry-run] Would update {club_name} / {competition_name}: {old_count} -> {new_count}'
                )
            )
            return

        trophy.count = new_count
        trophy.save(update_fields=['count'])
        self.stdout.write(
            self.style.SUCCESS(
                f'Updated {club_name} / {competition_name}: {old_count} -> {new_count}'
            )
        )
