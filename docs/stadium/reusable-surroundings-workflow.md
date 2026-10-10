# Gemeinsamer Ablauf für Stadionumfelder

## Ziel und feste Grenzen

Zwei **stadionfreie** Hintergrundbilder pro Verein, Tag und Nacht. Das echte
Stadion und der 2D-Spielablauf bleiben separate Ebenen. Die bestätigte
75%-Feldkamera (1880 × 940, 105 × 68 m, Haupttribüne hinten, vorne offen)
ändert sich weder nach Verein noch Dachzustand. Umfeldbilder sind am
Ortsrahmen registriert, nicht am aktuellen Stadionbestand.

Offline-Höhenhüllen sind nur Vorbereitungshilfen. Keine neue 3D-Stadt im
Spiel, kein produktiver Einbau und keine direkte KI-Erstellung.

Die bereits ausgewählten Kameramatrizen und Feldecken sind als kleiner
Vertrag in `surroundings-camera.json` dauerhaft gespeichert, exakt aus der
bestätigten Mittelweg-Probe übernommen. Das ist keine neue Kamerawahl.
Große Render und Rohquellen bleiben ignorierte, reproduzierbare Ausgaben.
Nach einem Aufgaben-Merge nicht voraussetzen, dass diese Caches vorhanden sind.

## Einmalige Vorbereitung je Verein

1. **Modell und Ortsrahmen kalibrieren.** Feldmittelpunkt, Feldachsen,
   Modelladapter und reale Haupttribüne zuordnen. Eine gemeinsame Feldkamera
   ist nicht überall dieselbe geografische Blickrichtung.
2. **Vereinsprofil anlegen.** Als Vorlage die JSON-Profile in
   `surroundings-profiles/` verwenden: eindeutige ID, Modelladapter,
   Stadion-/Feld-OSM-IDs, Quelle, Haupttribüne, erwartete geografische
   Kameraseite, ausgeblendete Tribünenfläche, Ortsreferenzen und offene Fragen.
3. **Sichtbarkeit feststellen.** Außenboden, ausgeschnittene Tribüne,
   sonstigen Innenboden, Stadionverdeckung und geschütztes Feld getrennt
   messen, jeweils mit und ohne Dach. Der Bildanteil bestimmt den Aufwand,
   nicht allein Zuschauerzahl oder Vereinsgröße.
4. **Bildprägende Höhen prüfen.** Für dominante Gebäude, Hanglagen und
   Waldkanten prüfen, ob echte Fotos, Höhenreferenzen und Gelände relativ zum
   Feld vorliegen. Ein amtlicher Zahlenwert oder Hausgrundriss beweist keine
   unverdeckte Fassade. Nicht jedes fehlende Detail erhält eine Einzelaufgabe.
5. **Vorlagen liefern.** Kameraregistrierte Arbeitsvorlage ohne Vereinsstadion,
   Originalkarte, Kontrollmasken, bedingte Höhenreferenz falls vorhanden,
   Quellen-/Lückenübersicht und zwei Prompts.

Bei Orthofotos reicht die Boden-Grundrissmaske **nicht** als Stadionentfernung.
Fotografierte Dächer, Fassaden, Pylone und Schatten können darüber hinausreichen.
Das Profil benötigt zusätzlich eine visuell kalibrierte `photo_stadium_removal`-
Maske im Originalraster, gebunden an dessen Größe und SHA-256. Diese wird mit
derselben Orts-/Kameraregistrierung projiziert und zur Aussparung addiert.
Sie ist unabhängig vom aktuellen Stadionmodell und keine neue vermessene
Stadionfläche. Eine geänderte Fotoquelle verlangt eine neue Maskenkontrolle.

Unterstützte Adapter: `unity-dortmund` für das kalibrierte Unity-Prüfmodell
und `blueprint-v2` für passend kalibrierte Blaupausen. Andere Unity-/GLTF-
Modelle oder geografische Achsenkonventionen benötigen einen eigenen
expliziten Adapter; nicht einfach als Dortmund deklarieren. Der derzeitige
Renderexport erzeugt die zwei Piloten. Für einen dritten Verein müssen
zunächst gleichartig geprüfte Render geliefert werden; kein universeller
Modellimport wird behauptet. Der Paketbau ist profilgesteuert.

Die `hidden_footprint`-Typen sind OSM-Gebäudering oder Blaupausen-Tribüne.
Die gemeinsame Frontseite liegt in Szenen-Z > 35 m. Andere Schnitte sind
nicht stillschweigend kompatibel. Kompassabweichungen führen zu Fehlern.

## Quellenstatus

| Status | Bedeutung |
|---|---|
| Kartiert | Horizontale Lage durch Originaldaten; nicht automatisch aktuelle Fassade |
| Bedingt | Zugeordnete Höhe/Hülle, aber Gelände, Bezug oder Dachform unvollständig |
| Unbekannt | Keine belastbare Zuordnung oder Quelle; keine typische Ersatzhöhe |
| Historisch | Originalfoto mit anderem Bauzustand; keine aktuelle Aufnahme |

Karten-, Foto- und Höhenlizenzen getrennt dokumentieren. Ein Quellenlink
ist keine Erlaubnis zur Weiterverwendung. Originalfotos aus anderer Richtung
liefern Materialien, nicht die neue Zielperspektive. Dienstaktualisierung
ist kein Foto-/Vermessungsdatum.

### Piloten

- **Dortmund:** Kameraseite Ost, 82,003° ab Nord. NRW-Orthofoto mit unbekanntem
  Aufnahmedatum. Sichtbarer Außenboden Dach-an 0,0042 %, Dach-aus 0,8497 %;
  daraus nicht auf höhere Nachbarobjekte schließen.
- **Elversberg:** Kameraseite Nordost, 41,129°. Die Arbeitsvorlage ist eine
  OSM-Karte, **kein Luftbild**. Außenboden rund 40,22/42,91 %. Amtliche
  Höhenhüllen bleiben bedingt: Wasgau bis 9,379 m, TVE bis 14,204 m.
  Lidl bleibt unbekannt, keine 6-m-Ersatzhöhe. Gelände, Kronen und
  nicht zugeordnete Häuser können Sichtlinien verändern.

Die bekannten Elversberger Höhenquellen wurden erneut aus dem dokumentierten
WFS abgefragt. Neue Gelände-/Foto-Recherchen sind nicht Voraussetzung, eine
ehrlich unvollständige Vorlage zu liefern. Vor einer **ortsverifizierten**
Bildabnahme müssen dominante Lücken geklärt oder eine ausdrücklich weniger
genaue Darstellungsqualität freigegeben werden. Keine aktuelle TVE-Fassade
aus dem Originalfoto von 2017 ableiten.

## Erstellen und zurückgeben

```sh
# Vorhandene frische Render verwenden; nur bei fehlenden/geänderten Belegen:
# Falls auch die ursprüngliche Mittelweg-Renderbasis fehlt:
node scripts/export_stadium_frame_probe.mjs --middle
# Der Paketbauer vergleicht weiterhin gegen den dauerhaften Kameravertrag.
node scripts/export_stadium_frame_probe.mjs --middle --main-stand-back
node scripts/export_dortmund_geo_probe.mjs
python scripts/build_dortmund_geo_probe.py

# Elversberg: dokumentierte GML-Seiten und Capabilities bereitstellen:
python scripts/prepare_elversberg_height_probe.py
node scripts/export_elversberg_height_probe.mjs

# Beide Piloten oder einzelne neue Profile:
python scripts/build_stadium_surroundings_pack.py
python scripts/build_stadium_surroundings_pack.py --profiles PFAD_ZUM_PROFIL.json
```

Ausgaben unter `generated-artifacts/stadium-surroundings/<verein>/`.
`guide.html` ist eigenständig und enthält einzeln herunterladbare PNGs und
kopierbare Prompts. Kein ZIP erforderlich, Prompts maximal 15.000 Zeichen.
Die graue Fläche ist unbekannter Boden unter dem Vereinsstadion. Sie ist
gegebenenfalls um konservativ entfernte Stadion-Fotoanteile und Schatten
erweitert; sie ist keine vermessene zusätzliche Stadionfläche und keine
freie Lizenz für einen erfundenen Vorplatz. Die Höhe der TVE-Hülle
und die Form einer Dachplatte darf Higgsfield nicht als Originalfassade
übernehmen. Farbige Kontrollbilder sind Referenzen, kein fertiger Hintergrund.

**Zuerst Tag:** Vorlage/Quellen prüfen, Tagesentwurf erstellen und visuell
abnehmen. **Dann Nacht:** ausschließlich aus diesem Tagesbild ableiten,
keine unabhängig neu erzeugte Architektur. Passende Umfeldbeleuchtung
benötigt eigene Referenzen; Elversbergs fehlende Modellleuchten nicht ins
Bild malen. Kein Stadion, Fußballplatz, Tor, Dachrest oder Stadionlichtkegel.

Masken oder Prompts allein garantieren keinen Pixelschutz. Bei Drift
gezielte registrierte Bildbearbeitung verwenden; keine unbegrenzte
Wiederholung derselben freien Promptschleife.

```sh
python scripts/review_stadium_surroundings.py \
  --pack generated-artifacts/stadium-surroundings/elversberg \
  --day TAG.png --night NACHT.png \
  --output generated-artifacts/stadium-surroundings-review/elversberg
```

Formatabweichungen, Transparenz, EXIF-Drehung und beschädigte Paketdateien
werden abgewiesen. Ein kantenbasierter Test meldet belastbare globale
Tag-/Nachtverschiebung auch bei anderer Helligkeit. Er beweist **nicht**
lokale Layouttreue, echte Geografie oder Stadionfreiheit.

## Abnahme und Ausbau

Abnahmematrix: Tag/Nacht × Dach an/aus × Bestand/Ausbau = acht Zustände.
Das Prüfwerkzeug erstellt vier diagnostische Bestandskompositionen und
bewahrt Feldpixel exakt gegenüber dem jeweiligen Originalrender. Es
erzeugt keine echte Nutzerabnahme. Die harten Silhouettenränder sind keine
fertige Alpha-Integration.

Für den Ausbau ein zweites Paket aus wirklich verändertem Modellrender
unter **derselben** Kamera und Ortsregistrierung erstellen. `--expansion-pack`
übernimmt dessen vier Render zur Prüfung mit denselben Hintergrundbildern.
Identische Silhouetten werden nicht als Ausbau akzeptiert.
Die Bilder müssen dafür nicht neu generiert werden.

`manual_review.example.json` kopieren und erst nach tatsächlicher Sichtprüfung
ausfüllen; `--manual-review` übergeben. Rechte, Tagoptik, Ortsstruktur,
Stadionfreiheit, Nachtlayout, Ausbau und die erklärten Referenzgrenzen jeweils
bestätigen. Die Ausgangsqualität und offenen Fragen bleiben auch im
Prüfbericht sichtbar; eine Bestätigung macht sie nicht zu vermessenen Fakten. Technisch
erkannte Verschiebung bleibt auch bei ausgefülltem Formular abgewiesen.
Ohne Ausbau-Render oder Sichtabnahme bleibt der Status offen. Selbst ein
vollständig geprüftes Paket benötigt eine separate Integrationsentscheidung.

### Aktualität richtig trennen

Die Hintergrundregistrierung enthält Kamera und geografischen Ortsrahmen,
keine Stadionkapazität oder aktuelle Mesh-Silhouette. Ein neuer Ausbau
verändert daher die Verdeckungsnachweise, nicht automatisch das Bild.
PNG-Bytes sind mit Renderkontext verbunden. Die vorhandenen Nachweise
belegen jedoch nicht sämtliche aktuellen Modellabhängigkeiten; diese
gesonderte Aktualitätsprüfung wird hier nicht doppelt implementiert.

## Checkliste für den nächsten Verein

- Orts-/Feldachsen und Haupttribüne ausdrücklich kalibriert?
- Unterstützter Adapter und beide Dach-/Tag-/Nacht-Render vorhanden?
- Karten-/Fotorechte und Bauzustand bekannt?
- Tatsächlich freie Außenflächen statt ausgeschnittener Tribünen gemessen?
- Dominante Gelände-, Gebäude- und Vegetationslücken eingeordnet?
- Arbeitsvorlage stadionfrei, Kamera unverändert, Prompts unter 15.000 Zeichen?
- Tag zuerst visuell abgenommen, Nacht geometrisch daraus abgeleitet?
- Acht Zustände mit echtem Ausbau geprüft, Feldpixel beim Zusammensetzen erhalten?
- Separate Integration freigegeben?
