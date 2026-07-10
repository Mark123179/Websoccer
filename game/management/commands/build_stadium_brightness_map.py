"""
Berechnet für alle Stadionbilder (Vereinsfotos + Fallback) eine
Ziel-Helligkeits-Korrektur und persistiert sie als JSON, damit die
Management-Hub-Kachel "Stadion" unabhängig vom hinterlegten Vereinsfoto
gleich hell/beleuchtet wirkt wie die übrigen Kacheln.

Aufruf: python manage.py build_stadium_brightness_map
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from game.stadium_brightness import compute_factor_from_luminance, BRIGHTNESS_MAP_PATH

try:
    from PIL import Image
except ImportError:
    Image = None


STATIC_ROOT_CANDIDATES = [
    os.path.join(settings.BASE_DIR, 'game', 'static'),
]

STADIUM_SUBPATHS = [
    'game/images/stadiums/germany',
]

EXTRA_STATIC_RELPATHS = [
    'game/images/backgrounds/stadium-hero.jpg',
]

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')


def _resolve_abs_path(static_rel_path):
    for root in STATIC_ROOT_CANDIDATES:
        candidate = os.path.join(root, *static_rel_path.split('/'))
        if os.path.exists(candidate):
            return candidate
    return None


class Command(BaseCommand):
    help = 'Berechnet Helligkeits-Normalisierungsfaktoren für Stadion-Kachelbilder.'

    def handle(self, *args, **options):
        if Image is None:
            self.stderr.write(self.style.ERROR('Pillow ist nicht installiert.'))
            return

        static_root = STATIC_ROOT_CANDIDATES[0]
        result = {}

        static_rel_paths = list(EXTRA_STATIC_RELPATHS)
        for subpath in STADIUM_SUBPATHS:
            abs_dir = os.path.join(static_root, *subpath.split('/'))
            if not os.path.isdir(abs_dir):
                continue
            for fname in sorted(os.listdir(abs_dir)):
                if fname.lower().endswith(IMAGE_EXTS):
                    static_rel_paths.append(f'{subpath}/{fname}')

        for rel_path in static_rel_paths:
            abs_path = _resolve_abs_path(rel_path)
            if not abs_path or not os.path.exists(abs_path):
                continue
            try:
                img = Image.open(abs_path).convert('L')
                img_small = img.resize((64, 64))
                pixels = list(img_small.getdata())
                luminance = sum(pixels) / len(pixels)
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f'Übersprungen ({rel_path}): {exc}'))
                continue

            factor = compute_factor_from_luminance(luminance)
            result[rel_path] = {
                'luminance': round(luminance, 1),
                'factor': factor,
            }

        os.makedirs(os.path.dirname(BRIGHTNESS_MAP_PATH), exist_ok=True)
        with open(BRIGHTNESS_MAP_PATH, 'w', encoding='utf-8') as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)

        self.stdout.write(self.style.SUCCESS(
            f'{len(result)} Stadionbilder analysiert, Map gespeichert unter {BRIGHTNESS_MAP_PATH}'
        ))
