"""
Management-Command: fetch_rl_form_data
Budget-effizientes Laden von RL-Form-Daten aus API-Football.

Pro Team: 1 Request (Fixtures) + max. 10 Requests (Spieler-Stats) = 11 Requests.
Nur Spieler mit gültigem PlayerRLFormProfile-Mapping werden verarbeitet.

Beispiel-Aufruf:
    python manage.py fetch_rl_form_data --team-api-id 157
    python manage.py fetch_rl_form_data --player-id 123 --dry-run
    python manage.py fetch_rl_form_data --budget 22      # zwei Teams
    python manage.py fetch_rl_form_data                  # alle gemappten Teams
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

SNAPSHOTS_PER_PLAYER = 10


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
            '--budget',
            type=int,
            default=50,
            help=(
                'Maximale Anzahl API-Requests (default: 50). '
                'Entspricht ~4 Teams (à 11 Requests). '
                'Das Tages-Limit von API-Football liegt bei 100 Requests.'
            ),
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
            default=6.0,
            help='Pause (Sekunden) zwischen Requests (default: 6.0 für Free Plan 10/Min).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force   = options['force']
        budget  = options['budget']
        sleep   = options['sleep']

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
            f'Budget: {budget} Requests | '
            f'{len(profiles)} Spieler in {len(teams)} Team(s).'
        )

        requests_used  = 0
        total_snapshots = 0

        def _use_request(label):
            """Prüft Budget, erhöht Zähler, schläft. Gibt False zurück wenn Budget aufgebraucht."""
            nonlocal requests_used
            if requests_used >= budget:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠ Budget erschöpft ({requests_used}/{budget}). '
                        f'Verbleibende Teams/Fixtures werden übersprungen.'
                    )
                )
                return False
            requests_used += 1
            remaining = budget - requests_used
            self.stdout.write(
                f'  [{requests_used}/{budget} | {remaining} verbleibend] {label}'
            )
            if sleep and not dry_run:
                time.sleep(sleep)
            return True

        for team_id, team_profiles in teams.items():
            if requests_used >= budget:
                self.stdout.write(
                    self.style.WARNING('Budget aufgebraucht — weitere Teams übersprungen.')
                )
                break

            team_name = team_profiles[0].api_football_team_name or str(team_id)
            self.stdout.write(f'\n→ Team {team_name} (ID {team_id}): {len(team_profiles)} Spieler')

            season = team_profiles[0].api_football_season
            if not _use_request(f'GET /fixtures?team={team_id}&season={season}'):
                break

            try:
                fixtures = get_team_fixtures(team_id, season=season, last=10)
            except requests.RequestException as exc:
                self.stdout.write(self.style.ERROR(f'  Fehler beim Laden der Fixtures: {exc}'))
                if not dry_run:
                    for p in team_profiles:
                        p.rl_form_status  = PlayerRLFormProfile.STATUS_API_ERROR
                        p.rl_form_updated_at = timezone.now()
                        p.save(update_fields=['rl_form_status', 'rl_form_updated_at'])
                continue

            player_map = {p.api_football_player_id: p for p in team_profiles}

            for fixture in fixtures:
                if requests_used >= budget:
                    self.stdout.write(
                        self.style.WARNING('  Budget erschöpft — restliche Fixtures übersprungen.')
                    )
                    break

                fix_id       = fixture['fixture']['id']
                fix_date_str = fixture['fixture']['date'][:10]
                fix_date     = date.fromisoformat(fix_date_str)
                league_id    = fixture.get('league', {}).get('id', 0)
                home         = fixture.get('teams', {}).get('home', {})
                away         = fixture.get('teams', {}).get('away', {})
                opp_name     = away.get('name', '') if home.get('id') == team_id else home.get('name', '')

                # Per-Player prüfen, nicht per-Fixture: nur wenn ALLE Spieler das Fixture
                # bereits haben, darf es übersprungen werden.
                if not force:
                    players_missing = [
                        p for p in team_profiles
                        if not PlayerFormSnapshot.objects.filter(
                            player=p.player,
                            source=PlayerFormSnapshot.SOURCE_API_FOOTBALL,
                            fixture_id=str(fix_id),
                        ).exists()
                    ]
                    if not players_missing:
                        self.stdout.write(
                            f'  Fixture {fix_id} ({fix_date_str}) — alle Spieler vorhanden, übersprungen'
                        )
                        continue
                else:
                    players_missing = list(team_profiles)

                if not _use_request(f'GET /fixtures/players?fixture={fix_id}&team={team_id}'):
                    break

                try:
                    player_stats_list = get_fixture_player_stats(fix_id, team_id)
                except requests.RequestException as exc:
                    self.stdout.write(
                        self.style.WARNING(f'  Fixture {fix_id}: Netzwerkfehler {exc} — übersprungen')
                    )
                    if not dry_run:
                        for p in players_missing:
                            p.rl_form_status     = PlayerRLFormProfile.STATUS_API_ERROR
                            p.rl_form_updated_at = timezone.now()
                            p.save(update_fields=['rl_form_status', 'rl_form_updated_at'])
                    continue

                stats_by_player_id = {
                    entry.get('player', {}).get('id'): entry
                    for entry in player_stats_list
                    if entry.get('player', {}).get('id') is not None
                }

                missing_ids = {p.api_football_player_id for p in players_missing}
                for api_player_id, profile in player_map.items():
                    # Snapshot nur schreiben wenn dieser Spieler fehlt (oder --force)
                    if api_player_id not in missing_ids and not force:
                        continue
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
                # Stale Snapshots bereinigen: nur die neuesten SNAPSHOTS_PER_PLAYER behalten
                for profile in team_profiles:
                    player = profile.player
                    all_snap_ids = list(
                        PlayerFormSnapshot.objects
                        .filter(player=player, source=PlayerFormSnapshot.SOURCE_API_FOOTBALL)
                        .order_by('-fixture_date')
                        .values_list('id', flat=True)
                    )
                    stale_ids = all_snap_ids[SNAPSHOTS_PER_PLAYER:]
                    if stale_ids:
                        deleted, _ = PlayerFormSnapshot.objects.filter(id__in=stale_ids).delete()
                        if deleted:
                            self.stdout.write(f'  🗑 {profile.player.last_name}: {deleted} alte Snapshot(s) entfernt')

                    compute_rl_form_for_player(player, mark_fetched=True)
                    # Profil neu laden (compute_rl_form_for_player schreibt direkt in DB)
                    profile.refresh_from_db()
                    self.stdout.write(
                        f'  → RL-Form {profile.player.last_name}: '
                        f'{profile.rl_form_score:+d} (Fit {profile.rl_form_fit})'
                    )

        remaining = max(0, budget - requests_used)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nFertig: {requests_used}/{budget} Requests verbraucht '
                f'({remaining} verbleibend) | {total_snapshots} Snapshot(s) gespeichert.'
            )
        )
