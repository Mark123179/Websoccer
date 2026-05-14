from pathlib import Path
import shutil

from django.conf import settings


def _image_paths(player):
    if not player.fm_inside_id or not player.club or not player.club.fm_inside_id:
        return None

    project_root = settings.BASE_DIR.parent
    images_root = project_root / 'Images'
    face_path = images_root / 'Players' / f'face_{player.fm_inside_id}.png'
    kit_path = (
        images_root /
        '2D Kits' /
        f'{player.club.fm_inside_id}_home.png'
    )
    output_dir = (
        settings.BASE_DIR /
        'game' /
        'static' /
        'game' /
        'images' /
        'player_composites'
    )
    output_name = (
        f'{player.fm_inside_id}_{player.club.fm_inside_id}_home.png'
    )

    return face_path, kit_path, output_dir, output_name


def get_cached_profile_portrait_static_path(player):
    paths = _image_paths(player)
    if paths is None:
        return player.portrait_static_path

    face_path, kit_path, output_dir, output_name = paths
    output_path = output_dir / output_name
    static_path = f'game/images/player_composites/{output_name}'

    if not face_path.exists() or not kit_path.exists():
        return player.portrait_static_path

    if output_path.exists():
        output_mtime = output_path.stat().st_mtime
        if (
            output_mtime >= face_path.stat().st_mtime and
            output_mtime >= kit_path.stat().st_mtime
        ):
            return static_path

    try:
        build_profile_portrait(face_path, kit_path, output_path)
    except Exception:
        return player.portrait_static_path

    return static_path if output_path.exists() else player.portrait_static_path


def get_cached_trophy_static_path(trophy_asset_id):
    if not trophy_asset_id:
        return ''

    source_path = _find_trophy_source(trophy_asset_id)
    if source_path is None:
        return ''

    output_dir = (
        settings.BASE_DIR /
        'game' /
        'static' /
        'game' /
        'images' /
        'trophies'
    )
    output_name = f'{_safe_trophy_output_stem(source_path.stem)}.png'
    output_path = output_dir / output_name

    if output_path.exists():
        if output_path.stat().st_mtime >= source_path.stat().st_mtime:
            return f'game/images/trophies/{output_name}'

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, output_path)

    return f'game/images/trophies/{output_name}'


def get_cached_nation_static_path(nation_asset_id):
    if not nation_asset_id:
        return ''

    clean_id = str(nation_asset_id).removesuffix('.png')
    source_path = (
        settings.BASE_DIR.parent /
        'Images' /
        'Logos' /
        'Others' /
        'Federations' /
        f'TCM4_{clean_id}.png'
    )

    if not source_path.exists():
        return ''

    output_dir = (
        settings.BASE_DIR /
        'game' /
        'static' /
        'game' /
        'images' /
        'nations' /
        'federations'
    )
    output_name = f'{clean_id}.png'
    output_path = output_dir / output_name

    if output_path.exists():
        if output_path.stat().st_mtime >= source_path.stat().st_mtime:
            return f'game/images/nations/federations/{output_name}'

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, output_path)

    return f'game/images/nations/federations/{output_name}'


def _find_trophy_source(trophy_asset_id):
    clean_id = str(trophy_asset_id).removesuffix('.png')
    trophies_root = settings.BASE_DIR.parent / 'Images' / 'Trophies'
    direct_path = trophies_root / f'{clean_id}.png'

    if direct_path.exists():
        return direct_path

    symbol_path = settings.BASE_DIR.parent / 'Images' / 'Symbol' / f'{clean_id}.png'
    if symbol_path.exists():
        return symbol_path

    if trophies_root.exists():
        matches = list(trophies_root.rglob(f'{clean_id}.png'))
        if matches:
            return matches[0]

    return None


def _safe_trophy_output_stem(stem):
    from django.utils.text import slugify

    return slugify(stem) or stem


def build_profile_portrait(face_path, kit_path, output_path):
    from PIL import Image

    canvas_size = (520, 680)
    canvas = Image.new('RGBA', canvas_size, (0, 0, 0, 0))

    kit = Image.open(kit_path).convert('RGBA')
    kit = _trim_transparency(kit)
    kit.thumbnail((430, 430), Image.Resampling.LANCZOS)
    kit_x = (canvas_size[0] - kit.width) // 2
    kit_y = 294
    canvas.alpha_composite(kit, (kit_x, kit_y))

    face = Image.open(face_path).convert('RGBA')
    face = _trim_transparency(face)
    face.thumbnail((260, 260), Image.Resampling.LANCZOS)
    face_x = (canvas_size[0] - face.width) // 2
    face_y = 88
    canvas.alpha_composite(face, (face_x, face_y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, 'PNG', optimize=True)


def _trim_transparency(image):
    alpha = image.getchannel('A')
    bbox = alpha.getbbox()
    if not bbox:
        return image

    return image.crop(bbox)
