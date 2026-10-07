"""Verify active v2 source identities, rendered fields and extended CSV, read-only."""
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.import_pilot_n11_evidence import assert_local_pilot, capture
from scripts.import_pilot_n12_evidence import export_strengths, V2
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import RequestFactory
from django.urls import reverse
from game import models as m
from game.club_import.package_validation import read_package
from game.tests.source_identity_html import SourceIdentityParser
from game.views_creator import creator_player_edit

PACKAGE = ROOT / "attached_assets/0_bvb_vereinspaket_2026-10-05_v2_1_1791282305881.zip"
OUT = ROOT / "docs/import-pilot"
PROVIDERS = (("TM", "tm", "TM"), ("FM", "fmi", "FMInside"),
             ("CMTRACKER", "cmtracker", "CMTracker"))


def main():
    assert_local_pilot()
    _, data = read_package(PACKAGE)
    cm_matches = []
    gardarsson = {}
    csv_path = OUT / "n12-staerken-51.csv"
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        before = capture()
        delivered = json.loads((OUT / "n12-after.json").read_text())["pilot"]
        assert before["tables"] == delivered["tables"]
        assert before["package_hashes"][-1] == V2
        user = get_user_model().objects.filter(is_staff=True, is_active=True).first()
        assert user is not None
        for source in data["players"]:
            player = m.Player.objects.get(transfermarkt_id=source["ids"]["tm"]["value"])
            request = RequestFactory().get(reverse("creator_player_edit", args=[player.pk]))
            request.user, request.session = user, {}
            response = creator_player_edit(request, player.pk)
            assert response.status_code == 200, source["display_name"]
            rows = SourceIdentityParser(response.content.decode()).rows
            for code, key, label in PROVIDERS:
                expected = source["ids"][key]
                identity = player.external_ids.get(source__code=code)
                value = str(expected["value"]) if expected["value"] is not None else ""
                checked = expected.get("checked_at") or ""
                assert (identity.external_id or "") == value, source["display_name"]
                assert identity.status == expected["status"]
                assert (identity.checked_at.isoformat() if identity.checked_at else "") == checked
                assert rows[code]["external_id"] == (value or "—")
                assert rows[code]["status"] == expected["status"]
                assert rows[code]["checked_at"] == checked
                assert rows[code]["readonly"]
                if checked:
                    y, month, day = checked.split("-")
                    assert f"ID geprüft: {day}.{month}.{y}" in rows[code]["text"]
            if source["ids"]["cmtracker"]["value"] is not None:
                cm_matches.append({
                    "Name": source["display_name"],
                    "TM-ID": source["ids"]["tm"]["value"],
                    "CMTracker-ID Paket": str(source["ids"]["cmtracker"]["value"]),
                    "CMTracker-ID DB": player.external_ids.get(
                        source__code="CMTRACKER").external_id,
                    "CMTracker-ID Source-Anzeige": rows["CMTRACKER"]["external_id"],
                    "Status": rows["CMTRACKER"]["status"],
                    "ID geprüft am": rows["CMTRACKER"]["checked_at"],
                    "Ergebnis": "identisch",
                })
            if player.last_name == "Gardarsson":
                gardarsson = rows
        assert len(cm_matches) == 34
        assert gardarsson["FM"]["blocks"]
        assert not gardarsson["CMTRACKER"]["blocks"]
        assert "Status: nicht gefunden · sperrt" in gardarsson["FM"]["text"]
        assert "Status: dort nicht vorhanden · sperrt nicht" in gardarsson["CMTRACKER"]["text"]
        csv_proof = export_strengths()
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            csv_rows = {row["TM-ID"]: row for row in csv.DictReader(handle, delimiter=";")}
        assert len(csv_rows) == 51
        for source in data["players"]:
            row = csv_rows[str(source["ids"]["tm"]["value"])]
            for code, key, label in PROVIDERS:
                expected = source["ids"][key]
                value = str(expected["value"]) if expected["value"] is not None else ""
                assert row[label + "-ID"] == value
                assert row[label + "-ID-Status"] == expected["status"]
                assert row[label + "-ID geprüft am"] == (expected.get("checked_at") or "")
        after = capture()
        # Capture's wall-clock timestamp is not a persisted pilot fact.
        assert {k: v for k, v in before.items() if k != "at"} == {
            k: v for k, v in after.items() if k != "at"
        }, "Read-only verification must preserve every pilot fact."
    cm_path = OUT / "n12-cmtracker-id-abgleich-34.csv"
    with cm_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cm_matches[0]), delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(cm_matches)
    proof = {
        "active_package": "v2", "package_hash": V2,
        "creator_pages_rendered_read_only": len(data["players"]),
        "canonical_source_identity_blocks_verified": len(data["players"]) * len(PROVIDERS),
        "cmtracker_ids_matched_package_database_and_rendered_input": len(cm_matches),
        "cmtracker_mismatches": 0,
        "cmtracker_comparison_sha256": hashlib.sha256(cm_path.read_bytes()).hexdigest(),
        "gardarsson": gardarsson, "strength_csv": csv_proof,
        "pilot_game_tables_unchanged": len(after["tables"]),
        "issues": after["issues"], "open": after["open"],
        "package_closed": after["package_closed"],
        "strengths": after["strengths"], "locks": after["locks"],
        "verification": "Read-only transaction, existing staff object, no login/session/account mutation.",
    }
    (OUT / "n12-source-id-status-verification.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(proof, ensure_ascii=False))


if __name__ == "__main__":
    main()
