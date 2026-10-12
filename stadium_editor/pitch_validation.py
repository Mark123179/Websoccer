"""Read-only centreline measurements for centred, cardinal source pitch meshes.

No full-mesh bounding box is used as a field measurement. Cross sections away
from corners must agree on all four narrow boundary bands. Unsupported sources
fail closed; this module never changes or scales geometry.
"""
import hashlib
import math
import struct

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
TOLERANCE_METERS = 0.02
METHOD = "boundary-cross-sections-v1"


class PitchValidationError(ValueError):
    """Safe, human-readable error; contains no storage URLs."""


def _unknown(reason):
    raise PitchValidationError("Spielfeld nicht automatisch messbar: " + reason)


def _triangles(manifest, binary):
    triangles = []
    names = []
    # Only explicitly identified line materials, never grass bounds or names
    # guessed from a large geometry bounding box.
    for mesh in manifest.get("meshes", []):
        parts = [p for p in mesh["parts"]
                 if p.get("material", "").upper() == "000STADIUMLINE"]
        if not parts:
            continue
        names.append(mesh["name"])
        count, offset = mesh["vertexCount"], mesh["positionOffset"]
        if offset < 0 or offset + count * 12 > len(binary):
            _unknown("Positionsdaten der Linien sind unvollständig.")
        vertices = list(struct.iter_unpack("<fff", binary[offset:offset + count * 12]))
        if not all(math.isfinite(n) for v in vertices for n in v):
            _unknown("Linien enthalten nicht endliche Koordinaten.")
        for part in parts:
            start, size = part["indexOffset"], part["indexCount"] * 4
            if start < 0 or start + size > len(binary) or size % 12:
                _unknown("Dreiecksindizes der Linien sind unvollständig.")
            indices = [i[0] for i in struct.iter_unpack("<I", binary[start:start + size])]
            if any(i >= count for i in indices):
                _unknown("Dreiecksindex außerhalb der Liniengeometrie.")
            triangles.extend(tuple((vertices[i][0], vertices[i][2]) for i in indices[j:j+3])
                             for j in range(0, len(indices), 3))
    if not triangles:
        _unknown("Kein unterstütztes Linienmaterial 000STADIUMLINE vorhanden.")
    return triangles, names


def _bands(triangles, axis, cut):
    """Union of filled triangle intersections, including layered line meshes."""
    intervals = []
    other = 1 - axis
    for triangle in triangles:
        hits = []
        for a, b in zip(triangle, (*triangle[1:], triangle[0])):
            if a[other] == b[other]:
                continue
            if min(a[other], b[other]) <= cut <= max(a[other], b[other]):
                t = (cut - a[other]) / (b[other] - a[other])
                hits.append(a[axis] + t * (b[axis] - a[axis]))
        if len(hits) >= 2 and max(hits) - min(hits) > 1e-7:
            intervals.append((min(hits), max(hits)))
    merged = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1] + 0.0001:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    return merged


def _axis_measurement(triangles, axis, cuts):
    sections = [_bands(triangles, axis, cut) for cut in cuts]
    persistent = []
    for lo, hi in sections[0]:
        if not 0.01 <= hi - lo <= 0.25:
            continue
        bands = [(lo, hi)]
        for section in sections[1:]:
            matches = [(a, b) for a, b in section
                       if abs(a - lo) <= 0.002 and abs(b - hi) <= 0.002]
            if len(matches) != 1:
                break
            bands.append(matches[0])
        if len(bands) == len(cuts):
            center = sum((a + b) / 2 for a, b in bands) / len(bands)
            # Halfway line is continuous too, but is not a boundary.
            if abs(center) > 0.01:
                persistent.append({"center": center, "band": [lo, hi]})
    # Ambiguous extra continuous lines are not silently chosen by their bounds.
    if len(persistent) != 2 or persistent[0]["center"] >= 0 or persistent[1]["center"] <= 0:
        _unknown("Vier eindeutige durchgehende Randlinien fehlen; erwartet wird "
                 "ein zentriertes, an X/Z ausgerichtetes Feld in Metern.")
    if abs(persistent[0]["center"] + persistent[1]["center"]) > 0.01:
        _unknown("Randlinien sind nicht um den Quellursprung zentriert.")
    return {"sizeMeters": persistent[1]["center"] - persistent[0]["center"],
            "cutsMeters": list(cuts), "boundaries": persistent}


def measure_pitch(manifest, binary):
    """Measure source world-space line midpoints, independent of grass size."""
    triangles, names = _triangles(manifest, binary)
    # Interior cuts avoid corner arcs and isolated marks behind the goal lines.
    # Try both cardinal orientations, not an expected dimension fit.
    for long_axis in (1, 0):
        try:
            width = _axis_measurement(triangles, 1 - long_axis, (-40, -27, -13, 13, 27, 40))
            length = _axis_measurement(triangles, long_axis, (-27, -23, -13, 13, 23, 27))
            if length["sizeMeters"] <= width["sizeMeters"]:
                continue
            return {"method": METHOD, "geometrySha256": hashlib.sha256(binary).hexdigest(),
                    "lineMeshes": names, "lengthAxis": "z" if long_axis else "x",
                    "lineCenterLengthMeters": length["sizeMeters"],
                    "lineCenterWidthMeters": width["sizeMeters"],
                    "lengthEvidence": length, "widthEvidence": width}
        except PitchValidationError:
            continue
    _unknown("Keine eindeutigen Randlinien an allen Querschnitten; unterstützt werden "
             "zentrierte X/Z-Felder in Metern mit schmalen geometrischen Linien. "
             "Texturfelder, gedrehte oder unbekannte Geometrie benötigen eine Quellprüfung.")


def validate_pitch_geometry(manifest, binary):
    """Registration gate, always recomputed from bytes, never manifest claims."""
    result = measure_pitch(manifest, binary)
    if manifest.get("geometrySha256") != result["geometrySha256"]:
        raise PitchValidationError("Spielfeldprüfung: Geometrie-Prüfsumme stimmt nicht.")
    length, width = result["lineCenterLengthMeters"], result["lineCenterWidthMeters"]
    if abs(length - PITCH_LENGTH) > TOLERANCE_METERS or abs(width - PITCH_WIDTH) > TOLERANCE_METERS:
        raise PitchValidationError(
            f"Abweichende Spielfeldgröße: {length:.3f} × {width:.3f} m; "
            f"erforderlich sind 105 × 68 m (Toleranz {TOLERANCE_METERS:.2f} m). "
            "Keine automatische Skalierung.")
    return result
