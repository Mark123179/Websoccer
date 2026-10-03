"""Build the card mask from the approved, static SAM object segmentation."""
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'game/static/game/images/match-preview'


def build():
    with Image.open(ASSETS / 'locker-room.png') as source:
        target_size = source.size
    with Image.open(ASSETS / 'object-mask-sam.png') as objects:
        if objects.size != target_size:
            raise ValueError('SAM segmentation must match the original photo dimensions.')
        alpha = ImageChops.invert(objects.convert('L'))
    mask = Image.new('RGBA', target_size, (255, 255, 255, 255))
    mask.putalpha(alpha)
    mask.save(ASSETS / 'panel-mask-sam.png', optimize=True)


if __name__ == '__main__':
    build()