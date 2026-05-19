# ============================================================
# Websoccer Asset Filter — 1. Bundesliga Komplett
# Erstellt gefilterte ZIPs für den Replit-Upload
# Ausführen: Rechtsklick → "Mit PowerShell ausführen"
# ============================================================

$SOURCE  = "C:\Users\mashu\Documents\Codex\Websoccer\Images"
$OUTPUT  = "C:\Users\mashu\Desktop\websoccer_upload"

# ============================================================
# IDs — 1. Bundesliga (18 Clubs)
# ============================================================
$CLUB_IDS = @(
    907,    # Borussia Dortmund
    908,    # Borussia Mönchengladbach
    909,    # Bayer 04 Leverkusen
    910,    # Eintracht Frankfurt
    911,    # 1. FSV Mainz 05
    912,    # SV Werder Bremen
    913,    # VfB Stuttgart
    914,    # SC Freiburg
    915,    # FC Bayern München
    916,    # VfL Wolfsburg
    917,    # VfL Bochum
    922,    # FC St. Pauli
    5890,   # 1. FC Union Berlin
    6430,   # Holstein Kiel
    6721,   # RB Leipzig
    12185,  # TSG 1899 Hoffenheim
    12498,  # FC Augsburg
    13076   # 1. FC Heidenheim
)

# ============================================================
# Spieler-IDs (aus der Datenbank, Bayern + BVB + Gladbach
# haben fm_inside_ids — alle anderen folgen nach dem Upload)
# ============================================================
$PLAYER_IDS = @(
    # FC Bayern München
    8718372,     # Manuel Neuer
    20041862,    # Thomas Müller
    28049320,    # Harry Kane
    28113827,    # Joshua Kimmich
    45109024,    # Leroy Sané
    53113114,    # Raphaël Guerreiro
    76049803,    # Serge Gnabry
    83228802,    # Leon Goretzka
    85045409,    # Jamal Musiala
    91119265,    # Alphonso Davies
    91137493,    # Josip Stanisic
    91207698,    # Jonathan Tah
    92021718,    # Dayot Upamecano
    92039023,    # Aleksandar Pavlovic
    92088306,    # Konrad Laimer
    93123163,    # Hiroki Ito
    98040383,    # Michael Olise
    # Borussia Dortmund
    12038706,
    12087972,
    16045721,
    16147659,
    16182894,
    16279486,
    19383257,
    28066083,
    28124579,
    28127875,
    29221846,
    35006814,
    35008097,
    37046467,
    45109947,
    48036785,
    49037694,
    72051281,
    72051619,
    85111795,
    89063073,
    91018450,
    91104807,
    91107360,
    91139869,
    91144396,
    91144903,
    91167376,
    91190660,
    91193050,
    91194484,
    91206105,
    91207281,
    92012093,
    92065436,
    92065694,
    92067018,
    93142507,
    98029083,
    # Borussia Mönchengladbach
    2000020405,
    2000069555,
    2000110066,
    2000116422,
    2000121585,
    2000147056,
    2000151926,
    2000154596,
    2000171034,
    2000180861,
    2000189121,
    2000205927,
    2000259380,
    2000259404,
    2000262633,
    2000333549,
    2000338374,
    2000375662,
    2000468465,
    2000529129,
    91190673
)

# ============================================================
# Bundesliga-Wettbewerb-IDs (für Logos)
# ============================================================
$COMPETITION_IDS = @(
    "bundesliga", "dfbpokal", "championsleague",
    "europaleague", "conferenceleague", "supercup",
    "1", "2", "3"   # FM-Inside Wettbewerbs-IDs
)

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Websoccer Asset Filter — 1. Bundesliga    ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Quelle : $SOURCE" -ForegroundColor Gray
Write-Host "  Ziel   : $OUTPUT" -ForegroundColor Gray
Write-Host ""

# Ausgabe-Ordner anlegen
$folders = @("players","logos","kits","stadiums","city","backgrounds","flags","nations","symbols","competitions","trophies")
foreach ($f in $folders) {
    New-Item -ItemType Directory -Force -Path "$OUTPUT\$f" | Out-Null
}

# ============================================================
# 1) SPIELER-PORTRAITS — nur benötigte IDs
# ============================================================
Write-Host "[1/7] Spieler-Portraits..." -ForegroundColor Yellow
$playerSrc = Join-Path $SOURCE "Players"
$pFound = 0; $pMiss = 0

foreach ($id in $PLAYER_IDS) {
    $copied = $false
    foreach ($ext in @("png","svg","jpg","webp","jpeg")) {
        $file = Join-Path $playerSrc "$id.$ext"
        if (Test-Path $file) {
            Copy-Item $file "$OUTPUT\players\" -Force
            $copied = $true; $pFound++; break
        }
    }
    if (-not $copied) { $pMiss++ }
}
Write-Host "  ✓ $pFound Portraits gefunden ($pMiss nicht vorhanden)" -ForegroundColor Green

# ============================================================
# 2) VEREINS-LOGOS / WAPPEN — alle 18 Clubs
# ============================================================
Write-Host "[2/7] Vereins-Logos & Wappen..." -ForegroundColor Yellow
$logoSrc = Join-Path $SOURCE "Logos"
$lFound = 0

foreach ($id in $CLUB_IDS) {
    foreach ($ext in @("png","svg","jpg","webp")) {
        $file = Join-Path $logoSrc "$id.$ext"
        if (Test-Path $file) {
            Copy-Item $file "$OUTPUT\logos\" -Force
            $lFound++
        }
    }
}
Write-Host "  ✓ $lFound Logo-Dateien gefunden" -ForegroundColor Green

# ============================================================
# 3) TRIKOTS (2D Kits) — alle 18 Clubs × Heim/Auswärts/Third
# ============================================================
Write-Host "[3/7] Trikots (2D Kits)..." -ForegroundColor Yellow
$kitSrc = Join-Path $SOURCE "2D Kits"
$kFound = 0

foreach ($id in $CLUB_IDS) {
    foreach ($suffix in @("_home","_away","_third","_gk_home","_gk_away")) {
        foreach ($ext in @("svg","png")) {
            $file = Join-Path $kitSrc "${id}${suffix}.$ext"
            if (Test-Path $file) {
                Copy-Item $file "$OUTPUT\kits\" -Force
                $kFound++
            }
        }
    }
    # Auch ohne Suffix versuchen
    foreach ($ext in @("svg","png")) {
        $file = Join-Path $kitSrc "$id.$ext"
        if (Test-Path $file) {
            Copy-Item $file "$OUTPUT\kits\" -Force
            $kFound++
        }
    }
}
Write-Host "  ✓ $kFound Trikot-Dateien gefunden" -ForegroundColor Green

# ============================================================
# 4) STADION-BILDER — alle 18 Clubs
# ============================================================
Write-Host "[4/7] Stadion-Bilder..." -ForegroundColor Yellow
$stadSrc = Join-Path $SOURCE "Stadium"
$sFound = 0

# Nach Club-ID suchen
foreach ($id in $CLUB_IDS) {
    foreach ($ext in @("jpg","png","webp","jpeg")) {
        Get-ChildItem $stadSrc -Recurse -Filter "*$id*.$ext" 2>$null | ForEach-Object {
            Copy-Item $_.FullName "$OUTPUT\stadiums\" -Force; $sFound++
        }
    }
}
# Bekannte Stadtamen direkt suchen
$stadiumNames = @(
    "allianz","signal-iduna","westfalenstadion","bayarena","red-bull","commerzbank",
    "mercedes-benz","europa-park","borussia-park","mewa","weserstadion","wwk",
    "volkswagen","vonovia","rheinenergie","hardtwaldstadion","holstein","millerntor",
    "voith-arena","heidenheim","munchen","dortmund","leverkusen","leipzig","frankfurt",
    "stuttgart","freiburg","gladbach","hoffenheim","wolfsburg","bremen","augsburg",
    "mainz","berlin","bochum","kiel","hamburg","pauli"
)
foreach ($name in $stadiumNames) {
    Get-ChildItem $stadSrc -Recurse -Filter "*$name*" 2>$null | ForEach-Object {
        if (-not (Test-Path "$OUTPUT\stadiums\$($_.Name)")) {
            Copy-Item $_.FullName "$OUTPUT\stadiums\" -Force; $sFound++
        }
    }
}
Write-Host "  ✓ $sFound Stadion-Dateien gefunden" -ForegroundColor Green

# ============================================================
# 5) CITY-BILDER — Bundesliga-Städte
# ============================================================
Write-Host "[5/7] City-Bilder..." -ForegroundColor Yellow
$citySrc = Join-Path $SOURCE "City"
$cFound = 0

$cities = @(
    "munchen","münchen","munich","dortmund","leverkusen","leipzig","frankfurt",
    "stuttgart","freiburg","monchengladbach","mönchengladbach","hoffenheim",
    "wolfsburg","bremen","augsburg","mainz","berlin","bochum","kiel","hamburg",
    "heidenheim","sinsheim","germany","deutsch"
)
foreach ($city in $cities) {
    Get-ChildItem $citySrc -Recurse -Filter "*$city*" 2>$null | ForEach-Object {
        if (-not (Test-Path "$OUTPUT\city\$($_.Name)")) {
            Copy-Item $_.FullName "$OUTPUT\city\" -Force; $cFound++
        }
    }
}
Write-Host "  ✓ $cFound City-Bilder gefunden" -ForegroundColor Green

# ============================================================
# 6) KLEINE ORDNER KOMPLETT (Flaggen, Nationen, Symbols,
#    Backgrounds, Trophies, Competitions)
# ============================================================
Write-Host "[6/7] Kleine Ordner (komplett)..." -ForegroundColor Yellow

$completeMap = @{
    "Flaggen"     = "$OUTPUT\flags"
    "Nationen"    = "$OUTPUT\nations"
    "Symbol"      = "$OUTPUT\symbols"
    "Backgrounds" = "$OUTPUT\backgrounds"
    "Trophies"    = "$OUTPUT\trophies"
}

foreach ($entry in $completeMap.GetEnumerator()) {
    $src = Join-Path $SOURCE $entry.Key
    if (Test-Path $src) {
        Copy-Item -Path "$src\*" -Destination $entry.Value -Recurse -Force
        $count = (Get-ChildItem $entry.Value -Recurse -File).Count
        Write-Host "  ✓ $($entry.Key): $count Dateien" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $($entry.Key) nicht gefunden" -ForegroundColor DarkYellow
    }
}

# Wettbewerbs-Logos
$compSrc = Join-Path $SOURCE "Competitions"
if (-not (Test-Path $compSrc)) { $compSrc = Join-Path $SOURCE "Wettbewerbe" }
if (-not (Test-Path $compSrc)) { $compSrc = Join-Path $SOURCE "Logos\Competitions" }
if (Test-Path $compSrc) {
    Copy-Item -Path "$compSrc\*" -Destination "$OUTPUT\competitions" -Recurse -Force
    $count = (Get-ChildItem "$OUTPUT\competitions" -Recurse -File).Count
    Write-Host "  ✓ Competitions: $count Dateien" -ForegroundColor Green
}

# ============================================================
# 7) ALLES IN ZIPs PACKEN
# ============================================================
Write-Host ""
Write-Host "[7/7] ZIPs erstellen..." -ForegroundColor Yellow

# ZIP 1: Spieler + Logos + Kits (klein)
$zip1 = "$OUTPUT\ws_players_logos_kits.zip"
$zip1Sources = @()
if ((Get-ChildItem "$OUTPUT\players" -File).Count -gt 0) { $zip1Sources += "$OUTPUT\players" }
if ((Get-ChildItem "$OUTPUT\logos" -File).Count -gt 0)   { $zip1Sources += "$OUTPUT\logos" }
if ((Get-ChildItem "$OUTPUT\kits" -File).Count -gt 0)    { $zip1Sources += "$OUTPUT\kits" }
if ($zip1Sources.Count -gt 0) {
    Compress-Archive -Path $zip1Sources -DestinationPath $zip1 -Force
    $s1 = [math]::Round((Get-Item $zip1).Length/1MB,1)
    Write-Host "  ✓ ws_players_logos_kits.zip ($s1 MB)" -ForegroundColor Cyan
}

# ZIP 2: Stadien + City (mittel)
$zip2 = "$OUTPUT\ws_stadiums_city.zip"
$zip2Sources = @()
if ((Get-ChildItem "$OUTPUT\stadiums" -File).Count -gt 0) { $zip2Sources += "$OUTPUT\stadiums" }
if ((Get-ChildItem "$OUTPUT\city" -File).Count -gt 0)     { $zip2Sources += "$OUTPUT\city" }
if ($zip2Sources.Count -gt 0) {
    Compress-Archive -Path $zip2Sources -DestinationPath $zip2 -Force
    $s2 = [math]::Round((Get-Item $zip2).Length/1MB,1)
    Write-Host "  ✓ ws_stadiums_city.zip ($s2 MB)" -ForegroundColor Cyan
}

# ZIP 3: Alle kleinen Ordner (Flaggen, Nationen, etc.)
$zip3 = "$OUTPUT\ws_small_assets.zip"
$zip3Sources = @()
foreach ($d in @("flags","nations","symbols","backgrounds","trophies","competitions")) {
    if (Test-Path "$OUTPUT\$d") {
        if ((Get-ChildItem "$OUTPUT\$d" -Recurse -File).Count -gt 0) {
            $zip3Sources += "$OUTPUT\$d"
        }
    }
}
if ($zip3Sources.Count -gt 0) {
    Compress-Archive -Path $zip3Sources -DestinationPath $zip3 -Force
    $s3 = [math]::Round((Get-Item $zip3).Length/1MB,1)
    Write-Host "  ✓ ws_small_assets.zip ($s3 MB)" -ForegroundColor Cyan
}

# ============================================================
# ZUSAMMENFASSUNG
# ============================================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              FERTIG!                        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Dateien auf dem Desktop unter:" -ForegroundColor White
Write-Host "  C:\Users\mashu\Desktop\websoccer_upload\" -ForegroundColor Gray
Write-Host ""
Write-Host "  Zum Hochladen in Replit:" -ForegroundColor White
Write-Host "  1. ws_players_logos_kits.zip  — klein, zuerst hochladen" -ForegroundColor Green
Write-Host "  2. ws_stadiums_city.zip       — mittel" -ForegroundColor Green
Write-Host "  3. ws_small_assets.zip        — Flaggen, Hintergründe usw." -ForegroundColor Green
Write-Host ""
Write-Host "  → In Replit per Drag & Drop in den Ordner 'tools/' ziehen" -ForegroundColor Yellow
Write-Host "  → Dann Bescheid geben — ich entpacke alles automatisch!" -ForegroundColor Yellow
Write-Host ""
Read-Host "  Enter drücken zum Beenden"
