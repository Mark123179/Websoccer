#!/usr/bin/env python3
"""Mask-protect freshly rendered stadium/field pixels and build the labelled plate."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size):
    result = subprocess.run(
        ["fc-match", "-f", "%{file}", "DejaVu Sans"],
        check=True, capture_output=True, text=True,
    )
    font_path = Path(result.stdout.strip())
    if not font_path.is_file():
        raise FileNotFoundError(f"fc-match returned no usable font file: {font_path}")
    return ImageFont.truetype(str(font_path), size)


def main():
    out = Path(sys.argv[1])
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    states = manifest["states"]
    for state in states:
        design = Image.open(out / state["image"]).convert("RGB")
        baseline = Image.open(out / state["baseline"]).convert("RGB")
        stadium_path = out / state["stadiumMask"]
        field_path = out / state["fieldMask"]
        stadium = Image.open(stadium_path).convert("L").point(lambda p: 255 if p > 0 else 0)
        field = Image.open(field_path).convert("L").point(lambda p: 255 if p > 0 else 0)
        if design.size != (1880, 940) or baseline.size != design.size:
            raise ValueError(f"Unexpected native frame size in {state['image']}")
        # Explicit source-pixel preservation: the fresh real stadium silhouette wins over surroundings.
        design.paste(baseline, (0, 0), stadium)
        # Pitch mask is separately exported for independent exact-pixel checks/evidence.
        design.paste(baseline, (0, 0), field)
        stadium.save(stadium_path, optimize=True)
        field.save(field_path, optimize=True)
        design.save(out / state["image"], optimize=True)

    # Four complete views on a single compact comparison sheet, with restrained technical labels.
    panel_w, panel_h = 940, 470
    margin, gutter, header = 26, 18, 54
    sheet = Image.new("RGB", (margin * 2 + panel_w * 2 + gutter, margin * 2 + (panel_h + header) * 2 + gutter),
                      "#081b1d")
    draw = ImageDraw.Draw(sheet)
    label_font, small_font = load_font(23), load_font(13)
    positions = [(margin, margin), (margin + panel_w + gutter, margin),
                 (margin, margin + panel_h + header + gutter),
                 (margin + panel_w + gutter, margin + panel_h + header + gutter)]
    for state, (x, y) in zip(states, positions):
        title = ("RÄUMLICH" if state["style"] == "spatial" else "FLACH")
        subtitle = "DACH AN" if state["roof"] else "DACH AUS"
        draw.text((x, y), title, fill="#c8dddd", font=label_font)
        draw.text((x + 164, y + 8), subtitle, fill="#79aeb2", font=small_font)
        draw.line((x, y + header - 8, x + panel_w, y + header - 8), fill="#285055", width=1)
        image = Image.open(out / state["image"]).convert("RGB").resize((panel_w, panel_h), Image.Resampling.LANCZOS)
        sheet.paste(image, (x, y + header))
    sheet.save(out / "comparison.png", optimize=True)
    print("Created comparison.png; protected each fresh stadium silhouette and retained separate binary field masks.")


if __name__ == "__main__":
    main()
