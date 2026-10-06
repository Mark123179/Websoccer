# Import-Neuaufbau: Nachtrag 10 zur Übergabe

Stand: 06.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 9 und zu Replits Entwurf `docs/import-pilot/t3-t4-nachtrag9-entwurf.md`

Dieser Nachtrag gibt den Entwurf für T3 und T4 mit zwei Auflagen frei. Er korrigiert den Schlüssel der Arbeitsliste aus Nachtrag 9 und hat bei Widersprüchen Vorrang vor Teil A, Teil B, Teil C und den Nachträgen 1 bis 9.

Alle Entscheidungen hat Mark am 06.10.2026 einzeln getroffen.

## Befund, der die Korrektur auslöst

Nachtrag 9 legt den Schlüssel eines Eintrags als Verein + Gegenstand + Feld fest. Im BVB-Paket ist dieser Schlüssel nicht eindeutig: Zehn Lücken tragen `club` / `u21` / `squad`. Das sind neun übersprungene U21-Auffüller und der leere Mittelfeldplatz. Sie unterscheiden sich nur im Text.

Mit einem eindeutigen Schlüssel in der Datenbank würden daraus eine Zeile statt zehn, oder die Migration scheitert an den 156 vorhandenen Zeilen im Pilot. Die Sollzahlen aus Nachtrag 9 (156 Zeilen, 128 offen, 28 geschlossen) setzen zehn getrennte Zeilen voraus.

Alle übrigen Schlüssel sind in v1 und v2 eindeutig, auch die 13 Vereinsnamen ohne TM-ID.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N47 | **Bei gleichem Schlüssel unterscheidet der Server am Text.** Der Schlüssel bleibt Verein + Gegenstandsart + Bezug + Feld. Hat ein Paket mehrere Lücken unter demselben Schlüssel, kommt der Text der Lücke als Unterscheidung dazu. v1 und v2 bleiben gültig, ein neues Paket ist nicht nötig. Korrigiert „Zu N43" in Nachtrag 9 |
| N48 | **Die Einzelsperre ist ausgeschrieben.** Ein Spieler ist gesperrt, solange eine der drei Bedingungen unten zutrifft. Das ist die Ausformulierung von N45 und E58 |
| N49 | **Der Entwurf für T3 und T4 ist mit den Auflagen N47 und N48 freigegeben.** Replit baut ohne weiteren Zwischenhalt. Nächster Halt am Ende von T3 und T4 mit dem Zehn-Punkte-Bericht |

## Zu N47: Schlüssel im Einzelnen

- Einfacher Fall: Der Schlüssel kommt im Paket genau einmal vor. Der Text gehört nicht zum Schlüssel und darf sich mit einem neuen Paket ändern.
- Mehrfacher Fall: Der Schlüssel kommt im Paket mehrmals vor. Jede dieser Lücken bekommt zusätzlich einen Unterschlüssel aus ihrem Text. Ändert sich der Text einer solchen Lücke, gilt sie als neue Lücke: Der alte Eintrag wird durch das Paket geschlossen, ein neuer entsteht.
- Die Eindeutigkeit in der Datenbank gilt über Schlüssel und Unterschlüssel.
- Die 156 vorhandenen Zeilen im Pilot bleiben 156 Zeilen. Zehn davon bekommen einen Unterschlüssel, Status und Text bleiben unverändert.
- Wechselt ein Schlüssel zwischen zwei Paketen vom einfachen in den mehrfachen Fall oder zurück, führt der Eintrag mit gleichem Text weiter. Replit beschreibt das Verhalten im Bericht.
- Die Sollzahlen aus Nachtrag 9 gelten unverändert: nach v2 156 Zeilen, 128 offen, 28 durch Paket erledigt.

Für das Werkzeug der zweiten Stufe: Jede Lücke bekommt einen eigenen Bezug, bei übersprungenen Spielern die TM-ID. Dann tritt der mehrfache Fall nicht mehr auf.

## Zu N48: Wann ein Spieler gesperrt ist

Ein Spieler ist einzeln gesperrt, solange mindestens eine Bedingung zutrifft:

1. Die FMI-, TM- oder CMTracker-ID hat den Status `nicht_gefunden`.
2. Zu einer vorhandenen FMI- oder CMTracker-ID (`gefunden` oder `von_hand`) fehlt das Rating dieser Quelle.
3. Für den Spieler ist keine Stärke berechnet.

`nicht_vorhanden` bei CMTracker sperrt nicht (E58).

- Die Sperre wird nach jedem Import und nach jeder Nacharbeit neu abgeleitet.
- Der Eintrag auf der Arbeitsliste schließt sich mit der Sperre und lässt sich nicht von Hand abhaken (N45).
- Bedingung 2 verhindert, dass eine von Hand nachgetragene ID einen Spieler freigibt, dessen Stärke nur aus der anderen Quelle stammt.

Prüfung am BVB-Paket v2: 34 Spieler mit beiden Quellen, 15 mit FMInside und CMTracker `nicht_vorhanden`, 2 ohne FMInside. Die Regel sperrt genau Takato Yamamoto und Bjarki Gardarsson.

## Zu N49: Was am Entwurf bestätigt ist

- Die bestehende Arbeitsliste wird erweitert, es gibt keine zweite Liste.
- Vorschau und bestätigter Import nutzen dieselbe Vergleichslogik. Die Vorschau schreibt nichts.
- Handabschluss und Paketabschluss bleiben unterscheidbar. Ein vom Paket geschlossener Eintrag öffnet sich wieder, wenn die Lücke zurückkommt.
- Der Test v1 → v2 → v2 läuft in einem eigenen Testbestand. Der Pilot bleibt auf v1.
- T4 passt die bestehenden Seiten an und bleibt hinter dem Verhaltensschalter.
- Die Schemaänderung an der Arbeitsliste kommt als neue Migration und läuft nach N33 überall.

## Ergänzung zum Bericht

Zu Punkt 10 zusätzlich:

- Name der neuen Migration
- Nachweis, dass die 156 Zeilen im Pilot nach der Migration in Anzahl, Status und Text unverändert sind
- Nachweis, dass die Arbeitsliste im alten Replit-Stand (`public`) weiter 0 Zeilen hat
- Verhalten im mehrfachen Fall: Textänderung, Wechsel zwischen einfachem und mehrfachem Fall
- die Sperrregel aus N48 als Testfälle: ID `nicht_gefunden`, ID `von_hand` ohne Rating, CMTracker `nicht_vorhanden`

## Freigabe

Freigegeben: T3 und T4 nach dem Entwurf, mit N47 und N48. Unverändert nicht freigegeben: Einlesen von v2 in den Pilot, Reset-Befehl (T5), Sicherung der Dortmund-Szene, jede Änderung an der Stärkeformel. Hetzner bleibt unberührt.
