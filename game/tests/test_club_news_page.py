import os
import re
from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from game.models import Club, League

INLINE_STYLE_RE = re.compile(r'style\s*=\s*"([^"]*)"', re.IGNORECASE)


class ClubNewsPageTest(TestCase):
    def setUp(self):
        league = League.objects.create(name='Testliga', country='Deutschland')
        self.club = Club.objects.create(
            name='FC Testverein',
            short_name='FCT',
            founded_year=1900,
            budget=Decimal('1000000.00'),
            league=league,
        )

    def test_club_news_renders_without_max_width_inline_style(self):
        response = self.client.get(
            reverse('club_news', kwargs={'club_id': self.club.id})
        )

        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        offenders = [
            style for style in INLINE_STYLE_RE.findall(html)
            if 'max-width' in style
        ]
        self.assertEqual(
            offenders, [],
            f'max-width-Inline-Styles im gerenderten HTML gefunden: {offenders}'
        )

    def test_club_news_template_source_has_no_max_width_inline_style(self):
        path = os.path.join(
            str(settings.BASE_DIR), 'game', 'templates', 'game', 'club_news.html'
        )
        self.assertTrue(os.path.exists(path), 'club_news.html nicht gefunden')

        with open(path, encoding='utf-8') as fh:
            source = fh.read()

        offenders = [
            style for style in INLINE_STYLE_RE.findall(source)
            if 'max-width' in style
        ]
        self.assertEqual(
            offenders, [],
            f'max-width-Inline-Styles im Template gefunden: {offenders}'
        )
