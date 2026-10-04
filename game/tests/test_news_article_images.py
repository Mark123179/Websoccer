"""Full-page and JS rendering regressions for historical news motifs."""
import json
import shutil
import subprocess
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from game.models import Club, ClubNewsItem, League, Player
from game.news_images import news_article_dicts, resolve_news_images


@override_settings(ASSETS_BASE_URL='/assets/')
class NewsArticleImageTests(TestCase):
    def setUp(self):
        league = League.objects.create(name='News League', country='Deutschland')
        self.club = Club.objects.create(name='News Home', founded_year=1900, budget=0,
                                        league=league)
        self.other = Club.objects.create(name='News Away', founded_year=1900, budget=0,
                                         league=league)
        self.selected = Player.objects.create(
            club=self.club, first_name='Selected', last_name='Player',
            position='ST', age=25, fm_inside_id=28049320)
        self.replacement = Player.objects.create(
            club=self.club, first_name='Other', last_name='Player',
            position='ST', age=25, fm_inside_id=12345)
        self.item = ClubNewsItem.objects.create(
            club=self.club, title='Historical news',
            card_data={'motiv': 'spieler', 'pid': str(self.selected.pk)},
            img_path='/unrelated.png', thumbnail_static_path='/unrelated-thumb.png',
            blocks=[{'k': 'text', 'text': 'Historical article body'}])

    def page_data(self, detail=False):
        url = reverse('club_news_detail' if detail else 'club_news', kwargs={
            'club_id': self.club.pk,
            **({'news_id': self.item.pk} if detail else {}),
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game/club_news.html')
        return response.context['vn_data']

    def test_transfer_keeps_exact_portrait_in_full_page_and_detail(self):
        before = news_article_dicts([self.item], self.club)[0]
        saved_card = self.item.card_data.copy()
        self.selected.club = self.other
        self.selected.save(update_fields=['club'])
        for social in (False, True):
            self.item.is_social = social
            self.item.save(update_fields=['is_social'])
            for detail in (False, True):
                with self.subTest(social=social, detail=detail):
                    data = self.page_data(detail)
                    article = (data['social'] if social else data['art'])[0]
                    self.assertEqual(article['cardImageUrl'], before['cardImageUrl'])
                    self.assertEqual(article['cardImageUrl'],
                                     resolve_news_images([self.item], self.club)[self.item.pk])
                    self.assertNotIn(str(self.selected.pk), data['players'])
                    self.assertIn(str(self.replacement.pk), data['players'])
                    self.assertEqual(data['initial_article'],
                                     f'db_{self.item.pk}' if detail else '')
                    self.assertEqual(article['blocks'], self.item.blocks)
        self.item.refresh_from_db()
        self.assertEqual(self.item.card_data, saved_card)
        self.assertEqual(self.item.img_path, '/unrelated.png')
        self.assertEqual(self.item.thumbnail_static_path, '/unrelated-thumb.png')

    def test_missing_player_id_never_uses_current_squad_or_legacy_image(self):
        for pid in (None, '', 'invalid', True, self.selected.pk + 1000000):
            with self.subTest(pid=pid):
                self.item.card_data = {'motiv': 'spieler', 'pid': pid}
                self.item.save(update_fields=['card_data'])
                for detail in (False, True):
                    data = self.page_data(detail)
                    self.assertEqual(data['art'][0]['cardImageUrl'], '')
                    self.assertEqual(data['art'][0]['card'], self.item.card_data)
                self.item.refresh_from_db()
                self.assertEqual(self.item.card_data['pid'], pid)

    def test_deleted_player_never_uses_another_person(self):
        self.selected.delete()
        self.assertEqual(self.page_data()['art'][0]['cardImageUrl'], '')
        self.assertEqual(self.page_data(True)['art'][0]['cardImageUrl'], '')

    def test_detail_rejects_article_from_another_club(self):
        response = self.client.get(reverse('club_news_detail', kwargs={
            'club_id': self.other.pk, 'news_id': self.item.pk,
        }))
        self.assertEqual(response.status_code, 404)

    def test_publish_response_uses_same_image_source(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(username='news-author')
        self.client.force_login(user)
        payload = {'titel': 'New publication', 'kat': 'Transfer-News',
                   'card': self.item.card_data, 'blocks': []}
        with patch('game.views.current_manager_club', return_value=self.club):
            response = self.client.post(
                reverse('club_news_publish', kwargs={'club_id': self.club.pk}),
                data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        article = response.json()['article']
        saved = ClubNewsItem.objects.get(pk=article['pk'])
        self.assertEqual(article, news_article_dicts([saved], self.club)[0])

    @skipUnless(shutil.which('node'), 'Node required for vanilla JS rendering checks')
    def test_js_cards_detail_and_editor_do_not_replace_missing_players(self):
        self.selected.club = self.other
        self.selected.save(update_fields=['club'])
        data = self.page_data(True)
        script_path = Path('game/static/game/js/vereinsnews.js')
        runner = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const root = {innerHTML: ''};
const ctx = {window: {VN_DATA: data, location: {hash: ''}},
             document: {getElementById: () => root}, URL};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const article = data.art[0], expected = article.cardImageUrl;
assert.strictEqual(ctx.state.view, 'article');
assert.ok(root.innerHTML.includes(expected));
assert.ok(root.innerHTML.includes('Historical article body'));
for (const render of [ctx.cardHTML, a => ctx.topHTML(a, 0), ctx.articleHTML]) {
    assert.ok(render(article).includes(expected));
    const missing = {...article, cardImageUrl: ''};
    assert.ok(!render(missing).includes(expected));
    assert.ok(!render(missing).includes('face_12345'));
}
assert.ok(ctx.homeHTML().includes(expected));
assert.strictEqual(ctx.cardArt({card: {motiv: 'spieler', pid: 'missing'}}).img, null);
const currentId = Object.keys(data.players)[0];
assert.strictEqual(ctx.cardArt({card: {motiv: 'spieler', pid: currentId}}).img,
                   data.players[currentId].img);
assert.strictEqual(ctx.cardArt({card: {motiv: 'wappen'},
                               cardImageUrl: '/exact-crest.png'}).img, '/exact-crest.png');
assert.strictEqual(ctx.cardArt({card: {motiv: 'eigenes'},
                               cardImageUrl: '/exact-upload.png'}).custom, '/exact-upload.png');
assert.strictEqual(ctx.cardArt({img: '/legacy.png',
                               cardImageUrl: '/exact-legacy.png'}).img, '/exact-legacy.png');
"""
        result = subprocess.run(
            ['node', '-e', runner, str(script_path)],
            input=json.dumps(data), text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)