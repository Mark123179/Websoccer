from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from game.club_profile import build_news
from game.models import Club, ClubNewsItem, Player
from game.news_images import news_image_url, resolve_news_images


@override_settings(ASSETS_BASE_URL='/assets/')
class NewsImageTests(SimpleTestCase):
    def setUp(self):
        self.club = Club(pk=7, name='Newsverein', fm_inside_id=915)
        self.player = Player(pk=42, first_name='Harry', last_name='Kane',
                             position='ST', fm_inside_id=28049320, club_id=999)

    def item(self, pk=1, card=None, **kwargs):
        return ClubNewsItem(pk=pk, club_id=self.club.pk, title='Echte Nachricht',
                            card_data=card, **kwargs)

    def test_selected_motifs_override_legacy_thumbnails_and_preserve_data(self):
        own = 'data:image/png;base64,iVBORw0KGgo='
        items = [
            self.item(1, {'motiv': 'wappen'}, thumbnail_static_path='/old.png'),
            self.item(2, {'motiv': 'spieler', 'pid': '42'}, img_path='/wrong.png'),
            self.item(3, {'motiv': 'eigenes', 'customSrc': own}),
        ]
        before = [item.to_vn_dict() for item in items]
        with patch('game.news_images.Player.objects.in_bulk', return_value={42: self.player}) as lookup:
            images = resolve_news_images(items, self.club)
        lookup.assert_called_once_with({42})
        self.assertEqual(images, {
            1: '/assets/clubs/logos/915_club.png',
            2: '/assets/players/face_28049320.png',
            3: own,
        })
        self.assertEqual([item.to_vn_dict() for item in items], before)

    def test_missing_or_invalid_player_never_uses_another_portrait(self):
        for pid in (None, True, 3.5, 'nope', '', -1, '9' * 5000, 999):
            with self.subTest(pid=pid), patch(
                    'game.news_images.Player.objects.in_bulk', return_value={}) as lookup:
                images = resolve_news_images([
                    self.item(card={'motiv': 'spieler', 'pid': pid},
                              thumbnail_static_path='/unrelated-player.png')
                ], self.club)
                self.assertEqual(images[1], '')
                if pid != 999:
                    lookup.assert_not_called()

    def test_duplicate_player_references_are_loaded_once_even_after_transfer(self):
        items = [self.item(n, {'motiv': 'spieler', 'pid': 42}) for n in (1, 2, 3)]
        with patch('game.news_images.Player.objects.in_bulk', return_value={42: self.player}) as lookup:
            images = resolve_news_images(items, self.club)
        lookup.assert_called_once_with({42})
        self.assertEqual(set(images.values()), {'/assets/players/face_28049320.png'})

    def test_legacy_image_sources_and_invalid_cards(self):
        items = [
            self.item(1, thumbnail_static_path='game/images/news.png', img_path='/secondary.png'),
            self.item(2, ['invalid'], img_path='assets/players/face_123.png'),
            self.item(3, {'motiv': 'unknown'}, img_path='https://images.example.org/news.png'),
            self.item(4),
            self.item(5, {'motiv': 'eigenes', 'customSrc': None}),
        ]
        with patch('game.news_images.Player.objects.in_bulk') as lookup:
            images = resolve_news_images(items, self.club)
        lookup.assert_not_called()
        self.assertEqual(images, {
            1: '/static/game/images/news.png', 2: '/assets/players/face_123.png',
            3: 'https://images.example.org/news.png', 4: '', 5: '',
        })

    def test_asset_base_is_read_at_call_time(self):
        for base in ('/assets/', 'https://cdn.example.org/'):
            with self.subTest(base=base), override_settings(ASSETS_BASE_URL=base):
                self.assertEqual(news_image_url('/static/assets/players/face_42.png'),
                                 base + 'players/face_42.png')
        self.assertEqual(news_image_url('/media/news.png'), '/media/news.png')
        self.assertEqual(news_image_url({'invalid': 'image'}), '')

    def test_club_overview_context_and_template_use_selected_image(self):
        manager = MagicMock()
        manager.all.return_value.__getitem__.return_value = [
            self.item(card={'motiv': 'wappen'}),
        ]
        club = SimpleNamespace(pk=7, id=7, public_news=manager,
                               crest_static_path=self.club.crest_static_path)
        news = build_news(club)
        self.assertEqual(news[0]['thumbnailUrl'], '/assets/clubs/logos/915_club.png')
        html = render_to_string('game/club_profile/cards/news_card.html', {
            'profile': {'news': news, 'links': {'newsUrl': '/clubs/7/news/'}}
        })
        self.assertIn('src="/assets/clubs/logos/915_club.png"', html)
        self.assertIn('href="/clubs/7/news/"', html)
        self.assertIn('href="/clubs/7/news/1/"', html)
        self.assertLess(html.index('class="club-card-link"'), html.index('class="club-news-list"'))

    def test_link_alignment_is_scoped_to_news_card(self):
        css = Path('game/static/game/css/club-profile/compact-panels.css').read_text()
        rule = css.split('.news-profile-card .club-card-link {')[-1].split('}')[0]
        self.assertIn('right: auto', rule)
        self.assertIn('justify-content: flex-start', rule)
        self.assertIn('position: relative', rule)
        self.assertIn('bottom: auto', rule)