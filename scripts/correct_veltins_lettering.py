"""Veltins-only clean seat lettering in the original crowd UV atlas.

Prepare offline; --activate uploads an immutable texture revision after review.
No geometry, lighting, economic capacity or saved stadium-design writes.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "stadium_editor/blueprints/v2/models/920.json"
SOURCE = ROOT / "generated-artifacts/veltins-study/source-export"
OUT = ROOT / "generated-artifacts/veltins-lettering-correction"
TEXTURE = "texture--3116212797608367091.webp"
SIZE = 2048
REFERENCE = "https://www.ruhr24.de/assets/images/42/863/42863053-blick-in-die-veltins-arena-des-fc-schalke-04-2lNTlb0qML7a.jpg"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def lettering_mask():
    """Original atlas placement; one glyph line, shared by treads and risers.

    Crowd UVs intentionally repeat on different tread/riser surfaces. Painting
    by world height would overwrite those shared pixels with conflicting rows.
    Keep the source atlas registration and replace only its hand-drawn glyphs.
    """
    font = ImageFont.truetype(FONT, 220)
    text = "FC SCHALKE 04"
    bounds = font.getbbox(text)
    glyphs = Image.new("L", (bounds[2] - bounds[0], bounds[3] - bounds[1]))
    ImageDraw.Draw(glyphs).text((-bounds[0], -bounds[1]), text, font=font, fill=255)
    glyphs = glyphs.resize((216 * 4, 32 * 4), Image.Resampling.LANCZOS)
    mask = Image.new("L", (SIZE, SIZE))
    mask.paste(glyphs, (155 * 4, 109 * 4))
    return np.asarray(mask, dtype=float) / 255


def corrected_texture(manifest, binary, original):
    pixels = np.array(original.convert("RGB").resize((SIZE, SIZE), Image.Resampling.NEAREST))
    painted = np.zeros((SIZE, SIZE), dtype=bool)
    white = lettering_mask()[..., None]
    artwork = np.rint(np.array([47, 72, 124]) * (1 - white) +
                      np.array([241, 244, 247]) * white).astype(np.uint8)
    registered = False
    for mesh in manifest["meshes"]:
        if not mesh["name"].startswith("C_front1_"):
            continue
        uv = np.frombuffer(binary, "<f4", count=mesh["vertexCount"] * 2,
                          offset=mesh["uvOffset"]).reshape(-1, 2)
        for part in mesh["parts"]:
            if part.get("texture") != TEXTURE:
                continue
            if (uv[:, 0].min() < 374 / 512 and uv[:, 0].max() > 150 / 512 and
                    uv[:, 1].min() < 145 / 512 and uv[:, 1].max() > 105 / 512):
                registered = True
    if not registered:
        raise ValueError("Insufficient original lettering-stand UV coverage")
    # Replace the complete original glyph patch. Triangle-only repainting leaves
    # old glyph fragments in atlas gutters that bilinear sampling brings back.
    # The runtime retains the original UVs, seats, stair gaps and geometry.
    painted[105 * 4:145 * 4, 150 * 4:374 * 4] = True
    pixels[painted] = artwork[painted]
    return Image.fromarray(pixels), painted


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    raw = REGISTRY.read_bytes()
    baseline = json.loads(raw)
    binary = (SOURCE / "geometry.bin").read_bytes()
    if digest(binary) != baseline["geometrySha256"]:
        raise ValueError("Original geometry does not match the current registry")
    for name, checksum in baseline["assetSha256"].items():
        if digest((SOURCE / name).read_bytes()) != checksum:
            raise ValueError(f"Source bytes do not match current registry: {name}")
    image, painted = corrected_texture(baseline, binary, Image.open(SOURCE / TEXTURE))
    assets = OUT / "source-export"
    assets.mkdir(exist_ok=True)
    image.save(assets / TEXTURE, "WEBP", lossless=True)
    candidate = deepcopy(baseline)
    candidate["assetSha256"][TEXTURE] = digest((assets / TEXTURE).read_bytes())
    candidate["seatingArtworkRevision"] = {
        "baselineAssetVersion": baseline["assetVersion"],
        "baselineManifestSha256": digest(raw), "reference": REFERENCE,
        "scope": "Clean photo-informed FC SCHALKE 04 seat letters through original west lower-tier UVs.",
        "limits": "Photo-informed seat artwork, not an exact surveyed per-seat arrangement.",
        "geometryUnchanged": True,
    }
    candidate.pop("assetVersion")
    candidate["assetVersion"] = digest(json.dumps(candidate, sort_keys=True).encode())[:16]
    from stadium_editor.model_registry import validate_model_manifest
    validate_model_manifest(candidate)
    (OUT / "baseline-manifest.json").write_bytes(raw)
    for name in candidate["assetSha256"]:
        if name != TEXTURE:
            shutil.copyfile(SOURCE / name, assets / name)
    review = OUT / "osm-fresh"
    review.mkdir(exist_ok=True)
    (review / "manifest.json").write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n")
    presentation = json.loads((ROOT / "generated-artifacts/veltins-study/osm-fresh/installed-presentation.json").read_text())
    presentation["presentation"]["assetVersion"] = candidate["assetVersion"]
    presentation["presentation"]["modelUrl"] = f"/models/920/{candidate['assetVersion']}/manifest.json"
    (review / "presentation.json").write_text(json.dumps(presentation))
    (OUT / "texture-check.json").write_text(json.dumps({
        "paintedPixels": int(painted.sum()), "geometryUnchanged": True,
        "fixturesUnchanged": candidate["fixtures"] == baseline["fixtures"],
        "baselineVersion": baseline["assetVersion"], "candidateVersion": candidate["assetVersion"],
    }, indent=2))
    print(f"Prepared {candidate['assetVersion']}; {painted.sum()} lettering pixels.")


def activate():
    from concurrent.futures import ThreadPoolExecutor
    from game.object_storage_backend import get_client
    from stadium_editor.model_registry import model_manifest, validate_model_manifest
    baseline_raw = (OUT / "baseline-manifest.json").read_bytes()
    raw = (OUT / "osm-fresh/manifest.json").read_bytes()
    candidate, baseline = json.loads(raw), json.loads(baseline_raw)
    validate_model_manifest(candidate)
    if REGISTRY.read_bytes() != baseline_raw or candidate["clubFmiId"] != 920:
        raise ValueError("Veltins baseline changed; rebase instead of overwriting")
    presentation = (OUT / "osm-fresh/presentation.json").read_bytes()
    evidence = json.loads((OUT / "osm-fresh/ansichten/render-evidence.json").read_text())
    if ({row["name"] for row in evidence} !=
            {"editor-dach-an", "ticker-tag", "ticker-ohne-dach", "ticker-nacht-flutlicht"}
            or any(row["assetVersion"] != candidate["assetVersion"] or row["errors"]
                   or row["presentationSha256"] != digest(presentation) or row["installed"]
                   for row in evidence)):
        raise ValueError("Matching current editor and ticker renders required")
    if set(candidate) != set(baseline) | {"seatingArtworkRevision"}:
        raise ValueError("Unexpected manifest fields")
    for key in baseline:
        if key not in ("assetVersion", "assetSha256") and candidate[key] != baseline[key]:
            raise ValueError(f"Texture revision must not change {key}")
    if (set(candidate["assetSha256"]) != set(baseline["assetSha256"]) or
            [n for n, h in baseline["assetSha256"].items()
             if candidate["assetSha256"][n] != h] != [TEXTURE]):
        raise ValueError("Only the Veltins crowd texture may change")

    def upload(name):
        data = (OUT / "source-export" / name).read_bytes()
        if digest(data) != candidate["assetSha256"][name]:
            raise ValueError("Candidate checksum mismatch")
        client = get_client()
        key = f"stadium-models/920/{candidate['assetVersion']}/{name}"
        if not client.exists(key):
            client.upload_from_bytes(key, data)
        if digest(client.download_as_bytes(key)) != digest(data):
            raise ValueError("Stored checksum mismatch")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(upload, candidate["assetSha256"]))
    if REGISTRY.read_bytes() != baseline_raw:
        raise ValueError("Concurrent registry update; uploaded assets remain inactive")
    with tempfile.NamedTemporaryFile(dir=REGISTRY.parent, delete=False) as file:
        temporary = Path(file.name)
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    try:
        os.replace(temporary, REGISTRY)
    finally:
        temporary.unlink(missing_ok=True)
    model_manifest.cache_clear()
    print(f"Activated Veltins lettering {candidate['assetVersion']}; no database writes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    if args.activate:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
        import django
        django.setup()
        activate()
    else:
        prepare()
