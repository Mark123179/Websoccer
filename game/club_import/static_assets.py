import struct
import zlib
from pathlib import Path
from django.http import FileResponse, Http404, HttpResponse
from django.contrib.staticfiles import finders
from game.asset_urls import assets_root
from .runtime import package_mode

def _chunk(kind, data):
    return struct.pack("!I", len(data)) + kind + data + struct.pack(
        "!I", zlib.crc32(kind + data) & 0xffffffff)


EMPTY_PNG = b"\x89PNG\r\n\x1a\n" + _chunk(
    b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) + _chunk(
    b"IDAT", zlib.compress(b"\0\0\0\0\0")) + _chunk(b"IEND", b"")


def serve(request, name, asset=False):
    if not package_mode() or "\\" in name or name.startswith("/") or ".." in Path(name).parts:
        raise Http404()
    if asset:
        root = Path(assets_root()).resolve()
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise Http404()
    else:
        found = finders.find(name)
        # Django's finder versions may return a list rather than one path.
        if isinstance(found, (list, tuple)):
            found = found[0] if found else None
        path = Path(found) if found else None
    if path is None or not path.is_file():
        if asset and name.startswith("clubs/logos/"):
            return HttpResponse(EMPTY_PNG, content_type="image/png")
        raise Http404()
    return FileResponse(path.open("rb"))
