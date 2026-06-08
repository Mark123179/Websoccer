"""
Management command: set_market_value_strength

Calculates base_strength from market_value + age for all players and writes
it to PlayerStrengthProfile. Runs BEFORE FM/SoFifa ratings are imported.
After FM ratings exist, base_strength will be overwritten from source ratings.

Formula:
  mv_score  = 30 + 65 × log(1 + mv_M€) / log(201)  [clamp 30–95]
  age_delta = youth malus (<21) and veteran malus (>28)
  base      = clamp(mv_score + age_delta, 30, 95)

Scale examples:
  0 M€ → 30 | 5 M€ → 52 | 20 M€ → 67 | 50 M€ → 78 | 100 M€ → 87 | 200 M€ → 95

Usage:
    python manage.py set_market_value_strength
    python manage.py set_market_value_strength --dry-run
    python manage.py set_market_value_strength --verbose
"""
import math
from decimal import Decimal

from django.core.management.base import BaseCommand

from game.models import Player, PlayerStrengthProfile, PlayerStrengthSnapshot
from django.utils import timezone


LOG_SCALE = math.log(1 + 200)   # log(201) — denominator for 200 M€ → 95


def mv_to_strength(mv_eur: float) -> float:
    """Market value (€) → raw strength score 30–95."""
    if mv_eur <= 0:
        return 30.0
    mv_m = mv_eur / 1_000_000
    score = 30.0 + 65.0 * math.log(1.0 + mv_m) / LOG_SCALE
    return max(30.0, min(95.0, score))


def age_modifier(age: int | None) -> int:
    """Age-based modifier in strength points."""
    if age is None:
        return 0
    if age < 18:
        return -6
    if age < 21:
        return -3
    if age <= 28:
        return 0
    if age <= 31:
        return -2
    if age <= 33:
        return -4
    return -6


class Command(BaseCommand):
    help = (
        "Set PlayerStrengthProfile.base_strength from market_value + age. "
        "Interim solution until FM/SoFifa ratings are imported."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print calculations without saving.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show every player's calculation.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        today = timezone.localdate()

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing saved.\n"))

        players = list(
            Player.objects.select_related("strength_profile", "club")
            .prefetch_related("source_ratings")
            .order_by("club__name", "last_name")
        )

        updated = skipped_ratings = no_mv = 0
        total = len(players)
        buckets = {r: 0 for r in range(30, 100, 5)}

        for player in players:
            name = f"{player.first_name} {player.last_name}".strip()

            # Skip if player already has source ratings (FM/SoFifa)
            if player.source_ratings.exists():
                skipped_ratings += 1
                if verbose:
                    self.stdout.write(f"SKIP (ratings) {name}")
                continue

            mv = float(player.market_value or 0)
            if mv <= 0:
                no_mv += 1
                mv = 0

            raw = mv_to_strength(mv)
            age = player.age
            delta = age_modifier(age)
            base = int(round(max(30.0, min(95.0, raw + delta))))

            # Bucket count
            for start in range(30, 100, 5):
                if start <= base < start + 5:
                    buckets[start] += 1
                    break

            if verbose:
                self.stdout.write(
                    f"{name}: mv={mv/1e6:.1f}M€ age={age} "
                    f"raw={raw:.1f} δ={delta:+d} → {base}"
                )

            if not dry_run:
                profile, _ = PlayerStrengthProfile.objects.get_or_create(
                    player=player,
                    defaults={"base_strength": base, "final_strength": base},
                )
                profile.base_strength = base
                profile.final_strength = base
                profile.save(update_fields=["base_strength", "final_strength"])

                PlayerStrengthSnapshot.objects.update_or_create(
                    player=player,
                    recorded_at=today,
                    match_reference=f"MV-STRENGTH-{today.isoformat()}",
                    defaults={
                        "base_strength": base,
                        "final_strength": base,
                        "max_strength": base,
                        "last_10_average_strength": base,
                        "notes": "Aus Marktwert + Alter berechnet (vor FM-Ratings).",
                    },
                )

            updated += 1

        # Summary
        self.stdout.write("\n" + "─" * 60)
        mode = "DRY RUN" if dry_run else "OK"
        self.stdout.write(self.style.SUCCESS(f"{mode}: {updated}/{total} Spieler aktualisiert"))
        self.stdout.write(f"  Übersprungen (hat Ratings): {skipped_ratings}")
        self.stdout.write(f"  Ohne Marktwert (→ 30):      {no_mv}")
        self.stdout.write("\n  Stärke-Verteilung:")
        for start, count in sorted(buckets.items()):
            if count > 0:
                bar = "█" * count
                self.stdout.write(f"  {start:2d}–{start+4}: {bar} ({count})")
