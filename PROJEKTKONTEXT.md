# Websoccer - Projekterinnerung

## Zweck

Websoccer ist ein Django-basiertes Browsergame im Fussballmanager-Stil. Das Projekt soll schrittweise zu einer spielbaren Management-Simulation wachsen, in der Vereine, Ligen, Spieler, Kader, Staerken, Budgets und spaeter Spielbetrieb, Transfers und Entwicklungssysteme abgebildet werden.

Die klare Arbeitsrichtung ist: Entwicklung in VS Code, Umsetzung in Django, iterative Sprints zusammen mit Codex/ChatGPT.

## Tech-Stack

- Sprache: Python
- Framework: Django
- Datenbank: SQLite fuer die lokale Entwicklung
- Frontend: Django Templates mit einfachem HTML/CSS
- Externe Logo-/Icon-Quelle: `https://api.svgl.app`
- App-Struktur:
  - `core`: Django-Projektkonfiguration
  - `game`: Fachlogik fuer Websoccer-Spielinhalte
- Entwicklungsumgebung:
  - VS Code
  - lokale virtuelle Python-Umgebung `.venv`
  - Projektstart ueber `manage.py`

## Aktueller Stand

Das Projekt enthaelt bereits eine erste fachliche Basis:

- Modell `League` fuer Ligen mit Name und Land
- Modell `Club` fuer Vereine mit Name, Kurzname, Gruendungsjahr, Budget und Liga
- Modell `Player` fuer Spieler mit Name, Alter, Position, Potential, Marktwert und optionalem Verein
- Modell `PlayerStrengthProfile` fuer berechnete Spielerstaerke aus Basisstaerke und Formmodifikator
- Admin-Integration fuer Ligen, Vereine, Spieler und Staerkeprofile
- Vereinsuebersicht unter `/clubs/`
- Vereinsdetailseite unter `/clubs/<id>/` mit Kaderanzeige
- Startseite unter `/` mit Status, Kennzahlen, Finanzuebersicht und Top-Vereinen
- Gemeinsames Template `base.html` mit dunklem Layout und Navigation
- `requirements.txt` dokumentiert die lokale Django-Umgebung
- Smoke-Tests pruefen Startseite, Vereinsuebersicht und Vereinsdetailseite
- Vereine und Spieler haben eine `fm_inside_id` als stabile externe Referenz-ID fuer Daten- und Asset-Zuordnung
- Management Command `seed_reference_clubs` laedt die 1. Mannschaft von Borussia Dortmund und FC Bayern mit Transfermarkt-Marktdaten plus FMInside-IDs fuer interne Staerke-/Admin-Zuordnung

Zusaetzlich gibt es ein eigenes Arbeitsdokument fuer das geplante Spielstaerkemodell:

- `SPIELSTAERKEMODELL.md`
- `OEKONOMIE_AGENT.md` fuer Finanzlogik, Geldfluesse und Balancing
- `DATEN_UND_ASSETS.md` fuer FMInside-IDs und spaetere lokale Bildzuordnung

## Bekannte Themen

- Einige deutsche Sonderzeichen und das Euro-Zeichen sind aktuell falsch kodiert und sollten bereinigt werden.
- Vor dem naechsten technischen Sprint sollte geprueft werden, ob die virtuelle Umgebung aktiv ist und Django korrekt installiert ist.
- Tests sind aktuell als erste Smoke-Tests vorhanden, aber fachlich noch nicht tief ausgearbeitet.

## Asset-Regel

- Fuer Logos, Icons und vergleichbare externe Marken-/Symbolgrafiken immer `https://api.svgl.app` verwenden.
- Spielerbilder, Vereinswappen und eigene Websoccer-Grafiken werden spaeter lokal anders geloest und sollen vorerst nicht ueber externe Quellen fest eingebaut werden.
- Lokale Bilder sollen spaeter ueber die `fm_inside_id` von Verein oder Spieler eindeutig zugeordnet werden.

## Referenzprojekte

Als fachliche und strukturelle Vorbilder dienen:

- `https://websoccer.ch`
- `https://champions-football-manager.de`

Diese Projekte sollen nicht kopiert werden. Sie dienen als Orientierung dafuer, welche Bereiche in einem Websoccer gut funktionieren koennen und welche Workflows Manager erwarten.

Ableitbare Muster:

- umfangreiches Datencenter mit Ligen, Teams, Spielern, Tabellen, Torjaegern, Einsatzzeiten, Noten/Scores, Zweikaempfen, Paessen und Archivdaten
- klar getrennter Spielbetrieb mit Kader, Aufstellung, Spielen, Tabellen, Pokalen, internationalen Wettbewerben und Jugendbereich
- Managerbereich mit Profil, Transferbuero, Beobachtungsliste, Vereinsnews, Finanzen, Stadion, Umfeld, Trainer und Mitarbeitern
- Community-/News-Bereich mit Regeln, News, freien Vereinen, Terminkalender, Forum und Aktivitaetschecks
- Startseite mit heutigen Spielen, News, Social-/Transfermeldungen, freien Vereinen und Login
- internationale Wettbewerbe und Nationalmannschaften als spaetere Ausbauziele

Wichtig fuer unser Projekt:

- Bewaehrte Navigations- und Datenstrukturen duerfen als Inspiration dienen.
- Eigene Spielmechaniken, Staerkemodell, Manager-Sichtbarkeit und Datenquellenregeln bleiben fuehrend.
- Keine fremden Texte, Designs, Bilder, Wappen, Spielerbilder oder Datenbestaende uebernehmen.
- Spielerbilder, Vereinswappen und eigene Websoccer-Grafiken werden spaeter lokal/rechtlich sauber geloest.

## Naechste sinnvolle Sprints

1. Projekt lauffaehig absichern
   - virtuelle Umgebung aktivieren oder `.venv` verwenden
   - Django-Abhaengigkeiten ueber `requirements.txt` pflegen
   - `python manage.py check` und `python manage.py test` erfolgreich ausfuehren
   - Encoding-Probleme in Modellen und Templates bereinigen

2. Datenmodell erweitern
   - Saisonmodell
   - Spielplan und Spieltage
   - Tabellenstand
   - Spielerattribute und Staerkelogik gemaess `SPIELSTAERKEMODELL.md`
   - Spielerprofil mit Saisonstatistik, Karriere und Sim-Informationen ausbauen

3. Spielsimulation vorbereiten
   - einfache Match-Engine
   - Tore, Ergebnis, Heim-/Auswaertseffekt
   - Einfluss von Staerke, Form und Potential

4. Manager-Funktionen aufbauen
   - Vereinsseite verbessern
   - Kaderverwaltung
   - Budget- und Marktwertlogik
   - spaeter Transfers, Training und Jugendspieler

5. Oekonomie-Agent einbeziehen
   - Einnahmen und Ausgaben fuer neue Features pruefen
   - Marktwert-, Gehalts- und Budgetlogik balancieren
   - Missbrauchsmoeglichkeiten und Inflation frueh erkennen
   - Spielerlebnis zwischen Risiko, Wachstum und sportlichem Erfolg abstimmen

## Wiederverwendbarer Kontext fuer neue Codex/ChatGPT-Sprints

Dieses Projekt ist ein Django-Websoccer im Aufbau. Es soll als Fussballmanager-Browsergame entwickelt werden. Der aktuelle Stand umfasst Grundmodelle fuer Ligen, Vereine, Spieler und Spielerstaerken sowie einfache Vereinslisten- und Detailansichten. Die Entwicklung passiert lokal in VS Code mit Python/Django und SQLite. Ziel ist eine iterative Erweiterung zu einem spielbaren Manager mit Saisonbetrieb, Tabellen, Match-Simulation, Kaderverwaltung und Transfer-/Trainingssystemen. Bei neuen Aufgaben bitte vorhandene Django-Struktur respektieren und kleine, nachvollziehbare Sprints umsetzen. Bei allen Features mit Geld, Transfers, Gehaeltern, Sponsoren, Stadion, Jugend oder Training soll der Oekonomie-Agent aus `OEKONOMIE_AGENT.md` mitgedacht werden.
