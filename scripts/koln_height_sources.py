"""Explicit, cached NRW source acquisition; never used by the live renderer."""
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests
from pyproj import Transformer

OUT = Path("generated-artifacts/koln-study/heights")
WCS = "https://www.wcs.nrw.de/geobasis/wcs_nw_dgm"
LOD = "https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/lod2_gml"


def fetch():
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = json.loads(Path("generated-artifacts/koln-study/osm-fresh/evidence.json").read_text())
    lon, lat = evidence["centerLonLat"]
    transform = Transformer.from_crs(4326, 25832, always_xy=True)
    east, north = transform.transform(lon, lat)
    # Includes the ±800 m catalog and its rotated render ground, not just bowl.
    bounds = [int(east - 1400), int(north - 1400), int(east + 1400), int(north + 1400)]
    tasks = [
        ("dgm-capabilities.xml", WCS, {"SERVICE": "WCS", "VERSION": "2.0.1",
                                     "REQUEST": "GetCapabilities"}),
        ("dgm-description.xml", WCS, {"SERVICE": "WCS", "VERSION": "2.0.1",
                                    "REQUEST": "DescribeCoverage", "COVERAGEID": "nw_dgm"}),
    ]
    # NRW's proxy rejects larger GetCoverage requests with InvalidParameterValue.
    # Explicit 1 km subsets keep native 1 m pixels, no silent lower-resolution retry.
    for x in range(bounds[0]//1000, bounds[2]//1000+1):
        for y in range(bounds[1]//1000, bounds[3]//1000+1):
            tasks.append((f"dgm-{x}-{y}.tif", WCS, [
                ("SERVICE", "WCS"), ("VERSION", "2.0.1"),
                ("REQUEST", "GetCoverage"), ("COVERAGEID", "nw_dgm"),
                ("FORMAT", "image/tiff"),
                ("SUBSETTINGCRS", "http://www.opengis.net/def/crs/EPSG/0/25832"),
                ("SUBSET", f"x({x*1000},{(x+1)*1000})"),
                ("SUBSET", f"y({y*1000},{(y+1)*1000})")]))
    # Catalog footprints are within ±800 m E/N. Download every intersected tile.
    for x in range(int((east-850)//1000), int((east+850)//1000)+1):
        for y in range(int((north-850)//1000), int((north+850)//1000)+1):
            name = f"LoD2_32_{x}_{y}_1_NW.gml"
            tasks.append((name, f"{LOD}/{name}", None))

    def get(task):
        name, url, params = task
        path = OUT / name
        meta_path = path.with_suffix(path.suffix + ".fetch.json")
        if path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
                raise ValueError(f"Source hash mismatch: {name}")
            return meta
        r = requests.get(url, params=params, timeout=180)
        r.raise_for_status()
        if name.endswith(".tif") and not r.content.startswith((b"II", b"MM")):
            raise ValueError(f"Not a GeoTIFF: {r.text[:500]}")
        path.write_bytes(r.content)
        meta = {"file": name, "url": r.url, "retrieved": r.headers.get("Date"),
                "lastModified": r.headers.get("Last-Modified"), "bytes": len(r.content),
                "sha256": hashlib.sha256(r.content).hexdigest()}
        meta_path.write_text(json.dumps(meta, indent=2))
        return meta
    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = list(pool.map(get, tasks))
    (OUT / "sources.json").write_text(json.dumps({
        "provider": "Geobasis NRW", "license": "Datenlizenz Deutschland – Zero 2.0",
        "crs": "EPSG:25832", "verticalDatum": "DHHN2016 / NHN (EPSG:7837)",
        "centerUTM": [east, north], "requestedDgmBounds": bounds, "sources": sources,
    }, indent=2))
    print(json.dumps({"files": len(sources), "bytes": sum(s["bytes"] for s in sources)}))


if __name__ == "__main__":
    fetch()
