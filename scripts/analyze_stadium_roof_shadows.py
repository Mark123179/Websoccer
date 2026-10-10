"""Compare actual probe renders; no synthesized lighting or modified source frames."""
import hashlib
import json
from itertools import repeat
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

ROOT = Path("generated-artifacts/stadium-roof-shadow-probe")


def main():
    report = json.loads((ROOT / "verification.json").read_text())
    states = report["states"]
    if len(states) != 5 or any(s["club"] != "dortmund" for s in states):
        raise ValueError("Expected the five isolated Dortmund shadow states.")
    geometry = Path("stadium_editor/static/stadium_editor/dortmund_original/geometry.bin")
    actual_hash = hashlib.sha256(geometry.read_bytes()).hexdigest()
    if actual_hash != report["sourceEvidence"]["geometrySha256"]:
        raise ValueError("Loaded original geometry differs from the fixture evidence.")
    for state in states:
        for key in ("projection", "pose", "corners", "sourceAlignment"):
            if state[key] != states[0][key]:
                raise ValueError(f"Controlled comparison changed {key}.")
        if state["activeSources"] != 6 or state["visibleRoofMeshes"] != (33 if state["roof"] else 0):
            raise ValueError("Source/roof inventory differs from the verified probe.")

    def frame(name):
        return Image.open(ROOT / f"{name}.png").convert("RGB")

    shadowed = frame("dortmund_roof_night_shadowed")
    control = frame("dortmund_roof_night_roof_noncasting")
    delta = ImageChops.difference(shadowed, control)
    if delta.getbbox() is None:
        raise ValueError("No rendered roof-caster effect; cannot claim visible occlusion.")
    pitch = Image.new("L", shadowed.size)
    ImageDraw.Draw(pitch).polygon([(c["x"], c["y"]) for c in states[0]["corners"]], fill=255)

    def pixel_summary(mask=None):
        stat = ImageStat.Stat(delta, mask)
        changed = over3 = total = 0
        rgb = delta.tobytes()
        differences = zip(rgb[0::3], rgb[1::3], rgb[2::3])
        for difference, included in zip(differences, mask.tobytes() if mask else repeat(255)):
            if not included:
                continue
            total += 1
            changed += int(max(difference) > 0)
            over3 += int(max(difference) > 3)
        return {"pixels": total, "changedPixels": changed, "pixelsWithChannelDeltaOver3": over3,
                "meanAbsoluteChannelDelta": stat.mean,
                "maxAbsoluteChannelDelta": [e[1] for e in stat.extrema]}

    metrics = {
        "comparison": "Visible original roof, casts ON versus OFF; all other shadows remain ON",
        "geometrySha256Checked": actual_hash,
        "fullFrame": pixel_summary(), "projectedPitchPolygon": pixel_summary(pitch),
        "units": "8-bit sRGB channel difference after ACES; not lux",
        "limitations": ["Pitch polygon is a screen-space region, not a surface-ID measurement",
                        "Software WebGL; not a hardware/FPS benchmark"],
    }
    (ROOT / "pixel-comparison.json").write_text(json.dumps(metrics, indent=2) + "\n")

    # Full-size unaltered rear-stand crops, annotated only outside image areas.
    # The paired originals have identical geometry visibility, so the difference
    # cannot be attributed to removing the roof from the camera image.
    crop = (260, 140, 1620, 450)
    crops = [image.crop(crop) for image in (shadowed, control)]
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    w, h = crops[0].size
    comparison = Image.new("RGB", (w, (h + 50) * 2), "#101820")
    draw = ImageDraw.Draw(comparison)
    for index, (image, label) in enumerate(zip(crops, [
        "Originaldach sichtbar, Dachschatten AN",
        "Originaldach sichtbar, nur Dachschatten AUS (Kontrolle)",
    ])):
        top = index * (h + 50)
        draw.text((12, top + 12), label, font=font, fill="white")
        comparison.paste(image, (0, top + 50))
    comparison.save(ROOT / "roof-shadow-controlled-comparison.png")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
