"""Safe, explicit importer for the checked-in stadium Blueprint V2 pair."""

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.models import Stadium
from stadium_editor.capacity import distribute_capacities
from stadium_editor.contracts import geometry_blocks
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.blueprints.v2 import imports as v2
from stadium_editor.seed import normalise_block_types


MAX_OSM_BYTES = 5 * 1024 * 1024
MAX_STECKBRIEF_BYTES = 128 * 1024
DEFAULT_BACKUP_DIR = Path(__file__).resolve().parents[2] / 'blueprints' / 'v2' / 'backups'
CLUB_MAPPING = v2.CLUB_BLUEPRINTS


def _standard_design(scene, stadium_name, geometry=None):
    """Keep this call overridable for fixture tests while using the reference."""
    return v2.standard_design(scene, stadium_name=stadium_name, geometry=geometry)


class Command(BaseCommand):
    help = (
        'Importiert genau ein Stadion aus der expliziten Blueprint-V2-Zuordnung. '
        'Ohne --apply bleibt der Befehl vollständig schreibfrei.'
    )

    # Tests may inject a fixture mapping without changing production mapping.
    mapping = CLUB_MAPPING

    def add_arguments(self, parser):
        parser.add_argument(
            '--club-id', type=int, required=True,
            help='Eindeutige Club-PK aus der geprüften V2-Zuordnung.',
        )
        parser.add_argument(
            '--osm',
            help='Optionaler, ausdrücklich angegebener OSM-Cache für Fixture-Tests.',
        )
        parser.add_argument(
            '--source-root',
            help='Optionales Verzeichnis für die in der Zuordnung genannten Cache-Dateien.',
        )
        parser.add_argument(
            '--backup-dir', default=str(DEFAULT_BACKUP_DIR),
            help='Ziel für die JSON-Sicherung vor einem schreibenden Import.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur validieren (Standard; aus Gründen der Rückwärtskompatibilität akzeptiert).',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='Import tatsächlich schreiben.',
        )
        parser.add_argument(
            '--confirm', '--confirm-import', '--yes', dest='confirm', action='store_true',
            help='Bestätigung für --apply.',
        )

    def _mapping_entry(self, club_id):
        mapping = self.mapping
        # Permit both common fixture styles: mutate/replace the module
        # mapping, or assign a custom mapping on Command.
        if mapping is v2.CLUB_BLUEPRINTS and CLUB_MAPPING is not v2.CLUB_BLUEPRINTS:
            mapping = CLUB_MAPPING
        entry = mapping.get(club_id)
        if not isinstance(entry, dict):
            raise CommandError(
                f'Club-ID {club_id} ist nicht in der expliziten Blueprint-V2-Zuordnung.'
            )
        for key in ('osm', 'steckbrief'):
            if not entry.get(key):
                raise CommandError(f'Blueprint-V2-Zuordnung für {club_id} ist unvollständig ({key}).')
        if not entry.get('source') and not entry.get('source_key'):
            raise CommandError(f'Blueprint-V2-Zuordnung für {club_id} ist unvollständig (source_key).')
        return entry

    @staticmethod
    def _bounded_file(path, maximum, label):
        path = Path(path)
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise CommandError(f'{label} nicht gefunden: {path}') from exc
        if not path.is_file():
            raise CommandError(f'{label} ist keine Datei: {path}')
        if size > maximum:
            raise CommandError(
                f'{label} ist zu groß ({size} Bytes; maximal {maximum} Bytes).'
            )
        return path

    def _source_path(self, entry, options):
        if options.get('osm'):
            requested = Path(options['osm'])
            expected = Path(entry['osm']).name
            if requested.name != expected:
                raise CommandError(
                    f'--osm muss den zugeordneten Cache-Namen {expected!r} '
                    f'verwenden (erhalten: {requested.name!r}).'
                )
            return self._bounded_file(requested, MAX_OSM_BYTES, 'OSM-Cache')
        root = Path(options.get('source_root') or v2.ROOT)
        return self._bounded_file(root / entry['osm'], MAX_OSM_BYTES, 'OSM-Cache')

    def _validate(self, stadium, geometry):
        try:
            effective = distribute_capacities(stadium, geometry)
            trusted = geometry_blocks(effective)
        except (TypeError, ValueError) as exc:
            raise CommandError(f'Blueprint-V2-Geometrie ist ungültig: {exc}') from exc
        if not trusted:
            raise CommandError('Blueprint-V2-Geometrie enthält keine Blöcke.')
        for block in effective['blocks']:
            try:
                if float(block['z1']) <= float(block['z0']):
                    raise ValueError('z1 muss größer als z0 sein')
            except (KeyError, TypeError, ValueError) as exc:
                raise CommandError(f'Block {block.get("id")}: ungültige Höhen.') from exc
        assigned = sum(int(block.get('capacity', 0) or 0) for block in effective['blocks'])
        if assigned != stadium.capacity_total:
            raise CommandError(
                f'Kapazität stimmt nicht: Geometrie {assigned}, Stadium {stadium.capacity_total}.'
            )
        return effective

    def _backup(self, stadium, geometry_row, design_row, backup_dir):
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        path = backup_dir / f'club-{stadium.club_id}-{stamp}.json'
        payload = {
            'club_id': stadium.club_id,
            'stadium_id': stadium.pk,
            'geometry': deepcopy(geometry_row.geometry) if geometry_row else None,
            'steckbrief': deepcopy(geometry_row.steckbrief) if geometry_row else {},
            'schema_version': geometry_row.schema_version if geometry_row else None,
            'source': geometry_row.source if geometry_row else None,
            'design': deepcopy(design_row.design) if design_row else None,
            'blickrichtung': design_row.blickrichtung if design_row else None,
        }
        encoded = json.dumps(payload, ensure_ascii=False, indent=2)
        # O_EXCL makes two concurrent imports produce two backups even when
        # their clocks have the same resolution.
        suffix = 0
        while True:
            candidate = path if suffix == 0 else path.with_name(
                f'{path.stem}-{suffix}{path.suffix}')
            try:
                fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                suffix += 1
                continue
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(encoded)
            path = candidate
            break
        return path

    def handle(self, *args, **options):
        if options['dry_run'] and options['apply']:
            raise CommandError('--dry-run und --apply schließen sich aus.')
        if options['apply'] and not options['confirm']:
            raise CommandError('--apply benötigt zusätzlich --confirm (oder --yes).')
        entry = self._mapping_entry(options['club_id'])
        try:
            stadium = Stadium.objects.select_related('club').get(club_id=options['club_id'])
        except Stadium.DoesNotExist as exc:
            raise CommandError(f'Kein Stadion für Club-ID {options["club_id"]}.') from exc
        osm_path = self._source_path(entry, options)
        try:
            # Validate the checked-in JSON before the reference touches it.
            json.loads(osm_path.read_text(encoding='utf-8'))
            steckbrief_data = v2.load_steckbrief()
            steckbrief = steckbrief_data.get(entry['steckbrief'])
            if not isinstance(steckbrief, dict):
                raise ValueError(f'Steckbrief-Eintrag fehlt: {entry["steckbrief"]}')
            scene = v2.generate(
                entry.get('source_key', entry.get('source')), osm_path=osm_path,
                steckbrief_name=entry['steckbrief'],
            )
            v2.assert_reviewed_reference(
                entry.get('source_key', entry.get('source')), scene)
            geometry = v2.scene_to_geometry(scene)
            # The scene classifies standing/seating, while the Stadium model
            # may also carry a VIP bucket.  Assign only the minimum number of
            # generated blocks needed for each occupied authoritative bucket.
            geometry = normalise_block_types(stadium, geometry)
            effective = self._validate(stadium, geometry)
            # Persist server-owned capacity allocations while retaining the
            # physical rows/seats (the V2 marker makes this distinction
            # explicit to distribute_capacities).
            geometry = effective
            design = _standard_design(scene, stadium.name, geometry)
        except CommandError:
            raise
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise CommandError(f'Blueprint-V2-Import fehlgeschlagen: {exc}') from exc

        mode = 'Schreibprüfung' if not options['apply'] else 'Import'
        self.stdout.write(
            f'{mode}: Club {stadium.club_id}, {len(effective["blocks"])} Blöcke, '
            f'{stadium.capacity_total} Plätze, Quelle '
            f'{entry.get("source_key", entry.get("source"))}.'
        )
        if not options['apply']:
            self.stdout.write(self.style.SUCCESS('Dry-Run: Keine Datenbank- oder Backup-Datei geändert.'))
            return

        with transaction.atomic():
            locked_stadium = Stadium.objects.select_for_update().select_related('club').get(pk=stadium.pk)
            geometry = self._validate(locked_stadium, geometry)
            geometry_row = (
                StadiumGeometry.objects.select_for_update()
                .filter(stadium_id=locked_stadium.pk).first()
            )
            design_row = (
                StadiumDesign.objects.select_for_update()
                .filter(stadium_id=locked_stadium.pk).first()
            )
            backup = self._backup(locked_stadium, geometry_row, design_row, options['backup_dir'])
            defaults = {
                'geometry': geometry,
                'steckbrief': steckbrief,
                'schema_version': 2,
                'source': 'OSM/BLUEPRINT V2',
                'attribution': 'Blaupause: OpenStreetMap-Daten (ODbL)',
            }
            if geometry_row is None:
                StadiumGeometry.objects.create(stadium=locked_stadium, **defaults)
            else:
                for key, value in defaults.items():
                    setattr(geometry_row, key, value)
                geometry_row.save(update_fields=list(defaults) + ['updated_at'])
            design_defaults = {
                'design': design,
                'blickrichtung': design.get('blickrichtung', 'NORD'),
            }
            if design_row is None:
                StadiumDesign.objects.create(stadium=locked_stadium, **design_defaults)
            else:
                design_row.design = design_defaults['design']
                design_row.blickrichtung = design_defaults['blickrichtung']
                design_row.save(update_fields=['design', 'blickrichtung', 'updated_at'])
        self.stdout.write(self.style.SUCCESS(f'Importiert; Backup: {backup}'))