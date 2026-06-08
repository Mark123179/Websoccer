from decimal import Decimal

from django.urls import reverse

from .club_profile_highlights import CURRENT_SEASON, build_highlights, compact_money
from .competition_assets import competition_logo_static_path
from .fixture_display import (
    FixtureDisplay,
    get_form_rows,
    get_last_fixture,
    get_next_fixture,
)
from .models import (
    COUNTRY_FLAG_ASSETS,
    Club,
    ClubProfileMatch,
    GameSeasonState,
    LeagueStandings,
)
from .player_assets import get_cached_trophy_static_path


def build_club_profile_context(club):
    profile = build_club_profile_view_model(club)

    return {
        'club': club,
        'profile': profile,
        'opponent_club': profile['opponentClub'],
    }


def build_club_profile_view_model(club, season=CURRENT_SEASON):
    players = list(
        club.player_set.select_related('strength_profile').order_by(
            '-market_value',
            'last_name',
            'first_name',
        )
    )
    opponent_club = find_profile_opponent(club)
    public_profile = get_public_profile(club)
    links = build_links(club)

    return {
        'club': build_club_identity(club, players),
        'links': links,
        'opponentClub': opponent_club,
        'nextMatch': build_match(club, opponent_club, ClubProfileMatch.KIND_NEXT, links),
        'lastMatch': build_match(club, opponent_club, ClubProfileMatch.KIND_LAST, links),
        'table': build_table(club, opponent_club),
        'trophyPages': chunk_list(build_trophies(club), 4),
        'proHighlights': build_highlights(club, players, season, is_youth=False),
        'youthHighlights': build_highlights(club, players, season, is_youth=True),
        'stadium': build_stadium(public_profile),
        'facilities': build_facilities(club),
        'city': build_city(public_profile, club),
        'kits': build_kits(club),
        'partnerClub': build_partner_club(public_profile),
        'news': build_news(club),
    }


def build_links(club):
    if club.league_id:
        full_table_url = reverse('league_detail', kwargs={'league_id': club.league_id})
    else:
        full_table_url = reverse('club_table', kwargs={'club_id': club.id})
    return {
        'professionalSquadUrl': reverse('club_professional_squad', kwargs={'club_id': club.id}),
        'youthSquadUrl': reverse('club_youth_squad', kwargs={'club_id': club.id}),
        'fullTableUrl': full_table_url,
        'newsUrl': reverse('club_news', kwargs={'club_id': club.id}),
        'profileUrl': reverse('club_detail', kwargs={'club_id': club.id}),
    }


def build_club_identity(club, players):
    league_name = club.league.name if club.league else 'Liga'
    country_name = club.league.country if club.league else 'Deutschland'
    pro_players = [player for player in players if player.age and player.age > 21]
    youth_players = [player for player in players if player.age and player.age <= 21]
    total_market_value = sum(
        Decimal(player.market_value or 0)
        for player in players
    )

    return {
        'id': str(club.id),
        'name': club.name,
        'shortName': club.short_name,
        'countryName': country_name,
        'countryFlagUrl': country_flag_static_path(country_name),
        'crestUrl': club.crest_static_path,
        'league': {
            'id': str(club.league_id or ''),
            'name': league_name,
            'logoUrl': competition_logo_static_path(league_name),
        },
        'clubValueFormatted': compact_money(total_market_value),
        'averageProAgeLabel': average_age_label(pro_players),
        'averageYouthAgeLabel': average_age_label(youth_players),
        'proPlayerCount': len(pro_players),
        'youthPlayerCount': len(youth_players),
        'recentForm': [r['label'] for r in get_form_rows(club, n=5)],
    }


def find_profile_opponent(club):
    match = club.public_profile_matches.filter(
        kind=ClubProfileMatch.KIND_NEXT,
    ).select_related('home_club', 'away_club').first()
    if match:
        for candidate in [match.home_club, match.away_club]:
            if candidate and candidate.id != club.id:
                return candidate

    return None


def get_public_profile(club):
    try:
        return club.public_profile
    except Exception:
        return None


def build_match(club, opponent_club, kind, links):
    # Prefer real SeasonFixture data; fall back to ClubProfileMatch if no fixture found
    if kind == ClubProfileMatch.KIND_NEXT:
        fixture = get_next_fixture(club)
    else:
        fixture = get_last_fixture(club)

    if fixture:
        home_club = fixture.home_club or club
        away_club = fixture.away_club or opponent_club or club
        is_home = fixture.home_club_id == club.pk
        disp = FixtureDisplay(fixture, club)
        base = {
            'id': str(fixture.id),
            'competitionName': fixture.league.name if fixture.league else 'Liga',
            'ntNationality': None,
            'competitionLogoUrl': competition_logo_static_path(
                fixture.league.name if fixture.league else ''
            ),
            'matchdayLabel': f'{fixture.matchday}. Spieltag' if fixture.matchday else '',
            'homeClub': club_stub(home_club),
            'awayClub': club_stub(away_club),
            'backgroundImageUrl': stadium_image_for(home_club),
        }
        if kind == ClubProfileMatch.KIND_NEXT:
            return {
                **base,
                'dateLabel': disp.date_label,
                'timeLabel': disp.time_label,
                'stadiumName': disp.stadium_name or stadium_name_for(home_club),
                'previewUrl': reverse('club_match_preview', kwargs={'club_id': club.id}),
            }
        rl = disp.result_label
        return {
            **base,
            'homeGoals': fixture.home_goals if fixture.home_goals is not None else 0,
            'awayGoals': fixture.away_goals if fixture.away_goals is not None else 0,
            'resultLabel': rl,
            'resultTone': disp.result_tone,
            'reportUrl': reverse('club_match_report', kwargs={'club_id': club.id}),
            'scorers': [],
        }

    # Fallback: try legacy ClubProfileMatch
    match = club.public_profile_matches.filter(kind=kind).select_related(
        'home_club', 'away_club',
    ).order_by('-id').first()

    if match:
        home_club = match.home_club or club
        away_club = match.away_club or opponent_club or club
        base = {
            'id': str(match.id),
            'competitionName': match.competition_name,
            'ntNationality': match.nt_nationality,
            'competitionLogoUrl': competition_logo_static_path(match.competition_name, match.nt_nationality),
            'matchdayLabel': match.matchday_label,
            'homeClub': club_stub(home_club),
            'awayClub': club_stub(away_club),
            'backgroundImageUrl': stadium_image_for(home_club),
        }
        if kind == ClubProfileMatch.KIND_NEXT:
            return {
                **base,
                'dateLabel': match.date_label,
                'timeLabel': match.time_label,
                'stadiumName': match.stadium_name,
                'previewUrl': reverse('club_match_preview', kwargs={'club_id': club.id}),
            }
        return {
            **base,
            'homeGoals': match.home_goals if match.home_goals is not None else 0,
            'awayGoals': match.away_goals if match.away_goals is not None else 0,
            'resultLabel': match.result_label or 'UNENTSCHIEDEN',
            'resultTone': result_tone(match.result_label),
            'reportUrl': reverse('club_match_report', kwargs={'club_id': club.id}),
            'scorers': match.scorers[:5],
        }

    # Final fallback: empty state only for next match; last match returns None (no data yet)
    if kind == ClubProfileMatch.KIND_NEXT:
        return {
            'id': 'next-fallback',
            'competitionName': club.league.name if club.league else 'Liga',
            'matchdayLabel': 'Nächste Partie',
            'dateLabel': 'Noch offen',
            'timeLabel': '',
            'stadiumName': stadium_name_for(club),
            'homeClub': club_stub(club),
            'awayClub': club_stub(opponent_club) if opponent_club else empty_club_stub(),
            'backgroundImageUrl': stadium_image_for(club),
            'previewUrl': reverse('club_match_preview', kwargs={'club_id': club.id}),
        }
    return None


def _current_season_key():
    """Gibt den aktuellen Saison-Schlüssel als String zurück (z. B. '0', '1')."""
    try:
        state = GameSeasonState.objects.only('current_season').first()
        return str(state.current_season) if state else '0'
    except Exception:
        return '0'


def build_table(club, opponent_club):
    """Baut die kompakte Ligatabellen-Vorschau für ein Vereinsprofil.

    Zeigt bis zu 7 Zeilen aus den echten LeagueStandings, zentriert
    um die Position des aktuellen Vereins.  Existieren noch keine
    Standings, wird ein leeres Label zurückgegeben.
    """
    if not club.league_id:
        return []

    season = _current_season_key()
    all_standings = list(
        LeagueStandings.objects
        .filter(league_id=club.league_id, season=season)
        .select_related('club')
        .order_by('position', '-points', 'club__name')
    )

    if not all_standings:
        return []

    # Eigene Position finden
    club_pos = None
    for s in all_standings:
        if s.club_id == club.id:
            club_pos = s.position
            break

    total = len(all_standings)
    window = 7

    if club_pos is None:
        # Verein nicht in Tabelle — einfach Top-7
        slice_start = 0
    else:
        # Fenster so wählen, dass der Verein möglichst mittig liegt
        half = window // 2
        slice_start = max(0, club_pos - 1 - half)
        slice_start = min(slice_start, max(0, total - window))

    visible = all_standings[slice_start: slice_start + window]

    rows = []
    for s in visible:
        diff = s.goals_for - s.goals_against
        diff_str = f'+{diff}' if diff > 0 else str(diff)
        rows.append({
            'position': s.position,
            'clubId': str(s.club_id),
            'clubName': s.club.short_name or s.club.name,
            'clubCrestUrl': s.club.crest_static_path,
            'clubProfileUrl': reverse('club_detail', kwargs={'club_id': s.club_id}),
            'played': s.played,
            'goalDifference': diff_str,
            'points': s.points,
            'isCurrentClub': s.club_id == club.id,
        })

    return rows


def build_trophies(club):
    trophies = [
        {
            'competitionName': trophy.competition_name,
            'count': trophy.count,
            'trophyImageUrl': trophy.trophy_static_path,
        }
        for trophy in club.public_trophies.all()
    ]
    if trophies:
        return trophies

    fallback = [
        ('Bundesliga', 33, '22'),
        ('DFB-Pokal', 20, '1301410'),
        ('Champions League', 6, '1301394'),
        ('Supercup', 10, '1301397'),
        ('Klub-WM', 2, 'international cup 1'),
    ]
    return [
        {
            'competitionName': competition_name,
            'count': count,
            'trophyImageUrl': get_cached_trophy_static_path(trophy_asset_id),
        }
        for competition_name, count, trophy_asset_id in fallback
    ]


def build_facilities(club):
    _LABELS = [
        ('nlz_level',      'Nachwuchsleistungszentrum', 'NLZ'),
        ('medizin_level',  'Medizinische Abteilung',    'Medizin'),
        ('training_level', 'Trainingsgelände',           'Training'),
        ('office_level',   'Geschäftsstelle',            'Büro'),
    ]
    try:
        stadium = club.stadium
    except Exception:
        stadium = None

    result = []
    for attr, full_label, short_label in _LABELS:
        level = getattr(stadium, attr, 0) if stadium else 0
        result.append({
            'fullLabel': full_label,
            'shortLabel': short_label,
            'level': level,
        })
    return result


def build_stadium(public_profile):
    capacity = getattr(public_profile, 'stadium_capacity', 0) or 0
    attendance = getattr(public_profile, 'average_attendance', 0) or 0
    utilization = round((attendance / capacity) * 100) if capacity and attendance else None

    return {
        'name': getattr(public_profile, 'stadium_name', '') or 'Stadion nicht hinterlegt',
        'imageUrl': (
            getattr(public_profile, 'stadium_image_static_path', '')
            or 'game/images/backgrounds/profile-pitch-stadium.svg'
        ),
        'capacityFormatted': format_number(capacity) if capacity else '-',
        'averageAttendanceFormatted': format_number(attendance) if attendance else '-',
        'utilizationFormatted': f'{utilization}%' if utilization else '-',
    }


def build_city(public_profile, club):
    country_name = (
        getattr(public_profile, 'city_country', '')
        or (club.league.country if club.league else 'Deutschland')
    )
    return {
        'name': getattr(public_profile, 'city_name', '') or 'Stadt nicht hinterlegt',
        'countryName': country_name,
        'imageUrl': (
            getattr(public_profile, 'city_image_static_path', '')
            or city_static_path(club)
            or 'game/images/backgrounds/overview/overview-navigation.png'
        ),
    }


def build_kits(club):
    by_label = {item['label'].lower(): item['path'] for item in club.kit_static_paths}
    return {
        'homeImageUrl': by_label.get('heim', ''),
        'awayImageUrl': by_label.get('auswärts', ''),
        'thirdImageUrl': by_label.get('third', ''),
    }


def build_partner_club(public_profile):
    partner = getattr(public_profile, 'partner_club', None)
    if not partner:
        return None

    return {
        'id': str(partner.id),
        'name': partner.name,
        'leagueName': partner.league.name if partner.league else 'Liga',
        'countryName': partner.league.country if partner.league else 'Deutschland',
        'crestUrl': partner.crest_static_path,
        'profileUrl': reverse('club_detail', kwargs={'club_id': partner.id}),
    }


def build_news(club):
    news = list(club.public_news.all()[:3])
    if news:
        return [
            {
                'id': str(item.id),
                'title': item.title,
                'dateLabel': item.published_at.strftime('%d.%m.%Y'),
                'thumbnailUrl': item.thumbnail_static_path,
                'url': reverse('club_news_detail', kwargs={
                    'club_id': club.id,
                    'news_id': item.id,
                }),
            }
            for item in news
        ]

    return [
        {
            'id': f'fallback-{index}',
            'title': title,
            'dateLabel': date_label,
            'thumbnailUrl': club.crest_static_path,
            'url': reverse('club_news', kwargs={'club_id': club.id}),
        }
        for index, (title, date_label) in enumerate([
            ('Topspieler führt die Formkurve an', 'Heute'),
            ('Jugendtalent trainiert bei den Profis', 'Gestern'),
            ('Stadion meldet starke Auslastung', 'Vor 2 Tagen'),
        ])
    ]


def club_stub(club):
    return {
        'id': str(club.id),
        'name': club.name,
        'shortName': club.short_name,
        'crestUrl': club.crest_static_path,
        'profileUrl': reverse('club_detail', kwargs={'club_id': club.id}),
    }


def empty_club_stub():
    return {
        'id': '',
        'name': 'Noch offen',
        'shortName': 'TBD',
        'crestUrl': '',
    }


def average_age_label(players):
    ages = [player.age for player in players if player.age]
    if not ages:
        return ''
    return f'{sum(ages) / len(ages):.1f}'.replace('.', ',')


def country_flag_static_path(country_name):
    asset = COUNTRY_FLAG_ASSETS.get(country_name)
    if not asset:
        return ''
    code = asset.get('code', '')
    if not code:
        return ''
    return f"https://flagcdn.com/{code.lower()}.svg"


def city_static_path(club):
    if not club or not club.fm_inside_id:
        return ''
    return f'game/images/city/{club.fm_inside_id}.jpg'


def stadium_name_for(club):
    profile = get_public_profile(club)
    return getattr(profile, 'stadium_name', '') or 'Websoccer Arena'


def stadium_image_for(club):
    profile = get_public_profile(club)
    return (
        getattr(profile, 'stadium_image_static_path', '')
        or 'game/images/backgrounds/profile-pitch-stadium.svg'
    )


def result_tone(result_label):
    if result_label == 'SIEG':
        return 'win'
    if result_label == 'NIEDERLAGE':
        return 'loss'
    return 'draw'


def format_number(value):
    return f'{int(value):,}'.replace(',', '.')


def chunk_list(items, size):
    if not items:
        return [[None] * size]
    return [
        (items[index:index + size] + [None] * size)[:size]
        for index in range(0, len(items), size)
    ]
