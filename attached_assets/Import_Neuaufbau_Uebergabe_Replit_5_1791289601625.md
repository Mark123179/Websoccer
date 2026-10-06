# Import-Neuaufbau: Übergabe an Replit

Stand: 05.10.2026 · Projekt: Websoccer / BLUEPRINT (playwebsoccer.de) · Autor: Mark mit Claude

Diese Datei enthält drei Teile: die **Arbeitsanweisung** (Teil A), die **Entscheidungen** mit Regeln und Format (Teil B) und den **Gesprächsverlauf** des Interviews (Teil C). Bei Widersprüchen gilt Teil B.

Das **BVB-Referenzpaket** (`manifest.json` + `data.json`) wird getrennt nachgeliefert. Es ist die verbindliche Formatvorlage. Wo diese Datei und das Paket voneinander abweichen, gilt das Paket, und die Abweichung wird Mark gemeldet.

---

# Teil A · Arbeitsanweisung

## A1 Ziel

Vereine und Spieler kommen künftig über genau einen Weg ins Spiel: ein Vereinspaket je Verein, das im Creator hochgeladen wird. Dafür werden Datenmodell und Import neu gebaut. Erste Stufe ist der Pilot mit Borussia Dortmund in einer **frischen, leeren Datenbank in Replit**.

## A2 Rahmen, der nicht verhandelbar ist

1. **Hetzner bleibt unberührt.** Bis Mark den Pilot abgenommen hat, wird auf dem Live-Server nichts migriert, zurückgesetzt oder deployed, was das Datenmodell betrifft.
2. **Frische Datenbank in Replit.** Keine Migration der alten 26 Vereine und 515 Spieler. Kein Überführen von Spielstand.
3. **Match Engine V2 ist eingefroren** (`.agents/memory/match-engine-v2-freeze.md`). Keine Konstante, Formel oder Gewichtung ändern. Die Engine bekommt dieselben Eingaben wie bisher, nur aus neuen Tabellen.
4. **Nicht löschen, nicht umbauen:** Schiedsrichter (463), Nationen, Sponsoren (~500), Benutzerkonten, Forum.
5. **NULL bleibt NULL, niemals 0.** Fehlende Werte werden nie geschätzt oder ersetzt.
6. **Kein Scraping auf dem Server.**
7. **Geschrieben wird ganz oder gar nicht** (eine Transaktion je Paket). Ein zweiter Upload desselben Pakets ändert nichts.
8. Erst prüfen, dann fragen: `.agents/memory/` und die bestehenden Module lesen, bevor Rückfragen an Mark gehen.

## A3 Reihenfolge der Tickets

Jedes Ticket endet mit einem kurzen Bericht an Mark. **T0 ist ein Halt:** erst nach Marks Freigabe geht es weiter.

### T0 · Auswirkungsanalyse (kein Code)

Der Tabellenschnitt in B6 ersetzt `Club`, `ClubPublicProfile`, `Stadium`, `Player`, `PlayerSourceRating`, `PlayerExternalId`, `ClubExternalId`, `ClubRecord`, `PlayerMarketValueSnapshot`, `PlayerTransferHistory` und verwandte Modelle. Praktisch jedes Modul liest daraus.

Lieferung:
- Liste aller Module, die Vereins-, Stadion- oder Spielerfelder lesen oder schreiben, mit Dateipfad
- je Modul: welche Felder, und wohin sie im neuen Schnitt wandern
- Vorschlag für die Reihenfolge der Umstellung und für das, was für den Pilot zwingend laufen muss (siehe A4) und was danach folgt
- alle Blocker und offenen Fragen, ausdrücklich markiert

**Halt. Bericht an Mark, auf Freigabe warten.**

### T1 · Neues Datenmodell

- Tabellen nach B6 anlegen, in einer frischen Datenbank
- Stärkeberechnung (`strength_service`, `PlayerStrengthProfile`) an die neuen Quellwerte anschließen, ohne die Formel zu ändern
- Gehalt je Spieler berechnen: `Marktwert / 1.000.000 × 5.000 €` pro Pflichtspiel, Marktwert NULL → Gehalt NULL und Eintrag auf der Arbeitsliste
- Vereine haben drei Zustände (siehe B11): `spielbar`, `nicht_spielbar` (voll importiert, Spieler bilden den Scouting-Pool) und `nur_verweis` (nur Name und TM-ID, z. B. aus der Transferhistorie). Die Liga „Platzhalter (Import)" entfällt
- Ligen tragen das Kennzeichen spielbar / nicht spielbar
- Kaderzugehörigkeit je Spieler: 1. Mannschaft oder U21 (B11)

### T2 · Paket einlesen

- Paket prüfen: Formatversion, Prüfsumme, Pflichtfelder, Summe der zwölf Stadionwerte = Gesamtkapazität, höchstens 3 HP und 3 NP, dritte Position nur ROV/ROM/LOV/LOM
- Import-Dienst: Vollanlage vor Ligastart, eingeschränkter Modus nach Ligastart (B4, E37)
- Abgleich bestehender Spieler und Vereine nur über externe IDs (TM-ID zuerst, dann FMI-ID). Kein Abgleich über Namen
- Jeder Import legt eine Paket-Zeile an (Datei, Prüfsumme, Erhebungstag, Quellversionen, Zeitpunkt, Benutzer)

### T3 · Creator: Upload, Vorschau, Arbeitsliste

- Upload → automatische Prüfung → **Vorschau** (Verein, Anzahl Spieler, Leihspieler, Lücken, fehlende Bilder) → Zielliga wählen → **Bestätigen**
- Ligen werden von Hand im Creator angelegt, nicht aus dem Paket
- **Arbeitsliste** je Liga und Verein, getrennt nach „sperrt" und „Info", mit Erledigt-Status. Nacharbeit direkt aus der Liste (ID oder Wert eintragen)
- **Ligastart-Sperre:** Eine Liga lässt sich nicht starten, solange sperrende Einträge offen sind
- Bildprüfung: je Verein, Spieler und Rekordhalter prüfen, ob die erwartete Datei unter `ASSETS_ROOT` liegt. Fehlende Bilder → Info-Eintrag

### T4 · Anzeige für den Pilot

Die Seiten, die die Abnahme in A4 braucht, lesen aus dem neuen Modell: Vereinsseite, Stadion-Kapazitäten, Kader, Spielerprofil (Marktwertgraph, Transferhistorie), Ruhmeshalle.

### T5 · Reset-Befehl (nur bauen und in Replit testen)

Management-Befehl mit Probelauf-Modus, der auf einem Bestandssystem alles nach B1 (E03, E04) leert und Schiedsrichter, Nationen, Sponsoren, Konten und Forum unangetastet lässt. Dazu Export und Wiederanhängen der Dortmund-Szene über FMI-ID 907 (E41). **Nicht auf Hetzner ausführen.**

### Zweite Stufe (nach bestandenem Pilot, eigener Auftrag)

Lokales Werkzeug (E30, E33), Server-Durchreiche für CMTracker und API-Football, fester Recherche-Auftrag, spielerbezogenes Aktualisierungs-Paket (E35), jährliches Rekord-Update (E22), Entfernen aller alten Importwege (E49).

Mit dem Jugendmodul (eigener Auftrag): Spieler-Antrag mit Warteschlange und Sammelpaket (E51, E60, E61, E63), Anzeige und Aufstellung der U21, Aufrück-Automatik bei über 3 Mio. € (E52).

## A4 Abnahme des Pilots (Mark klickt selbst durch)

1. Upload zeigt eine Vorschau und schreibt erst nach Bestätigung.
2. Vereinsseite zeigt Stammdaten, Farben, Spitzname und Stadion mit zwölf Kapazitäten.
3. Kader vollständig laut Transfermarkt, Leihspieler richtig zugeordnet, Rückennummern und Positionen nach Regel.
4. Ein Spielerprofil zeigt Marktwertgraph und Transferhistorie, neueste oben, fremde Vereine mit leerem Wappen.
5. Grundstärke ist für jeden Spieler aus beiden Quellen berechnet.
6. Ruhmeshalle zeigt die echten Rekorde und Titel.
7. Arbeitsliste zeigt alle Lücken, sperrende und nicht sperrende getrennt.
8. Ein zweiter Upload desselben Pakets ändert nichts.
9. 20 U21-Spieler sind vorhanden, erfüllen Alters- und Marktwertgrenze und den Positionsschlüssel 2-6-7-5; Gems sind mit Begründung gekennzeichnet. Sichtbar und aufstellbar werden sie erst mit dem Jugendmodul.

## A5 Agent-Einstellung je Ticket

| Ticket | Modus | Modell | Aufwand |
|---|---|---|---|
| T0 Auswirkungsanalyse | Power | stärkstes verfügbares | hoch |
| T1 Datenmodell | Power | stärkstes verfügbares | hoch |
| T2 Paket einlesen | Power | stärkstes verfügbares | mittel bis hoch |
| T3 Creator | Economy | Standard | mittel |
| T4 Anzeige | Economy | Standard | mittel |
| T5 Reset-Befehl | Power | stärkstes verfügbares | hoch |

---

# Teil B · Entscheidungen, Regeln, Format

## B1 Grundsatz

| # | Entscheidung |
|---|---|
| E01 | Neues Format von Grund auf, kein Aufsatz auf `WS_CLUB_IMPORT_V2` |
| E02 | Neubau reicht bis ins Datenmodell |
| E03 | Kompletter Reset, keine Migration des Bestands |
| E04 | Geleert werden Vereine, Spieler, Stadien, Spielstand, Ligen und Wettbewerbe. Es bleiben Schiedsrichter, Nationen, Sponsoren, Benutzerkonten, Forum |
| E05 | Ligen werden von Hand im Creator angelegt, beim Upload wird die Zielliga gewählt |
| E41 | Von den Gestaltungsdaten wird nur die Dortmund-Szene gerettet und über FMI-ID 907 wieder angehängt |

## B2 Identität und Lücken

| # | Entscheidung |
|---|---|
| E06 | FMI-, Transfermarkt- und CMTracker-ID sind Pflicht. FMI und CMTracker liefern die Grundstärke. API-Football dient der Vollberechnung (RL-Form) |
| E07 | Lücken arbeitet Mark händisch nach |
| E08 | Der Import läuft trotz Lücken. Lücken landen auf der Arbeitsliste im Creator. Der Ligastart ist gesperrt, solange sperrende Lücken offen sind |
| E40 | **Sperrt:** fehlende FMI-, TM- oder CMTracker-Zuordnung eines Spielers der 1. Mannschaft. **Sperrt nie:** fehlende API-Football-Zuordnung, fehlende Rekorde, fehlende Bilder. **Ergänzt durch E58/E59:** CMTracker „dort nicht vorhanden" ist keine Lücke; Nachwuchsspieler ohne FMInside sind einzeln gesperrt, sperren aber nicht die Liga |
| E31 | Bilder liegen bereits auf dem Server und sind nicht Teil des Pakets. Der Import prüft nur, ob sie da sind |

Erwartete Bildpfade unter `ASSETS_ROOT`, Schlüssel ist immer die FMI-ID:
`clubs/logos/{id}_club.png` · `clubs/stadiums/{id}_stadium.jpg` · `clubs/cities/{id}.jpg` · `clubs/kits/{id}_{home|away|third}.png` · `players/face_{id}.png`

## B3 Kader und Spieler

| # | Entscheidung |
|---|---|
| E09 | Der Kader ist der Transfermarkt-Kader am Erhebungstag |
| E10 | Ein Leihspieler spielt beim Leihverein. Der Stammverein bleibt Eigentümer. Rückkehr zum Saisonende. Ist der Leihverein nicht im Spiel, ist der Spieler bis Saisonende abwesend. **Präzisiert durch E68:** Er liegt solange im Leih-Pool |
| E11 | Positionen aus Transfermarkt-Einsätzen. Höchstens 2 HP und 2 NP. Eine dritte Stelle gibt es nur als Zwischenposition |
| E65 | Für die Positionsregel zählen **nur die Einsätze der letzten drei Saisons: die laufende plus die zwei davor** (am 05.10.2026 also 2026/27, 2025/26, 2024/25). Das Fenster wandert jede Saison weiter. Schwellen bleiben 25 und 10 |
| E12 | Mischfall (eine HP, eine NP des Paares) ergibt die Zwischenposition als 3. NP |
| E13 | Kein Vertrags-Feature. Rückennummer aus Transfermarkt. Gehalt: 1 Mio. € Marktwert = 5.000 € pro Pflichtspiel, berechnet der Server |
| E14 | Kein Startbudget im Import, das kommt im Finanz-Feature |
| E27 | Kompletter Transfermarkt-Marktwertverlauf je Spieler |
| E28 | Komplette Transfermarkt-Transferhistorie. Keine Leistungsdaten, Statistiken starten mit dem Sim-Start bei 0 |
| E29 | API-Football: Abgleich über Name und Geburtsdatum, keine Rückennummer als Abgleichsmerkmal. **Geändert durch E50:** nicht beim Erstimport |
| E50 | API-Football wird beim Erstimport **ausgelassen**. Der Free-Plan gibt nur die Saisons 2022 bis 2024 frei, also weder aktuelle Formwerte noch Geburtsdaten des heutigen Kaders. Die Zuordnung wird für alle Vereine in einem Durchgang nachgeholt, sobald der bezahlte Plan aktiv ist. Bis dahin steht sie je Spieler als nicht sperrender Eintrag auf der Arbeitsliste |
| E34 | FMInside und CMTracker: immer die neueste Version am Erhebungstag, je Spieler gespeichert |

### Positionsregel im Detail

Interne Kennungen: `TW IV LV RV DM ZM LM RM OM LF RF ST` und die Zwischenpositionen `LOV ROV LOM ROM`. Marks „RA/LA" entspricht intern `RF/LF`.

1. Gezählt werden die Transfermarkt-Einsätze je Position aus der laufenden Saison und den zwei Saisons davor (E65), ältere Einsätze zählen nicht. Ab 25 Einsätzen Hauptposition, ab 10 Einsätzen Nebenposition. Je höchstens 2, die mit den meisten Einsätzen.
2. Mindestens eine Hauptposition. Fehlt sie, gilt die meistgespielte Position, bei Spielern ohne Einsätze die Transfermarkt-Profilposition.
3. Zwischenpositionen:

| Paar | ergibt |
|---|---|
| RV + RM | ROV |
| RM + RF | ROM |
| LV + LM | LOV |
| LM + LF | LOM |

- beide Positionen des Paares sind HP → Zwischenposition als **3. HP**
- beide sind NP → Zwischenposition als **3. NP**
- eine HP, eine NP → Zwischenposition als **3. NP**

4. Andere dritte Positionen gibt es nicht. Unbekannte Transfermarkt-Bezeichnungen werden gemeldet, nie geraten.

### Transferhistorie in der Anzeige

Neueste oben. Vereine, die nicht im Spiel sind, erscheinen mit Namen und leerem Wappen. Intern verweisen sie über die TM-ID auf eine Vereinszeile im Zustand `nur_verweis` oder `nicht_spielbar`. Wird der Verein später importiert, greifen Verlinkung und Wappen ohne Nacharbeit. Transfers im Spiel werden mit Herkunft `sim` oben angefügt.

## B4 Stadion und Vereinsfelder

| # | Entscheidung |
|---|---|
| E24 | Zwölf Kapazitäten (Nord/Ost/Süd/West × Steh/Sitz/VIP) im Stufenmodell, jede Zahl mit Kennzeichen `belegt` oder `berechnet`. Summe = nationale Gesamtkapazität. Himmelsrichtung real laut Karte |
| E25 | Verteilregel: bestehende Anteile, auf die echte Lage gedreht |
| E26 | Ticketpreise, Ausbaustufen und Rasenqualität sind Spielstand und nicht im Paket |
| E32 | Zusätzlich im Paket: Vereinsfarben, Spitzname, Motto |
| E37 | Upload mit Vorschau und Bestätigung. Erneuter Upload ist immer erlaubt. Vor Ligastart ersetzt er alle Echtweltdaten. Nach Ligastart schreibt er nur Stammdaten, Stadionname, Rekorde und Titel. Kader und Spielstand bleiben unberührt |

### Stufenmodell und Verteilregel im Detail

Das Paket liefert die zwölf Werte fertig. Der Server prüft nur die Summe und übernimmt. Die Regel steht hier, damit Werkzeug und Server dieselbe Rechnung kennen.

- **Stufe 1:** Zahlen je Tribüne sind belegt → übernehmen, Kennzeichen `belegt`.
- **Stufe 2:** Nur die Summen Steh, Sitz, VIP sind belegt. Steh: 80 % Heimkurve, 20 % Gegenkurve. VIP: 100 % Haupttribüne. Sitz nach den Sitzanteilen der Profile unten, auf 100 % normiert. Kennzeichen `berechnet`.
- **Stufe 3:** Nur die Gesamtkapazität ist belegt. Verteilung nach den Profilen. Kennzeichen `berechnet`.

Profile (aus `club_reconcile.STADIUM_STAND_RATIOS`, Summe 100 %):

| Profil | Steh | Sitz | VIP |
|---|---|---|---|
| Heimkurve | 17,5 % | 7,5 % | 0 |
| Gegenkurve (gegenüber der Heimkurve) | 3,75 % | 21,25 % | 0 |
| Haupttribüne | 0 | 20,5 % | 4,5 % |
| Gegengerade (gegenüber der Haupttribüne) | 0 | 25 % | 0 |

Die Profile werden auf die reale Seite der Heimkurve und der Haupttribüne gelegt. Rundungsrest geht auf die Sitzplätze der Gegengerade. Reine Sitzplatzstadien haben 0 Stehplätze als belegten Wert. Liegen Heimkurve und Haupttribüne laut Recherche nicht auf benachbarten Seiten, gilt die bisherige Lage (Heimkurve Nord, Haupttribüne West) und es entsteht ein Info-Eintrag.

## B5 Rekorde und Titel

| # | Entscheidung |
|---|---|
| E15 | Alle Pflichtspiele zählen gleich (Liga, Pokal, Europa) |
| E16 | Quelle: Transfermarkt zuerst, Wikipedia nur als Lückenfüller. Quelle und Prüfdatum je Rekord |
| E17 | Fünf Rekorde bleiben Liga-Rekorde: beste Saison, schlechteste Saison, meiste Tore je Saison, wenigste Gegentore je Saison, bester Punkteschnitt als Trainer (ab 30 Ligaspielen). Punkte auf die 3-Punkte-Regel umgerechnet |
| E18 | Schnellstes Tor ist gestrichen. Neue Datenrekorde: jüngster eingesetzter Spieler, längste Siegesserie als Trainer, internationale Pokale. „Meiste Spieler des Spiels" entsteht nur im Spiel und hat keinen Echtwert. Die neuen Rekorde kommen in die Datenbank, auch wenn die Ruhmeshalle sie noch nicht zeigt |
| E19 | Nicht belegbar → leer mit Vermerk „nicht belegt" und wo gesucht wurde. Info-Eintrag, sperrt nicht |
| E20 | Rekordhalter: Name, TM-Personen-ID, Nation. Hat die Person eine FMI-ID, bekommt sie automatisch das Bild `players/face_{id}.png`. Sonst bleibt das Bild offen |
| E21 | Titel als Einzeleinträge mit Wettbewerb und Saison in vier Kategorien. Herkunft `real` oder `sim`. Die Anzahl ist die Summe |
| E22 | Jährliches Rekord-Update je Verein für Bestwerte. Keine realen Titel nach dem Schnitt. Liegt ein neuer Echtwert über dem Spielrekord, zählt der Echtwert |
| E23 | Titel bis Saisonende 2025/26. Alles andere mit Stand des Erhebungstags |

Rekordschlüssel (bestehende aus `game/records/registry.py`, neue fett):

- Spieler: `top_scorer`, `top_assists`, `most_apps_field`, `most_apps_gk`, `most_titles_player`, `highest_market_value`, **`youngest_player`**, **`most_motm`** (nur sim)
- Trainer: `longest_tenure`, `most_matches_coach`, `most_titles_coach`, `best_ppg_coach`, `most_wins_coach`, **`longest_win_streak_coach`**
- Verein: `biggest_win`, `biggest_defeat`, `longest_win_streak`, `longest_unbeaten`, `longest_winless`, `best_season`, `worst_season`, `most_goals_season`, `fewest_conceded_season`, `record_signing`, `record_sale`
- Titelzähler werden aus den Titel-Einträgen berechnet: Meisterschaften, nationale Pokale, **internationale Pokale**, unterklassig/Aufstieg

Titelkategorien: `championship` (höchste Spielklasse) · `national_cup` (Pokal, Supercup, Ligapokal, in England entsprechend mehr Wettbewerbe) · `international_cup` · `lower_tier` (unterklassige Meisterschaften und Aufstiege, zählen nicht als Meisterschaft).

## B6 Tabellenschnitt (E43)

**Echtwelt** (schreibt nur der Import)

| Tabelle | Inhalt |
|---|---|
| Verein | Name, Kurzname, Gründungsjahr, Stadt, Land, Lat/Lng, Farben, Spitzname, Motto, Zustand `spielbar` / `nicht_spielbar` / `nur_verweis` |
| Stadion | Name, Ort, zwölf Kapazitäten mit je einem Kennzeichen belegt/berechnet, Heimkurvenseite, Haupttribünenseite |
| Spieler | Nachname, Vorname, Künstlername, Geburtsdatum, Nationen, Größe, Fuß, HP/NP, Stammverein, Leihstatus |
| Externe ID | gehört zu Verein, Spieler oder Person · Quelle (FMI, TM, CMTRACKER, API_FOOTBALL) · Wert · Status · geprüft am |
| Quellwerte | Spieler, Quelle, Version, Rating, Potential, Einzelattribute |
| Person | Rekordhalter: Name, Nation |

**Real + Sim** (Import und Spiel schreiben, jede Zeile trägt die Herkunft)

| Tabelle | Inhalt |
|---|---|
| Marktwertpunkt | Spieler, Datum, Wert, Verein |
| Transfer | Spieler, Datum, von, nach, Ablöse, Leihe |
| Rekord | Verein, Schlüssel, Wert, Halter, Datum, Zeitraum, Gegner, Saison, Wettbewerb, Quelle |
| Titel | Verein, Wettbewerb, Saison, Kategorie |

**Spielstand** (schreibt nur das Spiel)

Kader (Spieler, aktueller Verein, Mannschaft 1. Mannschaft/U21, Rückennummer, Gehalt, Einzelsperre, Kennzeichen Leih-Pool mit Stammverein, Leihverein und Leihende), Stadion-Ausbau (Ausbauten, Preise, Umfeld), Stärkeprofil, Finanzen, Spiele, Saison. Später mit dem Jugendmodul: Spieler-Antrag (Manager, TM-Link, Stand, Ablehnungsgrund).

**Import**

Paket (Datei, Prüfsumme, Erhebungstag, Quellversionen, Zeitpunkt) und Arbeitsliste (was fehlt, bei wem, sperrt ja/nein, erledigt).

Status einer externen ID: `gefunden` · `nicht_gefunden` (Lücke, bei FMI/TM/CMTRACKER sperrend) · `nicht_vorhanden` (nachweislich nicht in der Quelle, mit Prüfdatum; nur für CMTracker zulässig, sperrt nicht, E58) · `von_hand` (Mark hat nachgetragen).

Die Rückennummer aus dem Paket ist ein Startwert: Sie wird nur bei der Erstanlage in den Kader geschrieben und gehört danach dem Spielstand.

## B7 Paketformat (E36)

Ein ZIP mit zwei Dateien. Verbindlich wird die Struktur mit dem BVB-Referenzpaket; dies ist der abgestimmte Entwurf.

**`manifest.json`**

```json
{
  "format": "WS_CLUB_PACKAGE",
  "format_version": 1,
  "package_type": "club",
  "club": {"fmi_id": 907, "tm_id": 16, "name": "Borussia Dortmund"},
  "collected_at": "2026-10-06",
  "titles_through_season": "2025/26",
  "source_versions": {"fminside": "…", "cmtracker_db": "…", "api_football_season": null},
  "counts": {"players": 0, "loaned_out": 0, "records": 0, "titles": 0,
             "gaps_blocking": 0, "gaps_info": 0},
  "data_sha256": "…"
}
```

`package_type` ist für später reserviert: `player_update` (E35) und `record_update` (E22).

**`data.json`**, oberste Ebene: `club`, `stadium`, `players`, `persons`, `records`, `titles`, `gaps`.

```json
{
  "club": {
    "name": "", "short_name": "", "founded_year": 0,
    "city": "", "country": "", "lat": 0.0, "lng": 0.0,
    "colors": {"primary": "#000000", "secondary": "#000000", "tertiary": null},
    "nickname": "", "motto": "",
    "ids": {"fmi": {"value": 907, "status": "gefunden", "checked_at": ""},
            "tm": {}, "cmtracker": {}, "api_football": {}},
    "sources": [{"field": "colors", "name": "wikipedia", "url": "", "checked_at": ""}]
  },
  "stadium": {
    "name": "", "city": "", "capacity_national": 0,
    "home_end": "S", "main_stand": "W",
    "stands": {
      "N": {"standing": {"value": 0, "basis": "belegt"},
            "seating":  {"value": 0, "basis": "belegt"},
            "vip":      {"value": 0, "basis": "berechnet"}},
      "E": {}, "S": {}, "W": {}
    },
    "tier": 1,
    "sources": [{"name": "", "url": "", "checked_at": ""}]
  },
  "players": [{
    "ids": {"fmi": {}, "tm": {}, "cmtracker": {}, "api_football": {}},
    "last_name": "", "first_name": "", "display_name": "",
    "date_of_birth": "YYYY-MM-DD",
    "nationalities": ["", ""], "height_cm": 0, "foot": "R",
    "squad": {"team": "first | u21",
              "status": "first_team | loaned_in | loaned_out",
              "owner_club": {"tm_id": 0, "name": ""},
              "loan_club": null, "shirt_number": 0},
    "positions": {"main": ["RV", "RM", "ROV"], "secondary": [],
                  "method": "appearances | profile",
                  "seasons": ["2024/25", "2025/26", "2026/27"],
                  "appearances": [{"tm_position": "", "code": "RV", "count": 0}]},
    "market_value_eur": 0,
    "market_values": [{"date": "", "value_eur": 0, "club": {"tm_id": 0, "name": ""}}],
    "transfers": [{"date": "", "season": "", "from": {"tm_id": 0, "name": ""},
                   "to": {"tm_id": 0, "name": ""}, "fee_eur": null,
                   "fee_text": "", "is_loan": false}],
    "ratings": {
      "fminside":  {"version": "", "url": "", "rating": 0, "potential": 0, "raw": {}},
      "cmtracker": {"db": "", "rating": 0, "potential": 0, "raw": {}}
    },
    "api_football": null
  }],
  "persons": [{"ref": "p1", "name": "", "nationality": "", "tm_id": 0, "fmi_id": null}],
  "records": [{
    "key": "top_scorer", "origin": "real", "basis": "all_competitive | league",
    "status": "belegt | nicht_belegt",
    "value_numeric": 0, "value_display": "",
    "holder": {"person_ref": "p1"},
    "opponent": null, "date": null, "period_from": null, "period_to": null,
    "season": "", "competition": "", "context": "",
    "sources": [{"name": "transfermarkt", "url": "", "checked_at": ""}],
    "searched": []
  }],
  "titles": [{"competition": {"name": "", "fm_id": null, "category": "national_cup"},
              "season": "2020/21", "origin": "real", "source_url": ""}],
  "gaps": [{"entity": "player | club | record | image", "ref": "",
            "field": "", "severity": "blocking | info", "note": ""}]
}
```

Hinweise:
- `ratings.*.raw` enthält die Attribute mit den Namen der Quelle. Die Zuordnung auf die internen Attribute macht der Server über die bestehenden Tabellen (`FMI_ATTR_MAP`, `FMI_GK_MAP`, CMTracker-Zuordnung aus `docs/cmtracker_integration.md`). So bleibt das Paket ein unverfälschter Abzug der Quelle.
- Fehlende Werte sind `null`, nie `0` und nie leerer Text.
- `api_football` ist im Erstimport `null` und die ID hat den Status `nicht_gefunden` (E50). Die Felder bleiben im Format, damit die spätere Zuordnung ohne Formatänderung möglich ist: `{"player_id", "team_id", "team_name", "league_id", "season"}`.
- Geld in ganzen Euro, Datum als `YYYY-MM-DD`.
- Nachwuchsspieler stehen in derselben `players`-Liste mit `squad.team = "u21"`. Gems tragen zusätzlich `"gem": {"criteria": ["talent_list | early_value | youth_international"], "sources": [{"name": "", "url": "", "checked_at": ""}]}`, Auffüller `"gem": null`.
- Im Manifest unter `counts` zusätzlich `"u21": 20` und `"gems": 0`.
- `competition.fm_id` ist die FM-Wettbewerbs-ID, über die das Trophäenbild `trophies/{id}.png` gefunden wird.

## B8 Werkzeug, Recherche, Aktualisierung (zweite Stufe)

| # | Entscheidung |
|---|---|
| E30 | Ein lokales Werkzeug auf Marks PC baut das komplette Paket. Es liest Transfermarkt und FMInside im Browser und holt CMTracker und API-Football über eine geschützte Durchreiche des Servers (der CMTracker-Schlüssel ist an die Hetzner-IP gebunden) |
| E33 | Neues Werkzeug. Die Lese-Bausteine für TM und FMInside aus `tools/cfm_importer/` werden übernommen. Auftrags-API und Kandidaten-Kontrolle entfallen |
| E38 | Das Werkzeug liest alle festen TM-Tabellen (Rekordspieler, Rekordtorschützen, Trainerhistorie, Transferrekorde, Erfolge). Claude recherchiert den Rest und liefert je Verein eine Datei mit Quelle zu jedem Wert |
| E35 | Aktualisierung spielerbezogen: Der Server gibt die Spielerliste mit IDs aus, das Werkzeug liest Attribute und Marktwert neu. Geschrieben werden nur Attribute, Marktwert und neue Verlaufspunkte |
| E49 | Nach bestandenem Pilot werden alle alten Importwege entfernt: V2-ZIP, Vereins-CSV, FM-ID-CSV, CMTracker/SoFIFA-CSV, Auftrags-API, Seed-Befehle. Die API-Anbindungen `game/cmtracker_api.py` und `game/api_football.py` bleiben |

## B9 Reihenfolge und Lieferung

| # | Entscheidung |
|---|---|
| E39 | Pilot nur BVB, danach 1. Bundesliga, danach Liga für Liga |
| E44 | Erste Lieferung: komplettes BVB-Paket und diese Übergabedatei |
| E45 | Claude baut das BVB-Referenzpaket. Das Werkzeug gilt als fertig, wenn es dasselbe Paket selbst erzeugt |
| E46 | CMTracker-Rohdaten für BVB holt Mark mit einem vorbereiteten Befehlsblock auf dem Server (erledigt am 05.10.2026: Datenbank `26091500`, 34 Spieler). API-Football entfällt für den Erstimport (E50) |
| E47 | Testumgebung ist Replit mit frischer, leerer Datenbank |
| E42 | Live-Reset nach bestandenem Pilot: sichern (Datenbank-Dump und Dortmund-Szene), zurücksetzen, Liga Verein für Verein direkt live befüllen |
| E48 | Abnahme nach den acht Punkten in A4 |

## B11 Nachwuchs, Scouting-Pool, Spieler-Antrag (Nachtrag vom 05.10.2026)

| # | Entscheidung |
|---|---|
| E51 | Jedes Vereinspaket bringt einen **U21-Startkader mit genau 20 Spielern** mit. Zuerst die Gems, dann wird aufgefüllt. Weitere Spieler kommen später per Spieler-Antrag |
| E52 | **U21-Regel:** höchstens 21 Jahre und höchstens 3 Mio. € Marktwert. Ein Nachwuchsspieler über 3 Mio. € wird erstellt und in die 1. Mannschaft gestellt. Steigt ein U21-Spieler während der Saison über 3 Mio. €, spielt er die Sim-Saison in der U21 zu Ende und muss vor der neuen Saison hoch. Die Automatik dafür baut Mark mit dem Jugendmodul |
| E53 | Auch **nicht spielbare Ligen** (z. B. Belgien) bekommen **volle Vereinspakete**. Es gibt spielbare und nicht spielbare Ligen |
| E54 | Die Spieler nicht spielbarer Vereine **sind der Scouting-Pool** und ersetzen die erfundenen Platzhalter (`POOLSEED-…`). Bestehende Scouting-Regeln gelten unverändert (Land ab 50 Spielern scoutbar, Top-Stars/Top-Talente reserviert, Geld verlässt das Spiel). Der echte Verein bleibt als Herkunft, der Wechsel steht als Spiel-Eintrag in der Transferhistorie |
| E55 | **Mindestalter 16** am Erhebungstag. Jüngere werden nicht erstellt, weder im Startkader noch als Gem noch per Antrag |
| E56 | **Gem** ist ein Nachwuchsspieler des Vereins ab 16, der mindestens eines erfüllt: steht auf einer anerkannten Talentliste (Golden-Boy-Auswahl, Guardian Next Generation, Wonderkid-Liste des Football Manager) · hat mit höchstens 18 Jahren mindestens 1 Mio. € Transfermarkt-Marktwert · ist Junioren-Nationalspieler mit Profieinsatz (Definition in E69). Quelle je Gem. Keine eigene Obergrenze, begrenzt nur durch die 20 Plätze |
| E57 | **Auffüllen nach Positionsschlüssel 2-6-7-5** (Tor, Abwehr, Mittelfeld, Angriff). Gems und doppelt geführte Spieler (E66) besetzen ihre Positionen zuerst. Freie Plätze je Gruppe füllt die höchste Nachwuchsmannschaft (U23, sonst U19), danach die U19, jeweils nach höchstem Marktwert, ersatzweise nach Einsatzminuten der laufenden Saison. Für Auffüller gilt immer: 16 bis 21 Jahre, höchstens 3 Mio. €, nicht im Profikader geführt |
| E58 | **Nur-FM-Spieler:** Findet das Werkzeug einen Spieler bei CMTracker über Name + Geburtsdatum nachweislich nicht, setzt es selbst den Status `nicht_vorhanden` mit Prüfdatum. Die Grundstärke kommt dann allein aus FMInside, es entsteht kein sperrender Eintrag. Nur unklare Fälle (mehrere mögliche Treffer) gehen an Mark. Taucht der Spieler später auf, holt ihn die Aktualisierung nach |
| E59 | **Ohne FMInside:** Beim Auffüllen wird so ein Spieler übersprungen und der nächste Kandidat genommen. Ein Gem oder beantragter Spieler ohne FMInside wird erstellt, ist aber **einzeln gesperrt** (nicht aufstellbar, nicht transferierbar), bis Werte vorliegen. Die Liga sperrt er nicht |
| E60 | **Spieler-Antrag nur für den eigenen Verein.** Der Manager reicht einen Transfermarkt-Link ein. Geprüft wird automatisch, ob der aktuelle Verein laut TM der eigene ist, egal auf welcher Ebene (1. Mannschaft, U23, 2. Mannschaft, U19, U17, weitere Jugend). Ein verliehener Spieler kann nur vom Stammverein beantragt werden und folgt dann der Leihregel E10. Ablehnung automatisch mit Grund |
| E61 | **Keine eigene U21-Kadergrenze.** Es gilt die Kadergrenze des gesamten Vereins aus dem Vereinsumfeld (laut Mark 60 auf Stufe 0, in T0 zu bestätigen). Ein Antrag geht nur durch, wenn ein Platz frei ist |
| E62 | Auch **nicht spielbare Vereine bekommen den vollen 20er-Kader** |
| E63 | Anträge werden im **Sammellauf** bearbeitet, den Mark startet, wann er will: Das Werkzeug holt alle offenen Anträge, prüft, erhebt und baut ein Sammelpaket, das Mark mit einem Klick bestätigt. Der Manager sieht den Stand (eingereicht, in Bearbeitung, erstellt, abgelehnt mit Grund) und wird benachrichtigt |
| E64 | Der **U21-Startkader gehört ins BVB-Referenzpaket** (neunter Abnahmepunkt). Der Spieler-Antrag wird mit dem Jugendmodul gebaut, nicht im Pilot |
| E66 | **Doppelt geführte Spieler:** Wer bei Transfermarkt im Profikader und zugleich in einem Nachwuchskader steht und die U21-Grenzen erfüllt (höchstens 21 Jahre, höchstens 3 Mio. €), gehört in die **U21**. Diese Spieler **zählen zu den 20 Plätzen und sind gesetzt wie die Gems**: Sie besetzen ihre Positionen im Schlüssel zuerst, aufgefüllt wird nur der Rest |
| E67 | **Leihspieler im Nachwuchskader** zählen als Auffüller, behandelt wie in der 1. Mannschaft (E10): Ein in die Nachwuchsmannschaft geliehener Spieler spielt in der U21 des Leihvereins, der Stammverein bleibt Eigentümer, Rückkehr zum Saisonende. Beispiel BVB II: Takato Yamamoto (von Gamba Osaka) und Daniel Sumbu (von Sturm Graz II), beide bis 30.06.2027 geliehen |
| E68 | **Verliehene Spieler und der Leih-Pool:** Ein an einen anderen Verein verliehener Spieler wird erstellt und kommt in einen eigenen **Leih-Pool**. Wird der Leihverein später angelegt, wandert der Spieler aus dem Pool dorthin (und spielt dort nach E10). Wird der Leihverein nie angelegt, kehrt er am Saisonende zum Stammverein zurück. Gilt für Nachwuchs und 1. Mannschaft gleich. Der Leih-Pool ist kein Teil des Scouting-Pools, dort ist niemand zu haben. **Verliehene Nachwuchsspieler zählen zu den 20 Plätzen** des U21-Startkaders. Beispiel: Elias Benkara (BVB II, bis 30.06.2027 an Greuther Fürth verliehen) |
| E69 | **Profieinsatz** im Gem-Kriterium heißt: mindestens ein **Pflichtspiel für eine 1. Mannschaft**. Einsätze für eine zweite Mannschaft oder Nachwuchsmannschaft zählen nicht, auch wenn sie in einer Profi- oder Regionalliga spielt (BVB II in der Regionalliga West zählt also nicht) |

Positionsgruppen für den Schlüssel: Tor = `TW` · Abwehr = `IV LV RV LOV ROV` · Mittelfeld = `DM ZM LM RM OM LOM ROM` · Angriff = `LF RF ST`. Maßgeblich ist die Hauptposition 1.

Reichen die Kandidaten einer Positionsgruppe nicht aus (zu wenige Spieler mit FMInside-Eintrag innerhalb der Grenzen), bleibt der Platz leer und es entsteht ein Info-Eintrag auf der Arbeitsliste. Plätze werden nicht mit Spielern anderer Gruppen aufgefüllt.

Der Positionsschlüssel gilt nur für das Auffüllen. Gesetzte Spieler (Gems, doppelt geführte) bleiben immer im Kader, auch wenn sie eine Positionsgruppe über ihren Anteil hinaus besetzen; aufgefüllt wird dann nur in den Gruppen, die noch unter ihrem Anteil liegen, bis 20 erreicht sind. Sind mehr als 20 Spieler gesetzt, bleiben alle gesetzt und es wird nicht aufgefüllt. Verliehene Nachwuchsspieler (E68) nehmen wie die geliehenen (E67) als Auffüller an der Auswahl teil, also nach Positionsschlüssel und Marktwert. (Die drei letzten Sätze sind Annahmen aus der Sitzung vom 05.10.2026 und von Mark noch nicht ausdrücklich bestätigt.)

## B10 Offene Prüfpunkte

- API-Football (geprüft am 05.10.2026): Der Free-Plan gibt nur die Saisons 2022 bis 2024 frei. Der Kader-Abruf `/players/squads` funktioniert, liefert aber kein Geburtsdatum. Die Zuordnung folgt mit dem bezahlten Plan (E50).
- Football Manager 27 erscheint laut Ankündigung ab 10.11.2026, EA FC 27 ist veröffentlicht. Vereine, die vor und nach einem Versionswechsel importiert werden, haben verschiedene Datenstände, bis die erste Aktualisierung läuft (Folge von E34).
- Nach dem Live-Reset neu aufzubauen, nicht Teil dieses Auftrags: Scouting-Pool, Finanz-Kalibrierung, Gegenprüfung der 50-Saisons-Baseline mit dem neuen Datenbestand.

---

# Teil C · Gesprächsverlauf

Interview vom 05.10.2026. Je Frage: Claudes Empfehlung und Marks Entscheidung.

| # | Frage | Empfehlung | Marks Entscheidung |
|---|---|---|---|
| 1 | Basis des Pakets | V3 auf V2 aufbauen | Neues Format von Grund auf |
| 2 | Wie weit reicht „von Grund auf" | Format und Parser neu, Schreibregeln bleiben | Bis ins Datenmodell |
| 3 | Was passiert mit dem Bestand | IDs und Stärkeprofil bleiben als Anker | Kompletter Reset |
| 4 | Tiefe des Resets | Vereinsdaten weg, Weltdaten und Ligen bleiben | Wie empfohlen, aber Ligen auch neu |
| 5 | Wie entstehen Ligen | Eigenes Liga-Paket, Verweis per FM-ID | Von Hand im Creator |
| 6 | Pflicht-Schlüssel | FMI und TM Pflicht, Rest optional | FMI, TM und CMTracker nötig, API-Football für die Vollberechnung eigentlich auch |
| 7 | Spieler fehlt in einer Quelle | Status „existiert dort nicht", Spieler kommt rein | „Die muss ich dann händisch nacharbeiten" |
| 8 | Ort der Nacharbeit | Import läuft, Arbeitsliste im Creator, Ligastart gesperrt | Wie empfohlen |
| 9 | Kaderquelle | FM-Export, nur 1. Mannschaft | Transfermarkt-Kader zum Stichtag |
| 10 | Leihspieler | Spielt beim Leihverein, kehrt zurück | Wie empfohlen |
| 11 | Positionsquelle | FMInside-Eignung | Transfermarkt wie bisher, nur 2 HP und 2 NP, dritte Stelle nur als Zwischenposition |
| 12 | Mischfall HP + NP | 3. NP | Wie empfohlen |
| 13 | Vertrag, Nummer, Gehalt | Vertrag und Nummer aus TM, Gehalt rechnet der Server | Kein Vertrags-Feature, Nummer aus TM, Gehalt 5.000 € je 1 Mio. € pro Pflichtspiel |
| 14 | Startbudget | Server rechnet aus Kader-Marktwert | Kein Startbudget, kommt im Finanz-Feature |
| 15 | Welche Spiele zählen für Rekorde | Personen alle Pflichtspiele, Mannschaft nur Liga | Alle Pflichtspiele gleich, dazu „jüngster eingesetzter Spieler" |
| 16 | Rekordquelle im Konfliktfall | TM zuerst, Wikipedia füllt und korrigiert Altfälle | TM zuerst, Wikipedia nur als Lückenfüller |
| 17 | Saisonrekorde | Fünf bleiben Liga-Rekorde | Wie empfohlen |
| 18 | Fünf neue Rekorde | Alle fünf, „Spieler des Spiels" nur aus dem Spiel | Schnellstes Tor gestrichen, die anderen in die Datenbank, „Spieler des Spiels" nur aus dem Spiel |
| 19 | Rekord nicht belegbar | Leer mit Vermerk, sperrt nichts | Wie empfohlen |
| 20 | Daten zum Rekordhalter | Name, TM-ID, Nation, Bild optional | Zusätzlich FMInside prüfen, mit ID automatisch ein Bild, sonst CutOuts später |
| 21 | Detailtiefe der Titel | Einzeleinträge mit Saison, vier Kategorien | Einzeleinträge mit Herkunft real/sim; Hinweise auf Schnitt nach 2025/26, England, jährliche Nachrecherche |
| 22 | Umfang der jährlichen Nachrecherche | Nur Bestwerte, keine neuen Titel | Titel nicht, aber Ergebnisse, Transfers, Trainerrekorde, Tore, Einsätze, Marktwert |
| 23 | Stichtage | Titel bis 2025/26, alles andere 30.09.2026 | Titel bis Saisonende 2025/26, alles andere Stand des Erhebungstags |
| 24 | Herkunft der Tribünenzahlen | Stufenmodell mit Kennzeichen | Wie empfohlen |
| 25 | Feste Verteilregel | Bestehende Anteile, auf echte Lage gedreht | Wie empfohlen |
| 26 | Stadion-Startwerte | Nicht im Paket | Wie empfohlen |
| 27 | Tiefe des Marktwertverlaufs | Kompletter TM-Verlauf | Wie empfohlen |
| 28 | Karrieredaten | Transferhistorie und Leistungsdaten | Nur Transferhistorie, Leistungsdaten nein, Start bei 0 |
| 29 | API-Football im Paket | Nur IDs und Zuordnung | Einmaliger Abruf beim Import über Name und Geburtsdatum; Transferhistorie neueste oben, fremde Vereine mit leerem Wappen und späterer Verlinkung |
| 30 | Wer baut das Paket | Lokales Werkzeug, Claude liefert Recherche | Wie empfohlen |
| 31 | Bilder im Paket | Ja | Bilder sind schon auf dem Server, Arbeitsliste für Fehlendes |
| 32 | Zusätzliche Vereinsfelder | Farben und Rivalen | Farben, Spitzname und Motto |
| 33 | Bestehender CFM-Importer | Neues Werkzeug, Lese-Bausteine übernehmen | Wie empfohlen |
| 34 | Datenstand der Attribute | Feste Version für alle | Immer die neueste Version am Erhebungstag |
| 35 | Aktualisierung nach dem Start | Spielerbezogenes Aktualisierungs-Paket | Wie empfohlen |
| 36 | Aufbau des Pakets | Mischform CSV und JSON | Alles in einer JSON-Datei |
| 37 | Upload-Ablauf | Vorschau und Bestätigen, nach Ligastart gesperrt | Vorschau und Bestätigen, immer erlaubt |
| 38 | Aufteilung der Recherche | Werkzeug liest TM-Tabellen, Claude den Rest | Wie empfohlen |
| 39 | Reihenfolge | Pilot mit BVB und kleinem Verein | Pilot nur BVB, dann 1. Bundesliga |
| 40 | Sperrt eine API-Football-Lücke | Erst bei aktiver RL-Kopplung | Sperrt nicht; Free-Requests reichen für den Erstimport |
| 41 | Gestaltungsdaten beim Reset | Alles exportieren und über FMI-ID wieder anhängen | Nur die Dortmund-Szene retten |
| 42 | Zeitpunkt des Live-Resets | Wenn die Liga bereitliegt | Nach bestandenem Pilot |
| 43 | Tabellenschnitt | Wie vorgeschlagen | Wie empfohlen |
| 44 | Umfang der ersten Lieferung | Bis BVB-Pilot, Updates danach | Komplett BVB, dazu separate Datei mit Verlauf, Entscheidungen und Anweisung an Replit |
| 45 | Wer erzeugt das BVB-Paket | Claude baut das Referenzpaket | Wie empfohlen |
| 46 | CMTracker- und API-Rohdaten | Befehlsblock für den Server | Wie empfohlen |
| 47 | Was ist der Testserver | Replit mit frischer, leerer Datenbank | Wie empfohlen |
| 48 | Abnahme des Pilots | Acht Punkte | Wie empfohlen |
| 49 | Alte Importwege | Nach bestandenem Pilot entfernen | Wie empfohlen |
| 50 | API-Football im Free-Plan (Nachtrag nach dem Server-Abruf) | Beim Erstimport auslassen, mit bezahltem Plan nachholen | Wie empfohlen |
| 51 | Wie kommt Nachwuchs für die U21 ins Spiel | Antrag per TM-Link; im zweiten Anlauf: Startkader aus der höchsten Nachwuchsmannschaft, Rest per Antrag mit Sammelfreigabe | Startkader ja, dazu Recherche nach Gems; U21 nur bis 3 Mio. € Marktwert; Hinweis auf Scouting in nicht spielbaren Ligen |
| 52 | Bedeutung der 3-Mio.-Grenze | Spielberechtigung der U21, darüber 1. Mannschaft, sofortiges Aufrücken | Erstellen und in die 1. Mannschaft schieben; wer in der Saison darüber steigt, spielt sie zu Ende und muss vor der neuen Saison hoch (Automatik baut Mark) |
| 53 | Spieler aus nicht spielbaren Ligen fürs Scouting | Pool-Paket je Liga, nur Spieler | Volle Vereinspakete auch für diese Ligen |
| 54 | Behandlung dieser Spieler | Nicht spielbare Vereine sind der Scouting-Pool | Wie empfohlen |
| 55 | Wer gilt als Gem (unterbrochen) | Feste Kriterien, höchstens fünf je Verein | Zwischenruf: Mindestalter 16; Kriterien gut, aber es muss auf 20 Spieler aufgefüllt werden |
| 56 | Wie wird auf 20 aufgefüllt | Gems zuerst, dann Positionsschlüssel 2-6-7-5 | Wie empfohlen |
| 57 | Nachwuchs ohne CMTracker | Status automatisch, Stärke nur aus FMInside | Wie empfohlen |
| 58 | Nachwuchs ohne FMInside | Auffüller überspringen, Gems und Anträge einzeln sperren | Wie empfohlen |
| 59 | Wen darf ein Manager beantragen | Jeder beantragbar, landet beim echten Verein | Nur eigener Nachwuchs beantragbar |
| 60 | Obergrenze für die U21 | U21-Kader höchstens 25 | Keine eigene Grenze; die Kadergrenze des Vereins aus dem Vereinsumfeld gilt (vermutlich 60 auf Stufe 0) |
| 61 | Prüfung des Antrags | Automatisch über Transfermarkt, nur Nachwuchsmannschaften | Automatisch: aktueller Verein ist der eigene, egal welche Ebene; Leihstatus beachten, verliehene Spieler nur vom Stammverein |
| 62 | Nachwuchs bei nicht spielbaren Vereinen | Nur 1. Mannschaft und Gems | Auch dort der volle 20er-Kader |
| 63 | Rhythmus der Antragsbearbeitung | Sammellauf einmal pro Woche | Sammellauf, wann Mark will |
| 64 | U21 im BVB-Pilot | Startkader ins BVB-Paket, Antrag später | Wie empfohlen |
| 65 | Welche Einsätze zählen für die Positionsregel (Nachtrag aus der Paket-Sitzung) | Laufende Saison plus zwei davor | Nur die letzten drei Saisons; laufende plus zwei davor |
| 66 | Spieler, die im Profikader und in einem Nachwuchskader stehen und die U21-Grenzen erfüllen (Nachtrag aus der Paket-Sitzung) | In die U21; zählen zu den 20 und sind gesetzt wie Gems | Wie empfohlen |
| 67 | Zählen Leihspieler im Nachwuchskader als Auffüller (Nachtrag aus der Paket-Sitzung) | Ja, wie in der 1. Mannschaft | Ja, wie in der 1. Mannschaft |
| 68 | Was passiert mit verliehenen Nachwuchsspielern (Nachtrag aus der Paket-Sitzung); Folgefrage: zählen sie zu den 20 | Zur Folgefrage: zählen nicht zu den 20, kommen obendrauf | Erstellen, eigener Pool; wird der Leihverein angelegt, wandert der Spieler dorthin, sonst Rückkehr am Saisonende zum Stammverein. Zählen zu den 20 |
| 69 | Was zählt als Profieinsatz im Gem-Kriterium (Nachtrag aus der Paket-Sitzung) | Pflichtspiel für eine 1. Mannschaft | Pflichtspiel für eine 1. Mannschaft |

Abschluss: Mark hat das gemeinsame Verständnis am 05.10.2026 bestätigt. Frage 50 kam am selben Tag nach dem ersten Server-Abruf dazu, die Fragen 51 bis 64 (Nachwuchs, Scouting-Pool, Spieler-Antrag) ebenfalls am 05.10.2026. Die Entscheidungsnummern E51 bis E64 in B11 sind nach Thema geordnet und entsprechen nicht eins zu eins den Fragenummern.
