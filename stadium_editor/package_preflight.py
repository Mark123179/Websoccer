"""Local terrain preflight: no Django setup, database, uploads or registration."""
import json
from pathlib import Path
import subprocess

from .surroundings_data import project_surroundings
from .surroundings_ground import validated_ground_fields

RUNNER = Path(__file__).with_name("surroundings_preflight.mjs")
# Fail explicitly on pathological inputs; never return a partial inspection.
CHECK_TIMEOUT_SECONDS = 120
CHECK_HEAP_MIB = 512
MAX_INPUT_BYTES = 128 * 1024 * 1024
_UNSET = object()


def _failure(path, message, code="invalid_package", *, terrain_declared=False):
    return {"ok": False, "terrainDeclared": terrain_declared, "findings": [
        {"severity": "error", "path": path, "code": code, "message": message},
    ]}


def inspect_package(package, *, frame=_UNSET, axes=_UNSET):
    """Accept raw surroundings, a natural/runtime wrapper, or editor geometry.

    Axes must be supplied from the target manifest; defaults match the renderer.
    No club-specific tree enrichment or persistent state is read.
    """
    paths = {}
    prefix = ""
    terrain_declared = False
    try:
        if not isinstance(package, dict):
            return _failure("package", "Das Paket muss ein JSON-Objekt sein.")
        # Editor geometry carries its frame in meta even when no stadium
        # blocks or legacy background were exported. Runtime wrappers use frame.
        if any(key in package for key in ("bg", "blocks", "meta")):
            data, paths = project_surroundings(package, validate_ground=False)
            source_frame = package.get("meta") or {}
            prefix = "surroundings."
        elif "surroundings" in package or "data" in package:
            key = "surroundings" if "surroundings" in package else "data"
            data = package[key]
            prefix = f"{key}."
            source_frame = package.get("frame", {})
        else:
            data, source_frame = package, {}
        if not isinstance(data, dict):
            return _failure(prefix.rstrip(".") or "data", "Umfelddaten müssen ein Objekt sein.")
        terrain_declared = any(key in data for key in ("groundLevel", "groundCutout", "groundElevation"))
        # Python checks happen before Node serialization (bool, huge int, NaN).
        try:
            validated_ground_fields(data)
        except ValueError as error:
            return _failure(f"{prefix}groundLevel/groundCutout", str(error), "invalid_terrain",
                            terrain_declared=terrain_declared)
        payload = {"data": data, "frame": source_frame if frame is _UNSET else frame}
        if axes is not _UNSET:
            payload["axes"] = axes
        raw = json.dumps(payload, allow_nan=False)
        # json.dumps uses ASCII escaping by default, so character count = bytes.
        if len(raw) > MAX_INPUT_BYTES:
            return _failure(
                "renderer", "Prüfpaket überschreitet 128 MiB; vollständige Prüfung nicht ausgeführt.",
                "checker_failed", terrain_declared=terrain_declared,
            )
        result = subprocess.run(
            ["node", f"--max-old-space-size={CHECK_HEAP_MIB}", str(RUNNER)],
            input=raw, text=True, capture_output=True,
            timeout=CHECK_TIMEOUT_SECONDS, check=False,
        )
        if result.returncode:
            return _failure("renderer", "Die lokale Rendererprüfung ist fehlgeschlagen.", "checker_failed",
                            terrain_declared=terrain_declared)
        report = json.loads(result.stdout)
        for finding in report["findings"]:
            path = finding["path"]
            layer = path.split("[")[0]
            if layer in paths and "[" in path:
                index = int(path.split("[")[1].split("]")[0])
                finding["path"] = paths[layer][index]
            elif path != "frame/axes":
                finding["path"] = prefix + path
        return report
    except (OSError, subprocess.TimeoutExpired):
        return _failure("renderer", "Node.js nicht verfügbar oder Prüfzeit überschritten.", "checker_failed",
                        terrain_declared=terrain_declared)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return _failure("package", "Ungültige Paketstruktur oder nicht endliche JSON-Zahlen.",
                        terrain_declared=terrain_declared)


def format_report(report):
    lines = ["Gelände-Paketprüfung: " + ("OK" if report["ok"] else "ABGELEHNT")]
    for finding in report["findings"]:
        label = "FEHLER" if finding["severity"] == "error" else "HINWEIS"
        lines.append(f"{label} {finding['path']}: {finding['message']}")
    if not report["findings"]:
        lines.append("Keine Konflikte mit der deklarierten Geländeaussparung erkannt.")
    lines.append("Nur lesend: keine Quelländerungen, Registrierung oder Uploads.")
    return "\n".join(lines)
