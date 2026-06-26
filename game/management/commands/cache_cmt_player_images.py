"""Lädt CMT-Spielerbilder lokal in media/player_images/cmt/<id>.png.

Ohne --apply: Dry-Run (keine Downloads).
Mit --apply: lädt player_image_url herunter, setzt player_image_cached_path.
Mit --force: überschreibt bereits gecachte Bilder.
Fehlende/404-Bilder erzeugen nur eine Warnung, kein Abbruch.

Kein updated_at (Feld existiert nicht auf PlayerCMTProfile).
"""

import os
import time

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from game.models import PlayerCMTProfile

_MEDIA_SUBDIR = 'player_images/cmt'
_TIMEOUT_S    = 15
_MAX_RETRIES  = 2
_RETRY_WAIT_S = 2


class Command(BaseCommand):
    help = (
        'Lädt CMT-Spielerbilder lokal. '
        'Standard: Dry-Run. --apply lädt herunter.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Bilder herunterladen und player_image_cached_path setzen.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Bereits gecachte Bilder neu herunterladen.',
        )
        parser.add_argument(
            '--db', metavar='SLUG', default='',
            help='Nur Profile mit diesem db_slug verarbeiten.',
        )

    def handle(self, *args, **options):
        from django.conf import settings as _conf

        apply   = options['apply']
        force   = options['force']
        db_slug = options['db'].strip()
        now     = timezone.now()

        mode = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(self.style.WARNING(
            f'cache_cmt_player_images [{mode}]'
            + (f'  db={db_slug}' if db_slug else '')
            + ('  --force' if force else '')
        ))

        media_dir = os.path.join(_conf.MEDIA_ROOT, _MEDIA_SUBDIR)
        if apply:
            os.makedirs(media_dir, exist_ok=True)

        qs = PlayerCMTProfile.objects.select_related('player').exclude(player_image_url='')
        if db_slug:
            qs = qs.filter(db_slug=db_slug)
        if not force:
            qs = qs.filter(player_image_cached_path='')

        total = qs.count()
        self.stdout.write(f'Bilder zu laden: {total}')

        cached = skipped = failed = 0

        for prof in qs.iterator(chunk_size=50):
            cmt_id     = prof.cmt_player_id or str(prof.player_id)
            filename   = f'{cmt_id}.png'
            rel_path   = f'{_MEDIA_SUBDIR}/{filename}'
            dest_path  = os.path.join(media_dir, filename) if apply else ''
            player_name = getattr(prof.player, 'full_name', f'ID {prof.player_id}')

            if not apply:
                self.stdout.write(f'  (dry) {player_name}: {prof.player_image_url} → {rel_path}')
                cached += 1
                continue

            success = False
            for attempt in range(1, _MAX_RETRIES + 2):
                try:
                    resp = requests.get(
                        prof.player_image_url,
                        timeout=_TIMEOUT_S,
                        headers={'User-Agent': 'Websoccer/1.0'},
                    )
                    if resp.status_code == 200:
                        with open(dest_path, 'wb') as fh:
                            fh.write(resp.content)
                        success = True
                        break
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'  WARN {player_name}: HTTP {resp.status_code} — {prof.player_image_url}'
                        ))
                        break
                except requests.RequestException as exc:
                    if attempt <= _MAX_RETRIES:
                        time.sleep(_RETRY_WAIT_S)
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'  WARN {player_name}: Download fehlgeschlagen — {exc}'
                        ))

            if success:
                prof.player_image_cached_path = rel_path
                prof.last_imported_at = now
                prof.save(update_fields=['player_image_cached_path', 'last_imported_at'])
                self.stdout.write(f'  ✓ {player_name} → {rel_path}')
                cached += 1
            else:
                failed += 1

        self.stdout.write('')
        result_parts = [f'{cached} {"gecacht" if apply else "würden gecacht"}']
        if skipped:
            result_parts.append(f'{skipped} übersprungen')
        if failed:
            result_parts.append(f'{failed} fehlgeschlagen')
        self.stdout.write(self.style.SUCCESS('Ergebnis: ' + ', '.join(result_parts)))
        if not apply:
            self.stdout.write(
                self.style.WARNING('Dry-Run — keine Downloads. Mit --apply starten.')
            )
