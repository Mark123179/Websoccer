"""Register an approved source-model package after verifying durable assets.

No ORM writes. Existing registrations cannot be replaced by this command.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from game.object_storage_backend import get_client
from stadium_editor.model_registry import (
    manifest_path, model_manifest, validate_model_manifest, validate_pitch_geometry,
)
from stadium_editor.pitch_validation import PitchValidationError


def _publish_manifest(target, raw):
    """Publish complete bytes atomically, never replacing an existing entry."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".registration-",
                                         delete=False) as file:
            temporary = Path(file.name)
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        # Unlike replace(), link() fails if another registration won the race.
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != raw:
                raise ValueError("Registrierung besteht bereits; keine automatische Überschreibung.")
    finally:
        if temporary is not None:
            temporary.unlink()


def register(package, fmi):
    raw = (package / "models" / f"{fmi}.json").read_bytes()
    manifest = json.loads(raw)
    validate_model_manifest(manifest)
    if manifest["clubFmiId"] != fmi:
        raise ValueError("Verein passt nicht zur expliziten Ziel-ID.")
    target = manifest_path(fmi)
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Registrierung besteht bereits; keine automatische Überschreibung.")
    assets = package / "stadium-models" / str(fmi) / manifest["assetVersion"]
    names = ["geometry.bin", *manifest["textures"]]
    # Verify the entire package before any storage writes.
    for name in names:
        if hashlib.sha256((assets / name).read_bytes()).hexdigest() != manifest["assetSha256"][name]:
            raise ValueError(f"Asset-Prüfsumme stimmt nicht: {name}")
    measurement = validate_pitch_geometry(manifest, (assets / "geometry.bin").read_bytes())
    print("Spielfeld geprüft: "
          f"{measurement['lineCenterLengthMeters']:.3f} × "
          f"{measurement['lineCenterWidthMeters']:.3f} m (Linienmittelachsen).")

    def store(name):
        client = get_client()
        key = f"stadium-models/{fmi}/{manifest['assetVersion']}/{name}"
        if not client.exists(key):
            data = (assets / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != manifest["assetSha256"][name]:
                raise ValueError(f"Asset-Prüfsumme stimmt nicht: {name}")
            client.upload_from_bytes(key, data)
        if hashlib.sha256(client.download_as_bytes(key)).hexdigest() != manifest["assetSha256"][name]:
            raise ValueError(f"Gespeicherte Asset-Prüfsumme stimmt nicht: {name}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        for index, _ in enumerate(executor.map(store, names), 1):
            if index % 20 == 0 or index == len(names):
                print(f"Assets dauerhaft geprüft: {index}/{len(names)}", flush=True)
    _publish_manifest(target, raw)
    model_manifest.cache_clear()
    print(f"Modell registriert: {fmi} · {manifest['stadiumName']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--fmi", type=int, required=True)
    args = parser.parse_args()
    try:
        register(args.package, args.fmi)
    except PitchValidationError as error:
        print(f"Registrierung abgebrochen: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Storage errors can contain signed URLs: never expose their contents.
        print(f"Registrierung abgebrochen ({type(error).__name__}).", file=sys.stderr)
        sys.exit(1)
