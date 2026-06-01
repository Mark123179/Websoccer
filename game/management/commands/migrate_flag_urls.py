from django.core.management.base import BaseCommand

from game.models import COUNTRY_FLAG_ASSETS, ManagerProfile


class Command(BaseCommand):
    help = (
        'Migriert alte nationality_flag-Werte (game/images/flags/{asset_id}.svg) '
        'auf CDN-URLs (https://flagcdn.com/{code}.svg). '
        'Einmalige Datenmigration für bestehende Manager.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Zeigt an, was geändert würde, ohne zu speichern.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        asset_id_to_cdn = {}
        for country_name, info in COUNTRY_FLAG_ASSETS.items():
            asset_id = info.get('asset_id')
            code = info.get('code', '').lower()
            if asset_id and code:
                old_path = f'game/images/flags/{asset_id}.svg'
                cdn_url = f'https://flagcdn.com/{code}.svg'
                if old_path not in asset_id_to_cdn:
                    asset_id_to_cdn[old_path] = cdn_url

        old_paths = list(asset_id_to_cdn.keys())
        qs = ManagerProfile.objects.filter(nationality_flag__in=old_paths)
        total = qs.count()

        self.stdout.write(f'{total} Manager mit alten Flag-Pfaden gefunden.')

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run — keine Änderungen werden gespeichert.'))

        updated = 0
        skipped = 0
        for profile in qs.iterator():
            old_flag = profile.nationality_flag
            new_flag = asset_id_to_cdn.get(old_flag)
            if not new_flag:
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(
                    f'  [dry] {profile.name!r}: {old_flag!r} → {new_flag!r}'
                )
            else:
                profile.nationality_flag = new_flag
                profile.save(update_fields=['nationality_flag'])
            updated += 1

        if skipped:
            self.stdout.write(self.style.WARNING(f'{skipped} Einträge übersprungen (kein Mapping gefunden).'))

        if dry_run:
            self.stdout.write(self.style.WARNING(f'Dry-run abgeschlossen: {updated} würden migriert.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'{updated} Manager-Flag-URLs migriert.'))
