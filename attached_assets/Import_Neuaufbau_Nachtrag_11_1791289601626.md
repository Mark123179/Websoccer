# Import-Neuaufbau: Nachtrag 11 zur Übergabe

Stand: 06.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 10 und zu Replits Zwischenbericht zu T3 und T4

Dieser Nachtrag bewertet den Zwischenbericht zu T3 und T4, nimmt die Bildprüfung aus der Pilotabnahme und gibt das Einlesen von v2 in den Pilot frei. Er hat bei Widersprüchen Vorrang vor Teil A, Teil B, Teil C und den Nachträgen 1 bis 10.

Alle Entscheidungen hat Mark am 06.10.2026 einzeln getroffen.

## Bewertung des Zwischenberichts

| Auflage | Soll | Bericht | Stand |
|---|---|---|---|
| N47 Schlüssel | 156 Zeilen im Pilot unverändert, zehn mit Unterschlüssel, `public` bei 0 | 156 Zeilen, Prüfsumme über ID, Status und Text gleich, genau zehn Unterschlüssel, `public` 0 | erfüllt |
| N48 Sperre | nach v2 genau 2 Sperren | Testbestand nach v2: 49 Stärken, 2 Sperren | erfüllt |
| N49 Ablauf | Vorschau schreibt nichts, Test im eigenen Bestand, Pilot bleibt auf v1 | neun neue Prüfungen grün, Pilot auf v1 | erfüllt |
| Stärkeformel | unverändert | unverändert, Stichprobe auf die Rohskala 0–200 korrigiert | erfüllt |
| Gesamtlauf | alle Tests grün | 1.657 von 1.658, ein roter Mengentest | offen, siehe N52 |

## Entscheidungen

| # | Entscheidung |
|---|---|
| N50 | **Die Bildprüfung gehört nicht zur Pilotabnahme.** Im Pilot ist sie ausgeschaltet und schreibt keine Einträge. Geprüft wird beim Import auf dem Live-Server, dort liegen die Dateien |
| N51 | **N48 gilt unverändert, v1 ruht.** 16 Sperren bei v1 sind das richtige Ergebnis der Regel. v1 wird im Pilot nicht neu eingelesen. Maßstab für die Abnahme sind die Zahlen nach v2 |
| N52 | **T3 und T4 gelten erst mit grünem Gesamtlauf als fertig.** Replit korrigiert den Mengentest und belegt die Herkunft des Scheinvereins |
| N53 | **v2 darf in den Pilot, sobald der grüne Bericht vorliegt.** Kein Zwischenhalt. Vorher sichert Replit den Pilotstand auf v1 |

## Zu N50: Bildprüfung

Auf Replit liegen nur wenige Spielerbilder. Die Bilder liegen vollständig auf dem Live-Server (E31). Die im Bericht genannten 51 Spielerporträts und 11 Personenporträts messen deshalb den Dateispeicher von Replit und sagen nichts über den BVB-Bestand.

- Replit schaltet die Bildprüfung über eine Einstellung. Im Pilot steht sie auf aus, auf dem Live-Server auf an.
- Ist sie aus, zeigt die Vorschau keine Bildzahlen, und der Knopf der Bildprüfung schreibt nichts.
- Die Arbeitsliste im Pilot bleibt bei den 156 Zeilen aus dem Paket.
- Der Code der Bildprüfung bleibt wie gebaut. Der Bericht belegt, dass sie arbeitet: Das Wappen wird gefunden, fehlende Dateien werden nach Art gezählt.
- Punkt 5 der Berichtsliste aus Nachtrag 8 (fehlende Bilder beim BVB nach Art) ist damit erledigt und kein Abnahmekriterium.
- E40 gilt unverändert: Fehlende Bilder sperren nie.

Reihenfolge, die Mark festgelegt hat: erst die BVB-Daten im Pilot abnehmen, dann auf den Live-Server ausrollen samt Import-Knopf, dann jeden weiteren Verein direkt auf dem Live-Server importieren. Dort werden auch die Bilddateien kontrolliert.

## Zu N51: Sperren bei v1

In v1 haben 14 dynamische Spieler keine Potenzialquelle und damit keine berechnete Stärke. Nach N48, Bedingung 3, sind sie gesperrt. Zusammen mit Takato Yamamoto und Bjarki Gardarsson ergibt das 16.

- Die Regel wird nicht gelockert, es gibt keine Ersatzstärke.
- Der Pilot wird nicht mit v1 neu aufgebaut.
- Mit v2 lösen sich die 14 Fälle auf. Soll nach v2: 49 Stärken, 2 Sperren.

## Zu N52: Grüner Gesamtlauf

- Der neue Mengentest zählt nur Vereine, die zum Importbestand gehören.
- Replit liefert den Gesamtlauf mit 1.658 von 1.658.
- Dazu ein Satz, aus welcher Migration der Scheinverein stammt und wozu er dient.
- Dazu der Nachweis, dass der Scheinverein in Vereinslisten, Ligen und Zählungen der App nicht auftaucht.

## Zu N53: v2 in den Pilot

Ablauf ohne weiteren Halt, sobald der grüne Gesamtlauf und der Zehn-Punkte-Bericht vorliegen:

1. Pilotstand auf v1 als Dump sichern. Dateiname und Ablageort stehen im Bericht.
2. v2 über Vorschau und Bestätigung einlesen, so wie es später live läuft.
3. Zahlen nach dem Import melden.

Sollzahlen nach v2 im Pilot:

| Größe | Soll |
|---|---|
| Zeilen auf der Arbeitsliste | 156 |
| davon offen | 128 |
| davon durch Paket erledigt | 28 |
| berechnete Stärken | 49 |
| Einzelsperren | 2 (Takato Yamamoto, Bjarki Gardarsson) |

Weicht eine Zahl ab, hält Replit an und meldet die Abweichung mit Ursache. Der Dump aus Schritt 1 bleibt liegen.

Danach kontrolliert Mark die BVB-Daten auf den vier Seiten aus T4.

## Ergänzung zum Bericht

Zusätzlich zum Zehn-Punkte-Bericht:

- Gesamtlauf mit Anzahl der Tests und Ergebnis
- Herkunft und Nachweis zum Scheinverein (N52)
- Name der Einstellung für die Bildprüfung und ihr Wert im Pilot (N50)
- Dump des Pilotstands auf v1: Dateiname, Größe, Ablageort
- die fünf Sollzahlen nach v2 im Pilot, Ist gegen Soll
- Bildschirmfotos von Vorschau und Arbeitsliste nach v2 im Pilot

## Freigabe

Freigegeben: Korrektur des Mengentests, Einstellung für die Bildprüfung, Zehn-Punkte-Bericht, Sicherung des Pilotstands auf v1, Einlesen von v2 in den Pilot.

Unverändert nicht freigegeben: Reset-Befehl (T5), Sicherung der Dortmund-Szene, jede Änderung an der Stärkeformel. Hetzner bleibt unberührt.
