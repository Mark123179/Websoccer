import html as htmllib
import os
import re
import time
import unicodedata
import urllib.request
from urllib.error import HTTPError, URLError

from django.core.management.base import BaseCommand

from game.models import Club, Player


CDN_PORTRAIT = 'https://img.fminside.net/facesfm26/{id}.png'
CDN_CREST    = 'https://img.fminside.net/logos/Men/Clubs/Normal/{id}.png'

PORTRAIT_DIR = 'game/static/game/images/players'
CREST_DIR    = 'game/static/game/images/crests'

FMINSIDE_CLUBS = [
    (907,   'https://fminside.net/clubs/7-fm-26/907-borussia-dortmund'),
    (908,   'https://fminside.net/clubs/7-fm-26/908-borussia-monchengladbach'),
    (909,   'https://fminside.net/clubs/7-fm-26/909-bayer-leverkusen'),
    (910,   'https://fminside.net/clubs/7-fm-26/910-eintracht-frankfurt'),
    (911,   'https://fminside.net/clubs/7-fm-26/911-mainz-05'),
    (912,   'https://fminside.net/clubs/7-fm-26/912-werder-bremen'),
    (913,   'https://fminside.net/clubs/7-fm-26/913-vfb-stuttgart'),
    (914,   'https://fminside.net/clubs/7-fm-26/914-sc-freiburg'),
    (915,   'https://fminside.net/clubs/7-fm-26/915-fc-bayern'),
    (916,   'https://fminside.net/clubs/7-fm-26/916-wolfsburg'),
    (917,   'https://fminside.net/clubs/7-fm-26/917-bochum'),
    (922,   'https://fminside.net/clubs/7-fm-26/922-st-pauli'),
    (5890,  'https://fminside.net/clubs/7-fm-26/5890-union-berlin'),
    (6430,  'https://fminside.net/clubs/7-fm-26/6430-holstein-kiel'),
    (6721,  'https://fminside.net/clubs/7-fm-26/6721-rb-leipzig'),
    (12185, 'https://fminside.net/clubs/7-fm-26/12185-tsg-hoffenheim'),
    (12498, 'https://fminside.net/clubs/7-fm-26/12498-fc-augsburg'),
    (13076, 'https://fminside.net/clubs/7-fm-26/13076-heidenheim'),
]

FETCH_DELAY   = 5
PORTRAIT_DELAY = 0.15


class Command(BaseCommand):
    help = (
        'Scrapt FMInside für alle 18 Bundesliga-Clubs, setzt fm_inside_ids '
        'für alle Spieler per Namen-Matching und lädt Portraits + Wappen herunter.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--portraits-only',
            action='store_true',
            help='Nur fehlende Portraits herunterladen (kein Scraping)',
        )
        parser.add_argument(
            '--crests-only',
            action='store_true',
            help='Nur fehlende Wappen herunterladen (kein Scraping)',
        )
        parser.add_argument(
            '--club',
            type=int,
            help='Nur einen bestimmten Club bearbeiten (fm_inside_id)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=FETCH_DELAY,
            help=f'Sekunden zwischen FMInside-Requests (Standard: {FETCH_DELAY})',
        )

    def handle(self, *args, **options):
        os.makedirs(PORTRAIT_DIR, exist_ok=True)
        os.makedirs(CREST_DIR, exist_ok=True)

        delay = options['delay']

        if options['portraits_only']:
            self.download_all_portraits()
            return

        if options['crests_only']:
            self.download_all_crests(delay)
            return

        clubs_to_process = FMINSIDE_CLUBS
        if options['club']:
            clubs_to_process = [(fmid, url) for fmid, url in FMINSIDE_CLUBS if fmid == options['club']]
            if not clubs_to_process:
                self.stdout.write(self.style.ERROR(f"Club {options['club']} nicht in der Liste."))
                return

        total_matched   = 0
        total_portraits = 0
        total_crests    = 0

        for i, (club_fm_id, url) in enumerate(clubs_to_process):
            try:
                club = Club.objects.get(fm_inside_id=club_fm_id)
            except Club.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Club fm_id={club_fm_id} nicht in DB — übersprungen."))
                continue

            if i > 0:
                time.sleep(delay)

            self.stdout.write(f"\n[{i+1}/{len(clubs_to_process)}] {club.name}...")

            try:
                page = self._fetch(url)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Fetch fehlgeschlagen: {e}"))
                continue

            page_size = len(page)

            crest_saved = self._download_crest(club_fm_id, page)
            if crest_saved:
                total_crests += 1

            if page_size < 30000:
                self.stdout.write(self.style.WARNING(
                    f"  Seite zu klein ({page_size} Bytes) — wahrscheinlich Rate-Limit. "
                    f"Wappen: {'✓' if crest_saved else '–'}"
                ))
                continue

            fm_players = self._extract_players(page)
            if not fm_players:
                self.stdout.write(self.style.WARNING(f"  Keine Spieler auf Seite ({page_size} Bytes)"))
                continue

            matched  = self._match_players(club, fm_players)
            portraits = self._download_portraits_for_club(club)

            total_matched   += matched
            total_portraits += portraits

            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {page_size//1000}KB | FMInside-Pool={len(fm_players)//2} | "
                f"IDs vergeben={matched} | Portraits={portraits} | Wappen={'✓' if crest_saved else 'schon da'}"
            ))

        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(self.style.SUCCESS(
            f"Fertig: {total_matched} IDs neu vergeben | "
            f"{total_portraits} Portraits heruntergeladen | "
            f"{total_crests} Wappen gespeichert"
        ))

        total = Player.objects.count()
        with_id = Player.objects.exclude(fm_inside_id__isnull=True).exclude(fm_inside_id=0).count()
        self.stdout.write(f"Spieler gesamt: {with_id}/{total} mit fm_inside_id")

    def _fetch(self, url):
        req = urllib.request.Request(url, headers={
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/121.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        })
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read()
        try:
            import gzip
            return gzip.decompress(raw).decode('utf-8', errors='ignore')
        except Exception:
            return raw.decode('utf-8', errors='ignore')

    def _download_bytes(self, url):
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://fminside.net/',
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.read()

    def _extract_players(self, page):
        if '<h2>Full Squad</h2>' not in page:
            return {}
        section = page.split('<h2>Full Squad</h2>', 1)[1].split('<h2>', 1)[0]
        rows = re.findall(r'<ul class="player">(.*?)</ul>', section, flags=re.S)
        players = {}
        for row in rows:
            link = re.search(
                r'href="/players/7-fm\d+/(\d+)-[^"]+"[^>]*>([^<]+)</a>', row
            )
            if not link:
                continue
            fm_id = int(link.group(1))
            name  = htmllib.unescape(link.group(2)).strip()
            players[self._norm(name)] = fm_id
            parts = name.split()
            if len(parts) > 1:
                players[self._norm(' '.join(reversed(parts)))] = fm_id
        return players

    def _match_players(self, club, fm_players):
        matched = 0
        for p in Player.objects.filter(club=club):
            if p.fm_inside_id and p.fm_inside_id != 0:
                continue
            fm_id = (
                fm_players.get(self._norm(p.full_name))
                or fm_players.get(self._norm(p.last_name))
                or fm_players.get(self._norm(p.first_name + ' ' + p.last_name))
            )
            if fm_id:
                p.fm_inside_id = fm_id
                p.save(update_fields=['fm_inside_id'])
                matched += 1
        return matched

    def _download_portraits_for_club(self, club):
        downloaded = 0
        for p in Player.objects.filter(club=club).exclude(fm_inside_id__isnull=True).exclude(fm_inside_id=0):
            dst_png = os.path.join(PORTRAIT_DIR, f'{p.fm_inside_id}.png')
            dst_svg = os.path.join(PORTRAIT_DIR, f'{p.fm_inside_id}.svg')
            if os.path.exists(dst_png) or os.path.exists(dst_svg):
                continue
            try:
                data = self._download_bytes(CDN_PORTRAIT.format(id=p.fm_inside_id))
                with open(dst_png, 'wb') as f:
                    f.write(data)
                downloaded += 1
                time.sleep(PORTRAIT_DELAY)
            except Exception:
                pass
        return downloaded

    def _download_crest(self, club_fm_id, page=''):
        dst = os.path.join(CREST_DIR, f'{club_fm_id}.png')
        if os.path.exists(dst):
            return False

        for logo_id in self._find_logo_ids(club_fm_id, page):
            try:
                data = self._download_bytes(CDN_CREST.format(id=logo_id))
                with open(dst, 'wb') as f:
                    f.write(data)
                return True
            except Exception:
                continue
        return False

    def _find_logo_ids(self, club_fm_id, page):
        ids = [club_fm_id]
        if page:
            for m in re.finditer(
                r'logos/Men/Clubs/Normal/(\d+)\.png', page
            ):
                found = int(m.group(1))
                if found not in ids:
                    ids.append(found)
        return ids

    def download_all_portraits(self):
        self.stdout.write('Lade alle fehlenden Portraits herunter...')
        players = (
            Player.objects.exclude(fm_inside_id__isnull=True)
            .exclude(fm_inside_id=0)
            .order_by('club__name', 'last_name')
        )
        ok = skip = err = 0
        for p in players:
            dst = os.path.join(PORTRAIT_DIR, f'{p.fm_inside_id}.png')
            if os.path.exists(dst) or os.path.exists(dst.replace('.png', '.svg')):
                skip += 1
                continue
            try:
                data = self._download_bytes(CDN_PORTRAIT.format(id=p.fm_inside_id))
                with open(dst, 'wb') as f:
                    f.write(data)
                ok += 1
                time.sleep(PORTRAIT_DELAY)
            except Exception:
                err += 1

        self.stdout.write(self.style.SUCCESS(
            f'Portraits: {ok} neu, {skip} übersprungen, {err} nicht verfügbar'
        ))

    def download_all_crests(self, delay=3):
        self.stdout.write('Lade alle fehlenden Wappen herunter...')
        ok = skip = err = 0
        for club_fm_id, url in FMINSIDE_CLUBS:
            dst = os.path.join(CREST_DIR, f'{club_fm_id}.png')
            if os.path.exists(dst):
                skip += 1
                continue
            try:
                data = self._download_bytes(CDN_CREST.format(id=club_fm_id))
                with open(dst, 'wb') as f:
                    f.write(data)
                ok += 1
                self.stdout.write(f'  ✓ {club_fm_id}.png')
                time.sleep(0.5)
                continue
            except Exception:
                pass
            try:
                time.sleep(delay)
                page = self._fetch(url)
                saved = self._download_crest(club_fm_id, page)
                if saved:
                    ok += 1
                    self.stdout.write(f'  ✓ {club_fm_id}.png (via Seite)')
                else:
                    err += 1
                    self.stdout.write(self.style.WARNING(f'  ? {club_fm_id} nicht gefunden'))
            except Exception as e:
                err += 1
                self.stdout.write(self.style.ERROR(f'  ✗ {club_fm_id}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'Wappen: {ok} neu, {skip} übersprungen, {err} nicht verfügbar'
        ))

    @staticmethod
    def _norm(name):
        n = unicodedata.normalize('NFKD', name)
        n = ''.join(c for c in n if not unicodedata.combining(c))
        return re.sub(r'[^a-z0-9]+', '', n.lower())
