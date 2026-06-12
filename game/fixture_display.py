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
    """Letzte n gespielte Spiele als Form-Liste [{'label','tone','score'}, ...]
    aus allen Wettbewerben (Liga + Pokal + Freundschaft)."""
    import datetime
    from .models import SeasonFixture, SimulatedMatch

    combined = []

    for f in SeasonFixture.objects.filter(
        Q(home_club=club) | Q(away_club=club), is_played=True
    ).order_by('-scheduled_date', '-id')[:n]:
        is_home = f.home_club_id == club.pk
        my = f.home_goals if is_home else f.away_goals
        op = f.away_goals if is_home else f.home_goals
        if my is None or op is None:
            continue
        combined.append({
            'sort_key': (f.scheduled_date or datetime.date.min, f.id),
            'my': my, 'op': op,
            'score': f'{my}:{op}',
        })

    for m in SimulatedMatch.objects.filter(
        Q(home_club=club) | Q(away_club=club),
        match_type__in=['pokal', 'freundschaft'],
    ).order_by('-simulated_at')[:n]:
        is_home = m.home_club_id == club.pk
        my = m.home_goals if is_home else m.away_goals
        op = m.away_goals if is_home else m.home_goals
        combined.append({
            'sort_key': (m.simulated_at.date(), m.id),
            'my': my, 'op': op,
            'score': f'{my}:{op}',
        })

    combined.sort(key=lambda x: x['sort_key'], reverse=True)
    combined = combined[:n]
    combined.sort(key=lambda x: x['sort_key'])

    label_map = {'SIEG': 'S', 'NIEDERLAGE': 'N', 'UNENTSCHIEDEN': 'U'}
    return [
        {'label': label_map[rl := _result_label(e['my'], e['op'])],
         'tone': _result_tone(rl),
         'score': e['score']}
        for e in combined
    ]


def get_form_rows_with_opponents(club, n=5):
    """Form-Liste inkl. Gegnerdaten für Taktik-Header (alle Wettbewerbe)."""
    import datetime
    from django.urls import reverse
    from .models import SeasonFixture, SimulatedMatch

    combined = []

    for f in SeasonFixture.objects.filter(
        Q(home_club=club) | Q(away_club=club), is_played=True
    ).select_related('home_club', 'away_club').order_by('-scheduled_date', '-id')[:n]:
        is_home = f.home_club_id == club.pk
        my = f.home_goals if is_home else f.away_goals
        op = f.away_goals if is_home else f.home_goals
        opp = f.away_club if is_home else f.home_club
        if my is None or op is None:
            continue
        combined.append({
            'sort_key': (f.scheduled_date or datetime.date.min, f.id),
            'my': my, 'op': op, 'opp': opp,
        })

    for m in SimulatedMatch.objects.filter(
        Q(home_club=club) | Q(away_club=club),
        match_type__in=['pokal', 'freundschaft'],
    ).select_related('home_club', 'away_club').order_by('-simulated_at')[:n]:
        is_home = m.home_club_id == club.pk
        my = m.home_goals if is_home else m.away_goals
        op = m.away_goals if is_home else m.home_goals
        opp = m.away_club if is_home else m.home_club
        combined.append({
            'sort_key': (m.simulated_at.date(), m.id),
            'my': my, 'op': op, 'opp': opp,
        })

    combined.sort(key=lambda x: x['sort_key'], reverse=True)
    combined = combined[:n]
    combined.sort(key=lambda x: x['sort_key'])

    label_map = {'SIEG': 'S', 'NIEDERLAGE': 'N', 'UNENTSCHIEDEN': 'U'}
    result = []
    for e in combined:
        rl = _result_label(e['my'], e['op'])
        opp = e['opp']
        result.append({
            'label': label_map[rl],
            'tone': _result_tone(rl),
            'score': f"{e['my']}:{e['op']}",
            'opponent_name': opp.name if opp else 'Gegner',
            'opponent_crest': opp.crest_static_path if opp else '',
            'opponent_url': reverse('club_detail', kwargs={'club_id': opp.id}) if opp else '#',
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
