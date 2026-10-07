# Import-Neuaufbau: Nachtrag 13 zur Übergabe

Stand: 07.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 12, zum Kontrollbericht `Import_BVB_Pilot_Kontrolle.md` und zu den Replit-Aufgaben #1044, #1045 und #739

Dieser Nachtrag hält die Abnahme des BVB-Pilots fest und legt fest, wie die Live-Umstellung abläuft und wie die weiteren Vereinspakete entstehen. Bei Widersprüchen hat er Vorrang vor Teil A, Teil B, Teil C und den Nachträgen 1 bis 12.

Alle Entscheidungen hat Mark am 06. und 07.10.2026 einzeln getroffen.

## Stand

- **Der BVB-Pilot ist abgenommen.** Mark hat ihn als geglückt und fertig erklärt.
- **Claudes Halt aus N61 ist aufgehoben.** Die Gegenprüfung ist abgeschlossen. Die Punkte 1 bis 15 aus Nachtrag 12 und die Reste R1 bis R4 sind im echten Pilot umgesetzt. Einzelheiten stehen im Kontrollbericht.
- Der Pilot steht auf v2. Das Paket v3 ist gebaut und geprüft, aber nirgends eingelesen.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N62 | **Die Vereinspakete entstehen im Chat.** Im Chat „Verein Import Praxis" nennt Mark einen Verein nach dem anderen, Claude liefert je Verein eine ZIP, Mark lädt sie live hoch. Das lokale Werkzeug aus E30 ist zurückgestellt |
| N63 | **CMTracker-Daten kommen je Liga in einem Lauf.** Mark führt den Abruf einmal je Liga auf dem Server aus, der Chat bedient sich für jeden Verein aus dieser einen Datei |
| N64 | **Die Umstellung kommt sofort.** Nach #1045 und #1044 stellt Mark live um. Die 18 Vereine füllt er danach nach und nach direkt live, ohne Zwischenschritt über den Pilot |
| N65 | **Sicherheitsregel für die Umstellung.** #1045 vor der Umstellung, #739 danach, Prüfung der ausgehenden Proxys auf Hetzner bei der Umstellung |
| N66 | **Der BVB wird mit v3 das erste Paket live.** Der Pilot bleibt auf v2 stehen. Die Schritte „Pilot sichern" und „v3 im Pilot hochladen" entfallen |

## Zu N62: Pakete im Chat

Ablauf je Verein:

1. Mark nennt den Verein.
2. Claude liest Transfermarkt und FMInside über Marks Chrome aus. Die Rohdatei landet in Marks Download-Ordner, Claude fragt dafür je Verein einmal um Erlaubnis.
3. Die CMTracker-Daten kommen aus der Liga-Datei nach N63.
4. Claude recherchiert Rekorde, Titel, Stadion und Farben mit Quellen.
5. Die Bauskripte erzeugen die ZIP. Claude prüft sie gegen den Paketvertrag und gibt sie aus, dazu eine kurze Liste der Lücken und Sperren.
6. Mark lädt die ZIP live über den Import-Knopf hoch.

Format: `WS_CLUB_PACKAGE`, Version 1, ZIP mit `manifest.json` und `data.json`. Maßgeblich ist der Stand des BVB-Pakets v3.

Vorarbeit von Claude, einmalig:

- **Paketvertrag** als Projektdokument: jedes Feld aus v3 mit Typ, Pflicht oder optional, erlaubten Werten und Herkunft, dazu die Vorgaben für das Werkzeug aus den Nachträgen 8, 9, 10 und 12.
- **Bauskripte für jeden Verein.** Die Skripte des BVB-Pakets tragen Name, Farben und IDs noch fest im Code.
- **Skill „Vereinspaket bauen"** mit Ablauf, Skripten und Prüfung, damit jeder Verein gleich läuft, auch wenn der Chat lang wird.

Voraussetzung bei Mark: Der PC ist mit dem Chat verbunden, Chrome läuft mit der Erweiterung, der Download-Ordner ist freigegeben.

Damit ruhen E30, E33 und E45, soweit sie das lokale Werkzeug betreffen. Die Aufteilung der Recherche (E38) und die Regeln für den Paketinhalt gelten unverändert. Das Werkzeug wird wieder Thema, wenn die regelmäßige Aktualisierung aller Spieler ansteht (E35).

## Zu N63: CMTracker je Liga

- Claude schreibt einen Befehl für den Server, der alle Vereine einer Liga in einem Lauf abholt, dazu die Nachwuchsspieler über Name und Geburtsdatum (E58).
- Der Befehl liest nur aus. Im Chat stehen keine Schlüssel.
- Mark holt die Ergebnisdatei in seinen Download-Ordner.
- Erste Liga ist die 1. Bundesliga.

## Zu N64 und N66: Umstellung

Reihenfolge. Die Einzelheiten liefert Replit mit #1044, ausgeführt wird jeder Schritt von Mark.

1. Replit schließt #1045 ab und liefert einen grünen Gesamtlauf.
2. Replit schließt #1044 ab: Sicherung und Wiederherstellungsprüfung, Reset-Vorschau mit Lösch- und Schutzliste, Anleitung für die Umschaltung.
3. Mark spielt den Stand auf den Server. Die Migrationen laufen im Altmodus, das Spiel bleibt unverändert.
4. Mark sichert die Datenbank und die Dortmund-Stadionszene und prüft die Wiederherstellung.
5. Mark sieht die Reset-Vorschau durch und gibt den Reset gesondert frei.
6. Reset. Konten, Rechte und Schutzdaten bleiben (N6, N7).
7. Mark schaltet auf den Paketmodus um. Die Bildprüfung ist live eingeschaltet (N50).
8. Mark prüft die ausgehenden Proxys nach N65.
9. Mark legt die Bundesliga an und lädt `bvb_vereinspaket_2026-10-05_v3.zip` hoch.
10. Mark kontrolliert den BVB gegen die Sollzahlen unten und prüft die Bilder.
11. Weitere Vereine folgen nach N62, in beliebiger Reihenfolge.

Zwischen Schritt 6 und dem letzten Verein ist der Live-Bestand unvollständig. Die Liga lässt sich erst starten, wenn alle 18 Vereine importiert sind und kein sperrender Eintrag offen ist.

Sollzahlen für den BVB als Erstimport live:

| Größe | Soll |
|---|---|
| Spieler | 51 (31 in der 1. Mannschaft, 19 in der U21, Benkara im Leih-Pool) |
| berechnete Stärken | 49 |
| Einzelsperren | 2 (Takato Yamamoto, Bjarki Gardarsson) |
| Arbeitsliste aus dem Paket | 128 offen (126 Info, 2 Einzelsperre), 0 sperrend, 0 erledigt |
| Marktwertpunkte | 637 (631 aus dem Paket, 6 Startwerte) |
| Transfers | 322 |
| Rekorde, Titel | 24 und 30 |
| Titel-Kacheln | 8 / 5 / 3 |
| Ø Alter Profis | 24,4 |

Fehlen live Bilddateien, kommen dafür Info-Einträge zur Arbeitsliste dazu. Sie sperren nicht (E40).

Mit N64 ist Marks frühere Reihenfolge abgelöst, nach der zuerst alle Pakete der Liga bereitliegen sollten. Mit N66 sind N60 und die Schritte 3 und 4 aus N61 abgelöst, soweit sie den Upload von v3 in den Pilot betreffen.

## Zu N65: Sicherheit

**Vor der Umstellung, #1045:**

- Alle eigenen Fehlerantworten des Moduls `game/club_import/package_views.py` gehen als reiner Text raus. Betroffen sind Vorschau und Bestätigung, die den Fehlertext bisher als HTML zurückgeben.
- Regressionstests mit HTML-Markern in Datum, Zahlenfeld, Vereinsname und Lückentext.
- Einmalige Maskierungsprüfung von Vorschau, Arbeitsliste, Ruhmeshalle und Transferhistorie, einschließlich ihrer HTML-Helfer.
- Danach ein grüner Gesamtlauf.

**Nach der Umstellung, #739:** die neun Bibliotheksmeldungen und die übrige Versionswartung, ohne Termindruck, solange kein erreichbarer Angriffsweg hinzukommt.

**Bei der Umstellung:** Mark prüft auf Hetzner ausgehende HTTPS-Proxys und abweichende Zieladressen. Gemeint ist nicht der nginx davor. Bei Abweichungen wird die Einstufung neu bewertet.

## Offen ohne Halt

- Creator → Spieler → Source zeigt Status und Prüfdatum der IDs nicht. „Nicht gefunden" und „dort nicht vorhanden" sehen beide wie „—" aus.
- Die Stärkentabelle hat nur die TM-ID. Die Spalten FMI-ID und CMTracker-ID fehlen für den Vergleich aller Spieler.

Beides hält die Umstellung nicht auf.

## Freigabe

Freigegeben: #1045 vollständig. #1044 als Vorbereitung, einschließlich Reset-Vorschau im Probelauf, Sicherungsplan für Datenbank und Dortmund-Szene und Anleitung. Claudes Vorarbeit für den Chat nach N62 und der Liga-Befehl nach N63.

Nicht freigegeben: Reset, Datenlöschung, Push, Pull, Zugriff auf Hetzner oder Umschaltung durch Replit. Jede Änderung an der Stärkeformel und an der Vereinswert-Regel. Einlesen von v3 in den Pilot.
