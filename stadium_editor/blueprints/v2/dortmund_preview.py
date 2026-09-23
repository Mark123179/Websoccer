"""Read-only Dortmund review scene from the supplied, measured reference package.

This is deliberately separate from the reviewed V2 import reference. Never use
this module as an implicit replacement for a stored StadiumGeometry/Design.
"""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


PACKAGE = Path(__file__).resolve().parents[3] / 'attached_assets' / 'stadium_stage_replit_paket_1790159390136.zip'
MEMBER = 'scenes/bvb_v2.json'
SHA256 = '5a0f4ba2f4474f1bfa86710e518feb6f1014b6b43748d36e1f0dd411de68fa3c'


def load_preview():
    with ZipFile(PACKAGE) as archive:
        info = archive.getinfo(MEMBER)
        if info.file_size > 256 * 1024:
            raise ValueError('Die Dortmunder Vorschauquelle ist zu groß.')
        data = archive.read(info)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Die Dortmunder Vorschauquelle wurde verändert.')
    scene = json.loads(data)
    if (scene.get('schema'), scene.get('version'), scene.get('stadium')) != (
        'websoccer.stadium-live-scene', 1, 'Signal Iduna Park'
    ):
        raise ValueError('Die Dortmunder Vorschauquelle hat ein unbekanntes Format.')
    return scene