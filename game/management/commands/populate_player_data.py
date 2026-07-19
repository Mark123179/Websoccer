"""
Management command: populate_player_data

Fetches player biographical data from transfermarkt.de and updates:
  - height_cm, strong_foot, date_of_birth, age
  - real_life_club (current TM club → FK to Club if BL club found)
  - If TM club not in our DB → optionally moves player to Karrierende
  - salary_per_match (market_value × SALARY_FACTOR)
  - Secondary positions from "Sonstige Positionen:" label

Usage:
    python manage.py populate_player_data                       # all players, bio data
    python manage.py populate_player_data --club Bayern         # one club
    python manage.py populate_player_data --set-rl-club         # also set real_life_club + fix squads
    python manage.py populate_player_data --fix-squads          # reassign club from TM (implies --set-rl-club)
    python manage.py populate_player_data --overwrite           # overwrite existing values
    python manage.py populate_player_data --dry-run             # preview only
    python manage.py populate_player_data --delay 0.5           # custom request delay
"""
import re
import time
from datetime import date
from decimal import Decimal

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from game.models import Club, Player


# ── TM position label → WS position code ─────────────────────────────────────
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
    "Linksaußen": "LF",
    "Rechter Flügel": "RF",
    "Rechtsaußen": "RF",
    "Mittelstürmer": "ST",
    "Hängende Spitze": "ST",
    "Zweite Spitze": "ST",
    "Linker Angriff": "LF",
    "Rechter Angriff": "RF",
    "Sturm": "ST",
}

VALID_WS_POSITIONS = {
    "TW", "IV", "LV", "RV", "LOV", "ROV", "DM", "ZM",
    "LM", "RM", "LOM", "ROM", "OM", "LF", "RF", "ST",
}

# TM club name variants → normalize to our DB name
TM_CLUB_VARIANTS: dict[str, str] = {
    "VfL Bochum 1848": "VfL Bochum",
    "1. FC Heidenheim 1846": "1. FC Heidenheim",
    "FC Basel 1893": "FC Basel",
    "Borussia VfL 1900 Mönchengladbach": "Borussia Mönchengladbach",
    "Bayer 04 Leverkusen Fußball": "Bayer 04 Leverkusen",
    "TSG Hoffenheim": "TSG 1899 Hoffenheim",
    "Mainz 05": "1. FSV Mainz 05",
    "1. FSV Mainz": "1. FSV Mainz 05",
}

SALARY_FACTOR = Decimal("0.006")
MIN_SALARY = Decimal("500")
MAX_SALARY = Decimal("2000000")
KARRIERENDE_CLUB_ID = 1


# ── Helpers ───────────────────────────────────────────────────────────────────

def salary_from_market_value(mv: Decimal | None) -> Decimal:
    if not mv or mv <= 0:
        return MIN_SALARY
    return max(MIN_SALARY, min(MAX_SALARY, mv * SALARY_FACTOR))


def tm_position_to_ws(tm_label: str) -> str | None:
    label = tm_label.strip()
    if label in TM_TO_WS:
        return TM_TO_WS[label]
    for key, code in TM_TO_WS.items():
        if key.lower() in label.lower():
            return code
    return None


def parse_dob(text: str) -> date | None:
    text = text.strip()
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def parse_height(text: str) -> int | None:
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


def parse_foot(text: str) -> str | None:
    """Parse foot preference. Handles German (rechts/links/beidfüßig) and English (right/left/both)."""
    t = text.lower().strip()
    if t in ("rechts", "right"):
        return "R"
    if t in ("links", "left"):
        return "L"
    if t in ("beidfüßig", "both", "beid"):
        return "B"
    # Substring fallback
    if "rechts" in t or "right" in t:
        return "R"
    if "links" in t or "left" in t:
        return "L"
    if "beid" in t or "both" in t:
        return "B"
    return None


def normalize_tm_club_name(tm_name: str) -> str:
    """Normalize TM club name to match our DB. Returns original if no variant found."""
    cleaned = tm_name.strip()
    return TM_CLUB_VARIANTS.get(cleaned, cleaned)


def build_club_lookup() -> dict[str, Club]:
    """Build {normalized_name: Club} lookup from DB."""
    lookup: dict[str, Club] = {}
    for club in Club.objects.all():
        lookup[club.name.strip()] = club
        # Also add lowercase variant
        lookup[club.name.strip().lower()] = club
    return lookup


def match_club(tm_club_name: str, lookup: dict[str, Club]) -> Club | None:
    """Match a TM club name to a Club object. Returns None if not found."""
    if not tm_club_name:
        return None
    normalized = normalize_tm_club_name(tm_club_name)
    # Exact match
    if normalized in lookup:
        return lookup[normalized]
    # Case-insensitive
    if normalized.lower() in lookup:
        return lookup[normalized.lower()]
    # Partial match: our club name is contained in TM name or vice versa
    for name, club in lookup.items():
        if len(name) > 4 and (name in normalized or normalized in name):
            return club
    return None


# ── TM Scraper ────────────────────────────────────────────────────────────────

def scrape_tm_profile(tm_id: int, session: requests.Session) -> dict:
    """
    Fetch and parse a transfermarkt.de player profile.

    Returns dict with:
      dob, age, height_cm, strong_foot,
      current_club_name (TM text),
      primary_position_text, ws_position,
      secondary_ws_positions (list),
      all_positions_text
    Returns {} on failure.
    """
    url = f"https://www.transfermarkt.de/spieler/profil/spieler/{tm_id}"
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return {}
    except requests.RequestException:
        return {}

    soup = BeautifulSoup(resp.text, "lxml")
    result: dict = {}

    # ── DOB + Age ─────────────────────────────────────────────────────────────
    dob_span = soup.find("span", itemprop="birthDate")
    if dob_span:
        raw = dob_span.get_text(strip=True)
        result["dob"] = parse_dob(raw)
        parsed_age = parse_age(raw)
        if parsed_age:
            result["age"] = parsed_age

    # ── Info-table: parse all label → value pairs ─────────────────────────────
    info_table = soup.find("div", class_="info-table") or soup
    all_spans = info_table.find_all("span") if info_table else []
    span_texts = [(s, s.get_text(strip=True)) for s in all_spans]

    label_map: dict[str, str] = {}
    for i, (span, text) in enumerate(span_texts):
        if text.endswith(":"):
            label = text[:-1]
            nxt_sib = span.find_next_sibling()
            if nxt_sib and nxt_sib.get_text(strip=True):
                label_map[label] = nxt_sib.get_text(strip=True)
            elif i + 1 < len(span_texts):
                label_map[label] = span_texts[i + 1][1]

    # ── Height ────────────────────────────────────────────────────────────────
    if "Größe" in label_map:
        result["height_cm"] = parse_height(label_map["Größe"])

    # ── Foot ──────────────────────────────────────────────────────────────────
    if "Fuß" in label_map:
        result["strong_foot"] = parse_foot(label_map["Fuß"])

    # ── Current club ──────────────────────────────────────────────────────────
    for label in ("Aktueller Verein", "Verein", "Aktuelle Mannschaft", "Aktuelle Leihgabe bei"):
        if label in label_map:
            result["current_club_name"] = label_map[label]
            break

    # ── Positions via Hauptposition/Nebenposition div ─────────────────────────
    # TM has a dedicated position div:
    # "Hauptposition:|Offensives Mittelfeld|Nebenposition:|Zentrales Mittelfeld|Linksaußen"
    pos_div = None
    all_divs = soup.find_all("div")
    for div in all_divs:
        txt = div.get_text()
        if "Hauptposition" in txt and "Nebenposition" in txt:
            # Take the most specific (smallest) containing div
            if pos_div is None or len(div.get_text()) < len(pos_div.get_text()):
                pos_div = div

    hp_ws: str | None = None
    np_ws_list: list[str] = []

    if pos_div:
        parts = [p.strip() for p in pos_div.get_text(separator="|", strip=True).split("|") if p.strip()]
        state = None
        for part in parts:
            label = part.rstrip(":")
            if label == "Hauptposition":
                state = "hp"
            elif label == "Nebenposition":
                state = "np"
            elif state == "hp" and not hp_ws:
                ws = tm_position_to_ws(part)
                if ws and ws in VALID_WS_POSITIONS:
                    hp_ws = ws
                    result["primary_position_text"] = part
            elif state == "np":
                ws = tm_position_to_ws(part)
                if ws and ws in VALID_WS_POSITIONS and ws not in np_ws_list:
                    np_ws_list.append(ws)

    # Fallback: use info-table "Position:" label
    pos_text = label_map.get("Position", "")
    if pos_text:
        result["all_positions_text"] = pos_text
        if not hp_ws:
            specific = pos_text.split(" - ")[-1].strip()
            ws = tm_position_to_ws(specific)
            if ws and ws in VALID_WS_POSITIONS:
                hp_ws = ws
                result["primary_position_text"] = specific

    if hp_ws:
        result["ws_position"] = hp_ws
    result["secondary_ws_positions"] = np_ws_list[:3]

    return result


# ── Command ───────────────────────────────────────────────────────────────────

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
            help="Overwrite existing data (height, foot, DOB). Default: fill missing only.",
        )
        parser.add_argument(
            "--set-rl-club",
            action="store_true",
            default=False,
            help=(
                "Set real_life_club from TM current club. "
                "Players not at a BL club keep real_life_club=NULL."
            ),
        )
        parser.add_argument(
            "--fix-squads",
            action="store_true",
            default=False,
            help=(
                "Also update club assignment: move players to their TM current club "
                "if it is in our DB, or to Karrierende if not. Implies --set-rl-club."
            ),
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Skip first N players in the queryset (for batching large clubs).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most N players (0 = no limit).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_scrape = options["skip_scrape"]
        delay = options["delay"]
        overwrite = options["overwrite"]
        club_filter = options["club"]
        player_id = options["player_id"]
        set_rl_club = options["set_rl_club"] or options["fix_squads"]
        fix_squads = options["fix_squads"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be saved.\n"))

        # Build club lookup once
        club_lookup = build_club_lookup() if set_rl_club or fix_squads else {}
        try:
            karrierende = Club.objects.get(pk=KARRIERENDE_CLUB_ID)
        except Club.DoesNotExist:
            karrierende = None

        # ── Build queryset ─────────────────────────────────────────────────────
        qs = Player.objects.select_related("club", "real_life_club").order_by(
            "club__name", "last_name"
        )
        if player_id:
            qs = qs.filter(pk=player_id)
        elif club_filter:
            qs = qs.filter(club__name__icontains=club_filter)

        offset = options["offset"]
        limit = options["limit"]
        players = list(qs)
        if offset:
            players = players[offset:]
        if limit:
            players = players[:limit]
        total = len(players)
        self.stdout.write(f"Processing {total} players …\n")

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.transfermarkt.de/",
        })

        scraped_ok = scraped_fail = salary_updated = skipped_no_tm = 0
        rl_set = squad_moved = 0

        for i, player in enumerate(players, 1):
            name = f"{player.first_name} {player.last_name}".strip()
            club_name = player.club.name if player.club else "—"
            prefix = f"[{i}/{total}] {club_name} · {name}"

            update_fields: list[str] = []
            notes: list[str] = []
            data: dict = {}

            # ── 1. Scrape TM.de ────────────────────────────────────────────────
            if not skip_scrape and player.transfermarkt_id:
                self.stdout.write(f"{prefix} (tm:{player.transfermarkt_id}) … ", ending="")
                data = scrape_tm_profile(player.transfermarkt_id, session)

                if not data:
                    self.stdout.write(self.style.ERROR("FAIL"))
                    scraped_fail += 1
                else:
                    scraped_ok += 1

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

                    # Foot (always overwrite if we have a valid value — fixes "right"/"left" bug)
                    new_foot = data.get("strong_foot")
                    if new_foot and (overwrite or player.strong_foot not in ("R", "L", "B")):
                        player.strong_foot = new_foot
                        update_fields.append("strong_foot")
                        notes.append(f"foot:{new_foot}")

                    # Primary position text (TM human-readable, e.g. "Offensives Mittelfeld")
                    if data.get("primary_position_text") and (
                        overwrite or not player.primary_position
                    ):
                        player.primary_position = data["primary_position_text"]
                        update_fields.append("primary_position")

                    # WS position code (e.g. "OM") → position + main_position_1
                    ws_pos = data.get("ws_position")
                    if ws_pos and ws_pos in VALID_WS_POSITIONS and (
                        overwrite or not player.position
                    ):
                        player.position = ws_pos
                        update_fields.append("position")
                        notes.append(f"pos:{ws_pos}")

                    if ws_pos and ws_pos in VALID_WS_POSITIONS and (
                        overwrite or not player.main_position_1
                    ):
                        player.main_position_1 = ws_pos
                        update_fields.append("main_position_1")

                    # Secondary positions
                    sec = [p for p in data.get("secondary_ws_positions", []) if p in VALID_WS_POSITIONS]
                    for attr, idx in [
                        ("secondary_position_1", 0),
                        ("secondary_position_2", 1),
                        ("secondary_position_3", 2),
                    ]:
                        if idx < len(sec) and (overwrite or not getattr(player, attr, "")):
                            setattr(player, attr, sec[idx])
                            update_fields.append(attr)

                    # ── RL-Verein from TM current club ─────────────────────────
                    if (set_rl_club or fix_squads) and data.get("current_club_name"):
                        tm_club_name = data["current_club_name"]
                        matched_club = match_club(tm_club_name, club_lookup)

                        if overwrite or not player.real_life_club:
                            player.real_life_club = matched_club  # None if not BL
                            update_fields.append("real_life_club")
                            rl_set += 1
                            if matched_club:
                                notes.append(f"rl:{matched_club.name[:20]}")
                            else:
                                notes.append(f"rl:NULL({tm_club_name[:15]})")

                        # Fix squad assignment
                        if fix_squads and karrierende:
                            target_club = matched_club or karrierende
                            if player.club != target_club:
                                old_club = player.club.name if player.club else "—"
                                if target_club is karrierende and not dry_run:
                                    # Karriereende-Ereignispfad: Abfindung
                                    # buchen, solange der Spieler noch am
                                    # abgebenden Verein hängt.
                                    from game.economy.severance import (
                                        GRUND_KARRIEREENDE, book_abfindung,
                                    )
                                    book_abfindung(player, GRUND_KARRIEREENDE)
                                player.club = target_club
                                update_fields.append("club")
                                squad_moved += 1
                                notes.append(f"→{target_club.name[:15]}")

                    self.stdout.write(
                        self.style.SUCCESS("OK")
                        + (f" [{', '.join(notes)}]" if notes else " [no new data]")
                    )

                if i < total:
                    time.sleep(delay)

            elif not player.transfermarkt_id:
                skipped_no_tm += 1
                self.stdout.write(f"{prefix} — no TM ID, skip")

            # ── 2. Salary (always) ─────────────────────────────────────────────
            new_salary = salary_from_market_value(player.market_value)
            if player.salary_per_match != new_salary:
                player.salary_per_match = new_salary
                update_fields.append("salary_per_match")
                salary_updated += 1

            # ── 3. Save ────────────────────────────────────────────────────────
            if update_fields and not dry_run:
                seen: set[str] = set()
                unique = []
                for f in update_fields:
                    if f not in seen:
                        seen.add(f)
                        unique.append(f)
                player.save(update_fields=unique)

        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(self.style.SUCCESS("Done."))
        self.stdout.write(f"  Players processed : {total}")
        if not skip_scrape:
            self.stdout.write(f"  TM scrape OK      : {scraped_ok}")
            self.stdout.write(f"  TM scrape FAIL    : {scraped_fail}")
            self.stdout.write(f"  No TM ID (skipped): {skipped_no_tm}")
        self.stdout.write(f"  Salary updated    : {salary_updated}")
        if set_rl_club:
            self.stdout.write(f"  RL-Verein gesetzt : {rl_set}")
        if fix_squads:
            self.stdout.write(f"  Kader verschoben  : {squad_moved}")
        if dry_run:
            self.stdout.write(self.style.WARNING("  (DRY RUN — nothing saved)"))
