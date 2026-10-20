"""Bind the roof-only payload to the approved partition, sources and comparisons."""
import base64
import hashlib
import html
import json
from pathlib import Path
import subprocess

from scripts.install_koln_roofs import (
    ROOF_KEYS, PACKAGE, apply_roof_package, contract_without_roofs, digest,
)
from scripts.refine_koln_heights import HEIGHTS, REVIEW

VIEWS = ("abel-ost-tag", "abel-west-tag", "abel-ost-nacht", "abel-west-nacht",
         "ticker-tag", "ticker-nacht-flutlicht")


def package():
    raw = (REVIEW / "presentation.json").read_bytes()
    presentation = json.loads(raw)
    data = presentation["presentation"]["surroundings"]
    original = json.loads(Path("docs/stadium/koln-height-evidence.json").read_text())
    stripped = contract_without_roofs(data["buildingParts"])
    if stripped != original["buildingParts"]:
        raise ValueError("Approved component partition changed")
    current = json.loads((HEIGHTS / "height-evidence.json").read_text())
    if current["terrain"] != original["terrain"] or current["buildings"] != original["buildings"]:
        raise ValueError("Terrain or single-height evidence changed")
    # Match the exact baseline bytes served by capture_koln_study.mjs, using
    # JS number formatting rather than assuming Python serialization is equal.
    baseline_hash = subprocess.check_output([
        "node", "--input-type=module", "-e",
        """import fs from 'node:fs';import {createHash} from 'node:crypto';
        const d=JSON.parse(fs.readFileSync(process.argv[1]));
        for(const g of d.presentation.surroundings.buildingParts.groups)for(const p of g.parts)
          for(const k of ['roofSurfaces','roofStatus','roofRejection','rejectedRoofEvidence'])delete p[k];
        console.log(createHash('sha256').update(JSON.stringify(d)).digest('hex'));""",
        str(REVIEW / "presentation.json"),
    ], text=True).strip()
    manifest = json.loads((REVIEW / "manifest.json").read_text())
    comparisons = {}
    for label, directory, is_flat in (
        ("before", "roof-baseline-views", True), ("after", "roof-views", False)
    ):
        renders = json.loads((REVIEW / directory / "render-evidence.json").read_text())
        if {r["name"] for r in renders} != set(VIEWS):
            raise ValueError("Missing day/night comparison")
        for r in renders:
            if (r["errors"] or r["flatRoofs"] != is_flat
                    or r["assetVersion"] != manifest["assetVersion"]):
                raise ValueError("Invalid render evidence")
            expected_hash = baseline_hash if is_flat else hashlib.sha256(raw).hexdigest()
            if r["presentationSha256"] != expected_hash:
                raise ValueError("Stale roof comparison")
            image = REVIEW / directory / (r["name"] + ".png")
            if hashlib.sha256(image.read_bytes()).hexdigest() != r["imageSha256"]:
                raise ValueError("Render image hash changed")
        comparisons[label] = renders
    source = json.loads((HEIGHTS / "sources.json").read_text())
    parts = {p["lodId"]: {k: p[k] for k in ROOF_KEYS if k in p}
             for g in data["buildingParts"]["groups"] for p in g["parts"]}
    files = {p["file"] for g in stripped["groups"] for p in g["parts"]}
    sources = [s for s in source["sources"] if s["file"] in files]
    for s in sources:
        if hashlib.sha256((HEIGHTS / s["file"]).read_bytes()).hexdigest() != s["sha256"]:
            raise ValueError("Roof source file changed")
    payload = {
        "version": 1, "verticalDatum": data["buildingParts"]["verticalDatum"],
        "referenceNHN": data["buildingParts"]["referenceNHN"],
        "baselinePartsSha256": digest(stripped), "parts": parts, "sources": sources,
        "invariants": {"partitionUnchanged": True, "terrainUnchanged": True,
                       "singleHeightApprovalUnchanged": True},
        "comparisons": comparisons,
        "rendererSha256": {
            name: hashlib.sha256((Path("stadium_editor/static/stadium_editor") / name).read_bytes()).hexdigest()
            for name in ("building_parts.js", "dortmund_surroundings.js", "unity_stadium_scene.js")
        },
    }
    if apply_roof_package({**data, "buildingParts": stripped}, payload) != data:
        raise ValueError("Roof-only overlay does not reproduce reviewed surroundings")
    PACKAGE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sections = []
    for name in VIEWS:
        images = []
        for directory, label in (("roof-baseline-views", "Vorher · horizontale Hülle"),
                                 ("roof-views", "Nachher · geprüfte Dachflächen")):
            image = base64.b64encode((REVIEW / directory / (name + ".png")).read_bytes()).decode()
            images.append(f'<figure><figcaption>{label}</figcaption>'
                          f'<img src="data:image/png;base64,{image}"></figure>')
        sections.append(f'<h2>{html.escape(name)}</h2><section>{"".join(images)}</section>')
    report = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<title>Abelbauten – amtliche Dachflächen</title><style>
body{{background:#0b131b;color:#e1eaf1;font:16px system-ui;margin:32px}}
section{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}figure{{margin:0}}
img{{width:100%}}figcaption{{padding:10px 0}}p{{max-width:1000px}}
</style><h1>Abelbauten: Tag-/Nachtvergleich</h1>
<p>Gleiche Kamera, gleicher NHN-Bezug ({payload['referenceNHN']:.9f} m), unverändertes
Gelände und unveränderte OSM-Restflächen. Neun amtliche RoofSurface-Pakete;
zwei ausgeschlossene Dächer behalten ihre horizontale Hülle. Diagnosekameras
sind keine Freigabe einer neuen Spielkamera. Wände sind weiterhin schematisch.</p>
{''.join(sections)}</html>"""
    (HEIGHTS / "koln-dachvergleich.html").write_text(report)
    print(json.dumps({"package": str(PACKAGE), "sources": len(parts),
                      "accepted": sum(p["roofStatus"] == "official_surfaces" for p in parts.values()),
                      "report": str(HEIGHTS / "koln-dachvergleich.html")}))


if __name__ == "__main__":
    package()
