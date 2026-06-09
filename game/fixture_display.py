"""
Hilfsfunktionen um SeasonFixture-Daten für Templates aufzubereiten.
"""
from django.db.models import Q
from django.urls import reverse


_MONTHS_DE = [
    '', 'Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
    'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez',
]


def _format_date(d):
    if not d:
        return 'Noch offen'
    return f'{d.day}. {_MONTHS_DE[d.month]} {d.year}'


def _format_time(t):
    if not t:
        return ''
    return f'{t.strftime("%H:%M")} Uhr'


def _result_label(my_goals, opp_goals):
    if my_goals is None or opp_goals is None:
        return 'UNENTSCHIEDEN'
    if my_goals > opp_goals:
        return 'SIEG'
    if my_goals < opp_goals:
        return 'NIEDERLAGE'
    return 'UNENTSCHIEDEN'


def _result_tone(label):
    if label == 'SIEG':
        return 'win'
    if label == 'NIEDERLAGE':
        return 'loss'
    return 'draw'


def get_next_fixture(club):
    """Nächstes ungespieltees Fixture für den Verein."""
    from .models import SeasonFixture
    return (
        SeasonFixture.objects
        .filter(Q(home_club=club) | Q(away_club=club), is_played=False)
        .select_related('home_club', 'away_club', 'league')
        .order_by('scheduled_date', 'id')
        .first()
    )


def get_last_fixture(club):
    """Zuletzt gespieltes Fixture für den Verein."""
    from .models import SeasonFixture
    return (
        SeasonFixture.objects
        .filter(Q(home_club=club) | Q(away_club=club), is_played=True)
        .select_related('home_club', 'away_club', 'league')
        .order_by('-scheduled_date', '-id')
        .first()
    )


def get_form_rows(club, n=5):
    """Letzte n gespielte Spiele als Form-Liste [{'label','tone','score'}, ...]."""
    from .models import SeasonFixture
    fixtures = list(
        SeasonFixture.objects
        .filter(Q(home_club=club) | Q(away_club=club), is_played=True)
        .select_related('home_club', 'away_club')
        .order_by('-scheduled_date', '-id')[:n]
    )
    result = []
    for f in reversed(fixtures):
        is_home = f.home_club_id == club.pk
        my_goals = f.home_goals if is_home else f.away_goals
        opp_goals = f.away_goals if is_home else f.home_goals
        if my_goals is None or opp_goals is None:
            continue
        label_map = {
            'SIEG': 'S', 'NIEDERLAGE': 'N', 'UNENTSCHIEDEN': 'U',
        }
        rl = _result_label(my_goals, opp_goals)
        score = f'{my_goals}:{opp_goals}'
        result.append({
            'label': label_map[rl],
            'tone': _result_tone(rl),
            'score': score,
        })
    return result


def get_form_rows_with_opponents(club, n=5):
    """Form-Liste inkl. Gegnerdaten für Taktik-Header."""
    from django.urls import reverse
    from .models import SeasonFixture
    fixtures = list(
        SeasonFixture.objects
        .filter(Q(home_club=club) | Q(away_club=club), is_played=True)
        .select_related('home_club', 'away_club')
        .order_by('-scheduled_date', '-id')[:n]
    )
    result = []
    for f in reversed(fixtures):
        is_home = f.home_club_id == club.pk
        my_goals = f.home_goals if is_home else f.away_goals
        opp_goals = f.away_goals if is_home else f.home_goals
        opponent = f.away_club if is_home else f.home_club
        if my_goals is None or opp_goals is None:
            continue
        rl = _result_label(my_goals, opp_goals)
        result.append({
            'label': {'SIEG': 'S', 'NIEDERLAGE': 'N', 'UNENTSCHIEDEN': 'U'}[rl],
            'tone': _result_tone(rl),
            'score': f'{my_goals}:{opp_goals}',
            'opponent_name': opponent.name if opponent else 'Gegner',
            'opponent_crest': opponent.crest_static_path if opponent else '',
            'opponent_url': reverse('club_detail', kwargs={'club_id': opponent.id}) if opponent else '#',
        })
    return result


class FixtureDisplay:
    """
    Wrapper um ein SeasonFixture für Template-Attribute
    wie competition_name, date_label, usw.
    """

    def __init__(self, fixture, club):
        self._f = fixture
        self._club = club

    @property
    def competition_name(self):
        return self._f.league.name if self._f.league else 'Liga'

    @property
    def matchday_label(self):
        return f'{self._f.matchday}. Spieltag' if self._f.matchday else ''

    @property
    def date_label(self):
        return _format_date(self._f.scheduled_date)

    @property
    def time_label(self):
        return _format_time(self._f.scheduled_time)

    @property
    def stadium_name(self):
        try:
            return self._f.home_club.stadium.name
        except Exception:
            return ''

    @property
    def home_goals(self):
        return self._f.home_goals

    @property
    def away_goals(self):
        return self._f.away_goals

    @property
    def scorers(self):
        return []

    @property
    def result_label(self):
        is_home = self._f.home_club_id == self._club.pk
        my = self._f.home_goals if is_home else self._f.away_goals
        opp = self._f.away_goals if is_home else self._f.home_goals
        return _result_label(my, opp)

    @property
    def result_tone(self):
        return _result_tone(self.result_label)
