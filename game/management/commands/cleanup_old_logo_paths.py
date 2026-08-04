"""
cleanup_old_logo_paths

Finds League rows whose logo_static_path still uses an old manual format
(e.g. 'game/images/competitions/bundesliga.svg', 'game/images/leagues/...',
'img/competitions/...') instead of the canonical 'competitions/{id}_comp.png'
written by the Creator upload endpoint.

For every such league the command checks whether a properly named asset
already exists in object storage:

  competitions/{league.id}_comp.png

If the asset is present  → logo_static_path is updated to the new format.
If the asset is absent   → logo_static_path is reset to '' so the template
                          falls back gracefully instead of serving a broken path.

Usage:
    python manage.py cleanup_old_logo_paths            # dry-run (safe, no DB writes)
    python manage.py cleanup_old_logo_paths --apply    # actually update the DB
"""

from django.core.management.base import BaseCommand

from game.models import League


def _is_old_format(path: str) -> bool:
    """Return True when path is set but NOT in the canonical new format."""
    if not path:
        return False
    return not path.startswith('competitions/')


def _asset_exists_in_storage(key: str) -> bool:
    """Return True when the object-storage key exists.  Returns False on any error."""
    try:
        from game.object_storage_backend import get_client
        client = get_client()
        objects = list(client.list(prefix=key))
        for obj in objects:
            obj_key = obj.key if hasattr(obj, 'key') else str(obj)
            if obj_key == key:
                return True
        return False
    except Exception:
        return False


class Command(BaseCommand):
    help = (
        'Reset/migrate League.logo_static_path values that use the old manual format '
        '(dry-run by default, use --apply to write changes).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Write changes to the database (omit for a safe dry-run preview).',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        old_format_leagues = [
            league for league in League.objects.exclude(logo_static_path='')
            if _is_old_format(league.logo_static_path)
        ]

        if not old_format_leagues:
            self.stdout.write(self.style.SUCCESS(
                'No leagues with old-format logo_static_path found. Nothing to do.'
            ))
            return

        self.stdout.write(
            f'Found {len(old_format_leagues)} league(s) with old-format logo_static_path:\n'
        )

        to_migrate = []
        to_clear = []

        for league in old_format_leagues:
            canonical_key = f'competitions/{league.id}_comp.png'
            exists = _asset_exists_in_storage(canonical_key)
            action = 'MIGRATE' if exists else 'CLEAR'
            new_value = canonical_key if exists else ''

            self.stdout.write(
                f'  [{action}] id={league.id!r:>6}  name={league.name!r}\n'
                f'           old: {league.logo_static_path!r}\n'
                f'           new: {new_value!r}'
            )

            if exists:
                to_migrate.append((league, canonical_key))
            else:
                to_clear.append(league)

        self.stdout.write(
            f'\nSummary: {len(to_migrate)} to migrate, {len(to_clear)} to clear.\n'
        )

        if not apply:
            self.stdout.write(self.style.WARNING(
                'Dry-run mode — no changes written. Re-run with --apply to apply.'
            ))
            return

        migrated = 0
        cleared = 0
        errors = 0

        for league, new_path in to_migrate:
            try:
                league.logo_static_path = new_path
                league.save(update_fields=['logo_static_path'])
                self.stdout.write(f'  Migrated: {league.name!r} → {new_path!r}')
                migrated += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(
                    f'  ERROR migrating {league.name!r}: {exc}'
                ))
                errors += 1

        for league in to_clear:
            try:
                league.logo_static_path = ''
                league.save(update_fields=['logo_static_path'])
                self.stdout.write(f'  Cleared:  {league.name!r}')
                cleared += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(
                    f'  ERROR clearing {league.name!r}: {exc}'
                ))
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {migrated} migrated, {cleared} cleared, {errors} error(s).'
        ))
