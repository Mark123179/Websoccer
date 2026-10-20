"""Apply a reviewed roof-only overlay; never restore or replace surroundings."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

PACKAGE = Path("docs/stadium/koln-roof-evidence.json")
ROOF_KEYS = ("roofSurfaces", "roofStatus", "roofRejection", "rejectedRoofEvidence")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def without_roofs(part):
    return {k: v for k, v in part.items() if k not in ROOF_KEYS}


def apply_roof_package(data, package):
    """Fail closed on stale source identity, partitions or vertical reference."""
    result = deepcopy(data)
    contract = result.get("buildingParts", {})
    if (package.get("version") != 1 or contract.get("version") != 1
            or contract.get("referenceNHN") != package.get("referenceNHN")
            or contract.get("verticalDatum") != package.get("verticalDatum")
            or data.get("heightEvidence", {}).get("terrainReferenceNHN") != package.get("referenceNHN")
            or digest(contract_without_roofs(contract)) != package.get("baselinePartsSha256")):
        raise ValueError("Roof overlay needs the unchanged, approved Abelbau/NHN baseline")
    expected = package.get("parts", {})
    found = set()
    for group in contract["groups"]:
        for part in group["parts"]:
            identity = part["lodId"]
            if identity not in expected or identity in found:
                raise ValueError("Missing or duplicate roof source identity")
            found.add(identity)
            addition = expected[identity]
            if not isinstance(addition, dict) or set(addition) - set(ROOF_KEYS):
                raise ValueError("Roof package contains non-roof changes")
            for key in ROOF_KEYS:
                part.pop(key, None)
            part.update(deepcopy(addition))
    if found != set(expected):
        raise ValueError("Unmatched roof source identities")
    from stadium_editor.package_preflight import inspect_package
    report = inspect_package(result)
    if not report["ok"]:
        raise ValueError(f"Invalid roof overlay: {report['findings']}")
    return result


def contract_without_roofs(contract):
    result = deepcopy(contract)
    for group in result.get("groups", []):
        group["parts"] = [without_roofs(p) for p in group["parts"]]
    return result


def install(package):
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django
    django.setup()
    from django.db import transaction
    from stadium_editor.models import StadiumGeometry
    with transaction.atomic():
        row = StadiumGeometry.objects.select_for_update().get(
            stadium__club__fm_inside_id=916, stadium__club__transfermarkt_id=3)
        geometry = deepcopy(row.geometry)
        # Both live projection inputs must already contain the approved parts.
        for key in ("surroundings", "bg"):
            if not isinstance(geometry.get(key), dict):
                raise ValueError(f"Missing approved environment: {key}")
            # Legacy bg.buildings has object wrappers; validate against the
            # unchanged canonical live-surroundings catalog instead.
            canonical = deepcopy(geometry["surroundings"])
            canonical["buildingParts"] = geometry[key].get("buildingParts")
            updated = apply_roof_package(canonical, package)
            geometry[key]["buildingParts"] = updated["buildingParts"]
        from stadium_editor.package_preflight import inspect_package
        report = inspect_package(geometry)
        if not report["ok"]:
            raise ValueError(report)
        row.geometry = geometry
        row.save(update_fields=["geometry", "updated_at"])
    print(json.dumps({"ok": True, "roofOnly": True, "sources": len(package["parts"])}))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--install", action="store_true",
                        help="Apply only to an existing approved DB baseline")
    args = parser.parse_args()
    if not args.install:
        parser.error("Explicit --install required; no automatic database writes")
    install(json.loads(args.package.read_text()))
