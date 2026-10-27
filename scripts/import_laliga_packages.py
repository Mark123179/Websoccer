"""Apply the explicitly approved, source-preserving LaLiga quarantine batch."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import zipfile

from scripts.import_additional_club_packages import (
    import_batch, m, transaction, validate_batch_players,
)
from game.club_import.package_validation import PackageError, read_package


SOURCE = Path("attached_assets/laliga_vereinspakete_2026-10-27_1793090727720.zip")
SOURCE_SHA = "ac87857f81e8929450b21a71973b664e1abbd61b8b435de98c491883d52c27eb"
OUTPUT = Path("generated-artifacts/laliga-2026-10-27")
QUARANTINE = {
    1162017: (2000280111, "FMInside-ID ebenfalls Adrián Pérez bei Sevilla zugeordnet."),
    1596653: (2000280111, "FMInside-ID ebenfalls Adrián Pérez bei Athletic zugeordnet."),
    1066206: (2000351880, "FMInside-ID ebenfalls Joni Hernández zugeordnet."),
    1533553: (2000351880, "FMInside-ID ebenfalls Toni Fernández zugeordnet."),
    1342235: (2000395283, "FMInside-ID ebenfalls Noah Rodríguez zugeordnet."),
    1451988: (2000395283, "FMInside-ID ebenfalls Anxo Rodríguez zugeordnet."),
    790669: (2000086852, "FMInside-Zuordnung bei abweichendem Geburtsdatum ungeklärt."),
    1064403: ((2000374246, 2000277721), "Zwei abweichende FMInside-IDs für Álvaro García."),
}
LOAN_OVERRIDES = {
    1064403: ({"tm_id": 1108, "name": "Deportivo Alavés"},
              {"tm_id": 1050, "name": "FC Villarreal"}),
    982999: ({"tm_id": 150, "name": "Real Betis Sevilla"},
             {"tm_id": 3709, "name": "FC Getafe"}),
}


def prepare():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise PackageError("Original delivery changed; approval must be reviewed.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    paths, packages, evidence, seen = [], [], [], Counter()
    loan_evidence = []
    totals = Counter()
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        if len(outer.namelist()) != 20:
            raise PackageError("Expected exactly 20 club packages.")
        for name in outer.namelist():
            if Path(name).name != name or not name.endswith(".zip"):
                raise PackageError("Unexpected archive entry.")
            with zipfile.ZipFile(io.BytesIO(outer.read(name))) as inner:
                if sorted(inner.namelist()) != ["data.json", "manifest.json"]:
                    raise PackageError("Unexpected club archive structure.")
                manifest = json.loads(inner.read("manifest.json"))
                data_raw = inner.read("data.json")
                data = json.loads(data_raw)
            if hashlib.sha256(data_raw).hexdigest() != manifest["data_sha256"]:
                raise PackageError("Original club checksum mismatch.")
            for player in data["players"]:
                tm = player["ids"]["tm"]["value"]
                if tm in LOAN_OVERRIDES:
                    loan_evidence.append({
                        "club": data["club"]["name"], "tm": tm,
                        "original_squad": dict(player["squad"]),
                    })
                    owner, borrower = LOAN_OVERRIDES[tm]
                    player["squad"].update(owner_club=dict(owner), loan_club=dict(borrower))
                    data["gaps"].append({
                        "entity": "player", "ref": f"tm:{tm}", "field": "squad",
                        "severity": "info",
                        "note": "Spielerbezogen freigegebene Hauptvereins-Zuordnung: "
                                + owner["name"] + " → " + borrower["name"]
                                + ". Originale B-Team-Angaben bleiben im Quellenarchiv erhalten.",
                    })
                if tm not in QUARANTINE:
                    continue
                expected, reason = QUARANTINE[tm]
                expected_ids = expected if isinstance(expected, tuple) else (expected,)
                if player["ids"]["fmi"]["value"] not in expected_ids:
                    raise PackageError("Quarantined source assignment changed.")
                seen[tm] += 1
                evidence.append({
                    "club": data["club"]["name"], "tm": tm,
                    "player": player["display_name"], "reason": reason,
                    "original_fmi": player["ids"]["fmi"],
                    "original_fminside_rating": player["ratings"]["fminside"],
                    "original_package_checksum": manifest["data_sha256"],
                })
                player["ids"]["fmi"] = {
                    "value": None, "status": "nicht_gefunden",
                    "checked_at": manifest["collected_at"],
                }
                player["ratings"]["fminside"] = None
                data["gaps"].append({
                    "entity": "player", "ref": f"tm:{tm}", "field": "ids.fmi",
                    "severity": "player_lock",
                    "note": "Freigegebene FM-Quarantäne: " + reason
                            + " Originalbeleg erhalten; keine Freigabe durch erneute Lieferung.",
                })
            for severity in ("blocking", "player_lock", "info"):
                manifest["counts"]["gaps_" + severity] = sum(
                    gap["severity"] == severity for gap in data["gaps"])
            encoded = json.dumps(data, ensure_ascii=False, indent=2).encode()
            manifest["data_sha256"] = hashlib.sha256(encoded).hexdigest()
            path = OUTPUT / name
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
                package.writestr("data.json", encoded)
                package.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
            checked_manifest, checked_data = read_package(path)
            packages.append((path, checked_manifest, checked_data))
            paths.append(path)
            totals.update({key: len(data[key]) for key in ("players", "persons", "records", "titles")})
    if set(seen) != set(QUARANTINE) or any(
            count != (2 if tm == 1064403 else 1) for tm, count in seen.items()):
        raise PackageError("Quarantine coverage differs from the approved eight players.")
    if Counter(row["tm"] for row in loan_evidence) != Counter({1064403: 2, 982999: 2}):
        raise PackageError("Approved loan exceptions do not cover both package views.")
    shared = validate_batch_players(packages)
    provenance = {
        "original_archive": str(SOURCE), "original_sha256": SOURCE_SHA,
        "quarantine": evidence, "loan_exceptions": loan_evidence, "source_totals": dict(totals),
        "reciprocal_loans": len(shared),
        "unique_players": len({p["ids"]["tm"]["value"] for _, _, d in packages for p in d["players"]}),
    }
    (OUTPUT / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    return paths, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    paths, provenance = prepare()
    print(f"Prepared {len(paths)} validated packages, "
          f"{provenance['unique_players']} unique players; starting guarded import.", flush=True)
    with transaction.atomic():
        league, _ = m.League.objects.get_or_create(
            name="LaLiga", country="Spanien",
            defaults={"level": 1, "is_playable": False})
        report = import_batch(paths, {}, apply=True, target_league_id=league.pk)
        for tm in QUARANTINE:
            player = m.Player.objects.get(transfermarkt_id=tm)
            if (player.fm_inside_id is not None or not player.import_lock
                    or player.source_ratings.filter(source="FM").exists()):
                raise PackageError("Quarantined FM identity or rating remains active.")
        for tm, (owner, borrower) in LOAN_OVERRIDES.items():
            player = m.Player.objects.get(transfermarkt_id=tm)
            if (player.owner_club.transfermarkt_id != owner["tm_id"]
                    or player.club.transfermarkt_id != borrower["tm_id"]
                    or player.squad_team != "u21"
                    or str(player.loan_until) != "2027-06-30"):
                raise PackageError("Approved youth loan projection is incomplete.")
        expected_clubs = {read_package(path)[0]["club"]["tm_id"] for path in paths}
        if set(league.club_set.values_list("transfermarkt_id", flat=True)) != expected_clubs:
            raise PackageError("League membership differs from the complete delivery.")
        report.update(applied=args.apply, source=provenance,
                      quarantine_verified=True, club_count=len(expected_clubs))
        if not args.apply:
            transaction.set_rollback(True)
    report_path = OUTPUT / ("applied-report.json" if args.apply else "dry-run-report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ("packages", "source")}, ensure_ascii=False, indent=2))
    print("Report:", report_path)


if __name__ == "__main__":
    main()
