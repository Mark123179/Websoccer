"""Management Command: run_verbandsabgabe

Erhebt die Verbandsabgabe (Spec Kap. 12.5) für alle Vereine der laufenden
Saison. HART DEAKTIVIERT: Der Runner verweigert die Ausführung, solange
EconomyParameter VERBANDSABGABE.enabled nicht explizit True ist —
Aktivierung nur nach Balancing-Freigabe.

Verwendung:
    python manage.py run_verbandsabgabe --dry-run   # Vorschau (auch bei disabled)
    python manage.py run_verbandsabgabe             # bucht (nur bei enabled)
    python manage.py run_verbandsabgabe --season 1
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Erhebt die Verbandsabgabe (Spec Kap. 12.5) — verweigert hart bei disabled.'

    def add_arguments(self, parser):
        parser.add_argument('--season', type=str, default=None,
                            help='Sim-Saison (default: laufende Saison).')
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='Nur berechnen und anzeigen, nichts buchen.')

    def handle(self, *args, **options):
        from game.economy import verbandsabgabe
        from game.economy.params import current_season

        saison = options.get('season') or current_season()
        dry_run = options['dry_run']

        if not dry_run and not verbandsabgabe.is_enabled(saison):
            raise CommandError(
                'Die Verbandsabgabe ist DEAKTIVIERT (EconomyParameter '
                'VERBANDSABGABE.enabled=False). Keine Buchung ausgeführt. '
                'Vorschau mit --dry-run möglich; Aktivierung nur nach '
                'expliziter Balancing-Freigabe.'
            )

        if dry_run:
            # Vorschau rechnet auch bei disabled — ohne Buchung.
            from decimal import Decimal
            from game.models import Club
            cfg = verbandsabgabe._config(saison)
            faktor = cfg.get('faktor', 2.0)
            satz = cfg.get('satz', 0.10)
            rows = []
            for club in Club.objects.filter(budget__isnull=False).order_by('pk'):
                umsatz = verbandsabgabe.jahresumsatz(club, saison)
                abgabe = verbandsabgabe.berechne_abgabe(
                    club.budget, umsatz, faktor=faktor, satz=satz,
                )
                if abgabe > 0:
                    rows.append((club, umsatz, abgabe))
            status = 'AKTIV' if cfg.get('enabled') else 'DEAKTIVIERT'
            self.stdout.write(
                f'[dry-run] Verbandsabgabe ({status}), Saison {saison}, '
                f'faktor={faktor}, satz={satz}:'
            )
            if not rows:
                self.stdout.write('  Kein Verein über dem Freibetrag.')
                return
            total = Decimal('0.00')
            for club, umsatz, abgabe in rows:
                total += abgabe
                self.stdout.write(
                    f'  • {club.name}: Kontostand {club.budget:,.0f} €, '
                    f'Umsatz {umsatz:,.0f} € → Abgabe {abgabe:,.0f} €'
                )
            self.stdout.write(f'  Summe: {total:,.0f} € ({len(rows)} Verein(e))')
            return

        ergebnisse = verbandsabgabe.run_verbandsabgabe(saison)
        if not ergebnisse:
            self.stdout.write(self.style.WARNING(
                'Kein Verein über dem Freibetrag — nichts gebucht.'
            ))
            return
        total = sum(e['abgabe'] for e in ergebnisse)
        for e in ergebnisse:
            self.stdout.write(
                f'  • {e["club"].name}: Abgabe {e["abgabe"]:,.0f} € gebucht'
            )
        self.stdout.write(self.style.SUCCESS(
            f'Verbandsabgabe gebucht: {total:,.0f} € bei {len(ergebnisse)} Verein(en).'
        ))
