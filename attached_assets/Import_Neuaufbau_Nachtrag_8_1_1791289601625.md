# Import-Neuaufbau: Nachtrag 8 zur Übergabe

Stand: 06.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 7 und zu Replits T2-Bericht vom 06.10.2026

Dieser Nachtrag nimmt T2 ab, regelt das Potenzial bei „Dynamic" und gibt T3 und T4 frei. Er hat bei Widersprüchen Vorrang vor Teil A, Teil B, Teil C und den Nachträgen 1 bis 7.

Alle Entscheidungen hat Mark am 06.10.2026 einzeln getroffen.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N38 | **T2 ist abgenommen.** Der BVB ist im Pilot eingelesen, die Zahlen stimmen mit dem Paket überein, ein zweiter Upload ändert nichts, der alte Replit-Stand ist unverändert. Der offene Stärkepunkt (14 Spieler ohne gespeicherte Stärke) wird durch N39 gelöst. Die Sicherungen `t1_saved_*` dürfen entfernt werden |
| N39 | **Bei „Dynamic" gilt der obere Wert der FMInside-Spanne als Potenzial.** Beispiele von Mark: Samuele Inácio 65–80 → 80, Kenan Yildiz 80–95 → 95, Savinho 75–90 → 90. Das ist ein Quellwert und keine Schätzung, die Regel „NULL bleibt NULL" ist nicht berührt |
| N40 | **Das Paket liefert die Spanne mit.** Das Werkzeug liest sie aus und trägt den oberen Wert als FMInside-Potenzial ein. Das BVB-Referenzpaket wird dafür neu gebaut |
| N41 | **Ablauf:** Replit baut T3 und T4 in einem Zug, ein Halt am Ende. Parallel baut die Paket-Sitzung das BVB-Paket mit den Spannen neu. Mark lädt das neue Paket selbst über den neuen Creator-Upload hoch und klickt danach die Abnahme durch |

## Zu N39: Woher die Spanne kommt

Auf der FMInside-Spielerseite steht beim Potenzial nur „Dynamic". Die Spanne erscheint beim Überfahren des Potenzial-Symbols neben dem Rating, ohne Login. Beleg von Mark für Samuele Inácio (FM26, 26.2.0):

> Potential between 65 and 80 (-8)

Die Zahl in Klammern ist die Potenzial-Stufe aus Football Manager. Sie gehört fest zu einer Spanne.

Geltung (Lesart von Claude, aus Marks Beispielen abgeleitet): Die Regel gilt für jeden Spieler mit „Dynamic", auch wenn er zusätzlich einen CMTracker-Eintrag hat. Beim BVB sind das 28 Spieler, darunter Ethan Nwaneri und Elias Benkara. Bei ihnen ändert sich dadurch die maximale Stärke; die aktuelle Stärke bleibt gleich.

Ist für einen Spieler keine Spanne lesbar, bleibt das FMInside-Potenzial leer. Dann gilt, was heute gilt: keine berechnete Stärke ohne Potenzialquelle, Info-Eintrag auf der Arbeitsliste, kein Ersatzwert.

## Zu N40: Änderung am Paket

Ergänzung in `players[].ratings.fminside`, Formatversion bleibt 1:

```json
"fminside": {
  "rating": 50,
  "potential": 80,
  "potential_range": {"min": 65, "max": 80, "code": -8},
  "raw": {"potential_text": "Potential between 65 and 80 (-8)"}
}
```

- `potential` trägt bei „Dynamic" den oberen Wert der Spanne.
- `potential_range` ist nur bei „Dynamic" gefüllt und sonst `null`.
- `raw.potential_text` enthält den Text des Hinweisfelds im Wortlaut.
- Am Server ändert sich nichts an der Rechnung: Er liest `potential` wie bisher. Die Spanne bleibt als Beleg im Quellstand-Archiv.
- Das neue BVB-Paket unterscheidet sich vom alten nur in diesen Feldern und in der Prüfsumme.

## Auftrag an die Paket-Sitzung

1. Für alle 28 BVB-Spieler mit „Dynamic" die Spanne aus dem Hinweisfeld des Potenzial-Symbols auf der FMInside-Spielerseite lesen (über Marks Browser, FM26 26.2.0).
2. `potential`, `potential_range` und `raw.potential_text` wie oben eintragen.
3. Paket neu bauen, Prüfsumme neu berechnen, sonst nichts ändern. Erhebungstag bleibt 05.10.2026.
4. Mark melden: Liste der 28 Spieler mit Rating, Spanne und Stufe; Spieler, bei denen keine Spanne lesbar war.
5. Für das Werkzeug der zweiten Stufe festhalten: Die Spanne gehört zum Standardumfang jedes Pakets.

## Umfang von T3: Creator-Upload, Vorschau, Arbeitsliste

- Upload → automatische Prüfung → **Vorschau** → Zielliga wählen → **Bestätigen**. Die Vorschau schreibt nichts.
- Die Vorschau zeigt: Verein, Anzahl Spieler je Mannschaft, Leihfälle, Lücken nach Schwere, fehlende Bilder, und bei erneutem Upload vor Ligastart, was sich ändert und welche Spieler in den Prüfpool gehen (N36).
- Ligen werden von Hand im Creator angelegt, mit dem Kennzeichen spielbar oder nicht spielbar.
- **Arbeitsliste** je Liga und Verein, getrennt nach sperrend, Einzelsperre und Info, mit Erledigt-Status.
- Nacharbeit direkt aus der Liste: externe ID oder Wert eintragen; TM-ID zu einem Vereinsnamen nachtragen (N11); Verknüpfungsvorschlag mit einem Klick bestätigen (N12); Prüfpool-Spieler von Hand zuordnen (N36).
- **Ligastart-Sperre:** Eine Liga lässt sich nicht starten, solange sperrende Einträge offen sind. Das gilt für jeden Startweg.
- Bildprüfung: je Verein, Spieler und Rekordhalter prüfen, ob die erwartete Datei unter `ASSETS_ROOT` liegt. Fehlt sie, entsteht ein Info-Eintrag. Es wird nichts hochgeladen.

## Umfang von T4: Anzeige auf den echten Seiten

Im neuen Modus zeigen die bestehenden Seiten die importierten Daten:

- **Vereinsseite:** Stammdaten, Farben, Spitzname, Motto, Stadion mit zwölf Kapazitäten
- **Kader:** 1. Mannschaft mit Rückennummern und Positionen, Geliehene gekennzeichnet, Leih-Pool getrennt ausgewiesen. Die U21 ist nur im Creator zur Prüfung sichtbar, nicht öffentlich und nicht aufstellbar
- **Spielerprofil:** vollständiger Marktwertgraph (Startwert gekennzeichnet), Transferhistorie mit dem neuesten Eintrag oben, fremde Vereine mit Name und leerem Wappen
- **Ruhmeshalle:** echte Rekorde und Titel; Titelzahl aus den Einzeleinträgen; neue Rekordschlüssel müssen gespeichert, aber noch nicht angezeigt werden
- Fehlende Werte werden als unbekannt gezeigt, nie als 0

Dazu zwei Korrekturen:

- **Fehlendes Wappen:** Die Auslieferung liefert ein leeres Wappen und keinen Serverfehler (T2-Bericht, Punkt 7).
- **Zugang für Mark:** Der Pilot bekommt eine eigene Adresse im Replit-Projekt. Mark meldet sich mit seinem normalen Konto an. Schreibzugriffe sind für Creator-Upload, Arbeitsliste und Liga-Anlage geöffnet, Hintergrundjobs bleiben aus.

Alles Neue liegt hinter dem Verhaltensschalter. Im Altmodus ändert sich nichts.

## Bericht am Ende von T3 und T4

1. Adresse des Pilots und Anmeldeweg
2. Upload-Ablauf mit Bildschirmfotos von Vorschau, Bestätigung und Arbeitsliste
3. Nachweis: Vorschau schreibt nichts; ein Abbruch hinterlässt nichts
4. Ligastart-Sperre: welche Startwege geprüft wurden
5. Bildprüfung: Anzahl fehlender Bilder beim BVB nach Art
6. Bildschirmfotos der vier Seiten mit BVB-Daten
7. Liste der Stellen mit Verhaltensschalter, soweit neu
8. Testergebnis im Altmodus

## Abnahme durch Mark

Mit dem neuen BVB-Paket, hochgeladen über den Creator:

1. Upload zeigt eine Vorschau und schreibt erst nach Bestätigung.
2. Vereinsseite zeigt Stammdaten, Farben, Spitzname und Stadion mit zwölf Kapazitäten.
3. Kader vollständig laut Transfermarkt, Leihspieler richtig zugeordnet, Rückennummern und Positionen nach Regel.
4. Ein Spielerprofil zeigt Marktwertgraph und Transferhistorie, neueste oben, fremde Vereine mit leerem Wappen.
5. Stärke ist für jeden Spieler mit Quellwerten berechnet, bei „Dynamic" mit dem oberen Wert der Spanne. Die zwei Gems ohne FMInside sind einzeln gesperrt.
6. Ruhmeshalle zeigt die echten Rekorde und Titel.
7. Arbeitsliste zeigt alle Lücken, getrennt nach sperrend, Einzelsperre und Info.
8. Ein zweiter Upload desselben Pakets ändert nichts.
9. Die U21 ist nach Regel besetzt: 19 Spieler, ein leerer Mittelfeldplatz mit Info-Eintrag, Benkara im Leih-Pool (N2).

## Freigabe

Freigegeben: T3 und T4 nach dem Umfang oben. Nicht freigegeben: Reset-Befehl (T5), Sicherung der Dortmund-Szene, jede Änderung an der Stärkeformel.
