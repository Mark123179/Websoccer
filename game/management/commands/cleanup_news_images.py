from django.core.management.base import BaseCommand, CommandError

from game.news_image_cleanup import MIN_AGE_DAYS, CleanupUnsafe, cleanup_news_images


class Command(BaseCommand):
    help = (
        'Verwaiste News-Bilder prüfen (Standard: Vorschau, mindestens 7 Tage alt). '
        'Löschen nur mit --apply --confirm-writers-stopped. Sicherungen bleiben erhalten.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--min-age-days', type=int, default=MIN_AGE_DAYS)
        parser.add_argument(
            '--confirm-writers-stopped', action='store_true',
            help='Bestätigt: News-Veröffentlichungen, Bearbeitungen und Bildmigrationen sind pausiert.',
        )

    def handle(self, *args, **options):
        if options['apply'] and not options['confirm_writers_stopped']:
            raise CommandError(
                'Zuerst News-Veröffentlichungen, Bearbeitungen und Bildmigrationen pausieren; '
                'danach --confirm-writers-stopped angeben. Keine Änderung.'
            )
        try:
            cleanup_news_images(
                apply=options['apply'], min_age_days=options['min_age_days'],
                emit=self.stdout.write,
            )
        except CleanupUnsafe as exc:
            raise CommandError(f'Bereinigung abgebrochen: {exc}') from exc
        except Exception as exc:
            # SDK errors may include credentials or article payloads.
            raise CommandError(
                f'Bereinigung abgebrochen ({type(exc).__name__}). '
                'Referenzen, Sicherungen, Speicherzugriff und Metadaten prüfen. '
                'Bereits gemeldete Löschungen sind nicht rückgängig gemacht.'
            ) from exc