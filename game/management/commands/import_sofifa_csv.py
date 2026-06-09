"""SoFIFA-CSV-Importer (CLI-Wrapper).

Duenner Wrapper um ``game.sofifa_import_service``; die eigentliche Importlogik
(Header-Mapping, Matching, Schreiben, Change-/Import-Log, Neuberechnung) liegt
im gemeinsam mit dem Creator-Upload genutzten Service-Modul.

CSV-Format (Header, Gross-/Kleinschreibung egal, Trennzeichen via --delimiter):

    sofifa_id,name,club,rating,potential,profile_url,tempo,ausdauer,...

Pflichtspalten: ``sofifa_id`` und ``rating`` (bzw. ``overall``).
Optionale Spalten: ``name``, ``club``/``verein``, ``potential``, ``profile_url``
sowie beliebige Attributspalten (deutsche Feldnamen wie ``tempo``, ``ausdauer``,
``kraft`` ... bzw. Torwart ``tw_reflexe`` ...). Englische SoFIFA-Labels werden
als Aliase erkannt.

Nur die in der CSV vorhandenen Spalten werden geschrieben; nicht gelistete
Attribute bleiben unveraendert. Nach einem echten (nicht --dry-run) Lauf werden
die Spielstaerken automatisch neu berechnet.

Die eigentliche Import-Logik lebt in game.sofifa_import_service.run_sofifa_import
und wird auch vom Browser-Upload im Creator-Mode genutzt.
"""

import re
import unicodedata
import html

from django.core.management.base import BaseCommand, CommandError

# ── Hilfsfunktionen und Konstanten werden aus dem Service re-exportiert ──────
# (Management-Commands importieren sie per from-Import, damit externer Code
#  wie views_creator.py sie direkt aus dem Command-Modul beziehen kann –
#  das ist der bestehende Import-Pfad, der nicht gebrochen werden darf.)

OUTFIELD_ATTR_COLUMNS = [
    'tempo', 'ausdauer', 'kraft', 'technik', 'dribbling', 'passspiel',
    'flanken', 'abschluss', 'kopfball', 'zweikampf', 'defensivstellung',
    'uebersicht', 'teamwork', 'ecken', 'freistoss', 'elfmeter',
]
GK_ATTR_COLUMNS = [
    'tw_reflexe', 'tw_fangsicherheit', 'tw_eins_gegen_eins',
    'tw_stellungsspiel', 'tw_passen',
]
ALL_ATTR_COLUMNS = OUTFIELD_ATTR_COLUMNS + GK_ATTR_COLUMNS

COLUMN_ALIASES = {
    'sofifa_id': 'sofifa_id', 'sofifa': 'sofifa_id', 'sofifaid': 'sofifa_id',
    'id': 'sofifa_id',
    'name': 'name', 'spieler': 'name', 'player': 'name',
    'full_name': 'name', 'fullname': 'name',
    'club': 'club', 'verein': 'club', 'team': 'club',
    'rating': 'rating', 'overall': 'rating', 'ovr': 'rating',
    'ova': 'rating', 'gesamt': 'rating',
    'potential': 'potential', 'pot': 'potential',
    'profile_url': 'profile_url', 'url': 'profile_url', 'sofifa_url': 'profile_url',
    'acceleration': 'tempo', 'pace': 'tempo', 'sprint_speed': 'tempo',
    'stamina': 'ausdauer',
    'strength': 'kraft',
    'ball_control': 'technik', 'technique': 'technik',
    'dribbling': 'dribbling',
    'short_passing': 'passspiel', 'passing': 'passspiel',
    'crossing': 'flanken',
    'finishing': 'abschluss',
    'heading_accuracy': 'kopfball', 'heading': 'kopfball',
    'standing_tackle': 'zweikampf', 'tackling': 'zweikampf',
    'defensive_awareness': 'defensivstellung', 'positioning': 'defensivstellung',
    'vision': 'uebersicht',
    'teamwork': 'teamwork',
    'corners': 'ecken',
    'fk_accuracy': 'freistoss', 'free_kick': 'freistoss',
    'penalties': 'elfmeter',
    'gk_reflexes': 'tw_reflexe', 'reflexes': 'tw_reflexe',
    'gk_handling': 'tw_fangsicherheit', 'handling': 'tw_fangsicherheit',
    'one_on_ones': 'tw_eins_gegen_eins',
    'gk_positioning': 'tw_stellungsspiel',
    'gk_kicking': 'tw_passen', 'kicking': 'tw_passen',
    # ── CMTracker / API-Export-Format (info.* / attributes.* / card_attrs.*) ──
    # normalize_header entfernt Punkte → zusammengezogene Schlüssel.
    'infoplayerid': 'sofifa_id',
    'infonameknownas': 'name',
    'infonamefirstname': 'first_name_raw',
    'infonamelastname': 'last_name_raw',
    'infoteamsclub_teamname': 'club',
    'infooverallrating': 'rating',
    'infopotential': 'potential',
    'card_attrspac': 'tempo',
    'attributesstamina': 'ausdauer',
    'attributesstrength': 'kraft',
    'attributesballcontrol': 'technik',
    'attributesdribbling': 'dribbling',
    'attributesshortpassing': 'passspiel',
    'attributescrossing': 'flanken',
    'attributesfinishing': 'abschluss',
    'attributesheadingaccuracy': 'kopfball',
    'attributesstandingtackle': 'zweikampf',
    'attributesmarking': 'defensivstellung',
    'attributesvision': 'uebersicht',
    'attributespenalties': 'elfmeter',
    'attributesfreekickaccuracy': 'freistoss',
    'attributesgkreflexes': 'tw_reflexe',
    'attributesgkhandling': 'tw_fangsicherheit',
    'attributesgkpositioning': 'tw_stellungsspiel',
    'attributesgkkicking': 'tw_passen',
    'attributesgkdiving': 'tw_eins_gegen_eins',
}
for _col in ALL_ATTR_COLUMNS:
    COLUMN_ALIASES.setdefault(_col, _col)


def normalize_header(raw):
    raw = (raw or '').strip().lstrip('\ufeff').lower()
    raw = raw.replace('-', '_').replace(' ', '_')
    raw = re.sub(r'[^a-z0-9_]', '', raw)
    raw = re.sub(r'_+', '_', raw).strip('_')
    return raw


def normalize_name(name):
    name = html.unescape(name or '')
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z]', '', name).lower()


def name_similarity(a, b):
    if not a or not b:
        return 0
    if a == b:
        return 200
    if a in b or b in a:
        return 150
    import difflib
    return int(difflib.SequenceMatcher(None, a, b).ratio() * 100)


class Command(BaseCommand):
    help = 'Importiert EA/SoFIFA-Ratings aus einer CSV (Matching ueber sofifa_id).'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', help='Pfad zur SoFIFA-CSV-Datei.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Zeigt geplante Aenderungen, ohne in die DB zu schreiben.',
        )
        parser.add_argument(
            '--skip-recalculate', action='store_true',
            help='Spielstaerken nach dem Import NICHT neu berechnen.',
        )
        parser.add_argument(
            '--delimiter', default=',',
            help='CSV-Trennzeichen (Standard: Komma).',
        )
        parser.add_argument(
            '--encoding', default='utf-8-sig',
            help='Datei-Encoding (Standard: utf-8-sig).',
        )

    def handle(self, *args, **options):
        from game.sofifa_import_service import run_sofifa_import

        csv_path = options['csv_path']
        dry_run = options['dry_run']
        delimiter = options['delimiter']
        encoding = options['encoding']

        try:
            with open(csv_path, newline='', encoding=encoding) as fh:
                csv_text = fh.read()
        except FileNotFoundError:
            raise CommandError(f'CSV-Datei nicht gefunden: {csv_path}')
        except OSError as exc:
            raise CommandError(f'CSV konnte nicht gelesen werden: {exc}')

        # Nicht-Standard-Trennzeichen: re-parse mit korrektem Delimiter und
        # normalisiere zurueck auf Komma-CSV fuer den Service.
        if delimiter != ',':
            import csv as _csv
            import io
            rows = list(_csv.reader(io.StringIO(csv_text), delimiter=delimiter))
            buf = io.StringIO()
            writer = _csv.writer(buf)
            writer.writerows(rows)
            csv_text = buf.getvalue()

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '── DRY-RUN: es werden KEINE Aenderungen geschrieben ──'
            ))

        result = run_sofifa_import(
            csv_text,
            dry_run=dry_run,
            skip_recalculate=options['skip_recalculate'],
        )

        if result['fatal_error']:
            raise CommandError(result['fatal_error'])

        stats = result['stats']
        total_clips = 0
        for r in result['row_results']:
            if r['action'] == 'error':
                self.stdout.write(self.style.ERROR(
                    f"  Zeile {r['line_no']}: {r['error_msg']}"
                ))
            elif r['action'] == 'unmatched':
                pass
            else:
                mark = {'new': '＋', 'updated': '✎', 'unchanged': '·'}[r['action']]
                mode_note = '' if r['match_mode'] == 'id' else f" [{r['match_mode']}]"
                detail = ('; '.join(r['diff_lines'])) if r['diff_lines'] else 'keine Aenderung'
                club = f" ({r['club_name']})" if r['club_name'] else ''
                self.stdout.write(
                    f"  {mark} {r['player_name']}{club}{mode_note}: {detail}"
                )
                for clip in r.get('clips', []):
                    total_clips += 1
                    self.stdout.write(self.style.WARNING(
                        f"    ⚠ {r['player_name']}: {clip} geclipt"
                    ))

        self.stdout.write('')
        clip_note = f', {total_clips} Attribute geclipt' if total_clips else ''
        self.stdout.write(self.style.SUCCESS(
            f"Bilanz: {stats['new']} neu, {stats['updated']} aktualisiert, "
            f"{stats['unchanged']} unveraendert, {stats['unmatched']} nicht "
            f"gematcht, {stats['error']} Fehler{clip_note}."
        ))

        unmatched = [r for r in result['row_results'] if r['action'] == 'unmatched']
        if unmatched:
            self.stdout.write(self.style.WARNING('Nicht gematcht:'))
            for r in unmatched:
                label = r['player_name']
                club = f" ({r['club_name']})" if r['club_name'] else ''
                self.stdout.write(self.style.WARNING(f'  - Zeile {r["line_no"]}: {label}{club}'))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN beendet — nichts geschrieben.'
            ))
            return

        changed = stats['new'] + stats['updated']
        if changed and not options['skip_recalculate']:
            self.stdout.write(self.style.SUCCESS('Spielstaerken neu berechnet.'))
        elif changed and options['skip_recalculate']:
            self.stdout.write('--skip-recalculate gesetzt — Neuberechnung uebersprungen.')
        else:
            self.stdout.write('Keine Aenderungen — Neuberechnung uebersprungen.')
