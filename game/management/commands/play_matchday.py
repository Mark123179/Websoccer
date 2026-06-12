"""Management Command: play_matchday

Spielt alle Spiele eines Spieltags durch Match Engine V2.
Erstellt SimulatedMatch-Einträge, aktualisiert SeasonFixture und LeagueStandings.

Verwendung:
    python manage.py play_matchday --league <id> --matchday <n>
    python manage.py play_matchday --league <id> --matchday <n> --season <s>
    python manage.py play_matchday --league <id> --matchday <n> --force
    python manage.py play_matchday --league <id> --matchday <n> --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Spielt einen Spieltag durch V2-Engine, speichert Fixtures + Standings.'

    def add_arguments(self, parser):
        parser.add_argument('--league', type=int, required=True,
                            help='Datenbank-ID der Liga')
        parser.add_argument('--matchday', type=int, required=True,
                            help='Spieltag-Nummer')
        parser.add_argument('--season', type=str, default=None,
                            help='Saison (default: aktuell aus GameSeasonState)')
        parser.add_argument('--force', action='store_true', default=False,
                            help='Bereits gespielte Fixtures neu simulieren (V2-Re-Sim)')
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='Nur anzeigen, nichts speichern')

    def handle(self, *args, **options):
        from game.models import (
            League, SeasonFixture, SimulatedMatch,
            LeagueStandings, GameSeasonState,
        )
        from game.match_engine import simulate_match

        out = self.stdout.write

        # ── Liga + Saison ─────────────────────────────────────────────────────
        try:
            league = League.objects.get(pk=options['league'])
        except League.DoesNotExist:
            raise CommandError(f"Liga {options['league']} nicht gefunden.")

        if options['season'] is not None:
            season = options['season']
        else:
            gss = GameSeasonState.objects.first()
            season = str(gss.current_season) if gss else '0'

        matchday = options['matchday']
        force    = options['force']
        dry_run  = options['dry_run']

        out(f"\nLiga: {league.name} | Spieltag {matchday} | Saison {season}"
            + (' [FORCE]' if force else '')
            + (' [DRY-RUN]' if dry_run else ''))
        out('─' * 60)

        # ── Fixtures laden ────────────────────────────────────────────────────
        qs = (
            SeasonFixture.objects
            .filter(league=league, season=season, matchday=matchday)
            .select_related('home_club', 'away_club')
            .order_by('id')
        )
        if not qs.exists():
            raise CommandError(
                f"Keine Fixtures für Liga={league.pk}, ST={matchday}, Saison={season}."
            )

        to_play = list(qs) if force else [f for f in qs if not f.is_played]
        skipped = [f for f in qs if f.is_played and not force]

        if skipped:
            out(f"Übersprungen (bereits gespielt): {len(skipped)}")
            for f in skipped:
                out(f"  {f.home_club.short_name} {f.home_goals}:{f.away_goals} "
                    f"{f.away_club.short_name}")

        if not to_play:
            out(self.style.SUCCESS('\nAlle Spiele bereits gespielt — nichts zu tun.'))
            return

        out(f"Zu spielen: {len(to_play)}\n")

        # ── Spiele simulieren ─────────────────────────────────────────────────
        results = []
        errors  = []

        for fixture in to_play:
            home = fixture.home_club
            away = fixture.away_club
            try:
                data = simulate_match(home, away)
                hg   = data['home_goals']
                ag   = data['away_goals']
                ms   = data.get('match_stats', {})
                mode = data.get('simulation_mode', 'minutes')
                out(f"  {home.short_name or home.name[:10]:<12} "
                    f"{hg}:{ag} "
                    f"{away.short_name or away.name[:10]:<12} "
                    f"xG {data['home_xg']:.2f}/{data['away_xg']:.2f}  "
                    f"Schüsse {ms.get('home_shots',0)}/{ms.get('away_shots',0)}  "
                    f"[{mode}]")
                results.append((fixture, data, hg, ag))
            except Exception as exc:
                errors.append((fixture, str(exc)))
                out(self.style.WARNING(
                    f"  FEHLER {home.short_name} vs {away.short_name}: {exc}"
                ))

        if dry_run:
            out(self.style.SUCCESS(f'\n[DRY-RUN] {len(results)} Spiele simuliert (nicht gespeichert).'))
            return

        if not results:
            out(self.style.ERROR('\nKeine Spiele erfolgreich simuliert.'))
            return

        # ── DB-Schreiben in einer Transaktion ─────────────────────────────────
        with transaction.atomic():
            for fixture, data, hg, ag in results:
                # 1. SimulatedMatch erstellen (alten ggf. ersetzen)
                if fixture.simulated_match_id:
                    old_sm = fixture.simulated_match
                    fixture.simulated_match = None
                    fixture.save(update_fields=['simulated_match'])
                    old_sm.delete()

                sm = SimulatedMatch.objects.create(
                    home_club=fixture.home_club,
                    away_club=fixture.away_club,
                    home_goals=hg,
                    away_goals=ag,
                    report_data=data,
                )

                # 2. SeasonFixture aktualisieren
                fixture.home_goals    = hg
                fixture.away_goals    = ag
                fixture.is_played     = True
                fixture.simulated_match = sm
                fixture.save(update_fields=[
                    'home_goals', 'away_goals', 'is_played', 'simulated_match'
                ])

                # 3. LeagueStandings für Heim + Gast aktualisieren
                _update_standings(league, season, fixture.home_club, hg, ag, win=(hg > ag), draw=(hg == ag))
                _update_standings(league, season, fixture.away_club, ag, hg, win=(ag > hg), draw=(hg == ag))

                # 4. Spieler-Stats + Form-Snapshots schreiben
                try:
                    from game.season_service import _update_player_season_stats
                    _update_player_season_stats(fixture, data)
                except Exception:
                    pass

            # 5. Positionen neu berechnen
            _recalculate_positions(league, season)

        # ── LeagueSeasonState synchronisieren ────────────────────────────────
        if not force:
            from game.season_service import get_season_state
            state = get_season_state(league, season)
            all_played = not SeasonFixture.objects.filter(
                league=league, season=season, matchday=matchday, is_played=False
            ).exists()
            if all_played and not state.is_simulated:
                state.is_simulated = True
                state.save(update_fields=['is_simulated', 'updated_at'])

        out(self.style.SUCCESS(
            f'\n✓ {len(results)}/{len(to_play)} Spiele gespeichert | '
            f'Tabelle aktualisiert | {len(errors)} Fehler'
        ))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _update_standings(league, season, club, gf, ga, win, draw):
    """Aktualisiert oder erstellt einen LeagueStandings-Eintrag für einen Verein."""
    from game.models import LeagueStandings

    s, _ = LeagueStandings.objects.get_or_create(
        league=league,
        club=club,
        season=season,
    )
    s.played += 1
    s.goals_for     += gf
    s.goals_against += ga

    if win:
        s.won    += 1
        s.points += 3
        form_char = LeagueStandings.FORM_WIN
    elif draw:
        s.drawn  += 1
        s.points += 1
        form_char = LeagueStandings.FORM_DRAW
    else:
        s.lost   += 1
        form_char = LeagueStandings.FORM_LOSS

    # Form: neuestes Ergebnis vorne, max. 5 Zeichen
    s.form = (form_char + s.form)[:5]

    s.save(update_fields=[
        'played', 'won', 'drawn', 'lost',
        'goals_for', 'goals_against', 'points', 'form',
    ])


def _recalculate_positions(league, season):
    """Sortiert und aktualisiert die Platzierungen aller Standings-Zeilen."""
    from game.models import LeagueStandings

    rows = list(
        LeagueStandings.objects
        .filter(league=league, season=season)
        .order_by(
            '-points',
            'club__name',  # Ersatz-Sortierkritierium bis echte TD vorhanden
        )
    )
    # Echter Sort: Pkt DESC → TD DESC → Tore DESC → Name ASC
    rows.sort(key=lambda s: (
        -s.points,
        -(s.goals_for - s.goals_against),
        -s.goals_for,
        s.club.name,
    ))

    updates = []
    for new_pos, row in enumerate(rows, 1):
        old_pos = row.position
        row.position_change = (old_pos - new_pos) if old_pos > 0 else 0
        row.position        = new_pos
        updates.append(row)

    LeagueStandings.objects.bulk_update(updates, ['position', 'position_change'])
