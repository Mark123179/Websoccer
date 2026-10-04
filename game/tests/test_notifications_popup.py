import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from game.models import Notification


class NotificationsPopupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='popup-owner', password='test-only')
        self.other = get_user_model().objects.create_user(username='popup-other', password='test-only')
        self.manager = self.user.manager_profile
        self.client.force_login(self.user)
        self.url = reverse('notifications_open')

    def create_item(self, **kwargs):
        return Notification.objects.create(recipient=self.manager, title='Nachricht', **kwargs)

    def test_empty_popup_and_private_no_store(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'items': [], 'unread_count': 0})
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_only_latest_ten_owned_items_are_read(self):
        items = [self.create_item() for _ in range(12)]
        other_item = Notification.objects.create(recipient=self.other.manager_profile, title='Privat')
        data = self.client.post(self.url).json()
        self.assertEqual([item['id'] for item in data['items']], [item.pk for item in reversed(items[2:])])
        self.assertTrue(all(item['is_new'] for item in data['items']))
        self.assertEqual(data['unread_count'], 2)
        self.assertEqual(Notification.objects.filter(recipient=self.manager, is_read=True).count(), 10)
        other_item.refresh_from_db()
        self.assertFalse(other_item.is_read)
        again = self.client.post(self.url).json()
        self.assertFalse(any(item['is_new'] for item in again['items']))
        self.assertEqual(again['unread_count'], 2)

    def test_latest_order_is_stable_when_timestamps_are_equal(self):
        first, second = self.create_item(), self.create_item()
        Notification.objects.filter(recipient=self.manager).update(created_at=first.created_at)
        items = self.client.post(self.url).json()['items']
        self.assertEqual([item['id'] for item in items], [second.pk, first.pk])

    def test_text_is_preserved_and_unsafe_links_are_removed(self):
        for url in (
            'javascript:alert(1)', 'data:text/html,test',
            '//outside.example/test', 'https://outside.example/test',
        ):
            with self.subTest(url=url):
                item = self.create_item(body='<img src=x onerror=alert(1)>', url=url)
                data = self.client.post(self.url).json()['items'][0]
                self.assertEqual(data['id'], item.pk)
                self.assertEqual(data['url'], '')
                self.assertEqual(data['body'], '<img src=x onerror=alert(1)>')
                item.refresh_from_db()
                self.assertEqual(item.url, url)
        self.create_item(url='/clubs/1/')
        self.assertEqual(self.client.post(self.url).json()['items'][0]['url'], '/clubs/1/')

    def test_https_popup_rejects_same_host_http_link(self):
        item = self.create_item(url='http://testserver/clubs/1/')
        response = self.client.post(self.url, secure=True)
        self.assertEqual(response.json()['items'][0]['url'], '')
        item.refresh_from_db()
        self.assertEqual(item.url, 'http://testserver/clubs/1/')
        self.create_item(url='https://testserver/clubs/1/')
        response = self.client.post(self.url, secure=True)
        self.assertEqual(response.json()['items'][0]['url'], 'https://testserver/clubs/1/')

    def test_get_does_not_mark_anything_read_and_login_is_required(self):
        item = self.create_item()
        self.assertEqual(self.client.get(self.url).status_code, 405)
        item.refresh_from_db()
        self.assertFalse(item.is_read)
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        item.refresh_from_db()
        self.assertFalse(item.is_read)

    def test_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        item = self.create_item()
        self.assertEqual(client.post(self.url).status_code, 403)
        item.refresh_from_db()
        self.assertFalse(item.is_read)

    def test_session_csrf_from_rendered_bell_allows_opening(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        html = client.get(reverse('notifications_page')).content.decode()
        token = re.search(r'data-csrf="([^"]+)"', html).group(1)
        item = self.create_item()
        response = client.post(self.url, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['unread_count'], 0)
        item.refresh_from_db()
        self.assertTrue(item.is_read)