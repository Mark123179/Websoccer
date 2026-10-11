"""Allowlisted source-model assets, durably stored outside Git."""
import hashlib
import mimetypes
from pathlib import Path

from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from .model_registry import manifest_path, model_manifest


def verified_model_asset(manifest, name, *, cache=True):
    """Retrieve and verify bytes, including cache hits. Read-only when cache=False."""
    fmi, version = manifest["clubFmiId"], manifest["assetVersion"]
    allowed = {"geometry.bin", *manifest["textures"]}
    if name not in allowed:
        raise ValueError("Unbekanntes Stadionasset: name")
    from game.asset_urls import assets_root
    local = Path(assets_root()) / "stadium-models" / str(fmi) / version / name
    directory = Path("/tmp/stadium-model-assets") / str(fmi) / version
    path = directory / name
    if local.is_file():
        data = local.read_bytes()
        source = str(local)
    elif cache and path.is_file():
        data = path.read_bytes()
        source = str(path)
    else:
        from game.object_storage_backend import get_client
        source = f"stadium-models/{fmi}/{version}/{name}"
        data = get_client().download_as_bytes(source)
    if hashlib.sha256(data).hexdigest() != manifest["assetSha256"][name]:
        raise ValueError(f"Stadionasset-Prüfsumme stimmt nicht: {name}")
    if not cache:
        return data, source
    if source == str(local) or source == str(path):
        return (local if source == str(local) else path), source
    import os
    import tempfile
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as tmp:
            temporary = tmp.name
            tmp.write(data)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return path, source


@require_GET
def model_asset(request, fmi_id, version, name):
    manifest = model_manifest(fmi_id)
    if manifest is None or version != manifest["assetVersion"]:
        raise Http404
    allowed = {"manifest.json", "geometry.bin", *manifest["textures"]}
    if name not in allowed:
        raise Http404
    if name == "manifest.json":
        path = manifest_path(fmi_id)
    else:
        path, _ = verified_model_asset(manifest, name)
    response = FileResponse(path.open("rb"), content_type=
                            mimetypes.guess_type(name)[0] or "application/octet-stream")
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response
