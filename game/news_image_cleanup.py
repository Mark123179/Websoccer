"""Opt-in news-image garbage collection. No upload or automatic cleanup hooks."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
import json
import os
from pathlib import Path
import posixpath
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.utils import timezone

from .models import ClubNewsItem
from .news_image_storage import BACKUP_PREFIX


IMAGE_PREFIX = 'news-images/'
MIN_AGE_DAYS = 7


class CleanupUnsafe(Exception):
    """An incomplete inventory must never be treated as an empty inventory."""


@dataclass(frozen=True)
class StoredImage:
    name: str
    changed_at: datetime
    revision: object


def safe_name(name, prefix):
    return (
        isinstance(name, str) and name.startswith(prefix) and '\\' not in name
        and all(part not in {'', '.', '..'} for part in name.split('/'))
    )


class LocalNewsStore:
    label = 'local'

    def __init__(self, storage):
        self.storage = storage
        self.root = Path(storage.location).resolve()

    def path(self, name):
        if not (safe_name(name, IMAGE_PREFIX) or safe_name(name, BACKUP_PREFIX)):
            raise CleanupUnsafe('Unsicherer Speicherpfad.')
        path = self.root / name
        # Do not follow links, including links in parent directories.
        for part in (path, *path.parents):
            if part == self.root:
                break
            if part.is_symlink():
                raise CleanupUnsafe('Symbolischer Link im News-Speicher.')
        return path

    def names(self, prefix):
        directory = self.root / prefix.rstrip('/')
        if directory.is_symlink():
            raise CleanupUnsafe('Symbolischer Link im News-Speicher.')
        if not directory.exists():
            return []
        names = []
        for parent, dirs, files in os.walk(directory, followlinks=False, onerror=self.walk_error):
            for child in dirs + files:
                path = Path(parent) / child
                if path.is_symlink():
                    raise CleanupUnsafe('Symbolischer Link im News-Speicher.')
            names.extend((Path(parent) / file).relative_to(self.root).as_posix() for file in files)
        return sorted(names)

    @staticmethod
    def walk_error(error):
        raise error

    def metadata(self, name):
        stat = self.path(name).stat()
        # ctime protects recent replacements and files with backdated mtimes.
        changed = max(stat.st_mtime, stat.st_ctime)
        return StoredImage(
            name, datetime.fromtimestamp(changed, dt_timezone.utc),
            (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns),
        )

    def read_backup(self, name):
        with self.path(name).open('rb') as saved:
            return json.load(saved)

    def delete_unchanged(self, image):
        if self.metadata(image.name) != image:
            return False
        # Deliberately do not use the object backend's error-swallowing delete().
        self.storage.delete(image.name)
        if self.path(image.name).exists():
            raise CleanupUnsafe('Datei wurde nicht gelöscht.')
        return True


class BucketNewsStore:
    label = 'bucket'

    def __init__(self):
        from .object_storage_backend import get_client
        # The installed Replit SDK only exposes names through list(). Use the
        # same GCS metadata bridge as views_media, but never swallow failures.
        self.bucket = get_client()._Client__bucket()

    def names(self, prefix):
        names = sorted(blob.name for blob in self.bucket.list_blobs(prefix=prefix))
        if any(not safe_name(name, prefix) for name in names):
            raise CleanupUnsafe('Unsicherer Objektpfad im News-Speicher.')
        return names

    def metadata(self, name):
        blob = self.bucket.get_blob(name)
        if blob is None or blob.updated is None or blob.time_created is None or blob.generation is None:
            raise CleanupUnsafe('Objektalter oder Objektversion nicht feststellbar.')
        changed = max(blob.updated, blob.time_created)
        if timezone.is_naive(changed):
            raise CleanupUnsafe('Objektalter ohne Zeitzone.')
        return StoredImage(name, changed, int(blob.generation))

    def read_backup(self, name):
        return json.loads(self.bucket.blob(name).download_as_bytes())

    def delete_unchanged(self, image):
        if self.metadata(image.name) != image:
            return False
        # Server-side generation precondition protects against replacement.
        self.bucket.blob(image.name).delete(if_generation_match=image.revision)
        return True


def news_stores():
    from .object_storage_backend import ReplitObjectStorage
    if isinstance(default_storage, FileSystemStorage):
        return [LocalNewsStore(default_storage)]
    if isinstance(default_storage, ReplitObjectStorage):
        # Media serving also reads historical local files. Backups/references in
        # either location protect images in both; never silently omit a backend.
        return [BucketNewsStore(), LocalNewsStore(FileSystemStorage(location=settings.MEDIA_ROOT))]
    raise CleanupUnsafe('Dieser Speicher unterstützt keine sichere News-Bereinigung.')


def referenced_names(value):
    """Conservatively inspect every JSON string, not only current image slots."""
    if isinstance(value, dict):
        for child in value.values():
            yield from referenced_names(child)
    elif isinstance(value, list):
        for child in value:
            yield from referenced_names(child)
    elif isinstance(value, str) and not value.strip().startswith('data:'):
        try:
            path = posixpath.normpath(unquote(urlsplit(value.strip()).path))
            media_path = urlsplit(settings.MEDIA_URL).path.rstrip('/') + '/'
            if path.startswith(media_path):
                path = path[len(media_path):]
            elif media_path.lstrip('/') and path.startswith(media_path.lstrip('/')):
                path = path[len(media_path.lstrip('/')):]
            else:
                path = path.lstrip('/')
            if safe_name(path, IMAGE_PREFIX):
                yield path
        except ValueError as exc:
            raise CleanupUnsafe('Bildreferenz kann nicht sicher gelesen werden.') from exc


def protected_names(stores):
    protected = set()
    # Follow the rendering contract, not only the current upload fields:
    # legacy/default cards prefer thumbnail_static_path over img_path.
    for card, blocks, img_path, thumbnail in ClubNewsItem.objects.values_list(
        'card_data', 'blocks', 'img_path', 'thumbnail_static_path'
    ).iterator(chunk_size=200):
        protected.update(referenced_names([card, blocks, img_path, thumbnail]))
    for store in stores:
        for name in store.names(BACKUP_PREFIX):
            if not safe_name(name, BACKUP_PREFIX):
                raise CleanupUnsafe('Unsicherer Sicherungspfad.')
            backup = store.read_backup(name)
            if (not isinstance(backup, dict) or backup.get('version') != 1
                    or not isinstance(backup.get('news_id'), int)
                    or not isinstance(backup.get('club_id'), int)):
                raise CleanupUnsafe('Unbekanntes Sicherungsformat.')
            for phase in ('before', 'after'):
                snapshot = backup.get(phase)
                if (not isinstance(snapshot, dict)
                        or set(snapshot) != {'card_data', 'blocks'}
                        or not isinstance(snapshot['card_data'], (dict, type(None)))
                        or not isinstance(snapshot['blocks'], list)):
                    raise CleanupUnsafe('Unvollständige Migrationssicherung.')
                protected.update(referenced_names(snapshot))
    return protected


def cleanup_news_images(*, apply=False, min_age_days=MIN_AGE_DAYS, emit):
    if min_age_days < MIN_AGE_DAYS:
        raise CleanupUnsafe(f'Die Wartefrist muss mindestens {MIN_AGE_DAYS} Tage betragen.')
    stores = news_stores()
    cutoff = timezone.now() - timedelta(days=min_age_days)
    protected = protected_names(stores)
    candidates = []
    retained = 0
    # Complete all inventories and metadata reads before the first deletion.
    for store in stores:
        for name in store.names(IMAGE_PREFIX):
            if not safe_name(name, IMAGE_PREFIX):
                raise CleanupUnsafe('Unsicherer Bildpfad.')
            image = store.metadata(name)
            if name in protected:
                retained += 1
                emit(f'BEHALTEN {store.label}:{name} (Referenz/Restaurierung)')
            elif image.changed_at > cutoff:
                retained += 1
                emit(f'BEHALTEN {store.label}:{name} (Wartefrist)')
            else:
                candidates.append((store, image))
    removed = 0
    for store, image in candidates:
        if not apply:
            emit(f'KANDIDAT {store.label}:{image.name} (seit {image.changed_at.isoformat()})')
            continue
        # Fresh reads from ALL rows and ALL backups, immediately before deleting.
        # Writers must be paused for apply: storage + DB cannot share a transaction.
        if image.name in protected_names(stores):
            emit(f'BEHALTEN {store.label}:{image.name} (neue Referenz)')
        elif store.delete_unchanged(image):
            removed += 1
            emit(f'GELÖSCHT {store.label}:{image.name}')
        else:
            emit(f'BEHALTEN {store.label}:{image.name} (Datei geändert)')
    emit(
        f'{"Löschlauf" if apply else "Vorschau (keine Änderungen)"}: '
        f'{len(candidates)} Kandidat(en), {retained} geschützt/zu jung, {removed} gelöscht.'
    )