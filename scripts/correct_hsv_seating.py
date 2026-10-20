"""HSV-only seating artwork, projected through the original crowd UV triangles.

No geometry or game-data changes. Preparation is offline; --activate explicitly
uploads a new immutable asset version and switches the HSV registry only.
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
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "stadium_editor/blueprints/v2/models/947.json"
SOURCE = ROOT / "generated-artifacts/hsv-study/source-export"
OUT = ROOT / "generated-artifacts/hsv-seating-correction"
TEXTURE = "texture--8009233366261755537.webp"
SIZE = 2048
# Angular, deliberately seat-sized letters rather than a stretched font decal.
LETTERS = {
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "V": ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def artwork(z, y):
    """Photo layout: lower central diamond, middle HSV, two upper diamonds."""
    # Quantize the artwork to seat columns/rows, not arbitrary brush strokes.
    z = np.floor(z / .52) * .52 + .26
    y = np.floor(y / .32) * .32 + .16
    white = np.zeros(z.shape, dtype=bool)
    black = np.zeros(z.shape, dtype=bool)
    for center, height, half_width, half_height in (
        (0, 5.8, 12.5, 3.2), (-43, 28.3, 10.5, 3.8), (43, 28.3, 10.5, 3.8)
    ):
        radius = np.abs(z - center) / half_width + np.abs(y - height) / half_height
        white |= radius <= 1
        # Ratios match the existing canonical HSV crest (947.png).
        black |= radius <= .62
        white |= radius <= .21
        black &= radius > .21
    # The pitch-facing view looks along +x; positive z is left on this stand.
    for letter, center in zip("HSV", (35, 0, -35), strict=True):
        col = np.floor((center + 6.5 - z) / 2.6).astype(int)
        row = np.floor((19.5 - y) / 1.02).astype(int)
        inside = (col >= 0) & (col < 5) & (row >= 0) & (row < 7)
        bitmap = np.array([[int(cell) for cell in line] for line in LETTERS[letter]])
        white |= inside & (bitmap[np.clip(row, 0, 6), np.clip(col, 0, 4)] == 1)
    return white & ~black, black


def corrected_texture(manifest, binary, original):
    """Rasterize only the original front-stand triangles, preserving other sides."""
    pixels = np.array(original.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS))
    painted = np.zeros((SIZE, SIZE), dtype=bool)
    for mesh in manifest["meshes"]:
        if not mesh["name"].startswith("C_front1_"):
            continue
        vertices = np.frombuffer(binary, "<f4", count=mesh["vertexCount"] * 3,
                                 offset=mesh["positionOffset"]).reshape(-1, 3)
        uv = np.frombuffer(binary, "<f4", count=mesh["vertexCount"] * 2,
                           offset=mesh["uvOffset"]).reshape(-1, 2)
        for part in mesh["parts"]:
            if part.get("texture") != TEXTURE:
                continue
            indices = np.frombuffer(binary, "<u4", count=part["indexCount"],
                                    offset=part["indexOffset"]).reshape(-1, 3)
            for triangle in indices:
                coords = uv[triangle] * SIZE
                low = np.maximum(0, np.floor(coords.min(0)).astype(int) - 1)
                high = np.minimum(SIZE - 1, np.ceil(coords.max(0)).astype(int) + 1)
                xx, yy = np.meshgrid(np.arange(low[0], high[0] + 1),
                                     np.arange(low[1], high[1] + 1))
                matrix = np.vstack((coords.T, np.ones(3)))
                if abs(np.linalg.det(matrix)) < 1e-8:
                    continue
                weights = np.linalg.solve(
                    matrix, np.stack((xx.ravel() + .5, yy.ravel() + .5,
                                      np.ones(xx.size))))
                inside = (weights >= -1e-5).all(0)
                world = weights.T @ vertices[triangle]
                z, y = world[:, 2], world[:, 1]
                # Bright blue plastic seats, separated by narrow row/seat gaps.
                gaps = ((z % .52) < .035) | ((y % .32) < .045)
                colors = np.tile([16, 104, 181], (len(z), 1))
                white, black = artwork(z, y)
                colors[white] = [238, 242, 245]
                colors[black] = [14, 18, 22]
                colors[gaps] = (colors[gaps] * .57).astype(int)
                x, v = xx.ravel()[inside], yy.ravel()[inside]
                pixels[v, x] = colors[inside]
                painted[v, x] = True
    if painted.sum() < 100_000:
        raise ValueError("Insufficient original front-stand UV coverage")
    return Image.fromarray(pixels), painted


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    baseline_raw = REGISTRY.read_bytes()
    baseline = json.loads(baseline_raw)
    binary = (SOURCE / "geometry.bin").read_bytes()
    if digest(binary) != baseline["geometrySha256"]:
        raise ValueError("Original geometry does not match the current registry")
    for name, checksum in baseline["assetSha256"].items():
        if digest((SOURCE / name).read_bytes()) != checksum:
            raise ValueError(f"Source bytes no longer match current registry: {name}")
    image, painted = corrected_texture(baseline, binary, Image.open(SOURCE / TEXTURE))
    texture_path = OUT / TEXTURE
    image.save(texture_path, format="WEBP", lossless=True)
    candidate = deepcopy(baseline)
    candidate["assetSha256"][TEXTURE] = digest(texture_path.read_bytes())
    candidate["seatingArtworkRevision"] = {
        "baselineAssetVersion": baseline["assetVersion"],
        "baselineManifestSha256": digest(baseline_raw),
        "reference": "attached_assets/image_1792501216666.png",
        "scope": "Original C_front1_ UV triangles only; photo-based seat artwork, not a seat survey.",
        "geometryUnchanged": True,
    }
    candidate.pop("assetVersion")
    candidate["assetVersion"] = digest(json.dumps(candidate, sort_keys=True).encode())[:16]
    from stadium_editor.model_registry import validate_model_manifest
    validate_model_manifest(candidate)
    (OUT / "baseline-manifest.json").write_bytes(baseline_raw)
    review = OUT / "osm-fresh"
    review.mkdir(exist_ok=True)
    (review / "manifest.json").write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n")
    assets = OUT / "source-export"
    assets.mkdir(exist_ok=True)
    for name in candidate["assetSha256"]:
        shutil.copyfile(texture_path if name == TEXTURE else SOURCE / name, assets / name)
    presentation = json.loads((ROOT / "generated-artifacts/hsv-study/osm-fresh/presentation.json").read_text())
    presentation["presentation"]["assetVersion"] = candidate["assetVersion"]
    presentation["presentation"]["modelUrl"] = f"/models/947/{candidate['assetVersion']}/manifest.json"
    (review / "presentation.json").write_text(json.dumps(presentation))
    (OUT / "texture-check.json").write_text(json.dumps({
        "paintedPixels": int(painted.sum()), "geometryUnchanged": True,
        "fixturesUnchanged": candidate["fixtures"] == baseline["fixtures"],
        "baselineVersion": baseline["assetVersion"], "candidateVersion": candidate["assetVersion"],
    }, indent=2))
    print(f"Prepared {candidate['assetVersion']}; {painted.sum()} corrected front-stand pixels.")


def activate():
    from concurrent.futures import ThreadPoolExecutor
    from game.object_storage_backend import get_client
    from stadium_editor.model_registry import model_manifest, validate_model_manifest
    baseline_raw = (OUT / "baseline-manifest.json").read_bytes()
    raw = (OUT / "osm-fresh/manifest.json").read_bytes()
    candidate = json.loads(raw)
    validate_model_manifest(candidate)
    if REGISTRY.read_bytes() != baseline_raw:
        raise ValueError("HSV registry changed since preparation; rebase instead of overwriting")
    evidence = json.loads((OUT / "osm-fresh/ansichten/render-evidence.json").read_text())
    if ({row["name"] for row in evidence} != {"editor-dach-an", "ticker-tag"}
            or any(row["assetVersion"] != candidate["assetVersion"] or row["errors"]
                   for row in evidence)):
        raise ValueError("Matching editor and ticker render evidence is required before activation")
    baseline = json.loads(baseline_raw)
    if candidate["clubFmiId"] != 947:
        raise ValueError("This correction is exclusively for HSV")
    for key in baseline:
        if key not in ("assetVersion", "assetSha256") and candidate[key] != baseline[key]:
            raise ValueError(f"Texture revision must not change {key}")
    changes = [name for name, checksum in baseline["assetSha256"].items()
               if checksum != candidate["assetSha256"].get(name)]
    if set(candidate["assetSha256"]) != set(baseline["assetSha256"]) or changes != [TEXTURE]:
        raise ValueError("Only the HSV crowd texture may change")

    def upload(name):
        data = (OUT / "source-export" / name).read_bytes()
        if digest(data) != candidate["assetSha256"][name]:
            raise ValueError(f"Candidate checksum mismatch: {name}")
        client = get_client()
        key = f"stadium-models/947/{candidate['assetVersion']}/{name}"
        if not client.exists(key):
            client.upload_from_bytes(key, data)
        if digest(client.download_as_bytes(key)) != digest(data):
            raise ValueError("Stored asset checksum mismatch")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(upload, candidate["assetSha256"]))
    if REGISTRY.read_bytes() != baseline_raw:
        raise ValueError("Concurrent registry update; uploaded assets remain inactive")
    # An explicit, HSV-only revision; generic registration remains insert-only.
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
    print(f"Activated HSV texture revision {candidate['assetVersion']}; no database writes.")


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
