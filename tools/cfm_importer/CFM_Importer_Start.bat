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

rem --- System-Python suchen (python oder py-Launcher) -------------------------
set "SYS_PY="
where python >nul 2>nul && set "SYS_PY=python"
if not defined SYS_PY (
  where py >nul 2>nul && set "SYS_PY=py -3"
)
if not defined SYS_PY (
  echo [FEHLER] Python wurde nicht gefunden.
  echo          Bitte Python 3.10 oder neuer installieren und beim Setup
  echo          die Option "Add Python to PATH" aktivieren.
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
