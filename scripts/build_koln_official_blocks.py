"""Reproduce the small, checked-in plan-sector resource from hashed sources."""
import hashlib
import json
from pathlib import Path

from stadium_editor.koln_blocks import build_official_geometry, fingerprint

ROOT = Path(__file__).resolve().parents[1]
SEATS_SHA = "7ed9b68df8befccc1637786af57a4470da68db424c6e419efca9ca6c8f0e81f2"
PLAN_SHA = "6a43f986fd76002b04b30b9c011c2dc04cce692ee47ad543ab94b4ff0b76537d"
RESOURCE = ROOT / "stadium_editor/blueprints/v2/koln_official_blocks.json"


def main():
    seats_raw = (ROOT / "attached_assets/koln_1792488328917.json").read_bytes()
    plan_raw = (ROOT / "generated-artifacts/koln-blocks/current-official-plan.png").read_bytes()
    if hashlib.sha256(seats_raw).hexdigest() != SEATS_SHA:
        raise ValueError("Unbekannte Köln-Sitzquelle.")
    if hashlib.sha256(plan_raw).hexdigest() != PLAN_SHA:
        raise ValueError("Der FC-Plan ist nicht der geprüfte Plan 2026/27.")
    old = json.loads((ROOT / "generated-artifacts/koln-study/editor-geometry.json").read_text())
    # Re-running the main study now creates official blocks; keep the original
    # source-envelope reference from this resource once it has been reviewed.
    if old.get("blockTopology") and RESOURCE.exists():
        existing = json.loads(RESOURCE.read_text())
        old["blocks"] = existing["legacyBlocks"]
        old["meta"] = existing["referenceFrame"]
    seats = json.loads(seats_raw)["seats"]
    geometry, evidence = build_official_geometry(old, seats)
    evidence.update(sourceSha256=SEATS_SHA, planSha256=PLAN_SHA,
                    legacyBlocksSha256=fingerprint(old["blocks"]))
    data = {key: geometry[key] for key in (
        "blocks", "blockTopology", "physical_grid", "officialPlan", "homeStand", "mainStand")}
    data.update(referenceFrame=old["meta"], legacyBlocks=old["blocks"], evidence=evidence)
    RESOURCE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(geometry['blocks'])} Planblöcke, {len(seats)} Quellpunkte: {RESOURCE}")


if __name__ == "__main__":
    main()
