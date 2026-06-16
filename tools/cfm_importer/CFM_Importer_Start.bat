@echo off
rem ============================================================================
rem  CFM-Importer — Start-Skript fuer Windows
rem  Richtet eine virtuelle Umgebung ein, installiert Abhaengigkeiten und
rem  startet den Importer. Kommt mit deutschen Pfaden und Leerzeichen zurecht
rem  und enthaelt KEINE benutzerspezifischen absoluten Pfade.
rem ============================================================================
setlocal enableextensions
chcp 65001 >nul
rem In das Verzeichnis dieses Skripts wechseln (unterstuetzt Leerzeichen/Umlaute).
pushd "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

rem --- System-Python suchen ---------------------------------------------------
rem  Zuerst den offiziellen py-Launcher versuchen (trifft NIE den Microsoft-
rem  Store-Platzhalter). Danach echtes python.exe, wobei der Store-Stub unter
rem  ...\WindowsApps\ ausdruecklich ignoriert wird.
set "SYS_PY="
where py >nul 2>nul && set "SYS_PY=py -3"
if not defined SYS_PY (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | find /i "\WindowsApps\" >nul || (
      if not defined SYS_PY set "SYS_PY=%%P"
    )
  )
)
rem  Gefundenen Interpreter pruefen (faengt den Store-Platzhalter ab, falls er
rem  trotzdem antwortet).
if defined SYS_PY (
  %SYS_PY% -c "import sys" >nul 2>nul || set "SYS_PY="
)
if not defined SYS_PY (
  echo [FEHLER] Es wurde kein funktionierendes Python gefunden.
  echo          1^) Python 3.10 oder neuer von python.org installieren und beim
  echo             Setup "Add python.exe to PATH" aktivieren.
  echo          2^) Windows-Einstellungen ^> Apps ^> Erweiterte App-Einstellungen ^>
  echo             App-Ausfuehrungsaliase: "python.exe"/"python3.exe" auf AUS.
  goto :ende
)

rem --- Virtuelle Umgebung anlegen (nur beim ersten Start) ---------------------
if not exist "%VENV_PY%" (
  echo [SETUP] Erstelle virtuelle Umgebung ...
  %SYS_PY% -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [FEHLER] Die virtuelle Umgebung konnte nicht erstellt werden.
    goto :ende
  )
)

rem --- Abhaengigkeiten installieren -------------------------------------------
echo [SETUP] Aktualisiere pip ...
"%VENV_PY%" -m pip install --upgrade pip >nul 2>nul
echo [SETUP] Installiere Abhaengigkeiten (einmalig kann dies dauern) ...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [FEHLER] Die Abhaengigkeiten konnten nicht installiert werden.
  goto :ende
)

rem --- Konfiguration vorbereiten ----------------------------------------------
if not exist "config.json" (
  echo [HINWEIS] config.json fehlt. Kopiere Vorlage config.example.json ...
  copy /y "config.example.json" "config.json" >nul
  echo [HINWEIS] Bitte API-URL und Token in config.json eintragen und speichern.
  notepad "config.json"
)

rem --- Importer starten -------------------------------------------------------
echo.
echo [START] Starte den CFM-Importer ...
echo.
"%VENV_PY%" -m cfm_importer %*
set "RC=%ERRORLEVEL%"
echo.
echo [ENDE] Der Importer wurde beendet (Code %RC%).

:ende
echo.
pause
popd
endlocal
