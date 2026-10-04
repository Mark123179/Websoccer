import base64
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from game.models import Club, ClubNewsItem, League
from game.news_validation import (
    MAX_IMAGE_BYTES, MAX_NEWS_BODY_BYTES, validate_image_source,
)


def raster_source(fmt='PNG'):
    stream = BytesIO()
    Image.new('RGB', (2, 2), 'red').save(stream, format=fmt)
    mime = {'PNG': 'png', 'JPEG': 'jpeg', 'GIF': 'gif', 'WEBP': 'webp'}[fmt]
    return 'data:image/' + mime + ';base64,' + base64.b64encode(stream.getvalue()).decode()


class NewsPublishSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='news_security')
        cls.league = League.objects.create(name='News Security League', country='Deutschland')
        cls.club = Club.objects.create(
            name='News Security', founded_year=1900, budget=0, league=cls.league,
            managed_by=cls.user.manager_profile,
        )
        cls.other = Club.objects.create(
            name='Other News', founded_year=1900, budget=0, league=cls.league,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('club_news_publish', args=[self.club.pk])

    def post(self, payload, url=None):
        return self.client.post(url or self.url, json.dumps(payload), content_type='application/json')

    def payload(self, source=None):
        return {
            'titel': 'Neue Nachricht', 'sub': 'Untertitel', 'kat': 'Transfer-News',
            'outlet': 'Vereinsredaktion',
            'card': {'motiv': 'eigenes', 'pid': '', 'accent': '#22e6ff', 'customSrc': source},
            'blocks': [],
        }

    def assert_rejected(self, payload, status=400):
        before = ClubNewsItem.objects.count()
        response = self.post(payload)
        self.assertEqual(response.status_code, status, response.content[:300])
        self.assertFalse(response.json()['ok'])
        self.assertEqual(ClubNewsItem.objects.count(), before)

    def test_legitimate_custom_images_survive_publication_and_reload(self):
        for source in [raster_source(fmt) for fmt in ('PNG', 'JPEG', 'GIF', 'WEBP')] + [
            'https://example.org/news.png?x=1&y=2', 'http://example.org/news.jpg', '/media/news.png',
        ]:
            with self.subTest(source=source[:60]):
                response = self.post(self.payload(source))
                self.assertEqual(response.status_code, 200, response.content[:300])
                item = ClubNewsItem.objects.get(pk=response.json()['article']['pk'])
                self.assertEqual(item.card_data['customSrc'], source)
                self.assertEqual(item.to_vn_dict()['card']['customSrc'], source)

    def test_allowed_motifs_and_absent_card(self):
        for motif in ('none', 'wappen', 'spieler', 'eigenes'):
            body = self.payload()
            body['card']['motiv'] = motif
            self.assertEqual(self.post(body).status_code, 200)
        body = self.payload()
        del body['card']
        self.assertEqual(self.post(body).status_code, 200)

    def test_attribute_injection_and_unsafe_schemes_are_rejected(self):
        for source in [
            'https://example.org/x" onerror="alert(1)',
            '/x"><script>alert(1)</script>',
            'javascript:alert(1)', 'JaVaScRiPt:alert(1)', 'vbscript:msgbox(1)',
            'file:///etc/passwd', 'blob:https://example.org/id', '//example.org/a',
            '/\\example.org/a', 'https://example.org/a\n.png',
            'data:text/html;base64,PHNjcmlwdD4=', 'data:image/svg+xml;base64,PHN2Zz4=',
            'https://user:password@example.org/a.png', 'https://example.org:bad/a',
        ]:
            with self.subTest(source=source):
                self.assert_rejected(self.payload(source))

    def test_false_json_types_return_errors_not_server_exceptions(self):
        for body in ([], None, True, 42, 'text'):
            with self.subTest(body=body):
                self.assert_rejected(body)
        for field, values in {
            'card': [[], 'card', 42, False],
            'titel': [[], {}, 42, None],
            'sub': [{}, False], 'kat': [[], {}], 'outlet': [[], {}],
            'blocks': [{}, 'blocks', [None], [42], [{'k': []}]],
        }.items():
            for value in values:
                body = self.payload()
                body[field] = value
                with self.subTest(field=field, value=value):
                    self.assert_rejected(body)
        for field, values in {
            'motiv': [[], {}, 42, 'unknown'],
            'pid': [[], {}, False, '../player', '1' * 20],
            'accent': [[], {}, False, 'red', '#fff" onclick="alert(1)'],
            'customSrc': [[], {}, 42, False],
        }.items():
            for value in values:
                body = self.payload()
                body['card'][field] = value
                with self.subTest(field=field, value=value):
                    self.assert_rejected(body)
        body = self.payload()
        body['card']['unknown'] = 'field'
        self.assert_rejected(body)

    def test_invalid_raster_contents_and_mime_mismatch(self):
        for source in (
            'data:image/png;base64,%%%%', 'data:image/png;base64,AAAA',
            raster_source().replace('image/png', 'image/jpeg'),
        ):
            self.assert_rejected(self.payload(source))

    def test_size_limits_apply_before_persistence(self):
        source = 'data:image/png;base64,' + base64.b64encode(b'x' * (MAX_IMAGE_BYTES + 1)).decode()
        self.assert_rejected(self.payload(source))
        self.assert_rejected(self.payload('data:image/png;base64,' + 'A' * MAX_NEWS_BODY_BYTES), 413)
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=50):
            self.assert_rejected(self.payload(), 413)

    def test_image_blocks_cannot_bypass_source_validation(self):
        for source in ('javascript:alert(1)', 'https://a.test/" onerror="alert(1)', [], {}):
            body = self.payload()
            body['blocks'] = [{'k': 'image', 'src': source}]
            self.assert_rejected(body)
        body = self.payload()
        body['blocks'] = [{'k': 'image', 'src': raster_source(), 'cap': 'Bild'}]
        self.assertEqual(self.post(body).status_code, 200)

    def test_foreign_club_permissions_remain_intact(self):
        url = reverse('club_news_publish', args=[self.other.pk])
        body = self.payload(raster_source())
        self.assertEqual(self.post(body, url).status_code, 403)
        body['outlet'] = 'Kicker'
        self.assertEqual(self.post(body, url).status_code, 200)
        body['blocks'] = [{'k': 'match'}]
        self.assertEqual(self.post(body, url).status_code, 403)

    def test_legacy_records_are_not_rewritten_by_full_page(self):
        sources = [
            raster_source(), 'https://example.org/news.png',
            'data:image/png;base64,' + 'A' * (MAX_IMAGE_BYTES * 2),
            'https://example.org/x" onerror="alert(1)',
        ]
        for source in sources:
            item = ClubNewsItem.objects.create(
                club=self.club, title='Alt </script><script>alert(1)</script>',
                card_data=self.payload(source)['card'],
            )
            response = self.client.get(reverse('club_news', args=[self.club.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['vn_data']['art'][0]['card']['customSrc'], source)
            self.assertNotIn(b'</script><script>alert(1)</script>', response.content)
            item.refresh_from_db()
            self.assertEqual(item.card_data['customSrc'], source)


class NewsSourceValidationTests(SimpleTestCase):
    def test_pixel_limit(self):
        stream = BytesIO()
        Image.new('1', (4001, 4000)).save(stream, format='PNG')
        source = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()
        with self.assertRaisesMessage(ValueError, '16 Megapixel'):
            validate_image_source(source)

    def test_template_json_bootstrap_cannot_break_out(self):
        attack = '</script><script>alert(1)</script>'
        html = render_to_string('game/club_news.html', {
            'club': Club(name='Test'), 'vn_data': {'art': [{'card': {'customSrc': attack}}]},
        })
        self.assertNotIn(attack, html)
        self.assertIn(r'\u003C/script\u003E', html)
        self.assertIn('JSON.parse', html)


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.images.append(dict(attrs))


class NewsClientSecurityTests(SimpleTestCase):
    def test_collected_production_news_script_matches_hardened_source(self):
        source = Path('game/static/game/js/vereinsnews.js').read_bytes()
        production = Path('staticfiles/game/js/vereinsnews.js').read_bytes()
        self.assertEqual(production, source, 'Regenerate the collected production news script.')

    def test_all_custom_image_render_paths_escape_legacy_attributes(self):
        script = Path('game/static/game/js/vereinsnews.js')
        program = r"""
const vm = require('node:vm'), fs = require('node:fs'), assert = require('node:assert/strict');
const ctx = {
  window: {VN_DATA: {is_own_club: true}, location: {hash: ''}},
  document: {getElementById: () => ({innerHTML: ''})}, URL,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const source = 'https://example.org/a" onerror="alert(1)&test=1';
const article = {id:'db_1',kat:'Fans',outlet:'Vereinsredaktion',title:'Alt',date:'Heute',
  card:{motiv:'eigenes',customSrc:source,accent:'#22e6ff'},blocks:[]};
ctx.ART = [article]; ctx.state.ed.card = article.card; ctx.state.edPrev = 'karte';
const outputs = [
  ctx.cardHTML(article),ctx.topHTML(article,1),ctx.homeHTML(),
  ctx.articleHTML(article),ctx.previewHTML(),ctx.editorHTML(),
  ctx.blocksHTML([{k:'image',src:source}]),ctx.blockEdHTML({k:'image',src:source},0)
];
article.cardImageUrl = source;
outputs.push(ctx.cardHTML(article),ctx.topHTML(article,1),ctx.homeHTML(),ctx.articleHTML(article));
delete article.cardImageUrl;
for(const bad of [null,42,[],{},'javascript:alert(1)','data:text/html;base64,AAAA',
  'data:image/svg+xml,<svg onload="alert(1)">','//example.org/x','/\\example.org/x']) {
  article.card.customSrc = bad;
  assert.equal(ctx.cardArt(article).custom, '');
  assert.equal(ctx.imageHTML(bad,'card-custom'), '');
  article.cardImageUrl = bad;
  assert.equal(ctx.cardArt(article).custom, null);
  delete article.cardImageUrl;
}
for(const card of [null,[],42,{accent:[],motiv:'unknown'}]) {
  article.card = card;
  ctx.cardHTML(article);ctx.articleHTML(article);
}
for(const good of ['/media/news.png','https://example.org/a.png','data:image/png;base64,AAAA',
  'data:image/svg+xml;base64,PHN2Zy8+', 'data:image/avif;base64,AAAA',
  'data:image/png;base64,'+'A'.repeat(2*1024*1024)]) {
  assert.equal(ctx.safeImageSource(good),good);
}
let readers = 0, alerts = 0;
ctx.alert = () => alerts++;
ctx.FileReader = function(){readers++;};
ctx.window.App.readImg({type:'image/svg+xml',size:1},-1);
ctx.window.App.readImg({type:'image/png',size:1024*1024+1},-1);
assert.equal(readers,0);assert.equal(alerts,2);
console.log(JSON.stringify({source,outputs}));
"""
        result = subprocess.run(
            ['node', '-e', program, str(script)], capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        self.assertEqual(len(data['outputs']), 12)
        for output in data['outputs']:
            parser = ImageParser()
            parser.feed(output)
            self.assertTrue(parser.images)
            for image in parser.images:
                self.assertEqual(image['src'], data['source'])
                self.assertNotIn('onerror', image)
                self.assertEqual(set(image), {'class', 'src', 'alt'})