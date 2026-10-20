"""Explicitly approved, hash-pinned HSV revision; no ORM or deployment operations.

The ordinary registration command deliberately continues to reject replacements.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from game.object_storage_backend import get_client
from scripts.report_hsv_lights import verify
from stadium_editor.model_registry import manifest_path, model_manifest

BASELINE_SHA = "8736869c7f78320ead82226281cbe99e67154456b4549166c37cc3daa20357f4"
CANDIDATE_SHA = "efa5689a0da72e0f1cad21b6b809bb9e74cf4b6209a588287eb399944a07a7d0"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require_baseline(target, expected_sha=None):
    raw = target.read_bytes()
    if sha(raw) != (expected_sha or BASELINE_SHA):
        raise ValueError("HSV-Ausgangsmanifest weicht ab; Aktivierung abgebrochen.")
    return raw


def store_verified(client, key, data):
    """Never replace an existing object, including a conflicting partial upload."""
    if not client.exists(key):
        client.upload_from_bytes(key, data)
    if sha(client.download_as_bytes(key)) != sha(data):
        raise ValueError("Dauerhaft gespeicherte HSV-Datei weicht ab.")


def switch_registry(target, raw, *, expected_sha=None):
    """Serialize activations and recheck the baseline immediately before replace."""
    directory = os.open(target.parent, os.O_RDONLY)
    temporary = None
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        require_baseline(target, expected_sha)
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".hsv-", delete=False) as file:
            temporary = Path(file.name)
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        require_baseline(target, expected_sha)
        os.replace(temporary, target)
        os.fsync(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        os.close(directory)


def activate(study, *, approved=False):
    if not approved:
        raise ValueError("Ausdrückliche Nutzerfreigabe erforderlich.")
    target = manifest_path(947)
    baseline_raw = require_baseline(target)  # Before any storage access.
    candidate_raw = (study / "manifest.json").read_bytes()
    if sha(candidate_raw) != CANDIDATE_SHA:
        raise ValueError("Kandidat ist nicht das ausdrücklich freigegebene Paket.")
    # The auditor reserializes its baseline snapshot (Unicode/whitespace); the
    # original registry bytes remain pinned separately and are archived verbatim.
    if json.loads((study / "baseline-manifest.json").read_bytes()) != json.loads(baseline_raw):
        raise ValueError("Prüfbelege gehören nicht zum Ausgangsmanifest.")
    _, baseline, candidate, _, _ = verify(study)
    if (baseline["assetVersion"], candidate["assetVersion"]) != (
            "26bbf1d9b445d255", "fdea273ea50e8748"):
        raise ValueError("Unerwartete HSV-Version.")
    old_prefix = f"stadium-models/947/{baseline['assetVersion']}"
    new_prefix = f"stadium-models/947/{candidate['assetVersion']}"
    assets = study / "package" / new_prefix
    names = ["geometry.bin", *candidate["textures"]]

    def check_old(name):
        data = get_client().download_as_bytes(f"{old_prefix}/{name}")
        if sha(data) != baseline["assetSha256"][name]:
            raise ValueError("Bisheriges dauerhaftes HSV-Asset weicht ab.")

    def store_new(name):
        data = (assets / name).read_bytes()
        if sha(data) != candidate["assetSha256"][name]:
            raise ValueError("Lokales HSV-Asset wurde während der Prüfung verändert.")
        store_verified(get_client(), f"{new_prefix}/{name}", data)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(check_old, names))
        list(pool.map(store_new, names))
        list(pool.map(check_old, names))
    # Retain both exact manifests independently of the mutable registry.
    client = get_client()
    for manifest, raw in ((baseline, baseline_raw), (candidate, candidate_raw)):
        key = f"stadium-model-revisions/947/{manifest['assetVersion']}/manifest.json"
        store_verified(client, key, raw)
    switch_registry(target, candidate_raw)
    model_manifest.cache_clear()
    print(json.dumps({
        "clubFmiId": 947, "assetVersion": candidate["assetVersion"],
        "baselineManifestSha256": sha(baseline_raw),
        "activeManifestSha256": sha(target.read_bytes()),
        "newAssetsReadBack": len(names), "oldAssetsVerifiedUnchanged": len(names),
        "reviewedRenderStates": 8, "databaseWrites": 0,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--approved", action="store_true",
                        help="Only after explicit user approval of this exact HSV candidate.")
    args = parser.parse_args()
    try:
        activate(args.study, approved=args.approved)
    except Exception as error:
        # Storage exceptions can contain signed URLs; never log their contents.
        print(f"HSV-Aktivierung abgebrochen ({type(error).__name__}).", file=sys.stderr)
        sys.exit(1)
