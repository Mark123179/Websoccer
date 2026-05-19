# ============================================================
# Websoccer Asset Filter — erstellt gefilterte ZIPs für Replit
# Ausführen: Rechtsklick → "Mit PowerShell ausführen"
# ============================================================

$SOURCE = "C:\Users\mashu\Documents\Codex\Websoccer"
$OUTPUT = "C:\Users\mashu\Desktop\websoccer_upload"

# === IDs die wir in der Datenbank haben ===
$PLAYER_IDS = @(
    8718372, 20041862, 28049320, 28113827, 45109024,
    53113114, 76049803, 83228802, 85045409, 91119265,
    91137493, 91207698, 92021718, 92039023, 92088306,
    93123163, 98040383
)
$CLUB_IDS = @(907, 915)

Write-Host "=== Websoccer Asset Filter ===" -ForegroundColor Cyan
Write-Host "Quelle: $SOURCE"
Write-Host "Ziel:   $OUTPUT"
Write-Host ""

# Ausgabe-Ordner anlegen
New-Item -ItemType Directory -Force -Path "$OUTPUT\players" | Out-Null
New-Item -ItemType Directory -Force -Path "$OUTPUT\logos"   | Out-Null
New-Item -ItemType Directory -Force -Path "$OUTPUT\small"   | Out-Null

# ============================================================
# ZIP 1 — Kleine Ordner komplett kopieren
# ============================================================
Write-Host "[1/3] Kopiere kleine Ordner..." -ForegroundColor Yellow

$SMALL_FOLDERS = @("Backgrounds", "Flaggen", "Nationen", "Symbol", "2D Kits", "Trophies")
foreach ($folder in $SMALL_FOLDERS) {
    $src = Join-Path $SOURCE $folder
    $dst = Join-Path "$OUTPUT\small" $folder
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Recurse -Force
        Write-Host "  ✓ $folder" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $folder nicht gefunden" -ForegroundColor Red
    }
}

# ZIP erstellen
$zip1 = "$OUTPUT\ws_small_assets.zip"
Compress-Archive -Path "$OUTPUT\small\*" -DestinationPath $zip1 -Force
$size1 = [math]::Round((Get-Item $zip1).Length / 1MB, 1)
Write-Host "  → ws_small_assets.zip ($size1 MB)" -ForegroundColor Cyan

# ============================================================
# ZIP 2 — Player Portraits (nur benötigte IDs)
# ============================================================
Write-Host ""
Write-Host "[2/3] Filtere Spieler-Portraits..." -ForegroundColor Yellow

$playerSrc = Join-Path $SOURCE "Players"
$found = 0
$missing = 0

foreach ($id in $PLAYER_IDS) {
    $copied = $false
    foreach ($ext in @("png", "svg", "jpg", "webp")) {
        $file = Join-Path $playerSrc "$id.$ext"
        if (Test-Path $file) {
            Copy-Item $file "$OUTPUT\players\" -Force
            $copied = $true
            $found++
            break
        }
    }
    if (-not $copied) {
        Write-Host "  ✗ Kein Portrait für ID $id" -ForegroundColor DarkYellow
        $missing++
    }
}
Write-Host "  ✓ $found Portraits gefunden, $missing fehlen" -ForegroundColor Green

# ============================================================
# ZIP 3 — Club Logos (nur benötigte IDs)
# ============================================================
Write-Host ""
Write-Host "[3/3] Filtere Club-Logos..." -ForegroundColor Yellow

$logoSrc = Join-Path $SOURCE "Logos"
$foundLogos = 0

foreach ($id in $CLUB_IDS) {
    foreach ($ext in @("png", "svg", "jpg", "webp")) {
        $file = Join-Path $logoSrc "$id.$ext"
        if (Test-Path $file) {
            Copy-Item $file "$OUTPUT\logos\" -Force
            $foundLogos++
            Write-Host "  ✓ Club $id.$ext" -ForegroundColor Green
        }
    }
}

# Alles in eine ZIP (Players + Logos zusammen, klein genug)
$zip2 = "$OUTPUT\ws_player_logos.zip"
Compress-Archive -Path "$OUTPUT\players\*","$OUTPUT\logos\*" -DestinationPath $zip2 -Force
$size2 = [math]::Round((Get-Item $zip2).Length / 1MB, 1)
Write-Host "  → ws_player_logos.zip ($size2 MB)" -ForegroundColor Cyan

# ============================================================
# Zusammenfassung
# ============================================================
Write-Host ""
Write-Host "=== FERTIG ===" -ForegroundColor Cyan
Write-Host "Dateien zum Hochladen auf dem Desktop:" -ForegroundColor White
Write-Host "  1. ws_small_assets.zip  (~200 MB)" -ForegroundColor Green
Write-Host "  2. ws_player_logos.zip  (sehr klein, <5 MB)" -ForegroundColor Green
Write-Host ""
Write-Host "Beide ZIPs in Replit hochladen:" -ForegroundColor White
Write-Host "  → Replit File Explorer öffnen"
Write-Host "  → ZIP-Datei per Drag & Drop in den Ordner 'tools/' ziehen"
Write-Host "  → Dann sag Bescheid — ich entpacke sie automatisch!"
Write-Host ""
Read-Host "Enter drücken zum Beenden"
