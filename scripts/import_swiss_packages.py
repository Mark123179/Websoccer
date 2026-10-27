"""Source-preserving Swiss Workspace import; default rolls back every DB write."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import zipfile

from scripts.import_additional_club_packages import (
    import_batch, m, transaction, validate_batch_players,
)
from game.club_import.package_validation import PackageError, read_package


SOURCE = Path("attached_assets/schweiz_vereinspakete_2026-10-27_1793101337227.zip")
SOURCE_SHA = "4b0ae43e098ab953032ea8fcda679e9cd27ccb41c5a46f616e02e09ffe9b723d"
OUTPUT = Path("generated-artifacts/schweiz-2026-10-27")
OPEN_RECORDS = {
    (260, "longest_unbeaten"), (527, "longest_win_streak_coach"),
    (434, "longest_winless"), (321, "longest_winless"),
}
OWNER_EXCEPTIONS = {1133978: 985, 978438: 3}
OWNER_SOURCE_IDS = {1133978: 9251, 978438: 438}
DECISION = (
    "Freigegeben: Intertoto-Spiele vor 1995 zählen nicht für Vereinsrekorde. "
    "Originalbeleg im unveränderten Lieferarchiv; Entscheidung und Änderungen "
    "siehe docs/import-pilot/schweiz-2026-10-27.md."
)


def require(condition, message):
    if not condition:
        raise PackageError(message)


def revise_records(data):
    """Only the approved six record projections change; never alter player rows."""
    changes = []
    tm = data["club"]["ids"]["tm"]["value"]
    for record in data["records"]:
        key = record["key"]
        if (tm, key) not in OPEN_RECORDS and not (
                tm == 504 and key in ("biggest_defeat", "youngest_player")):
            continue
        original = deepcopy(record)
        if (tm, key) in OPEN_RECORDS:
            require("intertoto" in record["context"].lower(),
                    "Expected mixed Intertoto source record.")
            record.update(
                value_numeric=None, value_display="", holder=None, opponent=None,
                date=None, period_from=None, period_to=None, season=None,
                competition=None, status="nicht_belegt",
                context=DECISION + " Rekordserie offen: Ersatzwert ohne alte "
                        "Intertoto-Spiele noch nicht belegt; keine Subtraktion oder Schätzung.",
            )
            data["gaps"].append({
                "entity": "record", "ref": key, "field": f"records.{key}",
                "severity": "info",
                "note": record["context"],
            })
        elif key == "biggest_defeat":
            require(record["value_display"] == "2:9" and record["date"] == "1971-07-03",
                    "GC defeat source changed.")
            record.update(
                value_numeric=7, value_display="1:8",
                opponent={"tm_id": 26, "name": "FC Basel 1893"},
                date="2004-09-12", season="2004/05", competition="Super League",
                context=DECISION + " FM26 und die gelieferte TM-Rekordauswertung "
                        "belegen 1:8 gegen Basel am 12.09.2004.",
            )
        else:
            require(record["value_display"] == "15 Jahre, 111 Tage"
                    and record["date"] == "1992-06-27",
                    "GC youngest-player source changed.")
            record.update(
                value_numeric=record["value_numeric"] + 25,
                value_display="15 Jahre, 136 Tage",
                opponent={"tm_id": None, "name": "Neuchâtel Xamax FCS"},
                date="1992-07-22", season="1992/93", competition="Nationalliga A",
                context=DECISION + " Johann Vogel: im Paket belegtes FM26-Ligadebüt "
                        "am 22.07.1992 statt altem Intertoto-Einsatz am 27.06.1992.",
            )
        if tm == 504:
            record["sources"] = [
                {"name": "FM26 Historische Aufzeichnungen (gelieferte Auswertung)",
                 "url": None, "checked_at": "2026-10-27"},
                *record["sources"],
            ]
        changes.append({"club_tm": tm, "key": key, "original": original,
                        "projection": deepcopy(record)})
    return changes


def prepare():
    raw = SOURCE.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA,
            "Original delivery changed; approval must be reviewed.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    paths, packages, changes, owner_evidence = [], [], [], []
    totals = Counter()
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        require(len(outer.namelist()) == 12, "Expected exactly twelve club packages.")
        for name in outer.namelist():
            require(Path(name).name == name and name.endswith(".zip"),
                    "Unexpected source archive entry.")
            manifest, data = read_package(outer.read(name))
            for player in data["players"]:
                tm = player["ids"]["tm"]["value"]
                if tm not in OWNER_EXCEPTIONS:
                    continue
                squad = player["squad"]
                require(squad["status"] == "loaned_in"
                        and squad["owner_club"]["tm_id"] == OWNER_SOURCE_IDS[tm]
                        and squad["loan_club"]["tm_id"] == manifest["club"]["tm_id"]
                        and squad["loan_until"] == "2027-06-30",
                        "Approved main-club loan source changed.")
                owner_evidence.append({
                    "player_tm": tm, "preserved_owner_tm": OWNER_EXCEPTIONS[tm],
                    "original_squad": deepcopy(squad),
                })
            changes.extend(revise_records(data))
            totals.update({key: len(data[key]) for key in
                           ("players", "persons", "records", "titles")})
            encoded = json.dumps(data, ensure_ascii=False, indent=2).encode()
            manifest["data_sha256"] = hashlib.sha256(encoded).hexdigest()
            manifest["counts"]["gaps_info"] = sum(
                gap["severity"] == "info" for gap in data["gaps"])
            path = OUTPUT / name
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("data.json", encoded)
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
            checked_manifest, checked_data = read_package(path)
            packages.append((path, checked_manifest, checked_data))
            paths.append(path)
    require(Counter((r["club_tm"], r["key"]) for r in changes) == Counter(
        {key: 1 for key in OPEN_RECORDS | {(504, "biggest_defeat"), (504, "youngest_player")}}),
        "Approved record coverage changed.")
    require(Counter(row["player_tm"] for row in owner_evidence)
            == Counter({tm: 1 for tm in OWNER_EXCEPTIONS}),
            "Approved main-club loan coverage changed.")
    shared = validate_batch_players(packages)
    provenance = {
        "original_archive": str(SOURCE), "original_sha256": SOURCE_SHA,
        "record_changes": changes, "source_totals": dict(totals),
        "reciprocal_loans": len(shared),
        "unique_players": len({p["ids"]["tm"]["value"] for _, _, d in packages
                               for p in d["players"]}),
        "approved_club_countries": {"163": "Liechtenstein"},
        "owner_exceptions": owner_evidence,
    }
    (OUTPUT / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    return paths, provenance


def verify(league, paths):
    expected = {read_package(path)[0]["club"]["tm_id"] for path in paths}
    require(set(league.club_set.values_list("transfermarkt_id", flat=True)) == expected,
            "Swiss league membership differs from delivery.")
    require(league.max_teams == 12 and not league.is_playable,
            "Swiss league must remain non-playable with twelve places.")
    require(m.ClubPublicProfile.objects.get(club__transfermarkt_id=163).city_country
            == "Liechtenstein", "Vaduz country must remain Liechtenstein.")
    gc = m.ClubRecord.objects.get(
        club__transfermarkt_id=504, record_key="biggest_defeat", source="SEED")
    require(gc.value_display == "1:8" and str(gc.record_date) == "2004-09-12"
            and gc.opponent_tm_id == 26, "GC defeat projection is incomplete.")
    for tm, key in OPEN_RECORDS:
        row = m.ClubRecord.objects.get(club__transfermarkt_id=tm, record_key=key, source="SEED")
        require(row.value_numeric is None and row.evidence_status == "nicht_belegt",
                "Unverified mixed-competition record remains active.")
    for tm, owner in OWNER_EXCEPTIONS.items():
        player = m.Player.objects.get(transfermarkt_id=tm)
        target = 527 if tm == 1133978 else 938
        require(player.owner_club_tm_id == owner
                and player.owner_club.transfermarkt_id == owner
                and player.club.transfermarkt_id == target
                and str(player.loan_until) == "2027-06-30",
                "Approved main-club ownership or Swiss loan is incomplete.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    paths, provenance = prepare()
    print(f"Prepared twelve packages, {provenance['unique_players']} unique players.",
          flush=True)
    with transaction.atomic():
        league, _ = m.League.objects.get_or_create(
            name="Super League", country="Schweiz",
            defaults={"level": 1, "max_teams": 12, "is_playable": False})
        require(league.level == 1 and league.max_teams == 12,
                "Existing Swiss league setup differs from approval.")
        report = import_batch(paths, OWNER_EXCEPTIONS, apply=True, target_league_id=league.pk,
                              approved_club_countries={163: "Liechtenstein"})
        verify(league, paths)
        report.update(applied=args.apply, source=provenance, club_count=12,
                      open_records=4, record_projections_verified=True)
        if not args.apply:
            transaction.set_rollback(True)
    path = OUTPUT / ("applied-report.json" if args.apply else "dry-run-report.json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("packages", "source")},
                     ensure_ascii=False, indent=2))
    print("Report:", path)


if __name__ == "__main__":
    main()
