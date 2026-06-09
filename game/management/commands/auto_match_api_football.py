"""
Management command: auto_match_api_football

Automatisch API-Football Player IDs zuordnen, basierend auf:
1. Name (akzentfrei, normalisiert)
2. Geburtsdatum (exakt)
3. RL-Verein (player.real_life_club.api_football_id == team.id)

Nur für Spieler OHNE PlayerRLFormProfile. Erstellt Profile bei Erfolg.

Zweistufig:
- Phase 1: squad-Liste (alle Seiten, 1–4 Requests) für alle Spieler
- Phase 2: individuelle Suche für die Restlichen

Usage:
    python manage.py auto_match_api_football --club Bayern
    python manage.py auto_match_api_football --player-id 1510
    python manage.py auto_match_api_football --dry-run
    python manage.py auto_match_api_football --season 2024
"""
import re
import time
import unicodedata
from datetime import datetime

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from game.api_football import API_BASE, _headers, search_player
from game.models import Player, PlayerRLFormProfile


def _normalize_name(name):
    """NFD Decomposition + strip combining diacritical marks, lowercase."""
    return re.sub(r'[\u0300-\u036f]', '', unicodedata.normalize('NFD', name)).lower().strip()


class Command(BaseCommand):
    help = 'Auto-match API-Football Player IDs für Spieler ohne RL-Mapping.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--club',
            type=str,
            default=None,
            help='Nur Club (Name oder Teilname, z.B. "Bayern")',
        )
        parser.add_argument(
            '--player-id',
            type=int,
            default=None,
            help='Nur einen Spieler (Django-PK)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Nur vorschauen, keine DB-Änderungen',
        )
        parser.add_argument(
            '--season',
            type=int,
            default=2024,
            help='API-Football Saison (default: 2024)',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=3.0,
            help='Pause zwischen API-Requests (Sekunden, default: 3.0 für Free Plan)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Detaillierte Ausgabe',
        )

    def _get_squad(self, team_api_id, season):
        """Holt alle Spieler des Kaders via /players?team={id}&season={year}.
        Paginiert (max. 4 Seiten = 80 Spieler)."""
        squad = []
        for page in range(1, 5):
            resp = requests.get(
                f'{API_BASE}/players',
                headers=_headers(),
                params={'team': team_api_id, 'season': season, 'page': page},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            for entry in data.get('response', []):
                player = entry.get('player', {})
                squad.append({
                    'id': player.get('id'),
                    'name': player.get('name'),
                    'dob': player.get('birth', {}).get('date'),
                })
            paging = data.get('paging', {})
            if paging.get('current', page) >= paging.get('total', page):
                break
        return squad

    def _try_match(self, player, squad, fallback_search=False, team_api_id=None, season=None, sleep=0, verbose=False):
        """Match via squad (DOB) oder fallback search. Returns dict or None."""
        target_dob = player.date_of_birth
        target_name = f'{player.first_name} {player.last_name}'
        target_norm = _normalize_name(target_name)
        target_last = _normalize_name(player.last_name)

        # Phase 1: Squad (DOB)
        for s in squad:
            if s['dob'] and str(s['dob']) == str(target_dob):
                s_norm = _normalize_name(s['name'])
                if s_norm == target_norm or target_last in s_norm:
                    if verbose:
                        self.stdout.write(f'    Squad-Match: {s["name"]} (DOB={s["dob"]})')
                    return {
                        'api_football_player_id': s['id'],
                        'api_football_team_id': team_api_id,
                        'api_name': s['name'],
                        'api_dob': s['dob'],
                    }

        # Phase 2: Search (bei Missing)
        if not fallback_search:
            return None

        search_name = player.last_name
        if len(search_name) < 3:
            search_name = target_name

        try:
            results = search_player(search_name, team=team_api_id, season=season)
        except Exception as exc:
            if verbose:
                self.stdout.write(self.style.ERROR(f'    API-Fehler: {exc}'))
            return None

        if sleep:
            time.sleep(sleep)

        for entry in results:
            api_player = entry.get('player', {})
            api_name = api_player.get('name', '')
            api_dob_str = api_player.get('birth', {}).get('date', '')
            stats_list = entry.get('statistics', [])
            api_team_id = stats_list[0].get('team', {}).get('id') if stats_list else None

            if not api_team_id or int(api_team_id) != int(team_api_id):
                continue

            if api_dob_str:
                try:
                    api_dob = datetime.strptime(api_dob_str, '%Y-%m-%d').date()
                except ValueError:
                    api_dob = None
            else:
                api_dob = None

            if api_dob and api_dob != target_dob:
                continue

            api_name_norm = _normalize_name(api_name)
            if api_name_norm != target_norm:
                api_last = _normalize_name(api_name.split()[-1] if api_name else '')
                if api_last != target_last:
                    continue

            return {
                'api_football_player_id': api_player['id'],
                'api_football_team_id': api_team_id,
                'api_name': api_name,
                'api_dob': api_dob_str,
            }

        return None

    def _save_match(self, player, found, season, dry_run):
        rl_profile, _ = PlayerRLFormProfile.objects.get_or_create(
            player=player,
            defaults={
                'api_football_season': season,
                'api_football_team_id': found['api_football_team_id'],
            }
        )
        if not dry_run:
            rl_profile.api_football_player_id = found['api_football_player_id']
            rl_profile.api_football_team_id     = found['api_football_team_id']
            rl_profile.api_football_team_name   = player.real_life_club.name
            rl_profile.api_football_season      = season
            rl_profile.rl_form_status           = PlayerRLFormProfile.STATUS_NOT_FETCHED
            rl_profile.rl_form_updated_at       = timezone.now()
            rl_profile.save()

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        season  = options['season']
        sleep   = options['sleep']
        verbose = options['verbose']

        # Nur Spieler ohne RL-Mapping
        players = Player.objects.select_related('real_life_club').filter(
            rl_form_profile__api_football_player_id=None,
        ).exclude(
            real_life_club_id=None
        ).exclude(
            date_of_birth=None
        )

        if options['player_id']:
            players = players.filter(id=options['player_id'])

        if options['club']:
            players = players.filter(
                club__name__icontains=options['club']
            ) | players.filter(
                real_life_club__name__icontains=options['club']
            )
            players = players.distinct()

        players = list(players)
        if not players:
            self.stdout.write('Keine Spieler zum Mappen gefunden (alle haben bereits api_football_player_id).')
            return

        self.stdout.write(
            f'{len(players)} Spieler zu prüfen | Saison {season} | '
            f'{"DRY-RUN" if dry_run else "LIVE"}'
        )

        # Pro Team: Squad holen
        teams = {}
        for p in players:
            tid = p.real_life_club.api_football_id if p.real_life_club else None
            if tid:
                teams.setdefault(tid, []).append(p)

        matched = 0
        unmatched = 0
        errors = 0

        for team_api_id, team_players in teams.items():
            self.stdout.write(f'\n→ Team {team_api_id}: {len(team_players)} Spieler')

            try:
                squad = self._get_squad(team_api_id, season)
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f'  Fehler beim Squad-Load: {exc}')
                )
                errors += len(team_players)
                continue

            self.stdout.write(f'  Squad geladen: {len(squad)} Spieler')
            if sleep:
                time.sleep(sleep)

            for p in team_players:
                found = self._try_match(
                    p, squad,
                    fallback_search=True,
                    team_api_id=team_api_id,
                    season=season,
                    sleep=sleep,
                    verbose=verbose,
                )

                if not found:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ✗ {p.first_name} {p.last_name}: Kein Match '
                            f'(DOB={p.date_of_birth}, Team={team_api_id})'
                        )
                    )
                    unmatched += 1
                    continue

                self._save_match(p, found, season, dry_run)
                matched += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ {p.first_name} {p.last_name} '
                        f'→ API-ID {found["api_football_player_id"]} '
                        f'(Name: {found["api_name"]}, DOB: {found["api_dob"]})'
                    )
                )

        self.stdout.write(
            f'\nErgebnis: {matched} gematcht, {unmatched} ungematcht, {errors} Fehler '
            f'von {len(players)} Spielern.'
        )
