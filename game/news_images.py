"""Read-only card-motif images shared by club-news previews and full articles."""

from django.templatetags.static import static

from .asset_urls import asset_url
from .models import Player


def news_image_url(value):
    """Resolve legacy static paths without freezing the configured asset base."""
    if not isinstance(value, str) or not value.strip():
        return ''
    value = value.strip()
    for prefix in ('/static/assets/', '/assets/', 'assets/'):
        if value.startswith(prefix):
            relative = value[len(prefix):]
            category, separator, filename = relative.rpartition('/')
            return asset_url(category, filename) if separator else ''
    if value.startswith(('/', 'https://', 'http://', 'data:image/')):
        return value
    return static(value)


def _player_id(card):
    value = card.get('pid')
    if isinstance(value, bool):
        return None
    if isinstance(value, int) or (
            isinstance(value, str) and len(value) <= 19
            and value.isascii() and value.isdecimal()):
        value = int(value)
        if 0 < value <= 9223372036854775807:
            return value
    return None


def resolve_news_images(news, club):
    """Return {news_pk: image_url} for articles belonging to ``club``.

    Resolve only the exact saved player, including after a transfer. Batch the
    lookup and never replace a missing player with somebody from today's squad.
    """
    news = list(news)
    cards = {
        item.pk: item.card_data if isinstance(item.card_data, dict) else {}
        for item in news
    }
    player_ids = {
        _player_id(card) for card in cards.values()
        if card.get('motiv') == 'spieler'
    } - {None}
    players = Player.objects.in_bulk(player_ids) if player_ids else {}
    images = {}
    for item in news:
        card = cards[item.pk]
        motif = card.get('motiv')
        if motif == 'wappen':
            image = club.crest_static_path
        elif motif == 'spieler':
            player = players.get(_player_id(card))
            image = player.portrait_url if player else ''
        elif motif == 'eigenes':
            image = card.get('customSrc')
        else:
            image = item.thumbnail_static_path or item.img_path
        images[item.pk] = news_image_url(image)
    return images


def news_article_dicts(news, club, *, externalize_legacy=False):
    """Serialize articles with resolved images, without changing saved card data."""
    news = list(news)
    images = resolve_news_images(news, club)
    articles = []
    for item in news:
        article = dict(item.to_vn_dict(), cardImageUrl=images[item.pk])
        if externalize_legacy:
            from .news_image_storage import externalize_legacy_article
            article = externalize_legacy_article(item, article)
        articles.append(article)
    return articles