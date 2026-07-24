"""Sponsor-Stammdaten importieren (SPEC Kap. 3.1).

Liest sponsors.csv (Format: bereich,name,domain — Komma-getrennt) und
optional sponsor_names.json (Mapping slug → display_name, ~40 Einträge).

CSV-Format (Komma-getrennt, mit oder ohne Header):
  bereich,name,domain

Beispiel:
  ausruester,adidas,adidas.com
  hauptsponsor,deutsche_telekom,telekom.de

  → slug = slugify(name)  z.B. "adidas", "deutsche-telekom"
  → display_name aus sponsor_names.json[slug]
                   oder automatisch: "Adidas", "Deutsche Telekom"

Gültige Bereiche: hauptsponsor | trikotsponsor | ausruester | stadionpartner | tv_medien

Optionen:
  --csv-pfad   Pfad zur CSV-Datei (Default: sponsors.csv im Projektroot)
  --names-json Pfad zur JSON-Namens-Map (Default: attached_assets/sponsor_names.json)
  --bereich    Nur einen Bereich importieren
  --dry-run    Nur zählen, nicht schreiben
  --update     Vorhandene Einträge aktualisieren (Default: nur neue anlegen)
"""
import csv
import json
import os
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

VALID_BEREICHE = {
    'hauptsponsor', 'trikotsponsor', 'ausruester', 'stadionpartner', 'tv_medien',
}

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Command(BaseCommand):
    help = 'Importiert Sponsor-Stammdaten aus CSV + JSON.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-pfad', default=None,
            help='Pfad zur sponsors.csv (Default: sponsors.csv im Projektroot)',
        )
        parser.add_argument(
            '--names-json', default=None,
            help='Pfad zur sponsor_names.json (slug→display_name)',
        )
        parser.add_argument(
            '--bereich', default=None, choices=sorted(VALID_BEREICHE),
            help='Nur diesen Bereich importieren',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur analysieren, nicht in die DB schreiben',
        )
        parser.add_argument(
            '--update', action='store_true',
            help='Vorhandene Sponsoren aktualisieren (sonst nur neue anlegen)',
        )

    def handle(self, *args, **options):
        from game.models import Sponsor

        csv_pfad = options['csv_pfad'] or _find_csv()
        if not csv_pfad or not os.path.exists(csv_pfad):
            raise CommandError(
                f'sponsors.csv nicht gefunden. Angabe: --csv-pfad /pfad/zu/sponsors.csv\n'
                f'Gesucht in: {BASE_DIR / "sponsors.csv"}, attached_assets/sponsors.csv'
            )

        names_map = _load_names_json(options['names_json'])
        rows = _parse_csv(csv_pfad)

        bereich_filter = options['bereich']
        if bereich_filter:
            rows = [r for r in rows if r['bereich'] == bereich_filter]

        dry = options['dry_run']
        do_update = options['update']

        created = 0
        updated = 0
        skipped = 0
        errors = []

        for row in rows:
            slug = row['slug']
            name = row['name']
            bereich = row['bereich']
            branche = row.get('branche', '')
            display_name = names_map.get(slug, _auto_display_name(slug))

            if bereich not in VALID_BEREICHE:
                errors.append(f'Ungültiger Bereich "{bereich}" für {slug} — übersprungen')
                continue

            if dry:
                self.stdout.write(f'  [DRY] {slug} | {name} | {bereich}')
                created += 1
                continue

            try:
                obj, was_created = Sponsor.objects.get_or_create(
                    slug=slug,
                    defaults={
                        'name': name,
                        'display_name': display_name,
                        'bereich': bereich,
                        'branche': branche,
                        'aktiv': True,
                    },
                )
                if was_created:
                    created += 1
                elif do_update:
                    obj.name = name
                    obj.display_name = display_name
                    obj.bereich = bereich
                    obj.branche = branche
                    obj.save(update_fields=['name', 'display_name', 'bereich', 'branche'])
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors.append(f'{slug}: {exc}')

        for err in errors:
            self.stderr.write(self.style.ERROR(f'  FEHLER: {err}'))

        if dry:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN: {created} Einträge würden angelegt.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Import abgeschlossen: {created} neu, {updated} aktualisiert, '
                f'{skipped} übersprungen, {len(errors)} Fehler.'
            ))
            self.stdout.write(f'Gesamt Sponsoren in DB: {Sponsor.objects.count()}')

        if errors:
            sys.exit(1)


def _find_csv() -> str | None:
    candidates = [
        BASE_DIR / 'sponsors.csv',
        BASE_DIR / 'attached_assets' / 'sponsors.csv',
        BASE_DIR / 'data' / 'sponsors.csv',
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _load_names_json(path) -> dict:
    if path is None:
        candidates = [
            BASE_DIR / 'attached_assets' / 'sponsor_names.json',
            BASE_DIR / 'sponsor_names.json',
        ]
        for c in candidates:
            if c.exists():
                path = str(c)
                break
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _auto_display_name(slug: str) -> str:
    """Titelform des Slugs: Unterstriche/Bindestriche → Leerzeichen, capitalize."""
    return ' '.join(w.capitalize() for w in slug.replace('-', ' ').replace('_', ' ').split())


def _parse_csv(path: str) -> list[dict]:
    """Parst sponsors.csv im Format: bereich,name,domain (SPEC §3.1).

    Spalten:
      0 → bereich   (z.B. hauptsponsor, ausruester, …)
      1 → name      (Identifier/Slug-Vorlage, z.B. fritz_kola, deutsche_telekom)
      2 → domain    (z.B. fritz-kola.de) — für spätere Erweiterungen, nicht Pflicht
    """
    rows = []
    with open(path, encoding='utf-8', newline='') as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        for i, row in enumerate(reader):
            if not row or not any(r.strip() for r in row):
                continue
            # Header-Erkennung: erste Zeile mit bekannten Spaltennamen
            if i == 0 and row[0].strip().lower() in ('bereich', 'slug', 'id', 'name', 'typ'):
                continue
            if len(row) < 2:
                continue
            bereich = row[0].strip().lower()
            raw_name = row[1].strip()
            slug = slugify(raw_name)
            if not slug:
                continue
            rows.append({
                'slug': slug,
                'name': raw_name,     # Rohwert aus CSV (Basis für display_name-Fallback)
                'bereich': bereich,
                'branche': '',        # Nicht im neuen CSV-Format; kann per sponsor_names.json ergänzt werden
            })
    return rows
