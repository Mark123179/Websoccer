from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class StadiumStudyTests(TestCase):
    def test_admin_only_read_only_study_and_source_disclosures(self):
        user = get_user_model().objects.create_user("study-admin", is_superuser=True, is_staff=True)
        url = reverse("stadium_study")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="study-dortmund"')
        self.assertContains(response, 'id="study-elversberg"')
        self.assertContains(response, "keine Matchsimulation")
        self.assertContains(response, 'id="study-floodlight"')
        scene = response.context["study_config"]["elversberg"]
        self.assertEqual(scene["pitch"], {"length": 105.0, "width": 68.0})
        self.assertEqual(scene["steckbrief"].get("floodlights"), None)
        self.assertEqual(scene["surroundings"], {})
        self.assertEqual(self.client.session.get("live_story_test"), None)

    def test_staff_cannot_use_study(self):
        user = get_user_model().objects.create_user("study-staff", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("stadium_study")).status_code, 403)
