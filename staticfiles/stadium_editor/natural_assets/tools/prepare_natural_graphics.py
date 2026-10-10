#!/usr/bin/env python3
"""Safely stage the supplied Sketchfab source ZIPs, bake tree atlases, then trim build-only trees."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ASSET_ROOT = HERE.parent
WORKSPACE = ASSET_ROOT.parents[3]
ATTACHED = WORKSPACE / "attached_assets"
PACKS = {
    "realistic_trees_collection": "0_realistic_trees_collection_1791402300204.zip",
    "oak_trees": "0_oak_trees_1791402346802.zip",
    "various_forest_assets_pack": "0_various_forest_assets_pack_1791402358022.zip",
    "generic_passenger_car_pack": "0_generic_passenger_car_pack_1791402365987.zip",
}
BUILD_ONLY = ("realistic_trees_collection", "oak_trees", "various_forest_assets_pack")


def stage_archive(name: str, archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            raw = PurePosixPath(entry.filename)
            if raw.is_absolute() or ".." in raw.parts:
                raise ValueError(f"Unsafe ZIP path in {archive.name}: {entry.filename}")
            if entry.is_dir():
                continue
            relative = Path(*raw.parts)
            if relative.as_posix() not in {"scene.gltf", "scene.bin", "license.txt"} and \
                    not relative.as_posix().startswith("textures/"):
                continue
            target = (destination / relative).resolve()
            if destination.resolve() not in target.parents:
                raise ValueError(f"ZIP entry escapes destination: {entry.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as input_file, target.open("wb") as output_file:
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
    print(f"Staged verified relative paths for {name}: {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-source", action="store_true",
                        help="retain the extracted tree build inputs after baking")
    args = parser.parse_args()
    models = ASSET_ROOT / "models"
    for name, filename in PACKS.items():
        archive = ATTACHED / filename
        if not archive.is_file():
            raise FileNotFoundError(f"Supplied source archive is not available: {archive}")
        stage_archive(name, archive, models / name)
    baker = HERE / "bake_impostor_atlases.mjs"
    try:
        subprocess.run(["node", str(baker)], cwd=WORKSPACE, check=True)
    finally:
        if not args.keep_source:
            for name in BUILD_ONLY:
                shutil.rmtree(models / name, ignore_errors=True)
            print("Removed extracted tree build inputs; source ZIPs remain untouched.")
    print("Six 2048px, 8×8 hemi-octa alpha-WebP atlases prepared. Car glTF remains for local runtime instancing.")


if __name__ == "__main__":
    main()
