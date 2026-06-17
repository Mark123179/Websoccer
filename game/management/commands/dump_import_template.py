"""Schreibt die kanonische Template-Kopfzeile des CSV-Imports.

Die Spaltenliste stammt aus dem Feldschema (Single Source of Truth in
:mod:`game.club_import.field_schema`). So liefert jede künftige (auch
KI-erzeugte) CSV exakt dieselben Spalten in derselben Reihenfolge.

Beispiele:
    python manage.py dump_import_template
    python manage.py dump_import_template --output game/club_import/import_template.csv
"""

from django.core.management.base import BaseCommand

from game.club_import.field_schema import template_header


class Command(BaseCommand):
    help = 'Gibt die kanonische CSV-Template-Kopfzeile aus (oder schreibt sie in eine Datei).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', default=None,
            help='Zielpfad; ohne Angabe wird die Kopfzeile auf stdout ausgegeben.',
        )

    def handle(self, *args, **options):
        header = template_header()
        if options['output']:
            with open(options['output'], 'w', encoding='utf-8') as fh:
                fh.write(header + '\n')
            self.stdout.write(self.style.SUCCESS(
                f'Template-Kopfzeile geschrieben: {options["output"]}'
            ))
        else:
            self.stdout.write(header)
