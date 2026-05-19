# ============================================================
# Websoccer Asset Filter — 1. Bundesliga Komplett
# ============================================================
# Dieses Skript liest automatisch die Ordnerstruktur und
# findet alle benötigten Dateien, auch bei abweichenden Namen.
# Ausführen: Rechtsklick → "Mit PowerShell ausführen"
# ============================================================

$SOURCE = "C:\Users\mashu\Documents\Codex\Websoccer\Images"
$OUTPUT = "C:\Users\mashu\Desktop\websoccer_upload"

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
# Spieler-IDs (fm_inside_id aus der Datenbank)
# ============================================================
$PLAYER_IDS = @(
    # FC Bayern München (24)
    8718372, 20041862, 28049320, 28113827, 45109024, 53113114,
    76049803, 83228802, 85045409, 91119265, 91137493, 91207698,
    92021718, 92039023, 92088306, 93123163, 98040383, 28066083,
    28124579, 29221846, 35008097, 89063073, 91104807, 91190673,
    2000147056, 2000171034, 2000259380, 2000262633, 2000375662, 2000529129,
    # Borussia Dortmund (24)
    12038706, 12087972, 16045721, 16147659, 16182894, 16279486,
    19383257, 28127875, 35006814, 35008097, 37046467, 45109947,
    48036785, 53113114, 72051619, 85111795, 91018450, 91107360,
    91137493, 91139869, 92021718, 92065436, 92088306, 93123163,
    2000069555, 2000121585, 2000180861, 2000205927, 2000333549, 2000338374,
    # Borussia Mönchengladbach (27)
    37046467, 45109947, 48036785, 49037694, 72051281, 72051619,
    91144396, 91144903, 91167376, 91190660, 91193050, 91194484,
    91206105, 92012093, 92065436, 92067018, 93142507, 98029083,
    2000020405, 2000110066, 2000116422, 2000151926, 2000154596,
    2000189121, 2000259404, 2000468465,
    # SV Werder Bremen (1 bisher bekannt)
    92065694
)

# ============================================================
# Hilfsfunktion: Suche Ordner mit alternativen Namen
# ============================================================
function Find-Folder {
    param([string]$Base, [string[]]$Candidates)
    foreach ($name in $Candidates) {
        $path = Join-Path $Base $name
        if (Test-Path $path) { return $path }
    }
    return $null
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Websoccer Asset Filter — 1. Bundesliga    ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Quelle : $SOURCE" -ForegroundColor Gray
Write-Host "  Ziel   : $OUTPUT"   -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path $SOURCE)) {
    Write-Host "  FEHLER: Quellordner nicht gefunden: $SOURCE" -ForegroundColor Red
    Read-Host "  Enter drücken zum Beenden"
    exit 1
}

# Zeige vorhandene Unterordner
Write-Host "  Gefundene Unterordner in Quelle:" -ForegroundColor DarkCyan
Get-ChildItem $SOURCE -Directory | ForEach-Object { Write-Host "    · $($_.Name)" -ForegroundColor Gray }
Write-Host ""

# Ausgabe-Ordner anlegen
$folders = @("players","logos","kits","stadiums","city","backgrounds","flags","nations","competitions","trophies")
foreach ($f in $folders) { New-Item -ItemType Directory -Force -Path "$OUTPUT\$f" | Out-Null }

# ============================================================
# 1) SPIELER-PORTRAITS
# ============================================================
Write-Host "[1/7] Spieler-Portraits..." -ForegroundColor Yellow
$playerSrc = Find-Folder $SOURCE @("Players","Spieler","player","Face","Faces","facesfm26","portraits","Portraits","Player Faces","Bilder\Spieler")
if ($playerSrc) {
    Write-Host "  Ordner: $playerSrc" -ForegroundColor DarkGray
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
} else {
    Write-Host "  ✗ Spieler-Ordner nicht gefunden! Getestet: Players, Spieler, Faces, Portraits" -ForegroundColor Red
}

# ============================================================
# 2) VEREINS-LOGOS / WAPPEN
# ============================================================
Write-Host "[2/7] Vereins-Logos & Wappen..." -ForegroundColor Yellow
$logoSrc = Find-Folder $SOURCE @("Logos","logos","Wappen","Crests","crests","Badge","Badges","Club Logos","Vereinslogos","Logo","Verein\Logos","Clubs")
if ($logoSrc) {
    Write-Host "  Ordner: $logoSrc" -ForegroundColor DarkGray
    $lFound = 0; $lMiss = @()
    foreach ($id in $CLUB_IDS) {
        $copied = $false
        foreach ($ext in @("png","svg","jpg","webp","jpeg")) {
            $file = Join-Path $logoSrc "$id.$ext"
            if (Test-Path $file) {
                Copy-Item $file "$OUTPUT\logos\" -Force
                $lFound++; $copied = $true
            }
        }
        if (-not $copied) { $lMiss += $id }
    }
    Write-Host "  ✓ $lFound Logos gefunden" -ForegroundColor Green
    if ($lMiss.Count -gt 0) {
        Write-Host "  ? Nicht gefunden (IDs): $($lMiss -join ', ')" -ForegroundColor DarkYellow
        # Zeige erste 10 Dateien im Logo-Ordner als Hinweis
        Write-Host "  → Erste Dateien im Logo-Ordner:" -ForegroundColor DarkGray
        Get-ChildItem $logoSrc -File | Select-Object -First 10 | ForEach-Object { Write-Host "      $($_.Name)" -ForegroundColor Gray }
    }
} else {
    Write-Host "  ✗ Logo-Ordner nicht gefunden!" -ForegroundColor Red
    Write-Host "  → Bitte Ordnernamen prüfen. Getestet: Logos, Wappen, Crests, Badges, Club Logos" -ForegroundColor DarkYellow
    # Suche nach PNG-Dateien mit Club-IDs irgendwo im Quellordner
    Write-Host "  → Suche Club-IDs in gesamtem Quellordner..." -ForegroundColor DarkGray
    $anyFound = 0
    foreach ($id in $CLUB_IDS) {
        $results = Get-ChildItem $SOURCE -Recurse -Filter "$id.png" -ErrorAction SilentlyContinue
        if ($results) {
            Copy-Item $results[0].FullName "$OUTPUT\logos\$id.png" -Force
            $anyFound++
            Write-Host "    Gefunden: $($results[0].FullName)" -ForegroundColor Cyan
        }
    }
    if ($anyFound -gt 0) {
        Write-Host "  ✓ $anyFound Logos durch Tiefensuche gefunden" -ForegroundColor Green
    }
}

# ============================================================
# 3) TRIKOTS (2D Kits)
# ============================================================
Write-Host "[3/7] Trikots (2D Kits)..." -ForegroundColor Yellow
$kitSrc = Find-Folder $SOURCE @("2D Kits","Kits","kits","Trikots","trikots","Kit","Jersey","Jerseys","2D","2d Kits")
if ($kitSrc) {
    Write-Host "  Ordner: $kitSrc" -ForegroundColor DarkGray
    $kFound = 0
    foreach ($id in $CLUB_IDS) {
        foreach ($suffix in @("_home","_away","_third","_gk_home","_gk_away","")) {
            foreach ($ext in @("svg","png","jpg","webp")) {
                $file = Join-Path $kitSrc "${id}${suffix}.$ext"
                if (Test-Path $file) {
                    Copy-Item $file "$OUTPUT\kits\" -Force; $kFound++
                }
            }
        }
    }
    Write-Host "  ✓ $kFound Trikot-Dateien gefunden" -ForegroundColor Green
} else {
    Write-Host "  ✗ Trikot-Ordner nicht gefunden!" -ForegroundColor Red
}

# ============================================================
# 4) STADION-BILDER
# ============================================================
Write-Host "[4/7] Stadion-Bilder..." -ForegroundColor Yellow
$stadSrc = Find-Folder $SOURCE @("Stadium","Stadiums","Stadion","Stadien","stadiums","Grounds","Ground")
$sFound = 0
if ($stadSrc) {
    Write-Host "  Ordner: $stadSrc" -ForegroundColor DarkGray
    $stadiumNames = @(
        "allianz","signal-iduna","westfalenstadion","bayarena","red-bull","commerzbank",
        "mercedes-benz","europa-park","borussia-park","mewa","weserstadion","wwk",
        "volkswagen","vonovia","rheinenergie","hardtwaldstadion","holstein","millerntor",
        "voith-arena","fc-bayern","b-dortmund","b-leverkusen","e-frankfurt","mainz",
        "stuttgart","freiburg","b-gladbach","hoffenheim","wolfsburg","bochum","kiel",
        "union-berlin","redbull-leipzig","augsburg","heidenheim","st-pauli","pauli"
    )
    foreach ($name in $stadiumNames) {
        Get-ChildItem $stadSrc -Recurse -Filter "*$name*" -ErrorAction SilentlyContinue | ForEach-Object {
            if (-not (Test-Path "$OUTPUT\stadiums\$($_.Name)")) {
                Copy-Item $_.FullName "$OUTPUT\stadiums\" -Force; $sFound++
            }
        }
    }
    Write-Host "  ✓ $sFound Stadion-Dateien gefunden" -ForegroundColor Green
} else {
    Write-Host "  ✗ Stadion-Ordner nicht gefunden!" -ForegroundColor Red
}

# ============================================================
# 5) CITY-BILDER (als {club_id}.jpg)
# ============================================================
Write-Host "[5/7] City-Bilder..." -ForegroundColor Yellow
$citySrc = Find-Folder $SOURCE @("City","Cities","city","Stadtbilder","Städte","Stadt")
$cFound = 0
if ($citySrc) {
    Write-Host "  Ordner: $citySrc" -ForegroundColor DarkGray
    # Zuerst nach Club-ID-Dateien suchen
    foreach ($id in $CLUB_IDS) {
        foreach ($ext in @("jpg","png","jpeg","webp")) {
            $file = Join-Path $citySrc "$id.$ext"
            if (Test-Path $file) {
                Copy-Item $file "$OUTPUT\city\" -Force; $cFound++
            }
        }
    }
    # Dann nach Stadtnamen
    $cities = @("munchen","münchen","munich","dortmund","leverkusen","leipzig","frankfurt",
                "stuttgart","freiburg","monchengladbach","mönchengladbach","sinsheim",
                "wolfsburg","bremen","augsburg","mainz","berlin","bochum","kiel",
                "heidenheim","hamburg","germany")
    foreach ($city in $cities) {
        Get-ChildItem $citySrc -Recurse -Filter "*$city*" -ErrorAction SilentlyContinue | ForEach-Object {
            if (-not (Test-Path "$OUTPUT\city\$($_.Name)")) {
                Copy-Item $_.FullName "$OUTPUT\city\" -Force; $cFound++
            }
        }
    }
    Write-Host "  ✓ $cFound City-Bilder gefunden" -ForegroundColor Green
}

# ============================================================
# 6) KLEINE ORDNER KOMPLETT
# ============================================================
Write-Host "[6/7] Flags, Nationen, Backgrounds, Trophies..." -ForegroundColor Yellow

$completeMap = @{
    @("Flaggen","Flags","flags","Fahnen","Nations\Flags","flag-svg")          = "$OUTPUT\flags"
    @("Nationen","Nations","nations","Nationalmannschaften","Nation")         = "$OUTPUT\nations"
    @("Backgrounds","Hintergründe","Background","Hintergrunde","Hintergrund") = "$OUTPUT\backgrounds"
    @("Trophies","Trophäen","Trophy","Pokale","trophies","Cups")              = "$OUTPUT\trophies"
    @("Competitions","Wettbewerbe","Competition","Logos\Competitions")        = "$OUTPUT\competitions"
}

foreach ($entry in $completeMap.GetEnumerator()) {
    $src = Find-Folder $SOURCE $entry.Key
    if ($src) {
        Copy-Item -Path "$src\*" -Destination $entry.Value -Recurse -Force -ErrorAction SilentlyContinue
        $count = (Get-ChildItem $entry.Value -Recurse -File -ErrorAction SilentlyContinue).Count
        Write-Host "  ✓ $($entry.Key[0]): $count Dateien" -ForegroundColor Green
    }
}

# ============================================================
# 7) ZIPs ERSTELLEN
# ============================================================
Write-Host ""
Write-Host "[7/7] ZIPs erstellen..." -ForegroundColor Yellow

function Make-Zip {
    param([string]$ZipPath, [string[]]$Sources)
    $valid = $Sources | Where-Object { (Test-Path $_) -and ((Get-ChildItem $_ -Recurse -File).Count -gt 0) }
    if ($valid.Count -gt 0) {
        Compress-Archive -Path $valid -DestinationPath $ZipPath -Force
        $size = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
        Write-Host "  ✓ $(Split-Path $ZipPath -Leaf) ($size MB)" -ForegroundColor Cyan
        return $true
    }
    return $false
}

Make-Zip "$OUTPUT\ws_players_logos_kits.zip" @("$OUTPUT\players","$OUTPUT\logos","$OUTPUT\kits")
Make-Zip "$OUTPUT\ws_stadiums_city.zip"       @("$OUTPUT\stadiums","$OUTPUT\city")
Make-Zip "$OUTPUT\ws_small_assets.zip"        @("$OUTPUT\flags","$OUTPUT\nations","$OUTPUT\backgrounds","$OUTPUT\trophies","$OUTPUT\competitions")

# ============================================================
# ZUSAMMENFASSUNG
# ============================================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              FERTIG!                        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Dateien unter:" -ForegroundColor White
Write-Host "  $OUTPUT\" -ForegroundColor Gray
Write-Host ""
Write-Host "  Zum Hochladen in Replit:" -ForegroundColor White
Write-Host "  1. ws_players_logos_kits.zip  — Spieler-Portraits, Logos, Trikots" -ForegroundColor Green
Write-Host "  2. ws_stadiums_city.zip       — Stadion- und Stadtbilder" -ForegroundColor Green
Write-Host "  3. ws_small_assets.zip        — Flaggen, Nationen, Backgrounds, Trophies" -ForegroundColor Green
Write-Host ""
Write-Host "  → Alle 3 ZIPs per Drag & Drop in den Replit-Ordner 'tools/' ziehen" -ForegroundColor Yellow
Write-Host ""
Read-Host "  Enter drücken zum Beenden"
