"""Zentrale Asset-URL-Bausteine für die neue Live-Struktur (/assets/).

Alle Funktionen bauen reine URL-Strings aus settings.ASSETS_BASE_URL —
kein Dateisystem-Check, kein {% static %}. Fehlende Bilder werden
client-seitig per onerror-Fallback abgefangen.

Struktur (live via nginx unter /assets/, auf Replit unter /static/assets/):
    players/face_{fm_inside_id}.png
    clubs/logos/{fm_inside_id}_club.png
    clubs/stadiums/  clubs/cities/  clubs/jerseys/   (noch leer)
    trophies/{trophy_id}.png
    flags/  competitions/  avatars/  backgrounds/  icons/  (noch leer)
"""

import os as _os
from django.conf import settings


def assets_root():
    """Dateisystem-Pfad für Asset-Uploads (Creator-Mode schreibt hierhin).

    Entspricht ASSETS_BASE_URL auf dem Dateisystem:
      Lokal  → <BASE_DIR>/game/static/assets/
      Server → /var/www/assets  (via ASSETS_ROOT env-var)
    """
    root = getattr(settings, 'ASSETS_ROOT', None)
    if root:
        return str(root).rstrip('/')
    return _os.path.join(
        _os.path.dirname(_os.path.dirname(__file__)), 'game', 'static', 'assets'
    )


def assets_base_url():
    base = getattr(settings, 'ASSETS_BASE_URL', '/static/assets/')
    if not base.endswith('/'):
        base += '/'
    return base


def asset_url(category, filename):
    """Generische URL: asset_url('clubs/logos', '915_club.png')."""
    if not filename:
        return ''
    return f"{assets_base_url()}{category.strip('/')}/{filename}"


def default_player_url():
    """URL für das zentrale Default-Spielerbild (kein fm_inside_id)."""
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
    return asset_url('clubs/stadiums', f'{fm_inside_id}_stadium.png')


def club_city_url(fm_inside_id):
    if not fm_inside_id:
        return ''
    return asset_url('clubs/cities', f'{fm_inside_id}_city.png')


def club_jersey_url(fm_inside_id, kit='home'):
    if not fm_inside_id:
        return ''
    return asset_url('clubs/jerseys', f'{fm_inside_id}_{kit}.png')


def trophy_url(trophy_id):
    if not trophy_id:
        return ''
    clean_id = str(trophy_id).removesuffix('.png')
    return f'https://playwebsoccer.de/assets/trophies/{clean_id}.png'


def flag_url(code):
    if not code:
        return ''
    return asset_url('flags', f'{code}.png')


def competition_url(competition_id):
    if not competition_id:
        return ''
    clean_id = str(competition_id).removesuffix('_comp.png').removesuffix('.png')
    return f'https://playwebsoccer.de/assets/competitions/{clean_id}_comp.png'


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
