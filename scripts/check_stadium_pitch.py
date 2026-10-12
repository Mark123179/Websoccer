"""Reproduce source pitch measurements without database/storage writes."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stadium_editor.pitch_validation import PitchValidationError, validate_pitch_geometry


def check_controls():
    """Use durable originals, not ignored evidence from another workspace."""
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    from game.object_storage_backend import get_client
    from stadium_editor.model_registry import model_manifest

    models = []
    for fmi in (901, 907, 908, 915):
        if fmi == 907:
            source = ROOT / "stadium_editor/static/stadium_editor/dortmund_original"
            manifest = json.loads((source / "manifest.json").read_text())
            binary = (source / "geometry.bin").read_bytes()
            # The legacy original has no registry hash field.
            import hashlib
            manifest["geometrySha256"] = hashlib.sha256(binary).hexdigest()
        else:
            manifest = model_manifest(fmi)
            if manifest is None:
                raise PitchValidationError(f"Kontrollmodell {fmi} fehlt in der Registry.")
            key = f"stadium-models/{fmi}/{manifest['assetVersion']}/geometry.bin"
            binary = get_client().download_as_bytes(key)
        models.append({"clubFmiId": fmi, **validate_pitch_geometry(manifest, binary)})
    return {"status": "passed", "models": models}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--controls", action="store_true",
                        help="Vier Originalmodelle neu messen (Registry/App Storage, nur lesend).")
    args = parser.parse_args()
    if args.controls and (args.manifest or args.geometry):
        parser.error("--controls nicht mit Einzeldateien kombinieren.")
    if not args.controls and not (args.manifest and args.geometry):
        parser.error("--manifest und --geometry sind gemeinsam erforderlich.")
    try:
        if args.controls:
            result = check_controls()
        else:
            manifest = json.loads(args.manifest.read_text())
            # Standalone legacy exports can be measured too. Registration always
            # requires and verifies the declared digest.
            binary = args.geometry.read_bytes()
            if "geometrySha256" not in manifest:
                import hashlib
                manifest["geometrySha256"] = hashlib.sha256(binary).hexdigest()
            result = validate_pitch_geometry(manifest, binary)
    except Exception as error:
        message = str(error) if isinstance(error, PitchValidationError) else "Quelldateien fehlen oder sind ungültig."
        print(json.dumps({"status": "failed", "message": message}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "passed", **result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
