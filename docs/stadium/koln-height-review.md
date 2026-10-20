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
Ihre bisherigen 6-m-Gesamthüllen bleiben deshalb ausdrücklich **unvermessen**.
Eine maximale, mittlere oder benachbarte Teilkörperhöhe wäre hier keine
belegte Höhe des ganzen Gebäudes.

### Ergänzung: explizite Abel-Teilkörper

Die beiden Gesamthüllen werden nun **nur in der Darstellung** in ihre
eindeutig belegten Teilgrundrisse und unvermessene Restflächen aufgeteilt.
Der [Teilkörpervertrag](building-parts-contract.md) enthält Schema,
NHN-Umrechnung, Flächenprüfung und Aussagegrenzen. Keine Änderung an
`select_height`, keine zusätzliche Einzelhöhenfreigabe.

| Bau | LoD2-Teilkörper | Boden m NHN | Oberes Dachniveau m NHN | Teilhöhen m |
|---|---:|---:|---:|---:|
| Ost | 5 | 59,987–62,310 | 68,479–71,600 | 8,492–10,673 |
| West | 6 | 60,418–62,405 | 68,885–71,613 | 8,467–11,003 |

Alle elf Teilkörper stammen aus `LoD2_32_350_5644_1_NW.gml`,
mit explizitem ETRS89_UTM32-/DHHN2016-NHN-Bezug, Dachquelle `1000` und
Bodenquelle `1100`. Amtliche IDs, vollständige GroundSurface-Grundrisse,
abgeschnittene Anzeigeflächen und Quellattribute sind unter `buildingParts`
im [JSON-Beleg](koln-height-evidence.json) einzeln nachvollziehbar.
Ihre oberen Dachniveaus werden pro Teilkörper horizontal dargestellt,
nicht als Nachbau geneigter Dachflächen.

Die Teilkörperflächen überdecken im bisherigen Editorrahmen rund
1.826,407 m² (Ost) bzw. 1.604,217 m² (West).
18,853 m² bzw. 48,663 m² Rest behalten die unvermessene 6-m-Hülle.
Im Westbau überlagern sich zwei amtliche Kanten auf rund 0,00555 m²;
diese strittige Fläche wird keinem Teilkörper zugeteilt, sondern bleibt
im unvermessenen Rest. Keine mittlere/maximale Gebäudehöhe und kein
Verschieben der OSM-Grenzen.

Die Darstellung bleibt eine vereinfachte Gebäudehülle, keine LoD2-Dach- oder
Fassadenrekonstruktion. **Außerhalb der expliziten Teilkörper** sitzt die amtliche relative Gebäudehöhe über dem
höchsten dargestellten Geländepunkt des jeweiligen Grundrisses. Wandfüße
folgen dem Gelände; absolute NHN-Dachkanten werden nicht behauptet.
Bei den expliziten Abel-Teilkörpern werden stattdessen Boden und oberes
Dachniveau direkt in NHN relativ zum unveränderten Spielfeldbezug gezeichnet.
Amtliche Bodenhöhen sind im Beleg gespeichert.

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

Die folgenden geometrischen und visuellen Prüfungen dokumentieren den
ursprünglichen Einbau. Sie sind **kein** Nachweis räumlicher DGM-Treue.
Der ergänzende native Profilvergleich unten meldet derzeit **FAIL**.

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
- Teilkörper-Ergänzung: alle 966 Einzelhöhenzuordnungen, alle 668
  unvermessenen Statusdatensätze und der vollständige Geländebeleg sind
  gegenüber dem vorherigen JSON-Beleg **identisch**. Sechs Python-Tests;
  38 gezielte JS-Tests inklusive bestehender Fingerprints und drei neuer
  Teilkörperprüfungen erfolgreich. Renderer und Vorprüfung lehnen unter
  anderem Lücken, Überlappungen, falsche Quellen und falsche NHN-Bezüge ab.
- Installierte Tag-/Nachtansichten enthalten fünf Ost- und sechs
  West-Teilkörper. Zusätzlich Nahansichten beider Abelbauten bei Tag und
  Nacht/Flutlicht mit ausdrücklich diagnostischen Kameras; keine Änderung
  an der freigegebenen Spielkamera. Bild- und Presentation-Prüfsummen im Beleg.

## Reproduktion

Die Quellen des ursprünglichen Einbaus müssen vorliegen; ignorierte Dateien
werden nicht als dauerhaft vorhandene Belege vorausgesetzt.

```sh
# Frischer, unverfeinerter Katalog aus dem dokumentierten OSM-Snapshot:
python -m scripts.build_koln_review
# Expliziter Netzabruf; lokale Quellen danach ausschließlich mit Hashprüfung:
python -m scripts.koln_height_sources
python -m scripts.refine_koln_heights
# Räumlicher Vergleich; derzeit Exit 1. Nicht mit "|| true" übergehen!
python -m scripts.check_koln_height_profiles
# Nur nach fachlicher Klärung der Befunde mit einer neuen Übernahme fortfahren:
node scripts/capture_koln_study.mjs editor-dach-an editor-dach-aus draufsicht ticker-tag ticker-nacht-flutlicht
# Bilder prüfen; nur Umgebung installieren, keine Registry-/Modelländerung:
python -m scripts.install_koln_heights
node scripts/capture_koln_study.mjs --installed ticker-tag ticker-nacht-flutlicht editor-nacht-flutlicht abel-ost-tag abel-west-tag abel-ost-nacht abel-west-nacht
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

## Ergänzung: native Kontrollprofile statt Genauigkeitsannahme

Der eigenständige Offline-Prüfer `scripts/check_koln_height_profiles.py`
vergleicht die **tatsächlich interpolierte 20-m-Anzeige** mit den nativen,
SHA-256-geprüften GeoTIFFs aus `scripts/koln_height_sources.py`.
Er importiert kein Django, liest/schreibt keine Datenbank und ändert weder
Raster, Vorplatz, Übergang noch wirtschaftliche Stadiondaten.
Insbesondere wird kein Fehler durch neue Glättung oder höhere Grenzwerte
verdeckt. Eine bestandene Prüfung wäre lediglich ein bestandener Kontrollsatz,
keine flächendeckende Genauigkeitsgarantie.

### Verfahren und feste Alarmgrenzen

- 60 Querprofile über das gesamte deklarierte Raster: in beiden Achsen alle
  80 m, um 7 m gegenüber Rasterzeilen/-spalten versetzt. Längsabtastung maximal
  2 m; somit werden **Innenpunkte zwischen Stützpunkten** geprüft, nicht nur
  erneut die 20-m-Knoten. Ergänzend alle 915 kartierten Straßen-/Wegezüge
  einschließlich ihrer ursprünglichen Knicke mit maximal 2 m Segmentlänge.
  Der Abstand bezieht sich auf Modellmeter; keine Behauptung einer vollständigen
  Erfassung jeder kleinräumigen DGM-Struktur zwischen den Kontrollprofilen.
- Modell-X/Z wird mit derselben unveränderten Registrierung wie bei der
  Verfeinerung nach EPSG:25832 zurückgerechnet. GeoTIFF-Abtastung ist bilinear
  zwischen **1-m-Pixelzentren**. Keine NoData-Füllung oder Extrapolation.
  Fehlende/falsche Raster, Prüfsummen, Registrierung, Quellbezüge oder leere
  Kontrollzonen sind Fehler, kein grüner Ersatzdatensatz.
- Die Anzeige wird über den produktiven JavaScript-`elevationSampler`
  aus `measured_ground.js` ausgewertet: zwei ebene Dreiecke pro Zelle,
  **nicht** bilineare 20-m-Interpolation. Auch die Wegprojektion verwendet
  die produktive Funktion `editorPointToDortmund`.
- Gemeinsamer NHN-Bezug: Median der 25 nativen Spielfeldproben, geprüft gegen
  `heightEvidence.terrainReferenceNHN`. Anzeige-NHN =
  Referenz + `groundLevel` + interpolierter Rasteroffset.
  Dekorative Render-Layer-Abstände (Boden −0,35 m, Straße −0,12 m) werden
  nicht als Geländefehler gerechnet.
- Modellvorplatz = OSM-Stadionpolygon mit 20-m-Puffer; Übergang = weitere
  40 m außerhalb dieses Puffers; Rest = Außenbereich (`measured`).
  Die Bowl-Aussparung ist ausgeschlossen; Wegsteigungen werden nicht über
  diese Lücke hinweg berechnet. Ein Segment, das mehrere Zonen berührt,
  wird in jeder betroffenen Zone ausgewertet, nicht versteckt zugeordnet.
- Höhenfehler ist **Anzeige minus natives DGM**. Bericht je Zone:
  Anzahl, Bias, RMSE, 95. Perzentil des Absolutfehlers, Maximalfehler samt
  Profil, Station und X/Z. Quer- und Wegprofile werden zusätzlich getrennt
  zusammengefasst.
- Wegsteigung = 100 × Höhendifferenz / tatsächliche Segmentlänge.
  Steigungswechsel = nachfolgende minus vorherige Segmentsteigung.
  Bericht enthält jeweils Anzeige, DGM und deren Differenz in
  **Prozentpunkten (PP)**, einschließlich OSM-ID, Wegtyp, Namen (falls
  vorhanden), Brücken-/Tunnel-/Layer-Tags und Ort. Das ist kein
  Barrierefreiheits- oder Fahrbahnneigungsnachweis.

| Zone | maximaler Absolutfehler | P95 Absolutfehler |
|---|---:|---:|
| Außenbereich | 2,00 m | 0,75 m |
| Modellvorplatz | 3,00 m | 2,00 m |
| 40-m-Übergang | 3,00 m | 2,00 m |

Für Wege in **allen** Zonen: maximal **20 PP Steigungsabweichung** und
**20 PP Abweichung des Steigungswechsels**. Gleichheit ist zulässig;
jede Überschreitung lässt den Gesamtlauf scheitern. Die Konstanten stehen
fest im Prüfer, es gibt keinen Kommandozeilenschalter zum Aufweichen.
Dies sind bewusst grobe **Prüfalarmgrenzen**, keine aus der
DGM1-Quellengenauigkeit abgeleiteten Toleranzen: 2 m erkennt mehrmetrige
Geländefehler, P95 verhindert ihre Verdünnung durch viele ebene Proben.
Vorplatz/Übergang erhalten wegen ihrer deklarierten Modellanpassung eigene,
aber nicht unbegrenzte Fehlerbudgets. 20 PP signalisiert große lokale
Steigungsunterschiede auf der kurzen Kontrollstrecke.

### Ergebnis des nativen Vergleichs

**FAIL / Exit 1, neun Grenzwertüberschreitungen.**
Erneuter Quellenabruf und Neuaufbau der unveränderten Höhenmethode im
Workspace; **kein Einbau in die Datenbank und keine Produktionsprüfung**.
Die historischen ignorierten Höhendateien lagen in diesem Aufgaben-Workspace
nicht vor. Der neu erzeugte Rasterstand reproduziert den dokumentierten
Nullbezug von **59,863243103 m NHN**.

975 Profile, 107.928 ausgewertete Punkte außerhalb der Bowl
(71.822 Querprofilpunkte, 36.106 Wegpunkte); 35.191 Wegsegmente und
34.276 Steigungswechsel.

| Zone | Punkte | Bias | RMSE | P95 absolut | Maximum absolut |
|---|---:|---:|---:|---:|---:|
| Außenbereich | 105.834 | +0,017 m | 0,381 m | **0,753 m** | **7,008 m** |
| Modellvorplatz | 964 | +0,400 m | 0,797 m | 1,293 m | **5,214 m** |
| Übergang | 1.130 | −0,027 m | 0,644 m | 1,170 m | **4,503 m** |

| Zone | max. Steigungsabweichung | max. Wechselabweichung | max. angezeigte Steigung (absolut) | max. angezeigter Wechsel (absolut) |
|---|---:|---:|---:|---:|
| Außenbereich | **179,696 PP** | **185,119 PP** | 42,298 % | 51,174 PP |
| Modellvorplatz | 15,269 PP | **46,183 PP** | 2,893 % | 1,901 PP |
| Übergang | **49,975 PP** | **46,183 PP** | 9,036 % | 10,471 PP |

Konkrete Kontrollstellen (X/Z in Modellmetern):

- Außenbereich, Querprofil `cross-z--73`, Station 1133, **(−73; 1067)**:
  Anzeige 52,994 m NHN, DGM 45,986 m NHN, Fehler **+7,008 m**.
- Vorplatz, `way/155676742` (`service`, `road-322`), **(−75,275; −119,819)**:
  Anzeige 61,963 m NHN, DGM 56,749 m NHN, Fehler **+5,214 m**.
  Derselbe Weg im Übergang bei **(−75,408; −127,583)**:
  Anzeige 61,887 m NHN, DGM 57,384 m NHN, Fehler **+4,503 m**.
- Aachener Straße `way/5229974` (`primary`, `bridge=yes`, `layer=1`),
  von **(500,026; 541,495)** nach **(498,037; 541,347)**:
  Anzeige **26,536 %**, DGM **206,232 %**, Differenz **−179,696 PP**.
- `way/362049118` (`path`, `bridge=yes`, `layer=1`), bei
  **(496,847; 547,399)**: angezeigter Steigungswechsel ca. **0 PP**,
  nativer Wechsel **−185,119 PP**. **Das DGM beschreibt unter Brücken
  den Boden, nicht deren Deck.** Diese starke Differenz wird nicht als
  bewiesener Fahrbahnfehler ausgegeben, aber auch nicht aus dem Prüfer entfernt.
- `way/795340249` (`footway`, ohne Brückentag), bei
  **(−9,106; 129,601)**: Anzeige **0,045 %**, DGM **−49,929 %**,
  Differenz **+49,975 PP** im Übergang. Am Anschluss zum Vorplatz:
  angezeigter Wechsel **−0,391 PP**, nativer Wechsel **+45,792 PP**,
  Differenz **−46,183 PP** (beiden berührten Zonen zugeordnet).

Die Ergebnisse begründen eine fachliche Prüfung der Ausreißer, **keine**
automatische Gelände- oder Brückenkorrektur. Insbesondere ersetzt
eine erneute geometrische `inspect_package`-Freigabe diesen fehlgeschlagenen
Quellenvergleich nicht.

### Belege und Wiederholung

```sh
# Quellen und verfeinerte Anzeige zunächst wie oben reproduzieren.
python -m scripts.check_koln_height_profiles
# Exit 0: alle Grenzen eingehalten; 1: räumliche Grenzwertverletzung;
# 2: fehlende/ungültige Belege (ebenfalls FAIL).

# Kleine, vollständig offline reproduzierbare Regressionen:
python manage.py test game.tests.test_koln_heights game.tests.test_koln_height_profiles
node --test stadium_editor/tests_js/test_measured_ground.mjs
```

Vollständiger maschinenlesbarer Bericht:
`generated-artifacts/koln-study/heights/profile-check.json`.
Er enthält jede Probe, jedes Wegsegment und jeden Steigungswechsel, feste
Grenzen, Prüffehler, Quell-URLs und native GeoTIFF-Prüfsummen sowie
SHA-256-Bindungen an Presentation, OSM-Beleg und Quellenmanifest.
Große Berichte bleiben wie die GeoTIFFs ignoriert.
Pfadoptionen `--presentation`, `--evidence`, `--sources`, `--output` erlauben
explizite andere lokale Eingaben; es gibt keinen automatischen Netzabruf.

Eingangsbindungen dieses Laufs:

- Presentation: `c45bd1e72b933b302f6e54f815f38ea125397522487a583587995aae740a0b55`
- OSM-Beleg: `09b418aa9f951a24eee1ed248f29da793257c247f2903c534d9d56735f3a2b6f`
- Quellenmanifest: `299c13e3279b98d6f0c1befca0c4ee8299a3ff1eca1047a6f2ee150b516f6201`

Regressionen prüfen unter anderem native Pixelzentren, NoData/NaN und
Hashfehler, Modellregistrierung, echte Renderer-Dreieckinterpolation,
Ausreißer **zwischen** Stützpunkten, getrenntes Scheitern aller Zonen,
Steigungs-/Wechselalarme, Bowl-Lücken, Exit-Codes sowie eine vollständige
synthetische GeoTIFF→Renderer-Prüfung ohne Änderungen der Eingaben.
