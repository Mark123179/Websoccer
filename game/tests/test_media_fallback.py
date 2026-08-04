"""Regression: /media/-Serving fällt bei Bucket-Miss auf den lokalen MEDIA_ROOT zurück.

Vorgeschichte: Mit aktiviertem Object Storage brach serve_media bei einem im
Bucket fehlenden Objekt sofort mit 404 ab und erreichte den dokumentierten
Filesystem-Fallback (Altbestand aus der Zeit ohne Bucket-Zugriff) nie.
"""
import tempfile
from pathlib import Path
from unittest import mock

from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from game.views_media import serve_media


class _FakeBucket:
    def get_blob(self, name):
        return None  # Objekt existiert im Bucket nicht


class _FakeClient:
    """Simuliert einen funktionierenden Object-Storage-Client mit leerem Bucket."""

    def __init__(self):
        # serve_media greift auf das name-gemangelte Attribut der echten
        # Client-Klasse zu: client._Client__bucket()
        setattr(self, '_Client__bucket', lambda: _FakeBucket())

    def download_as_bytes(self, name):
        raise FileNotFoundError(name)


@override_settings(USE_REPLIT_OBJECT_STORAGE=True)
class MediaBucketMissFallbackTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_bucket_miss_serves_local_media_root_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'showauction' / 'hero'
            d.mkdir(parents=True)
            (d / 'legacy.png').write_bytes(b'PNG-legacy-bytes')
            with override_settings(MEDIA_ROOT=tmp), \
                 mock.patch('game.object_storage_backend.get_client',
                            return_value=_FakeClient()):
                resp = serve_media(
                    self.rf.get('/media/showauction/hero/legacy.png'),
                    'showauction/hero/legacy.png',
                )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'PNG-legacy-bytes')

    def test_miss_in_bucket_and_local_fs_raises_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp), \
                 mock.patch('game.object_storage_backend.get_client',
                            return_value=_FakeClient()):
                with self.assertRaises(Http404):
                    serve_media(
                        self.rf.get('/media/showauction/hero/weg.png'),
                        'showauction/hero/weg.png',
                    )
