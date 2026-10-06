"""Local N12 evidence; the sole optional mutation restores one archived context."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.import_pilot_n11_evidence import capture, assert_local_pilot
from django.db import transaction
from game import models as m
from game import strength_engine as se

V2 = "ab3925f40f1b84ddd103a25928d61aa7feb3c36d9036890ff802131896751391"


def restore_context():
    assert_local_pilot()
    baseline = json.loads((ROOT / "docs/import-pilot/n12-before.json").read_text())
    with transaction.atomic():
        current = capture()
        assert current["tables"] == baseline["tables"], "Pilot changed since N12 baseline."
        run = m.SourceImportRun.objects.filter(status="applied").order_by("-pk").first()
        assert run.data_sha256 == V2
        full = next(r["context"] for r in run.package_data["records"]
                    if r["key"] == "most_titles_player")
        assert len(full) == 233 and full.endswith("cup, Champions League, Weltpokal.")
        record = m.ClubRecord.objects.select_for_update().get(
            club=run.club, source="SEED", record_key="most_titles_player")
        before = m.ClubRecord.objects.filter(pk=record.pk).values().get()
        assert before["context_line"] == full[:200]
        assert m.ClubRecord.objects.filter(pk=record.pk).update(context_line=full) == 1
        after = m.ClubRecord.objects.filter(pk=record.pk).values().get()
        changed_fields = [key for key in before if before[key] != after[key]]
        assert changed_fields == ["context_line"]
        post = capture()
        changed_tables = [table for table in baseline["tables"]
                          if baseline["tables"][table] != post["tables"][table]]
        assert changed_tables == ["game_clubrecord"]
        proof = dict(record_id=record.pk, key="most_titles_player", changed_fields=changed_fields,
                     previous_length=200, restored_length=233, timestamp_unchanged=True)
    (ROOT / "docs/import-pilot/n12-context-repair.json").write_text(
        json.dumps(proof, indent=2) + "\n")
    return proof


def export_strengths():
    assert_local_pilot()
    run = m.SourceImportRun.objects.filter(status="applied").order_by("-pk").first()
    assert run.data_sha256 == V2
    rows = []
    for source in run.package_data["players"]:
        player = m.Player.objects.get(transfermarkt_id=source["ids"]["tm"]["value"])
        ratings = {r.source: r for r in player.source_ratings.all()}
        fm, cm = ratings.get("FM"), ratings.get("CMTRACKER")
        base = se.calculate_base_200(fm.rating if fm else None, cm.rating if cm else None)
        potential = se.calculate_potential_200(
            fm.potential if fm else None, cm.potential if cm else None, base)
        original_fm = source["ratings"].get("fminside") or {}
        span = original_fm.get("potential_range")
        rows.append({
            "Name": player.display_name, "TM-ID": player.transfermarkt_id,
            "FMInside-Rating": fm.rating if fm else "",
            "FMInside-Potenzial": fm.potential if fm and fm.potential is not None else "",
            "FMInside-Potenzialspanne": f'{span["min"]}–{span["max"]}' if span else "",
            "CMTracker-Rating": cm.rating if cm else "",
            "CMTracker-Potenzial": cm.potential if cm and cm.potential is not None else "",
            "Basis Rohskala 0–200": base if base is not None else "",
            "Potenzial Rohskala 0–200": potential if potential is not None else "",
            "Einzelsperre": "Ja" if player.import_lock else "Nein",
            "Sperrgrund": " | ".join(player.import_lock_reasons or []),
        })
    assert len(rows) == 51
    path = ROOT / "docs/import-pilot/n12-staerken-51.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "locked": sum(row["Einzelsperre"] == "Ja" for row in rows)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair-context", action="store_true")
    parser.add_argument("--export-strengths", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = {}
    if args.repair_context:
        result["repair"] = restore_context()
    if args.export_strengths:
        result["csv"] = export_strengths()
    evidence = capture()
    baseline = json.loads((ROOT / "docs/import-pilot/n12-before.json").read_text())
    result["pilot"] = evidence
    result["changed_tables"] = [table for table in baseline["tables"]
                               if baseline["tables"][table] != evidence["tables"][table]]
    assert result["changed_tables"] == ["game_clubrecord"]
    assert evidence["package_hashes"][-1] == V2
    assert (evidence["issues"], evidence["open"], evidence["package_closed"],
            evidence["strengths"], evidence["locks"]) == (156, 128, 28, 49, 2)
    (ROOT / args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "pilot"}, ensure_ascii=False))
