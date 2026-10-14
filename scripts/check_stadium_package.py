"""Read-only local stadium terrain check; input JSON is never imported as code."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stadium_editor.package_preflight import inspect_package, format_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="Lokale JSON-Datei: Umfeld, Runtime-/Natural-Paket oder Editor-Geometrie.")
    parser.add_argument("--manifest", type=Path,
                        help="Lokales Zielmodell-Manifest mit calibration.surroundingsAxes.")
    parser.add_argument("--frame", type=Path, help="Optionaler expliziter fieldC/axisTheta-JSON-Rahmen.")
    parser.add_argument("--json", action="store_true", help="Maschinenlesbarer Bericht auf stdout.")
    options = parser.parse_args(argv)
    try:
        package = json.loads(options.source.read_text(encoding="utf-8"))
        kwargs = {}
        if options.frame:
            kwargs["frame"] = json.loads(options.frame.read_text(encoding="utf-8"))
        if options.manifest:
            manifest = json.loads(options.manifest.read_text(encoding="utf-8"))
            calibration = manifest.get("calibration", {})
            if "surroundingsAxes" in calibration:
                kwargs["axes"] = calibration["surroundingsAxes"]
        report = inspect_package(package, **kwargs)
    except (OSError, ValueError, TypeError, AttributeError):
        report = {"ok": False, "terrainDeclared": False, "findings": [{
            "severity": "error", "path": "input", "code": "invalid_input",
            "message": "Quelldatei, Rahmen oder Manifest nicht lesbar bzw. kein gültiges JSON-Objekt.",
        }]}
    print(json.dumps(report, ensure_ascii=False) if options.json else format_report(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
