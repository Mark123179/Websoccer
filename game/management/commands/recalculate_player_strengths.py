"""
Neuberechnung aller Spielerstärken auf Basis der strength_engine.py (v2).

Änderungen gegenüber der Vorgänger-Version:
- Basis/Potential via se.calculate_base_200 / se.calculate_potential_200
- form_modifier via RL-Form aus PlayerFormSnapshot (se.calculate_rl_form_from_snapshots)
- Kein stilles Fallback mehr auf player.calculated_base_strength (Model-Property)
- Neues --player-id Flag für Einzelspieler-Neuberechnung

Was NICHT geändert wurde:
- PlayerStrengthProfile.freshness wird nur gesetzt wenn neu angelegt (kein Überschreiben)
- PlayerStrengthSnapshot wird weiterhin als Tageseintrag geschrieben
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from game import strength_engine as se
from game.models import (
    Player,
    PlayerFormSnapshot,
    PlayerSourceRating,
    PlayerStrengthProfile,
    PlayerStrengthSnapshot,
    StrengthFormulaSettings,
    STRENGTH_DEFAULT_BASE,
    strength_decimal,
)


class Command(BaseCommand):
    help = (
        'Spielerstärken mit strength_engine.py neu berechnen und in '
        'PlayerStrengthProfile + PlayerStrengthSnapshot schreiben.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Berechnung ausgeben ohne DB-Schreibzugriff.',
        )
        parser.add_argument(
            '--player-id',
            type=int,
            dest='player_id',
            help='Nur diesen einen Spieler (Datenbank-ID) neu berechnen.',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Pro Spieler eine Zeile ausgeben.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        single_id = options.get('player_id')

        settings = StrengthFormulaSettings.active()
        default_freshness = (
            settings.default_freshness if settings else Decimal('100.00')
        )
        today = timezone.localdate()

        qs = (
            Player.objects.prefetch_related(
                'source_ratings',
                'form_snapshots',
            ).select_related('strength_profile')
        )
        if single_id:
            qs = qs.filter(pk=single_id)
        qs = qs.order_by('last_name', 'first_name')

        total = 0
        source_based = 0
        default_based = 0
        skipped = 0

        for player in qs:
            total += 1
            rows = {r.source: r for r in player.source_ratings.all()}
            fm_row = rows.get(PlayerSourceRating.SOURCE_FM)
            ea_row = rows.get(PlayerSourceRating.SOURCE_EA)

            fmi_rating    = fm_row.rating    if fm_row else None
            fmi_potential = fm_row.potential if fm_row else None
            ea_rating     = ea_row.rating    if ea_row else None
            ea_potential  = ea_row.potential if ea_row else None

            # ── Basis & Potential ────────────────────────────────────────────
            base_200 = se.calculate_base_200(fmi_rating, ea_rating)
            if base_200 is None:
                base_200 = STRENGTH_DEFAULT_BASE
                default_based += 1
            else:
                base_200 = Decimal(str(base_200))
                source_based += 1

            potential_200 = se.calculate_potential_200(fmi_potential, ea_potential, int(base_200))
            if potential_200 is None:
                potential_200 = base_200
            else:
                potential_200 = Decimal(str(potential_200))

            # ── RL-Form-Modifier ─────────────────────────────────────────────
            api_snapshots = [
                s for s in player.form_snapshots.all()
                if s.source == PlayerFormSnapshot.SOURCE_API_FOOTBALL
            ]
            has_api_mapping = len(api_snapshots) > 0
            api_snapshots.sort(key=lambda s: s.fixture_date, reverse=True)
            snapshots_data = [
                {'rating': s.rating, 'minutes_played': s.minutes_played}
                for s in api_snapshots[:10]
            ]
            rl_form_result = se.calculate_rl_form_from_snapshots(
                snapshots_data, no_mapping=not has_api_mapping
            )
            rl_form_factor = se.get_rl_form_fit(rl_form_result['score'])
            form_modifier  = se.calculate_form_modifier(int(base_200), rl_form_factor)

            final_strength = strength_decimal(base_200 + form_modifier)
            max_strength   = max(
                strength_decimal(potential_200),
                final_strength,
            )

            if options['verbose'] or dry_run:
                rl_info = (
                    f'RL-Form {rl_form_result["score"]:+d}'
                    if not rl_form_result['no_data']
                    else 'RL-Form –'
                )
                self.stdout.write(
                    f'  {player.last_name}, {player.first_name:20s}  '
                    f'base={base_200:6.1f}  pot={potential_200:6.1f}  '
                    f'mod={form_modifier:+6.2f}  final={final_strength:6.1f}  '
                    f'{rl_info}'
                )

            if dry_run:
                continue

            # ── Profil schreiben ─────────────────────────────────────────────
            profile = getattr(player, 'strength_profile', None)
            if profile is None:
                profile = PlayerStrengthProfile(
                    player=player,
                    freshness=default_freshness,
                )

            profile.base_strength  = base_200
            profile.form_modifier  = form_modifier
            profile.final_strength = final_strength
            profile.save()

            # ── Snapshot schreiben ───────────────────────────────────────────
            PlayerStrengthSnapshot.objects.update_or_create(
                player=player,
                recorded_at=today,
                match_reference=f'RECALC-{today.isoformat()}',
                defaults={
                    'base_strength':           base_200,
                    'final_strength':          final_strength,
                    'max_strength':            max_strength,
                    'last_10_average_strength': final_strength,
                    'freshness':               profile.freshness,
                    'form_modifier':           form_modifier,
                    'notes': (
                        f'Engine v2. RL-Form {rl_form_result["score"]:+d}'
                        f' ({rl_form_result["match_count"]} Spiele).'
                    ),
                },
            )

        mode = 'DRY RUN' if dry_run else 'OK'
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}: {total} Spieler | '
                f'{source_based} mit Source-Ratings | '
                f'{default_based} mit Default-Base {STRENGTH_DEFAULT_BASE}'
            )
        )
