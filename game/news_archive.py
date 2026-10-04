"""Bounded, club-scoped archive reads shared by HTML and incremental requests."""
from datetime import date

from django.core import signing
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import Club, ClubNewsItem
from .news_images import news_article_dicts

PAGE_SIZE = 20
CURSOR_SALT = 'club-news-archive'


def archive_query(club):
    return ClubNewsItem.objects.filter(club=club).select_related('published_by')


def archive_page(club, kind, cursor=''):
    if kind not in ('art', 'social'):
        raise ValueError('Ungültige Beitragsart.')
    query = archive_query(club).filter(is_social=(kind == 'social'))
    if cursor:
        try:
            if len(cursor) > 4096:
                raise ValueError
            scope, cursor_kind, day, pk = signing.loads(cursor, salt=CURSOR_SALT)
            if scope != club.pk or cursor_kind != kind:
                raise ValueError
            day = date.fromisoformat(day)
            if type(pk) is not int or not 0 < pk <= 9223372036854775807:
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError, OverflowError):
            raise ValueError('Ungültiger Archiv-Cursor.') from None
        query = query.filter(Q(published_at__lt=day) | Q(published_at=day, pk__lt=pk))
    rows = list(query.order_by('-published_at', '-pk')[:PAGE_SIZE + 1])
    has_more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    next_cursor = ''
    if has_more:
        last = rows[-1]
        next_cursor = signing.dumps(
            [club.pk, kind, last.published_at.isoformat(), last.pk], salt=CURSOR_SALT)
    return {
        'items': news_article_dicts(rows, club, externalize_legacy=True),
        'next_cursor': next_cursor,
    }


@require_GET
def club_news_data(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    article_id = request.GET.get('article')
    if article_id is not None:
        if (not article_id.isascii() or not article_id.isdecimal() or len(article_id) > 19
                or not 0 < int(article_id) <= 9223372036854775807):
            return JsonResponse({'error': 'Ungültige Artikel-ID.'}, status=400)
        item = get_object_or_404(archive_query(club), pk=int(article_id))
        return JsonResponse({'article': news_article_dicts(
            [item], club, externalize_legacy=True)[0]})
    try:
        page = archive_page(club, request.GET.get('kind', 'art'), request.GET.get('cursor', ''))
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse(page)