"""
Management-Command: fetch_rl_form_data
Budget-effizientes Laden von RL-Form-Daten aus API-Football.

Pro Team: 1 Request (Fixtures) + max. 10 Requests (Spieler-Stats) = 11 Requests.
Nur Spieler mit gültigem PlayerRLFormProfile-Mapping werden verarbeitet.

Beispiel-Aufruf:
    python manage.py fetch_rl_form_data --team-api-id 157
    python manage.py fetch_rl_form_data --player-id 123 --dry-run
    python manage.py fetch_rl_form_data  # alle gemappten Teams
"""

import time
from datetime import date
from decimal import Decimal, InvalidOperation

import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.api_football import get_fixture_player_stats, get_team_fixtures
from game.models import Player, PlayerFormSnapshot, PlayerRLFormProfile
from game.strength_service import compute_rl_form_for_player


class Command(BaseCommand):
    help = 'Lädt RL-Form-Daten teamweise aus API-Football (11 Requests pro Team).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--team-api-id',
            type=int,
            default=None,
            help='Nur dieses Team verarbeiten (api_football_team_id).',
        )
        parser.add_argument(
            '--player-id',
            type=int,
            default=None,
            help='Nur diesen Spieler verarbeiten (Django-PK); Team wird automatisch ermittelt.',
        )
        parser.add_argument(
            '--last-fixtures',
            type=int,
            default=10,
            help='Anzahl der letzten Spieltage (default: 10).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Vorhandene Snapshots überschreiben.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Keine DB-Schreibvorgänge; nur Ausgabe was gefunden wurde.',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.3,
            help='Pause (Sekunden) zwischen Requests (default: 0.3).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        last = options['last_fixtures']
        sleep = options['sleep']

        profiles_qs = PlayerRLFormProfile.objects.select_related('player').filter(
            api_football_player_id__isnull=False,
            api_football_team_id__isnull=False,
        )

        if options['player_id']:
            profiles_qs = profiles_qs.filter(player_id=options['player_id'])

        if options['team_api_id']:
            profiles_qs = profiles_qs.filter(api_football_team_id=options['team_api_id'])

        profiles = list(profiles_qs)
        if not profiles:
            self.stdout.write(self.style.WARNING('Keine gemappten Spieler gefunden.'))
            return

        teams = {}
        for p in profiles:
            teams.setdefault(p.api_football_team_id, []).append(p)

        self.stdout.write(
            f'Verarbeite {len(profiles)} Spieler in {len(teams)} Team(s).'
        )

        total_requests = 0
        total_snapshots = 0

        for team_id, team_profiles in teams.items():
            team_name = team_profiles[0].api_football_team_name or str(team_id)
            self.stdout.write(
                f'\n→ Team {team_name} (ID {team_id}): {len(team_profiles)} Spieler'
            )

            try:
                fixtures = get_team_fixtures(team_id, last=last)
                total_requests += 1
                if sleep:
                    time.sleep(sleep)
            except requests.HTTPError as exc:
                self.stdout.write(
                    self.style.ERROR(f'  Fehler beim Laden der Fixtures: {exc}')
                )
                for p in team_profiles:
                    if not dry_run:
                        p.rl_form_status = PlayerRLFormProfile.STATUS_API_ERROR
                        p.rl_form_updated_at = timezone.now()
                        p.save(update_fields=['rl_form_status', 'rl_form_updated_at'])
                continue

            player_map = {
                p.api_football_player_id: p for p in team_profiles
            }

            for fixture in fixtures:
                fix_id = fixture['fixture']['id']
                fix_date_str = fixture['fixture']['date'][:10]
                fix_date = date.fromisoformat(fix_date_str)

                home = fixture.get('teams', {}).get('home', {})
                away = fixture.get('teams', {}).get('away', {})
                if home.get('id') == team_id:
                    opp_name = away.get('name', '')
                else:
                    opp_name = home.get('name', '')

                league_id = fixture.get('league', {}).get('id', 0)

                existing_check = PlayerFormSnapshot.objects.filter(
                    player__in=[p.player for p in team_profiles],
                    source=PlayerFormSnapshot.SOURCE_API_FOOTBALL,
                    fixture_id=str(fix_id),
                )
                if not force and existing_check.exists():
                    self.stdout.write(f'  Fixture {fix_id} ({fix_date_str}) — übersprungen (bereits vorhanden)')
                    continue

                try:
                    player_stats_list = get_fixture_player_stats(fix_id, team_id)
                    total_requests += 1
                    if sleep:
                        time.sleep(sleep)
                except requests.HTTPError as exc:
                    self.stdout.write(
                        self.style.WARNING(f'  Fixture {fix_id}: HTTP-Fehler {exc} — übersprungen')
                    )
                    continue

                stats_by_player_id = {}
                for entry in player_stats_list:
                    pid = entry.get('player', {}).get('id')
                    if pid is not None:
                        stats_by_player_id[pid] = entry

                for api_player_id, profile in player_map.items():
                    entry = stats_by_player_id.get(api_player_id)
                    if entry is None:
                        continue

                    stats = (entry.get('statistics') or [{}])[0]
                    games = stats.get('games') or {}
                    goals = stats.get('goals') or {}
                    cards = stats.get('cards') or {}

                    minutes = games.get('minutes') or 0
                    raw_rating = games.get('rating')
                    try:
                        rating = Decimal(str(raw_rating)).quantize(Decimal('0.01')) if raw_rating else None
                    except InvalidOperation:
                        rating = None

                    substituted_in = bool(games.get('substitute', False))

                    snapshot_data = {
                        'fixture_date':           fix_date,
                        'league_api_football_id': league_id,
                        'team_api_football_id':   team_id,
                        'team_name':              team_name,
                        'opponent_name':          opp_name,
                        'minutes_played':         minutes,
                        'possible_minutes':       90,
                        'started':                minutes > 0 and not substituted_in,
                        'substituted_in':         substituted_in,
                        'captain':                bool(games.get('captain', False)),
                        'position':               games.get('position') or '',
                        'rating':                 rating,
                        'goals':                  goals.get('total') or 0,
                        'assists':                goals.get('assists') or 0,
                        'yellow_cards':           cards.get('yellow') or 0,
                        'red_cards':              cards.get('red') or 0,
                        'raw_payload':            entry,
                    }

                    name = entry.get('player', {}).get('name', '')
                    if dry_run:
                        self.stdout.write(
                            f'  [dry] {profile.player.last_name} ({api_player_id}): '
                            f'{fix_date_str} {minutes} Min. Rating={rating or "–"}'
                        )
                    else:
                        PlayerFormSnapshot.objects.update_or_create(
                            player=profile.player,
                            source=PlayerFormSnapshot.SOURCE_API_FOOTBALL,
                            fixture_id=str(fix_id),
                            defaults=snapshot_data,
                        )
                        total_snapshots += 1
                        self.stdout.write(
                            f'  ✓ {profile.player.last_name}: {fix_date_str} '
                            f'{minutes} Min. Rating={rating or "–"}'
                        )

            if not dry_run:
                for profile in team_profiles:
                    compute_rl_form_for_player(profile.player)
                    self.stdout.write(
                        f'  → RL-Form {profile.player.last_name}: '
                        f'{profile.rl_form_score:+d} (Fit {profile.rl_form_fit})'
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nFertig: {total_requests} API-Requests, {total_snapshots} Snapshots gespeichert.'
            )
        )
