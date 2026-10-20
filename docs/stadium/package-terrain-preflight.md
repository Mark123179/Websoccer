# Geländekonflikte vor einer Paketübernahme prüfen

```bash
python scripts/check_stadium_package.py \
  --source /pfad/paket/geometry.json \
  --manifest /pfad/paket/models/915.json
```

Die Prüfung liest ausschließlich lokale JSON-Dateien. Sie registriert kein
Modell, lädt nichts hoch, schreibt keine Datenbank und verändert weder
Quellobjekte noch Dateien. Registrierung und Import bleiben separate,
ausdrücklich freizugebende Schritte. Paket-JavaScript wird nicht ausgeführt.
Ein Archiv zuvor separat entpacken und die vollständige Nachher-JSON wählen.

## Eingaben und Koordinaten

`--source` akzeptiert:

- Editor-Geometrie mit `bg`, `surroundings`, `meta` und/oder `blocks`.
  Dieselbe Projektion wie im gemeinsamen Runtime-Renderer verwendet
  `bg.<Liste>` vor `surroundings.<Liste>` und Gebäude-`poly`/`h`.
- Runtime-Paket mit `surroundings` und `frame`.
- Natürliches Umfeldpaket mit `data` und `frame`.
- Reine Umfelddaten mit `green`, `water`, `roads`, `buildings`,
  `buildingHeights`, `trees`, optional `groundLevel`/`groundCutout`.

Explizite `buildingParts` im gemeinsamen Unity-Umfeld werden einschließlich
NHN-Bezug, vollständiger Grundrisspartition und aller Teilflächen geprüft;
siehe [Teilkörpervertrag](building-parts-contract.md). Die Deklaration
bleibt auch bei der Legacy-`bg`-Projektion erhalten.

Für reine Umfelddaten ohne Rahmen gilt wie im Renderer `[0,0]`/Winkel `0`.
`--frame /pfad/frame.json` überschreibt den Rahmen explizit mit
`{"fieldC":[…,…],"axisTheta":…}` (Winkel in Radianten).
`--manifest` liest ausschließlich `calibration.surroundingsAxes`.
Ohne Achsendeklaration gilt wie im Renderer `NORD:+z`, `WEST:-x`.
Für ein gedrehtes/gespiegeltes Zielmodell dessen tatsächliches Manifest angeben.
Ein vorhandenes ungültiges Achsenpaar wird nicht durch Standardwerte ersetzt.
`groundCutout` liegt bereits in **Modell-(x,z)-Metern**, wird also nicht nochmals
mit dem Editor-Rahmen transformiert.

Keine vereinsabhängigen Baumkataloge werden ergänzt. Für eine Prüfung des
tatsächlichen Live-Zustands dessen vollständig projiziertes Runtime-Paket
verwenden. Diese Geländeprüfung ersetzt weder Modell-/Asset-Prüfsummen noch
eine visuelle Abnahme oder die vollständige Natural-Paketschema-Prüfung.

## Bericht und Status

`--json` liefert `ok`, `terrainDeclared` und `findings` mit
`severity`, `path`, `code`, `message`. Quellindizes sind **nullbasiert**.
Beispiele: `bg.buildings[3].poly`, `surroundings.water[2]`,
`data.trees[17]`, `roads[4]`.

- Exit `0`: keine blockierenden Konflikte. Hinweise können enthalten sein.
- Exit `1`: ungültige Daten, räumliche Konflikte oder Prüfung nicht ausführbar.
- Ungültige Geländedeklaration/Rahmen: erst diese korrigieren; danach kann
  die räumliche Prüfung erfolgen.
- Kreuzende, berührende oder die Aussparung umschließende Grün-/Wasserflächen
  werden abgelehnt. Vollständig innenliegende Flächen sind **Hinweise**,
  weil der Renderer sie ausschließlich in der Darstellung ausblendet.
- Straßen einschließlich ihrer gezeichneten Breite (`w × 1,25` je Seite)
  und achteckigen Verbindungen, Gebäude und Baumpositionen einschließlich
  Randberührung werden wie im Renderer geprüft.
- Ohne Geländedeklaration bleibt die Baseline erhalten: keine erfundene
  Aussparung, keine automatische Geländehebung, keine räumlichen Konflikte
  gegen ein nicht deklariertes Loch. Ungültige Quellgeometrie bleibt ein Fehler.

Die numerischen Geländeprüfungen aus Python laufen zuerst. Anschließend
verwendet eine lokale Node-Prüfung den unveränderten produktiven
`buildDortmundSurroundings` mit der mitgelieferten Three.js-Bibliothek
**ohne WebGL/Browser**. Jedes Quellobjekt wird separat geprüft, sodass ein
Fehler weitere Quellindizes nicht verdeckt. Erzeugte CPU-Geometrien werden
sofort freigegeben. Node.js muss verfügbar sein; ein fehlender Prüfer wird
ausdrücklich als Fehler gemeldet. Für automatisierte Aufrufer steht
`stadium_editor.package_preflight.inspect_package` zur Verfügung.
