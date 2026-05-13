from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from game.models import (
    Player,
    PlayerStrengthProfile,
    PlayerStrengthSnapshot,
    StrengthFormulaSettings,
    STRENGTH_DEFAULT_BASE,
    strength_decimal,
)


class Command(BaseCommand):
    help = 'Recalculate current strength profiles and write strength snapshots.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Calculate and print a summary without writing changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        settings = StrengthFormulaSettings.active()
        default_freshness = (
            settings.default_freshness
            if settings
            else Decimal('100.00')
        )
        today = timezone.localdate()
        recalculated_count = 0
        source_based_count = 0
        existing_base_count = 0
        default_base_count = 0

        players = Player.objects.prefetch_related('source_ratings').select_related(
            'strength_profile',
        ).order_by('last_name', 'first_name')

        for player in players:
            profile = getattr(player, 'strength_profile', None)
            if profile is None:
                profile = PlayerStrengthProfile(
                    player=player,
                    freshness=default_freshness,
                )

            if not player.uses_default_base_strength:
                base_strength = player.calculated_base_strength
                source_based_count += 1
            elif profile.pk and profile.base_strength != STRENGTH_DEFAULT_BASE:
                base_strength = strength_decimal(profile.base_strength)
                existing_base_count += 1
            else:
                base_strength = STRENGTH_DEFAULT_BASE
                default_base_count += 1

            potential_strength = player.calculated_potential_strength
            if potential_strength is None:
                potential_strength = strength_decimal(player.potential)

            form_modifier = strength_decimal(profile.form_modifier or Decimal('0.00'))
            freshness = profile.freshness or default_freshness
            final_strength = strength_decimal(base_strength + form_modifier)
            max_strength = max(
                strength_decimal(potential_strength),
                final_strength,
            )

            if dry_run:
                recalculated_count += 1
                continue

            profile.base_strength = base_strength
            profile.form_modifier = form_modifier
            profile.freshness = freshness
            profile.final_strength = final_strength
            profile.save()

            PlayerStrengthSnapshot.objects.update_or_create(
                player=player,
                recorded_at=today,
                match_reference=f'RECALC-{today.isoformat()}',
                defaults={
                    'base_strength': base_strength,
                    'final_strength': final_strength,
                    'max_strength': max_strength,
                    'last_10_average_strength': final_strength,
                    'freshness': freshness,
                    'form_modifier': form_modifier,
                    'notes': 'Automatisch aus aktuellem Staerkeprofil neu berechnet.',
                },
            )
            recalculated_count += 1

        mode = 'DRY RUN' if dry_run else 'OK'
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}: {recalculated_count} Spieler berechnet. '
                f'{source_based_count} mit Source-Ratings, '
                f'{existing_base_count} mit vorhandener Base, '
                f'{default_base_count} mit Default-Base.'
            )
        )
