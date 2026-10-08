# Spielfeldzentrierte Stadionstudie

Geschützte, rein lesende Ansicht: `/live/stadium-study/`, nur für Admins.
Der vorhandene Editor, der Admin-Testticker, echte Spiele, Spielzeiten,
Kapazitäten und gespeicherte Ausbauzustände bleiben unverändert.

## Empfehlung und Grenzen

Empfohlen ist die **Schnittansicht**: steilerer Blick, vollständige Feldfläche
von ungefähr 33 bis 93 Prozent der Bildhöhe. Die perspektivische Alternative
zeigt mehr Stadionrahmen; ihr Feld reicht ungefähr von 45 bis 93 Prozent.
Die kameraseitige Tribüne ist eine Darstellungs-Ausblendung, kein Abriss.
Die Unterschiede sind Kamerahöhe, Neigung und Bildaufbau, nicht nur Farbwechsel.

Dies ist eine visuelle Studie, **keine optische Nutzerabnahme und keine fertig
fotorealistische Spielansicht**. Die Figurenbewegung ist ausdrücklich eine
Demonstration; es werden keine Simulationsdaten erzeugt oder verändert.

## Gemeinsamer Feldvertrag

* Spielkoordinaten: 105 × 68 m; gemeinsame Tore, Linien, 2D-Figuren und Ball.
* Referenzformat: 1880 × 940 px, auf beiden Vereinsflächen proportional skaliert.
* Perspektive: Höhe 72 m, Abstand 76 m hinter der Seitenlinie, Neigung 36°.
* Schnittansicht: Höhe 98 m, Abstand 76 m, Neigung 44°.
* Die Kameraeinpassung verwendet ausschließlich das Spielfeld, niemals
  Vereinskapazität, Stadion-Bounds, Dach oder Ausbau.
* Dortmund: originale Unity-Meshes. Der Adapter normalisiert das Quellfeld
  (ungefähr 105,900 × 68,160 m) auf 105 × 68 m und dreht rechtshändig um 90°.
  Keine Spiegelung; Originaldateien werden nicht verändert.
* Elversberg: eigene vermessene Blaupause, um 180° in den gemeinsamen
  Koordinatenrahmen gedreht. Keine Skalierung nach Kapazität und keine
  Behauptung gleichwertiger Unity-Originalqualität.
* Die Studie fixiert die Szenenrotation explizit; automatische
  Haupttribünen-Einpassung des normalen Editors bleibt im Standard unverändert.

## Leuchtennachweis

`scripts/export_stadium_study_lights.py` untersucht das originale Unity-Bundle
offline. Der Webprozess liest nur den exportierten Nachweis.

Von 863 Lichtkomponenten erfüllen 64 Spot-Light-Komponenten die strenge
Studienauswahl: eingeschaltet, in der Quellhierarchie `LightBillboard`,
höchstens einen Meter von der inneren `st051_lght002.001`-Leuchtengeometrie
entfernt, originale Lichtachse trifft das Feld innerhalb der Quellreichweite.
Andere Komponenten bleiben Kandidaten und werden nicht als Ersatzlicht benutzt.
Die Zuordnung wurde mit den tatsächlich gerenderten Meshes und markierten
Lichtursprüngen überprüft. Das ist kein Anspruch, alle Stadionleuchten
vollständig erfasst oder den originalen Unity-Shader rekonstruiert zu haben.

Deklariert sind stabile Light-IDs, Hierarchie, lokale Komponententransformation,
Montagepunkte im exportierten Modellrahmen, Richtung, Öffnungswinkel,
Reichweite, Quellfarbe/-intensität, Mesh-ID, Abstand und Materialnachweise.
Bundle- und Geometrie-Hashes binden den Nachweis an die geprüfte Quelle.

Zwölf echte Komponenten sind die Laufzeitrepräsentanten; sämtliche 64 IDs
sind ausdrücklich ihren Gruppen zugeordnet. Es gibt keine Gruppenmittelpunkte
als Lampenersatz. Die Diagnose markiert alle 64 Ursprünge:
Cyan = Quelle, Gelb = Repräsentant. Die zwölf Lichtkegel entsprechen den
ausgewählten Quellen. Die kameraseitigen Montagepunkte können sich über das
Feld projizieren, weil die nahe Tribüne nur für die Darstellung ausgeblendet ist.

Originale Lichtpositionen, Achsen, Winkel und Reichweiten bleiben erhalten.
Unity-Intensität und Three.js sind nicht dieselbe Darstellungseinheit:
Browserintensität = Quellintensität × 8 × min(4, sqrt(Gruppengröße)),
mit quadratischem Distanzabfall. Dies ist eine offengelegte Studienkalibrierung,
keine vollständige photometrische Rekonstruktion. Keine zusätzlichen Nacht-
Spotlights, Richtungslichter oder leuchtenden Rasen-/Sitzmaterialien ersetzen
die Quellen. Schwaches Nacht-Himmelslicht ist separat; Flutlicht ist unabhängig
von Tag/Nacht schaltbar. Ein ausgeblendetes Dach löscht keine physische Anlage.

Für Elversberg fehlen nachgewiesene Leuchtenkomponenten/Montagepunkte.
Der allgemeine Mast-Steckbrief ist kein ausreichender Modellnachweis.
**Die Elversberger Nachtansicht bleibt daher bewusst unvollständig.**

## Umfeldbilder und konkrete Bildvorlage

Die gelieferten Dortmund-Bilder passen zur älteren, verworfenen Kamera.
Sie werden nur als Referenz gezeigt, nicht hinter der neuen Kamera verzerrt.
Elversberg besitzt kein bereitgestelltes Umfeldfoto; eine fremde Kulisse wird
nicht eingesetzt.

Nach visueller Kameraauswahl müssen neue vereinsbezogene Tag-/Nachtbilder
zur festen Kamera erstellt und vom Nutzer geliefert werden:

1. Gewünschte Ansicht wählen und die **Kamerareferenz** exportieren.
2. Die **Stadion-Silhouettenmaske** derselben Ansicht exportieren.
3. Beide PNGs haben exakt 1880 × 940 px, unabhängig vom aktuellen Fenster.
   Die Maske ist weiß auf schwarz und enthält keine Demofiguren/Feldmarkierungen.
4. Das neue Umfeldbild darf das Stadion nicht vorzeichnen. Feldregistrierung
   und Bildausschnitt unverändert erhalten; Stadiongröße niemals per Bild
   kompensieren. Ein späterer Ausbau verändert nur den Modellrahmen.

Beispiele und reale Software-WebGL-Aufnahmen liegen in
`docs/stadium/field-study-review/`. Die Exporte werden aus dem aktiven
Renderer erzeugt, nicht aus nachgebauten Bildschirmzeichnungen.

## Verifikation

* Zwei Django-Tests: Adminschutz, Staff-Ausschluss, beide Vereinsflächen,
  Quellhinweise und keine Testticker-Simulation.
* Fünf Node-Tests: gleiche vollständige Feldprojektion bei drei Viewportgrößen,
  rechtshändiger Quelladapter, echte statt gemittelte Lampen, kein Ersatzlicht,
  mitgeführte Montagepunkte bei Modelltransformation und unabhängiges Flutlicht.
* Authentifizierte Browseraufnahmen: beide Konzepte, Dach an/aus, Tag/Nacht,
  Leuchtendiagnose, Flutlicht aus, Mobilansicht und echte PNG-Downloads.
  Gemessene Feldabweichung zwischen den Vereinen: **0**.
* Ein anfänglicher Konsolen-404 betraf ausschließlich das fehlende Favicon;
  nach Ergänzung sind die gezielten Abschlussaufnahmen fehlerfrei.
* Der Transformationscheck ist ein isolierter Adaptertest, keine Mutation oder
  Behauptung eines tatsächlich gespeicherten Stadionausbaus.
