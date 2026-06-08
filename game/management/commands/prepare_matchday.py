"""Management Command: prepare_matchday

Prüft alle Vereine eines Spieltags und füllt fehlende Aufstellungen auf.
Managerlose Vereine erhalten die Standardaufstellung ohne Strafpunkt.
Gemanagte Vereine ohne Aufstellung: Auto-Aufstellung + Sportgericht-Eintrag + Stärkemalus.

Verwendung:
    python manage.py prepare_matchday --league <league_id> --matchday <n> --season <season>
    python manage.py prepare_matchday --league <league_id> --matchday <n> --season <season> --dry-run
"""

from django.core.management.base import BaseCommand, CommandError

from game.match_readiness import prepare_matchday_lineups
from game.models import League


class Command(BaseCommand):
    help = 'Füllt fehlende Aufstellungen für einen Spieltag auf (managerlose + säumige Manager).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--league',
            type=int,
            required=True,
            help='Datenbank-ID der Liga',
        )
        parser.add_argument(
            '--matchday',
            type=int,
            required=True,
            help='Spieltag-Nummer',
        )
        parser.add_argument(
            '--season',
            type=str,
            required=True,
            help='Saison-Bezeichnung (z. B. "2024")',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Nur analysieren, nichts speichern',
        )

    def handle(self, *args, **options):
        league_id = options['league']
        matchday = options['matchday']
        season = options['season']
        dry_run = options['dry_run']

        try:
            league = League.objects.get(pk=league_id)
        except League.DoesNotExist:
            raise CommandError(f'Liga mit ID {league_id} nicht gefunden.')

        self.stdout.write(
            f'Liga: {league} | Spieltag {matchday} | Saison {season}'
            + (' [DRY RUN]' if dry_run else '')
        )

        if dry_run:
            from game.models import SeasonFixture, TacticSetup
            from game.match_readiness import has_valid_lineup

            fixtures = SeasonFixture.objects.filter(
                league=league, matchday=matchday, season=season, is_played=False
            ).select_related('home_club__managed_by', 'away_club__managed_by')

            clubs_needing_lineup = []
            for fixture in fixtures:
                for side, club in (('Heim', fixture.home_club), ('Auswärts', fixture.away_club)):
                    try:
                        setup = TacticSetup.objects.get(club=club, squad_scope='pro')
                        valid = has_valid_lineup(setup)
                    except TacticSetup.DoesNotExist:
                        valid = False
                    if not valid:
                        clubs_needing_lineup.append((side, club, club.managed_by))

            if not clubs_needing_lineup:
                self.stdout.write(self.style.SUCCESS('Alle Aufstellungen gesetzt — nichts zu tun.'))
                return

            self.stdout.write(f'\nVereine ohne gültige Aufstellung ({len(clubs_needing_lineup)}):')
            for side, club, manager in clubs_needing_lineup:
                penalty = ' → Strafpunkt + Malus' if manager else ' → Auto (kein Manager)'
                self.stdout.write(f'  [{side}] {club}{penalty}')
            return

        stats = prepare_matchday_lineups(league, matchday, season)

        self.stdout.write('')
        self.stdout.write(f'  Fixtures geprüft : {stats["total"]}')
        self.stdout.write(f'  Aufstellungen     : {stats["filled"]} befüllt/repariert')
        self.stdout.write(f'  Strafpunkte       : {stats["penalized"]} Manager')
        self.stdout.write(f'  Übersprungen      : {stats["skipped"]} (<11 Spieler im Kader)')

        if stats['penalized']:
            self.stdout.write(self.style.WARNING(
                f'\n{stats["penalized"]} Manager wurden ins Sportgericht eingetragen '
                f'und spielen mit -20 % Stärkemalusfür Spieltag {matchday}.'
            ))

        self.stdout.write(self.style.SUCCESS('\nFertig.'))
