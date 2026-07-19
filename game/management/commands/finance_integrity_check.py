"""Ledger-Integritätscheck: Summe FinanceTransaction vs. Club.budget.

Täglicher Lauf (Celery Beat) bzw. manuell. Abweichung → Exit-Code 1
(Admin-Alarm). Mit --fix wird der Konto-Cache aus dem Ledger repariert.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Prüft je Verein: Ledger-Summe == Konto-Cache (Club.budget).'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true',
                            help='Konto-Cache aus dem Ledger neu setzen.')

    def handle(self, *args, **opts):
        from game.economy.integrity import check_ledger_integrity

        result = check_ledger_integrity(fix=opts['fix'])

        if not result['mismatches']:
            self.stdout.write(self.style.SUCCESS(
                f"OK — {result['checked']} Vereine geprüft, keine Abweichungen."
            ))
            return

        for m in result['mismatches']:
            self.stderr.write(self.style.ERROR(
                f"  {m['club']} (#{m['club_id']}): Konto {m['budget']:,.2f} € "
                f"vs. Ledger {m['ledger']:,.2f} € (Diff {m['diff']:+,.2f} €)"
            ))
        if opts['fix']:
            self.stdout.write(f"{result['fixed']} Konto-Caches repariert.")
            return

        raise CommandError(
            f"{len(result['mismatches'])} von {result['checked']} Vereinen weichen ab."
        )
