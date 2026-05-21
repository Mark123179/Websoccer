from django.core.management.base import BaseCommand

from game.models import Club, Player

_POSITION_ORDER = [
    'TW',
    'RV', 'ROV', 'IV', 'LI', 'LV', 'LOV',
    'DM', 'ZM', 'RM', 'LM', 'LOM', 'ROM', 'OM',
    'LF', 'RF', 'ST',
]

_POSITION_POOL = {
    'TW':  [1, 12, 22],
    'RV':  [2, 24],
    'ROV': [2, 24],
    'LV':  [3, 25],
    'LOV': [3, 25],
    'IV':  [4, 5, 15, 23],
    'LI':  [4, 5, 15, 23],
    'DM':  [6, 16],
    'ZM':  [8, 18],
    'RM':  [7, 17],
    'LM':  [11, 21],
    'ROM': [7, 17],
    'LOM': [11, 21],
    'OM':  [10, 20],
    'LF':  [11, 21],
    'RF':  [7, 17],
    'ST':  [9, 19],
}


def _player_position(player):
    return (
        player.position
        or player.primary_position
        or player.main_position_1
        or ''
    )


def _position_sort_key(player):
    pos = _player_position(player)
    try:
        return _POSITION_ORDER.index(pos)
    except ValueError:
        return len(_POSITION_ORDER)


def _assign_numbers_for_club(club, overwrite, verbosity):
    players = list(
        Player.objects.filter(club=club).order_by('id')
    )
    if not players:
        return 0

    if not overwrite:
        players = [p for p in players if p.shirt_number is None]
    if not players:
        return 0

    players.sort(key=_position_sort_key)

    used = set()
    if not overwrite:
        used = set(
            Player.objects.filter(club=club)
            .exclude(shirt_number=None)
            .values_list('shirt_number', flat=True)
        )

    def _next_free(candidates):
        for n in candidates:
            if n not in used:
                return n
        n = 13
        while n in used:
            n += 1
        return n

    pos_cursor = {}
    updated = []

    for player in players:
        pos = _player_position(player)
        pool = _POSITION_POOL.get(pos, [])
        cursor = pos_cursor.get(pos, 0)
        remaining = pool[cursor:]
        number = _next_free(remaining if remaining else [])
        pos_cursor[pos] = cursor + 1
        player.shirt_number = number
        used.add(number)
        updated.append(player)
        if verbosity >= 2:
            print(f'  {player.full_name} ({pos or "?"}) → #{number}')

    Player.objects.bulk_update(updated, ['shirt_number'])
    return len(updated)


class Command(BaseCommand):
    help = (
        'Assign shirt numbers to squad players for every club. '
        'Players who already have a number are skipped unless --overwrite is given.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--club-id',
            type=int,
            default=None,
            help='Only process this club ID.',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            default=False,
            help='Re-assign numbers even for players who already have one.',
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']
        club_id = options['club_id']
        verbosity = options['verbosity']

        qs = Club.objects.order_by('name')
        if club_id:
            qs = qs.filter(id=club_id)

        total = 0
        for club in qs:
            count = _assign_numbers_for_club(club, overwrite, verbosity)
            if count:
                total += count
                if verbosity >= 1:
                    self.stdout.write(
                        f'{club.name}: {count} Spieler mit Trikotnummer versehen.'
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Fertig. {total} Spieler insgesamt aktualisiert.'
            )
        )
