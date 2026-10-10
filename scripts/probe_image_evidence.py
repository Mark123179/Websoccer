"""Read and decode only PNG bytes bound to their export-time render context."""
import hashlib
import io
import json

from PIL import Image


def verify_probe_image(directory, state, fitted, role):
    evidence = state.get("imageEvidence", {}).get(role)
    if not evidence or evidence.get("version") != 1:
        raise ValueError(f"Missing image evidence: {state['club']}/{role}; re-export required.")
    context_json = evidence.get("contextJson", "")
    expected = {key: state[key] for key in (
        "club", "roof", "orientation", "projection", "pose", "corners")}
    expected.update(variant=state.get("variant", "day"), role=role,
                    format=fitted["format"], position=fitted["position"])
    if json.loads(context_json) != expected:
        raise ValueError(f"Image context mismatch: {state['club']}/{role}")
    variant = state.get("variant", "day")
    stem = f"{state['club']}_{'roof' if state['roof'] else 'no_roof'}"
    if variant != "day":
        stem += f"_{variant}"
    filename = f"{stem}{'_silhouette' if role == 'silhouette' else ''}.png"
    if evidence.get("file") != filename:
        raise ValueError(f"Image filename mismatch: {state['club']}/{role}")
    data = (directory / filename).read_bytes()
    binding = hashlib.sha256(context_json.encode("utf-8") + b"\0" + data).hexdigest()
    if (hashlib.sha256(data).hexdigest() != evidence.get("sha256")
            or binding != evidence.get("bindingSha256")):
        raise ValueError(f"Image content mismatch: {filename}; stale or swapped export.")
    # Decode the verified snapshot, not a second file read that could race a new export.
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or list(image.size) != fitted["format"]:
            raise ValueError(f"Image format/dimensions mismatch: {filename}")
        return image.convert("L" if role == "silhouette" else "RGB")
