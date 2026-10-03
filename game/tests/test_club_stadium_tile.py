from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class ClubStadiumTileTests(SimpleTestCase):
    def tile(self, club_id):
        return render_to_string(
            'game/club_profile/cards/stadium_model_card.html',
            {'club': SimpleNamespace(pk=club_id)},
        )

    def test_dortmund_keeps_tile_position_but_replaces_partner_with_model(self):
        html = self.tile(3)
        self.assertIn('partner-profile-card stadium-model-card', html)
        self.assertIn('3D-Stadion', html)
        self.assertIn('data-club-stadium-stage', html)
        self.assertIn('data-club-stadium-status', html)
        self.assertNotIn('PARTNERVEREIN', html)
        self.assertNotIn('<button', html)
        self.assertNotIn('<iframe', html)
        # The renderer replaces host children; status must remain a sibling.
        self.assertIn('data-club-stadium-stage></div>', html)

    def test_other_clubs_do_not_show_the_dortmund_stadium(self):
        html = self.tile(4)
        self.assertIn('Noch kein 3D-Modell verfügbar.', html)
        self.assertNotIn('data-club-stadium-stage', html)
        self.assertNotIn('PARTNERVEREIN', html)