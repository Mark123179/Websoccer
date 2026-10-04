import json
from datetime import timedelta
from pathlib import Path
import shutil
import subprocess
from unittest import skipUnless

from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from game.models import Club, ClubNewsItem, League
from game.news_archive import PAGE_SIZE


class NewsArchiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        league = League.objects.create(name='Archive League', country='Deutschland')
        cls.club = Club.objects.create(name='Archive FC', league=league, budget=0, founded_year=1900)
        cls.other = Club.objects.create(name='Other Archive', league=league, budget=0, founded_year=1900)
        today = timezone.localdate()
        ClubNewsItem.objects.bulk_create([
            ClubNewsItem(
                club=cls.club, title=f'Article {i}', category='Fans' if i % 3 == 0 else 'Interview',
                published_at=today - timedelta(days=i // 15), is_social=social,
                blocks=[{'k': 'text', 'text': f'Body {i}'}],
                views_count=100000 if i == 0 else i,
            )
            for social, size in [(False, 55), (True, 45)]
            for i in range(size)
        ])
        cls.foreign = ClubNewsItem.objects.create(club=cls.other, title='Foreign private scope')

    def data_url(self, club=None):
        return reverse('club_news_data', args=[(club or self.club).pk])

    def test_initial_html_is_bounded_and_top_ten_cover_whole_archive(self):
        response = self.client.get(reverse('club_news', args=[self.club.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.context['vn_data']
        self.assertEqual(len(data['art']), PAGE_SIZE)
        self.assertEqual(len(data['social']), PAGE_SIZE + 4)  # generated social posts remain
        self.assertEqual(len(data['top']), 10)
        self.assertEqual(data['archive']['total_art'], 55)
        self.assertTrue(data['archive']['art_cursor'])
        self.assertTrue(data['archive']['social_cursor'])
        old_top = ClubNewsItem.objects.filter(club=self.club, is_social=False, title='Article 54').get()
        self.assertIn(f'db_{old_top.pk}', [a['id'] for a in data['top']])
        self.assertNotIn(f'db_{old_top.pk}', [a['id'] for a in data['art']])

    def test_pages_preserve_order_filters_and_blocks_without_duplicates(self):
        for kind, social in [('art', False), ('social', True)]:
            cursor, articles = '', []
            while True:
                response = self.client.get(self.data_url(), {'kind': kind, 'cursor': cursor, 'limit': 100000})
                self.assertEqual(response.status_code, 200)
                page = response.json()
                self.assertLessEqual(len(page['items']), PAGE_SIZE)
                articles.extend(page['items'])
                cursor = page['next_cursor']
                if not cursor:
                    break
            expected = list(ClubNewsItem.objects.filter(
                club=self.club, is_social=social).order_by('-published_at', '-pk'))
            self.assertEqual([a['pk'] for a in articles], [a.pk for a in expected])
            self.assertEqual(len(set(a['id'] for a in articles)), len(expected))
            for article, item in zip(articles, expected):
                self.assertEqual(article['kat'], item.category)
                self.assertEqual(article['blocks'], item.blocks)
                self.assertEqual(article['isSocial'], social)

    def test_cursor_survives_new_publication_and_deleted_boundary(self):
        page = self.client.get(self.data_url()).json()
        initial_ids = [a['pk'] for a in page['items']]
        boundary = initial_ids[-1]
        expected = list(ClubNewsItem.objects.filter(club=self.club, is_social=False)
                        .order_by('-published_at', '-pk').values_list('pk', flat=True))[PAGE_SIZE:PAGE_SIZE * 2]
        ClubNewsItem.objects.create(club=self.club, title='Inserted after first page')
        ClubNewsItem.objects.filter(pk=boundary).delete()
        following = self.client.get(self.data_url(), {'cursor': page['next_cursor']}).json()
        self.assertEqual([a['pk'] for a in following['items']], expected)

    def test_old_direct_links_do_not_load_intermediate_pages(self):
        for social in (False, True):
            item = ClubNewsItem.objects.filter(club=self.club, is_social=social, title='Article 35').get()
            response = self.client.get(reverse('club_news_detail', args=[self.club.pk, item.pk]))
            self.assertEqual(response.status_code, 200)
            data = response.context['vn_data']
            self.assertEqual(data['initial_article'], f'db_{item.pk}')
            self.assertEqual(data['initial_item']['pk'], item.pk)
            self.assertEqual(data['initial_item']['blocks'], item.blocks)
            self.assertLessEqual(len(data['art']), PAGE_SIZE)
            self.assertNotIn(item.pk, [a['pk'] for a in data['art'] + data['social'] if 'pk' in a])
            target = self.client.get(self.data_url(), {'article': item.pk})
            self.assertEqual(target.json()['article'], data['initial_item'])

    def test_invalid_cursors_and_cross_club_articles_are_rejected(self):
        cursor = self.client.get(self.data_url()).json()['next_cursor']
        for params in ({'cursor': 'invalid'}, {'kind': 'nope'}, {'kind': 'social', 'cursor': cursor},
                       {'article': 'NaN'}, {'article': '-1'}, {'article': '9' * 100}):
            self.assertEqual(self.client.get(self.data_url(), params).status_code, 400)
        self.assertEqual(self.client.get(self.data_url(self.other), {'cursor': cursor}).status_code, 400)
        self.assertEqual(self.client.get(self.data_url(), {'article': self.foreign.pk}).status_code, 404)
        self.assertEqual(self.client.get(reverse('club_news_detail', args=[
            self.club.pk, self.foreign.pk])).status_code, 404)
        self.assertEqual(self.client.post(self.data_url()).status_code, 405)

    def test_empty_archive_has_no_next_page(self):
        ClubNewsItem.objects.filter(club=self.other).delete()
        self.assertEqual(self.client.get(self.data_url(self.other)).json(),
                         {'items': [], 'next_cursor': ''})


@skipUnless(shutil.which('node'), 'Node required for vanilla JS archive checks')
class NewsArchiveClientTests(SimpleTestCase):
    def test_incremental_load_retry_navigation_and_deduplication(self):
        runner = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const a=(id,kat='Interview')=>({id,pk:Number(id.slice(3)),title:id,kat,blocks:[],date:'01.01.2026',card:{}});
const root={innerHTML:''},requests=[];
let queue=[];
const ctx={window:{VN_DATA:{art:[a('db_3')],social:[a('auto_social_1','Social')],
  top:[a('db_1')],initial_item:a('db_0'),initial_article:'db_0',
  archive:{url:'/data/',art_cursor:'first',social_cursor:'social',total_art:3}},
  location:{hash:''},scrollTo:()=>{}},
  document:{getElementById:()=>root},URL,alert:()=>{},
  fetch:(url)=>{requests.push(url);return queue.shift()(url);}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
(async()=>{
assert.equal(ctx.state.view,'article');assert.equal(ctx.state.art.id,'db_0');
ctx.window.App.goHome();
assert.ok(root.innerHTML.includes('Weitere Beiträge laden'));
assert.equal(ctx.findArt('db_1').id,'db_1'); // old top-10 article can open
queue=[()=>Promise.resolve({ok:false}),()=>Promise.resolve({ok:true,json:()=>({items:[],next_cursor:''})})];
await ctx.window.App.loadMore();
assert.equal(ctx.ARCHIVE.art_cursor,'first');assert.equal(ctx.ARCHIVE.social_cursor,'social');
assert.ok(root.innerHTML.includes('Bitte erneut versuchen'));
let resolve;
queue=[()=>new Promise(r=>resolve=r),()=>Promise.resolve({ok:true,json:()=>({items:[a('db_8','Social')],next_cursor:''})})];
const pending=ctx.window.App.loadMore(),before=requests.length;
await ctx.window.App.loadMore();assert.equal(requests.length,before); // double clicks blocked
ctx.window.App.open('db_3');
resolve({ok:true,json:()=>({items:[a('db_3'),a('db_2','Fans')],next_cursor:'next'})});
await pending;
assert.equal(ctx.state.view,'article');assert.equal(ctx.state.art.id,'db_3');
assert.deepEqual(Array.from(ctx.ART,a=>a.id),['db_3','db_2']);
assert.equal(ctx.SOCIAL.length,2);assert.equal(ctx.ARCHIVE.social_cursor,'');
ctx.window.App.goHome();assert.ok(root.innerHTML.includes('db_2'));
queue=[()=>Promise.resolve({ok:true,json:()=>({items:[a('db_1')],next_cursor:''})})];
await ctx.window.App.loadMore();assert.ok(!root.innerHTML.includes('Weitere Beiträge laden'));
queue=[()=>Promise.resolve({ok:true,json:()=>({article:a('db_99')})})];
await ctx.window.App.openArchived('db_99');assert.equal(ctx.state.art.id,'db_99');
ctx.state.published=[a('db_3')];assert.equal(ctx.ALL().length,3);
ctx.ART=[];ctx.state.published=[];
assert.ok(ctx.homeHTML().includes('Noch keine News vorhanden')); // keep existing empty-state behavior
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result = subprocess.run(
            ['node', '-e', runner, str(Path('game/static/game/js/vereinsnews.js'))],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)