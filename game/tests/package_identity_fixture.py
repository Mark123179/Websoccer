"""Small synthetic package; identity tests must not depend on uploaded archives."""


def identity_package_fixture():
    def ids(values):
        return {provider: dict(value=value, status="gefunden" if value else "nicht_gefunden",
                               checked_at="2026-10-05")
                for provider, value in zip(("tm", "fmi", "cmtracker", "api_football"), values)}

    club = dict(
        name="Testverein", official_name="Testverein", short_name="TEST",
        founded_year=1900, city="Teststadt", country="Deutschland",
        lat=51.0, lng=7.0, colors=dict(primary="#ffffff", secondary="#000000", tertiary=None),
        nickname="", motto="", ids=ids((16, 907, 22, 165)), sources=[])
    stadium = dict(
        name="Teststadion", city="Teststadt", capacity_national=1000,
        home_end="S", main_stand="W", tier=2, lat=51.0, lng=7.0,
        stands={side: {kind: dict(value=250 if kind == "seating" else 0, basis="belegt")
                       for kind in ("standing", "seating", "vip")} for side in "NESW"},
        totals={kind: dict(value=1000 if kind == "seating_incl_vip" else 0, basis="belegt")
                for kind in ("standing", "seating_incl_vip", "vip")}, sources=[])
    player = dict(
        ids=ids((257814, 98040383, 235073, None)),
        first_name="Test", last_name="Torwart", display_name="Test Torwart",
        date_of_birth="1997-12-06", nationalities=["Schweiz"], height_cm=196, foot="R",
        squad=dict(team="first", status="own", owner_club=dict(tm_id=16, name="Testverein"),
                   loan_club=None, loan_until=None, shirt_number=1),
        positions=dict(main=["TW"], secondary=[], method="appearances",
                       seasons=[], appearances=[], tm_profile_position="Torwart"),
        market_value_eur=40000000, market_values=[], transfers=[],
        ratings=dict(
            fminside=dict(version="26.2.0", rating=81, potential=83, potential_range=None,
                          raw={"attributes": {}}, url=None),
            cmtracker=dict(db="26091500", rating=87, potential=89, raw={})),
        api_football=None, sources={})
    data = dict(club=club, stadium=stadium, players=[player], persons=[],
                records=[], titles=[], gaps=[])
    manifest = dict(
        format="WS_CLUB_PACKAGE", format_version=1, package_type="club",
        club=dict(tm_id=16, fmi_id=907, name="Testverein"), collected_at="2026-10-05",
        titles_through_season="2025/26", source_versions={}, position_window=[],
        counts=dict(players=1, first_team=1, u21=0, loaned_in=0, loaned_out=0,
                    persons=0, records=0, titles=0, gaps_blocking=0,
                    gaps_player_lock=0, gaps_info=0))
    return manifest, data
