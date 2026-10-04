from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from game.models import Club, ClubNewsItem, League
from game.news_image_cleanup import BucketNewsStore, LocalNewsStore, StoredImage, referenced_names
from game.news_image_storage import BACKUP_PREFIX, persist_news_images
from game.tests.test_news_card_security import raster_source


class NewsImageCleanupTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.root = Path(media.name)
        settings = override_settings(
            MEDIA_ROOT=media.name, USE_REPLIT_OBJECT_STORAGE=False,
            STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                      'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
        )
        settings.enable()
        self.addCleanup(settings.disable)
        league = League.objects.create(name='Cleanup League', country='Deutschland')
        self.club = Club.objects.create(
            name='Cleanup Club', founded_year=1900, budget=0, league=league,
        )
        # Simulate waiting eight days, without falsifying filesystem timestamps.
        self.later = timezone.now() + timedelta(days=8)

    def save(self, name, content=b'fixture'):
        return default_storage.save(name, ContentFile(content))

    def news(self, card=None, blocks=None, **kwargs):
        return ClubNewsItem.objects.create(
            club=self.club, title='Cleanup', card_data=card,
            blocks=blocks or [], **kwargs,
        )

    def backup(self, before=None, after=None, name=None):
        empty = {'card_data': None, 'blocks': []}
        data = {
            'version': 1, 'news_id': 999, 'club_id': self.club.pk,
            'before': before or empty, 'after': after or empty,
        }
        return self.save(name or BACKUP_PREFIX + 'nested/backup.json', json.dumps(data).encode())

    def run_cleanup(self, *args, age=True):
        out = StringIO()
        with patch('game.news_image_cleanup.timezone.now', return_value=(
            self.later if age else timezone.now()
        )):
            call_command('cleanup_news_images', *args, stdout=out)
        return out.getvalue()

    def apply(self, **kwargs):
        return self.run_cleanup('--apply', '--confirm-writers-stopped', **kwargs)

    def test_preview_then_apply_only_removes_old_unreferenced_news_images(self):
        orphan = self.save('news-images/nested/orphan.png')
        recent = self.save('news-images/recent.png')
        card = self.save('news-images/card.png')
        block = self.save('news-images/block.png')
        historical = self.save('news-images/historical.png')
        avatar = self.save('avatars/profile.png')
        other = self.save('news-images-extra/unrelated.png')
        backup = self.backup()
        item = self.news(
            card={'customSrc': '/media/' + card},
            blocks=[{'k': 'image', 'src': 'https://host/media/' + block + '?v=1#image'}],
            img_path='/media/' + historical,
        )
        real_metadata = LocalNewsStore.metadata

        def metadata(store, name):
            image = real_metadata(store, name)
            if name == recent:
                return StoredImage(name, self.later, image.revision)
            return image

        with patch.object(LocalNewsStore, 'metadata', metadata):
            preview = self.run_cleanup()
            self.assertIn('KANDIDAT local:' + orphan, preview)
            self.assertIn('1 Kandidat(en)', preview)
            self.assertIn('0 gelöscht', preview)
            self.assertTrue(default_storage.exists(orphan))
            applied = self.apply()
            self.assertIn('0 Kandidat(en)', self.apply())
        self.assertIn('1 gelöscht', applied)
        self.assertFalse(default_storage.exists(orphan))
        for name in (card, block, historical, recent, avatar, other, backup):
            self.assertTrue(default_storage.exists(name), name)
        item.refresh_from_db()
        self.assertEqual(item.card_data, {'customSrc': '/media/' + card})

    def test_minimum_retention_and_explicit_paused_writers_required(self):
        name = self.save('news-images/new.png')
        with self.assertRaises(CommandError):
            self.run_cleanup('--min-age-days', '6')
        with self.assertRaisesMessage(CommandError, 'pausieren'):
            self.run_cleanup('--apply')
        self.assertIn('0 Kandidat(en)', self.apply(age=False))
        self.assertIn('0 Kandidat(en)', self.run_cleanup('--min-age-days', '30'))
        self.assertTrue(default_storage.exists(name))

    def test_both_backup_states_protect_images_even_without_article(self):
        before = self.save('news-images/before.png')
        after = self.save('news-images/after.png')
        backup = self.backup(
            before={'card_data': {'customSrc': '/media/' + before}, 'blocks': []},
            after={'card_data': None, 'blocks': [{'k': 'image', 'src': '/media/' + after}]},
        )
        self.assertIn('0 Kandidat(en)', self.apply())
        self.assertTrue(default_storage.exists(before))
        self.assertTrue(default_storage.exists(after))
        self.assertTrue(default_storage.exists(backup))

    def test_thumbnail_only_legacy_article_reference_protects_old_image(self):
        from game.news_images import resolve_news_images
        name = self.save('news-images/legacy-thumbnail.png')
        item = self.news(thumbnail_static_path='/media/' + name)
        self.assertEqual(item.card_data, None)
        self.assertEqual(item.img_path, '')
        self.assertEqual(item.blocks, [])
        for url in ('/media/' + name, ' https://old-host/media/' + name + '?v=1#img '):
            with self.subTest(url=url):
                item.thumbnail_static_path = url
                item.save(update_fields=['thumbnail_static_path'])
                self.assertEqual(resolve_news_images([item], self.club)[item.pk], url.strip())
                preview = self.run_cleanup()
                self.assertNotIn('KANDIDAT local:' + name, preview)
                self.assertIn('0 Kandidat(en)', preview)
                self.assertIn('0 gelöscht', self.apply())
                self.assertTrue(default_storage.exists(name))
                item.refresh_from_db()
                self.assertEqual(item.thumbnail_static_path, url)

    def test_restored_migration_keeps_backup_after_images(self):
        source = raster_source()
        item = self.news(card={'customSrc': source})
        call_command('migrate_news_images', '--apply', stdout=StringIO())
        item.refresh_from_db()
        name = item.card_data['customSrc'].removeprefix('/media/')
        backup = next(self.root.glob(BACKUP_PREFIX + '*.json')).relative_to(self.root).as_posix()
        call_command('migrate_news_images', '--restore', backup, '--apply', stdout=StringIO())
        self.assertIn('0 Kandidat(en)', self.apply())
        self.assertTrue(default_storage.exists(name))
        item.refresh_from_db()
        self.assertEqual(item.card_data['customSrc'], source)

    def test_unreadable_or_unknown_backups_abort_before_any_deletion(self):
        image = self.save('news-images/orphan.png')
        name = BACKUP_PREFIX + 'broken.json'
        for content in (b'{broken', b'{"version":2}', b'[]',
                        b'{"version":1,"news_id":1,"club_id":1,"before":{},"after":{}}'):
            self.save(name, content)
            with self.assertRaises(CommandError):
                self.apply()
            self.assertTrue(default_storage.exists(image))
            default_storage.delete(name)

    def test_storage_listing_metadata_backup_and_database_errors_fail_closed(self):
        name = self.save('news-images/orphan.png')
        self.backup()
        targets = (
            'game.news_image_cleanup.LocalNewsStore.names',
            'game.news_image_cleanup.LocalNewsStore.metadata',
            'game.news_image_cleanup.LocalNewsStore.read_backup',
            'game.news_image_cleanup.ClubNewsItem.objects.values_list',
        )
        for target in targets:
            with self.subTest(target=target), patch(target, side_effect=OSError('private details')):
                with self.assertRaises(CommandError) as error:
                    self.apply()
                self.assertNotIn('private details', str(error.exception))
            self.assertTrue(default_storage.exists(name))

    def test_metadata_failure_on_second_image_prevents_first_deletion(self):
        names = [self.save('news-images/a.png'), self.save('news-images/b.png')]
        real = LocalNewsStore.metadata

        def metadata(store, name):
            if name == names[1]:
                raise OSError
            return real(store, name)

        with patch.object(LocalNewsStore, 'metadata', metadata):
            with self.assertRaises(CommandError):
                self.apply()
        self.assertTrue(all(default_storage.exists(name) for name in names))

    def test_reference_added_after_inventory_is_rechecked(self):
        name = self.save('news-images/orphan.png')
        from game.news_image_cleanup import protected_names
        calls = 0

        def references(stores):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.news(card={'customSrc': '/media/' + name})
            return protected_names(stores)

        with patch('game.news_image_cleanup.protected_names', side_effect=references):
            self.assertIn('neue Referenz', self.apply())
        self.assertTrue(default_storage.exists(name))

    def test_new_backup_and_replaced_image_are_rechecked(self):
        name = self.save('news-images/orphan.png')
        from game.news_image_cleanup import protected_names
        calls = 0

        def references(stores):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.backup(after={'card_data': {'customSrc': '/media/' + name}, 'blocks': []})
            return protected_names(stores)

        with patch('game.news_image_cleanup.protected_names', side_effect=references):
            self.apply()
        self.assertTrue(default_storage.exists(name))
        for backup in self.root.rglob('*.json'):
            backup.unlink()
        calls = 0

        def replace(stores):
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.root / name).write_bytes(b'replacement')
            return protected_names(stores)

        with patch('game.news_image_cleanup.protected_names', side_effect=replace):
            self.assertIn('Datei geändert', self.apply())
        self.assertEqual((self.root / name).read_bytes(), b'replacement')

    def test_symlinks_never_followed_and_delete_errors_reported(self):
        avatar = self.save('avatars/profile.png')
        (self.root / 'news-images').mkdir()
        link = self.root / 'news-images/link.png'
        link.symlink_to(self.root / avatar)
        with self.assertRaisesMessage(CommandError, 'Symbolischer Link'):
            self.apply()
        self.assertTrue(default_storage.exists(avatar))
        link.unlink()
        name = self.save('news-images/orphan.png')
        with patch.object(LocalNewsStore, 'delete_unchanged', side_effect=OSError):
            with self.assertRaises(CommandError):
                self.apply()
        self.assertTrue(default_storage.exists(name))

    def test_failed_second_upload_leaves_collectible_orphan(self):
        real_save = default_storage.save
        calls = 0

        def fail_second(name, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError
            return real_save(name, data)

        with patch('game.news_image_storage.default_storage.save', side_effect=fail_second):
            with self.assertRaises(OSError):
                persist_news_images(
                    {'customSrc': raster_source()},
                    [{'k': 'image', 'src': raster_source('JPEG')}],
                )
        self.assertEqual(len(list(self.root.glob('news-images/*'))), 1)
        self.assertIn('1 gelöscht', self.apply())

    def test_backup_failure_or_database_failure_has_correct_cleanup_protection(self):
        item = self.news(card={'customSrc': raster_source()})
        real_save = default_storage.save

        def fail_backup(name, data):
            if name.startswith(BACKUP_PREFIX):
                raise OSError
            return real_save(name, data)

        with patch('game.news_image_storage.default_storage.save', side_effect=fail_backup):
            with self.assertRaises(CommandError):
                call_command('migrate_news_images', '--apply', stdout=StringIO(), stderr=StringIO())
        self.assertIn('1 gelöscht', self.apply())
        # A successful backup followed by DB failure MUST retain its image.
        with patch.object(ClubNewsItem, 'save', side_effect=OSError):
            with self.assertRaises(CommandError):
                call_command('migrate_news_images', '--apply', stdout=StringIO(), stderr=StringIO())
        self.assertIn('0 Kandidat(en)', self.apply())
        self.assertEqual(len(list(self.root.glob('news-images/*'))), 1)
        item.refresh_from_db()
        self.assertTrue(item.card_data['customSrc'].startswith('data:'))

    def test_publication_database_failure_leaves_collectible_orphan(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(username='cleanup-publisher')
        self.club.managed_by = user.manager_profile
        self.club.save(update_fields=['managed_by'])
        self.client.force_login(user)
        self.client.raise_request_exception = False
        with patch('game.views.ClubNewsItem.objects.create', side_effect=OSError):
            response = self.client.post(
                reverse('club_news_publish', args=[self.club.pk]),
                json.dumps({'titel': 'Failure', 'card': {'customSrc': raster_source()}, 'blocks': []}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(ClubNewsItem.objects.exists())
        self.assertEqual(len(list(self.root.glob('news-images/*'))), 1)
        self.assertIn('1 gelöscht', self.apply())

    def test_bucket_and_local_backups_protect_both_locations(self):
        from django.core.files.storage import FileSystemStorage
        with TemporaryDirectory() as bucket_root:
            # Exercise the combined inventory without contacting a real bucket.
            bucket = LocalNewsStore(FileSystemStorage(location=bucket_root))
            bucket.label = 'bucket'
            names = ('news-images/a.png', 'news-images/b.png')
            for name in names:
                self.save(name)
                bucket.storage.save(name, ContentFile(b'image'))
            self.backup(after={'card_data': {'customSrc': '/media/' + names[0]}, 'blocks': []})
            bucket.storage.save(BACKUP_PREFIX + 'backup.json', ContentFile(json.dumps({
                'version': 1, 'news_id': 999, 'club_id': self.club.pk,
                'before': {'card_data': None, 'blocks': []},
                'after': {'card_data': None, 'blocks': [{'src': '/media/' + names[1]}]},
            }).encode()))
            with patch('game.news_image_cleanup.news_stores', return_value=[
                bucket, LocalNewsStore(default_storage),
            ]):
                self.assertIn('0 Kandidat(en)', self.apply())
            for name in names:
                self.assertTrue(default_storage.exists(name))
                self.assertTrue(bucket.storage.exists(name))


class NewsCleanupBucketTests(SimpleTestCase):
    def store(self):
        client = MagicMock()
        with patch('game.object_storage_backend.get_client', return_value=client):
            store = BucketNewsStore()
        return store, client._Client__bucket.return_value

    def test_bucket_age_generation_precondition_and_explicit_failure(self):
        store, bucket = self.store()
        now = timezone.now()
        blob = SimpleNamespace(updated=now, time_created=now - timedelta(days=1), generation='42')
        bucket.get_blob.return_value = blob
        image = store.metadata('news-images/a.png')
        self.assertEqual(image.revision, 42)
        self.assertTrue(store.delete_unchanged(image))
        bucket.blob.return_value.delete.assert_called_once_with(if_generation_match=42)
        bucket.blob.return_value.delete.side_effect = OSError
        with self.assertRaises(OSError):
            store.delete_unchanged(image)
        bucket.blob.return_value.delete.reset_mock()
        blob.generation = '43'
        self.assertFalse(store.delete_unchanged(image))
        bucket.blob.return_value.delete.assert_not_called()

    def test_missing_bucket_age_is_not_a_deletion_candidate(self):
        from game.news_image_cleanup import CleanupUnsafe
        store, bucket = self.store()
        bucket.get_blob.return_value = SimpleNamespace(updated=None, time_created=None, generation=1)
        with self.assertRaises(CleanupUnsafe):
            store.metadata('news-images/a.png')
        bucket.blob.return_value.delete.assert_not_called()

    def test_bucket_configuration_includes_local_fallback(self):
        from game.news_image_cleanup import news_stores
        with override_settings(STORAGES={
            'default': {'BACKEND': 'game.object_storage_backend.ReplitObjectStorage'},
        }), patch('game.news_image_cleanup.BucketNewsStore') as cloud:
            stores = news_stores()
        self.assertEqual(len(stores), 2)
        self.assertIs(stores[0], cloud.return_value)
        self.assertIsInstance(stores[1], LocalNewsStore)

    @override_settings(MEDIA_URL='/media/')
    def test_reference_url_normalization_and_recursive_legacy_fields(self):
        values = [
            '/media/news-images/a.png',
            'https://old-host/media/news-images/a.png?v=2#x',
            '/media/news-images/%61.png',
            'news-images/a.png',
            './media/news-images/a.png',
            {'legacy': [{'src': '/media/other/../news-images/a.png'}]},
            'https://example.org/external.png',
            '/media/avatars/a.png',
            'data:image/png;base64,AAAA',
        ]
        self.assertEqual(set(referenced_names(values)), {'news-images/a.png'})

    @override_settings(MEDIA_URL='https://cdn.example/uploads/')
    def test_custom_absolute_media_url(self):
        self.assertEqual(
            set(referenced_names('https://cdn.example/uploads/news-images/a.png')),
            {'news-images/a.png'},
        )