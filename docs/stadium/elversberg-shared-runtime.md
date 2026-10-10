# Elversberg: gemeinsamer Stadion- und Umfeldbestand

## Integration

2D-Editor, 3D-Editor, öffentliche Spielansicht, Elversberg-Liveticker und
Admin-Studie verwenden denselben aktuellen Stadionbestand. Die Live Scene
liest gespeicherte Geometrie und gespeichertes Design; der öffentliche
Endpunkt wird nicht zwischen Reloads zwischengespeichert. Ungespeicherte
Editoränderungen bleiben eine lokale Vorschau.

Die gemeinsame Umgebung enthält 334 Gebäude mit stabilen OSM-Way-Identitäten,
132 Straßen und zehn schematische Vegetationsgruppen. Editor-Rohkoordinaten
und pitch-zentrierte Live-Koordinaten werden explizit ineinander umgerechnet.
Die Vegetationsinstanzen entstehen aus einem gemeinsamen deterministischen
Generator. Es gibt keine zusätzlich erfundenen Häuser oder separaten Bäume
für einzelne Ansichten.

Die bestätigte Feldkamera und das 105×68-m-Spielfeld bleiben unverändert.
Elversbergs Orientierung wird am Modell eingestellt, nicht durch eine
Umkehrung der Feldkamera. Der vordere Stadionteil wird in der Spielansicht
ausgeblendet; die gespeicherte Geometrie wird dabei nicht verändert.
Dortmund und andere Vereine behalten ihre bisherigen Rendererpfade.

## Quellen und Grenzen

- Grundrisse, Straßen und kartierte Grünflächen: vorhandene OpenStreetMap-
  Daten, ODbL 1.0. Die Auswahl der Gebäude umfasst den lokalen 350-m-Bereich;
  durchlaufende Straßen behalten ihre echten Linien.
- 43 bedingte Gebäudehöhen aus der gesonderten LVGL-Zuordnung. Die
  Quellprüfsumme wird geprüft. Diese Zuordnung ist keine Vermessung der
  Sichtbarkeit: Höhenbezug und Gelände bleiben unbestätigt.
- Wasgau: OSM-Way 30887518, bedingte Höhe 9,379 m.
- TVE: OSM-Way 53864244, bedingte Höhe 14,204 m.
- Lidl: OSM-Way 53864241, **keine freigegebene Höhe**. Der dargestellte
  6-m-Körper ist ausdrücklich schematisch.
- Weitere Gebäude ohne zugeordnete Höhe: schematische 6-m-Körper, nicht als
  amtliche Gebäudehöhen ausgewiesen.
- Vegetation: schematische 3,5-m-Gruppen auf geeigneten kartierten Flächen,
  keine vermessenen Einzelbäume oder Waldhöhen. Sportflächen und Gruppen,
  die Stadion oder Gebäude überschneiden, werden konservativ ausgeschlossen.
- Boden: flache Bezugsfläche, kein vermessenes Geländemodell.
- Keine neuen Elversberger Lichtquellen. Echte Leuchten bleiben ein
  gesonderter Auftrag; Tag/Nacht verändert nicht den Ortsbestand.

Die sichtbaren Flutlichtmasten stammen aus der vorhandenen V2-Angabe
`count: 4, height: 30`. Der allgemeine Renderer erzeugt daraus Eckpositionen
außerhalb der Tribünenbegrenzung. Diese Darstellung ist **schematisch** und
kein Nachweis realer Montageorte. Nach der ausdrücklichen Herkunftserklärung
hat der Nutzer ihr vorläufiges Beibehalten und eine Nachtaufnahme gewählt.
`elversberg-night-schematic-canvas.png` zeigt Nacht mit separat
eingeschaltetem schematischem Flutlicht; die Quellen wurden nicht neu
positioniert oder als reale Elversberger Leuchten deklariert.

Der 2D-Editor startet nun stadionnah. Mausrad, Plus/Minus und „Einpassen“
steuern ausschließlich die lokale Ansicht. Der gewählte Zoom wird im Browser
je Stadion gemerkt, nicht in Geometrie oder Design geschrieben. Bei
gesperrtem Browserspeicher bleibt der Zoom für die Sitzung nutzbar; der
Hinweis an der Prozentanzeige benennt die fehlende dauerhafte Speicherung.
Plus/Minus, Mausrad, Neuladen, Fenstergrößenwechsel und Zurücksetzen wurden
schreibgeschützt mit echten Elversberger Daten im Browser geprüft.

Bei nicht verfügbarer Umfeldquelle wird keine Ersatzstadt erzeugt. Die
optionalen Umfelddetails fehlen dann mit einer ausdrücklichen Warnung.

## Technische Prüfungen

- 16 Django-Tests für Quellen, Roh-/Live-Koordinaten, schreibfreies Lesen,
  gespeicherte Designänderungen, Admin-Studie und Ticker-Zuordnung.
- 22 JavaScript-Tests für den gemeinsamen Renderer, deterministische
  Vegetation, Materialgruppen, unveränderte Feldkamera, Editoradapter und
  Ausbaugeometrie. Entfernte Straßen dürfen die anfängliche 2D-Editoransicht
  nicht auf eine winzige Stadiondarstellung verkleinern.
- Öffentlicher Live-Scene-Endpunkt: tatsächliche gespeicherte Elversberg-
  Geometrie mit 17 Blöcken und gemeinsamer Umgebung.
- Chromium mit explizitem SwiftShader: WebGL2 verfügbar; öffentliche
  Elversberg-Spielansicht startet einen WebGL-Canvas.

Zwei bereits vorher nicht passende, starre Template-String-Prüfungen in der
allgemeinen Editorsuite beziehen sich auf den alten Spielbericht-Einbau.
Diese sind kein grüner Nachweis für die gesamte Projekttestsuite und wurden
nicht durch Änderungen am Spielbericht kaschiert.

## Browserabnahme

Elversberg hat im geprüften Entwicklungsbestand keinen zugewiesenen Manager.
Für den Editor wird deshalb das echte View-HTML mit echten Elversberger
Geometrie-/Designdaten in einem schreibgeschützten Prüfbrowser geladen.
Vereinszuordnung, Nutzerrollen und gespeicherte Stadiondaten werden nicht
für die Prüfung verändert.

Der erste Prüfbrowser konnte kein WebGL starten; die dortige vermeintliche
3D-Aufnahme war kein 3D-Abnahmebeleg. Mit dem explizit gestarteten Chromium
und SwiftShader wurden anschließend echte WebGL-Ansichten im Editor, in der
öffentlichen Spielansicht, im Elversberg-Admin-Ticker und in der Admin-Studie
bestätigt. Die mobile Tickeransicht wurde bei 360 px Bildschirmbreite mit
einem 332×166-px-Canvas ohne horizontales Überlaufen geprüft. Der reguläre
Admin-Test bleibt standardmäßig Bayern–Dortmund; die Elversberg-Szene wird
nur über den ausdrücklich gewählten Stadionparameter zugeschaltet.

Die Tagesaufnahmen liegen unter
`generated-artifacts/elversberg-shared-runtime/`. Editor-Orbit und fester
Ticker-Spielblick sind unterschiedliche Kameras; ihre Bilder sind deshalb
keine Behauptung von Pixelgleichheit. Die technischen Daten- und
Projektionsprüfungen werden getrennt von dieser visuellen Übersicht geführt.

Im abschließenden Bildvergleich wurde Elversbergs Dachmaterial für den
hohen Spielblick beidseitig sichtbar gemacht; die alte reine
Dachunterseiten-Regel bleibt für andere Vereine erhalten. Der Ticker wurde
danach mit aktualisierten Assets erneut gezielt geprüft: Dach aus veränderte
den Canvas-Inhalt, Dach wieder an stellte ihn bytegleich wieder her. Die
vier Feldecken bleiben sichtbar. Die Übersicht `comparison.html` enthält
die finalen Tagesaufnahmen und die Abnahmegrenzen.

Der reale Elversberger Geometrie-/Design-/Kapazitätsbestand wurde nach der
Browserprüfung gegen den vorher gesicherten Bestand verglichen und ist
unverändert. Es existiert dort kein angewendeter Ausbau. Es wurde daher
kein angeblich echter Elversberger Ausbau für die Abnahme erzeugt:
Ausbauverhalten ist durch die vorhandenen JavaScript-Vertragstests geprüft,
ein realer angewendeter Elversberg-Ausbau bleibt als Live-Abnahmefall offen.

Ein Hashnachweis für den unveränderten realen Bestand liegt in
`generated-artifacts/elversberg-shared-runtime/verification.json`.
Die kurzlebige Prüfsession und temporären Editor-Fixtures wurden nach
Abschluss entfernt.

Technische Tests und Browsernachweise ersetzen nicht die Nutzerabnahme der
sichtbaren Gestaltung.
