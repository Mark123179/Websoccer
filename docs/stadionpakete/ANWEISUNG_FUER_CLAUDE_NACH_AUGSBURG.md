# Neue Anweisung für Claude nach dem Augsburg-Review

Ergänzt die bisherigen Stadionpaket-Anweisungen, insbesondere nach Bremen.
Auftrag: Augsburgs offene Modellpunkte an der Originalquelle bearbeiten und
ein neues prüfbares Paket liefern. Keine Registrierung, kein Assetupload,
keine externe Serverübertragung und keine Veröffentlichung.

## 1. Verbindliche lokale Tribünenzuordnung

- FMI **2238**, **FC Augsburg**, **WWK Arena**.
- Im Blaupausenrahmen: **Heimkurve NORD**, **Haupttribüne WEST**,
  **Gegentribüne OST**.
- NORD = Ulrich-Biesinger-Tribüne, Heimbereich K–O; WEST =
  Haupttribüne D–H mit VIP E/F/G; OST = Gegengerade R–V;
  SUED = Südtribüne, Gäste W/X in der Südost-Ecke.
- Modellachsen unverändert: `+x OST`, `-x WEST`, `+z NORD`, `-z SUED`;
  Umfeldachsen `{"NORD":"+z","WEST":"-x"}`. Nicht drehen oder spiegeln.
- Das Ausgangspaket beschreibt eine öffentliche Vorschau mit Heimkurve NORD.
  **Lokal waren dagegen alle drei Zuordnungen falsch: SUED/SUED/NORD.**
  Die freigegebene lokale Korrektur setzt `meta.homeStand=NORD` und
  `scene_meta.mainStand=WEST`, `scene_meta.farStand=OST`.
- Die Aussage „Heimkurve war bereits richtig“ gilt nicht für den lokalen
  Ausgangszustand. Die neue Korrektur nicht durch alte Vorschaudaten ersetzen.

## 2. Schutzdaten – keine wirtschaftliche Korrektur

- Lokale Kapazität **30.660**, wirtschaftliche Stehplätze:
  **NORD 5.366**, **SUED 1.150**, **OST/WEST 0**.
- Vereins-/Stadionfelder, Blöcke, Blocktypen, Reihen, Plätze, RLE,
  Designs und Ausbauten unverändert lassen.
- Öffentliche Renderzellen, Bundle-Kapazität 31.302 und 22.852
  Quell-Sitzplatzeinträge sind keine Importwerte.
- Geometrie, wirtschaftliche Plätze und Crowd-Bezeichnungen getrennt
  behandeln. Keine Neuverortung historischer Crowd aus ihren Namen ableiten.
- Lokale IDs nie aus dem Paket übernehmen; Identität über FMI und Verein
  prüfen. Private Backups nicht ins Übergabepaket aufnehmen.

## 3. Dachtrennung sauber lösen – bisheriger Kompromiss nicht abgenommen

Die unabhängige Binary-Nachrechnung bestätigt den dokumentierten Mangel:

- `roofMinHeight=22` mit Präfixen `front3_`, `faros`, `center3_df_`,
  `center1_2`, `center1_3` ordnet **95.069 Dreiecke** dem Dach zu.
- Dabei verschwinden **sechs Körperdreiecke** oberer Betonabschlüsse:
  jeweils zwei in `center1_25`, `center1_28.001`, `center1_34.001`.
- Zugleich verbleiben **1.853 Dreiecke der front3-Familie** im Körper:
  Dachstützen, Rand-/Rahmenteile und Leitern bleiben teilweise sichtbar.
- Das ist kein Defekt der Prüfsummen, sondern eine unzureichende
  Präfix-/Höhentrennung. Keine Rangteile als Crowd umdeklarieren, keine
  beliebige neue Höhenschwelle als angebliche Lösung ausgeben.

### Arbeitsauftrag

1. Original-Bundle einschließlich Zusatzwurzeln erneut inventarisieren.
   Exakte Meshnamen, Hierarchie, Materialien und Bounds pro Bauteil belegen.
2. Dachhaut, Membran, Tragwerk, Flutlichtbauteile und gegebenenfalls
   vorhandene Tafeln samt Halterungen gezielt vom festen Stadionkörper trennen.
   Nicht jedes `front3_*` allein wegen des Namens pauschal entfernen:
   feste Fassaden-/Körperteile anhand ihrer tatsächlichen Funktion zuordnen.
3. Bevorzugt eine quellengetreue Aufbereitung mit eindeutig separaten
   Dachmeshes liefern, die der vorhandene generische Vertrag darstellen kann.
   Transformationen, Materialien und nicht betroffene Körpergeometrie erhalten.
4. Falls dafür eine generische Erweiterung wie exakte `roofMeshNames`
   erforderlich ist: benötigten Vertrag separat präzise vorschlagen.
   **Keine nicht unterstützten Manifestfelder voraussetzen und keinen
   vereinsspezifischen Renderer-Patch liefern.** Implementierung in Replit
   bleibt ein gesonderter Auftrag.
5. Neue Nachrechnung: keine falsch entfernten Körperdreiecke; keine
   unbeabsichtigt stehen gebliebenen Teile des abschaltbaren Dachs.
   Bewusst verbleibende feste Stützen gesondert begründen.
6. Dach an/aus aus identischen Kameras zeigen: Editor, Ticker, Draufsicht,
   Gegenseite und Sitzkamera. Nicht nur Textur-/Hashprüfungen vorlegen.

## 4. Geländeanschluss belegen, nicht kaschieren

- Originalmodell: Spielfeld bei **y=0**, Umlauf/Vorplatz ungefähr **y=7,7**.
- Renderer-Umfeldboden ungefähr **y=-0,35**. Nach Entfernung der Kulisse
  steht deshalb der Umlauf deutlich über dem Umfeld.
- Ausgeschlossene Quell-Vorplatzplatten `center2_1/4` einfach wieder
  einzublenden ist keine abgenommene Lösung: sie erzeugen hohe Kanten und
  verdecken OSM-Straßen-/Parkflächen.

### Arbeitsauftrag

1. Originale Geländelage, Eingänge, Umlauf, Sockel und Übergänge an der
   Quelle untersuchen; Stadionkörper und reine Kulissenflächen unterscheiden.
2. Einen nachvollziehbaren Anschluss an das vollständige OSM-Umfeld
   vorbereiten. Keine frei erfundenen Böschungen, Berge oder flächigen
   Abdeckplatten als Quellgeometrie ausgeben.
3. Spielfeld, Sitzpositionen und Stadionmodell nicht pauschal anheben oder
   absenken: ihre gemeinsame Lage muss unverändert konsistent bleiben.
4. Braucht die Lösung eine neue generische Gelände-/Höhenfunktion im
   Renderer, die Anforderung mit Koordinaten, betroffenen Flächen,
   Quellen und Vorher-/Zielbildern separat liefern. Keine stillschweigende
   globale Bodenhöhenänderung; keine anderen Stadien verändern.
5. Nahansichten der Übergänge und weite Ansichten von allen vier Seiten
   liefern. Straßen, Parkflächen und Gebäude dürfen nicht verdeckt oder
   abgeschnitten werden.
6. Falls mit den verfügbaren Quellen keine belastbare Lösung möglich ist,
   ausdrücklich als offen melden statt einen korrigierten Stand zu behaupten.

## 5. Umfeld, Licht und erhaltene Quellen

- Vollständiges lokal mit dem Paket übereinstimmendes Umfeld:
  **26 Gebäude, 189 Straßen, 47 Grünflächen, 0 Wasserflächen**.
- Keine ungültigen Flächen festgestellt; keine Ausnahme und keine
  Polygonlöschung freigegeben. Gebäude nicht automatisch herausfiltern.
- Geografische Gegenprobe: Bürgermeister-Ulrich-Straße NORD, B 17 OST,
  XXXLutz Südost, Trainingsplatz und Kurt-Bösch-Straße WEST.
- **Lichtfaktor 1 beibehalten**, Fixture-Intensität **60**.
  Zwölf Laufzeitleuchten repräsentieren 50 Quellleuchten. Nicht erneut
  multiplizieren; Montageorte, Richtungen, Winkel, Farben, Reichweiten
  und Gruppen erhalten.
- Gelieferte Bildvergleiche zeigen bereits hellen Rasen bei dunkleren
  Rängen. Eine globale Verstärkung ist keine Lösung für die Ranghelligkeit.
  Die Bilder sind keine unabhängige Prüfung physikalischer Abschattung.
- Keine Fangnetze erfinden. Quell-Ausschlüsse und transparente Materialien
  erhalten, soweit die neue Quellenprüfung keine begründete Abweichung zeigt.

## 6. Übergabe und Grenzen des bisherigen Reviews

- Ausgangsversion: `2e3fd6a59307b6ea`, Geometriehash
  `7fedb4c8cf937ddf6b2538577f1a6dbac14b968296a7e399b5630e2a8210e029`.
- Ausgangspaket: **154 Prüfsummen**, **67 gültige Assets**,
  identische Manifestkopien; Spielfeld unabhängig **105 × 68 m** gemessen.
- Das Original-Unity-Bundle war beim Replit-Review nicht vorhanden.
  Der Review bestätigte Exportdaten, nicht eine neue Originalextraktion.
- Bisherige Bilder sind gelieferte Paketbelege, keine neu in Replit
  gerenderte Abnahmeserie.
- Neue Geometrie braucht neue passende Hashes/Assetversion, identische
  Manifestkopien, vollständige Prüfsummen, klare Änderungsnachweise und
  reproduzierbare Werkzeuge. Alte Bilder als historischen Stand kennzeichnen.
- Neues Paket zunächst zur Prüfung liefern. Die Metadatenkorrektur ist
  **keine Abnahme der Dach-/Geländekompromisse und keine Importfreigabe**.
