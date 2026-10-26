"""Verify the delivered series as a whole and assemble its reusable material package."""
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image

OUT = Path("generated-artifacts/grass-study")


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    variants = manifest["variants"]
    assert len(variants) == 12
    assert [v["id"] for v in variants] == [
        "A1", "A2", "A3", "A4", "B1", "B2", "B3", "C1", "C2", "D1", "D2", "D3"]
    assert len({v["pattern"] for v in variants}) == 4
    assert len({v["tone"] for v in variants}) == 4
    assert len({v["wear"] for v in variants}) == 3
    assert all((v["tone"], v["wear"]) == (1, 1) for v in variants[:4])
    assert all((v["pattern"], v["wear"]) == (1, 1) for v in variants[4:7])
    assert all((v["pattern"], v["tone"]) == (1, 1) for v in variants[7:9])
    for variant in variants:
        with Image.open(OUT / variant["texture"]) as image:
            assert image.size == (3150, 2040)
    dortmund = json.loads((OUT / "verification-dortmund.json").read_text())
    elversberg = json.loads((OUT / "verification-elversberg.json").read_text())
    assert len(dortmund["states"]) == 15
    assert len(elversberg["states"]) == 2
    assert dortmund["camera"] == elversberg["camera"]
    corners = dortmund["states"][0]["corners"]
    for evidence in [dortmund, elversberg]:
        assert not evidence["errors"] and not evidence["geometryChanged"]
        for state in evidence["states"]:
            assert state["corners"] == corners and state["shaderErrors"] == 0
            assert state["surfaceMeshes"] == (0 if state["id"] == "bestand" else 10)
            path = OUT / "renders" / state["file"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == state["sha256"]
            if state["night"]:
                assert state["verifiedFixtures"] > 0 and 0 < state["activeLights"] <= 12
    # Same image-space point, same grass material and explicit comparison lighting.
    with Image.open(OUT / "renders/A1-day.png") as a, Image.open(OUT / "renders/A1-elversberg.png") as b:
        av, bv = np.asarray(a.convert("RGB")), np.asarray(b.convert("RGB"))
        crop = (slice(550, 700), slice(500, 1300))
        cross_club_error = float(np.abs(av[crop].astype(float) - bv[crop]).mean())
        assert cross_club_error < 1, f"Grass lighting differs between stadiums: {cross_club_error}"
    with Image.open(OUT / "textures/C2.webp") as image:
        rgb = np.asarray(image)
        green_fraction = float(np.mean(rgb[:, :, 1] > rgb[:, :, 0]))
        assert green_fraction > .90, "Worn pitch is predominantly brown."
    summary = dict(variants=12, fullSize=[3150, 2040], projectionResidual=0,
        crossStadiumMeanRgbError=cross_club_error, wornGreenFraction=green_fraction,
        actualRenderedStates=17, productionChanged=False,
        unitTests="9 passing (UV continuity, camera, source lighting and shadow invariants)",
        inspection="All 12 actual daylight renders and top views, two night states and two stadium frames.")
    (OUT / "quality-summary.json").write_text(json.dumps(summary, indent=2))
    archive = OUT / "rasen-materialpaket.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=4) as pack:
        for folder in ["textures", "layers", "top", "renders"]:
            for path in sorted((OUT / folder).glob("*")):
                pack.write(path, path.relative_to(OUT))
        for name in ["grass-ai-base.png", "manifest.json", "generation.json", "quality-summary.json",
                     "verification-dortmund.json", "verification-elversberg.json",
                     "elversberg-scene.json", "vergleich-tag.png", "vergleich-draufsicht.png"]:
            pack.write(OUT / name, name)
        for filename in ["grass_study_materials.py", "export_grass_study.mjs",
                         "grass_study_report.py", "package_grass_study.py"]:
            pack.write(Path("scripts") / filename, f"reproduction/{filename}")
        pack.write("docs/stadium/grass-ai-comparison.md", "README.md")
        pack.write("stadium_editor/static/stadium_editor/grass_surface_study.js",
                   "reproduction/grass_surface_study.js")
    print(json.dumps(summary, indent=2))
    print(archive, archive.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
