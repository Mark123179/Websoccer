import io
import os

from django.core.files.base import File
from django.core.files.storage import Storage
from django.urls import reverse


def _get_client():
    from replit.object_storage import Client
    return Client()


class ReplitObjectStorage(Storage):

    def _save(self, name, content):
        client = _get_client()
        content.seek(0)
        data = content.read()
        client.upload_from_bytes(name, data)
        return name

    def _open(self, name, mode='rb'):
        client = _get_client()
        data = client.download_as_bytes(name)
        return File(io.BytesIO(data), name=name)

    def exists(self, name):
        client = _get_client()
        return client.exists(name)

    def delete(self, name):
        client = _get_client()
        try:
            client.delete(name)
        except Exception:
            pass

    def url(self, name):
        from django.conf import settings
        return settings.MEDIA_URL + name

    def size(self, name):
        data = self._open(name).read()
        return len(data)

    def listdir(self, path):
        client = _get_client()
        objects = client.list(prefix=path)
        dirs = []
        files = []
        for obj in objects:
            rel = obj.name[len(path):].lstrip('/')
            if '/' in rel:
                d = rel.split('/')[0]
                if d not in dirs:
                    dirs.append(d)
            else:
                files.append(rel)
        return dirs, files
