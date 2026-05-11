# Websoccer Design System

## Richtung

Websoccer soll sich wie ein modernes Football-Manager-Command-Center anfühlen: dunkel, fokussiert, datenstark und visuell nah am Stadion. Die Oberfläche orientiert sich an modernen Sport-Dashboards, nicht an Landingpages.

Der Look kombiniert:

- dunkle App-Shell mit linker Navigation
- Stadion- und Flutlichtgefühl durch CSS-Hintergründe
- Glas-Panels mit dünnen Cyan-Linien
- grüne Pitch- und Fitness-Akzente
- echte lokale Assets: Wappen, Spielerbilder, Flaggen, Kits
- dichte Managerdaten, aber klar scanbar

## Tokens

- `--app-bg`: `#03070c`
- `--stadium-bg`: `#07111a`
- `--panel`: `rgba(9, 23, 34, 0.82)`
- `--panel-strong`: `rgba(12, 31, 45, 0.94)`
- `--panel-soft`: `rgba(17, 43, 58, 0.72)`
- `--line`: `rgba(44, 231, 255, 0.18)`
- `--line-strong`: `rgba(44, 231, 255, 0.38)`
- `--cyan`: `#22e6ff`
- `--green`: `#30f29c`
- `--yellow`: `#ffd166`
- `--red`: `#ff5570`
- `--text`: `#f4fbff`
- `--muted`: `rgba(244, 251, 255, 0.64)`
- `--faint`: `rgba(244, 251, 255, 0.38)`
- `--radius`: `8px`

## Komponenten

- Sidebar: fixe linke Navigation mit WebSoccer-Brand, aktiver Cyan-Kante und Managerbox.
- Page Shell: `start-dashboard`, `club-dashboard`, `list-dashboard` und `player-dashboard` nutzen dieselbe dunkle Stadionfläche, denselben Grid-Hintergrund und dieselben Laptop-/Desktop-Breakpoints.
- Topbar: `app-topbar`, `home-topbar` und `page-topbar` nutzen dasselbe Raster aus Kontext, Suche, Statusicons, Datum und Primäraktion.
- Dashboard-Card: dunkles Glas-Panel mit 8px Radius, dünner Cyan-Linie und sanftem Schatten.
- KPI-Card: kompakte Kennzahlenkarte mit kleinem Uppercase-Label und großem Cyan-Wert.
- Vereinsübersicht: Wappen, Liga, Kaderwert, Budget, Moral und Form.
- Vereinsliste: Clubdatenbank mit denselben Tabellen-, KPI- und Radar-Mustern wie die Startseite.
- Spielerprofil: Spieler-Hero, Sim-Kontext, KPI-Leiste, Profilinformationen und Stärkeprofil im gleichen Dashboard-System.
- Match Center: VS-Karte, letztes Spiel und Spielvorschau.
- Ligatabelle: kompakt, aktuelle Zeile hervorgehoben.
- Kaderübersicht: Mini-Tabelle mit Spielerbild, Stärke und Fitness.
- Taktik: dunkle Pitch-Card mit Formation und Spielstil.
- Transfermarkt: Spieler-Cards mit Bild, Alter, Position und Marktwert.
- Finanzen: Kennzahlen plus einfache Chart-Visualisierung.

## Regeln

- Keine hellen Standard-Dashboardflächen für den Hauptscreen.
- Keine Marketing-Hero-Sektion. Der erste Screen muss direkt nutzbar sein.
- Keine verschachtelten Cards.
- Blau/Cyan ist Funktionslicht, nicht bloße Dekoration.
- Grün wird für Fitness, Pitch, Form und positive Sportwerte verwendet.
- Tabellen bleiben kompakt, bekommen aber moderne Zeilen, Bildspalten und Position-Badges.
- Alle Fußballassets bleiben lokal und werden über IDs zugeordnet.
