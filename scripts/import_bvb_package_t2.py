"""Authorized one-off pilot application and read-only T2 evidence export."""
import json
from collections import Counter
from pathlib import Path
from html import escape

from check_import_package_t2 import (
    ROOT, PACKAGE, MANIFEST, DATA, state, m, connection, transaction, TABLES)
from game.club_import.package_service import apply_package
from game.strength_service import compute_strength_for_player


def run():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema(),current_user")
        assert cursor.fetchone() == ("import_pilot", "import_pilot_role")
    protected_before = {key: value for key, value in state().items() if key in TABLES}
    with transaction.atomic():
        league = m.League.objects.filter(name="Bundesliga", country="Deutschland").first()
        if league is None:
            assert m.League.objects.count() == m.Club.objects.count() == m.Player.objects.count() == 0
            league = m.League.objects.create(name="Bundesliga", country="Deutschland", level=1, is_playable=True)
        result = apply_package(PACKAGE, league)
    first = state()
    replay = apply_package(PACKAGE, league)
    second = state()
    assert replay["unchanged"] and first == second
    assert protected_before == {key: value for key, value in second.items() if key in TABLES}
    club = m.Club.objects.get(pk=result["club"])
    players = list(m.Player.objects.order_by("last_name", "first_name"))
    pool = [p.full_name for p in players if p.is_in_loan_pool]
    borrowed = [p.full_name for p in players if p.club_id == club.pk
                and p.loan_club_tm_id == club.transfermarkt_id and p.owner_club_tm_id != club.transfermarkt_id]
    evidence = {
        "package_sha256": MANIFEST["data_sha256"], "applied_run": result["run"],
        "counts": {
            "clubs": m.Club.objects.count(), "players": len(players),
            "persons": m.HistoricCoach.objects.count(),
            "market_values": m.PlayerMarketValueSnapshot.objects.count(),
            "start_values": m.PlayerMarketValueSnapshot.objects.filter(is_start_value=True).count(),
            "real_market_values": m.PlayerMarketValueSnapshot.objects.filter(origin="real").count(),
            "transfers": m.PlayerTransferHistory.objects.count(),
            "records": m.ClubRecord.objects.count(), "title_entries": m.ClubTrophyEntry.objects.count(),
            "aggregated_title_rows": m.ClubTrophy.objects.count(),
            "source_snapshots": m.PlayerSourceRatingSnapshot.objects.count(),
            "players_with_ratings": m.Player.objects.filter(source_ratings__isnull=False).distinct().count(),
            "calculated": m.PlayerStrengthProfile.objects.count(),
            "issues": dict(Counter(m.ImportIssue.objects.values_list("severity", flat=True))),
        },
        "squad": {
            "first": [p.full_name for p in players if p.club_id == club.pk and p.squad_team == "first"],
            "u21": [p.full_name for p in players if p.club_id == club.pk and p.squad_team == "u21"],
            "loan_pool": pool, "borrowed": borrowed,
            "review_pool": [p.full_name for p in players if p.review_pool]},
        "locked": [{"name": p.full_name, "reason": p.import_lock_reasons}
                   for p in players if p.import_lock],
        "dynamic_uncomputable": [p.full_name for p in players
                                if not p.import_lock and not hasattr(p, "strength_profile")],
        "second_upload": {"same_result": replay["unchanged"], "compared_tables": len(first),
                          "changed_table_fingerprints": [key for key in first if first[key] != second[key]],
                          "created_rows": 0},
        "protected_tables": {"compared": len(protected_before), "changed": []},
        "real_life_club_nonempty": m.Player.objects.filter(real_life_club__isnull=False).count(),
    }
    references = []
    for player in DATA["players"]:
        references.extend(point.get("club") for point in player["market_values"])
        for transfer in player["transfers"]:
            references.extend([transfer.get("from"), transfer.get("to")])
        references.extend([player["squad"].get("owner_club"), player["squad"].get("loan_club")])
    references.extend(r.get("opponent") for r in DATA["records"])
    evidence["references"] = {
        "distinct_external_tm_ids": len({r["tm_id"] for r in references if r and r.get("tm_id")
                                        and r["tm_id"] != club.transfermarkt_id}),
        "names_without_tm_id": sorted({r["name"] for r in references if r and not r.get("tm_id") and r.get("name")}),
        "occurrences_without_tm_id": sum(bool(r and not r.get("tm_id") and r.get("name")) for r in references),
        "club_rows": m.Club.objects.count(), "reference_only_club_rows": 0}
    samples = []
    by_tm = {p.transfermarkt_id: p for p in players}
    sample_players = [by_tm[p["ids"]["tm"]["value"]] for p in DATA["players"][:3]]
    sample_players.append(next(p for p in players if p.club_id == club.pk
                              and p.owner_club_tm_id != club.transfermarkt_id
                              and hasattr(p, "strength_profile")))
    sample_players.append(next(p for p in players if p.squad_team == "u21"
                              and hasattr(p, "strength_profile")))
    for player in sample_players:
        name = player.full_name
        result_strength = compute_strength_for_player(player)
        samples.append({"name": name, "positions": player.main_positions,
            "sources": list(player.source_ratings.values("source", "rating", "potential")),
            "base_strength": str(result_strength["base_strength"]),
            "max_strength": str(result_strength["max_strength"]),
            "persisted_base": str(player.strength_profile.base_strength) if hasattr(player, "strength_profile") else None})
    evidence["strength_samples"] = samples
    output = ROOT / "docs/import-pilot/t2-evidence.json"
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "docs/import-pilot/t2-second-upload-fingerprints.json").write_text(
        json.dumps({"before": first, "after": second}, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
