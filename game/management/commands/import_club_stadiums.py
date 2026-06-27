"""Importiert Club-/Stadiondaten aus der Bundesliga-Stadion-CSV.

Beispiel:
    python manage.py import_club_stadiums imports/bundesliga_stadium_import_2025_26.csv --dry-run --strict
    python manage.py import_club_stadiums imports/bundesliga_stadium_import_2025_26.csv --strict
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from game.models import Club, ClubPublicProfile, Stadium


class ImportErrorList(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__('; '.join(errors))


def _model_has_field(model: type, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def _set_if_has(instance: Any, field_name: str, value: Any, update_fields: set[str]) -> None:
    if _model_has_field(instance.__class__, field_name):
        setattr(instance, field_name, value)
        update_fields.add(field_name)


def _int(row: dict[str, str], key: str, default: int = 0) -> int:
    raw = (row.get(key) or '').strip()
    if raw == '':
        return default
    return int(raw)


def _float_or_none(row: dict[str, str], key: str) -> float | None:
    raw = (row.get(key) or '').strip().replace(',', '.')
    if raw == '':
        return None
    return float(raw)


def _norm_name(value: str) -> str:
    value = value or ''
    value = value.replace('-', ' ')
    value = unicodedata.normalize('NFKC', value)
    value = re.sub(r'\s+', ' ', value).strip().casefold()
    return value


def _row_label(row: dict[str, str]) -> str:
    return row.get('club_name') or row.get('name') or row.get('club_slug') or '<unbekannt>'


def _validate_row(row: dict[str, str], line_no: int) -> list[str]:
    errors: list[str] = []
    label = _row_label(row)

    total = _int(row, 'stadium_capacity_total')
    north_total = _int(row, 'capacity_north_total')
    south_total = _int(row, 'capacity_south_total')
    east_total = _int(row, 'capacity_east_total')
    west_total = _int(row, 'capacity_west_total')

    standing_total = _int(row, 'standing_capacity_total')
    seated_total = _int(row, 'seated_capacity_total')
    vip_total = _int(row, 'vip_capacity_total')

    if north_total + south_total + east_total + west_total != total:
        errors.append(
            f'Zeile {line_no} {label}: Nord+Süd+Ost+West '
            f'({north_total + south_total + east_total + west_total}) != Gesamtkapazität ({total})'
        )

    if standing_total + seated_total + vip_total != total:
        errors.append(
            f'Zeile {line_no} {label}: Steh+Sitz+VIP '
            f'({standing_total + seated_total + vip_total}) != Gesamtkapazität ({total})'
        )

    tribunes = [
        ('north', 'Nord'),
        ('south', 'Süd'),
        ('east', 'Ost'),
        ('west', 'West'),
    ]
    for key, title in tribunes:
        tribune_total = _int(row, f'capacity_{key}_total')
        standing = _int(row, f'capacity_{key}_standing')
        seated = _int(row, f'capacity_{key}_seated')
        vip = _int(row, f'capacity_{key}_vip')
        if standing + seated + vip != tribune_total:
            errors.append(
                f'Zeile {line_no} {label}: {title} Steh+Sitz+VIP '
                f'({standing + seated + vip}) != {title}-Gesamt ({tribune_total})'
            )

    return errors


def _unique_or_none(qs):
    count = qs.count()
    if count == 1:
        return qs.first()
    return None


def _find_club(row: dict[str, str]) -> Club | None:
    # 1) Transfermarkt-ID
    for key in ('tm_club_id', 'transfermarkt_id', 'tm_id'):
        raw = (row.get(key) or '').strip()
        if not raw:
            continue
        try:
            tm_id = int(raw)
        except ValueError:
            continue
        if _model_has_field(Club, 'transfermarkt_id'):
            club = Club.objects.filter(transfermarkt_id=tm_id).first()
            if club:
                return club

    # 2) Slug/club_slug gegen Namen, Bindestriche zu Leerzeichen.
    for key in ('club_slug', 'slug'):
        raw = (row.get(key) or '').strip()
        if not raw:
            continue
        candidate = raw.replace('-', ' ')
        club = Club.objects.filter(name__iexact=candidate).first()
        if club:
            return club
        wanted = _norm_name(candidate)
        matches = [club for club in Club.objects.all() if _norm_name(club.name) == wanted]
        if len(matches) == 1:
            return matches[0]

    # 3) Exakter Name, danach eindeutiges icontains.
    for key in ('club_name', 'name'):
        raw = (row.get(key) or '').strip()
        if not raw:
            continue
        club = Club.objects.filter(name__iexact=raw).first()
        if club:
            return club
        exact_norm_matches = [club for club in Club.objects.all() if _norm_name(club.name) == _norm_name(raw)]
        if len(exact_norm_matches) == 1:
            return exact_norm_matches[0]
        contains_qs = Club.objects.filter(Q(name__icontains=raw) | Q(short_name__icontains=raw))
        club = _unique_or_none(contains_qs)
        if club:
            return club

    return None


def _update_club_optional_fields(club: Club, row: dict[str, str]) -> int:
    update_fields: set[str] = set()

    _set_if_has(club, 'city', row.get('club_city', '').strip(), update_fields)
    _set_if_has(club, 'club_city', row.get('club_city', '').strip(), update_fields)
    _set_if_has(club, 'country', row.get('club_country', '').strip(), update_fields)
    _set_if_has(club, 'club_country', row.get('club_country', '').strip(), update_fields)
    _set_if_has(club, 'country_code', row.get('club_country_code', '').strip(), update_fields)
    _set_if_has(club, 'club_country_code', row.get('club_country_code', '').strip(), update_fields)

    club_lat = _float_or_none(row, 'club_latitude')
    club_lng = _float_or_none(row, 'club_longitude')
    if club_lat is not None:
        _set_if_has(club, 'latitude', club_lat, update_fields)
        _set_if_has(club, 'club_latitude', club_lat, update_fields)
    if club_lng is not None:
        _set_if_has(club, 'longitude', club_lng, update_fields)
        _set_if_has(club, 'club_longitude', club_lng, update_fields)

    if update_fields:
        club.save(update_fields=sorted(update_fields))
    return len(update_fields)


def _update_stadium(club: Club, row: dict[str, str]) -> tuple[Stadium, bool]:
    defaults = {
        'name': row.get('stadium_name', '').strip() or f'Stadion {club.name}',
        'city': row.get('stadium_city', '').strip() or row.get('club_city', '').strip(),
        'nord_standing': _int(row, 'capacity_north_standing'),
        'nord_seating': _int(row, 'capacity_north_seated'),
        'nord_vip': _int(row, 'capacity_north_vip'),
        'ost_standing': _int(row, 'capacity_east_standing'),
        'ost_seating': _int(row, 'capacity_east_seated'),
        'ost_vip': _int(row, 'capacity_east_vip'),
        'sued_standing': _int(row, 'capacity_south_standing'),
        'sued_seating': _int(row, 'capacity_south_seated'),
        'sued_vip': _int(row, 'capacity_south_vip'),
        'west_standing': _int(row, 'capacity_west_standing'),
        'west_seating': _int(row, 'capacity_west_seated'),
        'west_vip': _int(row, 'capacity_west_vip'),
    }
    stadium, created = Stadium.objects.update_or_create(club=club, defaults=defaults)
    return stadium, created


def _update_public_profile(club: Club, row: dict[str, str], stadium: Stadium) -> None:
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)
    update_fields: set[str] = set()

    _set_if_has(profile, 'stadium_name', stadium.name, update_fields)
    _set_if_has(profile, 'stadium_capacity', _int(row, 'stadium_capacity_total'), update_fields)
    _set_if_has(profile, 'city_name', row.get('club_city', '').strip(), update_fields)
    _set_if_has(profile, 'city_country', row.get('club_country', '').strip(), update_fields)

    club_lat = _float_or_none(row, 'club_latitude')
    club_lng = _float_or_none(row, 'club_longitude')
    if club_lat is not None:
        _set_if_has(profile, 'map_lat', club_lat, update_fields)
    if club_lng is not None:
        _set_if_has(profile, 'map_lng', club_lng, update_fields)

    if update_fields:
        profile.save(update_fields=sorted(update_fields))


class Command(BaseCommand):
    help = 'Importiert Stadion-, Kapazitäts- und öffentliche Vereinsprofil-Daten aus einer CSV.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', help='Pfad zur UTF-8-CSV mit Semikolon-Trennung.')
        parser.add_argument('--dry-run', action='store_true', help='Validieren und planen, aber nichts speichern.')
        parser.add_argument('--strict', action='store_true', help='Bei nicht gefundenen Clubs oder Summenfehlern abbrechen.')

    def handle(self, *args, **options):
        csv_path = Path(options['csv_path'])
        dry_run = options['dry_run']
        strict = options['strict']

        if not csv_path.exists():
            raise CommandError(f'CSV nicht gefunden: {csv_path}')

        with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle, delimiter=';')
            rows = list(reader)

        if not rows:
            raise CommandError('CSV enthält keine Datenzeilen.')

        found = 0
        missing: list[str] = []
        sum_errors: list[str] = []
        updated_clubs = 0
        updated_stadiums = 0
        created_stadiums = 0
        warnings: list[str] = []

        with transaction.atomic():
            for index, row in enumerate(rows, start=2):
                row_errors = _validate_row(row, index)
                sum_errors.extend(row_errors)
                if row_errors and strict:
                    continue

                club = _find_club(row)
                if not club:
                    missing.append(f'Zeile {index}: {_row_label(row)}')
                    continue

                found += 1
                if _update_club_optional_fields(club, row):
                    updated_clubs += 1

                stadium, created = _update_stadium(club, row)
                if created:
                    created_stadiums += 1
                else:
                    updated_stadiums += 1

                _update_public_profile(club, row, stadium)

                if (row.get('tribune_split_is_estimated') or '').strip() == '1':
                    warnings.append(f'{club.name}: Tribünenverteilung ist geschätzt.')
                if (row.get('vip_capacity_is_estimated') or '').strip() == '1':
                    warnings.append(f'{club.name}: VIP-Kapazität ist geschätzt.')

            fatal_errors: list[str] = []
            if strict and missing:
                fatal_errors.extend([f'Club nicht gefunden: {item}' for item in missing])
            if strict and sum_errors:
                fatal_errors.extend(sum_errors)

            if dry_run:
                transaction.set_rollback(True)

            self.stdout.write('──────────────────────────────────────────')
            self.stdout.write('Stadion-Import DRY-RUN' if dry_run else 'Stadion-Import')
            self.stdout.write('──────────────────────────────────────────')
            self.stdout.write(f'Gelesene Zeilen:          {len(rows)}')
            self.stdout.write(f'Gefundene Clubs:           {found}')
            self.stdout.write(f'Nicht gefunden:            {len(missing)}')
            self.stdout.write(f'Aktualisierte Clubs:       {updated_clubs}')
            self.stdout.write(f'Aktualisierte Stadien:     {updated_stadiums + created_stadiums}')
            self.stdout.write(f'  davon neu erstellt:      {created_stadiums}')
            self.stdout.write(f'Summenfehler:              {len(sum_errors)}')
            self.stdout.write('──────────────────────────────────────────')

            if missing:
                self.stdout.write(self.style.WARNING('Nicht gefundene Clubs:'))
                for item in missing:
                    self.stdout.write(f'  - {item}')

            if sum_errors:
                self.stdout.write(self.style.ERROR('Summenfehler:'))
                for item in sum_errors:
                    self.stdout.write(f'  - {item}')

            if warnings:
                self.stdout.write(self.style.WARNING('Hinweise:'))
                for item in warnings[:50]:
                    self.stdout.write(f'  - {item}')
                if len(warnings) > 50:
                    self.stdout.write(f'  - ... {len(warnings) - 50} weitere Hinweise')

            if dry_run:
                self.stdout.write(self.style.WARNING('Dry run: keine Änderungen gespeichert.'))

            if fatal_errors:
                raise CommandError(f'Import abgebrochen: {len(fatal_errors)} Fehler im Strict-Modus.')

        if not dry_run:
            self.stdout.write(self.style.SUCCESS('Import abgeschlossen.'))
