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
    (2, ['Club Atlético Independiente', 'Independiente']),    # 1973, 1984
    (3, ['Club Atlético Boca Juniors', 'Boca Juniors']),       # 1977, 2000, 2003
    # 2 wins
    (2, ['Santos FC', 'Santos']),                              # 1962, 1963
    (2, ['FC Internazionale Milano', 'Internazionale', 'Inter', 'Inter Milan']),  # 1964, 1965
    (2, ['AFC Ajax', 'Ajax']),                                 # 1972, 1995
    (2, ['Juventus FC', 'Juventus']),                          # 1985, 1996
    (2, ['FC Porto', 'Porto']),                                # 1987, 2004
    (2, ['São Paulo FC', 'Sao Paulo FC', 'São Paulo', 'Sao Paulo']),  # 1992, 1993
    # 1 win
    (1, ['Racing Club de Avellaneda', 'Racing Club']),         # 1967
    (1, ['Club Estudiantes de La Plata', 'Estudiantes']),      # 1968
    (1, ['Feyenoord', 'Feyenoord Rotterdam']),                 # 1970
    (1, ['Club Atlético de Madrid', 'Atlético Madrid', 'Atletico Madrid', 'Atletico de Madrid']),  # 1974
    (1, ['Club Olimpia', 'Olimpia']),                          # 1979
    (1, ['Clube de Regatas do Flamengo', 'Flamengo']),         # 1981
    (1, ['Grêmio Foot-Ball Porto Alegrense', 'Gremio', 'Grêmio']),  # 1983
    (1, ['Club Atlético River Plate', 'River Plate']),         # 1986
    (1, ['FK Crvena zvezda', 'Red Star Belgrade', 'Crvena Zvezda']),  # 1991
    (1, ['Club Atlético Vélez Sársfield', 'Vélez Sársfield', 'Velez Sarsfield', 'Vélez']),  # 1994
    (1, ['Manchester United FC', 'Manchester United']),        # 1999
]

# fm_inside_ids whose rows are managed by earlier migrations (0039, 0044).
EXCLUDED_FM_INSIDE_IDS = {915, 907}


# ---------------------------------------------------------------------------
# Migration function
# ---------------------------------------------------------------------------

def seed_intercontinental_other_clubs(apps, schema_editor):
    Club = apps.get_model('game', 'Club')
    ClubTrophy = apps.get_model('game', 'ClubTrophy')

    # Build a normalized-name → count lookup from the winners table.
    normalized_winners = {}
    for count, aliases in INTERCONTINENTAL_WINNERS:
        for alias in aliases:
            normalized_winners[_normalize(alias)] = count

    # Fetch all clubs not already handled by earlier migrations.
    clubs = Club.objects.exclude(fm_inside_id__in=EXCLUDED_FM_INSIDE_IDS)

    for club in clubs:
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
