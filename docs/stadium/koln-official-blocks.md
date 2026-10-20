# Köln: FC-Blockplan 2026/27 im 2D-Editor

## Quellen und Aussagegrenze

Am 20.10.2026 von der aktuellen Vereinsseite abgerufen und visuell verglichen:

- Seite: <https://fc.de/club/ueber-den-fc/spiel-und-trainingsstaette/rheinenergiestadion>
- Aktuell dort verlinkte „Tribüne- und Blockübersicht“:
  <https://images.ctfassets.net/nurz7nsnha04/1drujCRR6glLPE8lUq5YL0/7d0692accee51fb318caa1a742be4a8d/Lageplan_Stadion_2627.png>
- SHA-256 des unveränderten Plans:
  `6a43f986fd76002b04b30b9c011c2dc04cce692ee47ad543ab94b4ff0b76537d`
- Unity-Sitzquelle `koln_1792488328917.json`, SHA-256:
  `7ed9b68df8befccc1637786af57a4470da68db424c6e419efca9ca6c8f0e81f2`

**Belegt sind Bezeichnungen, Rang, Reihenfolge, Tribünenseite und Fanbereiche.
Nicht belegt sind vermessene Grenzen jedes offiziellen Blocks in der Unity-Datei.**
Der FC-Plan ist schematisch; Unity enthält acht benannte Sitzquellgruppen,
keine offiziellen Blocknummern. Auch die sichtbaren Gänge bilden keine
nachgewiesene 1:1-Blocknummerierung. Deshalb zeigt der Editor ausdrücklich
„schematische Plansektoren auf den Unity-Sitzgruppen“. Die ursprüngliche
3D-Crowd wird weder aufgeteilt noch verändert.

Die vollständige maschinenlesbare Zuordnung mit Quellgruppen, tatsächlichen
Sitzpunktzahlen und Modell-Koordinatenintervallen steht in
`stadium_editor/blueprints/v2/koln_official_blocks.json`.
Jeder der 46.424 Quellpunkte gehört genau einem Sektor an. Seine Anzahl ist
ausschließlich ein Herkunftsbeleg, niemals eine wirtschaftliche Blockkapazität.

## Räumliche Zuordnung

Modellrahmen nach der bereits belegten +90°-Sitzdrehung:
`x=b, z=-a` aus Quellposition `[a,y,b]`.
`+x=Ost, -x=West, +z=Nord, -z=Süd`. Die gespeicherte Editor-Geometrie
verwendet anschließend unverändert den vorhandenen `axisTheta`-Frame.
Die Rangtrennung liegt bei `y=12 m`, in der tatsächlichen Lücke zwischen
Unter- und Oberrang.

| Seite | Unterrang | Oberrang | Reihenfolge im nordgerichteten Plan | Sitzquellen |
|---|---|---|---|---|
| Nord | N1–N6 | N11–N16 | West → Ost | `C_left1_C1-UltraHome`, `C_left1_C1-UltraAway`; unten zusätzlich `C_back1_C1-UltraAway` |
| Süd | S1–S6 | S11–S16 | Ost → West | unten `C_right1_C3-UltraHome`, oben `C_right1_C1-UltraHome` |
| Ost | O1–O8 | O11–O18 | Nord → Süd | `C_back1_C1-UltraHome` |
| West | W1–W8 | W11–W18 | Süd → Nord | unten `C_front1_C1-UltraHome`, oben `C_front3_C1-UltraHome` |

**Heimkurve:** S1–S6 im südlichen Unterrang. Der unveränderte wirtschaftliche
Süd-Stehplatz-Bucket wird auf diese unteren, nicht auf obere Hüllen verteilt.

**Gäste:** N6 unten sowie N15/N16 und O11 oben in der Nordost-Ecke.
Für die Nordseite liefert die Quelle eine zusätzliche harte räumliche
Trennung: alle `UltraAway`-Punkte liegen östlich aller dortigen `UltraHome`-
Punkte. Der Schnitt liegt jeweils in der tatsächlichen Lücke zwischen beiden
Gruppen. Damit liegen sämtliche Nord-Gästequellpunkte ausschließlich in
N6 bzw. N15/N16; kein Gastquellpunkt wandert in N5/N14.
O11 wird aus dem im Modell allgemein als `UltraHome` benannten
Ost-Oberrang über den offiziellen FC-Plan zugeordnet. Unity-Namen sind
also ausdrücklich nicht alleiniger Nachweis der aktuellen Fanbereiche.

Innerhalb der übrigen Bereiche folgen die Schnitte der Reihenfolge und
Anzahl des schematischen FC-Plans. Hüllen erhalten ihre radialen und
Höhen-Grenzen aus den ihnen tatsächlich zugeordneten Quellpunkten.
Sie sind **keine Behauptung exakter historischer Gangverläufe**.
Die VIP-Klassifikation mittlerer West-Blöcke ist ein Darstellungsadapter für
den vorhandenen Spiel-Bucket, keine Aussage über offizielle VIP-Einzelzahlen.

## Ökonomie und vorhandene Entwürfe

- `Stadium` bleibt alleinige Kapazitätsquelle. Im eingebauten Ausgangsstand:
  **50.000 insgesamt**, alle zwölf Tribünen-/Sitzart-Buckets unverändert.
- Kein Rückschluss von 46.424 Quellpunkten, Rastergröße oder offiziellen
  Blocknamen auf Kapazität, Preise, Ausbaukosten oder Einnahmen.
- Bestehendes Umfeld, Dach, Umriss, Modellmanifest und 3D-Quellen bleiben erhalten.
- Alte Hüllen haben IDs 0–32, neue Planbereiche IDs 1000–1055.
  Ein alter Browserentwurf scheitert damit an unbekannten IDs, statt
  versehentlich auf andere Blöcke geschrieben zu werden.
- Vorhandene Designs werden über die Weltposition jeder Rasterzelle
  übertragen, ausschließlich zwischen derselben Tribüne und demselben Rang.
  Überlappende Grundrisse von Unter-/Oberrang dürfen keine Farben austauschen.
  Palette und Blickrichtung bleiben erhalten. Unbedeckte Zellen sind
  Grundfarbe; das komplette ursprüngliche Design bleibt zusätzlich im Backup.
- Keine Entwurfszeile vorhanden: es wird keine künstliche Manager-Entwurfszeile
  erzeugt. Die vorhandene Standarddarstellung bleibt der Laufzeit-Fallback.
- Ein fehlerhafter Entwurf oder vollständig verschwindende verwendete
  Nicht-Grundfarbe bricht die Übernahme ab.
- Individuell veränderte/ausgebaute Rohgeometrie oder ein anderer Frame
  werden **nicht** mit der Basisgeometrie überschrieben. Das Kommando
  bricht vor jedem Schreiben ab und verlangt einen individuellen Abgleich.
- Geometrie, wirtschaftlicher Stadiondatensatz und Entwurf werden unter
  Sperren gelesen; Schreiben erfolgt in einer gemeinsamen Transaktion.
  Auch der normale Entwurfsspeicherpfad serialisiert gegen den Wechsel.

## Reproduktion und Einbau

Die kleine eingecheckte Ressource enthält sowohl die ursprünglichen
33 Hüllen als auch die 56 Plansektoren und ihre Herkunft. Der produktive
Übernahmebefehl benötigt weder Unity-Rohdateien noch Netzabruf.

```sh
# Bei vorhandenen, gehashten Studienquellen Ressource reproduzieren:
python -m scripts.build_koln_official_blocks

# Nur prüfen, keinerlei Datenbank- oder Backup-Schreibzugriff:
python manage.py align_koln_official_blocks

# Erst nach erfolgreicher Prüfung installieren:
python manage.py align_koln_official_blocks --apply
```

Vor dem ersten Schreiben entsteht eine exklusiv neu angelegte JSON-Sicherung
unter `generated-artifacts/koln-blocks/backups/`, mit vollständigen
Geometrie-, Stadion- und Entwurfsdatensätzen einschließlich Metadaten.
Ein zweiter Aufruf ist ein No-op. Bei einem Fehler wird die
Datenbanktransaktion zurückgerollt, die Sicherung bleibt erhalten.
Die Einrichtung nach einem Merge ruft denselben idempotenten Befehl mit
`--if-present --apply` auf; ohne Köln-Geometrie wird nichts angelegt.
Das ist kein Produktions-Deployment.

## Verifikation

```sh
python manage.py test stadium_editor.test_koln_blocks --keepdb
python manage.py check
node --check stadium_editor/static/stadium_editor/editor.js
```

Abgesichert: vollständige Nummernmenge und Quellpunktbilanz, Richtung und
Gästetrennung, asymmetrische Rasterübertragung, überlappende Ränge,
Dry-Run/Idempotenz, alle zwölf unveränderten Kapazitäts-Buckets, vollständiges
Backup, Transaktions-Rollback, Ablehnung individueller Ausbaugeometrie,
Entwurfsübernahme und realer API-Speicherzyklus einschließlich Alt-Tab-Schutz.

Die zusätzliche vorhandene Suite `stadium_editor.tests` hat sechs Fehlschläge
und einen Fehler bereits im unveränderten Ausgangscode. Ein separater
Kontrolllauf auf `HEAD` reproduzierte dieselben sieben Befunde; sie werden
nicht als Folgen des Köln-Abgleichs ausgegeben. Kontrollprotokoll:
`generated-artifacts/koln-blocks/baseline-tests.log`.
