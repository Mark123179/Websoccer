"""
Management-Command: 2. Bundesliga mit 18 Dummy-Vereinen anlegen,
Pokal-Reset und Neu-Auslosung mit 32 Teilnehmern (18 BL1 + 14 BL2).

Aufruf:
    python manage.py setup_bl2_and_redraw_cup
"""
from django.core.management.base import BaseCommand
from django.db import transaction


BL2_CLUB_NAMES = [
    ("Hamburger SV",        "HSV"),
    ("Fortuna Düsseldorf",  "F95"),
    ("1. FC Nürnberg",      "FCN"),
    ("Hannover 96",         "H96"),
    ("Schalke 04",          "S04"),
    ("1. FC Kaiserslautern","FCK"),
    ("Karlsruher SC",       "KSC"),
    ("SpVgg Greuther Fürth","SGF"),
    ("Eintracht Braunschweig","EBS"),
    ("SV Elversberg",       "SVE"),
    ("Hertha BSC",          "BSC"),
    ("Darmstadt 98",        "D98"),
    ("SSV Ulm 1846",        "ULM"),
    ("FC Köln",             "KOE"),
    ("Preußen Münster",     "SCP"),
    ("Jahn Regensburg",     "SSV"),
    ("Magdeburg",           "FCM"),
    ("Paderborn 07",        "SCP"),
]

BL2_START_FMI = 90_000_001  # weit weg von echten FMI-IDs


class Command(BaseCommand):
    help = "2. Bundesliga + 18 Dummy-Vereine anlegen, Pokal mit 32 Teilnehmern neu auslosen."

    def handle(self, *args, **options):
        from game.models import League, Club, CupSeason, CupRound, CupFixture
        from game.cup_service import build_cup_participants, draw_cup_round

        with transaction.atomic():
            # ── 1. 2. Bundesliga anlegen / wiederverwenden ─────────────────
            bl2, created = League.objects.get_or_create(
                name="2. Bundesliga",
                defaults={
                    "country": "Deutschland",
                    "competition_type": "league",
                    "max_teams": 18,
                    "strength_coefficient": "0.85",
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS("✓ 2. Bundesliga angelegt"))
            else:
                self.stdout.write("  2. Bundesliga existiert bereits")

            # ── 2. Dummy-Vereine anlegen (idempotent per fm_inside_id) ──────
            created_clubs = 0
            for i, (name, short) in enumerate(BL2_CLUB_NAMES):
                fmi = BL2_START_FMI + i
                club, was_created = Club.objects.get_or_create(
                    fm_inside_id=fmi,
                    defaults={
                        "name": name,
                        "short_name": short,
                        "league": bl2,
                        "budget": 10_000_000,
                        "fan_popularity": 20,
                        "founded_year": 1900,
                    },
                )
                if was_created:
                    created_clubs += 1
            self.stdout.write(self.style.SUCCESS(
                f"✓ {created_clubs} neue BL2-Vereine angelegt "
                f"({bl2.club_set.count()} gesamt)"
            ))

            # ── 3. CupSeason + Runden/Fixtures zurücksetzen ────────────────
            cs = CupSeason.objects.filter(
                competition__competition_type="cup"
            ).first()
            if not cs:
                self.stdout.write(self.style.ERROR("Keine CupSeason gefunden!"))
                return

            deleted_f, _ = CupFixture.objects.filter(
                cup_round__cup_season=cs
            ).delete()
            deleted_r, _ = CupRound.objects.filter(cup_season=cs).delete()
            cs.participants.clear()
            self.stdout.write(self.style.SUCCESS(
                f"✓ Reset: {deleted_r} Runden, {deleted_f} Fixtures gelöscht"
            ))

            # ── 4. Teilnehmer setzen: 18 BL1 + 14 BL2 = 32 ─────────────────
            bl1 = League.objects.get(name="1. Bundesliga")
            participants = build_cup_participants(
                cs, bl1, bl2,
                bl_count=18,
                zweite_bl_count=14,
                fallback_by_id=True,
            )
            self.stdout.write(self.style.SUCCESS(
                f"✓ {len(participants)} Teilnehmer gesetzt "
                f"(18 BL1 + 14 BL2)"
            ))

            # ── 5. Erste Runde anlegen (round_of_32) ──────────────────────
            cup_round = CupRound.objects.create(
                cup_season=cs,
                round_number=1,
                round_code="round_of_32",
                status=CupRound.STATUS_PENDING,
            )

            # ── 6. Auslosung ───────────────────────────────────────────────
            fixtures = draw_cup_round(cup_round, participants)

            byes   = sum(1 for f in fixtures if f.is_bye)
            played = sum(1 for f in fixtures if not f.is_bye)
            self.stdout.write(self.style.SUCCESS(
                f"✓ Auslosung: {len(fixtures)} Paarungen "
                f"({played} Spiele, {byes} Freilose)"
            ))

            # ── Kurze Vorschau ─────────────────────────────────────────────
            self.stdout.write("\n  Erste 6 Begegnungen:")
            for f in fixtures[:6]:
                h = f.home_club.name if f.home_club else "—"
                a = f.away_club.name if f.away_club else "Freilos"
                flag = "  🎟 " if f.is_bye else "  ⚽ "
                self.stdout.write(f"{flag}{h} vs {a}")

        self.stdout.write(self.style.SUCCESS("\n✅ Fertig — Pokal mit 32 Teilnehmern ausgelost."))
