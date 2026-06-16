"""
game/tests/test_gk_red_off_ordering.py

Regression test: bei TW-Rot (gk_red) erscheint im kombinierten Ticker
die Karte VOR dem Einwechslungs-Event und das gk_red_off-Event
NACH beiden (Karte → Sub → gk_red_off), auch bei identischer Minute.
"""

from django.test import TestCase

from game.views import _build_combined_events


class GkRedOffOrderingTest(TestCase):
    """Stellt sicher, dass intra-minute Priorität korrekt ist."""

    def _make_data(self, minute: int = 55):
        return {
            'home_club_name': 'Heimclub',
            'away_club_name': 'Gastclub',
            'home_goals': 1,
            'away_goals': 0,
            'goal_events': [
                {
                    'team': 'home',
                    'minute': 20,
                    'scorer_name': 'Torschütze',
                    'scorer_pos': 'ST',
                    'assister_name': '',
                    'assister_pos': '',
                }
            ],
            'card_events': [
                {
                    'player_id': 99,
                    'player_name': 'Keeper Karl',
                    'club_side': 'away',
                    'minute': minute,
                    'card_type': 'red',
                }
            ],
            'injury_events': [],
        }

    def _make_home_subs(self, minute: int = 55):
        return [
            {
                'minute': minute,
                'in_id': 10,
                'out_id': 20,
                'in_name': 'Ersatz-TW',
                'out_name': 'Feldspieler Franz',
                'target_slot': 'TW',
                'position_relation': 'exact',
                'condition': 'gk_red',
            }
        ]

    def test_card_before_sub_before_gk_red_off_same_minute(self):
        """card < sub < gk_red_off bei identischer Minute."""
        minute = 55
        events = _build_combined_events(
            self._make_data(minute),
            self._make_home_subs(minute),
            [],
        )

        real_events = [e for e in events if e['type'] in ('card', 'sub', 'gk_red_off')]

        types = [e['type'] for e in real_events if e.get('minute') == minute]

        self.assertIn('card', types, "Karten-Event fehlt bei Minute %d" % minute)
        self.assertIn('sub', types, "Sub-Event fehlt bei Minute %d" % minute)
        self.assertIn('gk_red_off', types, "gk_red_off-Event fehlt bei Minute %d" % minute)

        card_idx = types.index('card')
        sub_idx  = types.index('sub')
        gko_idx  = types.index('gk_red_off')

        self.assertLess(card_idx, sub_idx,
            "Karte muss vor dem Wechsel erscheinen (got: %s)" % types)
        self.assertLess(sub_idx, gko_idx,
            "Wechsel muss vor gk_red_off erscheinen (got: %s)" % types)

    def test_gk_red_off_commentary_not_empty(self):
        """gk_red_off-Event enthält Spielernamen und ist nicht leer."""
        minute = 71
        events = _build_combined_events(
            self._make_data(minute),
            self._make_home_subs(minute),
            [],
        )
        gko_events = [e for e in events if e['type'] == 'gk_red_off']
        self.assertEqual(len(gko_events), 1, "Genau ein gk_red_off-Event erwartet")
        commentary = gko_events[0].get('commentary', '')
        self.assertIn('Feldspieler Franz', commentary,
            "Spielername muss im Kommentar vorkommen: %r" % commentary)
        self.assertGreater(len(commentary), 20, "Kommentar zu kurz: %r" % commentary)

    def test_no_gk_red_off_for_normal_sub(self):
        """Bei normalem Wechsel (kein gk_red) wird kein gk_red_off erzeugt."""
        data = self._make_data(minute=55)
        data['card_events'] = []
        normal_subs = [
            {
                'minute': 60,
                'in_id': 11,
                'out_id': 21,
                'in_name': 'Einwechselspieler',
                'out_name': 'Auswechselspieler',
                'target_slot': 'LA',
                'position_relation': 'HP',
                'condition': 'fuehrung',
            }
        ]
        events = _build_combined_events(data, normal_subs, [])
        gko_events = [e for e in events if e['type'] == 'gk_red_off']
        self.assertEqual(len(gko_events), 0,
            "Kein gk_red_off bei normalem Wechsel erwartet")
