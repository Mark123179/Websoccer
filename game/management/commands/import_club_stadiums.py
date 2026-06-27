"""
Management command: import_club_stadiums

Importiert Stadion-Daten aus einer UTF-8-CSV (Semikolon-getrennt) für bestehende
Clubs. Keine Neuanlage von Clubs.

Club-Mapping-Reihenfolge:
  1. tm_club_id / transfermarkt_id / tm_id  → Club.transfermarkt_id
  2. club_slug / slug                        → Club.name (iexact, Bindestriche → Leerzeichen)
  3. club_name / name                        → Club.name (iexact, dann icontains)

Summenprüfungen (vor dem Speichern):
  - Nord+Ost+Süd+West = capacity_total
  - Stehplätze+Sitzplätze+VIP = capacity_total
  - je Tribüne: standing+seating+vip = tribune_total (falls tribune_total in CSV)

Verwendung:
    python manage.py import_club_stadiums imports/bundesliga_stadium_import_2025_26.csv
    python manage.py import_club_stadiums ... --dry-run
    python manage.py import_club_stadiums ... --dry-run --strict
"""
import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from game.models import Club, Stadium

_TM_ID_COLS  = ('tm_club_id', 'transfermarkt_id', 'tm_id')
_SLUG_COLS   = ('club_slug', 'slug')
_NAME_COLS   = ('club_name', 'name')

_STADIUM_STR_MAP = [
    (('stadium_name', 'stadion_name'), 'name'),
    (('stadium_city', 'stadion_city', 'city'),  'city'),
]

_STADIUM_INT_MAP = [
    (('nord_standing',),                 'nord_standing'),
    (('nord_seating',  'nord_seated'),   'nord_seating'),
    (('nord_vip',),                      'nord_vip'),
    (('ost_standing',),                  'ost_standing'),
    (('ost_seating',   'ost_seated'),    'ost_seating'),
    (('ost_vip',),                       'ost_vip'),
    (('sued_standing', 'sud_standing'),  'sued_standing'),
    (('sued_seating',  'sued_seated',
      'sud_seating',   'sud_seated'),    'sued_seating'),
    (('sued_vip',      'sud_vip'),       'sued_vip'),
    (('west_standing',),                 'west_standing'),
    (('west_seating',  'west_seated'),   'west_seating'),
    (('west_vip',),                      'west_vip'),
    (('nlz_level',),                     'nlz_level'),
    (('medizin_level',),                 'medizin_level'),
    (('training_level',),                'training_level'),
    (('office_level',),                  'office_level'),
    (('lawn_quality',),                  'lawn_quality'),
]

_STADIUM_DECIMAL_MAP = [
    (('price_standing',), 'price_standing'),
    (('price_seating',),  'price_seating'),
    (('price_vip',),      'price_vip'),
]


class _DryRunRollback(Exception):
    pass


class _StrictAbort(Exception):
    pass


class Command(BaseCommand):
    help = (
        'Importiert Stadion-Daten aus einer UTF-8-CSV (Semikolon-getrennt) '
        'für bestehende Clubs. Keine Neuanlage von Clubs.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            help='Pfad zur CSV-Datei (UTF-8, Semikolon-getrennt).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur analysieren, nichts speichern.',
        )
        parser.add_argument(
            '--strict', action='store_true',
            help=(
                'Abbruch bei nicht gefundenem Club oder Summenfehler. '
                'Impliziert --dry-run bei Fehlern.'
            ),
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        dry_run  = options['dry_run']
        strict   = options['strict']

        try:
            with open(csv_path, encoding='utf-8-sig', newline='') as fh:
                reader = csv.DictReader(fh, delimiter=';')
                rows = list(reader)
        except OSError as exc:
            self.stderr.write(self.style.ERROR(
                f'CSV konnte nicht gelesen werden: {exc}'
            ))
            return

        stats = {
            'rows':             len(rows),
            'found':            0,
            'not_found':        0,
            'clubs_updated':    0,
            'stadiums_updated': 0,
            'sum_errors':       0,
            'warnings':         [],
        }

        abort = False
        try:
            with transaction.atomic():
                for row in rows:
                    self._process_row(row, stats, dry_run, strict)

                if dry_run:
                    raise _DryRunRollback()

        except _DryRunRollback:
            pass
        except _StrictAbort as exc:
            self.stderr.write(self.style.ERROR(f'[STRICT ABORT] {exc}'))
            abort = True

        if not abort:
            self._print_summary(stats, dry_run)

    def _process_row(self, row, stats, dry_run, strict):
        club = self._find_club(row, stats, strict)
        if club is None:
            stats['not_found'] += 1
            return

        stats['found'] += 1

        ok = self._validate_sums(row, club.name, stats, strict)
        if not ok:
            return

        self._save_stadium(club, row, stats, dry_run)

    def _find_club(self, row, stats, strict):
        for col in _TM_ID_COLS:
            val = (row.get(col) or '').strip()
            if val and val.isdigit():
                club = Club.objects.filter(transfermarkt_id=int(val)).first()
                if club:
                    return club

        for col in _SLUG_COLS:
            val = (row.get(col) or '').strip()
            if val:
                name_from_slug = val.replace('-', ' ')
                club = Club.objects.filter(name__iexact=name_from_slug).first()
                if club:
                    return club

        for col in _NAME_COLS:
            val = (row.get(col) or '').strip()
            if not val:
                continue
            club = Club.objects.filter(name__iexact=val).first()
            if club:
                return club
            qs = Club.objects.filter(name__icontains=val)
            if qs.count() == 1:
                return qs.first()

        hint = (
            row.get('club_name') or row.get('name') or '?'
        ).strip()
        msg = f'Club nicht gefunden: "{hint}"'
        stats['warnings'].append(msg)
        self.stdout.write(self.style.WARNING(f'  [WARN] {msg}'))
        if strict:
            raise _StrictAbort(msg)
        return None

    def _validate_sums(self, row, club_name, stats, strict):
        def _i(col):
            v = (row.get(col) or '').strip()
            try:
                return int(v) if v else 0
            except ValueError:
                return 0

        capacity_total = _i('capacity_total')
        if capacity_total == 0:
            return True

        nord_s  = _i('nord_standing');  nord_e  = _i('nord_seating')  or _i('nord_seated');   nord_v  = _i('nord_vip')
        ost_s   = _i('ost_standing');   ost_e   = _i('ost_seating')   or _i('ost_seated');    ost_v   = _i('ost_vip')
        sued_s  = _i('sued_standing')  or _i('sud_standing')
        sued_e  = _i('sued_seating')   or _i('sued_seated') or _i('sud_seating') or _i('sud_seated')
        sued_v  = _i('sued_vip')       or _i('sud_vip')
        west_s  = _i('west_standing');  west_e  = _i('west_seating')  or _i('west_seated');   west_v  = _i('west_vip')

        nord_total  = nord_s  + nord_e  + nord_v
        ost_total   = ost_s   + ost_e   + ost_v
        sued_total  = sued_s  + sued_e  + sued_v
        west_total  = west_s  + west_e  + west_v
        quadrant_sum = nord_total + ost_total + sued_total + west_total

        standing_csv = _i('standing_total')
        seating_csv  = _i('seating_total')
        vip_csv      = _i('vip_total')

        standing_computed = nord_s + ost_s + sued_s + west_s
        seating_computed  = nord_e + ost_e + sued_e + west_e
        vip_computed      = nord_v + ost_v + sued_v + west_v

        standing = standing_csv if standing_csv else standing_computed
        seating  = seating_csv  if seating_csv  else seating_computed
        vip      = vip_csv      if vip_csv      else vip_computed
        type_sum = standing + seating + vip

        errors = []

        tribune_checks = (
            ('nord_total',  nord_total,  'Nord'),
            ('ost_total',   ost_total,   'Ost'),
            ('sued_total',  sued_total,  'Süd'),
            ('west_total',  west_total,  'West'),
        )
        for col, computed, label in tribune_checks:
            csv_val = _i(col)
            if csv_val and csv_val != computed:
                errors.append(
                    f'{label}: berechnet {computed} ≠ CSV {csv_val}'
                )

        if quadrant_sum != capacity_total:
            errors.append(
                f'N+O+S+W={quadrant_sum} ≠ capacity_total={capacity_total}'
            )

        if type_sum != capacity_total:
            errors.append(
                f'Steh+Sitz+VIP={type_sum} ≠ capacity_total={capacity_total}'
            )

        if standing_csv and standing_csv != standing_computed:
            errors.append(
                f'standing_total={standing_csv} ≠ berechnet {standing_computed}'
            )
        if seating_csv and seating_csv != seating_computed:
            errors.append(
                f'seating_total={seating_csv} ≠ berechnet {seating_computed}'
            )
        if vip_csv and vip_csv != vip_computed:
            errors.append(
                f'vip_total={vip_csv} ≠ berechnet {vip_computed}'
            )

        if errors:
            stats['sum_errors'] += len(errors)
            for e in errors:
                msg = f'Summenfehler [{club_name}]: {e}'
                stats['warnings'].append(msg)
                self.stdout.write(self.style.ERROR(f'  [FEHLER] {msg}'))
            if strict:
                raise _StrictAbort(
                    f'Summenfehler bei "{club_name}": ' + '; '.join(errors)
                )
            return False

        return True

    def _save_stadium(self, club, row, stats, dry_run):
        if dry_run:
            stats['clubs_updated']    += 1
            stats['stadiums_updated'] += 1
            return

        stadium, _ = Stadium.objects.get_or_create(
            club=club,
            defaults={'name': club.name, 'city': ''},
        )
        updated = False

        for csv_cols, model_field in _STADIUM_STR_MAP:
            if not hasattr(stadium, model_field):
                continue
            for col in csv_cols:
                val = (row.get(col) or '').strip()
                if val:
                    setattr(stadium, model_field, val)
                    updated = True
                    break

        for csv_cols, model_field in _STADIUM_INT_MAP:
            if not hasattr(stadium, model_field):
                continue
            for col in csv_cols:
                val = (row.get(col) or '').strip()
                if val:
                    try:
                        setattr(stadium, model_field, int(val))
                        updated = True
                    except ValueError:
                        stats['warnings'].append(
                            f'Ungültiger Integer-Wert für {col}: "{val}"'
                        )
                    break

        for csv_cols, model_field in _STADIUM_DECIMAL_MAP:
            if not hasattr(stadium, model_field):
                continue
            for col in csv_cols:
                val = (row.get(col) or '').strip().replace(',', '.')
                if val:
                    try:
                        setattr(stadium, model_field, Decimal(val))
                        updated = True
                    except InvalidOperation:
                        stats['warnings'].append(
                            f'Ungültiger Dezimalwert für {col}: "{val}"'
                        )
                    break

        if updated:
            stadium.save()

        stats['clubs_updated']    += 1
        stats['stadiums_updated'] += 1

        try:
            public = club.public_profile
            if hasattr(public, 'stadium_name'):
                sname = (
                    row.get('stadium_name') or
                    row.get('stadion_name') or ''
                ).strip()
                if sname:
                    public.stadium_name = sname
            if hasattr(public, 'stadium_capacity'):
                cap = (row.get('capacity_total') or '').strip()
                if cap and cap.isdigit():
                    public.stadium_capacity = int(cap)
            public.save()
        except Exception:
            pass

    def _print_summary(self, stats, dry_run):
        mode = 'DRY-RUN' if dry_run else 'IMPORT'
        sep  = '─' * 42
        self.stdout.write(f'\n{sep}')
        self.stdout.write(f'Stadion-Import {mode}')
        self.stdout.write(sep)
        self.stdout.write(f'Gelesene Zeilen:          {stats["rows"]}')
        self.stdout.write(f'Gefundene Clubs:           {stats["found"]}')
        self.stdout.write(f'Nicht gefunden:            {stats["not_found"]}')
        self.stdout.write(f'Aktualisierte Clubs:       {stats["clubs_updated"]}')
        self.stdout.write(f'Aktualisierte Stadien:     {stats["stadiums_updated"]}')
        self.stdout.write(f'Summenfehler:              {stats["sum_errors"]}')
        if stats['warnings']:
            self.stdout.write('Warnungen:')
            for w in stats['warnings']:
                self.stdout.write(f'  ⚠ {w}')
        self.stdout.write(sep)
