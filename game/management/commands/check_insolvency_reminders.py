"""Management Command: check_insolvency_reminders

Prüft täglich, ob offene Zahlungsunfähigkeits-Vermerke kurz vor Fristablauf
stehen (≤ ERINNERUNG_TAGE echte Tage), und sendet genau einmal eine
Erinnerungs-ClubNews. Die Idempotenz-Garantie liegt im Feld
InsolvencyCase.reminder_sent; ein bereits versendeter Hinweis wird nicht
doppelt erzeugt.

Verwendung:
    python manage.py check_insolvency_reminders
    python manage.py check_insolvency_reminders --date 2026-07-21
    python manage.py check_insolvency_reminders --dry-run
"""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Sendet Erinnerungs-News für Vermerke kurz vor Fristablauf.'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None,
                            help='Stichtag YYYY-MM-DD (default: heute).')
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='Nur anzeigen, ohne News zu schreiben.')

    def handle(self, *args, **options):
        import datetime as dt

        from django.utils import timezone

        from game.economy.insolvency import ERINNERUNG_TAGE
        from game.models import ClubNewsItem, InsolvencyCase

        ref = options.get('date')
        if ref:
            try:
                today = datetime.strptime(ref, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Ungültiges Datum. Bitte Format YYYY-MM-DD verwenden.')
        else:
            today = timezone.localdate()

        # Fenster: [Tagesbeginn heute, Tagesbeginn in ERINNERUNG_TAGE+1 Tagen)
        # → nur Vermerke, die noch NICHT abgelaufen sind, aber höchstens
        #   ERINNERUNG_TAGE Tage Restfrist haben.
        window_start = timezone.make_aware(
            dt.datetime.combine(today, dt.time.min)
        )
        window_end = timezone.make_aware(
            dt.datetime.combine(today + dt.timedelta(days=ERINNERUNG_TAGE + 1),
                                dt.time.min)
        )

        faelle = (
            InsolvencyCase.objects
            .filter(
                status__in=[InsolvencyCase.STATUS_OPEN, InsolvencyCase.STATUS_ENFORCED],
                deadline_at__gte=window_start,
                deadline_at__lt=window_end,
                reminder_sent=False,
            )
            .select_related('club')
            .order_by('deadline_at')
        )

        if not faelle.exists():
            self.stdout.write(self.style.WARNING(
                f'Keine Vermerke mit ausstehender Erinnerung (Stichtag {today}).'
            ))
            return

        count = 0
        for case in faelle:
            local_deadline = timezone.localtime(case.deadline_at)
            frist_str = local_deadline.strftime('%-d. %B %Y')
            verbleibend = (local_deadline.date() - today).days

            if verbleibend == 0:
                tage_label = 'heute'
            elif verbleibend == 1:
                tage_label = 'morgen'
            else:
                tage_label = f'in {verbleibend} Tagen'

            titel = (
                f'Erinnerung: Zahlungsunfähigkeits-Frist läuft {tage_label} ab '
                f'({frist_str})'
            )[:160]

            subtitle = (
                f'Der offene Sportgericht-Vermerk für deinen Verein läuft am '
                f'{frist_str} ab. Bringe den Kontostand bis dahin auf ≥ 0 €, '
                f'um das Verfahren zu schließen — sonst kann der Admin eine '
                f'Zwangsversteigerung einleiten.'
            )

            self.stdout.write(
                f'  • {case.club.name}: Frist {frist_str} ({tage_label})'
                + (' [dry-run]' if options['dry_run'] else '')
            )

            if not options['dry_run']:
                ClubNewsItem.objects.create(
                    club_id=case.club_id,
                    title=titel,
                    subtitle=subtitle,
                    category='Sportgericht',
                    outlet='Sportgericht',
                    published_at=today,
                    is_new=True,
                )
                case.reminder_sent = True
                case.save(update_fields=['reminder_sent'])
                count += 1

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'[dry-run] {faelle.count()} Vermerk(e) würden erinnert.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Erinnerung(en) versendet: {count}.'
            ))
