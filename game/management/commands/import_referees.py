"""
Management-Command: import_referees

Importiert Schiedsrichter aus einer CSV-Datei in die Referee-Tabelle.

Schema (UTF-8-BOM, Komma-getrennt):
  fm_uid, name, nationality, nationality_code, birth_date (DD.MM.YYYY),
  level (1–5), quote (1–20), karten_tendenz (1–20), spielfluss_tendenz (1–20),
  vorsaison_spiele, vorsaison_gelb_avg (Dezimal-Komma), vorsaison_rot,
  vorsaison_elfmeter, vorsaison_umstritten, vorsaison_competitions (komma-sep.)

Upsert-Logik:
  1. fm_uid gesetzt → Upsert auf fm_uid
  2. fm_uid leer    → Upsert auf (name, nationality) als Fallback

Optionen:
  --csv PATH       Pfad zur CSV-Datei (Pflicht)
  --dry-run        Zeige Vorschau ohne DB-Schreibzugriff
  --strict         Exit 1 bei Warnungen (sonst nur Exit 2 bei Fehlern)
  --skip-backfill  Überspringe assign_referees_to_past_matches nach Import
"""

import csv
import decimal
import os
import shutil
import sys
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from game.models import Referee


class Command(BaseCommand):
    help = "Importiert Schiedsrichter aus einer CSV-Datei (Upsert, idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--csv', required=True, metavar='PATH',
                            help='Pfad zur CSV-Datei')
        parser.add_argument('--dry-run', action='store_true',
                            help='Nur Vorschau, kein Schreiben')
        parser.add_argument('--strict', action='store_true',
                            help='Exit 1 bei Warnungen')
        parser.add_argument('--skip-backfill', action='store_true',
                            help='assign_referees_to_past_matches nicht aufrufen')

    def handle(self, *args, **opts):
        csv_path = opts['csv']
        dry_run = opts['dry_run']
        strict = opts['strict']
        skip_backfill = opts['skip_backfill']

        if not os.path.exists(csv_path):
            raise CommandError(f'CSV-Datei nicht gefunden: {csv_path}')

        rows = self._read_csv(csv_path)

        created_uid = 0
        created_name = 0
        updated = 0
        warnings = []
        errors = []

        name_fallback_candidates = []

        for lineno, row in enumerate(rows, start=2):
            try:
                ref_data, warn = self._parse_row(row, lineno)
            except ValueError as exc:
                errors.append(f'Zeile {lineno}: {exc}')
                continue

            warnings.extend(warn)

            if dry_run:
                if ref_data.get('_fallback_name'):
                    name_fallback_candidates.append(
                        f"  Zeile {lineno}: {ref_data['name']} ({ref_data['nationality']}) — Name+Nation-Fallback"
                    )
                continue

            try:
                was_created, via_uid = self._upsert(ref_data)
            except Exception as exc:
                errors.append(f'Zeile {lineno}: DB-Fehler: {exc}')
                continue

            if was_created:
                if via_uid:
                    created_uid += 1
                else:
                    created_name += 1
                    name_fallback_candidates.append(
                        f"  {ref_data['name']} ({ref_data['nationality']}) — Name+Nation-Fallback"
                    )
            else:
                updated += 1

        # ── Ausgabe ──────────────────────────────────────────────────────────
        if dry_run:
            self.stdout.write('[Dry-Run] Keine Änderungen gespeichert.\n')
            self.stdout.write(f'Gefundene Zeilen: {len(rows)}\n')
            uid_rows = sum(1 for r in rows if r.get('fm_uid', '').strip())
            name_rows = len(rows) - uid_rows
            self.stdout.write(f'  davon per fm_uid:       {uid_rows}\n')
            self.stdout.write(f'  davon Name+Nation-Fallback: {name_rows}\n')
            if name_fallback_candidates:
                self.stdout.write('Name-Fallback-Kandidaten:\n')
                for c in name_fallback_candidates:
                    self.stdout.write(c + '\n')
            if warnings:
                self.stdout.write(f'Warnungen: {len(warnings)}\n')
                for w in warnings[:10]:
                    self.stdout.write(f'  [WARN] {w}\n')
            if errors:
                self.stdout.write(self.style.ERROR(f'Fehler: {len(errors)}\n'))
                for e in errors[:10]:
                    self.stdout.write(self.style.ERROR(f'  [ERROR] {e}\n'))
            return

        # ── Bild-Auto-Copy (wie in creator_referee_save) ─────────────────────
        if not skip_backfill:
            self._copy_images_from_players()

        # ── Zusammenfassung ───────────────────────────────────────────────────
        summary = (
            f'{created_uid} angelegt (per fm_uid), '
            f'{created_name} angelegt (per Name+Nation), '
            f'{updated} aktualisiert, '
            f'{len(errors)} Fehler'
        )
        if errors:
            self.stdout.write(self.style.ERROR(summary))
            for e in errors[:20]:
                self.stdout.write(self.style.ERROR(f'  [ERROR] {e}'))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

        if name_fallback_candidates:
            self.stdout.write('Name+Nation-Fallback-Refs:\n' + '\n'.join(name_fallback_candidates))

        if warnings:
            self.stdout.write(f'  [{len(warnings)} Warnung(en)]')
            for w in warnings[:10]:
                self.stdout.write(f'  [WARN] {w}')

        # ── Backfill ──────────────────────────────────────────────────────────
        if not skip_backfill and (created_uid + created_name) > 0:
            self.stdout.write('Starte assign_referees_to_past_matches …')
            try:
                from django.core.management import call_command
                call_command('assign_referees_to_past_matches', stdout=self.stdout)
            except SystemExit:
                pass
            except Exception as exc:
                self.stdout.write(f'[WARN] Backfill-Fehler: {exc}')

        # ── Exit-Code ─────────────────────────────────────────────────────────
        if errors:
            sys.exit(2)
        if strict and warnings:
            sys.exit(1)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_csv(self, path):
        rows = []
        with open(path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows

    def _parse_row(self, row, lineno):
        warnings = []

        name = row.get('name', '').strip()
        if not name:
            raise ValueError('Name leer')

        # fm_uid
        uid_raw = row.get('fm_uid', '').strip()
        fm_uid = None
        if uid_raw:
            try:
                fm_uid = int(uid_raw)
            except ValueError:
                raise ValueError(f'fm_uid ungültig: {uid_raw!r}')

        # nationality
        nationality = row.get('nationality', '').strip()
        nationality_code = row.get('nationality_code', '').strip()

        # birth_date DD.MM.YYYY
        birth_date = None
        bd_raw = row.get('birth_date', '').strip()
        if bd_raw:
            try:
                birth_date = datetime.strptime(bd_raw, '%d.%m.%Y').date()
            except ValueError:
                warnings.append(f'Zeile {lineno}: birth_date ungültig: {bd_raw!r}')

        # level 1–5
        try:
            level = max(1, min(5, int(row.get('level', 3))))
        except (ValueError, TypeError):
            warnings.append(f'Zeile {lineno}: level ungültig, setze 3')
            level = 3

        # quote 1–20
        try:
            quote = max(1, min(20, int(row.get('quote', 10))))
        except (ValueError, TypeError):
            warnings.append(f'Zeile {lineno}: quote ungültig, setze 10')
            quote = 10

        # karten_tendenz / spielfluss_tendenz 1–20
        try:
            karten_tendenz = max(1, min(20, int(row.get('karten_tendenz', 10))))
        except (ValueError, TypeError):
            karten_tendenz = 10
        try:
            spielfluss_tendenz = max(1, min(20, int(row.get('spielfluss_tendenz', 11))))
        except (ValueError, TypeError):
            spielfluss_tendenz = 11

        # vorsaison stats
        def _int(key, default=0):
            try:
                return max(0, int(row.get(key, default) or default))
            except (ValueError, TypeError):
                return default

        def _dec(key, default='0'):
            raw = (row.get(key, '') or '').replace(',', '.').strip()
            try:
                return decimal.Decimal(raw) if raw else decimal.Decimal(default)
            except decimal.InvalidOperation:
                return decimal.Decimal(default)

        vorsaison_spiele = _int('vorsaison_spiele')
        vorsaison_gelb_avg = _dec('vorsaison_gelb_avg')
        vorsaison_rot = _int('vorsaison_rot')
        vorsaison_elfmeter = _int('vorsaison_elfmeter')
        vorsaison_umstritten = _int('vorsaison_umstritten')

        comps_raw = row.get('vorsaison_competitions', '').strip()
        vorsaison_competitions = (
            [c.strip() for c in comps_raw.split(',') if c.strip()]
            if comps_raw else []
        )

        return {
            'fm_uid': fm_uid,
            'name': name,
            'nationality': nationality,
            'nationality_code': nationality_code,
            'birth_date': birth_date,
            'level': level,
            'quote': quote,
            'karten_tendenz': karten_tendenz,
            'spielfluss_tendenz': spielfluss_tendenz,
            'vorsaison_spiele': vorsaison_spiele,
            'vorsaison_gelb_avg': vorsaison_gelb_avg,
            'vorsaison_rot': vorsaison_rot,
            'vorsaison_elfmeter': vorsaison_elfmeter,
            'vorsaison_umstritten': vorsaison_umstritten,
            'vorsaison_competitions': vorsaison_competitions,
            '_fallback_name': fm_uid is None,
        }, warnings

    def _upsert(self, data):
        fm_uid = data['fm_uid']
        fields = {k: v for k, v in data.items() if not k.startswith('_')}

        if fm_uid is not None:
            ref, created = Referee.objects.get_or_create(
                fm_uid=fm_uid,
                defaults=fields,
            )
            if not created:
                for k, v in fields.items():
                    setattr(ref, k, v)
                ref.save()
            return created, True
        else:
            # Name+Nation-Fallback
            ref, created = Referee.objects.get_or_create(
                name=data['name'],
                nationality=data['nationality'],
                defaults=fields,
            )
            if not created:
                for k, v in fields.items():
                    setattr(ref, k, v)
                ref.save()
            return created, False

    def _copy_images_from_players(self):
        """Kopiert Referee-CutOuts aus dem Spieler-Ordner in den Referee-Ordner."""
        assets_root = str(settings.ASSETS_ROOT).rstrip('/')
        player_dir = os.path.join(assets_root, 'players')
        ref_dir = os.path.join(assets_root, 'referees')
        os.makedirs(ref_dir, exist_ok=True)

        copied = 0
        skipped = 0
        for ref in Referee.objects.filter(fm_uid__isnull=False):
            uid = ref.fm_uid
            # Bereits im Referee-Ordner?
            already = next(
                (os.path.join(ref_dir, f'face_{uid}.{ext}')
                 for ext in ('png', 'jpg', 'jpeg')
                 if os.path.exists(os.path.join(ref_dir, f'face_{uid}.{ext}'))),
                None,
            )
            if already:
                skipped += 1
                continue
            # Im Spieler-Ordner?
            src = next(
                (os.path.join(player_dir, f'face_{uid}.{ext}')
                 for ext in ('png', 'jpg', 'jpeg')
                 if os.path.exists(os.path.join(player_dir, f'face_{uid}.{ext}'))),
                None,
            )
            if src:
                ext_only = os.path.splitext(src)[1]
                shutil.copy2(src, os.path.join(ref_dir, f'face_{uid}{ext_only}'))
                copied += 1

        if copied or skipped:
            self.stdout.write(
                f'Bilder: {copied} kopiert, {skipped} bereits vorhanden.'
            )
