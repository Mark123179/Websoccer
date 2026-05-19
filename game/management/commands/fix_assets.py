"""
fix_assets: 
  1. Korrigiert alle Club fm_inside_ids (12 verifizierte + behält 6 unbekannte)
  2. Extrahiert Wappen aus Germany-Pack für korrigierte Clubs
  3. Lädt Spielerportraits von sortitoutsi CDN (nur für Spieler mit fm_inside_id)
  4. Setzt default_player.png als Fallback
"""
import os, time, shutil, zipfile, re
import urllib.request
from django.core.management.base import BaseCommand
from django.conf import settings
from game.models import Club, Player

# Verifizierte korrekte FM Club UIDs
CORRECT_IDS = {
    'FC Bayern München':        915,
    'Borussia Dortmund':        907,
    'Borussia Mönchengladbach': 908,
    'Bayer 04 Leverkusen':      901,
    'VfL Bochum':               905,
    'Eintracht Frankfurt':      912,
    '1. FSV Mainz 05':          918,
    'SC Freiburg':              944,
    'FC St. Pauli':             946,
    'SV Werder Bremen':         948,
    'VfB Stuttgart':            960,
    'VfL Wolfsburg':            961,
    # Noch unbekannt – aktuelle Werte behalten:
    # '1. FC Union Berlin': 5890,
    # 'Holstein Kiel': 6430,
    # 'RB Leipzig': 6721,
    # 'TSG 1899 Hoffenheim': 12185,
    # 'FC Augsburg': 12498,
    # '1. FC Heidenheim': 13076,
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120'}
CRESTS_DIR  = os.path.join(settings.BASE_DIR, 'game', 'static', 'game', 'images', 'crests')
PLAYERS_DIR = os.path.join(settings.BASE_DIR, 'game', 'static', 'game', 'images', 'players')
GERMANY_ZIP = os.path.join(settings.BASE_DIR, 'attached_assets', 'Germany_1779232001068.zip')
DEFAULT_IMG = os.path.join(settings.BASE_DIR, 'attached_assets', 'default_player_1779231942698.png')


class Command(BaseCommand):
    help = 'Wappen extrahieren, Club-IDs korrigieren, Portraits laden'

    def add_arguments(self, parser):
        parser.add_argument('--portraits-only', action='store_true')
        parser.add_argument('--crests-only',    action='store_true')
        parser.add_argument('--delay', type=float, default=1.0)

    def handle(self, *args, **options):
        os.makedirs(CRESTS_DIR,  exist_ok=True)
        os.makedirs(PLAYERS_DIR, exist_ok=True)

        portraits_only = options['portraits_only']
        crests_only    = options['crests_only']
        delay          = options['delay']

        if not portraits_only:
            self._fix_club_ids()
            self._extract_crests()

        if not crests_only:
            self._copy_default()
            self._download_portraits(delay)

    # ──────────────────────────────────────────────
    def _fix_club_ids(self):
        self.stdout.write('\n=== Club-IDs korrigieren ===')
        from django.db import connection

        # Pass 1: alle die geändert werden müssen auf NULL setzen (umgeht UNIQUE-Konflikt)
        needs_change = {}
        for name, correct_id in CORRECT_IDS.items():
            try:
                club = Club.objects.get(name=name)
                if club.fm_inside_id != correct_id:
                    needs_change[club] = (club.fm_inside_id, correct_id)
                    club.fm_inside_id = None
                    club.save(update_fields=['fm_inside_id'])
            except Club.DoesNotExist:
                self.stdout.write(f'  ✗ {name}: nicht in DB')

        # Pass 2: korrekte IDs setzen + Crest-Dateien umbenennen
        for club, (old_id, correct_id) in needs_change.items():
            for ext in ('png', 'svg'):
                old_f = os.path.join(CRESTS_DIR, f'{old_id}.{ext}')
                new_f = os.path.join(CRESTS_DIR, f'{correct_id}.{ext}')
                if os.path.exists(old_f) and not os.path.exists(new_f):
                    shutil.move(old_f, new_f)
                    self.stdout.write(f'  Renamed: {old_id}.{ext} → {correct_id}.{ext}')
            club.fm_inside_id = correct_id
            club.save(update_fields=['fm_inside_id'])
            self.stdout.write(f'  ✓ {club.name}: {old_id} → {correct_id}')

        unchanged = len(CORRECT_IDS) - len(needs_change)
        self.stdout.write(f'  → {len(needs_change)} geändert, {unchanged} bereits korrekt')

    # ──────────────────────────────────────────────
    def _extract_crests(self):
        self.stdout.write('\n=== Wappen aus Germany-Pack extrahieren ===')
        if not os.path.exists(GERMANY_ZIP):
            self.stdout.write('  Germany-Pack nicht gefunden, übersprungen.')
            return

        # Alle Club-UIDs die wir brauchen
        needed = set(Club.objects.exclude(fm_inside_id=None)
                                 .values_list('fm_inside_id', flat=True))

        extracted = 0
        skipped   = 0
        with zipfile.ZipFile(GERMANY_ZIP) as z:
            for uid in needed:
                dest = os.path.join(CRESTS_DIR, f'{uid}.png')
                if os.path.exists(dest):
                    skipped += 1
                    continue
                internal = f'Germany/Clubs/TCM1_{uid}.png'
                try:
                    with z.open(internal) as src, open(dest, 'wb') as dst:
                        dst.write(src.read())
                    self.stdout.write(f'  ✓ Extrahiert: {uid}.png')
                    extracted += 1
                except KeyError:
                    self.stdout.write(f'  ✗ Nicht im Pack: TCM1_{uid}.png (uid={uid})')

        self.stdout.write(f'  → {extracted} extrahiert, {skipped} schon vorhanden')

    # ──────────────────────────────────────────────
    def _copy_default(self):
        dest = os.path.join(PLAYERS_DIR, 'default.png')
        if not os.path.exists(dest) and os.path.exists(DEFAULT_IMG):
            shutil.copy(DEFAULT_IMG, dest)
            self.stdout.write('  ✓ default.png kopiert')

    # ──────────────────────────────────────────────
    def _download_portraits(self, delay):
        self.stdout.write('\n=== Portraits von sortitoutsi laden ===')
        players = (Player.objects.exclude(fm_inside_id=None)
                                 .order_by('club__name', 'last_name'))
        total = players.count()
        downloaded = 0
        skipped    = 0
        failed     = 0

        self.stdout.write(f'  {total} Spieler mit fm_inside_id')

        for p in players:
            dest = os.path.join(PLAYERS_DIR, f'{p.fm_inside_id}.png')
            if os.path.exists(dest) and os.path.getsize(dest) > 500:
                skipped += 1
                continue

            url = f'https://sortitoutsi.b-cdn.net/uploads/face/face_{p.fm_inside_id}.png'
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = r.read()
                if len(data) < 500:
                    # Placeholder/leer → default verwenden
                    failed += 1
                    continue
                with open(dest, 'wb') as f:
                    f.write(data)
                downloaded += 1
                name = f'{p.first_name} {p.last_name}'.strip()
                self.stdout.write(f'  ✓ {name}: {len(data)//1024}KB')
                time.sleep(delay)
            except Exception as e:
                self.stdout.write(f'  ✗ {p.fm_inside_id}: {e}')
                failed += 1

        self.stdout.write(
            f'\n  → {downloaded} heruntergeladen | {skipped} vorhanden | {failed} fehlgeschlagen'
        )
