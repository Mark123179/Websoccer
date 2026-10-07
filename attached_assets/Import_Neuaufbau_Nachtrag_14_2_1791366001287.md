# Import-Neuaufbau: Nachtrag 14 zur Übergabe

Stand: 07.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 13 und zum Paketvertrag `Import_Paketvertrag.md`

Dieser Nachtrag legt fest, wie die Pakete der weiteren Vereine mit fünf Fällen umgehen, die beim BVB nicht vorkamen. Für Replit folgt daraus genau eine Änderung an der Paketprüfung. Bei Widersprüchen hat er Vorrang vor Teil A, Teil B, Teil C und den Nachträgen 1 bis 13.

Alle Entscheidungen hat Mark am 07.10.2026 einzeln getroffen.

## Anlass

Die Bauskripte für jeden Verein sind fertig und am BVB geprüft (Stand unten). Beim Abgleich mit `game/club_import/package_validation.py` sind fünf Fälle aufgefallen, in denen der Server ein Paket ablehnt oder die Übergabe nichts regelt. Beim BVB trat keiner davon auf.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N67 | **Profi ohne FMInside: Einzelsperre statt Ligasperre.** Ein Spieler der 1. Mannschaft ohne FMInside-Eintrag wird angelegt und ist einzeln gesperrt, wie ein Gem ohne FMInside (E59). Die Liga sperrt er nicht. Das Paket liefert dafür eine Lücke `player_lock`, nie `blocking`. Ändert E40 |
| N68 | **E58 gilt auch für die 1. Mannschaft.** Steht ein Profi nachweislich nicht in CMTracker, bekommt er den Status `nicht_vorhanden` mit Nachweis. Die Stärke kommt allein aus FMInside, es gibt keine Sperre und keine Lücke |
| N69 | **Spieler mit nur einem Namen bekommen den bürgerlichen Namen.** `first_name` ist das erste Wort des vollen Namens bei Transfermarkt, `last_name` der Rest, `display_name` der Künstlername. Je Spieler entsteht ein Info-Eintrag |
| N70 | **Leihe ohne Leihende: Saisonende.** Nennt Transfermarkt kein Leihende, trägt das Paket den 30.06. der laufenden Saison ein und legt einen Info-Eintrag an |
| N71 | **Vereins-ID im Marktwertverlauf aus der Transferhistorie.** Fehlt bei einem Marktwertpunkt die TM-ID des Vereins, kommt sie vom Verein, bei dem der Spieler laut seiner eigenen Transferhistorie an dem Tag war, und nur wenn der Name dazu passt. Was nicht eindeutig ist, bleibt ohne ID |

## Auftrag an Replit

### Die eine Änderung (zu N68)

`package_validation.py` verlangt heute für jeden Spieler der 1. Mannschaft ohne CMTracker-ID eine Lücke `player_lock`, auch wenn der Status `nicht_vorhanden` ist. Das widerspricht E58 und N48.

Neu:

- Ist `ids.cmtracker.status` = `nicht_vorhanden`, verlangt die Prüfung keine Einzelsperre, in keiner Mannschaft.
- Ist der Status `nicht_gefunden`, bleibt alles wie heute: ohne `player_lock` wird das Paket abgelehnt.

Tests dazu:

1. Profi mit FMInside und CMTracker `nicht_vorhanden` samt Nachweis, ohne Lücke: Paket wird angenommen, Spieler ist nicht gesperrt, die Stärke stammt allein aus FMInside.
2. Profi mit CMTracker `nicht_gefunden` ohne `player_lock`: Paket wird abgelehnt, wie heute.
3. Profi ohne FMInside mit `player_lock` (N67): Paket wird angenommen, Spieler ist gesperrt, der Ligastart ist nicht gesperrt.
4. Die Vorschau zeigt in Fall 1 keine Sperre und in Fall 3 genau eine.

Nach dem Lesen des Codes rechnen Vorschau und Sperrableitung (`prospective_locks`, `lock_reasons`) schon richtig, weil sie nur auf `nicht_gefunden` reagieren. Replit bestätigt das im Bericht oder nennt die Abweichung.

### Zu prüfen, ohne Änderung

- **Zu N67:** Der Ligastart ist damit nur noch durch Einträge der Schwere `blocking` gesperrt. Die entstehen allein auf dem Server, bei einem ID-Konflikt des Vereins. Replit bestätigt, dass es keinen anderen Weg gibt, auf dem ein Paket einen sperrenden Eintrag erzeugt.
- **Zu N69:** Replit nennt alle Stellen im Paketmodus, die statt `display_name` den Vor- oder Nachnamen zeigen (Listen, Aufstellung, Ticker, Suche). Dort stünde bei solchen Spielern der bürgerliche Name. Ob und wo das geändert wird, entscheidet Mark nach der Liste.
- **Zu N70 und N71:** keine Änderung. Mit N71 entstehen deutlich weniger Einträge „Vereinsverweis ohne TM-ID" (beim BVB wären es 0 statt 13).

### Neue Bezüge und Felder in den Lücken

Künftige Pakete halten N47 ein: Die Kombination aus Art, Bezug und Feld ist je Paket eindeutig. Dafür kommen neue Werte vor, die der Server schon heute als Text übernimmt:

| Art | Bezug | Feld |
|---|---|---|
| `club` | `u21:tm:<TM-ID>` | `squad` (übersprungener Auffüller) |
| `club` | `u21:<TOR/ABW/MIT/ANG>` | `squad` (leerer Platz) |
| `club` | `u21:nr:<Nummer>` | `squad.shirt_number` (Nummer doppelt) |
| `player` | `tm:<TM-ID>` | `first_name` (N69), `squad.loan_until` (N70), `market_values.club` (N71), `ids.fmi.match` (mehrere mögliche FMInside-Treffer) |

Replit bestätigt, dass Vorschau und Arbeitsliste diese Einträge anzeigen und keiner davon als Vereinsverweis fehlgedeutet wird (`reference_issue` sucht Vereinsnamen in Bezügen der Art `club`).

## Stand der Pakete

- Die Bauskripte erzeugen aus den BVB-Rohdaten vom 05.10. das Paket v3 Byte für Byte (Prüfsumme `b938a48e…c17b50`).
- Die Leseskripte für Transfermarkt und FMInside sind für jeden Verein umgebaut und am 07.10. am BVB neu gelaufen. Das daraus gebaute Paket hat dieselben 51 Spieler in derselben Reihenfolge, dieselben Stärkequellen, 631 Marktwertpunkte, 322 Transfers, 24 Rekorde, 30 Titel und 115 Lücken wie v3. Unterschiede: Prüfdatum, 78 nachgetragene Vereins-IDs (N71), zwei Vereinsnamen ohne Leerzeichen am Ende und kleine Änderungen bei Transfermarkt seit dem 05.10. (Einsatzzählung bei einzelnen Spielern ohne Folge für Haupt- und Nebenpositionen, eine Ablöseangabe).
- Der Paketvertrag `Import_Paketvertrag.md` beschreibt jedes Feld, die Regeln und die Prüfung des Servers.
- **Der BVB bleibt mit v3 das erste Paket live (N66).** v3 ist von diesem Nachtrag nicht betroffen.

## Reihenfolge

Die Änderung zu N68 hält die Live-Umstellung nicht auf. Sie muss fertig sein, bevor der erste Verein hochgeladen wird, der einen Profi ohne CMTracker-Eintrag hat. Bis dahin meldet die Paketprüfung im Chat den Fall, und das Paket bleibt liegen.

Replit ordnet die Änderung selbst ein: mit #1045, falls dort noch offen, sonst als eigene kleine Aufgabe nach #1044.

## Bericht

1. Geänderte Stelle in `package_validation.py`, alt und neu
2. Die vier Tests mit Ergebnis
3. Bestätigung zu Vorschau und Sperrableitung
4. Bestätigung, dass ein Paket keinen sperrenden Eintrag erzeugen kann
5. Liste der Stellen, die Vor- oder Nachname statt `display_name` zeigen
6. Bestätigung zu den neuen Bezügen und Feldern
7. Grüner Gesamtlauf

## Freigabe

Freigegeben: die Änderung an der Paketprüfung nach N68 mit ihren Tests, die Prüfungen und der Bericht.

Nicht freigegeben: jede Änderung an der Stärkeformel, an der Sperrregel N48, an der Anzeige von Namen (erst nach Marks Entscheidung zu Punkt 5) und alles, was Nachtrag 13 nicht freigibt.
