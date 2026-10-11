# Anleitung: Weitere Stadien im gemeinsamen räumlichen Modus

Stand: 10. Oktober 2026. Referenzen: freigegebener Elversberg-Modus und
abgenommene BVB-Fünfer-Serie. Diese Anleitung beschreibt den räumlichen
Modus, nicht die älteren Fotohintergrund-Experimente.

## 1. Ziel und unveränderliche Grenzen

Jeder Verein erhält sein eigenes Stadion und seine eigene Umgebung.
Gemeinsam sind Darstellungskonzept, Feldkamera und Verarbeitungsschnittstellen,
nicht die Dortmunder oder Elversberger Ortsobjekte.

- 2D-Editor, 3D-Editor und Spielansicht beziehen ihre Vereinsdaten aus dem
  aktuellen Bestand. Modelladapter verbinden die unterschiedlichen Quellformate.
- Ein Luftbild darf zur Prüfung dienen; es wird nicht als alter Fotohintergrund
  hinter das räumliche Stadion gesetzt.
- Die freigegebene Feldkamera wird übernommen, nicht pro Stadion neu angepasst.
- Die Anzeige ändert weder Managerzuordnung noch Wirtschaftskapazität,
  Finanzen, Stadionausbau oder gespeicherte Managergestaltung.
- Neue Vereine werden einzeln vorbereitet und abgenommen. Kein automatischer
  Massenimport oder Veröffentlichungsauftrag.

## 2. Woher welche Daten kommen

| Bestandteil | Bevorzugte Quelle | Verarbeitung und Grenzen |
| --- | --- | --- |
| Stadionkörper, Tribünen, Dächer, Träger | Vom Nutzer bereitgestelltes, zur Nutzung freigegebenes 3D-Modell, z. B. ein Unity-Bundle oder ein vorhandener Modellexport | Meshes, Transformationen, UVs und Materialzuordnung auslesen. Original und abgeleiteten Browserexport getrennt erhalten. |
| Stadion ohne vorhandenes 3D-Modell | Reale Grundrisse, belegte Maße, Dach-/Tribünenreferenzen; daraus ein quellenbasiertes Blueprint-V2-Modell | Rekonstruktion ausdrücklich kennzeichnen. OSM allein liefert kein vollständiges Tribünen-, Sitz- oder Dachmodell. Kein ähnliches fremdes Stadion als Ersatz. |
| Spielfeld und Stadiongrundriss | OpenStreetMap: tatsächliches Spielfeld und Stadionobjekte, mit stabilen OSM-IDs | Mittelpunkt, Längsachse, Umriss und Ortsbezug bestimmen. Die gemeinsame Spielfelddefinition beträgt 105 × 68 m; Originalmeshes nicht still auf diese Maße verzerren. |
| Straßen, Häusergrundrisse, Wasser, Parkplätze, Grünflächen | OpenStreetMap, bei Bedarf geprüft gegen amtliche Geodaten | Echte Polygone und Linien übernehmen; Auswahlgebiet dokumentieren. OSM-Daten sind nicht überall vollständig. |
| Gebäudehöhen | Passende amtliche LoD1-/LoD2-Daten oder tatsächlich vorhandene OSM-Höhenangaben | Gebäude räumlich zuordnen, Höhenbezug und Gelände prüfen. Gemessene, abgeleitete und schematische Höhen getrennt ausweisen. |
| Bäume und Vegetation | Kartierte Einzelbäume, Baumreihen, Wald-/Grünflächen | Kartierte Punkte erhalten. Aus Flächen erzeugte Gruppen deterministisch erzeugen und als schematisch kennzeichnen; Baumart und Höhe nicht als vermessen behaupten. |
| Gelände | Wenn verfügbar: amtliches DGM/DEM mit geeignetem Maßstab und Nutzungsrecht | Höhen in ein gemeinsames Bezugsniveau zum Spielfeld umrechnen. Fehlt geeignetes Gelände, die flache Bezugsfläche ausdrücklich nennen. Gebäudehöhe ersetzt keine Geländehöhe. |
| Flutlicht | Echte Light-/Transform-Daten und Leuchtenmeshes des Modells, gegebenenfalls belastbare externe Bestandsunterlagen | Montageort, Richtung und Identität belegen. Die Browser-Lichtstärke darf kalibriert werden; das ist keine originalgetreue Unity-Shaderübernahme. |
| Farben, Sitzgestaltung und Kapazität | Aktueller Datenbankbestand des betreffenden Vereins | Geometrie/Design lesen. Wirtschaftskapazität kommt aus `Stadium`, nicht aus der Anzahl exportierter Stühle. |
| Luftbilder und Fotos | Amtliche Orthofotos und rechtmäßig nutzbare aktuelle Referenzfotos | Lage, Ausrichtung und Bauzustand prüfen. Eine Draufsicht belegt weder Gebäudehöhe noch die sichtbare Fassade aus der Spielkamera. |

OSM stammt von OpenStreetMap-Mitwirkenden und unterliegt ODbL. Amtliche
Daten haben eigene Nutzungsbedingungen. Für bereitgestellte 3D-Modelle
Nutzungs- und Weitergaberechte klären: Ein vorhandenes Bundle ist keine
automatische Erlaubnis, es an einen externen Dienst weiterzugeben.

**Vorhandene Beispiele, keine universellen Datenquellen:**

- BVB-Modell: bereitgestelltes Unity-Bundle und separate Sitzdatei.
  Elternrotationen sind im Mesh-Export gebacken; die Sitzdatei braucht einen
  eigenen Achsenabgleich. Browsermaterialien sind teilweise vereinfacht.
- BVB-Umfeld: eigener OSM-Auszug und kartierte Baumdaten.
- Elversberg-Höhen: LVGL-LoD2-Zuordnung. Einige Höhen bleiben bedingt;
  nicht zugeordnete Häuser sind schematisch, nicht amtlich vermessen.
- LVGL-Beispieldienst: `https://geoportal.saarland.de/gdi-sl/inspirewfs_Gebaeude_3D_LoD2`.
- NRW-Orthofoto-Beispiel: `https://www.wms.nrw.de/geobasis/wms_nw_dop`.

Für einen neuen Standort passende regionale Dienste und deren aktuelle
Lizenz prüfen. Die genannten URLs sind Projektbeispiele, keine neue
Live-Verfügbarkeitsprüfung.

## 3. Verarbeitungsschritte

### Schritt A: Verein und Ausgangszustand festhalten

Explizite Club-PK, FM-Asset-ID, Stadionname, Standort und aktuellen Bauzustand
festhalten. Club-PK und FM-ID sind unterschiedliche Identitäten.
Kapazität, Managerzuordnung, Geometrie und Gestaltung vor schreibenden
Änderungen sichern. Zunächst außerhalb des produktiven Bestands arbeiten.

### Schritt B: Quellenpaket erstellen

Rohmodell, Sitzdaten und lokale Geodaten sammeln. Zu jeder Quelle
Herkunft, Abrufdatum, Lizenz, Koordinatensystem, Einheiten und Prüfsumme
festhalten. Relevante OSM-IDs und offene Datenlücken auflisten.
Prüfen, ob die referenzierten Dateien tatsächlich vorhanden sind:
Ein älterer erfolgreicher Render ersetzt keine fehlenden Rohdaten.

### Schritt C: Gemeinsamen Ortsrahmen bestimmen

Geografische Koordinaten in lokale Meterkoordinaten überführen. Das
Spielfeldzentrum ist der Bezugspunkt. Spielfeldlängsachse, Querachse,
geografischer Norden und Höhenachse ausdrücklich dokumentieren.

Anschließend den Modellrahmen dagegen registrieren. Unity-Elternrotationen
und separate Sitzdateirahmen beachten. Eine nötige Drehung wird als
Adaptertransformation geführt, nicht in die Rohquelle hineingeschrieben.
Gebäude, Straßen und Vegetation folgen demselben Ortsbezug; sie werden
nicht für ein schöneres Bild unabhängig verschoben.

### Schritt D: Stadion und Umgebung browserfähig aufbereiten

Das Modell auf die benötigten Teile exportieren und Texturen für den
Browser aufbereiten. Dreiecksindizes, Materialien, Bauteilnamen, Quell-IDs
und Abmessungen validieren. Ungeklärte Shaderwirkungen oder ergänzte
Fassaden als Vereinfachung/Rekonstruktion kennzeichnen.

Die Umgebung aus echten Flächen und Linien aufbauen: Straßen, Gebäude,
Grünflächen, Wasser und Vegetation. Höhen nur mit ihrer tatsächlichen
Belegqualität übernehmen. Bei unbekannten Werten keine heimlichen
„typischen“ Gebäudehöhen als reale Messungen ausgeben.

Ohne verfügbare Umfeldquelle keine Ersatzstadt erzeugen. Fehlende
optionale Umgebung mit Warnung auslassen. Ein benötigtes fehlendes
Stadionmodell nicht durch ein anderes Stadion ersetzen.

### Schritt E: Bestehende Datenstruktur und Ansichten verbinden

Gespeicherte Geometrie und Managergestaltung bleiben getrennt:
`StadiumGeometry` enthält Geometrie, `StadiumDesign` die Gestaltung.
`current_live_scene()` stellt den aktuellen Bestand für Runtime-Ansichten
zusammen. Ein spezieller Originalmodell-Renderer erhält einen passenden
Adapter; er darf nicht den BVB-Pfad für einen anderen Verein zweckentfremden.

Alle Ansichten müssen die richtigen aktuellen Vereinsdaten beziehen.
Ungespeicherte Editoränderungen sind nur Vorschauen. Farben aus einer
aktuellen Managergestaltung nicht durch einen alten Modellexport ersetzen.

Für einen neuen Blueprint zuerst eine geprüfte Vereinszuordnung einrichten.
Erst danach ist beispielsweise dieser bestehende Befehl nutzbar:

```text
python manage.py import_stadium_blueprint_v2 --club-id <GEPRUEFTE_CLUB_PK> --dry-run
```

Der Befehl ist kein universeller Unity-Importer. Ein schreibender Import
mit `--apply` benötigt eine gesonderte Freigabe; er kann auch das Design
betreffen. Vorher Backup und Erhalt vorhandener Gestaltung prüfen.

### Schritt F: Kamera, Dach und Licht

Die freigegebene `approved-elversberg`-Projektion aus `study_camera.js`
verwenden. Nicht erneut anhand der Stadiongröße oder einer geschätzten
Feldbreite zoomen. Für native Modellachsen die Kamerapose passend
transformieren und mathematisch vergleichen.

Die Orientierung des Stadions lösen, ohne die gemeinsame Kameraseite
umzukehren. Vorne störende Bauteile nur in der Spielansicht ausblenden.
Der Dachschalter verändert Sichtbarkeit, keine gespeicherte Geometrie.

Tag/Nacht wechselt Lichtzustände, nicht den Ortsbestand. Reale
Flutlichtquellen anhand ihrer Quellobjekte prüfen. Die sechs BVB-Gruppen
sind kein allgemeiner Sollwert für andere Stadien. Fehlende echte
Leuchten dürfen nur nach ausdrücklicher Zustimmung schematisch dargestellt
und entsprechend beschriftet werden.

### Schritt G: Prüfen und abnehmen

1. Quellen, Vereinsidentität, Einheiten und Transformationen prüfen.
2. Kapazität, Managerzuordnung, Finanzen und nicht freigegebene Daten unverändert nachweisen.
3. Aktuelle Gestaltung und Datennutzung in beiden Editoren und im Ticker prüfen.
4. Kameramatrix/Pose mit der Referenz vergleichen; Dach und Tag/Nacht prüfen.
5. Die fünf aktuellen Ansichten tatsächlich rendern und visuell prüfen.

Die vollständige Abnahmereihe:

- 2D-Editor.
- 3D-Editor.
- Ticker bei Tag mit Dach.
- Ticker bei Tag ohne Dach.
- Ticker bei Nacht mit Dach und eingeschaltetem Flutlicht.

Erst diese vollständige Serie vorzeigen. Keine Zwischenbilder, alten
Fotomodusbilder oder Bildmontagen als fertigen neuen Runtime-Stand ausgeben.
Für Software-WebGL darf eine temporäre Aufnahmefläche den Originalrenderer
mit aktuellem Datenbestand ausführen. Aufnahmehilfen werden nicht dauerhaft
in die Anwendung eingebaut. Ein zurückgekehrter Renderaufruf allein ist
noch kein fertiger Bildnachweis.

## 4. Was bereits vorhanden ist – und was noch Einzelarbeit bleibt

Vorhanden sind der räumliche Elversberg-Pfad, der BVB-Originalmodellpfad,
die gemeinsame Feldkamera, Blueprint-V2-Verträge und Importprüfungen.
**Ein fertiger universeller Importer für beliebige Stadionmodelle
existiert dadurch noch nicht.**

Pro neuem Stadion bleiben Quellenprüfung, Achsenregistrierung, Haupttribünen-
und Dachzuordnung, Materialbehandlung, Leuchtenprüfung und Abnahme nötig.
Dortmund-/Elversberg-Skripte sind teilweise fest auf ihre Quellen zugeschnitten:
als Referenz verwenden, nicht unverändert mit einer fremden Datei ausführen.

## 5. Arbeitsteilung mit Claude oder einem anderen Agenten

**Empfehlung:** Quellenrecherche und ein klar begrenztes, schreibfreies
Vorbereitungspaket können extern erfolgen. Integration und Abnahme im
bestehenden Projekt durchführen, wo tatsächliche Daten, Adapter,
Referenzkamera und geschützte Gestaltung verfügbar sind.

Claude kann auch die Integration übernehmen, wenn er wirklich Zugriff auf
dieselben erforderlichen Projektdateien, zulässigen Rohassets und eine
Testumgebung hat. Ein Chat mit Bildern allein reicht dafür nicht.

Ein externes Vorbereitungspaket sollte enthalten:

- Eindeutige Stadion-/Vereinsidentität und bestätigten Bauzustand.
- Zulässige Rohquellen oder genaue beschaffbare Quellenreferenzen.
- `sources.json`: Herkunft, Lizenz, Datum, Einheiten, Prüfsummen und Objekt-IDs.
- `transformation.json`: Modell-/Georahmen, Mittelpunkt, Achsen und Adapter.
- `surroundings.json`: echte Ortsgeometrien mit Herkunft und Höhenqualität.
- Modell-/Dach-/Material-/Leuchteninventar sowie offene Fragen.
- Reproduzierbare Verarbeitungsskripte und ein kurze Ausführungsanleitung.

Diese Dateinamen sind ein empfohlener Übergabevertrag, keine Behauptung,
dass jeder bestehende Importer sie bereits automatisch einliest.
Keine Zugangsdaten, Datenbankdumps oder personenbezogenen Managerdaten
an einen externen Chat geben. Große Rohassets nicht in Git einchecken.

## 6. Kopierbarer Auftrag für die externe Vorbereitung

```text
Bereite [STADION, VEREIN, STANDORT, BESTAETIGTER BAUZUSTAND] für den
gemeinsamen räumlichen Stadionmodus dieses Projekts vor.

Referenzen sind der freigegebene Elversberg-Modus und die abgenommene
BVB-Serie. Das Stadion benötigt sein eigenes Modell und seine eigene
Umgebung. Kein Fotohintergrund, keine Übernahme fremder Ortsobjekte.

Arbeite zunächst ausschließlich schreibfrei. Verwende nur bereitgestellte
oder rechtmäßig beschaffte Quellen. Dokumentiere Herkunft, Lizenz, Datum,
Einheiten, Koordinatenrahmen, stabile Objekt-IDs und Prüfsummen.

Ermittle Spielfeldzentrum und Achsen, registriere den Modellrahmen und
bereite reale Straßen, Gebäudegrundrisse, Grünflächen und Vegetation auf.
Trenne gemessene, abgeleitete, schematische und unbekannte Höhen.
Erfinde weder Häuser, Geländehöhen noch reale Leuchtenpositionen.
Kennzeichne Rekonstruktionen und ungeklärte Materialien ausdrücklich.

Liefere ein eigenständiges Vorbereitungspaket mit Quellenmanifest,
Transformation, Umfelddaten, Modell-/Dach-/Leuchteninventar,
Verarbeitungsskripten und offenen Fragen. Bestehende vereinsbezogene
Skripte nicht blind ausführen; deren Zielpfade dürfen nicht überschrieben werden.

Keine Änderung an Managerzuordnung, Wirtschaftskapazität, Finanzen,
Ausbau oder gespeicherter Gestaltung. Keine Datenbankimporte,
Produktionsänderungen oder Veröffentlichung.

Die Integration übernimmt anschließend das bestehende Projekt.
Die gemeinsame approved-elversberg-Kamera bleibt unverändert.
Die spätere Abnahme umfasst gemeinsam: 2D-Editor, 3D-Editor,
Ticker mit Dach, Ticker ohne Dach und Nacht mit Dach und Flutlicht.
```

## 7. Technische Einstiegspunkte im Projekt

- `docs/stadium/model-manifest.md`: verbindlicher Registry-/Kalibrierungsvertrag und Übergabeablauf für Claude.
- `stadium_editor/model_registry.py`: validierte Manifest-Registry unter `blueprints/v2/models/<fmi>.json`.
- `stadium_editor/unity_runtime.py`: datengetriebene Originalmodell-Präsentation.
- `scripts/export_stadium_model.py`: parametrischer Offline-Export mit vollständiger Kalibrierung und Quellbelegen.
- `python manage.py check_stadium_model --fmi <id> --assets`: rein lesende Manifest-/Asset-Prüfung.
- `stadium_editor/scene_service.py`: aktueller Runtime-Bestand.
- `stadium_editor/dortmund_runtime.py`: BVB-Präsentationsadapter.
- `stadium_editor/static/stadium_editor/study_camera.js`: Referenzprojektion.
- `stadium_editor/management/commands/import_stadium_blueprint_v2.py`: geprüfter Blueprint-Import.
- `scripts/export_dortmund_miniature.py`: beispielhafter Offline-Mesh-Export.
- `scripts/export_stadium_study_lights.py`: beispielhafte Leuchten-Quellprüfung.
- `docs/stadium/elversberg-shared-runtime.md`: Elversberg-spezifische Grenzen.
- `docs/dortmund-original-miniatur.md`: BVB-Quellformat und Exportgrenzen; historische Prüfstände von aktueller Freigabe unterscheiden.
- `.agents/memory/software-webgl-screenshots.md`: Aufnahmegrenzen und Prüfhinweise.

Die freigegebenen Vergleichsbilder liegen derzeit unter
`generated-artifacts/bvb-spatial-review/`. Dieser Ordner ist bewusst
ignoriert und wird nicht automatisch durch einen Git-Checkout übertragen.
Für eine externe Übergabe die Bilder ausdrücklich separat bereitstellen.

Für einen bereits vorhandenen Verein mit passender Stadiongeometrie ist
die Originalmodell-Anbindung nun datengetrieben: **Manifest als
`models/<fmi>.json` + Assets hochladen + `check_stadium_model` + Worker
neu starten**. Kein hart verdrahteter Vereinszweig ist dafür erforderlich.
Claude liefert Manifest, kalibrierte Assets, Quellbelege und die fünf
Ansichten; fehlende Kalibrierung ist ein Fehler und hat keine Standardwerte.
Die Registrierung ist keine Freigabe für einen DB-Import oder Änderungen
an Kapazität, Finanzen, Managerzuordnung, Ausbau oder gespeicherten Designs.
