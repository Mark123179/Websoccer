"""Saisonende-Finanzjob manuell anstoßen (Spec Kap. 15).

TV-Saisonausschüttung, Pokalprämien-Backstop, Zieljäger-Boni,
Koeffizienten-Fortschreibung. Idempotent; Teil-Läufe erlaubt, solange
noch nicht alle Ligen durchgespielt sind.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from game.economy.integrity import check_finance_completeness
from game.economy.params import current_season
from game.economy.season_jobs import finance_season_close


class Command(BaseCommand):
    help = 'Finanz-Saisonabschluss: TV-Ausschüttung, Prämien, Koeffizienten (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--saison', default=None,
            help='Saison-String (Default: aktuelle Sim-Saison).',
        )
        parser.add_argument(
            '--force', action='store_true', default=False,
            help='Vollständigkeits-Check überspringen (nur im Notfall).',
        )

    def handle(self, *args, **options):
        saison = options['saison'] or current_season()

        if not options['force']:
            result = check_finance_completeness(saison=str(saison))
            gaps = result.get('gaps', [])
            if gaps:
                lines = [
                    f'Finanz-Vollständigkeits-Check fehlgeschlagen: '
                    f'{len(gaps)} Lücke(n) in Saison {saison}.',
                    '',
                ]
                for g in gaps:
                    missing_str = ', '.join(g['missing']) if g['missing'] else '—'
                    header_hint = ' [kein Header]' if g['no_header'] else ''
                    lines.append(
                        f"  Spieltag {g['spieltag']:>2}  {g['liga']}  "
                        f"{g['club']}{header_hint}  — fehlend: {missing_str}"
                    )
                lines.append('')
                lines.append('Abbruch. Verwende --force um den Check zu überspringen.')
                raise CommandError('\n'.join(lines))

            self.stdout.write(self.style.SUCCESS(
                f'Vollständigkeits-Check OK '
                f'({result["checked_clubs"]} (Spieltag, Verein)-Kombinationen geprüft).'
            ))

        report = finance_season_close(saison)

        if report.get('skipped'):
            self.stdout.write(self.style.WARNING(
                f'Saison {saison} ist bereits abgeschlossen — nichts zu tun.'))
            return

        self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        if report.get('hinweis'):
            self.stdout.write(self.style.WARNING(report['hinweis']))
        elif report['errors']:
            self.stdout.write(self.style.ERROR(
                f"Abgeschlossen mit {len(report['errors'])} Fehler(n)."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Finanz-Saisonabschluss {saison} abgeschlossen.'))
