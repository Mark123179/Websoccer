"""Read-only source-model presentation; existing design and capacity are retained."""
from copy import deepcopy
import hashlib
import json

from .dortmund_runtime import runtime_presentation

def unity_presentation(stadium, geometry, design, manifest):
    if manifest["clubFmiId"] != stadium.club.fm_inside_id:
        raise ValueError("Stadionmodell gehört nicht zu diesem Verein: clubFmiId.")
    fmi = manifest["clubFmiId"]
    revision = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    presentation = runtime_presentation(stadium, geometry, design)
    presentation.update({
        "renderer": "unity-spatial",
        "modelUrl": f"/stadion/model-assets/{fmi}/{manifest['assetVersion']}/manifest.json?manifest={revision}",
        "stadium": manifest["stadiumName"],
        "clubId": stadium.club_id,
        "clubFmiId": fmi,
        "assetVersion": manifest["assetVersion"],
        "sourceSha256": manifest["sourceSha256"],
        "calibration": deepcopy(manifest["calibration"]),
    })
    presentation["surroundings"].setdefault("heightQuality", "schematic")
    return presentation
