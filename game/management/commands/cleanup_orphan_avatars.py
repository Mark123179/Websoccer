"""
cleanup_orphan_avatars

Finds and deletes avatar files in object storage that are no longer
referenced by any ManagerProfile.profile_image field.

Background: Before versioned uploads, avatars were stored at a fixed
path like `managers/{id}/avatar.jpg`.  Now each upload generates a
unique path like `managers/{id}/avatar_<hex>.<ext>`.  The old fixed-
path files are orphaned and waste storage.

Usage:
    python manage.py cleanup_orphan_avatars            # dry-run (safe)
    python manage.py cleanup_orphan_avatars --delete   # actually delete
"""

import re

from django.core.management.base import BaseCommand

from game.models import ManagerProfile

MANAGERS_PREFIX = 'managers/'


class Command(BaseCommand):
    help = 'Delete orphaned avatar files from object storage (dry-run by default)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            default=False,
            help='Actually delete orphaned files (omit for a safe dry-run preview)',
        )

    def handle(self, *args, **options):
        do_delete = options['delete']

        try:
            from replit.object_storage import Client as ObjClient
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'replit.object_storage is not available in this environment. '
                'Run this command from the Replit app environment.'
            ))
            return

        from game.object_storage_backend import get_client
        obj_client = get_client()

        # Collect every active profile_image path that lives in object storage.
        # Paths starting with 'game/' are static assets, not uploaded files.
        active_paths = set(
            ManagerProfile.objects
            .exclude(profile_image='')
            .exclude(profile_image__startswith='game/')
            .values_list('profile_image', flat=True)
        )

        self.stdout.write(
            f'Active avatar paths in DB: {len(active_paths)}'
        )

        # List all objects in the managers/ prefix.
        try:
            objects = list(obj_client.list(prefix=MANAGERS_PREFIX))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Failed to list objects: {exc}'))
            return

        self.stdout.write(f'Objects found under "{MANAGERS_PREFIX}": {len(objects)}')

        # Identify orphans — objects not referenced by any profile_image.
        orphans = []
        for obj in objects:
            key = obj.key if hasattr(obj, 'key') else str(obj)
            if key not in active_paths:
                orphans.append(key)

        if not orphans:
            self.stdout.write(self.style.SUCCESS('No orphaned avatar files found.'))
            return

        self.stdout.write(f'\nOrphaned files ({len(orphans)}):')
        for key in sorted(orphans):
            self.stdout.write(f'  {key}')

        if not do_delete:
            self.stdout.write(self.style.WARNING(
                f'\nDry-run: {len(orphans)} file(s) would be deleted. '
                'Re-run with --delete to actually remove them.'
            ))
            return

        # Delete each orphan.
        deleted = 0
        failed = 0
        for key in orphans:
            try:
                obj_client.delete(key, ignore_not_found=True)
                self.stdout.write(f'  Deleted: {key}')
                deleted += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'  Failed to delete {key}: {exc}'))
                failed += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {deleted} deleted, {failed} failed.'
        ))
