"""Vollständigkeitsprüfung für Finanz-Spieltagsläufe.

Prüft ob für jeden simulierten Spieltag alle 6 Typ-Marker
(TV_SOCKEL, SPONSOR, TICKET, GEHALT, STADION, BETRIEB) plus der
Haupt-Marker je Verein vorhanden sind. Fehlende Marker weisen auf
einen partiell fehlgeschlagenen Lauf hin — der Idempotenz-Guard kann
sie beim nächsten Aufruf von run_club_finance() schließen.

Exit-Code:
  0  Keine Lücken gefunden.
  1  Mindestens eine Lücke gefunden (Cronjob/CI kann alarmieren).
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Prüft Vollständigkeit der Finanz-Spieltagsläufe '
        '(Typ-Marker je Verein+Spieltag). Read-only, bucht nichts.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--saison', default=None,
            help='Saison-Filter (z.B. "0" oder "1"); ohne Angabe alle Saisons.',
        )
        parser.add_argument(
            '--liga', type=int, default=None, dest='liga_id',
            help='Liga-ID (Primärschlüssel); ohne Angabe alle Ligen.',
        )
        parser.add_argument(
            '--spieltag', type=int, default=None,
            help='Spieltag-Filter (1-basiert); ohne Angabe alle Spieltage.',
        )

    def handle(self, *args, **opts):
        from game.economy.integrity import check_finance_completeness

        result = check_finance_completeness(
            saison=opts['saison'],
            liga_id=opts['liga_id'],
            spieltag=opts['spieltag'],
        )

        gaps = result['gaps']
        checked = result['checked_clubs']

        if not gaps:
            self.stdout.write(self.style.SUCCESS(
                f'OK — {checked} (Spieltag, Verein)-Kombinationen geprüft, '
                f'keine Lücken gefunden.'
            ))
            return

        self.stderr.write(self.style.WARNING(
            f'[ALARM] {len(gaps)} Lücke(n) bei {checked} geprüften Kombinationen:'
        ))
        for g in gaps:
            missing_str = ', '.join(g['missing']) if g['missing'] else '—'
            header_flag = ' [KEIN HEADER]' if g['no_header'] else ''
            self.stderr.write(self.style.ERROR(
                f"  Liga {g['liga']} | Saison {g['saison']} | "
                f"ST{g['spieltag']} | {g['club']}{header_flag}: "
                f"fehlende Marker: {missing_str}"
            ))

        raise SystemExit(1)
