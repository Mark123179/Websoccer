"""Read-only verification of the offline Elversberg design comparison."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
CAMERA = ROOT / "docs/stadium/surroundings-camera.json"
EXPECTED = {(style, roof) for style in ("spatial", "flat") for roof in (True, False)}


def image_path(directory, name):
    """Output references must remain inside the study directory."""
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("Ungültiger relativer Bildpfad.")
    path = (directory / name).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError("Bildpfad verlässt das Studienverzeichnis.")
    if not path.is_file():
        raise ValueError(f"Bild fehlt: {name}")
    return path


def load_rgb(directory, name, size):
    path = image_path(directory, name)
    with Image.open(path) as image:
        if image.format != "PNG" or image.size != tuple(size):
            raise ValueError(f"Kein natives PNG in {size}: {name}")
        rgba = np.asarray(image.convert("RGBA"))
        if np.any(rgba[:, :, 3] != 255):
            raise ValueError(f"Gesamtansicht ist nicht vollständig deckend: {name}")
        return rgba[:, :, :3].copy()


def canonical_pitch(size, corners):
    mask = Image.new("L", tuple(size))
    ImageDraw.Draw(mask).polygon([(p["x"], p["y"]) for p in corners], fill=255)
    # Discard only the rasterization fringe, not a user-selected pitch sample.
    mask = mask.filter(ImageFilter.MinFilter(5))
    return np.asarray(mask) > 127


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    camera = json.loads(CAMERA.read_text())
    approved = camera["states"][0]
    size = camera["format"]
    if manifest.get("format") != size:
        raise ValueError("Bildformat weicht von der bestätigten Kamera ab.")
    if any(manifest.get("camera", {}).get(key) != approved[key]
           for key in ("projection", "pose", "corners")):
        raise ValueError("Die gemeinsame Kamera wurde verändert.")
    states = manifest.get("states", [])
    identities = [(state.get("style"), state.get("roof")) for state in states]
    if len(states) != 4 or set(identities) != EXPECTED or any(
            type(state.get("roof")) is not bool for state in states):
        raise ValueError("Genau vier eindeutige Stil-/Dachzustände sind erforderlich.")
    pitch = canonical_pitch(size, approved["corners"])
    baselines = {}
    outputs = {}
    results = []
    for state in states:
        if any(state.get(key) != approved[key] for key in ("projection", "pose", "corners")):
            raise ValueError("Ein Zustand verwendet eine abweichende Kamera.")
        result = load_rgb(directory, state["image"], size)
        original = load_rgb(directory, state["baseline"], size)
        with Image.open(image_path(directory, state["fieldMask"])) as image:
            if image.format != "PNG" or image.size != tuple(size):
                raise ValueError("Feldmaske hat ein falsches Format.")
            protected = np.asarray(image.convert("L")) > 127
        if not protected.any() or np.any(pitch & ~protected):
            raise ValueError("Die Feldmaske schützt nicht das vollständige Spielfeld.")
        mismatches = int(np.count_nonzero(np.any(result != original, axis=2) & protected))
        if mismatches:
            raise ValueError(f"Geschützte Feldpixel verändert: {state['image']} ({mismatches})")
        original_hash = hashlib.sha256(original.tobytes()).hexdigest()
        roof = state["roof"]
        if roof in baselines and baselines[roof] != original_hash:
            raise ValueError("Die Stile werden gegen unterschiedliche Originalrender verglichen.")
        baselines[roof] = original_hash
        outputs[(state["style"], roof)] = result
        changed_outside = int(np.count_nonzero(np.any(result != original, axis=2) & ~protected))
        if not changed_outside:
            raise ValueError("Es wurde kein Umfeldentwurf erzeugt.")
        results.append({
            "image": state["image"], "style": state["style"], "roof": roof,
            "protected_pixels": int(protected.sum()), "changed_protected_pixels": mismatches,
            "changed_surroundings_pixels": changed_outside,
            "baseline_rgb_sha256": original_hash,
        })
    if baselines[True] == baselines[False]:
        raise ValueError("Dach an/aus verwenden denselben Originalrender.")
    for roof in (True, False):
        if np.array_equal(outputs[("spatial", roof)], outputs[("flat", roof)]):
            raise ValueError("Räumlicher und flacher Entwurf sind identisch.")
    return {
        "status": "passed", "format": size, "camera_exact": True,
        "states": results,
        "limitations": [
            "Keine visuelle Nutzerabnahme.",
            "Pixelschutz und Kameraparität beweisen keine vermessene Ortsrekonstruktion.",
            "Keine Aussage über Nacht, Ausbau, produktive Integration oder Hardwareleistung.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.directory)
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
