# Websoccer - Spielstaerkemodell

Dieses Dokument ist die fachliche Basis fuer das geplante Spielstaerkemodell. Es ist bewusst als Arbeitsstand formuliert und soll in spaeteren Sprints weiter verfeinert werden.

## Kernidee

Die Spielstaerke soll nicht einfach eine sichtbare Zahl pro Spieler sein. Sie ist das Herzstueck des Spiels: realistisch, regelmaessig aktualisierbar, fuer Manager aber nicht vollstaendig transparent.

Die wahre Staerke entsteht aus langfristiger Grundqualitaet, aktueller Form, Positionsfit, Frische und kleinen Kontextfaktoren. Der Marktwert ist sichtbar und psychologisch wichtig, beeinflusst aber niemals die sportliche Staerke.

Arbeitsformel:

```text
Base-Staerke = EA-Wert + FM-Wert

Live-Staerke =
Base-Staerke
+ Formmodifier
+ Erfahrungsmodifier
+ National-/Reputationsmodifier
+ Moralmodifier

Effektive Spielstaerke =
Live-Staerke
* Positionsfit
* Frischefaktor
```

Danach werden Softcap und Begrenzung auf 0-200 angewendet.

Fuer die spaetere Match-Simulation kommt zusaetzlich ein rein spielbezogener Potential-Peak hinzu. Dieser Peak gilt nur fuer ein einzelnes SIM-Spiel und veraendert weder Base-Staerke noch langfristige Spielerentwicklung.

## Grundprinzipien

- Die Staerke laeuft auf einer Skala von 0-200.
- Die exakte interne Staerke sehen nur Admins.
- Manager sehen indirekte Hinweise wie Marktwert, Positionen, Formstatus, Frische, Zufriedenheit, Statistiken, Alter, Verein und Nationalitaet.
- Marktwert hat 0 Einfluss auf Spielstaerke, Form, Positionswert oder Simulation.
- Marktwert ist relevant fuer Gehalt, Transfers, Prestige, Budgetplanung, Vereinswert und Managerpsychologie.
- Base-Staerke ist langfristige Grundqualitaet.
- Form ist ein separater Modifier und veraendert die Base nicht dauerhaft.
- Keine Positionsgruppen und keine automatische Positionsverwandtschaft.
- Frische wirkt als Multiplikator und zwingt Manager zur Rotation.

## Base-Staerke

Die Base-Staerke wird in Version 1 aus EA und FM gebildet:

```text
Base-Staerke = EA-Wert + FM-Wert
```

Beispiele:

- EA 84 + FM 86 = Base 170
- EA 66 + FM 74 = Base 140

Wenn nur eine Quelle vorhanden ist:

- nur EA vorhanden: `Base = EA * 2`
- nur FM vorhanden: `Base = FM * 2`
- keine Quelle vorhanden: `Base = 40.00`

Alle internen Staerken werden mit zwei Dezimalstellen berechnet und angezeigt.

Spieler mit nur einer Quelle oder Default-Base werden intern markiert:

- Datenqualitaet niedrig/mittel
- Adminpruefung empfohlen
- Default 40.00 muss in der Django-Datenpruefung sichtbar sein

Aktuelle Quellenstrategie:

- Version 1: EA + FM
- Version 1.5: Adminpruefung fuer Spieler mit Default 40.00
- Version 2: weitere Quellen nur bei echtem Mehrwert

Wenn EA oder FM spaeter aktualisiert wird, wird die Base durch das naechste bestaetigte Update geaendert. Form bleibt davon getrennt.

## Sichtbarkeit

Manager sehen nicht:

- Base-Staerke
- Live-Staerke
- effektive Spielstaerke
- exakte Formmodifier
- exakte Positionsberechnung
- exakte Softcap
- Admin-Korrektur

Manager sehen oder koennen sehen:

- Name
- Alter
- Nationalitaet
- Groesse
- Fuss
- Positionen
- Marktwert
- Gehalt
- Vertrag
- Frische
- Zufriedenheit
- Formstatus
- Statistiken
- Verletzungsstatus
- grobe Profilbeschreibung
- Datenstand wie aktuell / laenger nicht geprueft

## Kernattribute

Das Modell nutzt sieben Kernbereiche:

- Offensive
- Defensive
- Spielaufbau
- Athletik
- Torhueter
- Standards
- Erfahrung / Spielintelligenz

Offensive beeinflusst Abschluss, Chancenverwertung, Offensivlaeufe, Dribbling in gefaehrlichen Raeumen und Torgefahr.

Defensive beeinflusst Zweikaempfe, Tackling, Stellungsspiel, Balleroberung, Defensivverhalten und Abfangen.

Spielaufbau beeinflusst Passen, Ballverteilung, Uebersicht, Spielintelligenz mit Ball, Aufbauspiel, Pressingresistenz und Kreativitaet.

Athletik beeinflusst Tempo, Dynamik, Robustheit, Ausdauer, Zweikampfstabilitaet, Pressingfaehigkeit, Frischeverlust und Leistung ueber 90 Minuten.

Torhueter ist fast nur fuer TW relevant und beeinflusst Paraden, Reflexe, Strafraumbeherrschung, Eins-gegen-eins sowie Abschlaege/Aufbau anteilig.

Standards beeinflussen Elfmeter, Freistoesse, Ecken, Flanken aus Standards und direkte Standardsituationen. Standards duerfen die Gesamtstaerke nicht dominieren.

Erfahrung / Spielintelligenz ersetzt einen freien Mentalitaetswert. Quellen koennen Profispiele, Minuten, Liga-Level, internationale Spiele, Nationalmannschaft, Kapitaensrolle, Stammspielerrolle und Positionskonstanz sein. Alter selbst ist kein direkter Erfahrungswert.

## Positionen

Gesetzte Positionen:

- TW
- IV
- LV
- RV
- LOV
- ROV
- DM
- ZM
- LM
- RM
- OM
- ROM
- LOM
- LF
- RF
- ST

Jeder Spieler bekommt:

- bis zu 3 Hauptpositionen
- bis zu 3 Nebenpositionen

Positionsfit:

- Hauptposition: `1.00`
- Nebenposition: `0.90`
- fremde Feldposition: ca. `0.70`
- komplett unlogische Feldposition: ca. `0.50-0.60`
- Feldspieler im Tor: ca. `0.25-0.40`
- Torwart im Feld: ca. `0.25-0.40`

Positionsverwandtschaft wird nicht automatisch abgeleitet. Ein IV kann also nicht einfach sinnvoll LV/RV spielen, nur weil er Verteidiger ist. Das muss explizit als Nebenposition gepflegt sein.

## Positionsgewichtung

Jede Position gewichtet die sieben Kernattribute anders.

Beispiele:

- IV: Defensive hoch, Athletik mittel, Spielaufbau mittel, Erfahrung mittel, Offensive niedrig, Standards niedrig/mittel
- LV/RV: Defensive hoch, Athletik hoch, Spielaufbau mittel, Offensive mittel
- LOV/ROV: Offensive hoeher als LV/RV, Athletik hoch, Spielaufbau wichtig, Defensive weiterhin relevant
- DM: Defensive hoch, Spielaufbau hoch, Erfahrung wichtig, Athletik mittel, Offensive gering
- ZM: Spielaufbau hoch, Athletik mittel, Defensive mittel, Offensive mittel, Erfahrung wichtig
- OM: Offensive hoch, Spielaufbau hoch, Standards anteilig, Defensive gering
- LF/RF: Offensive hoch, Athletik hoch, Spielaufbau/Dribbling hoch, Defensive gering bis mittel
- ST: Offensive sehr hoch, Athletik mittel/hoch, Erfahrung mittel, Spielaufbau gering/mittel, Defensive niedrig
- TW: Torhueterwert sehr hoch, Erfahrung mittel, Athletik mittel, Spielaufbau gering/mittel

Dadurch kann ein Spieler auf mehreren Positionen existieren, aber je nach Attributprofil dort unterschiedlich stark sein.

## Formmodell

Form ist der zentrale dynamische Unterschied zu vielen Websoccer-Systemen.

Base = langfristige Qualitaet  
Form = aktuelle reale Leistung

Geplante Formebenen:

- Kurzform: letzte 3-5 Spiele
- Mittelform: letzte 8-12 Spiele
- Saisonform: laufende Saison

Beispielgewichtung:

```text
Formmodifier =
50 % Mittelform
+ 30 % Kurzform
+ 20 % Saisonform
```

Startdaten fuer Version 1:

- Spielminuten
- moegliche Spielminuten
- Minutenquote
- Startelfquote
- Tore
- Vorlagen
- Score, z. B. FotMob/API-Score
- Verletzungsstatus
- Positionsdaten

API-Football und SportDB/Flashscore werden als automatische Testquellen fuer Version 1 genutzt. Die Daten werden nicht ueber Widgets, sondern serverseitig per Management Command importiert und lokal gespeichert.

Pilot-IDs:

- Bundesliga V3: `78`
- FC Bayern Muenchen: `157`
- Harry Kane: `184`

Hinweis: Der API-Football-Free-Plan erlaubt aktuell nicht jede Season. Beim ersten Test war `2025` gesperrt, `2024` funktionierte.

SportDB/Flashscore-Pilot:

- Bundesliga: `/api/flashscore/football/germany:81/bundesliga:W6BOzpK2`
- Harry Kane Flashscore-ID: `v5HSlEAa`
- aktueller Importer: `import_sportdb_flashscore_form`
- getestete Werte: Spielteilnahme, Startelf, Einwechslung, Minuten, Minutenquote, Flashscore-Rating, Tore, Vorlagen und Karten

Wichtigster Wert:

```text
Minutenquote = gespielte Minuten / moegliche Minuten
```

Formbestandteile:

- Minutenform
- Scoreform
- Scorerform
- Verfuegbarkeitsform

Tore und Vorlagen zaehlen positionsabhaengig, duerfen Form aber nicht dominieren.

## Form-Caps

Form darf Spieler bewegen, aber nicht die komplette Hierarchie zerstoeren.

Vorschlag:

- Base unter 110: maximal `+10`
- Base 110-139: maximal `+14`
- Base 140-159: maximal `+16`
- Base 160-179: maximal `+10`
- Base 180+: maximal `+6`

So koennen gute Wochen sichtbar werden, ohne dass ein mittlerer Spieler kurzzeitig automatisch Weltklasse wird.

## Softcap

Ab hohen Staerkebereichen wirken Boni reduziert.

Vorschlag:

- bis 150: Boni wirken zu 100 %
- 151-170: Boni wirken zu 75 %
- 171-185: Boni wirken zu 50 %
- ab 186: Boni wirken zu 25 %

200 soll absolute Ausnahme bleiben, kein normaler Weltklassewert.

## Erfahrung

Erfahrung bleibt ein kleiner Stabilisator, kein Hauptmotor.

Rahmen:

- wenig Erfahrung: `-2` bis `0`
- normale Erfahrung: `0` bis `+2`
- etablierter Stammspieler: `+3` bis `+5`
- international erfahrener Spieler: `+5` bis `+7`
- absoluter Leader: maximal `+8`

## Nationalmannschaft / Reputation

Nationalspielerstatus soll spaeter nicht binaer sein. Moegliche Faktoren:

- A-Nationalteam oder U21
- Staerke der Nation
- Stammspieler oder Kaderfueller
- Pflichtspiele oder Freundschaftsspiele
- Turniererfahrung

Einfluss bleibt klein, etwa maximal `+4` bis `+6`, und unterliegt der Softcap.

## Frische

Frische wirkt als Multiplikator:

- 95-100 Frische: 100 %
- 85-94: 97 %
- 75-84: 94 %
- 65-74: 90 %
- 55-64: 85 %
- 45-54: 78 %
- unter 45: 70 % plus hoeheres Verletzungs-/Leistungsrisiko

Frischeverlust:

- normaler Feldspieler: ca. `-10` pro 90 Minuten
- hohe Athletik: ca. `-8`
- niedrige Athletik: ca. `-12`
- Torhueter: ca. `-3`
- hoher Einsatz: zusaetzlicher Verbrauch

Frischeverlust wird nicht stark positionsabhaengig gemacht, damit das System nachvollziehbar bleibt.

## Potential-Peak pro Match

Potential soll nicht als dauerhaftes Karrierewachstum verstanden werden. Es ist ein optionales Match-Modul fuer die Simulation.

Grundidee:

- Ein Spieler hat eine aktuelle interne Staerke.
- Zusaetzlich kann es einen Potentialwert aus einer Quelle wie FM geben.
- Die Differenz zwischen aktueller Staerke und Potential beschreibt, wie weit ein Spieler in einem einzelnen Spiel theoretisch ueber seine normale Tagesleistung hinauswachsen kann.
- Dieser Ausschlag gilt nur fuer dieses eine SIM-Spiel.
- Danach bleibt die Base-Staerke unveraendert.

Beispiel:

- Jamal Musiala hat in einer Quelle aktuell `83` und Potential `93`.
- In den meisten Spielen liegt seine spielbezogene Leistung nahe an `83`.
- Manchmal kann er in Richtung `85`, `87` oder `89` ausschlagen.
- Sehr selten kann er fuer genau dieses eine Spiel sein volles Potential von `93` erreichen.
- Im naechsten Spiel wird neu berechnet.

Wichtig:

- Manager sehen weder die exakte aktuelle Staerke noch das exakte Potential.
- Das Potential ist kein garantierter Zielwert.
- Der Peak veraendert keine Base-Staerke.
- Der Peak ist kein langfristiges Entwicklungssystem.
- Der Peak ist ein temporaerer Simulationsfaktor.

Arbeitsformel fuer die Match-Simulation:

```text
Match-Staerke =
Effektive Spielstaerke
+ Potential-Peak-Bonus
```

Der `Potential-Peak-Bonus` darf niemals ueber das hinterlegte Potential hinausfuehren.

### Bedeutung der Potentialluecke

Potentialluecke bedeutet:

```text
Potentialluecke = Potentialwert - aktueller Staerkewert
```

Je groesser diese Luecke ist, desto groesser ist die theoretische Ausschlaghoehe in einem einzelnen Spiel.

Beispiel:

- Spieler A: aktuell `83`, Potential `93`, Luecke `10`
- Spieler B: aktuell `94`, Potential `95`, Luecke `1`

Spieler A kann in einzelnen Spielen deutlich staerker ueber seinem Normalwert performen. Spieler B ist bereits nahe am Maximum und hat dadurch kaum Peak-Spielraum.

Das bedeutet nicht, dass Spieler A haeufiger sein volles Potential erreicht. Es bedeutet nur, dass sein moeglicher Ausschlag groesser ist, wenn der Peak eintritt.

### Verlaesslichkeit vs. Ausschlag

Das System soll unterschiedliche Spielertypen erzeugen:

- Veteranen und etablierte Topspieler: konstant, verlaesslich, kleinere Peak-Spanne
- junge oder weniger gefestigte Spieler: schwankender, aber mit groesserer Peak-Gefahr
- Rohdiamanten: niedrigere Basis, groessere Varianz, selten sehr hohe Ausschlaege
- Stars nahe am Potential: hohe Basis, kleine Varianz

Beispiel:

- Harry Kane `94/95`: fast immer sehr stark, aber kaum zusaetzlicher Peak
- Joshua Kimmich `89/92`: hohe Konstanz, kleine bis mittlere Ausschlaege
- Leon Goretzka `77/85`: solide Basis mit gelegentlichem groesserem Ausschlag
- sehr junges Talent `60/80`: schwankend, meistens normal, selten deutlich ueber Normalwert

### Einflussfaktoren

Fuer Version 1 des Potential-Peaks koennen diese Faktoren die Peak-Chance oder Peak-Hoehe beeinflussen:

- gute reale Form erhoeht die Peak-Chance
- hohe Frische erhoeht die Peak-Chance
- Einsatz auf Hauptposition erhoeht die Peak-Chance
- Einsatz auf Nebenposition senkt sie leicht
- Einsatz auf fremder Position senkt sie deutlich
- schlechte Moral/Zufriedenheit kann die Peak-Chance senken, sobald das Moralsystem definiert ist
- junges Alter kann die Peak-Varianz erhoehen, muss aber noch feinjustiert werden

Bewusst nicht Teil von Version 1:

- Derby-Bonus
- Pokalspiel-Bonus
- Bonus gegen grosse Gegner
- besondere Story-/Narrativfaktoren

Diese Faktoren koennten spaeter geprueft werden, sind fuer den Start aber zu detailliert.

### Verteilung

Die Verteilung soll nicht linear sein. Das volle Potential soll selten erreicht werden.

Beispielhafte Denklogik bei `83/93`:

- meistens nahe an `83`
- manchmal leichte Ausschlaege wie `85` oder `87`
- selten hohe Ausschlaege wie `90`
- sehr selten volles Potential `93`

Die genauen Wahrscheinlichkeiten sind noch offen und muessen spaeter mit Simulationstests balanciert werden.

### Sichtbarkeit fuer Manager

Manager sehen keine exakte Potentialzahl und keine exakte Peak-Chance.

Moegliche indirekte Hinweise:

- konstant
- verlaesslich
- schwankend
- kann Spiele praegen
- talentiert, aber unbestaendig
- nahe am Leistungsmaximum

Diese Hinweise duerfen keine versteckte Potentialzahl rekonstruierbar machen.

## Verletzungen

Real-Life-Verletzungen fuehren nicht automatisch zu Sperren und nicht direkt zu Staerkeverlust.

Grundlinie:

- RL-Verletzung wirkt ueber fehlende Minuten und dadurch sinkende Form.
- Frische-Regeneration kann reduziert werden.
- Keine direkte Qualitaetsabwertung.
- Keine automatische Sperre im Websoccer.

Vorschlag:

- RL-verletzt: Frische-Regeneration `-25 %`
- Sobald die offizielle Quelle den Spieler wieder fit meldet: normale Regeneration

Verletzungsstatus gilt nur aus festgelegten Quellen, nicht aus Geruechten, Foren oder Einzelartikeln.

## Moral / Zufriedenheit

Moral ist ein Websoccer-Spielmechanismus, kein Real-Life-Leistungswert.

Moegliche Faktoren:

- Spielzeit im Websoccer
- Rolle im Team
- Vertragszufriedenheit
- Gehalt
- Wechselwunsch
- Vereinserfolg
- Kaderstatus
- Manager-Versprechen

Vorschlag:

- sehr unzufrieden: `-5` bis `-8`
- unzufrieden: `-2` bis `-4`
- neutral: `0`
- zufrieden: `+1` bis `+2`
- sehr zufrieden: `+3` bis `+5`

## Admin-Korrektur

Admin-Korrekturen sind erlaubt, aber nicht dauerhaft.

Sobald die Base-Staerke durch EA/FM aktualisiert wird, verfaellt die Admin-Korrektur.

Beispiel:

- vorher: EA + FM = 132, Admin-Korrektur +6, finale Base 138
- nach Update: EA + FM = 140, Admin-Korrektur verfaellt, finale Base 140

Alles wird protokolliert:

- wer geaendert hat
- wann geaendert wurde
- alter Wert
- neuer Wert
- Grund
- warum Korrektur verfallen ist

## Manager-Updateantraege

Manager koennen fuer eigene Spieler eine Datenpruefung beantragen.

Moegliche Angaben:

- SoFIFA-Link
- FM-Link, Screenshot oder Exportwert
- FotMob-Link
- Transfermarkt-Link
- Bemerkung

Manager aendern keine Werte direkt. Sie stellen nur einen Antrag.

Admin-Warteschlange:

- Spieler
- Verein
- Antragsteller
- Quelle
- aktueller gespeicherter Wert
- vorgeschlagener neuer Wert
- letzte Pruefung
- moegliche neue Base

Admin-Aktionen:

- uebernehmen
- korrigiert uebernehmen
- ablehnen

## Updateprozess

Es gibt keine taeglichen Pflichtupdates.

Geplant:

- manuelle Updates nach Bedarf
- gelegentliche Updates, wenn sinnvoll
- ein groesseres Wochenupdate

Woechentlicher Ablauf:

1. EA/FM-Daten pruefen oder importieren
2. Formdaten aktualisieren
3. Verletzungsstatus pruefen
4. Vereinswechsel pruefen
5. Positionen pruefen
6. Base bei bestaetigter Quellenaenderung neu berechnen
7. Admin-Korrektur ggf. verfallen lassen
8. Formmodifier neu berechnen
9. grosse Spruenge markieren
10. Audit-Log schreiben

Admin-Markierungen:

- gruen: aktuell
- gelb: laenger nicht geprueft
- rot: sehr lange nicht geprueft, Quelle fehlt, grosser Sprung oder Konflikt

Warnungen:

- Spieler +10 oder mehr Base seit letztem Update
- Spieler ohne EA/FM-Match
- Spieler mit Vereinswechsel
- Spieler mit Positionsaenderung
- Spieler mit Verletzungsstatus
- Spieler lange nicht aktualisiert
- Spieler nur mit einer Quelle
- Manager-Antrag offen

Das Dashboard ist wichtiger als Vollautomation.

## Quellenstrategie

EA / SoFIFA:

- praktisch als EA-Datenquelle
- kein Kernfokus auf automatisches Scraping
- moegliche Wege: Kaggle-CSV, manuelle Pflege, halbautomatischer Import, Manager-Antrag mit SoFIFA-Link

Kaggle:

- fuer Entwicklung, interne Pflege, CSV-Import und Testdaten nutzbar
- nicht oeffentlich damit werben
- Rohdaten nicht oeffentlich anzeigen
- Import immer protokollieren

FM:

- wahrscheinlich gut fuer CSV-/Exportlogik
- FM-ID als Mapping nutzen
- FM-/Facepack-Bilder nicht automatisch oeffentlich nutzen

API-Football:

- fuer Formdaten testbar
- Entwicklung zunaechst Free
- spaeter Abo fuer Launch/Testphase pruefen
- Daten pro Liga/Team/Saison holen und lokal speichern, nicht tausende Spieler einzeln abfragen

SportDB / Flashscore:

- aktueller Favorit fuer den Formdaten-Pilot, weil die aktuelle Bundesliga-Saison erreichbar ist
- liefert ueber Match-Endpunkte Lineups, Ratings, Events, Tore, Vorlagen, Karten und Wechselinformationen
- Import vorsichtig drosseln, da zu viele Requests schnell Rate-Limits ausloesen koennen
- Playerstats sind gross und werden nur optional geladen; Lineups und Details reichen fuer den ersten Formscore

FotMob / Sofascore:

- fuer Formdaten interessant
- technisch/zugriffsseitig schwieriger
- optional pruefen, nicht als feste Kernabhaengigkeit einplanen

Transfermarkt:

- nutzbar fuer Marktwert, Geburtsdatum, Nationalitaet, Positionen als Kontext, Verein und Mapping-ID
- nicht fuer Staerke, Form oder spielerische Qualitaet nutzen
- Bilder/Wappen nicht oeffentlich uebernehmen

## Empfohlene Datenstruktur

```text
Player
- id
- name
- birth_date
- nationality
- height
- foot
- ws_club
- real_life_club
- market_value

PlayerExternalID
- player_id
- source
- external_id
- source_url
- last_checked

PlayerBaseRating
- player
- ea_rating
- fm_rating
- base_strength
- data_quality
- last_base_update

PlayerAttributes
- player
- offensive
- defensive
- buildup
- athletic
- goalkeeper
- set_pieces
- experience

PlayerPosition
- player
- position
- type: main / secondary
- factor

PlayerStatus
- player
- ws_injury_type
- ws_injury_days_remaining
- ws_suspension_reason
- ws_suspension_matches_remaining

PlayerFormSnapshot
- player
- source
- fixture_id
- date
- minutes_played
- possible_minutes
- minutes_quote
- starts
- goals
- assists
- score
- injury_status
- source

PlayerStrength
- player
- base_strength
- form_modifier
- experience_modifier
- national_modifier
- morale_modifier
- live_strength
- freshness
- effective_strength
- calculated_at

PlayerStrengthAudit
- player
- old_value
- new_value
- changed_by
- reason
- source
- created_at
```

Quellen fuer `PlayerExternalID`:

- transfermarkt
- sofifa
- fm
- api_football
- fotmob
- sofascore

## Beispielrechnung

Spieler:

- EA: 78
- FM: 76
- Base: 154
- Formmodifier: +8
- Erfahrung: +3
- Nationalteam: +1
- Moral: +2

Live:

```text
154 + 8 + 3 + 1 + 2 = 168
```

Position und Frische:

- Hauptposition = 100 %
- Frische 88 = 97 %

Effektiv:

```text
168 * 1.00 * 0.97 = 163
```

Admin sieht:

- Base: 154
- Form: +8
- Live: 168
- Effektiv: 163

Manager sieht hoechstens:

- Form: gut
- Frische: 88 %
- Zufriedenheit: hoch
- Marktwert: X Mio.

## Feststehende Entscheidungen

- Staerke 0-200
- Base = EA + FM
- falls nur eine Source existiert: vorhandene Source * 2
- falls keine Source existiert: Default-Base 40.00 plus Admin-Markierung
- alle Staerken werden mit zwei Dezimalstellen berechnet und angezeigt
- Marktwert hat keinen Einfluss auf Staerke
- Staerke bleibt fuer Manager versteckt
- Form ist separater Modifier
- Form veraendert Base nicht dauerhaft
- keine Positionsgruppen
- keine automatische Positionsverwandtschaft
- bis zu 3 Hauptpositionen, bis zu 3 Nebenpositionen
- Positionsfit mit hartem Fremdpositionsmalus
- Frische als Multiplikator
- Athletik beeinflusst Frischeverlust leicht
- Torhueter verlieren weniger Frische
- Verletzungen fuehren nicht zu Sperren
- Admin-Korrektur verfaellt bei Base-Update
- Manager koennen Datenpruefung beantragen
- Admin entscheidet ueber Updates
- Spielerbearbeitungsantraege zeigen alten Wert rot, neuen Wert gruen und koennen im Admin angenommen oder abgelehnt werden
- Ligen erhalten einen Koeffizienten, damit Form- und Leistungsdaten aus verschiedenen Wettbewerbsstaerken gewichtet werden koennen
- Kaggle kann intern als CSV-Quelle genutzt werden
- FM-ID, EA-ID, TM-ID und API-ID werden als Mapping gespeichert
- Potential-Peak ist ein temporaerer Match-Faktor und keine dauerhafte Entwicklung
- Potential-Peak darf die Base-Staerke nicht veraendern
- Manager sehen keine exakte Potentialzahl und keine Peak-Wahrscheinlichkeit

## Offene Punkte

- exakte Positionsgewichtungen
- exakte Form-Cap-Werte
- exakte Softcap-Kurve
- welche API fuer Formdaten genutzt wird
- wie Verletzungen konkret Frische beeinflussen
- wie stark Moral wirkt
- wie Erfahrung genau berechnet wird
- wie Nationalmannschaft bewertet wird
- welche Attribute aus EA/FM genau in die sieben Bereiche laufen
- wie viel Form Spieler aus schwaecheren/staerkeren Ligen bekommen
- wie Liga-Level einbezogen wird
- wie Manager-Updateantraege genau aussehen
- exakte Wahrscheinlichkeitsverteilung fuer Potential-Peaks pro Match
- ob und wie stark Alter die Peak-Varianz beeinflusst
- wie Potentialwerte aus FM oder anderen Quellen auf die 0-200-Skala uebertragen werden

## Ein-Satz-Zusammenfassung

Die langfristige Qualitaet eines Spielers entsteht aus EA + FM, seine aktuelle Staerke aus realer Form, Frische, Positionsfit und kleinen Kontextmodifikatoren, waehrend Marktwert nur fuer Gehalt und Wahrnehmung relevant bleibt.
