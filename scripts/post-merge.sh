#!/bin/bash
set -e

python3 manage.py migrate --no-input
# A base-topology conversion must not block unrelated merges for a manager's
# customized stadium. Explicit opt-in retains the command's fail-closed checks.
if [[ "${ALIGN_KOLN_OFFICIAL_BLOCKS:-0}" == "1" ]]; then
    python3 manage.py align_koln_official_blocks --if-present --apply
else
    echo "[post-merge] Kölner Blockabgleich nicht angefordert; eigene Geometrie bleibt unverändert."
fi
python3 manage.py collectstatic --no-input --clear 2>/dev/null || true

# ── Regressions-Schnelltest ───────────────────────────────────────────────────
# Versucht nach jedem Merge einen frischen Snapshot (10 Saisons) zu erstellen,
# damit play_matchday immer einen aktuellen Referenzpunkt hat.
# Dieser optionale Schritt darf das 180-Sekunden-Setup nicht aufhalten.
# timeout beendet auch Kindprozesse; nach 5 Sekunden wird notfalls hart beendet.
# Fehler oder Zeitüberschreitungen blockieren die Nachbereitung NICHT.
mkdir -p .local/regression_history
echo "[post-merge] Starte Regressions-Schnelltest (10 Saisons) …"
if timeout --kill-after=5s 60s bash scripts/run_regression_v3.sh --seasons 10; then
    echo "[post-merge] Regressions-Snapshot erstellt."
else
    echo "[post-merge] WARNUNG: Regressions-Schnelltest fehlgeschlagen oder Zeitlimit erreicht — Nachbereitung wird fortgesetzt." >&2
fi
