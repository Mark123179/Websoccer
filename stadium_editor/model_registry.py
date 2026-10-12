"""Strict, read-only registry of source models. Invalid entries never register."""
from functools import lru_cache
import json
import logging
import math
from pathlib import Path
import re

from .pitch_validation import validate_pitch_geometry

MODEL_DIR = Path(__file__).parent / "blueprints" / "v2" / "models"
logger = logging.getLogger(__name__)
STANDS = {"NORD", "SUED", "OST", "WEST"}

def validate_model_manifest(manifest):
    """Raise ValueError naming the first missing/invalid field."""
    def require(value, valid, field):
        if not valid(value):
            raise ValueError(f"Ungültiges oder fehlendes Feld: {field}")

    text = lambda v: isinstance(v, str) and bool(v.strip())
    integer = lambda v: type(v) is int and v >= 0
    number = lambda v: type(v) in (int, float) and math.isfinite(v)
    digest = lambda v: isinstance(v, str) and bool(re.fullmatch(r"[0-9a-f]{64}", v))
    filename = lambda v: text(v) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", v))
    vector = lambda v: isinstance(v, list) and len(v) == 3 and all(number(n) for n in v)
    require(manifest, lambda v: isinstance(v, dict), "manifest")
    require(manifest.get("format"), lambda v: v == "unity-mesh-binary-v1", "format")
    require(manifest.get("clubFmiId"), lambda v: integer(v) and v > 0, "clubFmiId")
    for field in ("stadiumName", "source"):
        require(manifest.get(field), text, field)
    for field in ("sourceSha256", "geometrySha256"):
        require(manifest.get(field), digest, field)
    require(manifest.get("assetVersion"), filename, "assetVersion")
    require(manifest.get("textures"), lambda v: isinstance(v, list) and
            all(filename(n) for n in v) and len(v) == len(set(v)) and
            not {"manifest.json", "geometry.bin"} & set(v), "textures")
    require(manifest.get("assetSha256"), lambda v: isinstance(v, dict), "assetSha256")
    for name in ("geometry.bin", *manifest["textures"]):
        require(manifest["assetSha256"].get(name), digest, f"assetSha256.{name}")
    require(manifest["assetSha256"]["geometry.bin"],
            lambda v: v == manifest["geometrySha256"], "geometrySha256")
    require(manifest.get("meshes"), lambda v: isinstance(v, list) and bool(v), "meshes")
    for i, mesh in enumerate(manifest["meshes"]):
        prefix = f"meshes[{i}]"
        require(mesh, lambda v: isinstance(v, dict), prefix)
        require(mesh.get("name"), text, prefix + ".name")
        for field in ("positionOffset", "uvOffset", "vertexCount"):
            require(mesh.get(field), integer, prefix + "." + field)
        require(mesh["vertexCount"], lambda v: v > 0, prefix + ".vertexCount")
        for field in ("positionOffset", "uvOffset"):
            require(mesh[field], lambda v: v % 4 == 0, prefix + "." + field)
        require(mesh.get("parts"), lambda v: isinstance(v, list) and bool(v), prefix + ".parts")
        for j, part in enumerate(mesh["parts"]):
            key = f"{prefix}.parts[{j}]"
            require(part, lambda v: isinstance(v, dict), key)
            require(part.get("color"), vector, key + ".color")
            require(part.get("texture"), lambda v: v is None or v in manifest["textures"], key + ".texture")
            require(part.get("indexOffset"), lambda v: integer(v) and v % 4 == 0, key + ".indexOffset")
            require(part.get("indexCount"), lambda v: integer(v) and v > 0 and v % 3 == 0, key + ".indexCount")
            if "transparent" in part:
                require(part["transparent"], lambda v: type(v) is bool, key + ".transparent")
            if "alphaTest" in part:
                require(part["alphaTest"], lambda v: number(v) and 0 <= v <= 1, key + ".alphaTest")
            if "uvProjection" in part:
                require(part["uvProjection"], lambda v: isinstance(v, list) and
                        len(v) == 8 and all(number(n) for n in v), key + ".uvProjection")
    require(manifest.get("fixtures"), lambda v: isinstance(v, list) and 0 < len(v) <= 12, "fixtures")
    require(manifest.get("verifiedFixtureCount"), lambda v: integer(v) and
            v >= len(manifest["fixtures"]), "verifiedFixtureCount")
    for i, fixture in enumerate(manifest["fixtures"]):
        prefix = f"fixtures[{i}]"
        require(fixture, lambda v: isinstance(v, dict), prefix)
        for field in ("position", "direction", "color"):
            require(fixture.get(field), vector, prefix + "." + field)
        require(fixture["direction"], lambda v: any(n != 0 for n in v), prefix + ".direction")
        for field in ("range", "angle", "intensity", "meshDistance"):
            require(fixture.get(field), number, prefix + "." + field)
        require(fixture["meshDistance"], lambda v: 0 <= v <= 2, prefix + ".meshDistance")
        require(fixture["range"], lambda v: v > 0, prefix + ".range")
        require(fixture["angle"], lambda v: 0 < v < 180, prefix + ".angle")
        require(fixture["intensity"], lambda v: v >= 0, prefix + ".intensity")
        require(fixture.get("representedIds"), lambda v: isinstance(v, list) and bool(v)
                and all(text(n) for n in v), prefix + ".representedIds")
    require(manifest.get("seatView"), lambda v: isinstance(v, dict), "seatView")
    require(manifest["seatView"].get("position"), vector, "seatView.position")
    require(manifest.get("limits"), lambda v: isinstance(v, list) and all(text(n) for n in v), "limits")
    require(manifest.get("sourceEvidence"), lambda v: isinstance(v, dict), "sourceEvidence")
    for name, evidence in manifest["sourceEvidence"].items():
        require(evidence, lambda v: isinstance(v, dict), f"sourceEvidence.{name}")
        require(evidence.get("sha256"), digest, f"sourceEvidence.{name}.sha256")
    require(manifest.get("calibration"), lambda v: isinstance(v, dict), "calibration")
    c = manifest["calibration"]
    if "roofMeshPrefixes" in c:
        require(c["roofMeshPrefixes"], lambda v: isinstance(v, list) and all(text(n) for n in v),
                "calibration.roofMeshPrefixes")
    for field in ("roofMinHeight", "tickerRotationY"):
        require(c.get(field), number, "calibration." + field)
    require(c.get("skipMeshPrefixes"), lambda v: isinstance(v, list) and all(text(n) for n in v),
            "calibration.skipMeshPrefixes")
    for field in ("crowdPrefix", "pitchPrefix"):
        require(c.get(field), text, "calibration." + field)
    require(c.get("tickerFrontCut"), lambda v: isinstance(v, dict), "calibration.tickerFrontCut")
    require(c["tickerFrontCut"].get("normal"), lambda v: vector(v) and any(n != 0 for n in v),
            "calibration.tickerFrontCut.normal")
    require(c["tickerFrontCut"].get("constant"), number, "calibration.tickerFrontCut.constant")
    require(c.get("standAxes"), lambda v: isinstance(v, dict), "calibration.standAxes")
    for axis in ("+x", "-x", "+z", "-z"):
        require(c["standAxes"].get(axis), lambda v: isinstance(v, str) and v in STANDS,
                "calibration.standAxes." + axis)
    require(list(c["standAxes"].values()), lambda v: len(v) == 4 and set(v) == STANDS,
            "calibration.standAxes")
    require(c.get("orbitDefault"), lambda v: isinstance(v, dict), "calibration.orbitDefault")
    for field in ("azimuth", "elevation", "distance"):
        require(c["orbitDefault"].get(field), number, "calibration.orbitDefault." + field)
    require(c["orbitDefault"]["distance"], lambda v: v > 0, "calibration.orbitDefault.distance")


def manifest_path(fmi_id):
    if type(fmi_id) is not int or fmi_id <= 0:
        raise ValueError("Ungültiges Feld: clubFmiId")
    return MODEL_DIR / f"{fmi_id}.json"


@lru_cache(maxsize=128)
def model_manifest(fmi_id):
    try:
        path = manifest_path(fmi_id)
        if not path.is_file():
            return None
        manifest = json.loads(path.read_text(encoding="utf-8"))
        validate_model_manifest(manifest)
        if manifest["clubFmiId"] != fmi_id:
            raise ValueError("clubFmiId passt nicht zum Dateinamen")
        return manifest
    except (OSError, ValueError) as error:
        logger.warning("Stadionmodell %r nicht registriert: %s", fmi_id, error)
        return None


def registered_fmi_ids():
    return sorted({int(p.stem) for p in MODEL_DIR.glob("*.json")
                   if p.stem.isdecimal() and p.stem == str(int(p.stem))
                   and model_manifest(int(p.stem)) is not None})
