"""Read-only league table projection, including the initial preparation phase."""
from .models import GameSeasonState, LeagueStandings, SeasonFixture


def display_standings(league, season, queryset=None):
    """Use real standings; before the first season show the registered clubs."""
    if queryset is None:
        queryset = (
            LeagueStandings.objects.filter(league=league, season=str(season))
            .select_related("club")
            .order_by("position", "-points", "club__name")
        )
    rows = list(queryset)
    if rows or str(season) != "0":
        return rows
    state = GameSeasonState.objects.only("is_started").first()
    if state is not None and state.is_started:
        return rows
    if SeasonFixture.objects.filter(league=league, season="0", is_played=True).exists():
        return rows

    from .club_import.runtime import visible_clubs

    return [
        LeagueStandings(league=league, club=club, season="0", position=position)
        for position, club in enumerate(
            visible_clubs().filter(league=league).order_by("name", "pk"), start=1
        )
    ]
