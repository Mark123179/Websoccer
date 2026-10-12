# Einheitlicher Spielfeldvertrag

Die Linienmittelachsen müssen **105 × 68 Meter** bilden. Die zulässige
numerische Abweichung beträgt je Dimension **0,02 m**; sie dient nur der
Float-/Exportgenauigkeit, nicht der Freigabe anderer Feldgrößen.
Der 2D-Vertrag steht in `stage/pitch_geometry.js`; ein sprachübergreifender
Test vergleicht ihn mit dem Python-Prüfvertrag.

## Paket prüfen und registrieren

```sh
python scripts/check_stadium_pitch.py \
  --manifest <paket>/models/<fmi>.json \
  --geometry <paket>/stadium-models/<fmi>/<assetVersion>/geometry.bin

python scripts/register_stadium_model.py --package <paket> --fmi <fmi>
```

Beide Wege messen die tatsächlichen Dreiecke aus `geometry.bin` neu. Die
Registrierung prüft Hashes und Spielfeld **vor jedem Storage-Upload und
vor Veröffentlichung der Registry**. Ein behaupteter Messwert im Manifest
ersetzt diese Prüfung nicht. Bestehende Registrierungen und Stadionmodelle
werden durch die Prüfung weder verändert noch skaliert.

Die Einzelprüfung schreibt JSON auf stdout, Exitcode 0 bei Erfolg und 1 bei
Fehler. Für Legacy-Exporte ohne deklarierten Geometriehash erzeugt nur der
Einzelprüfer den Hash aus der Eingabedatei; die Registrierung verlangt
weiterhin die vorhandenen Manifest-Prüfsummen.

## Messverfahren und Grenzen

Unterstützt wird das Linienmaterial `000STADIUMLINE` mit geometrischen
Linienbändern in Quell-Weltkoordinaten, zentriert um den Ursprung, in Metern,
parallel zu X/Z (beide Vierteldrehungs-Orientierungen).
Die Dreiecke werden in mehreren inneren Querschnitten geschnitten:

- Seitenlinien: längs bei −40, −27, −13, 13, 27, 40 m.
- Torlinien: quer bei −27, −23, −13, 13, 23, 27 m.

Nur identische, durchgehende schmale Bänder (1–25 cm) an **allen**
Querschnitten zählen; ihre Bandmittelpunkte ergeben die Maße.
Die durchgehende Mittellinie wird separat ausgeschlossen.
Linienbreite, kurze Hintertormarkierungen, Eckbögen und angrenzender Rasen
gehen nicht als äußere Feldgrenzen ein. Es wird ausdrücklich **nicht**
die Bounding Box aller Linien als Feldmaß verwendet.

Fehlende, beschädigte, mehrdeutige, texturbasierte, versetzte oder anders
gedrehte Linien werden als **nicht automatisch messbar** gemeldet und
blockieren die Registrierung. Das ist kein Maßnachweis und kein stiller
Erfolg. Für solche Pakete muss die Quellgeometrie separat geprüft und ein
belegter Messadapter ergänzt werden; keine automatische Skalierung.

## Vier Original-Kontrollfälle reproduzieren

```sh
python scripts/check_stadium_pitch.py --controls
```

Dieser rein lesende Pfad verwendet Dortmunds mitgelieferte Originaldateien
und die hashgebundenen Registry-Originale aus App Storage für BayArena,
Borussia-Park und Allianz Arena. Er braucht die konfigurierte
Storage-Verbindung, aber weder Datenbankänderungen noch ignorierte
`generated-artifacts` früherer Arbeitsumgebungen. Fehlt ein Original oder
der Storage-Zugriff, schlägt die Kontrolle sichtbar fehl.

Erwartete Mittellinienmaße: alle vier 105 × 68 m; die größeren und
unterschiedlichen Rasenflächen sind keine Spielfeldmaße.
Die JSON-Ausgabe enthält Geometriehash, Messmethode, Meshnamen, Achse,
Schnittpositionen und gemessene Randbänder für eine erneute Prüfung.

```sh
python manage.py test stadium_editor.test_pitch_validation \
  stadium_editor.test_model_registry \
  stadium_editor.test_register_stadium_model --verbosity=1
node --test stadium_editor/tests_js/test_stadium_pitch_geometry.mjs
```

Die lokalen Tests brauchen keinen Storage-Zugriff. Sie enthalten Dortmunds
Original, verschiedene Linienbreiten, störende Hintertormarkierungen,
Vierteldrehung, unbekannte Geometrie, beschädigte Daten sowie abweichende
110 × 68, 105 × 70 und 100 × 64-m-Felder als Negativfälle. Sie prüfen
außerdem, dass abgelehnte Registrierungen keinerlei Storage-Aufruf auslösen.
