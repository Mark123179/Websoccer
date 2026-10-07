"""Validated, local stadium-environment packages; no ORM or runtime OSM calls."""
from copy import deepcopy
import json
import math
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent / "blueprints/natural"


def validate_natural_package(package):
    if not isinstance(package, dict) or (package.get("schema"), package.get("version"), package.get("units")) != (
        "websoccer.natural-surroundings", 1, "m"
    ):
        raise ValueError("Unbekanntes natürliches Stadionumfeld-Paket.")
    if not all(isinstance(package.get(key), str) and package[key].strip() for key in ("id", "title")):
        raise ValueError("Stadionumfeld benötigt Kennung und Titel.")
    def number(value):
        return type(value) in (int, float) and math.isfinite(value)
    def point(value):
        return isinstance(value, list) and len(value) == 2 and all(number(n) for n in value)
    frame = package.get("frame", {})
    if not point(frame.get("fieldC")) or not number(frame.get("axisTheta")):
        raise ValueError("Ungültige Spielfeldkalibrierung.")
    data = package.get("data")
    if not isinstance(data, dict):
        raise ValueError("Stadionumfeld-Daten fehlen.")
    for key in ("roads", "buildings", "buildingHeights", "green", "water", "trees", "shrubs"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"Ungültige Umfeldliste: {key}.")
    if len(data["buildings"]) != len(data["buildingHeights"]):
        raise ValueError("Gebäude und Höhen müssen übereinstimmen.")
    for key in ("geography", "trees"):
        if not isinstance(data.get("sources", {}).get(key), str) or not data["sources"][key].strip():
            raise ValueError(f"Quellenhinweis fehlt: {key}.")
    for key in ("buildings", "green", "water"):
        for polygon in data[key]:
            if not isinstance(polygon, list) or len(polygon) < 3 or not all(point(p) for p in polygon):
                raise ValueError(f"Ungültiger Grundriss: {key}.")
            area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1]))
            if abs(area) < 1e-8:
                raise ValueError(f"Grundriss ohne Fläche: {key}.")
    if any(not number(h) or h <= 0 for h in data["buildingHeights"]):
        raise ValueError("Gebäudehöhen müssen positiv sein.")
    for road in data["roads"]:
        if not isinstance(road, dict) or not isinstance(road.get("p"), list) or len(road["p"]) < 2:
            raise ValueError("Ungültige Straßenlinie.")
        if not all(point(p) for p in road["p"]) or not number(road.get("w")) or road["w"] <= 0:
            raise ValueError("Ungültige Straßenkoordinaten/-breite.")
        if not any(a != b for a, b in zip(road["p"], road["p"][1:])):
            raise ValueError("Straßenlinie ohne Länge.")
    if not all(point(p) for p in data["trees"] + data["shrubs"]):
        raise ValueError("Ungültige Vegetationsposition.")
    materials = data.get("buildingMaterials")
    if materials is not None and (
        not isinstance(materials, list) or len(materials) != len(data["buildings"])
        or any(m not in ("neutral", "brick") for m in materials)
    ):
        raise ValueError("Ungültige Gebäudematerialzuordnung.")
    if package.get("visualVersion") == 2:
        if frame.get("sceneAxes") != "pitch-west-camera" or frame["fieldC"] != [0, 0] or frame["axisTheta"] != 0:
            raise ValueError("Neue Ortsdaten müssen bereits in Spielfeldmetern vorliegen.")
        detail = data.get("sourceDetail", {})
        if not all(isinstance(detail.get(k), str) and detail[k].strip() for k in ("source", "fetched", "licence")):
            raise ValueError("Ortsdaten benötigen Quelle, Stand und Lizenz.")
        north = detail.get("frame", {}).get("northVector")
        if not point(north) or not 0.95 < math.hypot(*north) < 1.05:
            raise ValueError("Ungültige Nordkalibrierung.")
        for key in ("parking", "forest", "scrub", "sports", "landuse", "buildingsTagged", "grassTagged"):
            features = data.get(key)
            if not isinstance(features, list):
                raise ValueError(f"Kartierte Umfeldliste fehlt: {key}.")
            ids = set()
            for feature in features:
                if not isinstance(feature, dict) or type(feature.get("id")) is not int or feature["id"] in ids:
                    raise ValueError(f"Ungültige oder doppelte Ortskennung: {key}.")
                ids.add(feature["id"])
                polygon = feature.get("poly")
                if not isinstance(polygon, list) or len(polygon) < 3 or not all(point(p) for p in polygon):
                    raise ValueError(f"Ungültige kartierte Fläche: {key}.")
                area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1]))
                if abs(area) < 1e-8:
                    raise ValueError(f"Kartierte Fläche ohne Inhalt: {key}.")
        rows = data.get("treeRows")
        if not isinstance(rows, list) or any(
            not isinstance(r, dict) or not isinstance(r.get("line"), list)
            or len(r["line"]) < 2 or not all(point(p) for p in r["line"]) for r in rows
        ):
            raise ValueError("Ungültige Baumreihen.")
        tree_meta = data.get("treeMetadata")
        if not isinstance(tree_meta, list) or len(tree_meta) != len(data["trees"]) or any(
            not isinstance(t, dict) or type(t.get("id")) is not int or t.get("p") != p
            for t, p in zip(tree_meta, data["trees"])
        ):
            raise ValueError("Einzelbaumdaten und Positionen müssen übereinstimmen.")
        if len({t["id"] for t in tree_meta}) != len(tree_meta):
            raise ValueError("Doppelte Einzelbaumkennung.")
        model = package.get("model", {})
        if type(model.get("mirror")) is not bool or model.get("mirrorAxis") != "longitudinal":
            raise ValueError("Ungültige Modellspiegelung.")
    return package


def load_natural_package(package_id):
    if not isinstance(package_id, str) or not package_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in package_id
    ):
        raise ValueError("Ungültige Stadionpaket-Kennung.")
    path = PACKAGE_DIR / f"{package_id}.json"
    if path.stat().st_size > 2_000_000:
        raise ValueError("Stadionpaket ist zu groß.")
    return deepcopy(validate_natural_package(json.loads(path.read_text(encoding="utf-8"))))
