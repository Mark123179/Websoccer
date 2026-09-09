#!/usr/bin/env python3
"""Synchronize and package the complete Elversberg design handoff."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "exports" / "claude-design-elversberg-handoff"
ARCHIVE = ROOT / "exports" / "claude-design-elversberg-prototyp-handoff.zip"
ARCHIVE_ROOT = "claude-design-elversberg-handoff"

# Package-only source material remains authoritative in PACKAGE_DIR. Files that
# also power the application are always refreshed from their canonical source.
SYNCHRONIZED_FILES = {
    "data/elversberg-live-scene-demo.json": "exports/elversberg-live-scene-demo.json",
    "current-live-mode/live_mode.html": "stadium_editor/templates/stadium_editor/live_mode.html",
    "current-live-mode/live_mode.css": "stadium_editor/static/stadium_editor/live_mode.css",
    "current-live-mode/live_mode.js": "stadium_editor/static/stadium_editor/live_mode.js",
    "match-report-context/match_report.html": "game/templates/game/match_report.html",
    "match-report-context/match_report_v2.css": "game/static/game/css/match_report_v2.css",
    "comparison-dortmund/stadion-live-scene.json": "exports/stadion-live-scene.json",
    "comparison-dortmund/bvb-live-scene.jpg": "screenshots/bvb-live-scene.jpg",
    "source-material/TRANSFORMATION_NOTES.md": (
        "exports/claude-design-elversberg-handoff/TRANSFORMATION_NOTES.md"
    ),
}


def package_files() -> list[Path]:
    return sorted(
        path
        for path in PACKAGE_DIR.rglob("*")
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    )


def synchronize() -> None:
    for package_path, source_path in SYNCHRONIZED_FILES.items():
        source = ROOT / source_path
        destination = PACKAGE_DIR / package_path
        if not source.is_file():
            raise FileNotFoundError(f"Canonical source is missing: {source_path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)


def write_checksums(files: list[Path]) -> None:
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(PACKAGE_DIR).as_posix()}\n")
    (PACKAGE_DIR / "CHECKSUMS.sha256").write_text("".join(lines), encoding="utf-8")


def write_archive() -> None:
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in PACKAGE_DIR.rglob("*") if p.is_file()):
            relative = path.relative_to(PACKAGE_DIR).as_posix()
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{relative}")
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> None:
    synchronize()
    files = package_files()
    write_checksums(files)
    write_archive()
    print(f"Built {ARCHIVE.relative_to(ROOT)} with {len(files) + 1} files.")


if __name__ == "__main__":
    main()