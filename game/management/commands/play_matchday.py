"""Management Command: play_matchday

Spielt alle Spiele eines Spieltags durch Match Engine V2.
Erstellt SimulatedMatch-Einträge, aktualisiert SeasonFixture und LeagueStandings.

Verwendung:
    python manage.py play_matchday --league <id> --matchday <n>
    python manage.py play_matchday --league <id> --matchday <n> --season <s>
    python manage.py play_matchday --league <id> --matchday <n> --force
    python manage.py play_matchday --league <id> --matchday <n> --dry-run
    python manage.py play_matchday --league <id> --matchday <n> --skip-regression-check
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
        parser.add_argument('--skip-regression-check', action='store_true', default=False,
                            help='Regressions-Diff-Pre-Check überspringen')

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
        skip_regression = options['skip_regression_check']

        out(f"\nLiga: {league.name} | Spieltag {matchday} | Saison {season}"
            + (' [FORCE]' if force else '')
            + (' [DRY-RUN]' if dry_run else ''))
        out('─' * 60)

        # ── Regressions-Diff Pre-Check ────────────────────────────────────────
        if not skip_regression:
            _run_regression_check(self)

        # ── Fixtures laden ────────────────────────────────────────────────────
        qs = (
            SeasonFixture.objects
            .filter(league=league, season=season, matchday=matchday)
            .select_related('home_club', 'away_club', 'home_club__managed_by', 'away_club__managed_by')
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
                data = simulate_match(
                    home, away,
                    home_strength_malus=0.70 if fixture.home_lineup_malus else 1.0,
                    away_strength_malus=0.70 if fixture.away_lineup_malus else 1.0,
                )
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
                old_match_no = None
                if fixture.simulated_match_id:
                    old_sm = fixture.simulated_match
                    if str(old_sm.season) == str(season):
                        old_match_no = old_sm.match_no
                    fixture.simulated_match = None
                    fixture.save(update_fields=['simulated_match'])
                    old_sm.delete()

                sm = SimulatedMatch.create_numbered(
                    season,
                    match_no=old_match_no,
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

        # ── Finanz-Spieltagslauf (Phase 1, idempotent je Verein+Spieltag) ────
        finance_summary = {}
        try:
            from game.economy.matchday_run import run_matchday_finance
            finance_summary = run_matchday_finance(league, season, matchday)
            for err in finance_summary.get('errors', []):
                out(self.style.WARNING(f'  Finanzlauf: {err}'))
        except Exception as exc:
            out(self.style.WARNING(f'  Finanzlauf fehlgeschlagen: {exc}'))

        # ── Vollständigkeitsprüfung — Lücken-Alarm ────────────────────────────
        gaps = finance_summary.get('gaps', [])
        if gaps:
            out(self.style.WARNING(
                f'\n⚠  FINANZ-VOLLSTÄNDIGKEIT: {len(gaps)} Lücke(n) nach Spieltag {matchday}!'
            ))
            for g in gaps:
                if 'error' in g:
                    out(self.style.WARNING(f'   Prüffehler: {g["error"]}'))
                else:
                    missing_str = ', '.join(g.get('missing', []))
                    header_hint = ' [kein Header]' if g.get('no_header') else ''
                    out(self.style.WARNING(
                        f'   {g["club"]} (ST {g["spieltag"]}): '
                        f'fehlende Marker: {missing_str or "–"}{header_hint}'
                    ))

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

def _run_regression_check(cmd):
    """Führt den Regressions-Diff als Pre-Check aus.

    Gibt nur eine Warnung aus — kein Hard-Stop.
    Wird übersprungen, wenn keine History-Dateien vorhanden sind (Exit 2).
    """
    import sys
    from io import StringIO
    from pathlib import Path

    out = cmd.stdout.write

    try:
        scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / 'scripts'
        sys.path.insert(0, str(scripts_dir))
        import diff_regression as _dr

        old_path, new_path = _dr._find_two_latest()

        captured = StringIO()
        real_stdout = sys.stdout
        sys.stdout = captured
        try:
            exit_code = _dr.compare(old_path, new_path)
        finally:
            sys.stdout = real_stdout

        report = captured.getvalue()

        if exit_code == 0:
            out('  [Regression-Check] ✓ Engine stabil — kein Diff-Alarm.\n')
        else:
            out(cmd.style.WARNING(
                '\n⚠  REGRESSIONS-WARNUNG: Match Engine weicht vom letzten Referenz-Lauf ab!\n'
                '   Simulation wird trotzdem fortgesetzt. Bitte prüfen:\n'
                '     python scripts/diff_regression.py\n'
            ))
            for line in report.splitlines():
                out(f'   {line}')
            out('')

    except SystemExit:
        out('  [Regression-Check] Keine History-Daten — Pre-Check übersprungen.\n')
    except Exception as exc:
        out(cmd.style.WARNING(
            f'  [Regression-Check] Fehler beim Pre-Check ({exc}) — wird übersprungen.\n'
        ))
    finally:
        try:
            sys.path.remove(str(scripts_dir))
        except (ValueError, UnboundLocalError):
            pass


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
