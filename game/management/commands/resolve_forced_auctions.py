"""Management Command: resolve_forced_auctions

Wertet alle fälligen Zwangsversteigerungen aus (Spec Kap. 12.3): pro Auktion
gewinnt das höchste Gebot (bei Gleichstand das früher abgegebene). Der Erlös
geht an den Schuldnerverein (execute_money_transfer inkl. Ausbildungsabgabe).
Scheitert der Höchstbietende an Deckung/Kaderplatz, rückt das nächsthöhere
Gebot nach; ohne wertbares Gebot endet die Auktion als 'Kein Zuschlag'.

Verwendung:
    python manage.py resolve_forced_auctions
    python manage.py resolve_forced_auctions --date 2026-07-19
    python manage.py resolve_forced_auctions --dry-run
"""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Wertet fällige Zwangsversteigerungen aus (höchstes Gebot gewinnt).'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None,
                            help='Stichtag YYYY-MM-DD (default: heute).')
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='Nur anzeigen, welche Auktionen fällig wären.')

    def handle(self, *args, **options):
        from django.utils import timezone
        from game.economy import forced_auction
        from game.models import ForcedAuction

        ref = options.get('date')
        if ref:
            try:
                today = datetime.strptime(ref, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Ungültiges Datum. Bitte Format YYYY-MM-DD verwenden.')
        else:
            today = timezone.localdate()

        due = (
            ForcedAuction.objects
            .filter(status=ForcedAuction.STATUS_OPEN, ends_on__lte=today)
            .select_related('player', 'seller_club')
            .order_by('ends_on')
        )
        if not due.exists():
            self.stdout.write(self.style.WARNING(
                f'Keine fälligen Zwangsversteigerungen bis {today}.'
            ))
            return

        if options['dry_run']:
            self.stdout.write(f'[dry-run] Fällige Auktionen bis {today}:')
            for a in due:
                self.stdout.write(
                    f'  • {a.player.full_name} ({a.seller_club.name}), '
                    f'Termin {a.ends_on}, {a.bids.count()} Gebot(e)'
                )
            return

        summary = forced_auction.resolve_due_auctions(today=today)
        self.stdout.write(self.style.SUCCESS(
            f'Aufgelöst: {summary["auctions"]} Auktion(en), '
            f'{summary["settled"]} Zuschlag/Zuschläge, '
            f'{summary["unsold"]} ohne Zuschlag, '
            f'{summary["cancelled"]} abgebrochen (Konto bereinigt).'
        ))
