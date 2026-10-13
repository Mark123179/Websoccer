# Verbindliche Anweisung für zukünftige Stadionpakete

Du bereitest Stadionmodelle für eine bestehende Websoccer-Anwendung vor.
Liefere datengetriebene Pakete für die vorhandene Stadionmodell-Registry,
keine neuen vereinsbezogenen Sonderfälle im gemeinsamen Renderer.

## 1. Identität und geschützte Bestandsdaten

- Identifiziere den Verein über `clubFmiId` plus Vereins- und Stadionnamen.
  Interne Club-/Stadion-IDs anderer Installationen sind nicht übertragbar.
- Lokale IDs und wirtschaftliche Kapazitäten liest Replit aus seiner Datenbank.
  Vorschau-/Blaupausen-Kapazitäten dürfen diese Werte niemals ersetzen.
- Wirtschaftliche Kapazitäten, Ausbauaufträge, Blockgeometrien, Block-IDs,
  Raster und gespeicherte RLE-Designs nicht als Nebenwirkung einer
  Modellkorrektur verändern. Metadatenkorrekturen gesondert ausweisen.
- Kontrolle ist keine Importfreigabe. Registrierung, Datenkorrekturen,
  externe Serverübertragung und Veröffentlichung brauchen ihren eigenen
  ausdrücklich freigegebenen Umfang.

## 2. Kurvenlage vor der Kalibrierung beweisen

Prüfe vier voneinander unabhängige Ebenen:

1. **Reales Stadion:** offizieller Stadion-/Blockplan, Heimkurve,
   Gästebereich, Haupttribüne und mindestens drei geografische Umfeldanker.
2. **Quellmodell:** Native Koordinaten und Bounds der Heim-/Gästeflächen,
   VIP-/Pressebereiche und Mannschaftsbänke. Namen allein reichen nicht.
3. **Blaupause:** gespeicherte Tribünenlabels, geografischer Feldrahmen
   (`fieldC`, `axisTheta`) und explizite Heim-/Haupttribünenmetadaten.
4. **Wirtschaftliche Daten:** tatsächliche Plätze je Tribüne aus der
   bestehenden Anwendung, soweit als lesender Prüfbeleg verfügbar.

Eine automatisch aus `rows * seats` der **Rohblaupause** ermittelte
Heimkurve ist kein Beweis der realen Lage und nicht gleichbedeutend mit
der aktuellen wirtschaftlichen Stehplatzkapazität. Bei Widersprüchen
abbrechen, die Ebenen getrennt gegenüberstellen und eine eng begrenzte
Korrektur vorschlagen. Nicht blind Nord-/Süd-Blöcke oder Kapazitäten tauschen.

## 3. Achsen korrekt deklarieren

- `calibration.standAxes` beschreibt die vier Tribünenseiten im nativen
  Modellrahmen: `+x`, `-x`, `+z`, `-z`.
- `calibration.surroundingsAxes` legt fest, auf welche Modellachsen die
  positive Feldlängsrichtung (`NORD`) und die positive Querrichtung (`WEST`)
  des Umfeldadapters abgebildet werden.
- Labels müssen technisch konsistent sein:
  `standAxes[surroundingsAxes.NORD] == "NORD"` und entsprechend für `WEST`.
  **Das genügt noch nicht:** Beide Enden und beide Längsseiten müssen
  zusätzlich gegen die realen geografischen Anker bestehen.
- `axisTheta` und geografische Nordrichtung sind nicht dasselbe wie eine
  bloße Bildschirmrichtung. Ein Screenshot ohne verortete Anker beweist
  keine geografische Übereinstimmung.
- Ein optionales, explizit deklariertes Achsenpaar darf je Modell abweichen.
  Bestehende Stadionmodelle und das Altverhalten des Adapters nicht ändern.
- Nicht das Modell spiegeln, Schriftzüge umkehren oder die freigegebene
  gemeinsame Spielkamera drehen, um eine falsche Zuordnung zu verdecken.

### Stuttgart: konkrete Referenz für den Fehler

Offizieller Plan:
https://www.mhparena-stuttgart.de/arena/arenaplan

- Cannstatter Heimkurve: NW-Ende beim Carl Benz Center.
- Untertürkheimer Kurve mit Gästebereich: SO-Ende bei der SCHARRena.
- Quellmodell: Heimflächen bei `+z`, Gastflächen bei `-z`,
  Haupttribüne/Bänke bei `-x`.
- Richtige Kalibrierung:

```json
{
  "standAxes": {"+x": "OST", "-x": "WEST", "+z": "NORD", "-z": "SUED"},
  "surroundingsAxes": {"NORD": "+z", "WEST": "-x"}
}
```

Die erste Fassung deklarierte `+z = SUED` und spiegelte das Umfeld längs.
Sie war technisch valide, aber geografisch falsch. Die abgeleitete
SUED-Heimkurve der Rohblaupause war ebenfalls irreführend. Die bestehende
große wirtschaftliche Stehplatzseite war bereits im NORD.
Die Korrektur betrifft Achsen und explizite Orientierungsmetadaten,
nicht Plätze, Quellgeometrie oder Ausbauzustand.

Im aktuellen Geometrievertrag lauten die expliziten Metadaten für Stuttgart:

```json
{
  "meta": {"homeStand": "NORD"},
  "scene_meta": {"mainStand": "WEST", "farStand": "OST"}
}
```

Das ist eine **Teilansicht der ergänzten Schlüssel**, kein Ersatz für die
vollständige Geometrie oder die übrigen Metadaten. Bestehende Inhalte beim
Ergänzen erhalten. Die lokale Datenkorrektur ist getrennt vom Manifest;
eine spätere externe Serverübernahme muss beide Teile ausdrücklich prüfen.

**Diese Stuttgart-Werte nicht als Standard auf andere Stadien übertragen.**
Die Lage für jeden Verein neu belegen.

## 4. Umfeld unverändert und nachvollziehbar prüfen

- Verwende für die Abnahme das vollständige aktuelle Vereinsumfeld.
- Keine Gebäude, Bäume, Straßen oder Flächen still für bessere Bilder
  entfernen. Vorschau-Filter ausdrücklich nennen und den ungefilterten
  Bestand als Vergleich mitliefern.
- Bei Überlappungen Flächen/Bounds und Quelle nennen. Gebäude können echte
  Stadionanbauten sein; Listenindizes sind kein ausreichender Löschbeleg.
- Für reale Höhen braucht es räumlich zugeordnete Quellen. Schematische
  Höhen ausdrücklich als schematisch kennzeichnen.

## 5. Modell-, Spielfeld-, Dach- und Lichtprüfung

- Paket-Prüfsummen und `assetSha256` vollständig nachrechnen.
- Spielfeld **105 × 68 m an den Linienmittelachsen** messen, nicht an
  Rasen-Bounds, äußerer Linienbreite oder Eckbögen. Geometriehash und
  Messmethode beilegen. Nicht messbare Quellen ausdrücklich melden.
- Dachfamilien aus der Quelle isolieren. Dächer, Träger, Aufbauten,
  vorhandene Videotafeln und ihre Halterungen müssen dem Dachzustand folgen.
  Masten vollständig schalten, wenn sie als Bestandteil des Dachs
  ausgewiesen und freigegeben sind.
- Höhenbasierte Dachschaltung gegen echte Rang-/Treppen-Geometrie prüfen.
  Crowd-Ausnahmen allein schützen nicht alle Tribünenbauteile.
- Dach-an/aus: Kamera und alle Nicht-Dach-Zustände identisch halten,
  Dach-/Nicht-Dach-Dreiecke unabhängig nachzählen, Gegenseite und
  Draufsicht prüfen. Keine Rangbauteile zu Crowd umdeklarieren.
- Netz-/Choreo-/Kulissen-Ausschlüsse mit exakten Namen, Bounds, Material
  und Quellbeleg ausweisen. Fangnetze und Tornetze unterscheiden.
  Die Freigabe eines anderen Vereins gilt nicht automatisch.
- Leuchten aus echten Modellteilen belegen; höchstens zwölf
  Laufzeitlichtquellen, klare Dokumentation der zusammengefassten Leuchten.
  Keine erfundenen Lichtorte als Quellbeweis ausgeben.

## 6. Abnahmeserie und Paketinhalt

Die fünf aktuellen Ansichten gemeinsam liefern:
**2D, 3D-Editor, LiveTicker mit Dach, LiveTicker ohne Dach,
LiveTicker bei Nacht.**
Zusätzlich: Draufsicht, Gegenseite, verortete Umfeldansicht und
Dach-/Körper-Isolation. Prüfblocker nicht mit alten Bildern verdecken.

Mindestens mitliefern:

- `models/<FMI>.json` und sämtliche referenzierten Modellassets;
- vollständige Prüfsummenliste für den gelieferten Endstand;
- Quellidentität/Hashes, Ausschlussbericht, Spielfeldmessung,
  Dachzählung und Leuchtennachweise;
- Kurven-/Haupttribünenlage mit offiziellen Quellen,
  nativen Modellachsen und geografischen Ankern;
- offene Punkte und notwendige Metadatenkorrekturen als getrennte Liste;
- reproduzierbare Prüfwerkzeuge und eindeutige Einspielanweisung.

Prüfe gegen den **aktuellen** Projekt-Renderer und seine Python-/JS-Validatoren.
Keine älteren gemeinsamen Renderer-Dateien zurückkopieren.
Wenn ein gemeinsamer Patch wirklich nötig ist, Diff und vollständige
Nachher-Dateien auf denselben Stand bringen und Altmodelle gegenprüfen.
Asset-/Cache-Versionen korrekt behandeln.

## 7. Einspielen durch Replit

1. Lokale Identität und Schutzdaten lesend prüfen.
2. Fachliche Freigabe einschließlich benannter Einschränkungen einholen.
3. Vorher-Backup von Verein, Stadium, Geometrie, Design und Ausbauten.
4. Assets außerhalb Git dauerhaft speichern und aus dem Zielspeicher
   wieder herunterladen/verifizieren; Manifest in der Registry ablegen.
5. Nur freigegebene Orientierungsmetadaten unter Zeilensperre ergänzen.
   Kein globaler Heuristikwechsel und keine verdeckte Geometriekorrektur.
6. Nachher-Abgleich: Nur die ausdrücklich freigegebenen Felder dürfen
   abweichen; wirtschaftliche Kapazitäten, Blöcke, Designs und Ausbauten
   müssen identisch bleiben.
7. Laufende Anwendung mit registrierter Live-Scene, echten Zielassets und
   aktuellem Renderer prüfen. Lokal erfolgreiche Registrierung ist keine
   externe Serverübertragung oder Veröffentlichung.
