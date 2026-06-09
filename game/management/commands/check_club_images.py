import os

from django.conf import settings
from django.core.management.base import BaseCommand

from game.management.commands.seed_club_profiles import CLUB_PROFILES


class Command(BaseCommand):
    help = (
        'Prüft, ob alle Stadion- und Stadtbilder für die 18 Bundesliga-Clubs '
        'auf dem Dateisystem vorhanden sind. Gibt Fehler aus, wenn Bilder fehlen.'
    )

    def handle(self, *args, **options):
        missing = []
        ok = 0

        for entry in CLUB_PROFILES:
            fid = entry['fm_inside_id']
            profile = entry['profile']

            for key in ('stadium_image_static_path', 'city_image_static_path'):
                rel = profile.get(key, '')
                if not rel:
                    continue
                abs_path = os.path.join(settings.BASE_DIR, 'game', 'static', rel)
                if os.path.isfile(abs_path):
                    ok += 1
                else:
                    missing.append(
                        f'fm_inside_id={fid}  {key}: {rel}'
                    )

        if missing:
            self.stdout.write(
                self.style.ERROR(
                    f'{len(missing)} Bild(er) fehlen:\n' + '\n'.join(f'  {m}' for m in missing)
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Alle {ok} Club-Bilder vorhanden (18 × Stadion + 18 × Stadt).'
                )
            )
