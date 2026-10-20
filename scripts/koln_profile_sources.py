"""Read-only native DGM oracle. Pixel-centred interpolation, never gap filling."""
from contextlib import ExitStack
import hashlib
import math

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.merge import merge


def model_projection(presentation, evidence, sources):
    lon, lat = evidence["centerLonLat"]
    transform = Transformer.from_crs(4326, 25832, always_xy=True)
    if math.dist(transform.transform(lon, lat), sources["centerUTM"]) > .01:
        raise ValueError("DGM acquired for a different pitch centre")
    if (presentation["frame"]["fieldC"] != [0, 0] or
            presentation["calibration"]["surroundingsAxes"] != {"NORD": "+z", "WEST": "-x"} or
            abs(math.degrees(presentation["frame"]["axisTheta"]) -
                evidence["axisThetaDegrees"]) > 1e-8):
        raise ValueError("Unsupported/changed Cologne model registration")
    theta = presentation["frame"]["axisTheta"]
    scale = 6371000 * math.pi / 180

    def project(x, z):
        east = z * math.cos(theta) + x * math.sin(theta)
        north = z * math.sin(theta) - x * math.cos(theta)
        return transform.transform(lon + east / (scale * math.cos(math.radians(lat))),
                                   lat + north / scale)
    return project


class NativeDGM:
    def __init__(self, directory, sources, project):
        self.project = project
        items = [s for s in sources["sources"] if s["file"].endswith(".tif")]
        if not items:
            raise ValueError("No native GeoTIFF sources declared")
        with ExitStack() as stack:
            datasets = []
            for item in items:
                path = directory / item["file"]
                if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError(f"Source hash mismatch: {item['file']}")
                ds = stack.enter_context(rasterio.open(path))
                if (ds.crs is None or ds.crs.to_epsg() != 25832 or ds.res != (1., 1.) or ds.count != 1
                        or ds.transform.b != 0 or ds.transform.d != 0):
                    raise ValueError("Expected north-up native 1 m EPSG:25832 DGM")
                datasets.append(ds)
            raster, self.affine = merge(datasets, masked=True)
            self.values = raster[0]
        self.sources = items

    def __call__(self, x, z):
        col, row = (~self.affine) * self.project(x, z)
        col, row = col - .5, row - .5
        i, j = math.floor(col), math.floor(row)
        if i < 0 or j < 0 or i + 1 >= self.values.shape[1] or j + 1 >= self.values.shape[0]:
            raise ValueError(f"DGM coverage missing at model X/Z {x}, {z}")
        window = self.values[j:j+2, i:i+2]
        if np.ma.getmaskarray(window).any() or not np.isfinite(window).all():
            raise ValueError(f"DGM nodata at model X/Z {x}, {z}; no replacement allowed")
        a, b = col-i, row-j
        return float(window[0, 0]*(1-a)*(1-b) + window[0, 1]*a*(1-b) +
                     window[1, 0]*(1-a)*b + window[1, 1]*a*b)
