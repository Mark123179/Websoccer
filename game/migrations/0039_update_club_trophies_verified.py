from django.db import migrations


def update_club_trophies(apps, schema_editor):
    """
    Replace placeholder trophy seed data with verified historical counts.

    Sources / verification notes
    ----------------------------
    Bayern München (fm_inside_id=915)
      Bundesliga      : 33  (1932, 1969, 1972–74, 1980–82, 1985, 1986, 1987, 1988, 1989,
                              1990, 1994, 1997, 1999–2001, 2003, 2005–06, 2008, 2010,
                              2013–23)
      DFB-Pokal       : 20  (1957, 1966, 1967, 1969, 1971, 1982, 1984, 1986, 1998, 2000,
                              2003, 2005, 2006, 2008, 2010, 2013, 2014, 2016, 2019, 2020)
      Champions League:  6  (1974, 1975, 1976, 2001, 2013, 2020)
      DFL-Supercup    : 10  (1987, 1990, 2010, 2012, 2016, 2017, 2018, 2019, 2020, 2021)
      Klub-WM         :  2  (2013, 2020)
      DFB-Ligapokal   :  6  (1997, 1998, 1999, 2000, 2004, 2007)

    Borussia Dortmund (fm_inside_id=907)
      Bundesliga        : 8  (1956, 1957, 1963, 1995, 1996, 2002, 2011, 2012)
      DFB-Pokal         : 5  (1965, 1989, 2012, 2017, 2021)
      Champions League  : 1  (1997)
      DFL-Supercup      : 5  (1995, 1996, 2013, 2014, 2019)
      DFB-Ligapokal     : 3  (1998, 1999, 2003)
      Intercontinental  : 1  (1997)
    """
    Club = apps.get_model('game', 'Club')
    ClubTrophy = apps.get_model('game', 'ClubTrophy')

    bayern = Club.objects.filter(fm_inside_id=915).first()
    dortmund = Club.objects.filter(fm_inside_id=907).first()

    if bayern:
        ClubTrophy.objects.filter(club=bayern).delete()
        bayern_trophies = [
            ('Bundesliga',       33, '22',       0),
            ('DFB-Pokal',        20, '1301410',  1),
            ('Champions League',  6, '1301394',  2),
            ('DFL-Supercup',     10, '1301397',  3),
            ('Klub-WM',           2, '1001959',  4),
            ('DFB-Ligapokal',     6, '100',      5),
        ]
        for competition_name, count, trophy_asset_id, sort_order in bayern_trophies:
            ClubTrophy.objects.create(
                club=bayern,
                competition_name=competition_name,
                count=count,
                trophy_asset_id=trophy_asset_id,
                sort_order=sort_order,
            )

    if dortmund:
        ClubTrophy.objects.filter(club=dortmund).delete()
        dortmund_trophies = [
            ('Bundesliga',         8, '22',       0),
            ('DFB-Pokal',          5, '1301410',  1),
            ('Champions League',   1, '1301394',  2),
            ('DFL-Supercup',       5, '1301397',  3),
            ('DFB-Ligapokal',      3, '100',      4),
            ('Intercontinental',   1, '',         5),
        ]
        for competition_name, count, trophy_asset_id, sort_order in dortmund_trophies:
            ClubTrophy.objects.create(
                club=dortmund,
                competition_name=competition_name,
                count=count,
                trophy_asset_id=trophy_asset_id,
                sort_order=sort_order,
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0038_link_kirschgutzje_to_user'),
    ]

    operations = [
        migrations.RunPython(update_club_trophies, noop_reverse),
    ]
