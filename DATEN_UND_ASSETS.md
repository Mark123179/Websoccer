# Daten- und Asset-Zuordnung

## Ziel

Vereine und Spieler brauchen stabile Referenz-IDs, damit spaeter Bilder, Wappen, Stadionbilder, Stadtbilder und weitere Medien eindeutig zugeordnet werden koennen.

Als externe Referenz-ID verwenden wir vorerst die IDs von FMInside/FMIScout-kompatiblen Football-Manager-Datenseiten. Im Code heisst dieses Feld `fm_inside_id`.

## Datenfelder

- `Club.fm_inside_id`: stabile Referenz-ID fuer einen Verein
- `Player.fm_inside_id`: stabile Referenz-ID fuer einen Spieler

Diese IDs sind nicht die internen Django-IDs. Die Django-ID darf sich durch Datenbank-Resets aendern, die `fm_inside_id` bleibt als fachliche Zuordnung stabil.

## Asset-URL-Konfiguration (produktionskritisch)

### Zwei Umgebungsvariablen — Single Source of Truth: `core/settings.py`

| Variable | Live-Server (Hetzner) | Replit-Dev (Fallback) |
|---|---|---|
| `ASSETS_BASE_URL` | `/assets/` | `/static/assets/` |
| `ASSETS_ROOT` | `/app/assets` | `<BASE_DIR>/game/static/assets` |

**Beide Variablen werden ausschließlich in `core/settings.py`** aus `os.environ` gelesen.
Alle URL-Builder in `game/asset_urls.py` greifen zur **Laufzeit** via `_base()` auf
`settings.ASSETS_BASE_URL` zu — keine Modul-Level-Konstanten, die beim Import
eingefroren werden könnten.

### Produktionskritische Server-.env-Einträge

```
ASSETS_BASE_URL=/assets/
ASSETS_ROOT=/app/assets
```

`ASSETS_ROOT=/app/assets` ist ein Bind-Mount auf Host `/var/www/assets`.
nginx serviert `/var/www/assets` unter `/assets/`.

Fehlt `ASSETS_BASE_URL` in der `.env`, liefert der Server `/static/assets/`-URLs
(→ 404 für alle Bilder, da nginx diesen Pfad nicht auf das Asset-Verzeichnis mappt).

### Architektur

```
settings.ASSETS_BASE_URL   ← os.environ.get('ASSETS_BASE_URL', '/static/assets/')
          ↓
game/asset_urls.py::_base()   ← liest settings zur Laufzeit (nie einfrieren)
          ↓
asset_url(), club_logo_url(), player_face_url(), referee_face_url(),
trophy_url(), federation_url(), competition_url(), flag_url(), …
          ↓
Templates / Views / Context-Processor
```

### Injizierte Template-Variablen (via `game.context_processors.current_manager`)

Jede Template-Response enthält:
- `{{ assets_base_url }}` — entspricht `settings.ASSETS_BASE_URL`
- `{{ default_player_url }}` — entspricht `asset_urls.default_player_url()`

JS-Globals (gesetzt in `base.html` für alle Seiten):
- `window.wsAssetsBase` — z. B. `/assets/`
- `window.wsDefaultPlayerUrl` — z. B. `/assets/players/default_player.png`

### Gespeicherte URLs in SimulatedMatch-JSON

**Regel:** Bild-URLs dürfen **nicht** aus `report_data` direkt ins Template als `src`
durchgereicht werden. Sie müssen immer frisch über `asset_urls.*` aufgelöst werden.

Hintergrund: `report_data` kann eingefrorene `/static/assets/`-URLs aus früheren
Generierungen enthalten. Im Template oder View immer `player_face_url(fm_inside_id)`
etc. aufrufen statt gespeicherte Bild-URLs aus JSON direkt als `src` zu verwenden.

## Konfigurierbare Asset-Basis-URL (Hintergrund)

Bild-Assets (Spielergesichter, Club-Logos, Trophäen usw.) werden über eine konfigurierbare Basis-URL referenziert. Die App baut die URLs als reine Strings zusammen (`game/asset_urls.py`), ohne `{% static %}`-Auflösung oder Dateisystem-Checks. Fehlt eine Datei, liefert der Webserver 404 und die UI zeigt über `onerror` einen Platzhalter.

- Entwicklung (Replit): Default `/static/assets/` → Dateien liegen unter `game/static/assets/`
- Produktion (Hetzner): `ASSETS_BASE_URL=/assets/` → nginx serviert den Host-Ordner `/var/www/assets` (Bind-Mount `/var/www/assets:/app/assets:ro`, Location `/assets/` in `nginx/default.conf.template`)

Struktur unterhalb der Basis-URL:

```text
<ASSETS_BASE_URL>
  players/
    face_<player_fm_inside_id>.png
    default_player.png
  clubs/
    logos/<club_fm_inside_id>_club.png
    stadiums/<club_fm_inside_id>_stadium.jpg
    cities/<club_fm_inside_id>.jpg
    kits/<club_fm_inside_id>_{home|away|third}.png
    jerseys/…
  referees/
    face_<fm_uid>.{png|jpg|jpeg}
    referee_default.svg
  trophies/<trophy_asset_id>.png
  competitions/<id>_comp.png
  confederations/{1-7}_conf.png
  federations/<id>_federation.png
  flags/<code>.png
  media/<slug>_media.png
  avatars/  backgrounds/  icons/
```

Beispiele (Prod):

- Borussia Dortmund: `/assets/clubs/logos/907_club.png`
- FC Bayern: `/assets/clubs/logos/915_club.png`
- Harry Kane: `/assets/players/face_28049320.png`

## Externe Logos und Icons

Fuer allgemeine Logos, Icons und Symbolgrafiken gilt weiterhin:

- immer `https://api.svgl.app` verwenden
- keine fremden Spielerbilder, Vereinswappen oder Datenbankgrafiken fest einbauen

## Wichtig fuer spaetere Sprints

- Spielerbilder, Wappen, Stadien und Stadtbilder werden lokal eingefuegt.
- Code soll spaeter nur anhand der `fm_inside_id` den erwarteten Dateipfad bauen.
- Fehlende Bilder muessen einen neutralen Platzhalter anzeigen.
- Die ersten Referenzvereine sind Borussia Dortmund und FC Bayern.

## Referenzdaten laden

Die ersten beiden Referenzvereine koennen per Management Command aus Transfermarkt- und FMInside-Daten geladen werden:

```powershell
.\.venv\Scripts\python.exe manage.py seed_reference_clubs
```

Der Befehl laedt:

- Borussia Dortmund mit Club-ID `907`
- FC Bayern Muenchen mit Club-ID `915`
- nur die Spieler der 1. Mannschaft von Transfermarkt
- Transfermarkt-ID, Transfermarkt-Profil-Link und Transfermarkt-Marktwert-Link als Rohdaten
- sichtbare Transfermarkt-Verlinkungen im Kader fuehren auf das Spielerprofil, nicht auf den Marktwertverlauf
- FMInside-ID, Rating und Potential als interne Admin-/Staerke-Daten
- Geburtstag, Alter, Nationalitaeten, Hauptposition, Nebenpositionen, Marktwert und Vertragsende
- Gehalt pro Spiel nach Startformel: `5.000 EUR je 1.000.000 EUR Marktwert`

Aktueller Umfang nach dem Seed:

- Borussia Dortmund: 26 Spieler
- FC Bayern Muenchen: 25 Spieler

Hinweis: Spielerbilder und Vereinswappen werden lokal ueber die ID-Struktur ergaenzt. Bis dahin nutzt die UI automatisch das lokale Default-Spielerbild `game/static/game/images/default_player.svg`. Dieses SVG enthaelt das urspruengliche Default-PNG auf hellem Hintergrund, damit der Platzhalter in dunklen Tabellen sichtbar bleibt.

Aktuell eingebundene Club-Wappen:

- Quelle: `C:\Users\mashu\Documents\Codex\Websoccer\Images\Logos\Europe\Germany\Clubs`
- Borussia Dortmund: `game/static/game/images/crests/907.png` aus `TCM1_907.png`
- FC Bayern Muenchen: `game/static/game/images/crests/915.png` aus `TCM1_915.png`

Der alte lokale Ordner `Images\Wappen` ist nicht mehr die Quelle. Vereinslogos werden ab jetzt aus `Images\Logos` uebernommen und ueber die `fm_inside_id` benannt. `Club.crest_static_path` erwartet entsprechend `game/images/crests/<club_fm_inside_id>.png`.

Aktuell eingebundene Wettbewerbslogos:

- Quelle national: `C:\Users\mashu\Documents\Codex\Websoccer\Images\Logos\Europe\Germany\Competitions`
- Quelle international: `C:\Users\mashu\Documents\Codex\Websoccer\Images\Logos\Others\Internationals Competitions`
- 1. Bundesliga: `game/static/game/images/competitions/bundesliga.png` aus `TCM2_22.png`
- DFB-Pokal: `game/static/game/images/competitions/dfb-pokal.png` aus `TCM2_1301410.png`
- Champions League: `game/static/game/images/competitions/champions-league.png` aus `TCM2_1301394.png`
- Supercup: `game/static/game/images/competitions/supercup.png` aus `TCM2_1301397.png`

## Flaggen

Die Nationalitaeten der Spieler haben zwei Darstellungsarten:

- kompakte Bio-/Kaderanzeige: echte Flaggen aus `game/static/game/images/flags/<nation_id>.svg`
- grosses Spielerposter: Nationalitaets-/Verbandslogo aus dem neuen Logo-Pack

```text
C:\Users\mashu\Documents\Codex\Websoccer\Images\Logos\Others\Federations\TCM4_<nation_id>.png
```

Die Verbandslogos werden im Projekt gecacht unter:

```text
game/static/game/images/nations/federations/<nation_id>.png
```

Die Nation-IDs entsprechen den Football-Manager-Nation-IDs. Beispiel: England `765`, Irland `789`, Deutschland `771`.

## Trophies

Titel und Auszeichnungen verwenden die Football-Manager-ID aus `Images\Trophies`:

```text
C:\Users\mashu\Documents\Codex\Websoccer\Images\Trophies\<trophy_asset_id>.png
```

Im Projekt werden diese Dateien gecacht unter:

```text
game/static/game/images/trophies/<trophy_asset_id>.png
```

Aktuelle Harry-Kane-Dummy-Zuordnung:

- Meisterschaft / Bundesliga-Schale: `22`
- DFB-Pokal: `1301410`
- Champions League: `1301394`
- Supercup: `1301397`

## Spielerbilder und Kits

Spielerportraits werden ueber `Player.fm_inside_id` zugeordnet:

```text
game/static/game/images/players/<player_fm_inside_id>.svg
```

Die aktuellen SVGs betten die lokalen PNG-Dateien aus `Images/Players/face_<id>.png` ein. Fehlt ein Spielerbild, nutzt die UI weiter `game/static/game/images/default_player.svg`.

Vereins-Kits werden ueber `Club.fm_inside_id` zugeordnet:

```text
game/static/game/images/kits/<club_fm_inside_id>_home.svg
game/static/game/images/kits/<club_fm_inside_id>_away.svg
game/static/game/images/kits/<club_fm_inside_id>_third.svg
```
