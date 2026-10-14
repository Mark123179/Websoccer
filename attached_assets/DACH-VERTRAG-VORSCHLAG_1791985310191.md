# Dachtrennung WWK ARENA — gelieferte Lösung im vorhandenen Vertrag und optionaler Vertragsvorschlag

## 1 · Gelieferte Lösung (kein Renderer-Patch, kein neues Manifestfeld)
Der vorhandene generische Vertrag (`calibration.roofMeshPrefixes` = startsWith, `calibration.roofMinHeight`) wird unverändert genutzt. Die Mehrdeutigkeit der Quellnamen (`center1_2` = Hauptdach, `center1_20…39` = Ränge) wird **im Export** aufgelöst: die 59 nach Funktion bestimmten Dachmeshes tragen im Manifest den Namen `DACH_<Quellname>` (Export Fassung 7, `--roof-names dach_namen.json`). Geometrie, Transformation, Materialien, Reihenfolge und Binärdaten sind unverändert; `pathId` (Unity-Objekt-ID) und `hierarchy[0]` (= Quellname) bleiben im Manifest, `dach_aufbereitung_bericht.json` listet jede Umbenennung mit Hierarchie, Material, Bounds und Funktion. Kalibrierung: `roofMeshPrefixes ["DACH_"]`, `roofMinHeight −1` → jedes Dachmesh schaltet vollständig, kein Körpermesh wird berührt.

Nachrechnung (`quellbelege/nachweise.json`, Regel identisch zum Renderer): **Dach 96.252 / 96.252 Dreiecke**, Körper 0 Dachdreiecke, kein gelistetes Mesh mit Körperdreiecken, kein ungelistetes Mesh mit Dachdreiecken. Fassung 1 (`nachweise_fassung1_roofMinHeight22.json`): 95.069 Dach, 6 falsch entfernte Körperdreiecke, 1.853 verbliebene Dachdreiecke — behoben.

**Bewusst im Körper (begründet):** `front3_27`, `front3_27.001` (Beton-Fassadenstützen/Kolonnade, Fußpunkt auf Umlaufniveau 7,7 m, bis 22,1 bzw. 26,2 m; reale Außenerscheinung, 720 Dreiecke). Alternative auf Wunsch: in `dach_namen.json` aufnehmen → Kolonnade schaltet mit dem Dach (Re-Export, neue assetVersion).

## 2 · Optionaler Vertragsvorschlag (nur falls Umbenennung im Export nicht gewünscht ist)
Generische Erweiterung der Kalibrierung, abwärtskompatibel, kein vereinsspezifischer Code:

```json
"calibration": {
  "roofMeshNames": ["center1_2", "center1_3.003", "faros.001", "center3_df_0", "center3_df_1", "front3_0", "…"],
  "roofMeshPrefixes": [],
  "roofMinHeight": -1
}
```

- `roofMeshNames` (optional, Liste exakter Meshnamen): Kandidat = Name ∈ `roofMeshNames` **oder** startsWith(`roofMeshPrefixes`); alles Übrige wie bisher (Crowd nie Dach, Höhenschwelle `roofMinHeight`).
- Renderer (`unity_stadium_scene.js`, Zeilen 94–96): `const roofCandidate = !entry.name.startsWith(crowdPrefix) && (names.has(entry.name) || (!prefixes.length && !names.size) || prefixes.some(p => entry.name.startsWith(p)));` mit `names = new Set(calibration.roofMeshNames || [])`.
- Registry-Validierung (`model_registry.py`): optionales Feld, Liste eindeutiger Strings, jeder Name muss in `meshes[].name` vorkommen (sonst Fehler); `validate_surroundings_axes` unberührt.
- `dach_nachweis.py` würde die gleiche Regel spiegeln (Set-Prüfung vor Präfixprüfung).
- Migration: bestehende Manifeste ohne das Feld verhalten sich identisch. Für Augsburg entspräche `roofMeshNames` genau der Liste in `dach_namen.json` (59 Quellnamen), dann ohne `DACH_`-Umbenennung.

Implementierung bleibt ein gesonderter Auftrag an Replit; dieses Paket setzt das Feld **nicht** voraus.
