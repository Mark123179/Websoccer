#!/usr/bin/env bash
# Befüllt Nationalitäten der 127 betroffenen Spieler via CMTracker-API.
# Muss auf dem Produktionsserver (Hetzner) ausgeführt werden — API ist IP-gebunden.
#
# Verwendung:
#   ./scripts/run_nationality_backfill.sh
#   DRY_RUN=1 ./scripts/run_nationality_backfill.sh   # kein Schreiben
#
# Betroffene Vereine: Kiel, Mainz, Bochum, St. Pauli, Leverkusen,
#                     Leipzig, Frankfurt, Union Berlin, Werder Bremen

set -euo pipefail

DB_SLUG="${CMT_DB:-fc26}"
OUTDIR="${EXPORT_DIR:-exports/nationality_backfill_$(date +%Y%m%d_%H%M%S)}"

echo "=== Schritt 0: Vorher-Stand ==="
python manage.py report_missing_nationalities

if [ "${DRY_RUN:-0}" = "1" ]; then
    echo ""
    echo "=== Schritt 1: Dry-Run (kein Schreiben) ==="
    python manage.py backfill_nationality_from_cmt --db "$DB_SLUG"
    echo ""
    echo "DRY_RUN=1 — Abbruch vor dem Schreiben. Mit DRY_RUN=0 oder ohne Variable erneut ausführen."
    exit 0
fi

echo ""
echo "=== Schritt 1: Backfill via CMTracker (--apply --set-nt) ==="
python manage.py backfill_nationality_from_cmt --db "$DB_SLUG" --apply --set-nt

echo ""
echo "=== Schritt 2: Nachher-Stand ==="
python manage.py report_missing_nationalities

echo ""
echo "=== Schritt 3: CSV-Export aller betroffenen Vereine ==="
mkdir -p "$OUTDIR"
python manage.py export_club_import_csv --all-affected --outdir "$OUTDIR"

echo ""
echo "Fertig. CSVs in: $OUTDIR"
