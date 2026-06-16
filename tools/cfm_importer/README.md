# CFM-Importer (lokales Windows-Tool)

Eigenständiges Werkzeug, das **lokal auf einem Windows-PC** läuft, einen
sichtbaren Microsoft Edge öffnet (Playwright, persistentes Profil),
**Transfermarkt**, **FMInside** und **SoFIFA** ausliest und die **Rohdaten**
über die geschützte Token-API an den Creator-Mode des Websoccer-Servers
überträgt.

> Es findet **kein Scraping auf dem Server** statt. Das Tool berechnet **keine
> finalen Attribute** und importiert **keine Bilder** — das übernimmt die
> serverseitige Engine. Die Server-Datenbank ist maßgeblich; lokale Dateien
> dienen nur der Wiederaufnahme.

---

## 1. Voraussetzungen

- Windows 10/11
- **Microsoft Edge** (vorinstalliert)
- **Python 3.10 oder neuer** — beim Setup „Add Python to PATH" aktivieren
- Internetzugang zum Server und zu den Quellseiten

## 2. Installation & Start

1. Diesen Ordner (`tools/cfm_importer/`) auf den Windows-PC kopieren.
2. **`CFM_Importer_Start.bat` doppelklicken.** Beim ersten Start:
   - legt das Skript eine virtuelle Umgebung `.venv/` an,
   - installiert die Abhängigkeiten aus `requirements.txt`,
   - kopiert `config.example.json` → `config.json` und öffnet sie im Editor.
3. In `config.json` eintragen:
   - `api_base_url` — URL des Servers (z. B. `https://dein-repl.replit.app`)
   - `api_token` — Wert des Server-Secrets `CFM_IMPORTER_TOKEN`
   - Speichern, Editor schließen — das Tool startet automatisch.

Bei weiteren Starts genügt ein Doppelklick auf die BAT.

> **Edge-Treiber:** Über den Kanal `msedge` nutzt Playwright das installierte
> Edge direkt. Sollte Edge nicht gefunden werden, einmalig in der `.venv`
> `python -m playwright install msedge` ausführen.

## 3. Konfiguration (`config.json`)

| Feld | Bedeutung |
|------|-----------|
| `api_base_url` | Basis-URL des Servers (ohne abschließenden `/`). |
| `api_token` | Bearer-Token (= Secret `CFM_IMPORTER_TOKEN`). **Geheim halten.** |
| `browser_channel` | Browser-Kanal, Standard `msedge`. |
| `headless` | `false` = sichtbarer Browser (empfohlen). |
| `user_data_dir` | Profilordner (`edge_import_profile/`) für dauerhafte Cookies/Logins. |
| `heartbeat_seconds` | Abstand der Lease-Heartbeats (Standard 25 s). |
| `pauses` | Wartezeiten in ms (`page_load_ms`, `between_actions_ms`, `between_players_ms`). |
| `request` | HTTP-Verhalten (`timeout_seconds`, `max_retries`, `backoff_base_seconds`). |

## 4. Ablauf

1. **Verbindung & Token** werden geprüft.
2. Der **nächste offene Auftrag** wird geholt und angezeigt. Vor dem Start fragt
   das Tool nach (`--yes` überspringt die Rückfrage).
3. Der Auftrag wird **exklusiv übernommen** (Lease-Token).
4. Die **Kaderseite** wird über **Vereins-ID + Saison-ID** geöffnet (kein fest
   verdrahteter Slug). Alle Spieler werden gesammelt (dedupliziert über die
   TM-ID), die Gesamtzahl gemeldet.
5. Pro Spieler werden **Stammdaten**, **Positionsdaten**, **Leihsituation** sowie
   **FMInside-** und **SoFIFA-Rohwerte** erfasst und **nach jedem Spieler**
   übertragen. Fortschritt/Heartbeats gehen laufend an den Server.
6. Nach dem letzten Spieler wird der Auftrag **abgeschlossen** und steht im
   Creator-Mode **zur Kontrolle** bereit.

## 5. Robustheit

- Einzelne **Parser-/Seitenfehler** überspringen den Spieler mit konkreter
  Meldung — es werden **keine Leerwerte erfunden**.
- **Navigation** wird bei Timeout, HTTP 5xx und Blockaden (403/429) bis zu
  `request.nav_retries`-mal mit exponentiellem Backoff wiederholt; HTTP 404/410
  überspringt den Spieler sofort (kein Raten).
- **Cloudflare-/Captcha-Challenges** werden erkannt. Das Tool wartet zunächst bis
  zu `request.challenge_wait_seconds` auf die automatische Auflösung. Gelingt das
  nicht und läuft ein **sichtbarer** Browser (`headless: false`) mit
  `manual_unblock: true`, kann die Challenge **im Fenster von Hand gelöst** und
  der Lauf per **ENTER** fortgesetzt werden. Erst danach gilt eine Quelle als
  blockiert. Tipp: einmalig im selben Edge-Profil `https://sofifa.com` öffnen und
  die Challenge lösen — der Freigabe-Cookie bleibt im Profil erhalten.
- **Fehlendes SoFIFA/FMInside** bleibt unkritisch und wird zur **manuellen
  Nachpflege** in der Kontrollphase markiert.
- **API-Probleme** werden mit exponentiellem Backoff erneut versucht;
  Auth-/Lease-Fehler brechen sofort ab.

## 6. Wiederaufnahme

Bei Abbruch merkt sich das Tool die bereits übertragenen TM-IDs in
`state/job_<id>.json`. Ein erneuter Start desselben Auftrags überspringt diese
Spieler. Zusätzlich verhindert der serverseitige Upsert (je `job + tm_player_id`)
Doppelungen.

## 7. Protokolle

Tägliche Logdateien liegen unter `logs/` (`cfm_importer.log`, datiert rotiert,
30 Tage). **Tokens und Cookies werden niemals protokolliert** (der Token wird in
jeder Zeile maskiert).

## 8. Nicht eingecheckt (`.gitignore`)

`config.json`, `edge_import_profile/`, `logs/`, `state/`, `.venv/` bleiben lokal.

## 9. Kommandozeile

```
python -m cfm_importer            # mit Rückfrage
python -m cfm_importer --yes      # Auftrag direkt starten
python -m cfm_importer --version
```

## 10. Verzeichnisstruktur

```
tools/cfm_importer/
├─ CFM_Importer_Start.bat     # Einrichtung + Start (Windows)
├─ config.example.json        # Vorlage (echte config.json wird nicht eingecheckt)
├─ requirements.txt
├─ README.md
└─ cfm_importer/
   ├─ __main__.py             # Einstiegspunkt
   ├─ config.py               # Konfiguration laden/prüfen
   ├─ logging_setup.py        # tägliche Logs ohne Secrets
   ├─ api_client.py           # Token-API-Client (Backoff, Lease)
   ├─ state.py                # Wiederaufnahme
   ├─ positions.py            # TM-Positions-Mapping (Server-Spiegel)
   ├─ normalize.py            # Namensnormalisierung (Server-Spiegel)
   ├─ browser.py              # persistenter Edge-Kontext
   ├─ runner.py               # Ablaufsteuerung
   └─ adapters/
      ├─ base.py              # gemeinsame Helfer
      ├─ transfermarkt.py     # Kader, Stammdaten, Positionen, Leihe
      ├─ fminside.py          # FMInside-Match + Rohwerte
      └─ sofifa.py            # SoFIFA-Match + Rohwerte
```
