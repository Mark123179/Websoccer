"""Offline acquisition of explicitly approved, freely licensed environment assets.

Uses providers' documented download endpoints, not catalogue scraping.
Original downloads live in a cache; only browser derivatives enter static files.
Run after prepare_natural_trees.mjs; no runtime network access is introduced.
"""
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
from urllib.parse import urljoin
from zipfile import ZipFile

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "stadium_editor/static/stadium_editor/natural_assets"
CACHE = Path("/tmp/websoccer-natural-asset-sources")
REVISION = "9eac30e99696b53a85e425d22e51aa0a7501705a"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (Websoccer approved asset preparation)"


def download(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not target.exists():
        response = SESSION.get(url, timeout=120)
        response.raise_for_status()
        target.write_bytes(response.content)
    return target.read_bytes()


def image_file(raw, name, max_size=512):
    image = Image.open(io.BytesIO(raw))
    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    image.save(OUT / name, format="WEBP", quality=85, method=6)
    return name


def prepare(source_dir):
    OUT.mkdir(parents=True, exist_ok=True)
    library = json.loads((OUT / "library.json").read_text())
    assets = []
    textures = {}
    for key, asset, scale in [
        ("asphalt", "Asphalt006", 2),
        ("paving", "PavingStones136", 2),
        ("grass", "Grass001", 2),
        ("bark", "Bark001", 1),
    ]:
        url = f"https://ambientcg.com/get?file={asset}_1K-JPG.zip"
        with ZipFile(io.BytesIO(download(url))) as archive:
            maps = {"sizeMeters": scale}
            for channel, suffix in [("color", "Color"), ("normal", "NormalGL"), ("roughness", "Roughness")]:
                member = next(n for n in archive.namelist() if n.endswith(f"_{suffix}.jpg"))
                maps[channel] = image_file(archive.read(member), f"{key}_{channel}.webp")
        textures[key] = maps
        assets.append({"id": asset, "source": f"https://ambientcg.com/view?id={asset}",
                       "download": url, "license": "CC0-1.0"})
        print("Prepared", asset, flush=True)
    textures["leaves"] = {}
    for leaf in ["oak", "ash", "aspen"]:
        relative = f"src/app/public/textures/leaves/{leaf}.png"
        url = f"https://media.githubusercontent.com/media/dgreenheck/ez-tree/{REVISION}/{relative}"
        raw = download(url)
        # Verify the full Git LFS content against the pinned repository pointer.
        pointer = (source_dir / relative).read_text()
        expected = pointer.split("oid sha256:")[1].splitlines()[0]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"Leaf texture provenance check failed: {leaf}")
        textures["leaves"][leaf] = image_file(raw, f"leaf_{leaf}.webp", 512)
        assets.append({"id": f"leaf_{leaf}", "source": url, "license": "MIT", "sha256": expected})
    for asset in ["brick_wall_02", "overcast_soil_puresky", "shrub_03"]:
        info = json.loads(download(f"https://api.polyhaven.com/files/{asset}"))
        if asset == "brick_wall_02":
            maps = {"sizeMeters": 2}
            for channel, key in [("color", "Diffuse"), ("normal", "nor_gl"), ("roughness", "Rough")]:
                maps[channel] = image_file(download(info[key]["1k"]["jpg"]["url"]), f"brick_{channel}.webp")
            textures["brick"] = maps
        elif asset == "overcast_soil_puresky":
            url = info["hdri"]["1k"]["hdr"]["url"]
            (OUT / "overcast_soil_puresky_1k.hdr").write_bytes(download(url))
            library["sky"] = "overcast_soil_puresky_1k.hdr"
        else:
            model = info["gltf"]["1k"]["gltf"]
            model_dir = OUT / "shrub_03"
            model_dir.mkdir(exist_ok=True)
            (model_dir / "shrub_03.gltf").write_bytes(download(model["url"]))
            for relative, resource in model["include"].items():
                destination = model_dir / relative
                if ".." in destination.relative_to(model_dir).parts:
                    raise ValueError("Unsafe provider resource path.")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(download(resource["url"]))
            library["shrubs"] = {"id": "shrub_03", "file": "shrub_03/shrub_03.gltf",
                                  "placement": "only with geographic/reference evidence"}
        assets.append({"id": asset, "source": f"https://polyhaven.com/a/{asset}", "license": "CC0-1.0"})
        print("Prepared", asset, flush=True)
    library["textures"] = textures
    (OUT / "library.json").write_text(json.dumps(library, separators=(",", ":")))
    shutil.copyfile(source_dir / "LICENSE", OUT / "EZ-Tree-LICENSE.txt")
    shutil.copyfile(source_dir / "src/app/public/textures/LICENSE.md", OUT / "EZ-Tree-texture-attribution.md")
    files = [{"path": str(p.relative_to(OUT)), "bytes": p.stat().st_size,
              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "provenance.json"]
    (OUT / "provenance.json").write_text(json.dumps({
        "schema": "websoccer.asset-provenance", "version": 1,
        "generator": {"source": "https://github.com/dgreenheck/ez-tree", "revision": REVISION,
                      "license": "MIT", "runtimeDependency": False},
        "assets": assets, "files": files,
        "notes": ["CC0 assets allow commercial use and redistribution.",
                  "Leaf textures and generated-tree attribution retain the MIT notice.",
                  "OSM-derived packages have separate ODbL obligations.",
                  "Shrub 03 is prepared but not placed without mapped/reference evidence."],
    }, indent=2))


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
