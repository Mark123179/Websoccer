from django import template

from game import asset_urls as _assets

register = template.Library()


@register.simple_tag
def asset_url(category, filename):
    return _assets.asset_url(category, filename)


@register.filter
def player_face_url(fm_inside_id):
    return _assets.player_face_url(fm_inside_id)


@register.filter
def club_logo_url(fm_inside_id):
    return _assets.club_logo_url(fm_inside_id)


@register.filter
def trophy_url(trophy_id):
    return _assets.trophy_url(trophy_id)
