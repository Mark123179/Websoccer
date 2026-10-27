#!/usr/bin/env python3
"""Compare private files locally. Print neither row values nor credentials."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.club_import.live_restart_safety import compare_previews, compare_scenes


def main():
    if len(sys.argv) != 5:
        raise SystemExit("Benötigt: LIVE_PREVIEW RESTORE_PREVIEW LIVE_SCENES RESTORE_SCENES")
    try:
        reports = [json.loads(Path(path).read_text()) for path in sys.argv[1:]]
        compare_previews(*reports[:2])
        compare_scenes(*reports[2:])
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Prüfung fehlgeschlagen: {type(error).__name__}. Private Dateien lokal prüfen.", file=sys.stderr)
        return 1
    print("Sicherung/Restore: Tabellen-Fingerprints, Schutzregeln, Vereinsszenen und Sequenzen identisch.")
    print("Kein Reset ausgeführt oder freigegeben; Import-/Schutzprobe steht separat aus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
