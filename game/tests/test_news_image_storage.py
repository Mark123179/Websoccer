import base64
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from game.models import Club, ClubNewsItem, League
from game.news_image_storage import BACKUP_PREFIX, persist_news_images
from game.news_images import news_article_dicts, resolve_news_images
from game.tests.test_news_card_security import raster_source


class NewsImageStorageTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(
            MEDIA_ROOT=self.media.name, USE_REPLIT_OBJECT_STORAGE=False,
            STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                      'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
        )
        settings.enable()
        self.addCleanup(settings.disable)
        user = get_user_model().objects.create_user(username='news-storage')
        league = League.objects.create(name='Storage League', country='Deutschland')
        self.club = Club.objects.create(
            name='Storage Club', founded_year=1900, budget=0, league=league,
            managed_by=user.manager_profile,
        )
        self.client.force_login(user)
        self.source = raster_source()
        self.card = {'motiv': 'eigenes', 'customSrc': self.source}
        self.blocks = [
            {'k': 'text', 'text': 'Keep unchanged'},
            {'k': 'image', 'src': self.source, 'cap': 'Original caption'},
        ]

    def legacy(self):
        return ClubNewsItem.objects.create(
            club=self.club, title='Historical', card_data=self.card, blocks=self.blocks
        )

    def command(self, *args):
        out = StringIO()
        call_command('migrate_news_images', *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def backup_name(self):
        return next(Path(self.media.name).glob(f'{BACKUP_PREFIX}*.json')).relative_to(
            self.media.name
        ).as_posix()

    def test_publication_stores_card_and_blocks_as_urls_and_deduplicates(self):
        body = {'titel': 'With images', 'card': self.card, 'blocks': self.blocks}
        response = self.client.post(reverse('club_news_publish', args=[self.club.pk]),
                                    json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        article = response.json()['article']
        item = ClubNewsItem.objects.get(pk=article['pk'])
        url = item.card_data['customSrc']
        self.assertTrue(url.startswith('/media/news-images/'))
        self.assertEqual(item.blocks[1]['src'], url)
        self.assertEqual(item.blocks[1]['cap'], 'Original caption')
        self.assertEqual(item.blocks[0], self.blocks[0])
        self.assertNotIn('data:image', json.dumps(article))
        self.assertEqual(len(list(Path(self.media.name).glob('news-images/*'))), 1)
        image = self.client.get(url)
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.content, base64.b64decode(self.source.split(',')[1]))
        page = self.client.get(reverse('club_news', args=[self.club.pk]))
        self.assertEqual(page.context['vn_data']['art'][0]['card']['customSrc'], url)

    def test_storage_failure_never_publishes_or_falls_back(self):
        with patch('game.news_image_storage.default_storage.save', side_effect=OSError('offline')):
            response = self.client.post(
                reverse('club_news_publish', args=[self.club.pk]),
                json.dumps({'titel': 'Failure', 'card': self.card, 'blocks': self.blocks}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['ok'])
        self.assertFalse(ClubNewsItem.objects.exists())
        self.assertFalse(list(Path(self.media.name).glob('news-images/*')))

    def test_legacy_full_page_has_small_urls_but_database_and_compact_resolver_unchanged(self):
        items = [self.legacy() for _ in range(15)]
        with patch('game.news_image_storage.default_storage.save') as save:
            page = self.client.get(reverse('club_news', args=[self.club.pk]))
        save.assert_not_called()
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(self.source.encode(), page.content)
        for item in items:
            item.refresh_from_db()
            self.assertEqual(item.card_data, self.card)
            self.assertEqual(item.blocks, self.blocks)
        self.assertEqual(resolve_news_images(items, self.club)[items[0].pk], self.source)
        self.assertEqual(news_article_dicts(items, self.club)[0]['card']['customSrc'], self.source)
        article = page.context['vn_data']['art'][0]
        for url in (article['card']['customSrc'], article['blocks'][1]['src']):
            self.client.logout()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, base64.b64decode(self.source.split(',')[1]))
            self.assertEqual(response['Content-Type'], 'image/png')
            self.assertEqual(self.client.get(url, HTTP_IF_NONE_MATCH=response['ETag']).status_code, 304)
            self.assertEqual(self.client.get(url[:-2] + 'x/').status_code, 404)

    def test_legacy_over_new_size_limit_remains_available(self):
        # Existing display has no new-publication size gate.
        raw = b'x' * (1024 * 1024 + 1)
        source = 'data:image/png;base64,' + base64.b64encode(raw).decode()
        item = self.legacy()
        item.card_data['customSrc'] = source
        item.save(update_fields=['card_data'])
        article = news_article_dicts([item], self.club, externalize_legacy=True)[0]
        response = self.client.get(article['card']['customSrc'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, raw)

    def test_dry_run_apply_backup_idempotence_and_restore(self):
        item = self.legacy()
        self.assertIn('migrierbar', self.command('--news-id', str(item.pk)))
        self.assertFalse(list(Path(self.media.name).rglob('*')))
        item.refresh_from_db()
        self.assertEqual(item.card_data, self.card)
        self.command('--news-id', str(item.pk), '--apply')
        item.refresh_from_db()
        migrated = item.card_data.copy()
        self.assertTrue(migrated['customSrc'].startswith('/media/news-images/'))
        backup = self.backup_name()
        with default_storage.open(backup) as saved:
            original = json.load(saved)
        self.assertEqual(original['before']['card_data'], self.card)
        self.assertEqual(self.client.get('/media/' + backup).status_code, 404)
        self.assertIn('0 Beitrag', self.command('--apply'))
        self.command('--restore', backup)
        item.refresh_from_db()
        self.assertEqual(item.card_data, migrated)
        self.command('--restore', backup, '--apply')
        item.refresh_from_db()
        self.assertEqual(item.card_data, self.card)
        self.assertEqual(item.blocks, self.blocks)
        self.assertEqual(item.title, 'Historical')
        self.assertTrue(default_storage.exists(backup))
        self.assertIn('bereits vorhanden', self.command('--restore', backup, '--apply'))

    def test_migration_storage_failure_or_invalid_legacy_keeps_original(self):
        item = self.legacy()
        with patch('game.news_image_storage.default_storage.save', side_effect=OSError):
            with self.assertRaises(CommandError):
                self.command('--apply')
        item.refresh_from_db()
        self.assertEqual(item.card_data, self.card)
        with patch('game.news_image_storage.default_storage.open', side_effect=OSError):
            with self.assertRaises(CommandError):
                self.command('--apply')
        item.refresh_from_db()
        self.assertEqual(item.card_data, self.card)
        item.card_data['customSrc'] = 'data:image/svg+xml;base64,PHN2Zy8+'
        item.save(update_fields=['card_data'])
        with self.assertRaises(CommandError):
            self.command('--apply')
        item.refresh_from_db()
        self.assertEqual(item.card_data['customSrc'], 'data:image/svg+xml;base64,PHN2Zy8+')

    def test_failed_backup_does_not_change_row_and_restore_refuses_concurrent_edit(self):
        item = self.legacy()
        real_save = default_storage.save

        def fail_backup(name, data):
            if name.startswith(BACKUP_PREFIX):
                raise OSError('backup offline')
            return real_save(name, data)

        with patch('game.management.commands.migrate_news_images.default_storage.save',
                   side_effect=fail_backup):
            with self.assertRaises(CommandError):
                self.command('--apply')
        item.refresh_from_db()
        self.assertEqual(item.card_data, self.card)
        self.command('--apply')
        backup = self.backup_name()
        item.blocks = [{'k': 'text', 'text': 'New edit'}]
        item.save(update_fields=['blocks'])
        with self.assertRaisesMessage(CommandError, 'seit der Migration geändert'):
            self.command('--restore', backup, '--apply')
        item.refresh_from_db()
        self.assertEqual(item.blocks, [{'k': 'text', 'text': 'New edit'}])

    def test_external_urls_are_never_fetched_or_uploaded(self):
        with patch('game.news_image_storage.default_storage.save') as save:
            card, blocks = persist_news_images(
                {'motiv': 'eigenes', 'customSrc': 'https://example.org/a.png'},
                [{'k': 'image', 'src': '/media/existing.png'}],
            )
        save.assert_not_called()
        self.assertEqual(card['customSrc'], 'https://example.org/a.png')
        self.assertEqual(blocks[0]['src'], '/media/existing.png')