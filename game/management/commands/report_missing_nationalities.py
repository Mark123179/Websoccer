"""Management-Command: report_missing_nationalities

Analysiert Spieler ohne Nationalitätsangabe (leeres nationalities- UND leeres
nt_nationality-Feld) und gibt einen gruppierten Report aus.

Ausgabe-Formate:
  --format=text   (Standard) Lesbare Konsolentabelle, gruppiert nach Verein.
  --format=csv    CSV in stdout; mit --output=<Datei> in eine Datei schreiben.

Zusätzliche Filter:
  --club <Name>   Nur einen bestimmten Verein ausgeben.

Kontext: Die 127 Spieler (Stand 2026-07) wurden alle via CSV-Import angelegt
(wsc_player_id-Präfix WSC-), haben aber leere primary_nationality/nationalities-
Spalten in den Import-CSVs. Alle besitzen TM-ID, FMI-ID und eine CMT-External-ID
(PlayerExternalId mit DataSource CMTRACKER) — die eigentlichen CMT-Profile
(PlayerCMTProfile) fehlen noch. Zur automatisierten Befüllung via CMTracker-API
steht backfill_nationality_from_cmt bereit.
"""

import csv
import sys

from django.core.management.base import BaseCommand
from django.db.models import Count

from game.models import DataSource, Player, PlayerExternalId


class Command(BaseCommand):
    help = (
        'Report: Spieler ohne Nationalitätsangabe, gruppiert nach Verein. '
        '--format=csv exportiert alle Felder als CSV (inkl. CMT-Ext-ID, TM-ID, FMI-ID). '
        'Zur Behebung: backfill_nationality_from_cmt verwenden.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['text', 'csv'],
            default='text',
            help='Ausgabeformat: text (Standard) oder csv.',
        )
        parser.add_argument(
            '--output',
            metavar='DATEI',
            default='',
            help='Bei --format=csv: Zieldatei (leer = stdout).',
        )
        parser.add_argument(
            '--club',
            metavar='NAME',
            default='',
            help='Nur Spieler dieses Vereins ausgeben (Teilstring, Groß-/Kleinschreibung ignoriert).',
        )

    def handle(self, *args, **options):
        fmt = options['format']
        output_path = options['output'].strip()
        club_filter = options['club'].strip()

        qs = Player.objects.filter(
            nationalities='',
            nt_nationality='',
        ).select_related('club').order_by('club__name', 'last_name', 'first_name')

        if club_filter:
            qs = qs.filter(club__name__icontains=club_filter)

        players = list(qs)
        total = len(players)

        if total == 0:
            self.stdout.write(self.style.SUCCESS('Keine Spieler ohne Nationalität gefunden.'))
            return

        cmt_source = DataSource.objects.filter(code=DataSource.CODE_CMTRACKER).first()
        ext_id_map = {}
        if cmt_source:
            player_ids = [p.id for p in players]
            for ei in PlayerExternalId.objects.filter(
                player_id__in=player_ids,
                source=cmt_source,
            ):
                ext_id_map[ei.player_id] = ei.external_id

        if fmt == 'csv':
            self._output_csv(players, ext_id_map, output_path)
        else:
            self._output_text(players, ext_id_map, total)

    def _output_text(self, players, ext_id_map, total):
        self.stdout.write('')
        self.stdout.write(
            self.style.WARNING(
                f'Spieler ohne Nationalität: {total}'
            )
        )
        self.stdout.write('')

        by_club = {}
        for p in players:
            club_name = p.club.name if p.club else '(kein Verein)'
            by_club.setdefault(club_name, []).append(p)

        club_stats = (
            Player.objects.filter(nationalities='', nt_nationality='')
            .values('club__name')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )

        self.stdout.write(
            f'{"Verein":<35} {"Anzahl":>6}  {"TM-ID":>8}  {"FMI-ID":>12}  {"CMT-Ext-ID":>11}'
        )
        self.stdout.write('─' * 80)

        for row in club_stats:
            club_name = row['club__name'] or '(kein Verein)'
            club_players = by_club.get(club_name, [])
            has_tm = sum(1 for p in club_players if p.transfermarkt_id)
            has_fmi = sum(1 for p in club_players if p.fm_inside_id)
            has_cmt = sum(1 for p in club_players if ext_id_map.get(p.id))
            self.stdout.write(
                f'{club_name:<35} {row["cnt"]:>6}  {has_tm:>8}  {has_fmi:>12}  {has_cmt:>11}'
            )

        self.stdout.write('')
        self.stdout.write(
            'Legende: Spalten zeigen Anzahl Spieler mit jeweiliger ID befüllt.'
        )
        self.stdout.write('')
        self.stdout.write(
            'Ursache: primary_nationality/nationalities-Spalten in den Import-CSVs '
            'dieser Vereine waren leer.'
        )
        self.stdout.write(
            'Empfehlung: backfill_nationality_from_cmt --db <slug> --apply '
            'führt die CMTracker-API-Abfrage durch (nur auf dem Server verfügbar).'
        )
        self.stdout.write(
            'CSV-Export: python manage.py report_missing_nationalities --format=csv '
            '--output=missing_nationality.csv'
        )

    def _output_csv(self, players, ext_id_map, output_path):
        fieldnames = [
            'player_id',
            'full_name',
            'first_name',
            'last_name',
            'date_of_birth',
            'club',
            'wsc_player_id',
            'tm_player_id',
            'fmi_player_id',
            'cmt_external_id',
            'tm_profile_url',
        ]

        if output_path:
            fh = open(output_path, 'w', newline='', encoding='utf-8')
        else:
            fh = sys.stdout

        try:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for p in players:
                writer.writerow({
                    'player_id':      p.id,
                    'full_name':      p.full_name,
                    'first_name':     p.first_name,
                    'last_name':      p.last_name,
                    'date_of_birth':  p.date_of_birth.isoformat() if p.date_of_birth else '',
                    'club':           p.club.name if p.club else '',
                    'wsc_player_id':  p.wsc_player_id,
                    'tm_player_id':   p.transfermarkt_id or '',
                    'fmi_player_id':  p.fm_inside_id or '',
                    'cmt_external_id': ext_id_map.get(p.id, ''),
                    'tm_profile_url': p.transfermarkt_profile_url or '',
                })
        finally:
            if output_path:
                fh.close()
                self.stderr.write(
                    self.style.SUCCESS(f'{len(players)} Spieler nach {output_path!r} exportiert.')
                )
