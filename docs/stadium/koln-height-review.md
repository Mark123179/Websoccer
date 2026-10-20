# Köln – belegte Gelände- und Gebäudehöhen

Stand: 20.10.2026. Ergänzung zum [Quellbericht](koln-source-review.md).
**Workspace-Einbau, keine Veröffentlichung in Produktion.**

## Quellen und Aussagegrenzen

1. [Geobasis NRW DGM1](https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/hoehenmodelle/digitale-gelaendemodelle/digitales-gelaendemodell):
   WCS `https://www.wcs.nrw.de/geobasis/wcs_nw_dgm`, Coverage `nw_dgm`,
   zwölf explizite 1-km-GeoTIFF-Ausschnitte in nativer Rasterweite **1 m**.
   Rasterwerte beziehen sich auf Pixelzentren, nicht Pixelkanten.
   Lage EPSG:25832, Höhe NHN im DHHN2016 / EPSG:7837.
   Das DGM enthält keine Bauwerke, Brücken oder Vegetation.
2. [Geobasis NRW LoD2](https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/3d-gebaeudemodelle):
   neun CityGML-Kacheln, X 349–351 / Y 5643–5645, Version der Dateien
   gemäß gehashten Abrufmetadaten. Gebäude-/Bauwerksgrundlagen laut
   Produktbeschreibung ALKIS 01.07.2025 / ATKIS 01.10.2025,
   Laserscanning/DGM 2019–2025; bereitgestellter Bestand Juli 2026.
   Kein behauptetes Einzelaufnahmejahr für Köln.
3. [GDI-DE Quellcode 1000](https://registry.gdi-de.org/codelist/de.adv-online.gid/AX_LI_ProcessStep_Dachhoehe_Source/1000)
   bedeutet **aus Laserscanmessung**. Ein `measuredHeight`-Attribut allein
   reicht nicht: LoD2 kann auch Standardhöhen enthalten.

NRW nennt für LoD2 ±1 m Höhenqualität und mögliche grobe Abweichungen bei
komplexen Dächern. Für DGM1 gelten abhängig von Gelände/Bewuchs bis zu
±(10 cm + 5 % der Rasterweite) bzw. ±(10 cm + 20 %) bei 95 %
Sicherheitswahrscheinlichkeit. **Diese Genauigkeit gilt nicht für das hier
generalisierte 20-m-Anzeigeraster, den Modellvorplatz oder den Übergang.**

Lizenz: Geobasis NRW, Datenlizenz Deutschland – Zero 2.0;
OSM weiterhin © OpenStreetMap contributors / ODbL.
Alle Abruf-URLs, Antwortzeitpunkte, Dateigrößen und SHA-256-Prüfsummen,
Objektzuordnungen, Ausschlussgründe und Renderbindungen stehen in
[`koln-height-evidence.json`](koln-height-evidence.json). Große GeoTIFFs,
CityGML-Dateien und Bilder liegen ignoriert unter
`generated-artifacts/koln-study/`, nicht im Git-Verlauf.

## Räumliche Zuordnung und Abdeckung

Die unveränderte OSM-Projektion wird exakt zurück nach WGS84 und anschließend
per PROJ nach EPSG:25832 transformiert. Die Stadion-/Pitch-Achsen bleiben
unverändert; **keine** erneute Nord-/Süd- oder Ost-/West-Kalibrierung.
Der Renderer verwendet dasselbe pitch-zentrierte Modellkoordinatensystem.

Gebäude werden nur über echte amtliche `GroundSurface`-Grundrisse zugeordnet,
nicht über Namen, Nähe, Dachprojektionen oder Bounding-Boxen.
Erforderlich ist genau ein Kandidat mit **mindestens 85 % Überdeckung in
beiden Richtungen**, gültiger Meterhöhe und Laserquellcode für die Dachhöhe.
Mehrdeutige, partielle, standardwertbasierte oder geometrisch ungültige
Zuordnungen werden nicht übernommen. Drei amtliche Grundkomponenten mit
ungültiger/nullflächiger Geometrie sind mit Identität und Dateiname abgewiesen,
nicht automatisch repariert.

| Abdeckung | Ergebnis |
|---|---:|
| Verschiedene OSM-Gebäudeobjekte | 1.546 |
| Eindeutig zugeordnete amtliche Laserhöhen | 966 / 62,5 % |
| Objekte ohne freigegebene Einzelhöhe | 580 |
| Renderpolygone insgesamt | 1.634 |
| Unvermessene Renderteile einschließlich triangulierter Relationen | 668 |

Für alle 1.634 Renderteile existiert ein Statusdatensatz. Unvermessene
Bestandshüllen behalten ihren bisherigen Wert, inklusive dessen ursprünglicher
Einordnung (`OSM height`, Geschossableitung oder schematisch).
**Es wurden keine neuen Ersatzhöhen erfunden.**

Die Abelbauten Ost (`way/73467119`) und West (`way/73467122`) haben fünf bzw.
sechs überdeckende amtliche Teilkörper mit unterschiedlichen Höhen und
Bodenniveaus. Keine davon deckt jeweils den ganzen OSM-Grundriss ab.
Ihre bisherigen 6-m-Hüllen bleiben deshalb ausdrücklich **unvermessen**.
Eine maximale, mittlere oder benachbarte Teilkörperhöhe wäre hier keine
belegte Höhe des ganzen Gebäudes.

Die Darstellung bleibt eine vereinfachte Gebäudehülle, keine LoD2-Dach- oder
Fassadenrekonstruktion. Die amtliche relative Gebäudehöhe sitzt über dem
höchsten dargestellten Geländepunkt des jeweiligen Grundrisses. Wandfüße
folgen dem Gelände; absolute NHN-Dachkanten werden nicht behauptet.
Amtliche Bodenhöhen sind separat im Beleg gespeichert.

## Gelände und Anschluss

- **14.641 gültige DGM-Stützpunkte**, keine NoData-Ergänzung und keine
  Extrapolation. Modellabdeckung X/Z jeweils −1.200 bis +1.200 m;
  OSM-Auswahl bleibt unverändert ±800 m Ost/Nord.
- 25 native DGM-Abtastungen innerhalb der gemalten Spielfeldlinien liefern
  den Median **59,863 m NHN** als lokalen Nullbezug des Quellspielfelds.
  Dies ist eine Registrierung zwischen zwei Quellen, keine Stadionvermessung.
- Das Quell-Vorplatzniveau bleibt **+2,1 m**. OSM-Stadionkontur plus 20 m
  Anschlusszone bleiben eben; außerhalb schließen 40 m Smoothstep-Übergang
  an das gemessene Gelände an. Diese Zonen sind im Beleg räumlich beschrieben
  und ausdrücklich Modellanpassungen.
- 137 Rasterpunkte im Modellvorplatz, 98 im Übergang, 14.406 ohne
  Anschlussanpassung. Die nativen Abtastwerte über dem ganzen 2,4-km-Raster
  liegen zwischen 41,868 und 81,648 m NHN; keine Behauptung, dass dies die
  Minima/Maxima des engeren OSM-Ausschnitts oder des nativen DGM sind.
- Die vorhandene Bowl-Aussparung ist unverändert. Unterirdische
  Quellfundamente dürfen wie zuvor von Gelände überdeckt werden; Spielfeld
  und tiefe Ränge bleiben frei.
- Geländedreiecke, Straßen, Grün-/Wasserflächen werden an denselben
  Rasterzellgrenzen und Diagonalen aufgeteilt. So liegen sie auf denselben
  Ebenen, ohne schwebende oder vom Gelände verdeckte Teilflächen.
  Kein Quelldreieck/OSM-Objekt wird deshalb gelöscht oder an der Bowl beschnitten.
- Baumpositionen bleiben OSM; Baumformen und Baumhöhen bleiben schematisch.
  Wasserflächen werden wie bisher kartografisch dargestellt, nicht hydraulisch
  rekonstruiert. Ein DGM ist insbesondere keine Brückenhöhenquelle.

## Prüfung und unveränderte Spieldaten

- `inspect_package`: `ok=true`, `terrainDeclared=true`, **keine Befunde**,
  sowohl an der Presentation als auch an der installierten Editor-Geometrie.
- Fünf Quell-WebGL-Ansichten: Dach an/aus, Draufsicht, Spielansicht Tag und
  Spielansicht Nacht/Flutlicht. Zusätzlich drei aktuelle installierte Ansichten
  über die registrierten Anwendungs-Asset-Endpunkte: Spielansicht Tag,
  Spielansicht Nacht/Flutlicht und Umfeld Nacht/Flutlicht.
  Visuell geprüft: freie Bowl, keine überdeckten Ränge, kein Geländestreifen
  im Feld, Vorplatzanschluss, keine ausgelassenen Grün-/Wasserflächen.
- Installierte Bilder sind per SHA-256 an genau ihre Presentation gebunden;
  Dateiprüfsummen der Bilder stehen im Abschlussbeleg.
- 22 JavaScript-Tests erfolgreich: bestehende Renderer-Fingerprints,
  Aussparungsparität, Rastervalidierung, vollständige Quellfläche und
  identische Geländeebenen auch innerhalb von Dreiecken und Linien.
  Sechs Python-Tests erfolgreich: Validierung, unverändernde Projektion,
  Quellenmetadaten und Ausschluss mehrdeutiger/standardbasierter Höhen.
- Kapazität weiterhin **50.000**. Vollständiger Stadium-Datensatz,
  gespeicherte Entwürfe und Editor-Geometrie außerhalb `bg`/`surroundings`
  vor/nach Einbau auf Gleichheit geprüft. Kein neuer Modellmanifest-Eintrag,
  keine Modellasset-Änderung, kein Kapazitätsadapterlauf beim Höheneinbau.
- Anwendungsworkflow neu gestartet, Systemcheck sauber. Änderungen sind nur
  für ausdrücklich deklarierte Höhenraster aktiv; Altstadien behalten ihre
  bisherigen Geometrie-Fingerprints.

## Reproduktion

Die Quellen des ursprünglichen Einbaus müssen vorliegen; ignorierte Dateien
werden nicht als dauerhaft vorhandene Belege vorausgesetzt.

```sh
# Frischer, unverfeinerter Katalog aus dem dokumentierten OSM-Snapshot:
python -m scripts.build_koln_review
# Expliziter Netzabruf; lokale Quellen danach ausschließlich mit Hashprüfung:
python -m scripts.koln_height_sources
python -m scripts.refine_koln_heights
node scripts/capture_koln_study.mjs editor-dach-an editor-dach-aus draufsicht ticker-tag ticker-nacht-flutlicht
# Bilder prüfen; nur Umgebung installieren, keine Registry-/Modelländerung:
python -m scripts.install_koln_heights
node scripts/capture_koln_study.mjs --installed ticker-tag ticker-nacht-flutlicht editor-nacht-flutlicht
python -m scripts.package_koln_heights
```

Ein erneutes Verfeinern startet stets aus der an den OSM-Rohhash gebundenen
Basis; es stapelt keine Höhenanpassungen. Bei veränderter Basis oder
verschobenem Pitchzentrum bricht es ab, statt alte Quellen still zu übernehmen.
NRW-GetCoverage wird explizit in 1-km-Teilen abgefragt: der Dienst lehnte den
größeren Gesamtausschnitt mit einer generischen Parameterfehlermeldung ab.
Das ist keine Datenlücke.

Ausgaben: `heights/sources.json`, `height-evidence.json`,
`before-height-integration.json`, `integration-check.json`,
`final-evidence.json` und `koln-hoehenpruefung.html`.
Die beiden letzten Dateien sowie die installierten PNGs sind die aktuelle
Höhenübergabe; der ältere Erst-Einbaubericht dokumentiert bewusst den damaligen
ebenen Stand.
