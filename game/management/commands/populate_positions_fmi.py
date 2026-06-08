"""
Scrapes FM Inside (fminside.net) for player positions (Hauptposition + Nebenposition)
and writes them to position / main_position_1 / secondary_position_{1,2,3}.

Only processes players that have a fm_inside_id set in the DB.
Uses the URL schema: https://fminside.net/players/7-fm-26/{fm_inside_id}-{name-slug}

FM position attribute → WS code mapping:
  gk  → TW   dc  → IV   dl  → LV   dr  → RV
  wbl → LV   wbr → RV   dm  → DM   mc  → ZM
  ml  → LM   mr  → RM   amc → OM   aml → LF
  amr → RF   st  → ST

Usage:
  python manage.py populate_positions_fmi
  python manage.py populate_positions_fmi --club Bayern
  python manage.py populate_positions_fmi --dry-run
  python manage.py populate_positions_fmi --delay 0.5
  python manage.py populate_positions_fmi --fm-version fm-25
"""

import re
import time
import unicodedata

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from game.models import Player

FM_TO_WS: dict[str, str] = {
    "gk": "TW",
    "dc": "IV",
    "dl": "LV",
    "dr": "RV",
    "wbl": "LV",
    "wbr": "RV",
    "dm": "DM",
    "mc": "ZM",
    "ml": "LM",
    "mr": "RM",
    "amc": "OM",
    "aml": "LF",
    "amr": "RF",
    "st": "ST",
}

VALID_WS_POSITIONS: set[str] = {
    "TW", "IV", "LV", "RV", "LOV", "ROV",
    "DM", "ZM", "LM", "RM", "LOM", "ROM", "OM",
    "LF", "RF", "ST",
}

PROFICIENCY_ORDER: dict[str, int] = {
    "Natural": 0,
    "Accomplished": 1,
    "Competent": 2,
    "Unconvincing": 3,
    "Ineffective": 4,
}

FMI_BASE = "https://fminside.net/players"
FM_VERSIONS = ["7-fm-26", "7-fm-25", "7-fm-27", "7-fm-28"]


def name_to_slug(first: str, last: str) -> str:
    name = f"{first} {last}".strip()
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def scrape_fmi_positions(
    fm_inside_id: int,
    slug: str,
    session: requests.Session,
) -> dict | None:
    for version in FM_VERSIONS:
        url = f"{FMI_BASE}/{version}/{fm_inside_id}-{slug}"
        try:
            r = session.get(url, timeout=10, allow_redirects=True)
        except Exception:
            continue

        if r.status_code != 200:
            continue
        if "Page not found" in r.text[:400] or "404" in r.text[:200]:
            continue

        soup = BeautifulSoup(r.text, "lxml")

        # Primary position: the mobile_position span (= most natural role)
        mob = soup.select_one("span.mobile_position span[position]")
        primary_ws: str | None = None
        if mob:
            primary_ws = FM_TO_WS.get(mob["position"].lower())

        # All positions from desktop_positions
        all_spans = soup.select("span.desktop_positions span[position]")
        seen: set[str] = set()
        all_positions: list[tuple[str, int]] = []  # (ws_code, proficiency)
        for sp in all_spans:
            ws = FM_TO_WS.get(sp["position"].lower())
            if not ws or not (ws in VALID_WS_POSITIONS):
                continue
            if ws in seen:
                continue
            seen.add(ws)
            prof = PROFICIENCY_ORDER.get(sp.get("title", "Unknown"), 5)
            all_positions.append((ws, prof))

        # Fallback primary: best proficiency from desktop if mobile not found
        if not primary_ws and all_positions:
            all_positions.sort(key=lambda x: x[1])
            primary_ws = all_positions[0][0]

        if not primary_ws:
            return None

        # Secondaries: positions other than primary with at least Accomplished (<=1)
        secondaries = [
            ws for ws, prof in all_positions
            if ws != primary_ws and prof <= 1
        ]

        return {
            "primary_ws": primary_ws,
            "secondary_ws": secondaries[:3],
            "fm_version_found": version,
        }

    return None


class Command(BaseCommand):
    help = "Scrape FM Inside positions for players with fm_inside_id."

    def add_arguments(self, parser):
        parser.add_argument(
            "--club",
            type=str,
            default="",
            help="Filter by club name (case-insensitive contains).",
        )
        parser.add_argument(
            "--player-id",
            type=int,
            default=0,
            help="Process a single player by DB pk.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print what would change without saving.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Seconds between requests (default 0.5).",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            default=False,
            help="Overwrite existing position values (default: fill missing only).",
        )
        parser.add_argument(
            "--fm-version",
            type=str,
            default="",
            help="Force specific FM version prefix, e.g. '7-fm-25' (default: try all).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        delay: float = options["delay"]
        overwrite: bool = options["overwrite"]
        club_filter: str = options["club"]
        player_id: int = options["player_id"]
        fm_version: str = options["fm_version"]

        if fm_version:
            FM_VERSIONS.clear()
            FM_VERSIONS.append(fm_version)

        qs = (
            Player.objects.select_related("club")
            .exclude(fm_inside_id__isnull=True)
            .exclude(fm_inside_id=0)
            .order_by("club__name", "last_name")
        )
        if player_id:
            qs = qs.filter(pk=player_id)
        elif club_filter:
            qs = qs.filter(club__name__icontains=club_filter)

        players = list(qs)
        total = len(players)
        self.stdout.write(f"Processing {total} players with fm_inside_id …\n")

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://fminside.net/players",
        })

        ok = fail = skipped = already_set = 0

        for i, player in enumerate(players, 1):
            name = f"{player.first_name} {player.last_name}".strip()
            club_name = player.club.name if player.club else "—"
            prefix = f"[{i}/{total}] {club_name} · {name} (fmi:{player.fm_inside_id})"

            # Skip if positions already set and not overwriting
            if not overwrite and player.position and player.main_position_1:
                self.stdout.write(f"{prefix} … SKIP (pos already set: {player.position})")
                already_set += 1
                continue

            self.stdout.write(f"{prefix} … ", ending="")

            slug = name_to_slug(player.first_name, player.last_name)
            data = scrape_fmi_positions(player.fm_inside_id, slug, session)

            if not data:
                self.stdout.write(self.style.ERROR("FAIL (404/parse error)"))
                fail += 1
            else:
                primary = data["primary_ws"]
                secondaries = data["secondary_ws"]
                version = data["fm_version_found"]

                update_fields: list[str] = []
                notes: list[str] = [f"pos:{primary}({version})"]

                if overwrite or not player.position:
                    player.position = primary
                    update_fields.append("position")

                if overwrite or not player.main_position_1:
                    player.main_position_1 = primary
                    update_fields.append("main_position_1")

                for attr, idx in [
                    ("secondary_position_1", 0),
                    ("secondary_position_2", 1),
                    ("secondary_position_3", 2),
                ]:
                    if idx < len(secondaries) and (
                        overwrite or not getattr(player, attr, "")
                    ):
                        setattr(player, attr, secondaries[idx])
                        update_fields.append(attr)

                if secondaries:
                    notes.append(f"sec:{'+'.join(secondaries)}")

                if update_fields and not dry_run:
                    seen_fields: set[str] = set()
                    unique_fields = []
                    for f in update_fields:
                        if f not in seen_fields:
                            seen_fields.add(f)
                            unique_fields.append(f)
                    player.save(update_fields=unique_fields)

                ok += 1
                self.stdout.write(
                    self.style.SUCCESS("OK")
                    + f" [{', '.join(notes)}]"
                )

            if i < total and delay > 0:
                time.sleep(delay)

        self.stdout.write(
            f"\nDone.\n"
            f"  Updated        : {ok}\n"
            f"  Already set    : {already_set}\n"
            f"  Failed (404)   : {fail}\n"
        )
