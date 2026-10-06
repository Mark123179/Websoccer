"""Read-only projections for the package-mode screens. No source data mutation."""
from .package_validation import digest


TITLE_LABELS = {
    "championship": "Meisterschaft", "national_cup": "Nationaler Pokal",
    "super_cup": "Supercup", "international_cup": "International",
    "lower_tier": "Unterklassig",
}
DISPLAY_LABELS = dict(TITLE_LABELS, **{
    "Open": "Offen", "Player lock": "Einzelsperre", "Blocking": "Startsperre",
    "player": "Spieler", "coach": "Trainer", "club": "Verein",
})


def ordered_transfers(player, queryset=None):
    """Same-day real entries retain their order in the source package."""
    from game.models import SourceImportRun
    rows = list(queryset if queryset is not None else player.ws_transfer_history.all())
    run = SourceImportRun.objects.filter(status="applied").order_by("-applied_at", "-pk")
    package = next((item for item in run if any(
        p["ids"]["tm"]["value"] == player.transfermarkt_id for p in item.package_data["players"])), None)
    positions = {}
    if package:
        source = next(p for p in package.package_data["players"]
                      if p["ids"]["tm"]["value"] == player.transfermarkt_id)
        positions = {digest(row): index for index, row in enumerate(source["transfers"])}
    return sorted(rows, key=lambda row: (
        -row.transfer_date.toordinal(),
        positions.get(row.source_row_key, -row.pk)))


def loan_line(player):
    if player.loan_status not in ("loaned_in", "loaned_out"):
        return ""
    partner = (player.owner_club_original_name if player.loan_status == "loaned_in"
               else player.loan_club_original_name)
    prefix = "Leihe von" if player.loan_status == "loaned_in" else "verliehen an"
    parts = [f"{prefix} {partner or 'Unbekannter Verein'}"]
    start = next((row.transfer_date for row in ordered_transfers(player)
                  if row.is_loan and not is_loan_end(row.fee_text)), None)
    if start:
        parts.append("seit " + start.strftime("%d.%m.%Y"))
    parts.append("bis Ende Saison 1")
    return " · ".join(parts)


def is_loan_end(text):
    return (text or "").strip().lower().replace(" ", "").startswith(("leih-ende", "leihende"))
