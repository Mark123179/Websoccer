# Offener Stadionrahmen: gemeinsame Kameraprobe

## Freigegebener Prüfumfang

Die Feldnähe grundsätzlich beibehalten, aber zurückzoomen, damit Dortmund
als große Referenz vollständig im Bild liegt. Beide Dachzustände prüfen.
Der offene Rahmen bleibt erhalten: Die kameraseitige Tribüne wird nicht
wieder eingeblendet. Keine Integration in Spielansicht oder Admin-Test.

## Verfahren

`scripts/export_stadium_frame_probe.mjs` nutzt unveränderte Studienmodule
und echte Originalgeometrie. Indexierte Dreiecke werden mit ihren tatsächlichen
Material-Schnittebenen geschnitten; auch neue Schnittpunkte werden gemessen.
Der Dach-an-Zustand von Dortmund bestimmt genau eine gemeinsame Kamera.

Eine reine Vergrößerung des Bildwinkels erwies sich als ungünstig. Die
gelieferte Probe behält deshalb Brennweite und 44°-Neigung bei und bewegt
die Kamera entlang der bisherigen Position vom Feldzentrum zurück.
Eine binäre Suche ermittelt den kleinsten Rückzugsfaktor, bei dem sämtliche
gemessenen Rahmenpunkte mindestens 32 Pixel vom Bildrand entfernt liegen.
Der Rahmen wird vertikal zentriert; die horizontale Feldmitte bleibt unverändert.

Elversberg und beide Dachzustände erhalten diese Kamera unverändert.
Elversberg wird nur gegen die gemeinsame Kamera geprüft, nicht separat eingepasst.

## Ergebnis und Grenzen

Format: 1880 × 940; Spielkoordinaten: 105 × 68 Meter.
Kameraposition der Probe: etwa (0, 190,35, 213,66), verglichen mit (0, 98, 110).
Der notwendige Rückzugsfaktor beträgt etwa 1,94.

Der vollständige große Rahmen verlangt damit mehr als einen kleinen Rückzug:
Die nahe Feldkante hat etwa 47 % ihrer bisherigen Bildbreite, die Feldhöhe
etwa 50 %. Dies ist noch keine abgenommene neue Spielkamera. Die Anforderung
„gesamter sichtbarer Rahmen“ steht in dieser Komposition im Konflikt mit
einem nahezu unverändert großen 2D-Feld.

Die Prüfung bestätigt exakt identische Projektionsmatrizen, Posen und vier
Feldeckpunkte für alle vier Zustände. Die Dach-aus-Zustände enthalten keine
sichtbaren registrierten Dachmeshes. Alle vier Rahmen liegen innerhalb des
gemeinsamen Bildes. Das lässt sich nicht pauschal auf jedes künftige Stadion
oder jeden Ausbau übertragen.

Die Bilder verwenden den neutralen Studienhintergrund. Sie sind
Kamera-/Modellproben, keine fertigen geografischen Hintergrundbilder.

Ausgabe und Prüfprotokoll liegen unter dem ignorierten Verzeichnis
`generated-artifacts/stadium-frame-probe/`.

## Näherer Mittelweg (als gemeinsame Kamerabasis bestätigt)

Nach der Gesamtansicht hat der Nutzer das größere Feld priorisiert und einen
Mittelweg angefragt. `node scripts/export_stadium_frame_probe.mjs --middle`
erstellt dafür vier neue Ansichten unter
`generated-artifacts/stadium-middle-probe/`, ohne die Gesamtprobe zu überschreiben.

Dieser Versuch behält die ursprüngliche Kameraposition und Neigung bei,
reduziert die Brennweite auf 75 % und hält die nahe Feldkante auf ihrer
bisherigen Bildhöhe. Damit haben Feldbreite und Feldhöhe exakt 75 % der
ursprünglichen Nahansicht. Äußere Dortmunder Stadionränder und obere Teile
der Dachaufbauten sind bewusst angeschnitten; eine vollständige
Stadion-Einpassung wird hier nicht behauptet.

Der Nutzer hat diese Ansicht mit „Diesen Mittelweg beibehalten“ und
„Beibehalten“ als gemeinsame Kamerabasis ausgewählt. Fertige Umfelder und
eine Integration in die Anwendung sind damit nicht abgenommen.

Alle vier Feldeckpunkte müssen weiterhin vollständig im Bild liegen.
Die identische Projektion und Pose aller Vereine/Dachzustände sowie der
vollständige Dach-aus-Schalter werden unverändert geprüft. Spielkoordinaten,
Anwendungsansicht, Kamera-Presets und Vereinsdaten bleiben unverändert.

## Haupttribüne hinten (ausgewähltes Darstellungsprinzip)

Der Nutzer hat „Haupttribüne hinten sichtbar“ gewählt. Die neue isolierte
Probe entsteht mit:

`node scripts/export_stadium_frame_probe.mjs --middle --main-stand-back`

Ausgabe: `generated-artifacts/stadium-main-stand-back-probe/`.
Die bisherigen Kameraproben werden nicht überschrieben.

Nur die Stadionmodelle werden um 180° gedreht. Dortmund zeigt damit West
hinten, Süd links und Nord rechts; die vordere Ostseite bleibt ausgeschnitten.
Elversberg zeigt die Modellseite Süd hinten, Ost links und West rechts;
die vordere Modellseite Nord wird ausgeblendet. Geografisch liegt die
Elversberger Kameraseite ungefähr nordöstlich, die Haupttribüne südwestlich.

Elversbergs Anpassung erfolgt an einer isolierten Kopie der Eingabedaten,
einschließlich des Filters für die kameraseitige Tribüne. Es werden keine
Dachsegmente hinzugefügt. Die zuvor diskutierte Dachhälfte gehört jetzt
zur ausgeblendeten Vorderseite; ihr Datenstand bleibt unverändert.

Projektionsmatrix, Kamerapose und vier Feldeckpunkte werden in allen vier
Zuständen exakt gegen das Prüfprotokoll der bestätigten 75%-Probe verglichen.
Beide Dach-aus-Zustände müssen ohne sichtbare registrierte Dachmeshes sein.
Dies ist keine produktive Integration oder Vermessung der Stadionmodelle.

Die Dortmunder Umfeldregistrierung aus der bisherigen Westansicht ist für
die neue Ostansicht nicht unverändert verwendbar. Der Kartenadapter muss
die Modellhalbwendung mit berücksichtigen, bevor neue Umfeldvorlagen
als passend ausgegeben werden.
