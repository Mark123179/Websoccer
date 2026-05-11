# Daten- und Asset-Zuordnung

## Ziel

Vereine und Spieler brauchen stabile Referenz-IDs, damit spaeter Bilder, Wappen, Stadionbilder, Stadtbilder und weitere Medien eindeutig zugeordnet werden koennen.

Als externe Referenz-ID verwenden wir vorerst die IDs von FMInside/FMIScout-kompatiblen Football-Manager-Datenseiten. Im Code heisst dieses Feld `fm_inside_id`.

## Datenfelder

- `Club.fm_inside_id`: stabile Referenz-ID fuer einen Verein
- `Player.fm_inside_id`: stabile Referenz-ID fuer einen Spieler

Diese IDs sind nicht die internen Django-IDs. Die Django-ID darf sich durch Datenbank-Resets aendern, die `fm_inside_id` bleibt als fachliche Zuordnung stabil.

## Geplante lokale Asset-Struktur

Die Bilddateien werden spaeter lokal abgelegt. Die Zuordnung soll ueber die `fm_inside_id` erfolgen:

```text
assets/
  clubs/
    <club_fm_inside_id>/
      crest.png
      stadium.jpg
      city.jpg
  players/
    <player_fm_inside_id>/
      portrait.png
```

Beispiele:

- Borussia Dortmund: `assets/clubs/907/crest.png`
- FC Bayern: `assets/clubs/915/crest.png`
- Harry Kane: `assets/players/28049320/portrait.png`

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

Aktuell eingebundene Wappen:

- Borussia Dortmund: `game/static/game/images/crests/907.svg`
- FC Bayern Muenchen: `game/static/game/images/crests/915.svg`

Die aktuellen Wappen-SVGs sind Wrapper um die vorhandenen PNG-Dateien mit `180x180` Pixeln. Sie lassen sich im Code sauber wie SVG-Assets verwenden, sind aber noch keine echten Vektorpfade. Fuer sehr grosse Darstellungen oder perfekt scharfe Skalierung sollten spaeter echte SVG-Wappen oder groessere Originaldateien pro Verein ergaenzt werden.

## Flaggen

Die Nationalitaeten der Spieler werden in der UI als lokale Flaggenbilder angezeigt. Fuer die aktuell genutzten Nationen liegen SVG-Wrapper unter `game/static/game/images/flags/<nation_id>.svg`.

Die Nation-IDs entsprechen den Football-Manager-Nation-IDs aus den lokalen Flaggen-Dateien. Die SVGs betten die vorhandenen PNGs aus `Images/Flaggen` ein. Der lokale Ordner `Images/Nationen` enthaelt Nationenlogos und wird nicht fuer die Spieler-Nationalitaeten verwendet.

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
