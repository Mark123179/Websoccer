from django.core.files.storage import FileSystemStorage, Storage


class ReadOnlyAssetStorage(Storage):
    """Read assets without exposing writable paths through this storage API."""

    def __init__(self, location):
        self._reader = FileSystemStorage(location=location)

    def _open(self, name, mode="rb"):
        if mode not in {"r", "rb"}:
            raise PermissionError("Original pilot assets are read-only.")
        return self._reader.open(name, mode)

    def exists(self, name):
        return self._reader.exists(name)

    def size(self, name):
        return self._reader.size(name)

    def save(self, name, content, max_length=None):
        raise PermissionError("Original pilot assets are read-only.")

    def delete(self, name):
        raise PermissionError("Original pilot assets are read-only.")
