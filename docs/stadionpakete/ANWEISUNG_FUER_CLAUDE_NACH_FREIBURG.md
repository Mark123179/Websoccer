# Neue Anweisung für Claude: Stadionpakete nach dem Freiburg-Review

Bereite weitere Stadionpakete für die bestehende Websoccer-Modellregistry vor.
Keine vereinsbezogenen Sonderfälle im gemeinsamen Renderer einbauen.
Diese Anweisung ergänzt und präzisiert den bisherigen Übergabevertrag.

## 1. Verbindliche Erkenntnisse aus diesem Review

### Freiburg

- FMI **944**, SC Freiburg, Europa-Park Stadion.
- Heimkurve/Fanwand **SUED**, Haupttribüne **WEST**, Gegentribüne **OST**.
- Modellachsen: `+x OST`, `-x WEST`, `+z NORD`, `-z SUED`.
- Umfeldachsen: `{"NORD":"+z","WEST":"-x"}`.
- Nord-Ende der Blaupause: ungefähr **340°**, Süd-Ende ungefähr **160°**.
  Die Spielfeld-Längsachse als ungerichtete Linie kann mit 160° beschrieben
  werden; das macht 160° aber nicht zur Peilung des NORD-Endes.
- Flugplatz und Suwonallee liegen OST, P2 NORD, Hauptgebäude WEST.
- Die aktuelle lokale Kapazität beträgt **35.000**. Die 34.700 aus der alten
  öffentlichen Vorschau sind kein Importwert und dürfen nicht zurückgeschrieben werden.
- Wirtschaftliche Plätze und das rohe Raster sind unterschiedliche Größen.
- Notwendige Orientierungsmetadaten, nur ergänzen statt Geometrie ersetzen:

```json
{
  "meta": {"homeStand": "SUED"},
  "scene_meta": {"mainStand": "WEST", "farStand": "OST"}
}
```

- Die gelieferten Ausschlüsse der Fangnetze samt Abspannung und die Zuordnung
  der V-Stützen zum Dach werden durch die Helligkeitskorrektur nicht geändert.
  Nicht ungefragt Netze ergänzen, Stützen umbauen oder andere Modelle anpassen.

### Stuttgart

- FMI **960**, VfB Stuttgart, MHPArena.
- Die korrigierte Fassung ist bereits lokal registriert; Modellassets und
  Manifest nicht durch eine ältere Fassung ersetzen.
- Heimkurve NORD beim Carl Benz Center, Gastseite SUED bei der SCHARRena,
  Haupttribüne WEST und Gegentribüne OST.
- Dieselben Achsenlabels wie oben gelten hier nach eigener geografischer
  Prüfung, nicht weil Freiburg sie ebenfalls verwendet.
- Lokales Umfeld: **102 Gebäude**, nicht die gefilterten 99 der alten
  Paketvorschau. Die drei Objekte an den Indizes 16, 27 und 28 bleiben erhalten.
- Die aktuelle Vorschau muss den vollständigen Bestand zeigen. Ältere Bilder
  mit ausgeblendeten Gebäuden nur ausdrücklich als historische Vergleiche führen.

## 2. Nachtbeleuchtung sichtbar prüfen, nicht nur technisch abhaken

Ein aktivierter Schalter und zwölf gültige Lichtquellen beweisen noch keine
brauchbare Nachtansicht. Rasen, Linien, Tore beziehungsweise Torbereiche und
relevante Tribünenteile müssen im tatsächlichen Browserbild lesbar sein.

- Im aktuellen Projekt-Renderer prüfen, bei unveränderter Kamera und Exposure.
- Tag, Nacht ohne Flutlicht und Nacht mit Flutlicht getrennt vergleichen.
- Flutlicht bleibt unabhängig von Tag/Nacht schaltbar.
- Montageorte, Richtungen, Winkel, Farben, Reichweiten, Quell-IDs und
  Gruppenzuordnung aus dem Modell erhalten; höchstens zwölf Laufzeitquellen.
- Keine unsichtbaren Zusatzleuchten und keine selbstleuchtenden Rasen- oder
  Sitzflächen als Ersatz für ein korrekt kalibriertes Flutlicht verwenden.
- Unity-Intensitäten sind nicht automatisch passende Browser-Intensitäten.
  Für Freiburg wurde bei unverändertem gemeinsamen Renderer der Faktor **8**
  auf die exportierten Fixture-Intensitäten gewählt: ursprünglich 60, im
  Browsermanifest 480. Die Originalwerte bleiben im Kalibrierungsbeleg erhalten.
- Dieser Faktor ist **keine globale Konstante für weitere Stadien**.
- Wird der Faktor bereits in `fixtures[].intensity` eingerechnet, darf er
  nicht noch einmal im Renderer oder beim erneuten Einspielen angewandt werden.
- Kalibrierung nach stabiler Leuchten-ID und Quellwert prüfen. Skripte müssen
  einen bereits kalibrierten Stand erkennen oder bei unpassenden Werten abbrechen.
- Original- und Browserwerte, Faktor, Geometriehash, Rendererhash und identische
  Vergleichsbedingungen in einem eigenen Prüfbeleg dokumentieren.
- Eine lokale Korrektur darf weder Tag-ohne-Flutlicht noch Nacht-ohne-Flutlicht
  noch das Licht anderer Vereine verändern.

## 3. Geografie und Vorschauen

- Offiziellen Stadionplan, native Modellflächen, Blaupausenrahmen und
  wirtschaftliche Daten getrennt vergleichen.
- Nicht die aus `rows * seats` geschätzte Heimkurve als geografischen Beweis benutzen.
- Beide Enden und beide Längsseiten durch reale Anker belegen.
- Peilungen eindeutig benennen: geografischer Norden, gerichtetes NORD-Ende
  der Blaupause und ungerichtete Spielfeldachse sind nicht austauschbar.
- Ein technisch gültiges Achsenpaar beweist noch keine reale Orientierung.
- Vollständiges aktuelles Umfeld verwenden. Überlappungen melden, nicht durch
  ungefragtes Filtern oder Löschen verstecken. Fehlende/ungültige Polygone
  ausdrücklich melden statt still entfernen.

## 4. Schutzdaten und Einspielen

- Identität über FMI plus Vereins-/Stadionnamen; lokale IDs lesend auflösen.
- Kapazitäten, Geld, Ausbauten, Blöcke, Raster und gespeicherte Designs erhalten.
- Orientierungsmetadaten unter Zeilensperre mit Vorher-Backup und
  vollständigem Nachhervergleich ergänzen; keine globale Heuristik ändern.
- Kontrolle, Korrektur, Registrierung, externe Serverübertragung und
  Veröffentlichung sind getrennte Schritte. Keine zusätzlichen Schritte
  oder Löschungen aus einer engeren Freigabe ableiten.
- Vorschauen und Dokumente dürfen keine Sitzungen, Zugangsdaten,
  signierten URLs oder privaten Datenbankbackups enthalten.

## 5. Vollständiger und reproduzierbarer Endstand

- Modellmanifest, Assets, Kalibrierungsbelege und sämtliche Prüfsummen liefern.
- Beide Manifestkopien im Paket müssen identisch sein.
- Geometrie-/Texturänderungen von reinem Manifest-/Dokumentwechsel trennen.
  Bei unveränderten Assets kann die Assetversion gleich bleiben; die
  Manifestrevision muss den neuen Inhalt eindeutig unterscheiden.
- Den aktuellen gemeinsamen Renderer nicht mit älteren Harness-Kopien ersetzen.
- Eigene Hilfsskripte müssen den korrigierten Endstand reproduzieren:
  ungefiltertes Umfeld und genau einmal angewandte Lichtkalibrierung.
- **Gemeinsam liefern:** aktuelle 2D-Ansicht, 3D-Editor, Ticker mit Dach,
  Ticker ohne Dach und Nacht mit Flutlicht; zusätzlich verortete Draufsicht,
  Gegenseite, Dach-/Körper-Isolation und Nacht ohne Flutlicht.
- Dach an/aus bei identischer Kamera prüfen. Tafeln samt Halterung gehören
  zum Dachzustand; keine Ränge oder Treppen durch Höhenfilter verschwinden lassen.
- Spielfeld an den Linienmittelachsen unabhängig auf **105 × 68 m** messen.
- Nach jeder Korrektur betroffene Bilder neu erzeugen und Prüfsummen erneuern.
  Veraltete Bilder nicht als Abnahme des neuen Stands ausgeben.
