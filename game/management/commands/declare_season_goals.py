from django.core.management.base import BaseCommand

from game.models import Club
from game.season_goals import current_season_number, declare_goal_for_club


class Command(BaseCommand):
    help = (
        'Verkündet die Saisonziele des Präsidenten für alle Vereine '
        '(oder einen einzelnen Verein) anhand der Kaderstärke.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--club-id',
            type=int,
            default=None,
            help='Nur für diesen Verein verkünden.',
        )
        parser.add_argument(
            '--season',
            type=int,
            default=None,
            help='Saisonnummer (Standard: aktuelle Saison).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Bestehende Ziele neu berechnen (setzt Auswertung zurück).',
        )

    def handle(self, *args, **options):
        season = options['season'] or current_season_number()
        clubs = Club.objects.all()
        if options['club_id']:
            clubs = clubs.filter(id=options['club_id'])

        count = 0
        for club in clubs:
            goal = declare_goal_for_club(
                club, season_number=season, force=options['force']
            )
            count += 1
            self.stdout.write(
                f'  {club.name}: Rang {goal.rank_in_league}/{goal.league_size} '
                f'→ {goal.goal_tier_label} (max. Platz {goal.required_max_rank})'
            )

        self.stdout.write(self.style.SUCCESS(
            f'Saison {season}: {count} Saisonziel(e) verkündet.'
        ))
