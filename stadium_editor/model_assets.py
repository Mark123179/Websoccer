"""Allowlisted source-model assets, durably stored outside Git."""
from functools import lru_cache
import hashlib
import json
import mimetypes
from pathlib import Path

from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from .gladbach_runtime import MODEL


@lru_cache(maxsize=1)
def model_manifest():
    return json.loads(MODEL.read_text())


@require_GET
def model_asset(request, fmi_id, version, name):
    manifest = model_manifest()
    if fmi_id != 908 or version != manifest["assetVersion"]:
        raise Http404
    allowed = {"manifest.json", "geometry.bin", *manifest["textures"]}
    if name not in allowed:
        raise Http404
    if name == "manifest.json":
        path = MODEL
    else:
        from game.asset_urls import assets_root
        local = Path(assets_root()) / "stadium-models" / "908" / version / name
        cache = Path("/tmp/stadium-model-assets") / version
        cache.mkdir(parents=True, exist_ok=True)
        path = cache / name
        if not path.exists():
            if local.is_file():
                data = local.read_bytes()
            else:
                from game.object_storage_backend import get_client
                data = get_client().download_as_bytes(f"stadium-models/908/{version}/{name}")
            if hashlib.sha256(data).hexdigest() != manifest["assetSha256"][name]:
                raise ValueError("Stadionasset-Prüfsumme stimmt nicht.")
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as tmp:
                tmp.write(data)
                temporary = tmp.name
            os.replace(temporary, path)
    response = FileResponse(path.open("rb"), content_type=
                            mimetypes.guess_type(name)[0] or "application/octet-stream")
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response
