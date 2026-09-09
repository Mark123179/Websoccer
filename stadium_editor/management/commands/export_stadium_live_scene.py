import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from game.models import Club, Stadium
from stadium_editor.live_scene import LiveSceneError, build_live_scene
from stadium_editor.models import StadiumDesign, StadiumGeometry


class Command(BaseCommand):
    help = 'Exportiert den kanonischen Live-Scene-Vertrag eines Stadions.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--club-id', type=int, help='Django-Club-ID')
        group.add_argument(
            '--fm-inside-id',
            type=int,
            help='Stabile FMInside-Club-ID (Standard: 907/Borussia Dortmund)',
        )
        parser.add_argument(
            '--output',
            default='exports/stadion-live-scene.json',
            help='Ausgabepfad relativ zum Projektverzeichnis',
        )

    def handle(self, *args, **options):
        lookup = (
            {'pk': options['club_id']}
            if options['club_id'] is not None
            else {
                'fm_inside_id': (
                    options['fm_inside_id']
                    if options['fm_inside_id'] is not None
                    else 907
                )
            }
        )
        try:
            club = Club.objects.select_related('stadium').get(**lookup)
            stadium = club.stadium
            geometry = StadiumGeometry.objects.get(stadium=stadium)
            design = StadiumDesign.objects.get(stadium=stadium)
            payload = build_live_scene(stadium, geometry.geometry, design.design)
        except Club.DoesNotExist as exc:
            raise CommandError('Club nicht gefunden.') from exc
        except Stadium.DoesNotExist as exc:
            raise CommandError('Stadion nicht gefunden.') from exc
        except StadiumGeometry.DoesNotExist as exc:
            raise CommandError('Keine Stadion-Geometrie hinterlegt.') from exc
        except StadiumDesign.DoesNotExist as exc:
            raise CommandError('Kein Stadion-Design hinterlegt.') from exc
        except (LiveSceneError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        output = Path(options['output'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        self.stdout.write(self.style.SUCCESS(
            f'Live Scene exportiert: {output} ({len(payload["blocks"])} Blöcke)'
        ))