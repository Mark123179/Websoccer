"""Backfill-Command: Füllt CMT-Profil-Metadaten aus dem gespeicherten raw_payload.

Liest PlayerCMTProfile.raw_payload und schreibt:
  - nationality     (info.nation.name > info.nationality.label > info.nationality)
  - second_nationality (info.secondNation.name > ...)
  - player_image_url   (info.headshot > info.imageurl > info.image_url)

Ohne --apply werden nur Vorschau-Zeilen ausgegeben (Dry-Run).
Mit --force werden auch bereits gefüllte Felder überschrieben.

Kein updated_at (Feld existiert nicht auf PlayerCMTProfile).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from game.cmtracker_api import _dig
from game.models import PlayerCMTProfile


def _str(v):
    if v is None:
        return ''
    s = str(v).strip()
    return s if s not in ('None', 'null', '') else ''


def _extract(raw):
    nationality = _str(
        _dig(raw, 'info.nation.name') or
        _dig(raw, 'info.nationality.label') or
        _dig(raw, 'info.nationality')
    )
    second_nationality = _str(
        _dig(raw, 'info.secondNation.name') or
        _dig(raw, 'info.secondnationality.label') or
        _dig(raw, 'info.secondnationality')
    )
    player_image_url = _str(
        _dig(raw, 'info.headshot') or
        _dig(raw, 'info.imageurl') or
        _dig(raw, 'info.image_url') or ''
    )
    return nationality, second_nationality, player_image_url


class Command(BaseCommand):
    help = (
        'Backfill: nationality / second_nationality / player_image_url '
        'aus raw_payload in PlayerCMTProfile schreiben. '
        'Standard: Dry-Run. --apply schreibt, --force überschreibt.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Änderungen in die Datenbank schreiben (Standard: Dry-Run).',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Bestehende nicht-leere Werte überschreiben.',
        )
        parser.add_argument(
            '--db', metavar='SLUG', default='',
            help='Nur Profile mit diesem db_slug verarbeiten.',
        )

    def handle(self, *args, **options):
        apply   = options['apply']
        force   = options['force']
        db_slug = options['db'].strip()
        now     = timezone.now()

        mode = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(self.style.WARNING(
            f'backfill_cmt_profile_metadata [{mode}]'
            + (f'  db={db_slug}' if db_slug else '')
            + ('  --force' if force else '')
        ))

        qs = PlayerCMTProfile.objects.select_related('player').exclude(raw_payload={})
        if db_slug:
            qs = qs.filter(db_slug=db_slug)

        total = qs.count()
        self.stdout.write(f'Profile zu prüfen: {total}')

        updated = skipped = no_data = 0
        for prof in qs.iterator(chunk_size=100):
            raw = prof.raw_payload or {}
            if not raw:
                no_data += 1
                continue

            nat, second_nat, img_url = _extract(raw)

            fields_to_write = {}

            if nat and (force or not prof.nationality):
                fields_to_write['nationality'] = nat
            if second_nat and (force or not prof.second_nationality):
                fields_to_write['second_nationality'] = second_nat
            if img_url and (force or not prof.player_image_url):
                fields_to_write['player_image_url'] = img_url

            if not fields_to_write:
                skipped += 1
                continue

            player_name = getattr(prof.player, 'full_name', str(prof.player_id))
            summary = ', '.join(
                f'{k}={repr(v[:40])}' for k, v in fields_to_write.items()
            )
            self.stdout.write(f'  {player_name}: {summary}')

            if apply:
                for field, value in fields_to_write.items():
                    setattr(prof, field, value)
                prof.last_imported_at = now
                prof.save(update_fields=list(fields_to_write.keys()) + ['last_imported_at'])

            updated += 1

        self.stdout.write('')
        result = (
            f'Ergebnis: {updated} {"geschrieben" if apply else "würden geschrieben"}'
            f', {skipped} bereits gefüllt (übersprungen)'
            f', {no_data} ohne raw_payload.'
        )
        self.stdout.write(self.style.SUCCESS(result))
        if not apply:
            self.stdout.write(
                self.style.WARNING('Dry-Run — keine DB-Änderungen. Mit --apply schreiben.')
            )
