from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from game.models import (
    Club,
    DataSource,
    League,
    Player,
    PlayerCMTAttributeProfile,
    PlayerCMTProfile,
    PlayerExternalId,
)


def _league():
    return League.objects.create(name='Audit Liga', country='Deutschland')


def _club(league, name, fm_inside_id=None):
    return Club.objects.create(
        name=name,
        short_name=name[:20],
        founded_year=1900,
        budget=1_000_000,
        fan_popularity=50,
        league=league,
        fm_inside_id=fm_inside_id,
    )


def _player(first_name, last_name, club=None, **kwargs):
    defaults = {
        'age': 24,
        'position': 'ZM',
        'primary_position': 'ZM',
        'main_position_1': 'ZM',
        'potential': 70,
        'salary_per_match': 1000,
        'club': club,
    }
    defaults.update(kwargs)
    return Player.objects.create(
        first_name=first_name,
        last_name=last_name,
        **defaults,
    )


class AuditPlayerDataCompletenessCommandTest(TestCase):
    def test_command_outputs_global_and_club_completeness_counts(self):
        league = _league()
        club = _club(league, 'FC Audit', fm_inside_id=900)
        career_end = _club(league, 'Karrierende')
        cmt_source = DataSource.objects.get_or_create(
            code=DataSource.CODE_CMTRACKER,
            defaults={'name': 'CMTracker'},
        )[0]

        complete = _player(
            'Ada',
            'Complete',
            club=club,
            wsc_player_id='CMT100',
            fm_inside_id=100,
            transfermarkt_id=200,
            nationalities='Deutschland',
        )
        missing = _player('Ben', 'Missing', club=club)
        free_agent = _player('Cara', 'Free', club=None, loan_status='none')
        _player('Rita', 'Retired', club=career_end)

        PlayerCMTProfile.objects.create(
            player=complete,
            db_slug='26062400',
            cmt_player_id='100',
            player_image_url='https://example.test/player.png',
            player_image_cached_path='game/static/game/images/player_composites/missing.png',
        )
        PlayerCMTAttributeProfile.objects.create(
            player=complete,
            db_slug='26062400',
        )
        PlayerExternalId.objects.create(
            player=complete,
            source=cmt_source,
            external_id='100',
        )

        counts_before = {
            'players': Player.objects.count(),
            'profiles': PlayerCMTProfile.objects.count(),
            'attributes': PlayerCMTAttributeProfile.objects.count(),
            'external_ids': PlayerExternalId.objects.count(),
        }

        out = StringIO()
        call_command('audit_player_data_completeness', stdout=out)
        output = out.getvalue()

        self.assertIn('total players: 4', output)
        self.assertIn('active players ohne Karrierende: 3', output)
        self.assertIn('CMT profiles: 1', output)
        self.assertIn('CMT attributes: 1', output)
        self.assertIn('auto-created CMT players: 1', output)
        self.assertIn('free agents: 1', output)
        self.assertIn('nationalities filled: 1', output)
        self.assertIn('CMT image_url filled: 1', output)
        self.assertIn('CMT cached images: 0', output)
        self.assertIn('FC Audit | 2 | 1 | 1 | 1 | 1 | 1 | 2', output)
        self.assertNotIn('Karrierende |', output)

        counts_after = {
            'players': Player.objects.count(),
            'profiles': PlayerCMTProfile.objects.count(),
            'attributes': PlayerCMTAttributeProfile.objects.count(),
            'external_ids': PlayerExternalId.objects.count(),
        }
        self.assertEqual(counts_after, counts_before)
