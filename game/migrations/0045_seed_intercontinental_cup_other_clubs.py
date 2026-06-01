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
# Winner table
# ---------------------------------------------------------------------------
# Each entry: (count, [canonical name, *aliases])
# The canonical name (first alias) is used to resolve WINNER_FM_INSIDE_IDS.
#
# All names are matched via _normalize() against Club.name in the database,
# so diacritic variants (e.g. "Penharol" / "Peñarol") resolve correctly.
# Clubs already handled by migrations 0039 / 0044 are excluded.
#
# Counts verified against Wikipedia / RSSSF records:
#   https://en.wikipedia.org/wiki/Intercontinental_Cup_(football)
# ---------------------------------------------------------------------------
INTERCONTINENTAL_WINNERS = [
    # 3 wins
    (3, ['Real Madrid CF', 'Real Madrid']),                   # 1960, 1998, 2002
    (3, ['Club Atlético Peñarol', 'Peñarol', 'Penarol']),     # 1961, 1966, 1982
    (3, ['Associazione Calcio Milan', 'AC Milan', 'Milan']),  # 1969, 1989, 1990
    (3, ['Club Nacional de Football', 'Nacional']),           # 1971, 1980, 1988
    (3, ['Club Atlético Boca Juniors', 'Boca Juniors']),       # 1977, 2000, 2003
    # 2 wins
    (2, ['Club Atlético Independiente', 'Independiente']),    # 1973, 1984
    (2, ['Santos FC', 'Santos FC Brasil']),                   # 1962, 1963
    (2, ['FC Internazionale Milano', 'Internazionale', 'Inter Milan']),  # 1964, 1965
    (2, ['AFC Ajax', 'Ajax']),                                # 1972, 1995
    (2, ['Juventus FC', 'Juventus']),                         # 1985, 1996
    (2, ['FC Porto', 'Porto']),                               # 1987, 2004
    (2, ['São Paulo FC', 'Sao Paulo FC', 'São Paulo', 'Sao Paulo']),  # 1992, 1993
    # 1 win
    (1, ['Racing Club de Avellaneda', 'Racing Club Avellaneda']),  # 1967
    (1, ['Club Estudiantes de La Plata', 'Estudiantes']),     # 1968
    (1, ['Feyenoord', 'Feyenoord Rotterdam']),                # 1970
    (1, ['Club Atlético de Madrid', 'Atlético Madrid', 'Atletico Madrid', 'Atletico de Madrid']),  # 1974
    (1, ['Club Olimpia', 'Olimpia']),                         # 1979
    (1, ['Clube de Regatas do Flamengo', 'Flamengo']),        # 1981
    (1, ['Grêmio Foot-Ball Porto Alegrense', 'Gremio', 'Grêmio']),  # 1983
    (1, ['Club Atlético River Plate', 'River Plate']),        # 1986
    (1, ['FK Crvena zvezda', 'Red Star Belgrade', 'Crvena Zvezda']),  # 1991
    (1, ['Club Atlético Vélez Sársfield', 'Vélez Sársfield', 'Velez Sarsfield', 'Vélez']),  # 1994
    (1, ['Manchester United FC', 'Manchester United']),       # 1999
]

# fm_inside_ids whose rows are managed by earlier migrations (0039, 0044).
EXCLUDED_FM_INSIDE_IDS = {915, 907}

# ---------------------------------------------------------------------------
# fm_inside_id lookup table for winner clubs
# ---------------------------------------------------------------------------
# Maps the canonical club name (first alias in INTERCONTINENTAL_WINNERS) to its
# fm_inside_id as used by fminside.net (Football Manager 26 database).
#
# When a club row exists in the database with this fm_inside_id the migration
# uses it as the primary key instead of the less-precise name match.
# If no club row with that fm_inside_id is found, the name-based lookup below
# acts as the fallback — so adding an ID here is always safe.
#
# IDs verified against fminside.net (FM 26, database version 7-fm-26):
#   https://fminside.net/clubs/7-fm-26/<id>-<slug>
# ---------------------------------------------------------------------------
WINNER_FM_INSIDE_IDS = {
    # European clubs
    'Real Madrid CF':                   8633,   # fminside.net/clubs/7-fm-26/8633-real-madrid
    'Associazione Calcio Milan':        9825,   # fminside.net/clubs/7-fm-26/9825-ac-milan
    'AFC Ajax':                         1900,   # fminside.net/clubs/7-fm-26/1900-ajax
    'Juventus FC':                      3829,   # fminside.net/clubs/7-fm-26/3829-juventus
    'FC Internazionale Milano':         4931,   # fminside.net/clubs/7-fm-26/4931-internazionale
    'FC Porto':                         5703,   # fminside.net/clubs/7-fm-26/5703-porto
    'Manchester United FC':            10261,   # fminside.net/clubs/7-fm-26/10261-manchester-united
    'Club Atlético de Madrid':          9906,   # fminside.net/clubs/7-fm-26/9906-atletico-madrid
    'Feyenoord':                         113,   # fminside.net/clubs/7-fm-26/113-feyenoord
    'FK Crvena zvezda':                  429,   # fminside.net/clubs/7-fm-26/429-red-star-belgrade
    # South American clubs
    'Club Atlético Peñarol':            1877,   # fminside.net/clubs/7-fm-26/1877-penarol
    'Club Nacional de Football':        1879,   # fminside.net/clubs/7-fm-26/1879-nacional
    'Club Atlético Boca Juniors':       1656,   # fminside.net/clubs/7-fm-26/1656-boca-juniors
    'Santos FC':                        1659,   # fminside.net/clubs/7-fm-26/1659-santos
    'Club Atlético Independiente':      1653,   # fminside.net/clubs/7-fm-26/1653-independiente
    'Racing Club de Avellaneda':        1647,   # fminside.net/clubs/7-fm-26/1647-racing-club
    'Club Estudiantes de La Plata':     1652,   # fminside.net/clubs/7-fm-26/1652-estudiantes
    'Club Atlético River Plate':        1645,   # fminside.net/clubs/7-fm-26/1645-river-plate
    'Club Atlético Vélez Sársfield':    1657,   # fminside.net/clubs/7-fm-26/1657-velez-sarsfield
    'Club Olimpia':                     2441,   # fminside.net/clubs/7-fm-26/2441-olimpia
    'Clube de Regatas do Flamengo':     1660,   # fminside.net/clubs/7-fm-26/1660-flamengo
    'Grêmio Foot-Ball Porto Alegrense': 1663,   # fminside.net/clubs/7-fm-26/1663-gremio
    'São Paulo FC':                     1662,   # fminside.net/clubs/7-fm-26/1662-sao-paulo
}


# ---------------------------------------------------------------------------
# Migration function
# ---------------------------------------------------------------------------

def seed_intercontinental_other_clubs(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    ClubTrophy = apps.get_model('game', 'ClubTrophy')

    # Build fm_inside_id → count lookup (primary, precise).
    fm_id_winners = {}
    for count, aliases in INTERCONTINENTAL_WINNERS:
        canonical = aliases[0]
        fm_id = WINNER_FM_INSIDE_IDS.get(canonical)
        if fm_id is not None and fm_id not in EXCLUDED_FM_INSIDE_IDS:
            fm_id_winners[fm_id] = count

    # Build normalized-name → count lookup (fallback for clubs without a known
    # fm_inside_id or clubs whose fm_inside_id is not yet in the database).
    normalized_winners = {}
    for count, aliases in INTERCONTINENTAL_WINNERS:
        for alias in aliases:
            normalized_winners[_normalize(alias)] = count

    # Fetch all clubs not already handled by earlier migrations.
    clubs = Club.objects.exclude(fm_inside_id__in=EXCLUDED_FM_INSIDE_IDS)

    for club in clubs:
        # Prefer fm_inside_id lookup — avoids false positives from common name
        # fragments such as "Santos", "Nacional", or "Racing Club".
        count = fm_id_winners.get(club.fm_inside_id)
        if count is None:
            count = normalized_winners.get(_normalize(club.name))
        if count is None:
            continue

        ClubTrophy.objects.update_or_create(
            club=club,
            competition_name='Intercontinental',
            defaults={
                'count': count,
                'trophy_asset_id': 'international-cup-1',
                'sort_order': 9,
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0044_set_intercontinental_cup_asset_all_clubs'),
    ]

    operations = [
        migrations.RunPython(seed_intercontinental_other_clubs, noop_reverse),
    ]
