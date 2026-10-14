# Verbindliche Anweisung für Claude nach Augsburg V2

Gilt ergänzend zu den bisherigen Stadionpaket-Anweisungen für zukünftige
Arbeiten. Keine vereinsspezifischen Renderer-Patches. Pakete vorbereiten und
prüfbar liefern; Registrierung, Upload, Serverübertragung und Veröffentlichung
bleiben gesondert freizugeben.

## 1. Augsburg: aktueller Korrekturstand

- FMI **2238**, **FC Augsburg**, **WWK Arena**.
- Lokal: Heimkurve **NORD**, Haupttribüne **WEST**, Gegentribüne **OST**.
- Modell nicht drehen/spiegeln. `standAxes`:
  `{"+x":"OST","-x":"WEST","+z":"NORD","-z":"SUED"}`;
  `surroundingsAxes`: `{"NORD":"+z","WEST":"-x"}`.
- **30.660 Plätze**; wirtschaftliche Stehplätze **NORD 5.366,
  SUED 1.150, OST/WEST 0** bleiben unverändert.
- Vereins-/Stadionfelder, Blöcke, Typen, Reihen, Plätze, RLE,
  Designs und Ausbauten bleiben geschützt.
- V2-Modellversion **7718595a38dc4253**, Geometriehash
  `6c9c6d7a39f8035834661655bdcab71d8368f05e827e09993929a70280b6e06c`.
- V2 enthält gegenüber V1 vier ausdrücklich dokumentierte Fassadengitter
  (`ad_st009_normal_02/08/10/12`) und eine zusätzliche Textur.
  Alle 213 bestehenden Meshes sind bei Quell-ID-Zuordnung geometrisch,
  materiell und in ihrer Hierarchie unverändert. Unterschiedliche
  Gesamtdaten und neue Offsets deshalb nicht als bloße Umbenennung ausgeben.
- Zwölf Laufzeitquellen repräsentieren 50 Quellleuchten; Intensität **60**,
  Lichtfaktor **1**, unverändert.

## 2. Dach: vorhandenen Vertrag eindeutig nutzen

- Nach Funktion bestimmte Dachmeshes können im Export das Präfix `DACH_`
  erhalten. Quellname, Unity-Objekt-ID, Hierarchie, Materialien und
  Transformation müssen weiterhin nachvollziehbar sein.
- Augsburg: **59 Dachmeshes**, `roofMeshPrefixes=["DACH_"]`,
  `roofMinHeight=-1`. Unabhängig nachgerechnet: **96.252 Dachdreiecke**,
  keine teilweise geschalteten Dachmeshes, keine als Dach geschalteten
  Körpermeshes.
- Die sechs Betonabschluss-Dreiecke aus V1 bleiben Körper.
  `front3_27/27.001` bleiben begründet als feste Fassadenkolonnade erhalten.
  Das ist nicht dasselbe wie unbeabsichtigt verbliebene Dachstummel.
- `roofMeshNames` ist für diese Lösung **nicht erforderlich und nicht
  implementiert**. Keine nicht unterstützten Felder voraussetzen.
- Bei anderen Stadien Körper/Dach anhand der Quelle bestimmen, nicht nach
  Namen oder Höhe allein. Keine Treppen oder Ränge als Crowd umdeklarieren.
- Videotafeln und Halterungen, soweit in der Quelle vorhanden, dem
  Dachzustand zuordnen. Fehlende Tafeln oder Fangnetze nicht erfinden.

## 3. Gelände: neuer gemeinsamer, ausdrücklicher Vertrag

Die Funktion ist in Replit implementiert, kein reiner Augsburg-Mock mehr.
Die Deklaration liegt im **lokalen Geometrieobjekt `surroundings`** und wird
lesend nach **`presentation.surroundings`** projiziert:

```json
{
  "surroundings": {
    "groundLevel": 7.7,
    "groundCutout": [
      [-43.9,-96.3],[-34,-96.7],[20.7,-96.7],[34,-96.7],[43.9,-96.3],
      [53.9,-92.4],[62.8,-86.9],[66.5,-83.2],[71.9,-74.9],[76,-65.4],
      [77.8,-54.9],[77.8,25.9],[77.8,54.9],[76,65.4],[71.9,74.9],
      [66.5,83.2],[62.8,86.9],[53.9,92.4],[43.8,96.3],[32.9,97.5],
      [2.2,97.5],[-2.2,97.5],[-32.9,97.5],[-43.9,96.3],[-53.9,92.4],
      [-62.8,86.9],[-66.5,83.2],[-71.9,74.9],[-74.7,65],[-75.5,54.4],
      [-76,-54.4],[-76,-65.4],[-71.9,-74.9],[-66.5,-83.1],[-62.8,-86.9],[-53.9,-92.4]
    ]
  }
}
```

Das Beispiel ist die geprüfte Augsburg-Deklaration. Nicht auf andere
Stadien übertragen; dort ausschließlich eigene quellgeprüfte Koordinaten liefern.

### Bedeutung und Validierung

- Ohne beide Felder bleibt das bisherige Verhalten unverändert.
- `groundLevel` ist eine **Verschiebung der gesamten Umfeldgruppe** in Metern:
  Boden, Straßen, Grün, Wasser, Gebäude, Bäume und Konturen.
  Spielfeld, Sitze, Kameras und Stadionmodell bleiben unverändert.
- Zahl erforderlich, endlich, Bereich **−30 bis +30**. Keine Strings,
  Bool-Werte, `null`, NaN oder Infinity.
- Eine von null abweichende Höhe **benötigt eine Aussparung**.
  `groundCutout` ohne `groundLevel` ist ein Fehler, wird nicht still ignoriert.
- `groundCutout`: **3–256** Punkte in **Modellkoordinaten x,z**, nicht
  untransformierte OSM-/Blaupausenpunkte. Je Punkt genau zwei endliche
  Zahlen, jeweils innerhalb ±10.000 Meter.
- Ein abschließender Wiederholungspunkt des Startpunkts ist erlaubt und
  wird lesend normalisiert. Andere doppelte Punkte, rücklaufende Kanten,
  Selbstüberschneidungen und flächenlose Polygone werden abgelehnt.
- Beide Umlaufrichtungen sind erlaubt. Es darf keinen heimlichen Achsen-
  oder Vorzeichenwechsel geben. Die Aussparung wird nicht nochmals durch
  die Blaupausentransformation geschickt.

### Umgang mit Umfeldobjekten

- Der Grundboden erhält ein echtes Loch, keine darübergelegte Abdeckplatte.
- Grün-/Wasserpolygone vollständig **innerhalb** der Aussparung werden nur
  beim Rendern ausgelassen. Die Originaldaten werden **nicht gelöscht**.
  Die ausgelassenen Quellindizes werden im Renderbericht ausgewiesen.
- Grün-/Wasserpolygone, die den Rand berühren oder kreuzen, sowie Polygone,
  die die ganze Aussparung umschließen, führen zum **Abbruch**.
- Gebäude innerhalb oder an der Aussparung führen zum **Abbruch**.
  Niemals automatisch filtern, versetzen oder löschen.
- Straßen werden einschließlich gezeichneter Breite und Verbindungsecken
  geprüft. Es genügt nicht, nur die Stützpunkte zu prüfen: auch eine
  durchlaufende Straße mit allen Punkten außerhalb kann die Aussparung kreuzen.
  Betroffene Straßen führen zum **Abbruch**.
- Baumpositionen in/an der Aussparung führen zum **Abbruch**.
- Keine automatische Beschneidung kreuzender Objekte ist implementiert.
  Solche Fälle mit Quellen und Geometrie melden; eine weitere Lösung oder
  Datenänderung benötigt einen gesonderten Auftrag.
- Fehlermeldungen sind kein Anlass für pauschale Polygonbereinigung.

## 4. Augsburg-Geländebeleg

- Höhe **7,7 m**, Aussparung aus der konvexen Hülle des Quellmeshes
  `center1_28` (Umlaufplatte), **36 Punkte**.
- Die Hülle wurde gegen das V2-Geometriebinary nachgerechnet; die
  gelieferten auf 0,1 m gerundeten Eckpunkte stimmen überein.
- Grundboden liegt damit bei **7,35 m**; Umlaufplatte ungefähr **7,7–7,72 m**.
  Der verbleibende Versatz von etwa **0,35–0,37 m** wird nicht kaschiert.
- Vollständiger Quellbestand bleibt erhalten: **26 Gebäude, 189 Straßen,
  47 Grünflächen, 0 Wasserflächen**.
- Nur **`green[3]`** (OSM-Spielfeldpolygon) entfällt in der Renderausgabe
  innerhalb des Lochs. Es wurde **nicht aus der Datenbank entfernt**.
- Keine Straßen-, Gebäude- oder weiteren Flächenkonflikte bei der neuen
  Rendererprüfung. Keine Böschungen, Rampen oder sonstiges Relief erfunden.
- Diese Lösung ist eine quellbezogene ebene Höhenanpassung, keine
  Vermessung eines vollständigen realen Geländemodells.
- Keine neue Höhe für andere Stadien ableiten oder ungefragt deklarieren.

## 5. Verifikation und Übergabe zukünftiger Pakete

1. Identität über FMI und Verein mit dem lokalen Stand abgleichen.
   Fremde interne IDs und Vorschaukapazitäten nicht übernehmen.
2. Vorherstand sichern; Änderungen an exakt benannte Daten binden.
   Nach dem Commit den persistierten Stand erneut gegen Schutzdaten prüfen.
3. Alle Manifestkopien, Hashes, Texturen und Binärdaten prüfen.
   Bestehende Meshes über Quell-IDs vergleichen, nicht über Listenpositionen.
4. Spielfeld unabhängig an Linienmittelachsen nachmessen.
5. Mit aktuellem Projekt-Renderer rendern, nicht nur dem Paket-Mock.
   Dach an/aus, Tag/Nacht, niedrige Ansichten von allen Seiten,
   Geländeübergänge, Draufsicht und Innenansichten prüfen.
6. Quellzustand, hypothetisches Mock-Ziel und tatsächlichen Replit-Endstand
   eindeutig kennzeichnen. Historische Bilder sind keine neue Abnahme.
7. Bestehende Stadien ohne Geländedeklaration müssen unverändert bleiben.
   Browsermodule und Einstiegsskripte bei Änderungen gemeinsam cache-busten.
8. Private Backups, Zugangsdaten und temporäre Sitzungen aus dem Paket lassen.
9. Ein Original-Bundle, das in Replit nicht vorliegt, wurde hier nicht neu
   extrahiert. Export-/Binaryprüfung nicht als Originalextraktion ausgeben.
10. Korrektur und Paketlieferung erlauben weiterhin **keine Registrierung,
    keinen Upload, keine externe Übertragung und keine Veröffentlichung**.
