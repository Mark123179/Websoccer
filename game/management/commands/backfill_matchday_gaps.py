"""backfill_matchday_gaps — Fehlende Buchungstypen für einen Spieltag nachbuchen.

Hintergrund: Spieltag 6 (Liga 2, Saison 0) wurde als erster Spieltag mit dem
Live-Hook simuliert, aber mit einer älteren Version von run_matchday_finance().
Ergebnis: der FinanceMatchdayRun-Marker ist für alle 18 Clubs gesetzt, aber
SPONSOR_FIX, STADION_UNTERHALT und STADION_SPIELTAG fehlen.

Sicher: Marker löschen und komplett wiederholen würde GEHALT, TV_SOCKEL, TICKET
und BETRIEB doppelt buchen. Dieses Command bucht stattdessen nur die tatsächlich
fehlenden Typen nach (prüft vorher per Query).

Idempotenz: Wiederholter Aufruf erzeugt keine Doppelbuchungen — vorhandene Typen
werden übersprungen.
"""
from django.core.management.base import BaseCommand, CommandError

from game.economy.booking import book
from game.economy.sponsors import get_active_offer, sponsor_fix_rate
from game.economy.stadium import spieltagskosten, unterhalt_rate


NACHBUCHBARE_TYPEN = ('SPONSOR_FIX', 'STADION_UNTERHALT', 'STADION_SPIELTAG')


class Command(BaseCommand):
    help = (
        'Fehlende Buchungstypen für einen Spieltag gezielt nachbuchen '
        '(ohne FinanceMatchdayRun-Marker zu löschen).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--liga', type=int, default=2,
            help='Liga-ID (Default: 2 = 1. Bundesliga)',
        )
        parser.add_argument(
            '--saison', default='0',
            help='Saison-String (Default: 0)',
        )
        parser.add_argument(
            '--spieltag', type=int, default=6,
            help='Spieltag-Nummer (Default: 6)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur ausgeben, was gebucht würde — keine DB-Änderungen.',
        )

    def handle(self, *args, **options):
        from game.models import Club, FinanceTransaction, League, MatchdayRevenue, SeasonFixture

        liga_id = options['liga']
        saison = str(options['saison'])
        spieltag = options['spieltag']
        dry_run = options['dry_run']

        try:
            league = League.objects.get(pk=liga_id)
        except League.DoesNotExist:
            raise CommandError(f'Liga {liga_id} nicht gefunden.')

        fixtures = list(
            SeasonFixture.objects
            .filter(league_id=liga_id, season=saison, matchday=spieltag)
            .select_related('home_club', 'away_club')
        )
        if not fixtures:
            raise CommandError(
                f'Keine Fixtures für Liga {liga_id}, Saison {saison}, Spieltag {spieltag}.'
            )

        self.stdout.write(
            f'=== Backfill: Liga {league.name}, Saison {saison}, Spieltag {spieltag} '
            f'{"[DRY-RUN] " if dry_run else ""}==='
        )

        # Clubs und Heimstatus aufbauen
        clubs_is_home: dict = {}
        for f in fixtures:
            clubs_is_home[f.home_club] = True
            clubs_is_home[f.away_club] = False

        club_ids = [c.pk for c in clubs_is_home]

        # Welche Typen existieren bereits je Club?
        existing: dict[int, set] = {}
        for tx in FinanceTransaction.objects.filter(
            saison=saison, spieltag=spieltag, club_id__in=club_ids,
        ).values('club_id', 'typ'):
            existing.setdefault(tx['club_id'], set()).add(tx['typ'])

        # Zuschauerzahlen aus MatchdayRevenue (via TICKET-Buchung) rekonstruieren
        zuschauer_map: dict[int, int] = {}
        for tx in FinanceTransaction.objects.filter(
            saison=saison, spieltag=spieltag,
            typ='TICKET', referenz_typ='matchday_revenue',
            club_id__in=club_ids,
        ):
            if tx.referenz_id:
                try:
                    rev = MatchdayRevenue.objects.get(pk=tx.referenz_id)
                    zuschauer_map[tx.club_id] = rev.attendance
                except MatchdayRevenue.DoesNotExist:
                    pass

        total_gebucht = 0
        total_uebersprungen = 0
        errors = []

        for club, is_home in sorted(clubs_is_home.items(), key=lambda x: x[0].pk):
            present = existing.get(club.pk, set())
            fehlend = [t for t in NACHBUCHBARE_TYPEN if t not in present]

            # STADION_SPIELTAG nur für Heimvereine relevant
            if not is_home and 'STADION_SPIELTAG' in fehlend:
                fehlend.remove('STADION_SPIELTAG')

            if not fehlend:
                self.stdout.write(f'  {club.name}: vollständig — übersprungen.')
                total_uebersprungen += 1
                continue

            self.stdout.write(
                f'  {club.name}: fehlt {", ".join(fehlend)}'
                f'{" (Heimspiel)" if is_home else ""}'
            )

            try:
                gebucht = self._backfill_club(
                    club, league, saison, spieltag, fehlend,
                    zuschauer_map=zuschauer_map,
                    dry_run=dry_run,
                )
                total_gebucht += len(gebucht)
                for line in gebucht:
                    self.stdout.write(f'    {"[DRY-RUN] " if dry_run else ""}✓ {line}')
            except Exception as exc:
                errors.append(f'{club.name}: {exc}')
                self.stderr.write(f'    ✗ FEHLER: {exc}')

        self.stdout.write(
            f'\nErgebnis: {total_gebucht} Buchungen{"(simuliert)" if dry_run else ""}, '
            f'{total_uebersprungen} Vereine übersprungen, {len(errors)} Fehler.'
        )
        if errors:
            raise CommandError(f'Backfill mit {len(errors)} Fehler(n) abgeschlossen.')

    def _backfill_club(
        self, club, league, saison, spieltag, fehlend,
        zuschauer_map, dry_run,
    ) -> list[str]:
        """Bucht die fehlenden Typen für einen Verein nach. Gibt Beschreibungen zurück."""
        gebucht = []

        if 'SPONSOR_FIX' in fehlend:
            offer = get_active_offer(club, saison, autopick=True)
            if offer is None:
                gebucht.append('SPONSOR_FIX: kein Angebot — übersprungen.')
            else:
                rate = sponsor_fix_rate(offer, saison)
                if rate <= 0:
                    gebucht.append('SPONSOR_FIX: Rate 0 — übersprungen.')
                else:
                    beschreibung = f'{offer.sponsor_name}: Fixrate Spieltag {spieltag}'
                    if not dry_run:
                        book(
                            club, 'SPONSOR_FIX', rate,
                            beschreibung=beschreibung,
                            saison=saison, spieltag=spieltag,
                            referenz_typ='matchday', referenz_id=offer.pk,
                            pflicht=True,
                        )
                    gebucht.append(f'SPONSOR_FIX {rate:,.2f} € ({beschreibung})')

        if 'STADION_UNTERHALT' in fehlend:
            try:
                stadium = club.stadium
            except Exception:
                gebucht.append('STADION_UNTERHALT: kein Stadion — übersprungen.')
                stadium = None

            if stadium is not None:
                rate = unterhalt_rate(stadium, saison)
                if rate <= 0:
                    gebucht.append('STADION_UNTERHALT: Rate 0 — übersprungen.')
                else:
                    beschreibung = (
                        f'Stadion-Unterhalt Spieltag {spieltag} '
                        f'({stadium.capacity_total:,} Plätze)'
                    )
                    if not dry_run:
                        book(
                            club, 'STADION_UNTERHALT', -rate,
                            beschreibung=beschreibung,
                            saison=saison, spieltag=spieltag,
                            referenz_typ='matchday', pflicht=True,
                        )
                    gebucht.append(f'STADION_UNTERHALT -{rate:,.2f} € ({beschreibung})')

        if 'STADION_SPIELTAG' in fehlend:
            zuschauer = zuschauer_map.get(club.pk, 0)
            if not zuschauer:
                gebucht.append('STADION_SPIELTAG: keine Zuschauerzahl — übersprungen.')
            else:
                kosten = spieltagskosten(zuschauer, saison)
                if kosten <= 0:
                    gebucht.append('STADION_SPIELTAG: Kosten 0 — übersprungen.')
                else:
                    beschreibung = (
                        f'Spieltagskosten Spieltag {spieltag} '
                        f'({zuschauer:,} Zuschauer)'
                    )
                    if not dry_run:
                        book(
                            club, 'STADION_SPIELTAG', -kosten,
                            beschreibung=beschreibung,
                            saison=saison, spieltag=spieltag,
                            referenz_typ='matchday', pflicht=True,
                        )
                    gebucht.append(f'STADION_SPIELTAG -{kosten:,.2f} € ({beschreibung})')

        return gebucht
