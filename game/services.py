"""
game.services — shared business-logic helpers.

These functions are the single authoritative entry-points for any operation
that spans multiple models.  Views, admin actions and signals call these
functions; they never duplicate the logic themselves.
"""

from datetime import date as _date, timedelta

from django.db import transaction


def record_club_assignment(manager_profile, club, assignment_date=None):
    """Record that *manager_profile* takes over *club* on *assignment_date*.

    Side-effects (all atomic):
    1. The manager's current open ManagerCareerStation (if any) is closed the
       day before *assignment_date*.
    2. Any club previously managed by this manager is released (managed_by=None).
    3. *club.managed_by* is set to *manager_profile*.
    4. A new ManagerCareerStation is created with city/country copied directly
       from *club.public_profile* — no manual text input, no typos.

    Idempotent: calling twice with the same club on the same date does nothing
    harmful (the second call finds an already-open station and just updates the
    order).
    """
    from django.db.models import Max
    from .models import ManagerCareerStation, Club

    if assignment_date is None:
        assignment_date = _date.today()

    with transaction.atomic():
        # If the club already has a different manager, close that incumbent's
        # open station before displacing them. This ensures the outgoing manager
        # always gets a correct end date even when replaced without a formal
        # departure step.
        if club.managed_by_id and club.managed_by_id != manager_profile.pk:
            incumbent = club.managed_by
            ManagerCareerStation.objects.filter(
                manager=incumbent, ended_at__isnull=True
            ).update(ended_at=assignment_date - timedelta(days=1))
            # Release the club from the incumbent's record
            Club.objects.filter(managed_by=incumbent).update(managed_by=None)
            # Refresh the club instance so the FK is cleared before we write it again
            club.refresh_from_db(fields=['managed_by'])

        # Close any open station for the NEW manager (handles club-to-club moves)
        open_qs = ManagerCareerStation.objects.filter(
            manager=manager_profile, ended_at__isnull=True
        )
        if open_qs.exists():
            open_qs.update(ended_at=assignment_date - timedelta(days=1))

        # Release any other club this manager previously held
        Club.objects.filter(managed_by=manager_profile).update(managed_by=None)

        # Assign
        club.managed_by = manager_profile
        club.save(update_fields=['managed_by'])

        # Pull city/country from ClubPublicProfile (authoritative source)
        try:
            prof = club.public_profile
            city_name = (prof.city_name or '').strip() or club.name
            city_country = (prof.city_country or '').strip()
        except Exception:
            city_name = club.name
            city_country = ''

        max_order = (
            ManagerCareerStation.objects.filter(manager=manager_profile)
            .aggregate(m=Max('order'))['m'] or 0
        )

        ManagerCareerStation.objects.create(
            manager=manager_profile,
            club=club,
            city_name=city_name,
            city_country=city_country,
            started_at=assignment_date,
            order=max_order + 1,
        )


def record_club_departure(manager_profile, departure_date=None):
    """Record that *manager_profile* leaves their current club on *departure_date*.

    Side-effects (all atomic):
    1. All open ManagerCareerStations for this manager get ended_at = departure_date.
    2. The club whose managed_by == manager_profile is released (managed_by=None).
    """
    from .models import ManagerCareerStation, Club

    if departure_date is None:
        departure_date = _date.today()

    with transaction.atomic():
        ManagerCareerStation.objects.filter(
            manager=manager_profile, ended_at__isnull=True
        ).update(ended_at=departure_date)

        Club.objects.filter(managed_by=manager_profile).update(managed_by=None)
