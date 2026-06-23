"""Management Command: resolve_scouting_window

Wertet alle fälligen Scouting-Zuschlagstermine aus: pro Spieler gewinnt das
höchste aktive Gebot (bei Gleichstand das früher abgegebene). Der Gewinner wird
verpflichtet (Geld belastet, Spieler dem Verein zugeordnet), Verlierer-Gebote
werden freigegeben. Idempotent: bereits aufgelöste Gebote bleiben unberührt.

Verwendung:
    python manage.py resolve_scouting_window
    python manage.py resolve_scouting_window --date 2026-07-03
    python manage.py resolve_scouting_window --dry-run
"""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Wertet fällige Scouting-Zuschlagstermine aus (höchstes Gebot gewinnt).'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None,
                            help='Stichtag YYYY-MM-DD (default: heute).')
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='Nur anzeigen, welche Termine/Gebote fällig wären.')

    def handle(self, *args, **options):
        from django.utils import timezone
        from game.models import ScoutingBid
        from game.scouting import service

        ref = options.get('date')
        if ref:
            try:
                today = datetime.strptime(ref, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Ungültiges Datum. Bitte Format YYYY-MM-DD verwenden.')
        else:
            today = timezone.localdate()

        due = (
            ScoutingBid.objects
            .filter(status=ScoutingBid.STATUS_ACTIVE, window_date__lte=today)
            .order_by('window_date')
        )
        due_dates = sorted(set(due.values_list('window_date', flat=True)))

        if not due_dates:
            self.stdout.write(self.style.WARNING(f'Keine fälligen Zuschlagstermine bis {today}.'))
            return

        if options['dry_run']:
            self.stdout.write(f'[dry-run] Fällige Termine bis {today}: {len(due_dates)}')
            for wd in due_dates:
                cnt = due.filter(window_date=wd).count()
                players = due.filter(window_date=wd).values('player_id').distinct().count()
                self.stdout.write(f'  • {wd}: {cnt} aktive Gebote auf {players} Spieler')
            return

        summary = service.resolve_due_windows(today=today)
        self.stdout.write(self.style.SUCCESS(
            f'Aufgelöst: {summary["windows"]} Termin(e), '
            f'{summary["won"]} Verpflichtung(en), {summary["lost"]} verlorene Gebote.'
        ))
