"""Zentrale Asset-URL-Bausteine.

Produktions-Server (Hetzner): ASSETS_BASE_URL=/assets/ in .env — nginx liefert
/var/www/assets aus.

Replit-Dev (kein ASSETS_BASE_URL in .env): Fallback /static/assets/ — Django
staticfiles serviert game/static/assets/.

Single Source of Truth: settings.ASSETS_BASE_URL (gesetzt in core/settings.py).
Alle URL-Builder lesen diesen Wert zur Laufzeit via _base() — KEINE Modul-Level-
Konstanten, die beim Import eingefroren werden könnten.
"""

import os as _os
from django.conf import settings


def _base() -> str:
    """Liest ASSETS_BASE_URL zur Laufzeit aus settings — nie einfrieren."""
    return getattr(settings, 'ASSETS_BASE_URL', '/static/assets/')


def assets_root():
    """Dateisystem-Pfad für Asset-Uploads (Creator-Mode schreibt hierhin).

    Server → ASSETS_ROOT env-var (z.B. /app/assets)
    Fallback → <BASE_DIR>/game/static/assets/ (Replit-Dev)
    """
    root = getattr(settings, 'ASSETS_ROOT', None)
    if root:
        return str(root).rstrip('/')
    return _os.path.join(
        _os.path.dirname(_os.path.dirname(__file__)), 'game', 'static', 'assets'
    )


def asset_url(category, filename):
    """Generische URL: asset_url('clubs/logos', '915_club.png')."""
    if not filename:
        return ''
    return f"{_base()}{category.strip('/')}/{filename}"


def default_player_url():
    return asset_url('players', 'default_player.png')


def player_face_url(fm_inside_id):
    if not fm_inside_id:
        return ''
    return asset_url('players', f'face_{fm_inside_id}.png')


def club_logo_url(fm_inside_id):
    if not fm_inside_id:
        return ''
    return asset_url('clubs/logos', f'{fm_inside_id}_club.png')


def club_stadium_url(fm_inside_id):
    if not fm_inside_id:
        return ''
    return asset_url('clubs/stadiums', f'{fm_inside_id}_stadium.jpg')


def resolve_stadium_url(static_path):
    """Vollständige URL für ein gespeichertes Stadionbild.

    - Neues Format 'clubs/stadiums/{id}_stadium.jpg' → Asset-URL
    - Altes Format 'game/images/stadiums/...'        → lokale Static-URL (Fallback)
    """
    if not static_path:
        return ''
    if static_path.startswith('clubs/stadiums/'):
        return f'{_base()}{static_path}'
    from django.templatetags.static import static as _static
    return _static(static_path)


def club_city_url(fm_inside_id):
    if not fm_inside_id:
        return ''
    return f'{_base()}clubs/cities/{fm_inside_id}.jpg'


def resolve_city_url(static_path):
    """Vollständige URL für ein gespeichertes Stadtbild.

    - Neues Format 'clubs/cities/{fmid}.jpg' → Asset-URL
    - Altes Format 'game/images/city/...'    → lokale Static-URL (Fallback)
    """
    if not static_path:
        return ''
    if static_path.startswith('clubs/cities/'):
        return f'{_base()}{static_path}'
    from django.templatetags.static import static as _static
    return _static(static_path)


def club_jersey_url(fm_inside_id, kit='home'):
    if not fm_inside_id:
        return ''
    return asset_url('clubs/jerseys', f'{fm_inside_id}_{kit}.png')


def trophy_url(trophy_id):
    if not trophy_id:
        return ''
    clean_id = str(trophy_id).removesuffix('.png')
    return f'{_base()}trophies/{clean_id}.png'


def flag_url(code):
    if not code:
        return ''
    return asset_url('flags', f'{code}.png')


def referee_face_url(fm_uid):
    """Gibt die URL für das Schiedsrichter-Bild zurück.

    Reihenfolge: referees/face_{uid}.png → .jpg → .jpeg
    Prüft ggf. ASSETS_ROOT/referees/ direkt (falls gesetzt).
    Fallback: referee_default.svg.
    """
    if not fm_uid:
        return asset_url('referees', 'referee_default.svg')
    root = getattr(settings, 'ASSETS_ROOT', None)
    if root:
        ref_dir = _os.path.join(str(root).rstrip('/'), 'referees')
        for ext in ('png', 'jpg', 'jpeg'):
            if _os.path.exists(_os.path.join(ref_dir, f'face_{fm_uid}.{ext}')):
                return asset_url('referees', f'face_{fm_uid}.{ext}')
    return asset_url('referees', f'face_{fm_uid}.png')


def competition_url(competition_id):
    if not competition_id:
        return ''
    clean_id = str(competition_id).removesuffix('_comp.png').removesuffix('.png')
    return f'{_base()}competitions/{clean_id}_comp.png'


def federation_url(asset_id):
    """Föderations-Badge eines Verbands (Nationalmannschaft).

    Neue Asset-Struktur (Live-Server): /assets/federations/{id}_federation.png
    Ersetzt die alten statischen Pfade game/images/crests/nt_{id}.png.
    """
    if not asset_id:
        return ''
    return f'{_base()}federations/{asset_id}_federation.png'


def avatar_url(name):
    if not name:
        return ''
    return asset_url('avatars', name)


def background_url(name):
    if not name:
        return ''
    return asset_url('backgrounds', name)


def icon_url(name):
    if not name:
        return ''
    return asset_url('icons', name)
