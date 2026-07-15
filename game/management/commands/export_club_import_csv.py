"""Management-Command: export_club_import_csv

Exportiert Spielerdaten eines WS-Vereins als import-ready CSV im kanonischen
Format (identisch zu PRESENT_COLUMNS aus field_schema.py). Alle Felder
werden direkt aus der Datenbank gelesen — insbesondere primary_nationality und
nationalities kommen aus Player.nationalities (nachdem backfill_nationality_from_cmt
die Werte auf dem Produktionsserver befüllt hat).

Verwendung:
    python manage.py export_club_import_csv --club "Holstein Kiel" --output kiel.csv
    python manage.py export_club_import_csv --all-affected --outdir exports/
    python manage.py export_club_import_csv --club "VfL Bochum" --season-id 2025 --season-label "2025/26"

Die erzeugten CSVs können direkt mit import_club_ready_csv re-importiert werden:
    python manage.py import_club_ready_csv --csv kiel.csv --mode update
"""

import csv
import os
import sys
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from game.club_import.import_ready_csv import FMI_ATTR_MAP, SOFIFA_ATTR_MAP
from game.models import DataSource, Player, PlayerExternalId, PlayerSourceRating


AFFECTED_CLUBS = [
    'Holstein Kiel',
    '1. FSV Mainz 05',
    'VfL Bochum',
    'FC St. Pauli',
    'Bayer 04 Leverkusen',
    'RB Leipzig',
    'Eintracht Frankfurt',
    '1. FC Union Berlin',
    'SV Werder Bremen',
]

_FMI_PSR_TO_CSV = {v: k for k, v in FMI_ATTR_MAP.items()}
_SOFIFA_PSR_TO_CSV = {v: k for k, v in SOFIFA_ATTR_MAP.items()}

FIELDNAMES = [
    'club_name', 'club_short_name', 'founded_year', 'club_city', 'country',
    'latitude', 'longitude', 'fmi_club_id', 'tm_club_id', 'stadium_name',
    'stadium_city', 'stadium_capacity', 'season_id', 'season_label', 'ws_club',
    'real_club', 'loaned_from', 'squad_status', 'fm_unique_id', 'tm_player_id',
    'tm_url', 'fmi_url', 'sofifa_id', 'sofifa_url', 'first_name', 'last_name',
    'display_name', 'date_of_birth', 'height_cm', 'preferred_foot',
    'primary_nationality', 'nationalities', 'tm_market_value_eur',
    'hp_positions', 'np_positions', 'position_method',
    'fmi_rating', 'fmi_potential',
    'fmi_pace', 'fmi_stamina', 'fmi_strength', 'fmi_technique', 'fmi_dribbling',
    'fmi_passing', 'fmi_crossing', 'fmi_tackling', 'fmi_positioning',
    'fmi_finishing', 'fmi_heading', 'fmi_vision', 'fmi_teamwork', 'fmi_corners',
    'fmi_free_kick_taking', 'fmi_penalty_taking', 'fmi_gk_reflexes',
    'fmi_gk_handling', 'fmi_gk_one_on_ones', 'fmi_gk_positioning', 'fmi_gk_passing',
    'sofifa_rating', 'sofifa_potential',
    'sofifa_pace', 'sofifa_stamina', 'sofifa_strength', 'sofifa_dribbling',
    'sofifa_short_passing', 'sofifa_long_passing', 'sofifa_crossing',
    'sofifa_finishing', 'sofifa_heading', 'sofifa_standing_tackle',
    'sofifa_defensive_awareness', 'sofifa_vision', 'sofifa_free_kick',
    'sofifa_penalties', 'sofifa_gk_reflexes', 'sofifa_gk_handling',
    'sofifa_gk_positioning', 'sofifa_gk_passing',
    'fmi_source_version', 'sofifa_source_version', 'source_checked_at',
    'data_status', 'validation_warning',
]


def _safe(v):
    return '' if v is None else v


def _psr_fmi_row(psr):
    row = {}
    if psr is None:
        return row
    row['fmi_rating'] = _safe(psr.rating)
    row['fmi_potential'] = _safe(psr.potential)
    row['fmi_source_version'] = psr.source_version or ''
    row['fmi_url'] = psr.source_url or ''
    if psr.checked_at:
        row['source_checked_at'] = psr.checked_at.isoformat()
    for psr_field, csv_suffix in _FMI_PSR_TO_CSV.items():
        val = getattr(psr, psr_field, None)
        row[f'fmi_{csv_suffix}'] = '' if val is None else val
    return row


def _psr_sofifa_row(psr):
    row = {}
    if psr is None:
        return row
    row['sofifa_rating'] = _safe(psr.rating)
    row['sofifa_potential'] = _safe(psr.potential)
    row['sofifa_source_version'] = psr.source_version or ''
    if psr.checked_at and not row.get('source_checked_at'):
        row['source_checked_at'] = psr.checked_at.isoformat()
    for psr_field, csv_suffix in _SOFIFA_PSR_TO_CSV.items():
        val = getattr(psr, psr_field, None)
        row[f'sofifa_{csv_suffix}'] = '' if val is None else val
    return row


def export_club(club, season_id, season_label, outfile):
    from game.models import Club

    try:
        profile = club.public_profile
    except Exception:
        profile = None
    try:
        stadium = club.stadium
    except Exception:
        stadium = None

    club_info = {
        'club_name':      club.name,
        'club_short_name': club.short_name or club.name[:20],
        'founded_year':   club.founded_year or '',
        'club_city':      profile.city_name if profile else '',
        'country':        profile.city_country if profile else '',
        'latitude':       profile.map_lat if profile and profile.map_lat is not None else '',
        'longitude':      profile.map_lng if profile and profile.map_lng is not None else '',
        'fmi_club_id':    club.fm_inside_id or '',
        'tm_club_id':     club.transfermarkt_id or '',
        'stadium_name':   profile.stadium_name if profile else '',
        'stadium_city':   stadium.city if stadium else '',
        'stadium_capacity': profile.stadium_capacity if profile else '',
        'season_id':      season_id,
        'season_label':   season_label,
        'ws_club':        club.name,
    }

    players = (
        Player.objects
        .filter(club=club)
        .select_related('real_life_club', 'loan_partner_club')
        .prefetch_related('source_ratings')
        .order_by('last_name', 'first_name')
    )

    player_ids = [p.id for p in players]
    cmt_source = DataSource.objects.filter(code=DataSource.CODE_CMTRACKER).first()
    ext_id_map = {}
    ext_url_map = {}
    if cmt_source and player_ids:
        for ei in PlayerExternalId.objects.filter(
            player_id__in=player_ids, source=cmt_source
        ):
            ext_id_map[ei.player_id] = ei.external_id
            ext_url_map[ei.player_id] = ei.profile_url or ''

    psr_map = {}
    for psr in PlayerSourceRating.objects.filter(player_id__in=player_ids):
        psr_map[(psr.player_id, psr.source)] = psr

    writer = csv.DictWriter(outfile, fieldnames=FIELDNAMES, extrasaction='ignore')
    writer.writeheader()

    for player in players:
        psr_fmi = psr_map.get((player.id, PlayerSourceRating.SOURCE_FM))
        psr_cmt = psr_map.get((player.id, PlayerSourceRating.SOURCE_CMTRACKER))

        fmi_row = _psr_fmi_row(psr_fmi)
        cmt_row = _psr_sofifa_row(psr_cmt)

        mains = [p for p in [
            player.main_position_1, player.main_position_2, player.main_position_3
        ] if p]
        secs = [p for p in [
            player.secondary_position_1, player.secondary_position_2, player.secondary_position_3
        ] if p]

        squad_status = 'first_team'
        loaned_from = ''
        real_club = ''
        if player.loan_status == 'loaned_in':
            squad_status = 'loaned_in'
            if player.loan_partner_club:
                loaned_from = player.loan_partner_club.name
        elif player.loan_status == 'loaned_out':
            squad_status = 'loaned_out'
            if player.real_life_club and player.real_life_club != club:
                real_club = player.real_life_club.name
        else:
            if player.real_life_club and player.real_life_club != club:
                real_club = player.real_life_club.name

        # DB speichert Nationalitäten als ", "-getrennte Liste ("Deutschland, Türkei").
        # Der Importer erwartet jedoch "|"-getrennte Tokens in der nationalities-Spalte.
        # primary_nationality ist immer der erste Token.
        nats_db = player.nationalities or ''
        nat_parts = [p.strip() for p in nats_db.split(',') if p.strip()]
        primary_nat = nat_parts[0] if nat_parts else ''
        nats_pipe = '|'.join(nat_parts)

        foot_map = {'L': 'links', 'R': 'rechts', 'B': 'beidfüßig'}
        preferred_foot = foot_map.get(player.strong_foot, player.strong_foot or '')

        checked_at = fmi_row.get('source_checked_at') or cmt_row.get('source_checked_at', '')

        market_val = ''
        if player.market_value is not None:
            market_val = int(player.market_value)

        row = {
            **club_info,
            'real_club':          real_club,
            'loaned_from':        loaned_from,
            'squad_status':       squad_status,
            'fm_unique_id':       player.fm_inside_id or '',
            'tm_player_id':       player.transfermarkt_id or '',
            'tm_url':             player.transfermarkt_profile_url or '',
            'fmi_url':            fmi_row.get('fmi_url', ''),
            'sofifa_id':          ext_id_map.get(player.id, ''),
            'sofifa_url':         ext_url_map.get(player.id, ''),
            'first_name':         player.first_name or '',
            'last_name':          player.last_name or '',
            'display_name':       f'{player.first_name or ""} {player.last_name or ""}'.strip(),
            'date_of_birth':      player.date_of_birth.isoformat() if player.date_of_birth else '',
            'height_cm':          player.height_cm or '',
            'preferred_foot':     preferred_foot,
            'primary_nationality': primary_nat,
            'nationalities':      nats_pipe,
            'tm_market_value_eur': market_val,
            'hp_positions':       '|'.join(mains),
            'np_positions':       '|'.join(secs),
            'position_method':    'hp_np',
            'source_checked_at':  checked_at,
            'data_status':        'ok',
            'validation_warning': '',
            **fmi_row,
            **cmt_row,
        }

        writer.writerow(row)

    return len(players)


class Command(BaseCommand):
    help = (
        'Exportiert Spielerdaten eines WS-Vereins als import-ready CSV '
        '(PRESENT_COLUMNS-Format). Nationality wird direkt aus der DB gelesen, '
        'sodass nach backfill_nationality_from_cmt die Spalten befüllt sind. '
        'Verwendung: --club <Name> --output <Datei> oder --all-affected --outdir <Dir>.'
    )

    def add_arguments(self, parser):
        grp = parser.add_mutually_exclusive_group(required=True)
        grp.add_argument(
            '--club',
            metavar='NAME',
            help='Vereinsname (Teilstring, case-insensitive).',
        )
        grp.add_argument(
            '--all-affected',
            action='store_true',
            help=f'Alle {len(AFFECTED_CLUBS)} betroffenen Vereine exportieren.',
        )
        parser.add_argument(
            '--output',
            metavar='DATEI',
            default='',
            help='Ausgabedatei (nur bei --club; leer = stdout).',
        )
        parser.add_argument(
            '--outdir',
            metavar='VERZEICHNIS',
            default='exports',
            help='Ausgabeverzeichnis bei --all-affected (Standard: exports/).',
        )
        parser.add_argument(
            '--season-id',
            type=int,
            default=2025,
            help='Saison-ID (Standard: 2025).',
        )
        parser.add_argument(
            '--season-label',
            default='2025/26',
            help='Saison-Label (Standard: "2025/26").',
        )

    def handle(self, *args, **options):
        from game.models import Club

        season_id = options['season_id']
        season_label = options['season_label']

        if options['all_affected']:
            outdir = options['outdir']
            os.makedirs(outdir, exist_ok=True)
            total_clubs = 0
            total_players = 0
            for club_name in AFFECTED_CLUBS:
                try:
                    club = Club.objects.get(name=club_name)
                except Club.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f'  [übersprungen] {club_name!r} nicht in DB gefunden.'
                    ))
                    continue
                slug = club_name.lower().replace(' ', '_').replace('.', '').replace('/', '_')
                outpath = os.path.join(outdir, f'{slug}_import_ready.csv')
                with open(outpath, 'w', newline='', encoding='utf-8') as fh:
                    count = export_club(club, season_id, season_label, fh)
                self.stdout.write(
                    self.style.SUCCESS(f'  {club.name}: {count} Spieler → {outpath}')
                )
                total_clubs += 1
                total_players += count
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n{total_clubs} Vereine, {total_players} Spieler exportiert.'
                )
            )
        else:
            club_filter = options['club'].strip()
            clubs = Club.objects.filter(name__icontains=club_filter)
            if not clubs.exists():
                raise CommandError(f'Kein Verein gefunden für "{club_filter}".')
            if clubs.count() > 1:
                names = ', '.join(c.name for c in clubs[:10])
                raise CommandError(
                    f'Mehrere Vereine gefunden ({clubs.count()}): {names}. '
                    'Bitte präziseren Namen angeben.'
                )
            club = clubs.first()
            outpath = options['output'].strip()
            if outpath:
                with open(outpath, 'w', newline='', encoding='utf-8') as fh:
                    count = export_club(club, season_id, season_label, fh)
                self.stdout.write(
                    self.style.SUCCESS(f'{club.name}: {count} Spieler → {outpath}')
                )
            else:
                count = export_club(club, season_id, season_label, sys.stdout)
                self.stderr.write(
                    self.style.SUCCESS(f'\n{club.name}: {count} Spieler (stdout).')
                )
