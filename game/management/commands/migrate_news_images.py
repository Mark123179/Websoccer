"""Explicit, reversible migration; never run automatically on page reads."""

import json
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.models import ClubNewsItem
from game.news_image_storage import BACKUP_PREFIX, image_slots, persist_news_images
from game.news_validation import validate_image_source


class Command(BaseCommand):
    help = 'News-Bilder auslagern: standardmäßig nur Vorschau; --apply sichert und migriert.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--club-id', type=int)
        parser.add_argument('--news-id', type=int)
        parser.add_argument('--restore', metavar='BACKUP_OBJECT',
                            help='Originaldaten aus dieser Sicherung wiederherstellen (mit --apply).')

    def handle(self, *args, **options):
        if options['restore']:
            if options['club_id'] is not None or options['news_id'] is not None:
                raise CommandError('--restore darf nicht mit Filtern kombiniert werden.')
            return self.restore(options['restore'], options['apply'])

        items = ClubNewsItem.objects.order_by('pk')
        if options['club_id'] is not None:
            items = items.filter(club_id=options['club_id'])
        if options['news_id'] is not None:
            items = items.filter(pk=options['news_id'])
        count = failures = 0
        for pk in items.values_list('pk', flat=True).iterator(chunk_size=100):
            try:
                # Lock avoids overwriting concurrent edits/deletion. Storage failures
                # roll back the row; uploaded objects/backups are never deleted.
                with transaction.atomic():
                    item = ClubNewsItem.objects.select_for_update().get(pk=pk)
                    sources = [
                        container.get(key) for _, container, key
                        in image_slots(item.card_data, item.blocks)
                        if isinstance(container.get(key), str)
                        and container[key].startswith('data:')
                    ]
                    if not sources:
                        continue
                    for source in sources:
                        validate_image_source(source)
                    if not options['apply']:
                        self.stdout.write(f'News {pk}: {len(sources)} Bild(er), keine Änderung.')
                    else:
                        before = {'card_data': item.card_data, 'blocks': item.blocks}
                        card, blocks = persist_news_images(item.card_data, item.blocks)
                        after = {'card_data': card, 'blocks': blocks}
                        backup = json.dumps({
                            'version': 1, 'news_id': pk, 'club_id': item.club_id,
                            'before': before, 'after': after,
                        }, ensure_ascii=False).encode('utf-8')
                        name = default_storage.save(
                            f'{BACKUP_PREFIX}{pk}-{uuid4().hex}.json', ContentFile(backup)
                        )
                        with default_storage.open(name, 'rb') as saved:
                            if saved.read() != backup:
                                raise OSError('Sicherung konnte nicht verifiziert werden.')
                        # Expose the recovery reference even if the database save fails.
                        self.stdout.write(f'News {pk}: Sicherung {name}')
                        item.card_data, item.blocks = card, blocks
                        item.save(update_fields=['card_data', 'blocks'])
                        self.stdout.write(f'News {pk}: migriert.')
                    count += 1
            except Exception as exc:
                failures += 1
                # Never print image payloads or credentials from storage exceptions.
                self.stderr.write(f'News {pk}: unverändert; Fehler ({type(exc).__name__}).')
        self.stdout.write(f'{count} Beitrag/Beiträge {"migriert" if options["apply"] else "migrierbar"}.')
        if failures:
            raise CommandError(
                f'{failures} Beitrag/Beiträge nicht migriert. Originaldaten bleiben erhalten. '
                'Nicht unterstützte Altbilder müssen nicht migriert werden; Speicher und Bildformat prüfen.'
            )

    def restore(self, name, apply):
        if (not name.startswith(BACKUP_PREFIX) or '\\' in name
                or any(part in {'.', '..', ''} for part in name.split('/'))):
            raise CommandError('Ungültiger Sicherungspfad.')
        try:
            with default_storage.open(name, 'rb') as saved:
                backup = json.load(saved)
            if backup.get('version') != 1:
                raise ValueError
            before, after = backup['before'], backup['after']
            if set(before) != {'card_data', 'blocks'} or set(after) != set(before):
                raise ValueError
            with transaction.atomic():
                item = ClubNewsItem.objects.select_for_update().get(
                    pk=backup['news_id'], club_id=backup['club_id']
                )
                current = {'card_data': item.card_data, 'blocks': item.blocks}
                if current == before:
                    self.stdout.write(f'News {item.pk}: Originaldaten bereits vorhanden.')
                    return
                if current != after:
                    raise CommandError('Beitrag wurde seit der Migration geändert; Wiederherstellung abgebrochen.')
                if apply:
                    item.card_data, item.blocks = before['card_data'], before['blocks']
                    item.save(update_fields=['card_data', 'blocks'])
                self.stdout.write(
                    f'News {item.pk}: {"wiederhergestellt" if apply else "wiederherstellbar, keine Änderung"}.'
                )
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(
                f'Sicherung konnte nicht wiederhergestellt werden ({type(exc).__name__}); keine Änderung.'
            ) from exc