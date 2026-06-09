"""SoFIFA-CSV-Importer.

Importiert EA/SoFIFA-Spielerratings aus einer CSV-Datei, statt SoFIFA live zu
scrapen (Cloudflare blockiert das Scraping). Das Matching laeuft primaer ueber
die SoFIFA-ID (gespeichert als PlayerExternalId mit SOFIFA-DataSource); ist noch
keine ID verknuepft, greift ein Fallback ueber Name (+ optional Verein), der die
SoFIFA-ID anschliessend dauerhaft verknuepft.

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
"""

import csv
import html
import re
import unicodedata

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from game.models import (
    Club,
    DataSource,
    Player,
    PlayerEditLog,
    PlayerExternalId,
    PlayerSourceRating,
    PlayerSourceRatingSnapshot,
)


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

# Header-Alias -> kanonischer CSV-Schluessel.
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
    # Englische SoFIFA-Labels -> deutsche Attributspalten.
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
}
# Attributspalten duerfen auch unter ihrem eigenen Namen stehen.
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
        csv_path = options['csv_path']
        dry_run = options['dry_run']
        delimiter = options['delimiter']
        encoding = options['encoding']

        try:
            with open(csv_path, newline='', encoding=encoding) as fh:
                reader = csv.reader(fh, delimiter=delimiter)
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f'CSV-Datei nicht gefunden: {csv_path}')
        except OSError as exc:
            raise CommandError(f'CSV konnte nicht gelesen werden: {exc}')

        if not rows:
            raise CommandError('CSV ist leer.')

        header_map = self._build_header_map(rows[0])
        if 'sofifa_id' not in header_map:
            raise CommandError(
                'CSV-Header braucht eine sofifa_id-Spalte (Aliase: sofifa, id).'
            )
        if 'rating' not in header_map:
            raise CommandError(
                'CSV-Header braucht eine rating-Spalte (Aliase: overall, ovr).'
            )

        sofifa_ds, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_SOFIFA,
            defaults={'name': 'SoFIFA'},
        )
        today = timezone.localdate()

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '── DRY-RUN: es werden KEINE Aenderungen geschrieben ──'
            ))

        stats = {'new': 0, 'updated': 0, 'unchanged': 0, 'unmatched': 0, 'error': 0}
        unmatched_rows = []

        for line_no, raw_row in enumerate(rows[1:], start=2):
            if not any(cell.strip() for cell in raw_row):
                continue
            try:
                parsed = self._parse_row(raw_row, header_map)
            except ValueError as exc:
                stats['error'] += 1
                self.stdout.write(self.style.ERROR(f'  Zeile {line_no}: {exc}'))
                continue

            player, match_mode = self._match_player(parsed, sofifa_ds)
            if not player:
                stats['unmatched'] += 1
                label = parsed.get('name') or f"sofifa_id={parsed['sofifa_id']}"
                unmatched_rows.append(f'Zeile {line_no}: {label}')
                continue

            action, diff_lines = self._apply_row(
                player=player,
                parsed=parsed,
                sofifa_ds=sofifa_ds,
                today=today,
                dry_run=dry_run,
            )
            stats[action] += 1

            mark = {'new': '＋', 'updated': '✎', 'unchanged': '·'}[action]
            mode_note = '' if match_mode == 'id' else f' [{match_mode}]'
            detail = ('; '.join(diff_lines)) if diff_lines else 'keine Aenderung'
            self.stdout.write(
                f'  {mark} {player.full_name} ({player.club.name}){mode_note}: {detail}'
            )

        # ── Zusammenfassung ──────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Bilanz: {stats['new']} neu, {stats['updated']} aktualisiert, "
            f"{stats['unchanged']} unveraendert, {stats['unmatched']} nicht "
            f"gematcht, {stats['error']} Fehler."
        ))
        if unmatched_rows:
            self.stdout.write(self.style.WARNING('Nicht gematcht:'))
            for entry in unmatched_rows:
                self.stdout.write(self.style.WARNING(f'  - {entry}'))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN beendet — nichts geschrieben.'
            ))
            return

        changed = stats['new'] + stats['updated']
        if changed and not options['skip_recalculate']:
            self.stdout.write('Berechne Spielstaerken neu …')
            call_command('calculate_player_strengths')
            self.stdout.write(self.style.SUCCESS('Spielstaerken neu berechnet.'))
        elif not changed:
            self.stdout.write('Keine Aenderungen — Neuberechnung uebersprungen.')

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _build_header_map(self, header_row):
        """Spaltenindex -> kanonischer Schluessel."""
        header_map = {}
        for idx, cell in enumerate(header_row):
            key = COLUMN_ALIASES.get(normalize_header(cell))
            if key:
                header_map[key] = idx
        return header_map

    def _parse_row(self, raw_row, header_map):
        def cell(key):
            idx = header_map.get(key)
            if idx is None or idx >= len(raw_row):
                return ''
            return raw_row[idx].strip()

        sofifa_id = cell('sofifa_id')
        if not sofifa_id:
            raise ValueError('sofifa_id fehlt')

        rating = self._parse_int(cell('rating'), 0, 100, 'rating', required=True)
        potential = self._parse_int(cell('potential'), 0, 100, 'potential')

        attrs = {}
        for col in ALL_ATTR_COLUMNS:
            if col in header_map:
                val = self._parse_int(cell(col), 0, 99, col)
                if val is not None:
                    attrs[col] = val

        return {
            'sofifa_id': sofifa_id,
            'name': cell('name'),
            'club': cell('club'),
            'rating': rating,
            'potential': potential,
            'profile_url': cell('profile_url'),
            'attrs': attrs,
        }

    def _parse_int(self, raw, lo, hi, field, required=False):
        raw = (raw or '').strip()
        if not raw:
            if required:
                raise ValueError(f'{field} fehlt')
            return None
        try:
            val = int(float(raw))
        except ValueError:
            raise ValueError(f'{field} ist keine Zahl: {raw!r}')
        if not (lo <= val <= hi):
            raise ValueError(f'{field}={val} ausserhalb {lo}-{hi}')
        return val

    def _match_player(self, parsed, sofifa_ds):
        """Primaer ueber sofifa_id, sonst Fallback ueber Name (+ Verein)."""
        ext = (
            PlayerExternalId.objects
            .filter(source=sofifa_ds, external_id=parsed['sofifa_id'])
            .select_related('player', 'player__club')
            .first()
        )
        if ext:
            return ext.player, 'id'

        name = parsed.get('name')
        if not name:
            return None, None

        candidates = Player.objects.select_related('club').all()
        club_name = parsed.get('club')
        if club_name:
            club_norm = normalize_name(club_name)
            club_ids = [
                c.id for c in Club.objects.all()
                if club_norm and (
                    club_norm in normalize_name(c.name)
                    or normalize_name(c.name) in club_norm
                    or club_norm in normalize_name(c.short_name or '')
                )
            ]
            if club_ids:
                candidates = candidates.filter(club_id__in=club_ids)

        target = normalize_name(name)
        scored = []
        for p in candidates:
            score = name_similarity(target, normalize_name(p.full_name))
            if score >= 150:
                scored.append((score, p))

        if not scored:
            return None, None
        scored.sort(key=lambda t: t[0], reverse=True)
        # Eindeutigkeit: bester Treffer muss klar vor dem zweitbesten liegen.
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None, None
        return scored[0][1], 'name'

    def _apply_row(self, player, parsed, sofifa_ds, today, dry_run):
        existing = player.source_ratings.filter(
            source=PlayerSourceRating.SOURCE_EA,
        ).first()
        is_new = existing is None

        diff_lines = []
        if is_new:
            diff_lines.append(
                f"EA/SoFIFA: Quelldaten erstmals angelegt (Rating {parsed['rating']})"
            )
        else:
            if existing.rating != parsed['rating']:
                diff_lines.append(
                    f"EA/SoFIFA Rating: {existing.rating} → {parsed['rating']}"
                )
            if parsed['potential'] is not None and existing.potential != parsed['potential']:
                old_p = existing.potential if existing.potential is not None else '–'
                diff_lines.append(
                    f"EA/SoFIFA Potential: {old_p} → {parsed['potential']}"
                )
            for col, val in parsed['attrs'].items():
                old_val = getattr(existing, col, None)
                if old_val != val:
                    diff_lines.append(f"{col}: {old_val if old_val is not None else '–'} → {val}")

        if not is_new and not diff_lines:
            return 'unchanged', []

        if dry_run:
            return ('new' if is_new else 'updated'), diff_lines

        with transaction.atomic():
            defaults = {
                'rating': parsed['rating'],
                'source_url': parsed['profile_url'],
                'source_version': 'SoFIFA CSV-Import',
                'checked_at': today,
            }
            if parsed['potential'] is not None:
                defaults['potential'] = parsed['potential']
            defaults.update(parsed['attrs'])

            PlayerSourceRating.objects.update_or_create(
                player=player,
                source=PlayerSourceRating.SOURCE_EA,
                defaults=defaults,
            )

            PlayerSourceRatingSnapshot.objects.update_or_create(
                player=player,
                source=sofifa_ds,
                recorded_at=today,
                defaults={
                    'rating': parsed['rating'],
                    'potential': parsed['potential'],
                    'source_url': parsed['profile_url'],
                    'source_version': 'SoFIFA CSV-Import',
                    'update_current': False,
                    'raw_payload': {
                        'sofifa_id': parsed['sofifa_id'],
                        'attrs': parsed['attrs'],
                    },
                },
            )

            PlayerExternalId.objects.update_or_create(
                player=player,
                source=sofifa_ds,
                defaults={
                    'external_id': parsed['sofifa_id'],
                    'profile_url': parsed['profile_url'],
                    'is_primary': False,
                },
            )

            PlayerEditLog.objects.create(
                player=player,
                changed_by=None,
                category=PlayerEditLog.CATEGORY_SOURCE,
                summary='\n'.join(diff_lines),
            )

        return ('new' if is_new else 'updated'), diff_lines
