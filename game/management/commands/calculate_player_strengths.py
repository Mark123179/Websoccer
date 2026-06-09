"""
Management-Command: calculate_player_strengths

Berechnet die Spielstärken aller Spieler über die strength_engine.py-Pipeline
und schreibt die Ergebnisse in PlayerStrengthProfile (base_strength, final_strength).

Bestehende form_modifier und freshness bleiben erhalten.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from game.models import (
    Player,
    PlayerStrengthProfile,
    PlayerStrengthSnapshot,
    strength_decimal,
)
from game.strength_service import compute_strength_for_player


class Command(BaseCommand):
    help = (
        'Berechnet Spielstärken über strength_engine.py und schreibt sie '
        'in PlayerStrengthProfile. form_modifier und freshness bleiben unverändert.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Nur berechnen und ausgeben, ohne in die Datenbank zu schreiben.',
        )
        parser.add_argument(
            '--player-id',
            type=int,
            default=None,
            help='Nur einen einzelnen Spieler (per ID) neu berechnen.',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Pro Spieler eine Zeile ausgeben (auch ohne --dry-run).',
        )

    def handle(self, *args, **options):
        dry_run   = options['dry_run']
        player_id = options['player_id']
        verbose   = options['verbose']
        today     = timezone.localdate()

        qs = (
            Player.objects
            .prefetch_related('source_ratings', 'form_snapshots', 'strength_profile')
            .order_by('last_name', 'first_name')
        )
        if player_id:
            qs = qs.filter(pk=player_id)

        total          = 0
        computed       = 0
        skipped        = 0
        created_count  = 0

        for player in qs:
            total += 1
            result = compute_strength_for_player(player)

            if not result['computable']:
                skipped += 1
                if dry_run or verbose:
                    self.stdout.write(
                        f'  SKIP  {player.last_name}, {player.first_name} — '
                        f'keine Quelldaten'
                    )
                continue

            new_base = result['base_strength']
            new_max  = result['max_strength']

            profile = getattr(player, 'strength_profile', None)
            is_new  = profile is None

            if is_new:
                profile = PlayerStrengthProfile(
                    player=player,
                    base_strength=new_base,
                    form_modifier=Decimal('0.00'),
                    freshness=Decimal('100.00'),
                )
            else:
                profile.base_strength = new_base

            final = strength_decimal(profile.base_strength + profile.form_modifier)

            if dry_run:
                stored_base  = None if is_new else player.strength_profile.base_strength
                stored_final = None if is_new else player.strength_profile.final_strength
                diff_flag    = (
                    '' if stored_base is None
                    else f'  Δ={abs(new_base - stored_base):.2f}'
                )
                self.stdout.write(
                    f'  {"NEW " if is_new else "    "}'
                    f'{player.last_name}, {player.first_name}: '
                    f'base {stored_base} → {new_base}  '
                    f'final {stored_final} → {final}'
                    f'{diff_flag}'
                )
                computed += 1
                continue

            with transaction.atomic():
                profile.save()

                PlayerStrengthSnapshot.objects.update_or_create(
                    player=player,
                    recorded_at=today,
                    match_reference=f'ENGINE-{today.isoformat()}',
                    defaults={
                        'base_strength':           new_base,
                        'final_strength':          final,
                        'max_strength':            new_max if new_max is not None else final,
                        'last_10_average_strength': final,
                        'freshness':               profile.freshness,
                        'form_modifier':           profile.form_modifier,
                        'notes': 'Automatisch via calculate_player_strengths (strength_engine).',
                    },
                )

            if verbose:
                self.stdout.write(
                    f'  {"NEW " if is_new else "    "}'
                    f'{player.last_name}, {player.first_name}: '
                    f'base={new_base}  final={final}'
                )

            if is_new:
                created_count += 1
            computed += 1

        mode = 'DRY RUN' if dry_run else 'OK'
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}: {total} Spieler geprüft — '
                f'{computed} berechnet, {skipped} übersprungen'
                + (f', {created_count} neue Profile erstellt' if created_count and not dry_run else '')
            )
        )
