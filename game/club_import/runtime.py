"""Temporary behavior boundary; schema is identical in both modes (N33)."""
from django.conf import settings
from django.db.models import Q


def package_mode():
    return getattr(settings, "IMPORT_PACKAGE_MODE", False)


def image_check_enabled():
    return getattr(settings, "IMPORT_PACKAGE_IMAGE_CHECK_ENABLED", True)


def visible_clubs(queryset=None):
    """Keep the migration-seeded retirement target available to technical code."""
    from game.models import Club
    queryset = Club.objects.all() if queryset is None else queryset
    return queryset.exclude(name__iexact="Karrierende") if package_mode() else queryset


def visible_leagues(queryset=None):
    from game.models import League
    queryset = League.objects.all() if queryset is None else queryset
    return queryset.exclude(name__iexact="Sonderstatus", country="System") if package_mode() else queryset


def ownership_field():
    return "owner_club" if package_mode() else "real_life_club"


def owner(player):
    return getattr(player, ownership_field(), None)


def owner_name(player):
    club = owner(player)
    return club.name if club else (
        player.owner_club_original_name or "—" if package_mode() else "—")


def scouting_condition():
    from game.models import Player
    if not package_mode():
        return Q(club__isnull=True, pool_status=Player.POOL_STATUS_SCOUTABLE)
    return (Q(review_pool=False, import_lock=False, pool_status=Player.POOL_STATUS_SCOUTABLE)
            & (Q(club__import_state="nicht_spielbar")
               | Q(club__isnull=True, loan_club_tm_id__isnull=True)))


def can_scout(player):
    if not package_mode():
        return player.club_id is None and player.pool_status == "scoutable"
    return (not player.review_pool and not player.import_lock
            and player.pool_status == "scoutable"
            and (player.club_id is not None and player.club.import_state == "nicht_spielbar"
                 or player.club_id is None and player.loan_club_tm_id is None))


def match_condition():
    if not package_mode():
        return Q()
    return Q(import_lock=False, review_pool=False, squad_team="first",
             club__import_state="spielbar", strength_profile__isnull=False)


def assign_review_player(player, club, *, team="first", issue=None, user=None):
    """Backend-only controlled assignment; the worklist UI belongs to T3."""
    from django.db import transaction
    from django.utils import timezone
    from game.models import Player
    if not package_mode():
        raise ValueError("Review pool requires package mode.")
    if team not in ("first", "u21"):
        raise ValueError("Invalid team.")
    with transaction.atomic():
        player = Player.objects.select_for_update().get(pk=player.pk)
        if not player.review_pool:
            raise ValueError("Player is not in the review pool.")
        player.club = player.owner_club = club
        player.owner_club_tm_id = club.transfermarkt_id
        player.owner_club_original_name = club.name
        player.loan_club = None
        player.loan_club_tm_id = player.loan_club_original_name = None
        player.loan_until = None
        player.loan_status = "none"
        player.loan_partner_club = None
        player.squad_team = team
        player.review_pool = False
        player.pool_status = ("scoutable" if club.import_state == "nicht_spielbar"
                              and not player.import_lock else "none")
        player._suppress_club_history = True
        player.save()
        if issue:
            issue.resolution_status = "resolved"
            issue.resolved_at = timezone.now()
            issue.resolved_by = user
            issue.save(update_fields=["resolution_status", "resolved_at", "resolved_by"])
        return player
