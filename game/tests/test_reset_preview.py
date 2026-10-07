from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from game import models as m
from game.club_import.reset_preview import build_preview, render_sql


@override_settings(IMPORT_PACKAGE_MODE=False)
class ResetPreviewTests(TransactionTestCase):
    # Same seed-preserving lifecycle as the existing concurrency tests.
    # Otherwise an isolated --keepdb run empties migration-seeded catalogs.
    serialized_rollback = True

    def _fixture_teardown(self):
        super()._fixture_teardown()
        serialized = getattr(connection, "_test_serialized_contents", None)
        if serialized:
            connection.creation.deserialize_db_from_string(serialized)

    def test_preview_is_read_only_and_does_not_reset_profile_or_delete_club(self):
        user = get_user_model().objects.create_user("preview-only-user")
        profile = user.manager_profile
        profile.xp = 123
        profile.save(update_fields=["xp"])
        league = m.League.objects.create(name="Preview-only league", country="Test")
        club = m.Club.objects.create(name="Preview-only club", league=league, budget=123, founded_year=1900)
        with CaptureQueriesContext(connection) as captured:
            plan = build_preview(connection)
        statements = [q["sql"].lstrip().upper() for q in captured.captured_queries]
        self.assertFalse(any(s.startswith(("DELETE ", "UPDATE ", "INSERT ", "TRUNCATE ", "DROP "))
                             for s in statements))
        profile.refresh_from_db()
        self.assertEqual(profile.xp, 123)
        self.assertTrue(m.Club.objects.filter(pk=club.pk).exists())
        actions = {r["table"]: r["action"] for r in plan["tables"]}
        self.assertEqual(actions["auth_user"], "keep")
        self.assertEqual(actions["django_migrations"], "keep")
        self.assertEqual(actions["game_club"], "delete")
        self.assertEqual(actions["game_managerprofile"], "profile_reset")
        self.assertEqual(actions["game_landkoeffizient"], "season_zero_only")
        self.assertEqual(plan["profile_reset"]["level"], "1")
        self.assertEqual(plan["profile_reset"]["xp_max"], "800")
        if plan["sql_ready"]:
            with CaptureQueriesContext(connection) as generated:
                sql = render_sql(plan, connection.ops.quote_name)
            self.assertEqual(len(generated), 0)
            self.assertIn("Vorschau veraltet", sql)
            self.assertIn("Schutz verletzt", sql)
            self.assertNotIn("TRUNCATE", sql)
            self.assertNotIn(" CASCADE", sql)
            self.assertIn("COMMIT;", sql)
            self.assertNotIn('DELETE FROM "auth_user"', sql)
            self.assertNotIn('DELETE FROM "game_managerprofile"', sql)

    def test_pilot_and_package_mode_refused(self):
        with override_settings(SETTINGS_MODULE="import_pilot.settings"):
            with self.assertRaisesMessage(CommandError, "Pilot"):
                build_preview(connection)
        with override_settings(IMPORT_PACKAGE_MODE=True):
            with self.assertRaisesMessage(CommandError, "Altmodus"):
                build_preview(connection)

    def test_no_apply_option_and_blocked_plan_has_no_sql(self):
        with self.assertRaises(TypeError):
            call_command("preview_club_reset", execute=True, stdout=StringIO())
        with self.assertRaises(CommandError):
            render_sql({"sql_ready": False}, connection.ops.quote_name)
        for name in ("public", "production", "pilot", "import_restore_check_;DROP"):
            with self.subTest(name=name), self.assertRaises(CommandError):
                call_command("preview_club_reset", restore_check_name=name, stdout=StringIO())
