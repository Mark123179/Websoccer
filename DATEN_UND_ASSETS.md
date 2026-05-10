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

Hinweis: Spielerbilder und Vereinswappen werden spaeter lokal ueber die ID-Struktur ergaenzt. Bis dahin nutzt die UI automatisch das lokale Default-Spielerbild `game/static/game/images/default_player.svg`.
