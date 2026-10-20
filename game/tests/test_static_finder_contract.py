"""Static serving must keep working when the upload finder has no match."""
import tempfile
from pathlib import Path

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.handlers.wsgi import WSGIHandler
from django.test import RequestFactory, SimpleTestCase

from game.creator_club_assets import ThreeDKitFinder


class StaticFinderContractTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.static_root = self.root / 'static'
        self.asset_root = self.root / 'uploads'
        self.fixtures = {
            'assets/clubs/logos/918_club.png': b'logo-918',
            'assets/clubs/logos/901_club.png': b'logo-901',
            'game/css/finder-contract.css': b'body { color: white; }',
            'game/js/finder-contract.js': b'console.log("static");',
        }
        for relative, content in self.fixtures.items():
            target = self.static_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for kind in ('home', 'away', 'third'):
            target = self.asset_root / '3dkits' / f'907_{kind}.png'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f'texture-{kind}'.encode())
        self.enterContext(self.settings(
            DEBUG=True,
            STATIC_URL='/static/',
            ASSETS_ROOT=str(self.asset_root),
            STATICFILES_DIRS=[str(self.static_root)],
        ))
        self.handler = StaticFilesHandler(WSGIHandler())
        self.factory = RequestFactory()

    def assert_served(self, path, content, content_type):
        response = self.handler.get_response(self.factory.get('/static/' + path))
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], content_type)
            self.assertEqual(b''.join(response.streaming_content), content)
        finally:
            response.close()

    def test_no_match_returns_empty_list_in_both_modes(self):
        finder = ThreeDKitFinder()
        for path in (
            'assets/clubs/logos/missing.png',
            'game/images/3dkits/999999_home.png',
            'game/images/3dkits/../secret.png',
            'game/images/3dkits/907_unknown.png',
        ):
            for find_all in (False, True):
                with self.subTest(path=path, find_all=find_all):
                    self.assertEqual(finder.find(path, find_all=find_all), [])

    def test_missing_files_are_not_found_not_server_errors(self):
        for path in (
            'assets/clubs/logos/missing.png',
            'game/css/missing.css',
            'game/js/missing.js',
            'game/images/3dkits/999999_home.png',
        ):
            with self.subTest(path=path):
                self.assertIsNone(finders.find(path))
                self.assertEqual(finders.find(path, find_all=True), [])
                response = self.handler.get_response(self.factory.get('/static/' + path))
                self.assertEqual(response.status_code, 404)
                response.close()

    def test_ordinary_assets_continue_to_later_finders(self):
        for path, content in self.fixtures.items():
            with self.subTest(path=path):
                expected = str(self.static_root / path)
                self.assertEqual(finders.find(path), expected)
                self.assertEqual(finders.find(path, find_all=True), [expected])
                content_type = (
                    'text/css' if path.endswith('.css')
                    else 'text/javascript' if path.endswith('.js')
                    else 'image/png'
                )
                self.assert_served(path, content, content_type)

    def test_app_directory_assets_still_resolve(self):
        for path in ('game/css/game-stage.css', 'game/js/club-profile.js'):
            with self.subTest(path=path):
                resolved = finders.find(path)
                self.assertIsInstance(resolved, str)
                self.assertTrue(Path(resolved).is_file())
                self.assert_served(
                    path, Path(resolved).read_bytes(),
                    'text/css' if path.endswith('.css') else 'text/javascript',
                )

    def test_all_texture_slots_resolve_without_collecting_uploads(self):
        finder = ThreeDKitFinder()
        for kind in ('home', 'away', 'third'):
            path = f'game/images/3dkits/907_{kind}.png'
            expected = str(self.asset_root / '3dkits' / f'907_{kind}.png')
            with self.subTest(kind=kind):
                self.assertEqual(finder.find(path), expected)
                self.assertEqual(finder.find(path, True), [expected])
                self.assertEqual(finders.find(path), expected)
                self.assertEqual(finders.find(path, find_all=True), [expected])
                self.assert_served(path, f'texture-{kind}'.encode(), 'image/png')
        self.assertEqual(list(finder.list([])), [])
