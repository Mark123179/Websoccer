from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from game.models import (
    Club,
    DataSource,
    Player,
    PlayerAwardTitle,
    PlayerInjuryRecord,
    PlayerMarketValueSnapshot,
    PlayerSeasonStat,
    PlayerSuspensionRecord,
    PlayerTransferHistory,
)

KANE_ID = 1519
BAYERN_ID = 2
BVB_ID = 3


class Command(BaseCommand):
    help = 'Seed Harry Kane profile data (bio, stats, history, awards).'

    def handle(self, *args, **options):
        try:
            kane = Player.objects.get(id=KANE_ID)
        except Player.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Player id={KANE_ID} not found.'))
            return

        self._seed_base(kane)
        self._seed_market_value(kane)
        self._seed_season_stats(kane)
        self._seed_transfers(kane)
        self._seed_injuries(kane)
        self._seed_suspensions(kane)
        self._seed_awards(kane)
        self.stdout.write(self.style.SUCCESS('Kane profile seeded successfully.'))

    def _seed_base(self, kane):
        kane.height_cm = 188
        kane.strong_foot = 'right'
        kane.shirt_number = 9
        kane.main_position_1 = 'ST'
        kane.secondary_position_1 = 'OM'
        kane.real_life_club_id = BAYERN_ID
        kane.save(update_fields=[
            'height_cm', 'strong_foot', 'shirt_number',
            'main_position_1', 'secondary_position_1', 'real_life_club',
        ])
        self.stdout.write('Base fields updated.')

    def _seed_market_value(self, kane):
        PlayerMarketValueSnapshot.objects.filter(player=kane).delete()
        try:
            tm = DataSource.objects.get(id=1)
        except DataSource.DoesNotExist:
            tm = DataSource.objects.first()
            if not tm:
                self.stdout.write(self.style.WARNING('No DataSource found, skipping MW snapshots.'))
                return

        snapshots = [
            (date(2021, 12, 1), Decimal('75000000')),
            (date(2022, 6, 1),  Decimal('90000000')),
            (date(2022, 12, 1), Decimal('100000000')),
            (date(2023, 6, 1),  Decimal('110000000')),
            (date(2023, 12, 1), Decimal('100000000')),
            (date(2024, 3, 1),  Decimal('95000000')),
            (date(2024, 6, 1),  Decimal('90000000')),
            (date(2024, 12, 1), Decimal('80000000')),
            (date(2025, 6, 1),  Decimal('72000000')),
            (date(2025, 12, 1), Decimal('65000000')),
        ]
        for recorded_at, value in snapshots:
            PlayerMarketValueSnapshot.objects.create(
                player=kane,
                source=tm,
                recorded_at=recorded_at,
                value_eur=value,
            )
        self.stdout.write(f'{len(snapshots)} MW snapshots created.')

    def _seed_season_stats(self, kane):
        PlayerSeasonStat.objects.filter(player=kane).delete()
        rows = [
            {
                'competition': '1. Bundesliga',
                'matches': 24, 'goals': 21, 'assists': 7,
                'minutes_played': 2130, 'yellow_cards': 2, 'red_cards': 0,
                'substitutions_in': 1, 'substitutions_out': 4,
                'player_of_match_awards': 8, 'average_grade': Decimal('1.72'),
            },
            {
                'competition': 'Champions League',
                'matches': 8, 'goals': 7, 'assists': 2,
                'minutes_played': 720, 'yellow_cards': 1, 'red_cards': 0,
                'substitutions_in': 0, 'substitutions_out': 2,
                'player_of_match_awards': 3, 'average_grade': Decimal('1.88'),
            },
            {
                'competition': 'DFB-Pokal',
                'matches': 4, 'goals': 5, 'assists': 1,
                'minutes_played': 360, 'yellow_cards': 0, 'red_cards': 0,
                'substitutions_in': 1, 'substitutions_out': 1,
                'player_of_match_awards': 1, 'average_grade': Decimal('1.56'),
            },
            {
                'competition': 'Supercup',
                'matches': 1, 'goals': 1, 'assists': 0,
                'minutes_played': 90, 'yellow_cards': 0, 'red_cards': 0,
                'substitutions_in': 0, 'substitutions_out': 0,
                'player_of_match_awards': 0, 'average_grade': Decimal('2.10'),
            },
            {
                'competition': 'Europa League',
                'matches': 6, 'goals': 4, 'assists': 3,
                'minutes_played': 540, 'yellow_cards': 0, 'red_cards': 0,
                'substitutions_in': 0, 'substitutions_out': 1,
                'player_of_match_awards': 1, 'average_grade': Decimal('1.82'),
            },
            {
                'competition': 'Nationalmannschaft',
                'matches': 5, 'goals': 3, 'assists': 2,
                'minutes_played': 410, 'yellow_cards': 1, 'red_cards': 0,
                'substitutions_in': 0, 'substitutions_out': 3,
                'player_of_match_awards': 2, 'average_grade': Decimal('1.94'),
            },
        ]
        for row in rows:
            PlayerSeasonStat.objects.create(
                player=kane,
                season='2026/27',
                season_number=1,
                **row,
            )
        self.stdout.write(f'{len(rows)} season stat rows created.')

    def _seed_transfers(self, kane):
        PlayerTransferHistory.objects.filter(player=kane).delete()
        try:
            bvb = Club.objects.get(id=BVB_ID)
            fcb = Club.objects.get(id=BAYERN_ID)
        except Club.DoesNotExist:
            self.stdout.write(self.style.WARNING('Clubs not found for transfers, skipping.'))
            return

        leverkusen = Club.objects.filter(name__icontains='Leverkusen').first()
        stuttgart = Club.objects.filter(name__icontains='Stuttgart').first()
        frankfurt = Club.objects.filter(name__icontains='Frankfurt').first()

        transfers = [
            {
                'transfer_date': date(2023, 8, 12),
                'season': '2023/24',
                'from_club': None,
                'to_club': fcb,
                'fee_eur': Decimal('100000000'),
                'notes': 'Wechsel von Tottenham Hotspur zu FC Bayern München',
            },
            {
                'transfer_date': date(2022, 8, 1),
                'season': '2022/23',
                'from_club': bvb,
                'to_club': None,
                'fee_eur': Decimal('0'),
                'notes': 'Leihende',
            },
            {
                'transfer_date': date(2022, 1, 31),
                'season': '2021/22',
                'from_club': None,
                'to_club': bvb,
                'fee_eur': Decimal('0'),
                'notes': 'Leihe',
            },
            {
                'transfer_date': date(2025, 7, 1),
                'season': '2025/26',
                'from_club': fcb,
                'to_club': fcb,
                'fee_eur': Decimal('0'),
                'notes': 'Vertragsverlängerung',
            },
            {
                'transfer_date': date(2024, 1, 10),
                'season': '2023/24',
                'from_club': leverkusen or bvb,
                'to_club': fcb,
                'fee_eur': Decimal('15000000'),
                'notes': 'Wintertransfer',
            },
        ]
        for t in transfers:
            PlayerTransferHistory.objects.create(player=kane, **t)
        self.stdout.write(f'{len(transfers)} transfer rows created.')

    def _seed_injuries(self, kane):
        PlayerInjuryRecord.objects.filter(player=kane).delete()
        injuries = [
            {'start_date': date(2026, 10, 18), 'end_date': date(2026, 10, 27), 'injury_type': 'Oberschenkelverhärtung', 'days_missed': 9},
            {'start_date': date(2026, 4, 3),  'end_date': date(2026, 4, 10),  'injury_type': 'Sprunggelenksverletzung', 'days_missed': 7},
            {'start_date': date(2025, 12, 6), 'end_date': date(2025, 12, 13), 'injury_type': 'Rückenprobleme',          'days_missed': 7},
            {'start_date': date(2025, 9, 21), 'end_date': date(2025, 9, 29),  'injury_type': 'Muskelverhärtung',        'days_missed': 8},
            {'start_date': date(2025, 3, 12), 'end_date': date(2025, 3, 16),  'injury_type': 'Prellung',                'days_missed': 4},
        ]
        for inj in injuries:
            PlayerInjuryRecord.objects.create(player=kane, **inj)
        self.stdout.write(f'{len(injuries)} injury records created.')

    def _seed_suspensions(self, kane):
        PlayerSuspensionRecord.objects.filter(player=kane).delete()
        suspensions = [
            {'start_date': date(2026, 11, 9),  'end_date': date(2026, 11, 16), 'reason': 'Gelbsperre',       'matches_missed': 1},
            {'start_date': date(2026, 5, 4),   'end_date': date(2026, 5, 11),  'reason': 'Unsportlichkeit',  'matches_missed': 1},
            {'start_date': date(2025, 10, 19), 'end_date': date(2025, 10, 26), 'reason': 'Gelbsperre',       'matches_missed': 1},
            {'start_date': date(2025, 4, 2),   'end_date': date(2025, 4, 9),   'reason': 'Gelbsperre',       'matches_missed': 1},
            {'start_date': date(2024, 12, 14), 'end_date': date(2024, 12, 21), 'reason': 'Gelbsperre',       'matches_missed': 1},
        ]
        for sus in suspensions:
            PlayerSuspensionRecord.objects.create(player=kane, **sus)
        self.stdout.write(f'{len(suspensions)} suspension records created.')

    def _seed_awards(self, kane):
        PlayerAwardTitle.objects.filter(player=kane).delete()
        awards = [
            {'title': 'Supercup',                  'competition': 'Supercup',          'trophy_asset_id': '1301397', 'count': 1, 'awarded_at': date(2023, 8, 12)},
            {'title': 'Champions League',           'competition': 'Champions League',  'trophy_asset_id': '1301394', 'count': 3, 'awarded_at': date(2025, 6, 1)},
            {'title': 'DFB-Pokal',                  'competition': 'DFB-Pokal',         'trophy_asset_id': '1301410', 'count': 1, 'awarded_at': date(2025, 5, 24)},
            {'title': '1. Bundesliga Meisterschaft','competition': '1. Bundesliga',     'trophy_asset_id': '22',      'count': 1, 'awarded_at': date(2025, 5, 17)},
        ]
        for aw in awards:
            PlayerAwardTitle.objects.create(player=kane, season='2026/27', **aw)
        self.stdout.write(f'{len(awards)} award titles created.')
