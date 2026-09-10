from django.db import IntegrityError, transaction
from django.test import TestCase

from game.match_readiness import ensure_default_tactic
from game.models import Club, League, TacticSetup


class TacticSetupContextTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Kontext-Testliga')
        self.club = Club.objects.create(
            name='Kontext-Testclub',
            short_name='KTC',
            league=self.league,
            founded_year=2000,
            budget=0,
        )

    def test_existing_default_path_creates_pflicht_context(self):
        setup, _changed = ensure_default_tactic(self.club)

        self.assertEqual(setup.context, TacticSetup.CONTEXT_PFLICHT)

    def test_same_club_and_scope_can_have_both_contexts(self):
        pflicht = TacticSetup.objects.create(
            club=self.club,
            squad_scope='pro',
            context=TacticSetup.CONTEXT_PFLICHT,
        )
        freundschaft = TacticSetup.objects.create(
            club=self.club,
            squad_scope='pro',
            context=TacticSetup.CONTEXT_FREUNDSCHAFT,
        )

        self.assertNotEqual(pflicht.pk, freundschaft.pk)

    def test_context_combination_remains_unique(self):
        TacticSetup.objects.create(
            club=self.club,
            squad_scope='pro',
            context=TacticSetup.CONTEXT_PFLICHT,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            TacticSetup.objects.create(
                club=self.club,
                squad_scope='pro',
                context=TacticSetup.CONTEXT_PFLICHT,
            )