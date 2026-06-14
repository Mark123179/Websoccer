#!/usr/bin/env bash
# run_regression_v3.sh — Führt den V3-Regressionsbericht mit festen Seeds aus
# und speichert die JSON-Summary im History-Ordner.
#
# Aufruf:
#   bash scripts/run_regression_v3.sh             # 100 Saisons (Standard)
#   bash scripts/run_regression_v3.sh --seasons 10  # Schnelltest
#
# Ausgabe: .local/regression_history/YYYYMMDD_HHMMSS/
#            seeds_stability.json
#            summary.json
#            metrics.json
#            club_averages.csv
#
# Nach dem Lauf wird automatisch ein Diff gegen den vorherigen Run ausgeführt,
# sofern ein früherer Lauf vorhanden ist.

set -euo pipefail

# ── Konfiguration ─────────────────────────────────────────────────────────────

SEEDS="1,7,21,42,99,2026"
SEASONS="${REGRESSION_SEASONS:-100}"
HISTORY_DIR=".local/regression_history"

# ── CLI-Argumente ─────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --seasons)
            SEASONS="$2"
            shift 2
            ;;
        --seeds)
            SEEDS="$2"
            shift 2
            ;;
        *)
            echo "Unbekanntes Argument: $1" >&2
            echo "Verwendung: $0 [--seasons N] [--seeds SEED_LISTE]" >&2
            exit 1
            ;;
    esac
done

# ── Verzeichnis vorbereiten ───────────────────────────────────────────────────

TIMESTAMP=$(date -u "+%Y%m%d_%H%M%S")
OUTPUT_DIR="${HISTORY_DIR}/${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

# ── Header ────────────────────────────────────────────────────────────────────

echo "========================================"
echo " Regressionsbericht V3"
echo " Seeds:   $SEEDS"
echo " Saisons: $SEASONS"
echo " Ausgabe: $OUTPUT_DIR"
echo " Zeit:    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "========================================"
echo ""

# ── Regression ausführen ──────────────────────────────────────────────────────

python manage.py regression_sim \
    --seasons "$SEASONS" \
    --seeds   "$SEEDS" \
    --output  "$OUTPUT_DIR"

echo ""
echo "✓ Bericht abgeschlossen."
echo "  Dateien in: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"
echo ""

# ── Diff gegen vorherigen Lauf ────────────────────────────────────────────────

# Alle Unterverzeichnisse nach Zeitstempel sortieren, neuestes zuerst,
# dann das zweitneuste als "vorherigen Lauf" verwenden.
PREV=$(find "$HISTORY_DIR" -mindepth 1 -maxdepth 1 -type d \
    | sort -r \
    | grep -v "^${OUTPUT_DIR}$" \
    | head -1 \
    || true)

if [[ -n "$PREV" && -f "${PREV}/seeds_stability.json" ]]; then
    echo "Vergleiche mit vorherigem Lauf: $(basename "$PREV")"
    echo ""
    python scripts/diff_regression.py \
        "${PREV}/seeds_stability.json" \
        "${OUTPUT_DIR}/seeds_stability.json"
else
    echo "(Kein früherer Lauf gefunden — kein Diff.)"
fi

echo ""
echo "========================================"
echo " Fertig."
echo "========================================"
