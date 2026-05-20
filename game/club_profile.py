from decimal import Decimal

from django.urls import reverse

from .club_profile_highlights import CURRENT_SEASON, build_highlights, compact_money
from .models import (
    COUNTRY_FLAG_ASSETS,
    Club,
    ClubProfileMatch,
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
        'city': build_city(public_profile, club),
        'kits': build_kits(club),
        'partnerClub': build_partner_club(public_profile),
        'news': build_news(club),
    }


def build_links(club):
    return {
        'professionalSquadUrl': reverse('club_professional_squad', kwargs={'club_id': club.id}),
        'youthSquadUrl': reverse('club_youth_squad', kwargs={'club_id': club.id}),
        'fullTableUrl': reverse('club_table', kwargs={'club_id': club.id}),
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
        'recentForm': ['S', 'S', 'U', 'S', 'N'],
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
    match = club.public_profile_matches.filter(kind=kind).select_related(
        'home_club',
        'away_club',
    ).order_by('-id').first()

    if match:
        home_club = match.home_club or club
        away_club = match.away_club or opponent_club or club
        base = {
            'id': str(match.id),
            'competitionName': match.competition_name,
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

    opponent = opponent_club
    if kind == ClubProfileMatch.KIND_NEXT:
        return {
            'id': 'next-fallback',
            'competitionName': club.league.name if club.league else 'Liga',
            'matchdayLabel': 'Nächste Partie',
            'dateLabel': 'Noch offen',
            'timeLabel': '',
            'stadiumName': stadium_name_for(club),
            'homeClub': club_stub(club),
            'awayClub': club_stub(opponent) if opponent else empty_club_stub(),
            'backgroundImageUrl': stadium_image_for(club),
            'previewUrl': reverse('club_match_preview', kwargs={'club_id': club.id}),
        }

    return {
        'id': 'last-fallback',
        'competitionName': club.league.name if club.league else 'Liga',
        'matchdayLabel': 'Letzte Partie',
        'homeClub': club_stub(club),
        'awayClub': club_stub(opponent) if opponent else empty_club_stub(),
        'homeGoals': 0,
        'awayGoals': 0,
        'resultLabel': 'UNENTSCHIEDEN',
        'resultTone': 'draw',
        'backgroundImageUrl': stadium_image_for(club),
        'reportUrl': reverse('club_match_report', kwargs={'club_id': club.id}),
        'scorers': [],
    }


def build_table(club, opponent_club):
    rows = []
    table_clubs = []
    seen_ids = set()
    for candidate in [club, opponent_club]:
        if candidate and candidate.id not in seen_ids:
            table_clubs.append(candidate)
            seen_ids.add(candidate.id)
    for candidate in Club.objects.exclude(id__in=seen_ids).order_by('-budget', 'name'):
        if len(table_clubs) >= 7:
            break
        table_clubs.append(candidate)
        seen_ids.add(candidate.id)

    fallback_names = [
        ('Bayer Leverkusen', 'B04'),
        ('VfB Stuttgart', 'VFB'),
        ('RB Leipzig', 'RBL'),
        ('Eintracht Frankfurt', 'SGE'),
        ('Borussia Dortmund', 'BVB'),
        ('Wolfsburg', 'WOB'),
    ]
    while len(table_clubs) < 7:
        table_clubs.append(None)

    points = [78, 68, 63, 59, 55, 50, 46]
    diffs = [67, 37, 28, 17, 15, 8, 2]
    for index, candidate in enumerate(table_clubs[:7]):
        fallback = fallback_names[(index - 1) % len(fallback_names)]
        rows.append({
            'position': index + 1,
            'clubId': str(candidate.id) if candidate else '',
            'clubName': candidate.short_name if candidate else fallback[1],
            'clubCrestUrl': candidate.crest_static_path if candidate else '',
            'clubProfileUrl': reverse('club_detail', kwargs={'club_id': candidate.id}) if candidate else '',
            'played': 33,
            'goalDifference': f'+{diffs[index]}',
            'points': points[index],
            'isCurrentClub': bool(candidate and candidate.id == club.id),
        })

    if not any(row['isCurrentClub'] for row in rows):
        rows[-1] = {
            'position': 7,
            'clubId': str(club.id),
            'clubName': club.short_name,
            'clubCrestUrl': club.crest_static_path,
            'clubProfileUrl': reverse('club_detail', kwargs={'club_id': club.id}),
            'played': 33,
            'goalDifference': '+15',
            'points': 55,
            'isCurrentClub': True,
        }

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
    ]
    return [
        {
            'competitionName': competition_name,
            'count': count,
            'trophyImageUrl': get_cached_trophy_static_path(trophy_asset_id),
        }
        for competition_name, count, trophy_asset_id in fallback
    ]


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
    return f"game/images/flags/{asset['asset_id']}.svg"


def competition_logo_static_path(competition):
    assets = {
        '1. Bundesliga': 'game/images/competitions/bundesliga.png',
        'Bundesliga': 'game/images/competitions/bundesliga.png',
        'Websoccer Liga': 'game/images/competitions/websoccer-liga.svg',
        'DFB-Pokal': 'game/images/competitions/dfb-pokal.png',
        'Pokal': 'game/images/competitions/dfb-pokal.png',
        'Champions League': 'game/images/competitions/champions-league.png',
        'CL': 'game/images/competitions/champions-league.png',
        'Supercup': 'game/images/competitions/supercup.png',
    }
    return assets.get(competition, '')


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
        return [[]]
    return [
        items[index:index + size]
        for index in range(0, len(items), size)
    ]
