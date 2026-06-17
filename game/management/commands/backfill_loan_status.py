from django.core.management.base import BaseCommand
from game.models import Player


def _derive_loan_status(player):
    """Leitet den Leihstatus aus dem vorhandenen Vereins-/Leihzustand ab.

    - club=None + real_life_club gesetzt          -> 'loaned_out'
    - club != real_life_club + loan_partner_club  -> 'loaned_in'
    - sonst                                        -> 'none'
    """
    if player.club_id is None and player.real_life_club_id is not None:
        return 'loaned_out'
    if (
        player.real_life_club_id is not None
        and player.club_id != player.real_life_club_id
        and player.loan_partner_club_id is not None
    ):
        return 'loaned_in'
    return 'none'


class Command(BaseCommand):
    help = (
        'Befüllt loan_status bestehender Spieler nachträglich aus dem '
        'vorhandenen Vereins-/Leihzustand (club, real_life_club, '
        'loan_partner_club). Einmalig nach Task #542 gedacht.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Zeigt vorgesehene Änderungen pro Spieler, ohne zu speichern.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Dry-run — keine Änderungen werden gespeichert.'
            ))

        qs = Player.objects.all().order_by('id')

        total = qs.count()
        self.stdout.write(f'{total} Spieler werden geprüft.')

        counts = {'loaned_out': 0, 'loaned_in': 0, 'none': 0}
        updated = 0

        for player in qs.iterator():
            derived = _derive_loan_status(player)
            current = player.loan_status or 'none'
            if derived == current:
                continue

            counts[derived] += 1
            updated += 1

            prefix = '  [dry]' if dry_run else '  '
            self.stdout.write(
                f'{prefix} {player.full_name} (#{player.id}): '
                f'{current!r} -> {derived!r}'
            )

            if not dry_run:
                player.loan_status = derived
                player.save(update_fields=['loan_status'])

        summary = (
            f'{updated} Spieler betroffen '
            f'(loaned_out: {counts["loaned_out"]}, '
            f'loaned_in: {counts["loaned_in"]}, '
            f'none: {counts["none"]}).'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'Dry-run abgeschlossen: {summary}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
