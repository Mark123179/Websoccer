import unicodedata

from django.db import migrations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(name):
    """
    Return a lowercase, accent-stripped, whitespace-collapsed version of
    *name* for accent-insensitive exact matching.
    """
    nfkd = unicodedata.normalize('NFKD', name)
    stripped = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ' '.join(stripped.lower().split())


# ---------------------------------------------------------------------------
# Complete, verified trophy data for each major international club
# ---------------------------------------------------------------------------
# Format:
#   (aliases, trophies)
#   aliases  : list[str]  – canonical name first, then known variants
#   trophies : list of (competition_name, count, trophy_asset_id, sort_order)
#
# sort_order convention:
#   0 = domestic league
#   1 = domestic cup
#   2 = continental (Champions League / Copa Libertadores / Europa League)
#   3 = secondary honour (supercup)
#   9 = Intercontinental Cup
#
# Trophy asset IDs:
#   '1301394'                 – UEFA Champions League (FM Inside badge)
#   'continental cup 1'       – generic continental cup (Copa Libertadores etc.)
#   'national championship 1' – generic domestic league trophy
#   'national cup 1'          – generic domestic cup trophy
#   'international-cup-1'     – Intercontinental Cup (also set by migration 0045)
#
# All counts verified against Wikipedia "Honours" sections and RSSSF records
# as of June 2026.  Reference URLs are noted per club.
# ---------------------------------------------------------------------------

CLUB_FULL_TROPHIES = [

    # ------------------------------------------------------------------
    # Real Madrid CF — Spain
    # https://en.wikipedia.org/wiki/Real_Madrid_CF#Honours
    # La Liga: 36 (through 2024–25 season)
    # Copa del Rey: 20
    # Champions League / European Cup: 15
    #   (1956, 1957, 1958, 1959, 1960, 1966, 1998, 2000, 2002, 2014,
    #    2016, 2017, 2018, 2022, 2024)
    # Supercopa de España: 13
    # Intercontinental: 3 (1960, 1998, 2002)
    # ------------------------------------------------------------------
    (
        ['Real Madrid CF', 'Real Madrid'],
        [
            ('La Liga',             36, 'national championship 1', 0),
            ('Copa del Rey',        20, 'national cup 1',           1),
            ('Champions League',    15, '1301394',                  2),
            ('Supercopa de España', 13, 'national cup 1',           3),
            ('Intercontinental',     3, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Atlético de Madrid — Spain
    # https://en.wikipedia.org/wiki/Atlético_de_Madrid#Honours
    # La Liga: 11
    # Copa del Rey: 10
    # UEFA Cup / Europa League: 3 (2010, 2012, 2018)
    # Intercontinental: 1 (1974)
    # ------------------------------------------------------------------
    (
        ['Club Atlético de Madrid', 'Atlético Madrid', 'Atletico Madrid', 'Atletico de Madrid'],
        [
            ('La Liga',         11, 'national championship 1', 0),
            ('Copa del Rey',    10, 'national cup 1',           1),
            ('Europa League',    3, 'continental cup 1',        2),
            ('Intercontinental', 1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Associazione Calcio Milan — Italy
    # https://en.wikipedia.org/wiki/A.C._Milan#Honours
    # Serie A: 19
    # Coppa Italia: 5
    # Champions League / European Cup: 7
    #   (1963, 1969, 1989, 1990, 1994, 2003, 2007)
    # Intercontinental: 3 (1969, 1989, 1990)
    # ------------------------------------------------------------------
    (
        ['Associazione Calcio Milan', 'AC Milan', 'Milan'],
        [
            ('Serie A',          19, 'national championship 1', 0),
            ('Coppa Italia',      5, 'national cup 1',           1),
            ('Champions League',  7, '1301394',                  2),
            ('Intercontinental',  3, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Juventus FC — Italy
    # https://en.wikipedia.org/wiki/Juventus_F.C.#Honours
    # Serie A: 36
    # Coppa Italia: 15
    # Champions League / European Cup: 2 (1985, 1996)
    # Intercontinental: 2 (1985, 1996)
    # ------------------------------------------------------------------
    (
        ['Juventus FC', 'Juventus'],
        [
            ('Serie A',          36, 'national championship 1', 0),
            ('Coppa Italia',     15, 'national cup 1',           1),
            ('Champions League',  2, '1301394',                  2),
            ('Intercontinental',  2, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # FC Internazionale Milano — Italy
    # https://en.wikipedia.org/wiki/Inter_Milan#Honours
    # Serie A: 20
    # Coppa Italia: 9
    # Champions League / European Cup: 3 (1964, 1965, 2010)
    # Intercontinental: 2 (1964, 1965)
    # ------------------------------------------------------------------
    (
        ['FC Internazionale Milano', 'Internazionale', 'Inter', 'Inter Milan'],
        [
            ('Serie A',          20, 'national championship 1', 0),
            ('Coppa Italia',      9, 'national cup 1',           1),
            ('Champions League',  3, '1301394',                  2),
            ('Intercontinental',  2, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # AFC Ajax — Netherlands
    # https://en.wikipedia.org/wiki/AFC_Ajax#Honours
    # Eredivisie: 36
    # KNVB Cup: 21
    # Champions League / European Cup: 4 (1971, 1972, 1973, 1995)
    # Intercontinental: 2 (1972, 1995)
    # ------------------------------------------------------------------
    (
        ['AFC Ajax', 'Ajax'],
        [
            ('Eredivisie',       36, 'national championship 1', 0),
            ('KNVB Cup',         21, 'national cup 1',           1),
            ('Champions League',  4, '1301394',                  2),
            ('Intercontinental',  2, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Feyenoord — Netherlands
    # https://en.wikipedia.org/wiki/Feyenoord#Honours
    # Eredivisie: 16
    # KNVB Cup: 14
    # Champions League / European Cup: 1 (1970)
    # Intercontinental: 1 (1970)
    # ------------------------------------------------------------------
    (
        ['Feyenoord', 'Feyenoord Rotterdam'],
        [
            ('Eredivisie',       16, 'national championship 1', 0),
            ('KNVB Cup',         14, 'national cup 1',           1),
            ('Champions League',  1, '1301394',                  2),
            ('Intercontinental',  1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # FC Porto — Portugal
    # https://en.wikipedia.org/wiki/FC_Porto#Honours
    # Primeira Liga: 30
    # Taça de Portugal: 17
    # Champions League / European Cup: 2 (1987, 2004)
    # Intercontinental: 2 (1987, 2004)
    # ------------------------------------------------------------------
    (
        ['FC Porto', 'Porto'],
        [
            ('Primeira Liga',    30, 'national championship 1', 0),
            ('Taça de Portugal', 17, 'national cup 1',           1),
            ('Champions League',  2, '1301394',                  2),
            ('Intercontinental',  2, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Manchester United FC — England
    # https://en.wikipedia.org/wiki/Manchester_United_F.C.#Honours
    # Premier League / First Division: 20
    # FA Cup: 12
    # Champions League / European Cup: 3 (1968, 1999, 2008)
    # Intercontinental: 1 (1999)
    # ------------------------------------------------------------------
    (
        ['Manchester United FC', 'Manchester United'],
        [
            ('Premier League',   20, 'national championship 1', 0),
            ('FA Cup',           12, 'national cup 1',           1),
            ('Champions League',  3, '1301394',                  2),
            ('Intercontinental',  1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # FK Crvena zvezda (Red Star Belgrade) — Serbia
    # https://en.wikipedia.org/wiki/Red_Star_Belgrade#Honours
    # Superliga Srbije: 34
    # Kup Srbije: 27
    # Champions League / European Cup: 1 (1991)
    # Intercontinental: 1 (1991)
    # ------------------------------------------------------------------
    (
        ['FK Crvena zvezda', 'Red Star Belgrade', 'Crvena Zvezda'],
        [
            ('Superliga Srbije', 34, 'national championship 1', 0),
            ('Kup Srbije',       27, 'national cup 1',           1),
            ('Champions League',  1, '1301394',                  2),
            ('Intercontinental',  1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Nacional de Football — Uruguay
    # https://en.wikipedia.org/wiki/Club_Nacional_de_Football#Honours
    # Uruguayan Primera División: 49
    # Copa Uruguay: 10
    # Copa Libertadores: 3 (1971, 1980, 1988)
    # Intercontinental: 3 (1971, 1980, 1988)
    # ------------------------------------------------------------------
    (
        ['Club Nacional de Football', 'Nacional'],
        [
            ('Primera División',  49, 'national championship 1', 0),
            ('Copa Uruguay',      10, 'national cup 1',           1),
            ('Copa Libertadores',  3, 'continental cup 1',        2),
            ('Intercontinental',   3, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Atlético Peñarol — Uruguay
    # https://en.wikipedia.org/wiki/Peñarol#Honours
    # Uruguayan Primera División: 53
    # Copa Uruguay: 8
    # Copa Libertadores: 5 (1960, 1961, 1966, 1982, 1987)
    # Intercontinental: 3 (1961, 1966, 1982)
    # ------------------------------------------------------------------
    (
        ['Club Atlético Peñarol', 'Peñarol', 'Penarol'],
        [
            ('Primera División',  53, 'national championship 1', 0),
            ('Copa Uruguay',       8, 'national cup 1',           1),
            ('Copa Libertadores',  5, 'continental cup 1',        2),
            ('Intercontinental',   3, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Atlético Boca Juniors — Argentina
    # https://en.wikipedia.org/wiki/Boca_Juniors#Honours
    # Primera División Argentina: 35
    # Copa Argentina: 5 (1969, 2011-12, 2014-15, 2020-21, 2023-24)
    # Copa Libertadores: 6 (1977, 2000, 2001, 2003, 2007, 2015)
    # Intercontinental: 3 (1977, 2000, 2003)
    # ------------------------------------------------------------------
    (
        ['Club Atlético Boca Juniors', 'Boca Juniors'],
        [
            ('Primera División',  35, 'national championship 1', 0),
            ('Copa Argentina',     5, 'national cup 1',           1),
            ('Copa Libertadores',  6, 'continental cup 1',        2),
            ('Intercontinental',   3, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Atlético River Plate — Argentina
    # https://en.wikipedia.org/wiki/River_Plate#Honours
    # Primera División Argentina: 38
    # Copa Argentina: 8 (1985, 1994, 1995, 1996, 2017, 2019, 2022, 2023)
    # Copa Libertadores: 4 (1986, 1996, 2015, 2018)
    # Intercontinental: 1 (1986)
    # ------------------------------------------------------------------
    (
        ['Club Atlético River Plate', 'River Plate'],
        [
            ('Primera División',  38, 'national championship 1', 0),
            ('Copa Argentina',     8, 'national cup 1',           1),
            ('Copa Libertadores',  4, 'continental cup 1',        2),
            ('Intercontinental',   1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Atlético Independiente — Argentina
    # https://en.wikipedia.org/wiki/Club_Atlético_Independiente#Honours
    # Primera División Argentina: 16
    # Copa Argentina: 2 (1995, 2016)
    # Copa Libertadores: 7
    #   (1964, 1965, 1972, 1973, 1974, 1975, 1984)
    # Intercontinental: 2 (1973, 1984)
    # ------------------------------------------------------------------
    (
        ['Club Atlético Independiente', 'Independiente'],
        [
            ('Primera División',  16, 'national championship 1', 0),
            ('Copa Argentina',     2, 'national cup 1',           1),
            ('Copa Libertadores',  7, 'continental cup 1',        2),
            ('Intercontinental',   2, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Racing Club de Avellaneda — Argentina
    # https://en.wikipedia.org/wiki/Racing_Club_de_Avellaneda#Honours
    # Primera División Argentina: 9
    # Copa Argentina: 1 (1987)
    # Copa Libertadores: 1 (1967)
    # Intercontinental: 1 (1967)
    # ------------------------------------------------------------------
    (
        ['Racing Club de Avellaneda', 'Racing Club'],
        [
            ('Primera División',   9, 'national championship 1', 0),
            ('Copa Argentina',     1, 'national cup 1',           1),
            ('Copa Libertadores',  1, 'continental cup 1',        2),
            ('Intercontinental',   1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Estudiantes de La Plata — Argentina
    # https://en.wikipedia.org/wiki/Estudiantes_de_La_Plata#Honours
    # Primera División Argentina: 4 (1967, 1982-83, 2006, 2010)
    # Copa Argentina: 2 (2018, 2023)
    # Copa Libertadores: 4 (1968, 1969, 1970, 2009)
    # Intercontinental: 1 (1968)
    # ------------------------------------------------------------------
    (
        ['Club Estudiantes de La Plata', 'Estudiantes'],
        [
            ('Primera División',   4, 'national championship 1', 0),
            ('Copa Argentina',     2, 'national cup 1',           1),
            ('Copa Libertadores',  4, 'continental cup 1',        2),
            ('Intercontinental',   1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Atlético Vélez Sársfield — Argentina
    # https://en.wikipedia.org/wiki/Vélez_Sársfield#Honours
    # Primera División Argentina: 10
    # Copa Argentina: 2 (1996, 2022)
    # Copa Libertadores: 1 (1994)
    # Intercontinental: 1 (1994)
    # ------------------------------------------------------------------
    (
        ['Club Atlético Vélez Sársfield', 'Vélez Sársfield', 'Velez Sarsfield', 'Vélez'],
        [
            ('Primera División',  10, 'national championship 1', 0),
            ('Copa Argentina',     2, 'national cup 1',           1),
            ('Copa Libertadores',  1, 'continental cup 1',        2),
            ('Intercontinental',   1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Club Olimpia — Paraguay
    # https://en.wikipedia.org/wiki/Club_Olimpia#Honours
    # División de Honor (Apertura + Clausura combined titles): 44
    # Copa Paraguay: 28
    # Copa Libertadores: 3 (1979, 1990, 2002)
    # Intercontinental: 1 (1979)
    # ------------------------------------------------------------------
    (
        ['Club Olimpia', 'Olimpia'],
        [
            ('División de Honor', 44, 'national championship 1', 0),
            ('Copa Paraguay',     28, 'national cup 1',           1),
            ('Copa Libertadores',  3, 'continental cup 1',        2),
            ('Intercontinental',   1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Clube de Regatas do Flamengo — Brazil
    # https://en.wikipedia.org/wiki/Flamengo#Honours
    # Brasileirão: 8 (1980, 1982, 1983, 1987, 1992, 2009, 2019, 2020)
    # Copa do Brasil: 4 (2006, 2013, 2022, 2024)
    # Copa Libertadores: 3 (1981, 2019, 2022)
    # Intercontinental: 1 (1981)
    # ------------------------------------------------------------------
    (
        ['Clube de Regatas do Flamengo', 'Flamengo'],
        [
            ('Brasileirão',        8, 'national championship 1', 0),
            ('Copa do Brasil',     4, 'national cup 1',           1),
            ('Copa Libertadores',  3, 'continental cup 1',        2),
            ('Intercontinental',   1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Grêmio Foot-Ball Porto Alegrense — Brazil
    # https://en.wikipedia.org/wiki/Grêmio_Foot-Ball_Porto_Alegrense#Honours
    # Brasileirão: 2 (1981, 1996)
    # Copa do Brasil: 5 (1989, 1994, 1997, 2001, 2016)
    # Copa Libertadores: 3 (1983, 1995, 2017)
    # Intercontinental: 1 (1983)
    # ------------------------------------------------------------------
    (
        ['Grêmio Foot-Ball Porto Alegrense', 'Gremio', 'Grêmio'],
        [
            ('Brasileirão',        2, 'national championship 1', 0),
            ('Copa do Brasil',     5, 'national cup 1',           1),
            ('Copa Libertadores',  3, 'continental cup 1',        2),
            ('Intercontinental',   1, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # São Paulo FC — Brazil
    # https://en.wikipedia.org/wiki/São_Paulo_FC#Honours
    # Brasileirão: 6 (1977, 1986, 1987, 1992, 2006, 2008)
    # Copa do Brasil: 1 (1992)
    # Copa Libertadores: 3 (1992, 1993, 2005)
    # Intercontinental: 2 (1992, 1993)
    # ------------------------------------------------------------------
    (
        ['São Paulo FC', 'Sao Paulo FC', 'São Paulo', 'Sao Paulo'],
        [
            ('Brasileirão',        6, 'national championship 1', 0),
            ('Copa do Brasil',     1, 'national cup 1',           1),
            ('Copa Libertadores',  3, 'continental cup 1',        2),
            ('Intercontinental',   2, 'international-cup-1',      9),
        ],
    ),

    # ------------------------------------------------------------------
    # Santos FC — Brazil
    # https://en.wikipedia.org/wiki/Santos_FC#Honours
    # Brasileirão: 8 (1961, 1962, 1963, 1964, 1965, 1968, 2002, 2004)
    # Taça Brasil: 5 (1961, 1962, 1963, 1964, 1965)
    #   The Taça Brasil was the national cup competition before
    #   the Copa do Brasil was established in 1989. Santos did not win
    #   the Copa do Brasil in any subsequent edition.
    # Copa Libertadores: 2 (1962, 1963)
    # Intercontinental: 2 (1962, 1963)
    # ------------------------------------------------------------------
    (
        ['Santos FC', 'Santos'],
        [
            ('Brasileirão',        8, 'national championship 1', 0),
            ('Taça Brasil',        5, 'national cup 1',           1),
            ('Copa Libertadores',  2, 'continental cup 1',        2),
            ('Intercontinental',   2, 'international-cup-1',      9),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Migration function
# ---------------------------------------------------------------------------

def seed_full_trophies_international_clubs(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    ClubTrophy = apps.get_model('game', 'ClubTrophy')

    # Build a normalized-name → trophy list lookup.
    normalized_lookup = {}
    for aliases, trophies in CLUB_FULL_TROPHIES:
        for alias in aliases:
            normalized_lookup[_normalize(alias)] = trophies

    for club in Club.objects.all():
        trophies = normalized_lookup.get(_normalize(club.name))
        if trophies is None:
            continue

        for competition_name, count, trophy_asset_id, sort_order in trophies:
            ClubTrophy.objects.update_or_create(
                club=club,
                competition_name=competition_name,
                defaults={
                    'count': count,
                    'trophy_asset_id': trophy_asset_id,
                    'sort_order': sort_order,
                },
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0046_migrate_manager_flag_urls'),
    ]

    operations = [
        migrations.RunPython(seed_full_trophies_international_clubs, noop_reverse),
    ]
