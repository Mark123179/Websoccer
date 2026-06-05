from django.core.management.base import BaseCommand

from game.models import Club
from game.season_goals import current_season_number, evaluate_goal_for_club


class Command(BaseCommand):
    help = (
        'Wertet die Saisonziele zu Saisonende aus und schreibt bei Erfolg '
        'einen Hoeneß-Coin gut.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--club-id',
            type=int,
            default=None,
            help='Nur diesen Verein auswerten.',
        )
        parser.add_argument(
            '--season',
            type=int,
            default=None,
            help='Saisonnummer (Standard: aktuelle Saison).',
        )

    def handle(self, *args, **options):
        season = options['season'] or current_season_number()
        clubs = Club.objects.all()
        if options['club_id']:
            clubs = clubs.filter(id=options['club_id'])

        evaluated = 0
        met = 0
        for club in clubs:
            goal = evaluate_goal_for_club(club, season_number=season)
            if goal is None:
                continue
            evaluated += 1
            status = 'ERFÜLLT' if goal.achieved else 'verfehlt'
            if goal.achieved:
                met += 1
            self.stdout.write(
                f'  {club.name}: Endplatz {goal.final_rank} '
                f'(Ziel {goal.goal_tier_label}, max. {goal.required_max_rank}) → {status}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'Saison {season}: {evaluated} ausgewertet, {met} erfüllt '
            f'(je +1 Hoeneß-Coin).'
        ))
