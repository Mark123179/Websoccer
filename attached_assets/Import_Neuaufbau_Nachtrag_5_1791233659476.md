# Import-Neuaufbau: Nachtrag 5 zur Übergabe

Stand: 05.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 4 und zu Replits „N22: Modellplan zur Freigabe"

Dieser Nachtrag entscheidet über den Modellplan. Er ändert, **wie** der Tabellenschnitt B6 gebaut wird, und hat bei Widersprüchen Vorrang vor Teil A, Teil B6, Teil C und den Nachträgen 1 bis 4. Am BVB-Referenzpaket und am Paketformat ändert er nichts.

Alle Entscheidungen hat Mark am 05.10.2026 einzeln getroffen.

## Warum

Marks Ablauf ist: BVB prüfen → Liga ausrollen → alten Stand löschen und übernehmen. Replits Modellplan stellt die neuen Modelle mit neuen Namen neben `Club`, `Player` und `Stadium`. Engine-Brücke, Taktik, Saison, Finanzen, Transfers, Scouting, Freundschaftsspiele und Stadion-Editor hängen aber an genau diesen drei Tabellen (laut T0: 244 Beziehungen, 150 Laufzeitdateien, 69 Seitenvorlagen, 85 Testdateien). Nach dem Löschen des alten Stands wäre `Player` leer und kein Spieltag spielbar, bis jedes Modul umgehängt ist. Diese Zwischenstufe steht in der Übergabe nicht und ist nicht gewollt.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N23 | **`Club`, `Player` und `Stadium` bleiben die Anker des Spiels.** Alle Module behalten ihre Beziehungen. Der Import legt Verein, Stadion und Spieler in diesen Tabellen an. Replits Modellplan vom 05.10.2026 (neue Modelle daneben, Spiel später umhängen) ist nicht freigegeben |
| N24 | **Erweitern und reparieren, neu nur was fehlt.** Was es aus B6 schon als Tabelle gibt, wird erweitert und von den in T0 gefundenen Fehlern befreit. Neue Tabellen entstehen nur, wo nichts Passendes vorhanden ist. Werte an zwei Stellen sind die Ausnahme und werden einzeln benannt |
| N25 | **Die drei Schichten aus B6 gelten als Feldliste.** Jedes Feld gehört genau einer Schicht: Echtwelt (schreibt nur der Import), Real + Sim (Import und Spiel, mit Herkunft je Zeile), Spielstand (schreibt nur das Spiel). Echtweltfelder schreibt der Import über genau einen Weg. Nach Ligastart gilt die Schreibmaske aus E37 |
| N26 | **Abnahme auf den echten Seiten.** Der Pilot lädt die App `game` vollständig. Vereinsseite, Kader, Spielerprofil und Ruhmeshalle sind die bestehenden Seiten. Neu gebaut werden nur Upload, Vorschau und Arbeitsliste im Creator. Eigene Pilot-Ansichten unter `game/import/` entfallen |
| N27 | **Der neue Modellplan kommt als Feldliste, danach ein Halt.** Gebaut wird erst nach Marks Freigabe |

## Zu N24: Ausgangsvorschlag für die Zuordnung

Von Claude aus B6 und dem T0-Bericht abgeleitet, ohne Einsicht in `game/models.py`. Replit prüft jede Zeile am Code und korrigiert sie in der Feldliste.

| B6 | Bestehend | Was zu tun ist |
|---|---|---|
| Verein | `Club`, `ClubPublicProfile` | Zustand `spielbar` / `nicht_spielbar` / `nur_verweis` ergänzen (ersetzt die Platzhalter-Kennzeichen), Spitzname und Motto ergänzen. Stadionname und Kapazität nicht mehr doppelt im Profil führen |
| Stadion | `Stadium` | Kennzeichen belegt/berechnet je Kapazität, Heimkurvenseite, Haupttribünenseite ergänzen. Ausbau, Preise und Umfeld bleiben Spielstand |
| Spieler | `Player` | Fehlende Stammdaten ergänzen. Neu am Spieler: Mannschaft (1. Mannschaft / U21), Kennzeichen Leih-Pool mit Stammverein, Leihverein, Leihende, Einzelsperre. Die Trennung nach Alter entfällt |
| Externe ID | `PlayerExternalId`, `ClubExternalId` | Status (`gefunden`, `nicht_gefunden`, `nicht_vorhanden`, `von_hand`) und „geprüft am" ergänzen, Personen als dritte Besitzerart. Getrennte ID-Räume für TM-Spieler und TM-Trainer |
| Quellwerte | `PlayerSourceRating` | Version, Prüfdatum und Rohdaten erhalten. Rohpotential bleibt leer bei „Dynamic" |
| Person | `HistoricCoach` und Rekordhalterfelder | Zu einer Personentabelle zusammenführen oder erweitern |
| Marktwertpunkt | `PlayerMarketValueSnapshot` | Kürzung auf zehn Punkte und das Überschreiben von Marktwert und Gehalt beim Speichern entfernen. Herkunft, Verein, Kennzeichen „Startwert" (N10), Originalname ohne TM-ID (N11) ergänzen |
| Transfer | `PlayerTransferHistory` | Leihkennung, Herkunft, Originalname ergänzen. Unbekannte Ablöse bleibt leer |
| Rekord | `ClubRecord` | Leerer Wert zulässig, neue Schlüssel speichern, Gegner als TM-ID plus Name |
| Titel | `ClubTrophy` (nur Zähler) | **Neu:** Einzeleinträge mit Wettbewerb, Saison, Kategorie, Herkunft. Die Anzahl wird daraus abgeleitet |
| Kader | Felder an `Player` | Kein eigenes Kader-Modell nötig, wenn Mannschaft und Leih-Pool am Spieler stehen. Replit bestätigt oder widerspricht mit Begründung |
| Paket, Arbeitsliste | nichts Passendes | **Neu** |

Werte, die voraussichtlich an zwei Stellen stehen und deshalb in der Feldliste ausdrücklich als Spiegel zu kennzeichnen sind: der aktuelle Marktwert am Spieler (abgeleitet aus dem neuesten Marktwertpunkt) und die FMI-ID an Verein und Spieler (wird vom Bildsystem gelesen).

## Zu N26: Folgen für das Pilot-Schema

- Die Tabellen im Pilot-Schema entstehen aus den echten Migrationen der App `game`, einschließlich der neuen Migration für diesen Umbau. Dieselbe Migrationsdatei läuft später live. Kein eigener Migrationsweg nur für den Pilot.
- Zeilen, die alte Datenmigrationen anlegen (Vereine, Trophäen, Demo-Leihen, Stadionwerte, Karrierestationen), werden im Pilot-Schema entfernt. Vor dem BVB-Import haben alle Vereins-, Spieler-, Stadion-, Liga-, Wettbewerbs- und Spielstandstabellen 0 Zeilen. Replit belegt das mit Zeilenzahlen.
- Die kopierten Schutzbereiche bleiben erhalten. Wie die bereits kopierten Tabellen mit den Migrationen zusammengeführt werden, entscheidet Replit und berichtet es.
- Hintergrundjobs und Zeitplaner bleiben im Pilot aus. Die Trennung nach N14 bleibt unverändert.
- Der Pilot ist danach das vollständige Spiel auf leerem Bestand. Was mit nur einem Verein nicht sinnvoll läuft (Spieltag, Liga), muss nicht laufen, darf aber keine Ersatzvereine oder alten Daten heranziehen.

## Unverändert aus T0, weiterhin zu beheben

- Ersatzstärke 50 und Ersatzfrische 100 in der Engine-Brücke dürfen einen gesperrten Spieler nicht einsetzbar machen. Er wird vorher ausgeschlossen. An der Engine selbst wird nichts geändert.
- `Player.save` darf beim Import keine Sim-Vereinsstationen anlegen.
- Abgleich nur über externe IDs, kein Namensabgleich. Die Liga „Platzhalter (Import)" entfällt.
- Drei Stellen in `stadium_editor/views.py` lösen Dortmund über FMI 907 auf statt über die Vereinsnummer 3.
- Die Stärkeformel bleibt unverändert. Es ändert sich höchstens, woher die Eingaben gelesen werden.

## Was die Feldliste nach N27 enthält

Je Feld aus B6 und aus dem BVB-Paket eine Zeile:

1. Tabelle und Spalte
2. Zustand: vorhanden, erweitert, repariert oder neu
3. Schicht und wer schreiben darf
4. Spiegel ja/nein, und wenn ja: woraus abgeleitet und über welche Funktion
5. Was nach Ligastart bei erneutem Upload geschieht (überschreiben oder unberührt)

Dazu eine kurze Liste der Tabellen und Spalten, die mit diesem Umbau wegfallen.

## Ablauf

1. Replit legt die Feldliste vor. Halt.
2. Mark gibt frei. Replit baut Modell, Migration und Pilot-Schema (Rest von T1), danach T2 bis T4.
3. Abnahme des BVB auf den echten Seiten.
4. Liga im Pilot ausrollen.
5. Live sichern, zurücksetzen, dieselben Pakete live hochladen.

Das Aufräumen doppelter Spalten folgt später Modul für Modul und hält den Spielbetrieb nicht auf.

## Freigabe

Freigegeben ist nur das Schreiben der Feldliste. Nicht freigegeben: Modelländerungen, Migrationen, Paketimport, Sicherung der Dortmund-Szene. T2–T5 bleiben gesperrt. Hetzner bleibt unberührt.
