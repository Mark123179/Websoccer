"""Read-only, club-keyed photographic surroundings for the admin preview."""
from copy import deepcopy
from pathlib import Path

from django.templatetags.static import static


ROOT = Path(__file__).resolve().parent / "static" / "stadium_editor" / "image_backgrounds"

# Identity is the canonical FM club ID, not the test fixture's home/away club.
BACKGROUND_PAIRS = {
    907: {
        "clubFmId": 907,
        "title": "Signal Iduna Park",
        "model": "dortmund",
        "aspect": 2,
        "referenceSize": [1024, 512],
        # Far left/right, near right/left. Measured white playing-field corners,
        # not the bounds of the stadium or its expansion.
        "pitchCorners": [[421, 245], [604, 245], [621, 358], [403, 358]],
        "pitchHalfSize": [34.080013275146484, 52.95001220703125],
        "pitchY": 0.008346,
        "images": {
            "day": {"file": "907/day.webp", "size": [2688, 1344]},
            "night": {"file": "907/night.webp", "size": [1568, 784]},
        },
    },
}


def load_image_background(club_fm_id):
    """No fallback to another club, ORM write, or runtime image acquisition."""
    if type(club_fm_id) is not int or club_fm_id not in BACKGROUND_PAIRS:
        raise ValueError("Für diesen Verein fehlen die Tag-/Nachtbilder.")
    result = deepcopy(BACKGROUND_PAIRS[club_fm_id])
    for profile, image in result["images"].items():
        if not (ROOT / image["file"]).is_file():
            raise OSError(f"Stadion-Hintergrundbild fehlt: {profile}.")
        image["url"] = static("stadium_editor/image_backgrounds/" + image.pop("file"))
    return result
