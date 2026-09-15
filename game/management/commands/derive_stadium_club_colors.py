from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image

from game.models import Club


def _crest_path(club):
    if not club.fm_inside_id:
        return None
    stem = str(club.fm_inside_id)
    candidates = (
        Path(settings.BASE_DIR) / 'game/static/assets/clubs/logos' / f'{stem}_club.png',
        Path(settings.BASE_DIR) / 'game/static/game/images/crests' / f'{stem}.png',
        Path(settings.BASE_DIR) / 'game/static/game/images/crests' / f'{stem}.jpg',
    )
    return next((path for path in candidates if path.is_file()), None)


def _distance(left, right):
    return sum((a - b) ** 2 for a, b in zip(left, right)) ** 0.5


def derive_palette(path):
    with Image.open(path) as source:
        image = source.convert('RGBA')
        image.thumbnail((160, 160))
        colours = Counter()
        for red, green, blue, alpha in image.getdata():
            if alpha < 96:
                continue
            high, low = max(red, green, blue), min(red, green, blue)
            if high < 28 or low > 238 or high - low < 20:
                continue
            quantized = tuple((channel // 24) * 24 + 12 for channel in (red, green, blue))
            colours[quantized] += alpha
    ranked = [colour for colour, _count in colours.most_common(24)]
    if not ranked:
        return None
    primary = ranked[0]
    secondary = next((colour for colour in ranked[1:] if _distance(primary, colour) >= 72), None)
    if secondary is None:
        secondary = (244, 246, 248) if sum(primary) < 420 else (16, 18, 22)
    return tuple('#{:02x}{:02x}{:02x}'.format(*colour) for colour in (primary, secondary))


class Command(BaseCommand):
    help = (
        'Leitet fehlende Stadion-Standardfarben einmalig aus lokalen Vereinswappen ab. '
        'Vorhandene oder administrativ korrigierte Farben werden nicht überschrieben.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--club-id', action='append', type=int, dest='club_ids')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        clubs = Club.objects.filter(stadium__isnull=False).order_by('pk')
        if options['club_ids']:
            clubs = clubs.filter(pk__in=options['club_ids'])
        updated = skipped = missing = 0
        for club in clubs:
            if club.color_primary or club.color_secondary:
                skipped += 1
                continue
            path = _crest_path(club)
            palette = derive_palette(path) if path else None
            if not palette:
                missing += 1
                continue
            club.color_primary, club.color_secondary = palette
            if not options['dry_run']:
                club.save(update_fields=['color_primary', 'color_secondary'])
            updated += 1
            self.stdout.write(f'{club.pk}: {club.name} → {palette[0]} / {palette[1]}')
        self.stdout.write(self.style.SUCCESS(
            f'Farben: {updated} abgeleitet, {skipped} beibehalten, {missing} ohne geeignetes Wappen.'
        ))