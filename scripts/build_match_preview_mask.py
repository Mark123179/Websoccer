"""Occlude the cards behind the original photograph, without copying its RGB."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'game/static/game/images/match-preview'
REFERENCE_SIZE = (1024, 572)
SUPERSAMPLE = 4


def curved_contour(start, segments):
    """Sample cubic curves in the reference photo's pixel coordinates."""
    points = [start]
    for control1, control2, end in segments:
        origin = points[-1]
        for step in range(1, 33):
            t = step / 32
            points.append(tuple(
                (1-t)**3 * origin[axis]
                + 3*(1-t)**2*t * control1[axis]
                + 3*(1-t)*t*t * control2[axis]
                + t**3 * end[axis]
                for axis in (0, 1)
            ))
    return points


def build():
    chair = curved_contour((0, 464), [
        ((55, 467), (112, 473), (157, 482)),
        ((179, 484), (202, 487), (211, 493)),
        ((216, 498), (216, 513), (214, 527)),
        ((213, 532), (209, 535), (207, 536)),
    ]) + [(214, 541), (214, 572), (193, 572), (192, 545),
          (108, 572), (0, 572)]
    bag = curved_contour((831, 563), [
        ((811, 560), (806, 552), (809, 534)),
        ((811, 516), (813, 497), (816, 476)),
        ((817, 467), (824, 463), (838, 461)),
        ((848, 459), (859, 455), (867, 453)),
        ((874, 451), (881, 455), (895, 456)),
        ((906, 455), (912, 452), (918, 450)),
    ]) + [(933, 451), (949, 447), (957, 447), (960, 442),
          (964, 440), (973, 445), (981, 450), (993, 456),
          (1005, 460), (1024, 464), (1024, 572), (855, 572)]

    size = tuple(value * SUPERSAMPLE for value in REFERENCE_SIZE)
    alpha = Image.new('L', size, 255)
    for contour, feather in [(chair, 2.0), (bag, 0.65)]:
        coverage = Image.new('L', size, 0)
        ImageDraw.Draw(coverage).polygon(
            [(round(x*SUPERSAMPLE), round(y*SUPERSAMPLE)) for x, y in contour],
            fill=255,
        )
        coverage = coverage.filter(ImageFilter.GaussianBlur(feather*SUPERSAMPLE))
        alpha.paste(0, mask=coverage)

    with Image.open(ASSETS / 'locker-room.png') as source:
        target_size = source.size
    alpha = alpha.resize(target_size, Image.Resampling.LANCZOS)
    mask = Image.new('RGBA', target_size, (255, 255, 255, 255))
    mask.putalpha(alpha)
    mask.save(ASSETS / 'panel-mask.png', optimize=True)


if __name__ == '__main__':
    build()