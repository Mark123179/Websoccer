from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.test import TestCase
from django.urls import reverse

from game.models import Notification


class NotificationsPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='notifications-owner')
        self.other = get_user_model().objects.create_user(username='notifications-other')
        self.manager = self.user.manager_profile
        self.client.force_login(self.user)
        self.url = reverse('notifications_page')

    def create_item(self, **kwargs):
        return Notification.objects.create(
            recipient=self.manager, title='Eigene Nachricht', **kwargs,
        )

    def test_unsafe_links_render_as_plain_notifications_without_changing_urls(self):
        urls = (
            'javascript:alert(1)',
            'data:text/html,<script>alert(1)</script>',
            'https://outside.example/test',
            '//outside.example/test',
            '',
        )
        for url in urls:
            with self.subTest(url=url):
                item = self.create_item(url=url, body='Sichtbarer Nachrichtentext')
                response = self.client.get(self.url)
                displayed = next(
                    n for n in response.context['notifications'] if n.pk == item.pk
                )
                self.assertEqual(displayed.safe_url, '')
                self.assertEqual(displayed.url, url)
                self.assertContains(response, '<div class="notif-item is-unread">', count=1)
                self.assertNotContains(response, '<a class="notif-item')
                self.assertContains(response, item.title)
                self.assertContains(response, item.body)
                item.refresh_from_db()
                self.assertEqual(item.url, url)
                self.assertTrue(item.is_read)

    def test_internal_links_remain_clickable_without_changing_urls(self):
        for url in ('/clubs/1/', 'https://testserver/clubs/1/', 'http://testserver/clubs/1/'):
            with self.subTest(url=url):
                item = self.create_item(url=url)
                response = self.client.get(self.url)
                displayed = next(
                    n for n in response.context['notifications'] if n.pk == item.pk
                )
                self.assertEqual(displayed.safe_url, url)
                self.assertContains(
                    response, f'<a class="notif-item is-unread" href="{url}">', count=1,
                )
                item.refresh_from_db()
                self.assertEqual(item.url, url)

    def test_https_page_rejects_same_host_http_link(self):
        insecure = self.create_item(url='http://testserver/clubs/1/')
        secure = self.create_item(url='https://testserver/clubs/1/')
        relative = self.create_item(url='/clubs/1/')

        response = self.client.get(self.url, secure=True)

        urls = {item.pk: item.safe_url for item in response.context['notifications']}
        self.assertEqual(urls, {insecure.pk: '', secure.pk: secure.url, relative.pk: relative.url})
        self.assertNotContains(response, 'href="http://testserver/clubs/1/"')
        self.assertContains(response, '<div class="notif-item is-unread">', count=1)
        self.assertContains(response, 'href="https://testserver/clubs/1/"')
        self.assertContains(response, 'href="/clubs/1/"')

    def test_only_loaded_hundred_notifications_are_read(self):
        for _ in range(105):
            self.create_item()
        expected_ids = set(
            Notification.objects.filter(recipient=self.manager)
            .values_list('pk', flat=True)[:100]
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        loaded = response.context['notifications']
        self.assertEqual(len(loaded), 100)
        self.assertEqual({item.pk for item in loaded}, expected_ids)
        self.assertTrue(all(not item.is_read for item in loaded))
        self.assertContains(response, 'notif-item is-unread', count=100)
        read_ids = set(
            Notification.objects.filter(recipient=self.manager, is_read=True)
            .values_list('pk', flat=True)
        )
        self.assertEqual(read_ids, expected_ids)
        self.assertEqual(
            Notification.objects.filter(recipient=self.manager, is_read=False).count(), 5,
        )

    def test_arrival_between_loading_and_update_stays_unread(self):
        displayed = self.create_item()
        arrivals = []
        original_update = QuerySet.update

        def update_with_arrival(queryset, **kwargs):
            if queryset.model is Notification and kwargs == {'is_read': True}:
                arrivals.append(self.create_item(body='Nach dem Laden eingetroffen'))
            return original_update(queryset, **kwargs)

        # Deterministically insert at the race boundary, before the real SQL update.
        with patch.object(QuerySet, 'update', new=update_with_arrival):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(arrivals), 1)
        self.assertEqual(
            [item.pk for item in response.context['notifications']], [displayed.pk],
        )
        self.assertNotContains(response, 'Nach dem Laden eingetroffen')
        displayed.refresh_from_db()
        arrivals[0].refresh_from_db()
        self.assertTrue(displayed.is_read)
        self.assertFalse(arrivals[0].is_read)

    def test_other_manager_notifications_are_neither_shown_nor_read(self):
        own = self.create_item()
        foreign = Notification.objects.create(
            recipient=self.other.manager_profile, title='Fremde private Nachricht',
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item.pk for item in response.context['notifications']], [own.pk],
        )
        self.assertContains(response, own.title)
        self.assertNotContains(response, foreign.title)
        own.refresh_from_db()
        foreign.refresh_from_db()
        self.assertTrue(own.is_read)
        self.assertFalse(foreign.is_read)

    def test_existing_read_state_and_initial_highlighting_are_preserved(self):
        read = self.create_item(is_read=True)
        unread = self.create_item()

        response = self.client.get(self.url)

        states = {item.pk: item.is_read for item in response.context['notifications']}
        self.assertEqual(states, {read.pk: True, unread.pk: False})
        self.assertContains(response, 'notif-item is-unread', count=1)
        read.refresh_from_db()
        unread.refresh_from_db()
        self.assertTrue(read.is_read)
        self.assertTrue(unread.is_read)
        again = self.client.get(self.url)
        self.assertNotContains(again, 'notif-item is-unread')

    def test_empty_page_leaves_foreign_notification_unread(self):
        foreign = Notification.objects.create(
            recipient=self.other.manager_profile, title='Privat',
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['notifications'], [])
        self.assertContains(response, 'Keine Benachrichtigungen.')
        foreign.refresh_from_db()
        self.assertFalse(foreign.is_read)