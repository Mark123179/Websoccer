from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from stadium_editor import allianz_pilot as pilot


@override_settings(ALLOWED_HOSTS=["testserver"])
class AllianzPilotTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, path, *, staff=False, anonymous=False, method="get"):
        request = getattr(self.factory, method)(path)
        request.user = AnonymousUser() if anonymous else SimpleNamespace(
            is_authenticated=True, is_staff=staff,
        )
        return request

    def test_both_endpoints_require_login_and_staff(self):
        for name, view in [("allianz_pilot", pilot.allianz_pilot),
                           ("allianz_pilot_scene", pilot.allianz_pilot_scene)]:
            path = reverse(name)
            self.assertEqual(view(self.request(path, anonymous=True)).status_code, 302)
            self.assertEqual(view(self.request(path)).status_code, 403)
            self.assertEqual(view(self.request(path, staff=True, method="post")).status_code, 405)

    def test_page_exposes_real_scene_endpoint(self):
        with patch.object(pilot, "render") as render:
            pilot.allianz_pilot(self.request(reverse("allianz_pilot"), staff=True))
        self.assertEqual(render.call_args.args[2]["pilot_scene_url"],
                         reverse("allianz_pilot_scene"))

    def test_scene_response_is_private_and_not_cacheable(self):
        with patch.object(pilot, "pilot_scene", return_value={
            "presentation": {"clubFmiId": 915},
        }):
            response = pilot.allianz_pilot_scene(self.request(
                reverse("allianz_pilot_scene"), staff=True,
            ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_existing_visual_state_is_read_without_replacement(self):
        expected = {"presentation": {"clubFmiId": 915}}
        with patch.object(pilot, "Stadium") as stadium, \
                patch.object(pilot, "StadiumGeometry") as geometry, \
                patch.object(pilot, "current_live_scene", return_value=expected) as live, \
                patch.object(pilot, "load_blueprints") as blueprints:
            geometry.objects.filter.return_value.exists.return_value = True
            result = pilot.pilot_scene()
        self.assertIs(result, expected)
        live.assert_called_once_with(stadium.objects.select_related.return_value.get.return_value)
        blueprints.assert_not_called()
        geometry.objects.create.assert_not_called()

    def test_missing_visual_row_uses_reference_without_seeding(self):
        original = {"meta": {"club": "FC Bayern München"}, "blocks": []}
        with patch.object(pilot, "Stadium") as stadium, \
                patch.object(pilot, "StadiumGeometry") as geometry, \
                patch.object(pilot, "model_manifest", return_value={"clubFmiId": 915}), \
                patch.object(pilot, "load_blueprints", return_value={"fcbayernmnchen": original}), \
                patch.object(pilot, "unity_presentation", return_value={"clubFmiId": 915}) as build:
            geometry.objects.filter.return_value.exists.return_value = False
            result = pilot.pilot_scene()
        self.assertEqual(result["geometryOrigin"], "bundled-reference-read-only")
        self.assertIsNot(build.call_args.args[1], original)
        self.assertEqual(build.call_args.args[1], original)
        self.assertEqual(build.call_args.args[2], {})
        self.assertEqual(build.call_args.args[0],
                         stadium.objects.select_related.return_value.get.return_value)
        geometry.objects.create.assert_not_called()
        geometry.objects.get_or_create.assert_not_called()
