"""Check returned plates and compose diagnostics; never approve by proxy."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from geo_probe_geometry import polygon_mask
from probe_image_evidence import verify_probe_image
from surroundings_contract import (
    background_registration, composite, file_sha, read_json, validate_export,
)

MANUAL_FIELDS = (
    "day_visually_approved", "geographic_structure_reviewed", "stadium_absent",
    "night_layout_reviewed", "expansion_visually_reviewed", "rights_confirmed",
    "reference_limits_accepted",
)


def verify_pack(directory):
    directory = directory.resolve()
    manifest = read_json(directory / "manifest.json")
    if manifest.get("version") != 1:
        raise ValueError("Unsupported pack")
    for filename, sha in manifest["files"].items():
        path = (directory / filename).resolve()
        if not path.is_relative_to(directory) or file_sha(path) != sha:
            raise ValueError(f"Changed pack file: {filename}")
    expected = background_registration(manifest["camera"], manifest["frame"])
    if expected != manifest["background_registration"]:
        raise ValueError("Background registration differs")
    validate_export(manifest["profile"], manifest, manifest["states"][0])
    camera = manifest["camera"]
    for state in manifest["states"]:
        if (state["projection"] != camera["projection"] or state["pose"] != camera["worldInverse"]
                or state["corners"] != camera["corners"]):
            raise ValueError("Manifest camera/state mismatch")
    pitch = np.asarray(Image.open(directory / "03_keep_pitch_mask.png").convert("L")) > 128
    calculated = polygon_mask(camera, [(-52.5, -34), (52.5, -34), (52.5, 34), (-52.5, 34)])
    if not np.array_equal(pitch, calculated):
        raise ValueError("Protected pitch mask belongs to another camera")
    images = {}
    for state in manifest["states"]:
        variant = state.get("variant", "day")
        images[(state["roof"], variant)] = verify_probe_image(directory/"checks", state, manifest["fitted"], "render")
        if variant == "day":
            images[(state["roof"], "silhouette")] = verify_probe_image(directory/"checks", state, manifest["fitted"], "silhouette")
    return manifest, pitch, images


def read_plate(path, size):
    with Image.open(path) as image:
        if image.format not in {"PNG", "JPEG"} or list(image.size) != size:
            raise ValueError("Return must be PNG/JPEG, exact registered dimensions; no resizing")
        if image.getexif().get(274, 1) != 1:
            raise ValueError("Normalize EXIF orientation before returning the plate")
        if "A" in image.getbands() and np.min(np.asarray(image.getchannel("A"))) < 255:
            raise ValueError("Background plate must be opaque")
        return image.convert("RGB")


def structure_check(day, night, max_shift=4):
    """Brightness-insensitive global translation warning, NOT a layout proof."""
    size = (max(16, day.width//4), max(16, day.height//4))
    def edges(image):
        gray = np.asarray(image.convert("L").resize(size), dtype=float)
        gy, gx = np.gradient(gray)
        strength = np.hypot(gx, gy)
        nonzero = strength[strength > .1]
        if len(nonzero) < 100:
            return None
        return strength >= np.percentile(nonzero, 75)
    a, b = edges(day), edges(night)
    if a is None or b is None:
        return {"status": "insufficient_structure", "reason": "Zu wenig Kanten; manuell prüfen."}
    cross = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    magnitude = np.abs(cross)
    normalized = np.divide(cross, magnitude, out=np.zeros_like(cross), where=magnitude > 1e-9)
    corr = np.fft.ifft2(normalized).real
    y, x = np.unravel_index(np.argmax(corr), corr.shape)
    peak = float(corr[y, x])
    secondary = corr.copy()
    # Remove the periodic 7×7 neighborhood of the best peak.
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            secondary[(y+dy) % corr.shape[0], (x+dx) % corr.shape[1]] = 0
    uniqueness = peak/max(1e-9, float(secondary.max()))
    confidence = peak/max(1e-9, float(np.mean(np.abs(corr))))
    dx = x if x <= size[0]//2 else x-size[0]
    dy = y if y <= size[1]//2 else y-size[1]
    shift = [round(dx*day.width/size[0], 2), round(dy*day.height/size[1], 2)]
    reliable = confidence >= 8 and uniqueness >= 1.4
    status = "shift_detected" if reliable and max(map(abs, shift)) > max_shift else "manual_review_required"
    union = np.count_nonzero(a | b)
    return {"status": status, "estimated_alignment_shift_pixels": shift,
            "confidence": round(confidence, 3), "peak_uniqueness": round(uniqueness, 3),
            "edge_agreement": round(float(np.count_nonzero(a & b)/max(1, union)), 4),
            "limits": "Keine automatische Prüfung lokaler Umbauten, exakter Geografie oder Stadionfreiheit."}


def check_expansion(base, expansion, base_images, expansion_images):
    if expansion["club"] != base["club"] or expansion["background_registration"] != base["background_registration"]:
        raise ValueError("Expansion uses another locality/camera; do not regenerate the backdrop to hide it")
    if expansion["camera"] != base["camera"]:
        raise ValueError("Expansion changed field camera")
    if all(np.array_equal(np.asarray(base_images[(r, "silhouette")]) > 128,
                          np.asarray(expansion_images[(r, "silhouette")]) > 128) for r in (True, False)):
        raise ValueError("Expansion silhouettes are identical to Bestand; no changed geometry evidenced")


def review(pack, day_path, night_path, output, manual_path=None, expansion_pack=None):
    manifest, pitch, images = verify_pack(pack)
    day = read_plate(day_path, manifest["camera"]["format"])
    night = read_plate(night_path, manifest["camera"]["format"])
    structure = structure_check(day, night)
    manual = read_json(manual_path) if manual_path else {}
    expansions = None
    if expansion_pack:
        expansion, expansion_pitch, expansion_images = verify_pack(expansion_pack)
        check_expansion(manifest, expansion, images, expansion_images)
        if not np.array_equal(expansion_pitch, pitch):
            raise ValueError("Expansion pitch mask changed")
        expansions = expansion_images
    checks = []
    output.mkdir(parents=True, exist_ok=True)
    for kind, originals in (("bestand", images), ("ausbau", expansions)):
        for time, plate in (("day", day), ("night", night)):
            for roof in (True, False):
                if originals is None:
                    checks.append({"model": kind, "time": time, "roof": roof, "status": "awaiting_expansion_render"})
                    continue
                result = composite(plate, originals[(roof, time)], originals[(roof, "silhouette")], pitch)
                filename = f"{kind}_{'roof' if roof else 'no_roof'}_{time}.png"
                result.save(output / filename)
                checks.append({"model": kind, "time": time, "roof": roof,
                               "status": "diagnostic_composite_created", "file": filename,
                               "protected_pitch_pixels": int(pitch.sum()), "pitch_pixels_exact": True})
    manual_ok = all(manual.get(key) is True for key in MANUAL_FIELDS)
    technical_rejected = structure["status"] == "shift_detected"
    status = ("rejected_structure" if technical_rejected else
              "ready_for_separate_integration_decision" if manual_ok and expansions is not None
              else "awaiting_manual_review_and_or_expansion")
    report = {"status": status, "club": manifest["club"],
              "background_registration": manifest["background_registration"],
              "input_sha256": {"day": file_sha(day_path), "night": file_sha(night_path)},
              "source_quality": manifest["quality"],
              "open_reference_gaps": manifest["profile"]["gaps"],
              "structure": structure, "manual_review": manual,
              "missing_manual_checks": [key for key in MANUAL_FIELDS if manual.get(key) is not True],
              "acceptance_matrix": checks,
              "limitations": ["No AI detector or automatic stadium-absence certification.",
                  "Global shift test does not certify local object geometry.",
                  "Hard threshold silhouette edges: diagnostic composition only.",
                  "No production integration; no visual approval inferred from pixel equality.",
                  "Local provenance checks do not certify freshness of every model dependency."]}
    (output / "review.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--day", type=Path, required=True)
    parser.add_argument("--night", type=Path, required=True)
    parser.add_argument("--manual-review", type=Path)
    parser.add_argument("--expansion-pack", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = review(args.pack, args.day, args.night, args.output, args.manual_review, args.expansion_pack)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "rejected_structure" else 0


if __name__ == "__main__":
    raise SystemExit(main())
