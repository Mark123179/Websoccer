"""
Management command: populate_player_data

Fetches player biographical data from transfermarkt.de for all players
that have a transfermarkt_id set, and recalculates salary_per_match
from market_value for every player.

Usage:
    python manage.py populate_player_data               # all players
    python manage.py populate_player_data --club Bayern # one club
    python manage.py populate_player_data --dry-run     # preview only
    python manage.py populate_player_data --delay 2.5   # custom delay (seconds)
"""
import re
import time
from datetime import date, datetime
from decimal import Decimal

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.models import Club, Player


# ── Position mapping: Transfermarkt label → WS position code ─────────────────
TM_TO_WS: dict[str, str] = {
    "Torwart": "TW",
    "Innenverteidiger": "IV",
    "Libero": "IV",
    "Linker Verteidiger": "LV",
    "Linker Flügelverteidiger": "LV",
    "Rechter Verteidiger": "RV",
    "Rechter Flügelverteidiger": "RV",
    "Defensives Mittelfeld": "DM",
    "Zentrales Mittelfeld": "ZM",
    "Linkes Mittelfeld": "LM",
    "Rechtes Mittelfeld": "RM",
    "Offensives Mittelfeld": "OM",
    "Linkes offensives Mittelfeld": "LOM",
    "Rechtes offensives Mittelfeld": "ROM",
    "Linker Flügel": "LF",
    "Rechter Flügel": "RF",
    "Mittelstürmer": "ST",
    "Hängende Spitze": "ST",
    "Zweite Spitze": "ST",
    "Linker Angriff": "LF",
    "Rechter Angriff": "RF",
    "Sturm": "ST",
}

# Valid WS position codes from the model
VALID_WS_POSITIONS = {
    "TW", "IV", "LV", "RV", "LOV", "ROV", "DM", "ZM",
    "LM", "RM", "LOM", "ROM", "OM", "LF", "RF", "ST",
}

# Salary = market_value × this factor per match
# Calibrated so a 30 M€ player earns ~180 k€/match (≈ realistic Bundesliga)
SALARY_FACTOR = Decimal("0.006")
MIN_SALARY = Decimal("500")
MAX_SALARY = Decimal("2000000")


def salary_from_market_value(mv: Decimal | None) -> Decimal:
    if not mv or mv <= 0:
        return MIN_SALARY
    sal = mv * SALARY_FACTOR
    return max(MIN_SALARY, min(MAX_SALARY, sal))


def tm_position_to_ws(tm_label: str) -> str | None:
    """Map a TM position label to a WS code. Partial match fallback."""
    label = tm_label.strip()
    if label in TM_TO_WS:
        return TM_TO_WS[label]
    for key, code in TM_TO_WS.items():
        if key.lower() in label.lower():
            return code
    return None


def parse_dob(text: str) -> date | None:
    """Parse '03.05.2003 (23)' → date(2003, 5, 3)."""
    text = text.strip()
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def parse_height(text: str) -> int | None:
    """Parse '1,77 m' or '177 cm' → 177."""
    text = text.replace("\xa0", " ").strip()
    m = re.match(r"(\d),(\d{2})", text)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))
    m = re.match(r"(\d{3})", text)
    if m:
        return int(m.group(1))
    return None


def parse_age(text: str) -> int | None:
    m = re.search(r"\((\d{1,3})\)", text)
    return int(m.group(1)) if m else None


def scrape_tm_profile(tm_id: int, session: requests.Session) -> dict:
    """
    Fetch and parse a transfermarkt.de player profile.
    Returns a dict with keys: dob, age, height_cm, strong_foot,
    primary_position (TM text), ws_position, secondary_positions (list of WS codes),
    all_positions_text.
    Empty dict on failure.
    """
    url = f"https://www.transfermarkt.de/spieler/profil/spieler/{tm_id}"
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}
    except requests.RequestException:
        return {}

    soup = BeautifulSoup(resp.text, "lxml")
    result = {}

    # ── DOB + Age ─────────────────────────────────────────────────────────────
    dob_span = soup.find("span", itemprop="birthDate")
    if dob_span:
        raw = dob_span.get_text(strip=True)
        result["dob"] = parse_dob(raw)
        if result["dob"] is None:
            result["dob"] = None
        parsed_age = parse_age(raw)
        if parsed_age:
            result["age"] = parsed_age

    # ── Info-table (Größe, Fuß, Position …) ───────────────────────────────────
    # TM structure: alternating label/value spans inside .info-table
    info_table = soup.find("div", class_="info-table")
    if not info_table:
        # Fallback: search entire page for label spans
        info_table = soup

    # Collect ALL text-bearing spans; labels end with ':'
    all_spans = info_table.find_all("span") if info_table else []
    span_texts = [(s, s.get_text(strip=True)) for s in all_spans]

    label_map: dict[str, str] = {}
    for i, (span, text) in enumerate(span_texts):
        if text.endswith(":"):
            label = text[:-1]
            # value = next sibling span, or next item in span list
            next_sibling = span.find_next_sibling()
            if next_sibling and next_sibling.get_text(strip=True):
                label_map[label] = next_sibling.get_text(strip=True)
            elif i + 1 < len(span_texts):
                label_map[label] = span_texts[i + 1][1]

    if "Größe" in label_map:
        result["height_cm"] = parse_height(label_map["Größe"])

    if "Fuß" in label_map:
        foot_raw = label_map["Fuß"].lower()
        if "rechts" in foot_raw:
            result["strong_foot"] = "R"
        elif "links" in foot_raw:
            result["strong_foot"] = "L"
        elif "beid" in foot_raw:
            result["strong_foot"] = "B"

    # ── Positions ─────────────────────────────────────────────────────────────
    # Try dedicated position-detail section first
    pos_section = soup.find("div", class_=re.compile(r"detail-position"))
    positions_found: list[str] = []

    if pos_section:
        for item in pos_section.find_all(["dt", "dd", "span", "li"]):
            txt = item.get_text(strip=True)
            if txt and len(txt) > 3 and txt not in ("Position", "Torwart", "Verteidigung",
                                                      "Mittelfeld", "Angriff"):
                ws = tm_position_to_ws(txt)
                if ws and ws not in positions_found:
                    positions_found.append(ws)

    # Fallback: read from info-table "Position:" label
    pos_text = label_map.get("Position", "")
    if pos_text and not positions_found:
        # Format may be "Mittelfeld - Offensives Mittelfeld"
        parts = [p.strip() for p in pos_text.replace(" - ", "|").split("|")]
        for part in parts:
            ws = tm_position_to_ws(part)
            if ws and ws not in positions_found:
                positions_found.append(ws)

    if pos_text:
        # Extract the specific position (after last ' - ')
        specific = pos_text.split(" - ")[-1].strip()
        result["primary_position_text"] = specific

    if positions_found:
        result["ws_position"] = positions_found[0]
        result["secondary_ws_positions"] = positions_found[1:4]  # up to 3 extras

    # Also store raw positions text for source_positions field
    result["all_positions_text"] = pos_text or ""

    return result


class Command(BaseCommand):
    help = (
        "Populate player biographical data from transfermarkt.de "
        "and recalculate salary_per_match from market_value."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--club",
            type=str,
            default=None,
            help="Only process players of clubs whose name contains this string.",
        )
        parser.add_argument(
            "--player-id",
            type=int,
            default=None,
            help="Process a single player by Django PK.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be updated without saving.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=2.0,
            help="Seconds to wait between TM requests (default: 2.0).",
        )
        parser.add_argument(
            "--skip-scrape",
            action="store_true",
            default=False,
            help="Skip TM scraping; only recalculate salaries.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            default=False,
            help="Overwrite existing data (height, foot, DOB). By default, only fills missing fields.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_scrape = options["skip_scrape"]
        delay = options["delay"]
        overwrite = options["overwrite"]
        club_filter = options["club"]
        player_id = options["player_id"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be saved.\n"))

        # ── Build queryset ─────────────────────────────────────────────────────
        qs = Player.objects.select_related("club").order_by("club__name", "last_name")

        if player_id:
            qs = qs.filter(pk=player_id)
        elif club_filter:
            qs = qs.filter(club__name__icontains=club_filter)

        players = list(qs)
        total = len(players)
        self.stdout.write(f"Processing {total} players …\n")

        # ── HTTP session with browser-like headers ─────────────────────────────
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/webp,*/*;q=0.8"
                ),
                "Referer": "https://www.transfermarkt.de/",
            }
        )

        # ── Counters ───────────────────────────────────────────────────────────
        scraped_ok = 0
        scraped_fail = 0
        salary_updated = 0
        skipped_no_tm = 0

        for i, player in enumerate(players, 1):
            name = f"{player.first_name} {player.last_name}".strip()
            club_name = player.club.name if player.club else "—"
            prefix = f"[{i}/{total}] {club_name} · {name}"

            update_fields: list[str] = []
            data: dict = {}

            # ── 1. Scrape TM.de if tm_id available ────────────────────────────
            if not skip_scrape and player.transfermarkt_id:
                self.stdout.write(f"{prefix} (tm:{player.transfermarkt_id}) … ", ending="")
                data = scrape_tm_profile(player.transfermarkt_id, session)

                if not data:
                    self.stdout.write(self.style.ERROR("FAIL (scrape error)"))
                    scraped_fail += 1
                else:
                    scraped_ok += 1
                    notes: list[str] = []

                    # DOB
                    if data.get("dob") and (overwrite or not player.date_of_birth):
                        player.date_of_birth = data["dob"]
                        update_fields.append("date_of_birth")
                        notes.append(f"DOB:{data['dob']}")

                    # Age
                    if data.get("age") and (overwrite or not player.age):
                        player.age = data["age"]
                        update_fields.append("age")
                        notes.append(f"age:{data['age']}")

                    # Height
                    if data.get("height_cm") and (overwrite or not player.height_cm):
                        player.height_cm = data["height_cm"]
                        update_fields.append("height_cm")
                        notes.append(f"h:{data['height_cm']}cm")

                    # Foot
                    if data.get("strong_foot") and (overwrite or not player.strong_foot):
                        player.strong_foot = data["strong_foot"]
                        update_fields.append("strong_foot")
                        notes.append(f"foot:{data['strong_foot']}")

                    # Primary position (RL text)
                    if data.get("primary_position_text") and (
                        overwrite or not player.primary_position
                    ):
                        player.primary_position = data["primary_position_text"]
                        update_fields.append("primary_position")
                        notes.append(f"pos:{data['primary_position_text']}")

                    # WS position code
                    ws_pos = data.get("ws_position")
                    if ws_pos and ws_pos in VALID_WS_POSITIONS and (
                        overwrite or not player.position
                    ):
                        player.position = ws_pos
                        update_fields.append("position")

                    # main_position_1 (WS code of primary position)
                    if ws_pos and ws_pos in VALID_WS_POSITIONS and (
                        overwrite or not player.main_position_1
                    ):
                        player.main_position_1 = ws_pos
                        update_fields.append("main_position_1")

                    # secondary_positions from TM "also plays as"
                    sec = data.get("secondary_ws_positions", [])
                    sec = [p for p in sec if p in VALID_WS_POSITIONS]

                    def _set_sec(attr, idx):
                        if idx < len(sec):
                            cur = getattr(player, attr, "")
                            if overwrite or not cur:
                                setattr(player, attr, sec[idx])
                                update_fields.append(attr)

                    _set_sec("secondary_position_1", 0)
                    _set_sec("secondary_position_2", 1)
                    _set_sec("secondary_position_3", 2)

                    # source_positions (raw text for reference)
                    if data.get("all_positions_text") and (
                        overwrite or not player.source_positions
                    ):
                        player.source_positions = data["all_positions_text"]
                        update_fields.append("source_positions")

                    self.stdout.write(
                        self.style.SUCCESS("OK")
                        + (f" [{', '.join(notes)}]" if notes else " [no new data]")
                    )

                # Rate-limit between requests
                if i < total:
                    time.sleep(delay)

            elif not player.transfermarkt_id:
                skipped_no_tm += 1
                self.stdout.write(f"{prefix} — no TM ID, skip scrape")

            # ── 2. Salary recalculation (always) ──────────────────────────────
            new_salary = salary_from_market_value(player.market_value)
            if player.salary_per_match != new_salary:
                player.salary_per_match = new_salary
                update_fields.append("salary_per_match")
                salary_updated += 1

            # ── 3. Save ───────────────────────────────────────────────────────
            if update_fields and not dry_run:
                # Remove duplicates while keeping order
                seen: set[str] = set()
                unique_fields = []
                for f in update_fields:
                    if f not in seen:
                        seen.add(f)
                        unique_fields.append(f)
                player.save(update_fields=unique_fields)

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(self.style.SUCCESS(f"Done."))
        self.stdout.write(f"  Players processed : {total}")
        if not skip_scrape:
            self.stdout.write(f"  TM scrape OK      : {scraped_ok}")
            self.stdout.write(f"  TM scrape FAIL    : {scraped_fail}")
            self.stdout.write(f"  No TM ID (skipped): {skipped_no_tm}")
        self.stdout.write(f"  Salary updated    : {salary_updated}")
        if dry_run:
            self.stdout.write(self.style.WARNING("  (DRY RUN — nothing saved)"))
