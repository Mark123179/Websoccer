"""
Management command: sync_squads_tm

Syncs game-club squads from the CURRENT Transfermarkt squad pages
(no saison_id → always the latest season).

For each of the 18 game clubs:
  1. Scrapes /kader/verein/{tm_club_id}  (no saison_id)
  2. Matches TM players against DB by transfermarkt_id
  3. Moves existing players to this club (even from Karrierende or other clubs)
  4. Creates new Player records for players not yet in the DB
  5. Moves ex-players (no longer in TM squad) to Karrierende

Then for every club, salary_per_match is recalculated from market_value.

Usage:
    python manage.py sync_squads_tm                         # all 18 clubs
    python manage.py sync_squads_tm --club Bayern           # single club (substring match)
    python manage.py sync_squads_tm --dry-run               # preview only
    python manage.py sync_squads_tm --delay 1.5             # custom delay between requests
    python manage.py sync_squads_tm --no-retire             # skip moving ex-players to Karrierende
"""
import re
import time
from decimal import Decimal

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from game.models import Club, Player


# ── Game Club pk → (TM club ID, TM slug) ─────────────────────────────────────
# Slugs are informational only; TM uses the numeric ID for routing.
CLUB_TM_MAP: dict[int, tuple[int, str]] = {
    2:  (27,    "fc-bayern-munchen"),
    3:  (16,    "borussia-dortmund"),
    8:  (15,    "bayer-04-leverkusen"),
    9:  (23826, "rb-leipzig"),
    10: (24,    "eintracht-frankfurt"),
    11: (79,    "vfb-stuttgart"),
    12: (60,    "sport-club-freiburg"),
    13: (18,    "borussia-monchengladbach"),
    14: (533,   "tsg-hoffenheim"),
    15: (82,    "vfl-wolfsburg"),
    16: (86,    "sv-werder-bremen"),
    17: (167,   "fc-augsburg"),
    18: (39,    "1-fsv-mainz-05"),
    19: (89,    "1-fc-union-berlin"),
    20: (80,    "vfl-bochum-1848"),
    21: (269,   "holstein-kiel"),
    22: (35,    "fc-st-pauli"),
    23: (3523,  "1-fc-heidenheim-1846"),
}

KARRIERENDE_CLUB_ID = 1
SALARY_FACTOR = Decimal("0.006")
MIN_SALARY = Decimal("500")
MAX_SALARY = Decimal("2000000")

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_tm_market_value(text: str) -> Decimal:
    """Parse TM market value string to Decimal (EUR). Returns 0 on failure."""
    text = text.strip().replace("\xa0", " ").replace(",", ".")
    if not text or text in ("-", "—"):
        return Decimal("0")
    m_mio = re.search(r"([\d.]+)\s*Mio", text)
    if m_mio:
        return Decimal(m_mio.group(1)) * Decimal("1000000")
    m_tsd = re.search(r"([\d.]+)\s*Tsd", text)
    if m_tsd:
        return Decimal(m_tsd.group(1)) * Decimal("1000")
    return Decimal("0")


def tm_position_to_ws(label: str) -> str:
    """Convert TM position label → WS code. Returns 'ZM' as fallback."""
    label = label.strip()
    if label in TM_TO_WS:
        return TM_TO_WS[label]
    for key, code in TM_TO_WS.items():
        if key.lower() in label.lower():
            return code
    return "ZM"


def salary_from_mv(mv: Decimal) -> Decimal:
    if not mv or mv <= 0:
        return MIN_SALARY
    return max(MIN_SALARY, min(MAX_SALARY, mv * SALARY_FACTOR))


def split_name(full_name: str) -> tuple[str, str]:
    """
    Split a full name into (first_name, last_name).
    Heuristic: last token = last_name, rest = first_name.
    Single-word names → first_name='', last_name=full_name.
    """
    parts = full_name.strip().split()
    if len(parts) == 0:
        return ("", "")
    if len(parts) == 1:
        return ("", parts[0])
    return (" ".join(parts[:-1]), parts[-1])


def scrape_tm_squad(tm_club_id: int, slug: str, session: requests.Session) -> list[dict]:
    """
    Scrape the current TM squad page (no saison_id).

    Returns list of dicts: {tm_id, full_name, first_name, last_name,
                             position_text, ws_position, market_value}
    Returns [] on failure.
    """
    url = f"https://www.transfermarkt.de/{slug}/kader/verein/{tm_club_id}"
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return []
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    rows = soup.select("table.items tbody tr")
    seen_ids: set[int] = set()
    players: list[dict] = []

    for row in rows:
        name_link = row.select_one('td.hauptlink a[href*="/profil/spieler/"]')
        if not name_link:
            continue
        href = name_link["href"]
        m = re.search(r"/spieler/(\d+)$", href)
        if not m:
            continue
        tm_id = int(m.group(1))
        if tm_id in seen_ids:
            continue
        seen_ids.add(tm_id)

        full_name = name_link.get_text(strip=True)
        first_name, last_name = split_name(full_name)

        # Position is in the second <tr> of the inline-table inside td.posrela
        pos_td = row.select_one("td.posrela table tr:last-child td")
        pos_text = pos_td.get_text(strip=True) if pos_td else ""
        ws_pos = tm_position_to_ws(pos_text) if pos_text else "ZM"

        mv_td = row.select_one("td.rechts.hauptlink")
        mv_text = mv_td.get_text(strip=True) if mv_td else ""
        market_value = parse_tm_market_value(mv_text)

        players.append({
            "tm_id": tm_id,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "position_text": pos_text,
            "ws_position": ws_pos,
            "market_value": market_value,
        })

    return players


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Sync all 18 game-club squads from the CURRENT TM squad pages "
        "(no saison_id). Creates missing players, moves transfers, retires ex-squad."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--club",
            type=str,
            default=None,
            help="Only sync clubs whose name contains this string (case-insensitive).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would change without saving.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.5,
            help="Seconds between TM requests (default: 1.5).",
        )
        parser.add_argument(
            "--no-retire",
            action="store_true",
            default=False,
            help="Do NOT move ex-squad players to Karrierende.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        delay = options["delay"]
        club_filter = options["club"]
        no_retire = options["no_retire"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be saved.\n"))

        try:
            karrierende = Club.objects.get(pk=KARRIERENDE_CLUB_ID)
        except Club.DoesNotExist:
            self.stderr.write("ERROR: Karrierende club (pk=1) not found.")
            return

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.transfermarkt.de/",
        })

        # Build complete map of all tm_ids currently in DB for fast lookup
        # {tm_id → Player}
        tm_id_to_player: dict[int, Player] = {
            p.transfermarkt_id: p
            for p in Player.objects.select_related("club")
            if p.transfermarkt_id
        }

        # Determine which clubs to process
        clubs_to_process = []
        for club_pk, (tm_club_id, slug) in CLUB_TM_MAP.items():
            try:
                club = Club.objects.get(pk=club_pk)
            except Club.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Club pk={club_pk} not in DB, skipping."))
                continue
            if club_filter and club_filter.lower() not in club.name.lower():
                continue
            clubs_to_process.append((club, tm_club_id, slug))

        self.stdout.write(f"Syncing {len(clubs_to_process)} clubs …\n")

        total_moved = total_created = total_retired = 0

        for club, tm_club_id, slug in clubs_to_process:
            self.stdout.write(f"\n{'─'*60}")
            self.stdout.write(f"  {club.name}  (TM club ID: {tm_club_id})")
            self.stdout.write(f"{'─'*60}")

            # 1. Scrape current TM squad
            self.stdout.write(f"  Scraping {slug}/kader/verein/{tm_club_id} … ", ending="")
            squad = scrape_tm_squad(tm_club_id, slug, session)
            if not squad:
                self.stdout.write(self.style.ERROR("FAIL — skipping"))
                time.sleep(delay)
                continue
            self.stdout.write(self.style.SUCCESS(f"{len(squad)} players"))

            tm_ids_in_squad: set[int] = {p["tm_id"] for p in squad}

            # 2. Get current DB squad for this club
            current_db_squad = list(Player.objects.filter(club=club))
            current_db_tm_ids: set[int] = {
                p.transfermarkt_id for p in current_db_squad
                if p.transfermarkt_id
            }

            moved = created = 0

            # 3. Process each TM squad player
            for entry in squad:
                tm_id = entry["tm_id"]
                mv = entry["market_value"]
                ws_pos = entry["ws_position"]
                salary = salary_from_mv(mv)

                existing = tm_id_to_player.get(tm_id)

                if existing:
                    # Player exists — move to this club if not already there
                    old_club_name = existing.club.name if existing.club else "—"
                    fields_to_update = []

                    if existing.club_id != club.pk:
                        if not dry_run:
                            existing.club = club
                        fields_to_update.append("club")
                        moved += 1
                        self.stdout.write(
                            f"    → {existing.first_name} {existing.last_name}"
                            f" [{old_club_name} → {club.name}]"
                        )

                    # Update real_life_club
                    if existing.real_life_club_id != club.pk:
                        if not dry_run:
                            existing.real_life_club = club
                        fields_to_update.append("real_life_club")

                    # Update market value if TM has a value
                    if mv > 0 and existing.market_value != mv:
                        if not dry_run:
                            existing.market_value = mv
                            existing.salary_per_match = salary
                        fields_to_update.extend(["market_value", "salary_per_match"])

                    # Update position if player has none
                    if not existing.position and ws_pos in VALID_WS_POSITIONS:
                        if not dry_run:
                            existing.position = ws_pos
                            existing.main_position_1 = ws_pos
                        fields_to_update.extend(["position", "main_position_1"])

                    if fields_to_update and not dry_run:
                        existing.save(update_fields=list(set(fields_to_update)))

                else:
                    # New player — create a minimal record
                    created += 1
                    self.stdout.write(
                        f"    + NEW: {entry['full_name']}"
                        f" (tm:{tm_id}) pos={ws_pos} mv={float(mv)/1e6:.1f}M"
                    )
                    if not dry_run:
                        new_player = Player(
                            first_name=entry["first_name"],
                            last_name=entry["last_name"],
                            club=club,
                            real_life_club=club,
                            transfermarkt_id=tm_id,
                            position=ws_pos if ws_pos in VALID_WS_POSITIONS else "",
                            main_position_1=ws_pos if ws_pos in VALID_WS_POSITIONS else "",
                            market_value=mv,
                            salary_per_match=salary,
                            age=0,
                        )
                        new_player.save()
                        # Add to lookup for subsequent clubs
                        tm_id_to_player[tm_id] = new_player

            # 4. Retire ex-players (in DB for this club but NOT in TM squad)
            retired = 0
            if not no_retire:
                for db_player in current_db_squad:
                    if db_player.transfermarkt_id and db_player.transfermarkt_id not in tm_ids_in_squad:
                        self.stdout.write(
                            f"    ← RETIRE: {db_player.first_name} {db_player.last_name}"
                            f" (tm:{db_player.transfermarkt_id}) → Karrierende"
                        )
                        if not dry_run:
                            db_player.club = karrierende
                            db_player.real_life_club = None
                            db_player.save(update_fields=["club", "real_life_club"])
                        retired += 1
                    elif not db_player.transfermarkt_id:
                        # No TM ID — keep in place (Heidenheim/Mainz/Kiel placeholder players)
                        pass

            self.stdout.write(
                f"  Summary: {moved} moved, {created} created, {retired} retired"
            )
            total_moved += moved
            total_created += created
            total_retired += retired

            time.sleep(delay)

        self.stdout.write(f"\n{'═'*60}")
        mode = "DRY RUN" if dry_run else "DONE"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: {total_moved} moved, {total_created} created, "
                f"{total_retired} retired across {len(clubs_to_process)} clubs."
            )
        )
