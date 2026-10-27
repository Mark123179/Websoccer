# Samba Diop: Identitätsklärung und verbleibende Übernahme

Stand: 23.10.2026. Ausschließlich Workspace; keine Produktion.

## Ergebnis

| Spieler | Belastbarer Befund | Konsequenz |
| --- | --- | --- |
| Brest, TM **1437971**, **27.05.2007** | Samba **Hane** Diop, offensiver Flügelspieler. FMI **2000381104 gehört nicht zu ihm**. Keine belastbar belegte andere FMI-ID gefunden. | FM-Quarantäne und Einzelsperre beibehalten. Keine strittigen FM-Werte übernehmen. |
| Lorient, TM **1273019**, **06.01.2006** | FM26-ID **2000381104** ist durch vollständiges Geburtsdatum und Verein eindeutig zugeordnet. | Fachlich für die gezielte Übernahme des originalen FM26.2.0-Blocks freigegeben. Im aktuellen Datenbestand **noch nicht angewendet**, siehe unten. |

Keine Zusammenführung, kein Namens- oder Altersmatching. Ein ungeklärter
Brest-FM-Eintrag ist kein Nachweis für „nicht vorhanden“.

## Identitätsbelege

1. [Sortitoutsi, FM26, eindeutige ID 2000381104](https://sortitoutsi.net/football-manager-2026/person/2000381104/samba-diop):
   `ID 2000381104`, `DOB 2006-01-06`, `Contracted Club FC Lorient`,
   Nationalität Frankreich, Position DM. Die FAQ bestätigt ausdrücklich
   „He was born on 6th January 2006.“ Relevante Felder dauerhaft in
   [samba-diop-fm26-source.md](samba-diop-fm26-source.md) festgehalten.
2. [TM 1273019](https://www.transfermarkt.com/samba-diop/profil/spieler/1273019):
   06.01.2006, Montreuil-sous-Bois, FC Lorient B, Frankreich/Senegal,
   zentrales Mittelfeld/Innenverteidiger, 1,89 m. Abruf bestätigt die
   vollständige Identität unabhängig vom FM-Spielstartalter.
3. [TM 1437971](https://www.transfermarkt.com/samba-diop/profil/spieler/1437971):
   voller Name Samba Hane Diop, 27.05.2007, Stade Brest 29 B,
   Senegal, Linksaußen, 1,70 m.
4. [Offizielle Brest-Mitteilung vom 17.07.2026](https://www.sb29.bzh/17-07-26-premier-contrat-pro-pour-samba-diop.php):
   nennt ausdrücklich **Samba Hane Diop**, Senegal-U17, offensives Mittelfeld/
   linke Seite, vorher Voltigeurs de Châteaubriant und die Verbindung zur
   senegalesischen Akademie. Bestätigt die getrennte Laufbahn, enthält aber
   **keine FM-ID und kein vollständiges Geburtsdatum**.

Die ähnliche Höhe/Position im Lorient-FM-Datensatz stützt den Befund nur;
sie ersetzt nicht den entscheidenden ID-Geburtsdatum-Vereins-Beleg.
Die abweichenden 187 cm (FM) und 189 cm (TM) werden nicht „korrigiert“.

## Originalpakete und portable Übergabe

Die verschachtelten Originalarchive wurden direkt gelesen, nicht die ignorierten
geprüften Importfassungen. Originaldatei:
`attached_assets/ligue1_vereinspakete_2026-10-23_1792761279706.zip`.

- `brs_vereinspaket_2026-10-23.zip/data.json`:
  SHA-256 `f99b08277ee272773b1d55b0d44918e91c84f5d23b92e034f60f190d54f5be88`.
- `fcl_vereinspaket_2026-10-23.zip/data.json`:
  SHA-256 `4a25ce13da8e6ff5eeb6bb7e255c76d0443f18d98cff8fce635da365d4202193`.

Beide Originalzeilen liefern **denselben** FM-Block (38/60, Version 26.2.0,
Club Lorient, DM/MC, 187 cm, kein Geburtsdatum) und `match: name_age`.
Damit ist die fehlerhafte Brest-Zuordnung nachvollziehbar. Ein Alter von 19
im FM26-Startdatensatz darf nicht mit dem Alter am Importtag verglichen werden.

[samba-diop-resolution.json](samba-diop-resolution.json) enthält beide
Entscheidungen und den **vollständigen, unveränderten originalen Lorient-FM-Block**.
Damit hängt die Übergabe nicht von ignorierten Hilfsdateien oder der Verfügbarkeit
der Upload-ZIP im nächsten Fork ab. Der Block enthält weiterhin `date_of_birth:
null`: Der externe Identitätsbeleg wird nicht als angeblicher FMInside-Rohwert
ausgegeben.

## Tatsächlich geprüfter Datenbestand: Übernahme blockiert

Die ausschließlich lesende Prüfung ergab im aktuellen Workspace:

- Standardschema `public`: **0** Spieler mit TM 1437971/1273019, **0** Vereine
  mit TM 3911/1158, **0** ImportIssue zu `tm:1437971`/`tm:1273019`.
- In **keinem** vorhandenen `SourceImportRun.package_data` des Standardschemas
  findet sich eine dieser beiden Spielerzeilen.
- Separates Schema `import_pilot`: ebenfalls **0** Zielspieler und
  **0** zugehörige ImportIssue.

Es wurde deshalb **nichts in die Datenbank geschrieben**. Keine Spieler oder
Vereine neu angelegt, keine vollständigen Vereinspakete erneut importiert,
keine Sperren aufgehoben. CMTracker, Stärken, Spielstände und fremde Spieler
sind unverändert. Eine erfolgreiche Datenbankübernahme oder vorhandene
Brest-Sperrzeile kann in diesem Fork nicht behauptet werden.

## Eng begrenzter nächster Anwendungsschritt

Erst wenn der zugehörige Ligue-1-Importbestand im Workspace verfügbar ist:

1. Beide Personen ausschließlich über TM-ID **und** vollständiges Geburtsdatum
   identifizieren; Vereinszuordnung prüfen. Bei Abweichungen abbrechen.
2. Beim Lorient-Eintrag `ImportIssue.external_reference.original_run_id`
   zum unveränderten `SourceImportRun.package_data` verfolgen. Den dortigen
   FM-Block mit dem hier gesicherten Original vergleichen. Keine bereinigte
   Hilfsfassung zur vermeintlichen Originalquelle erklären.
3. Nur für Lorient die FM-ID 2000381104 und den belegten FM26.2.0-Block
   projizieren und den ID-Geburtsdatum-Vereins-Beleg getrennt in der
   Zuordnungsevidenz dokumentieren. FM-Quelle/Snapshot nachvollziehbar halten.
   Vorher sicherstellen, dass die ID keinem fremden Spieler zugeordnet ist.
4. CMTracker-Zeilen/Snapshots/Status unverändert lassen. Insbesondere **nicht**
   unverändert `project_ratings()` aufrufen: Diese Funktion bearbeitet FM
   **und** CMTracker, und `patch()`/`apply_package()` wäre für diese Korrektur
   zu breit. Bei der Stärkeneuberechnung vorhandene Frische und Form erhalten,
   nicht die Initialisierungsdefaults von `project_ratings()` übernehmen.
5. Nur die geklärte Lorient-FM-Identitätslücke schließen. Andere offene Gründe
   erhalten und die datenabhängige Einzelsperre über `issue_lifecycle.py`
   neu beurteilen. Keine pauschale Freigabe aller Einträge des Spielers.
6. Brest bleibt ohne diese FM-ID und ohne den strittigen FM-Ratingblock gesperrt.
   Seine CMTracker-ID **87526** und deren Werte bleiben unverändert.
   Für Brest fehlt weiterhin ein **eigener, direkt mit dem Geburtsdatum
   27.05.2007 verknüpfter FM-Identitätsbeleg**. Eine erfolglose Websuche allein
   rechtfertigt keinen Status „nicht vorhanden“.
7. Vorher/nachher unveränderte CMTracker- und fremde Spielerzustände sowie
   unveränderte Originalarchive/Originalläufe nachweisen.

Eine erneute unbereinigte Paketlieferung ist für Brest weiterhin keine
fachliche Freigabe. Diese Recherche ändert keine allgemeinen Importregeln.

## Recherchegrenzen

Die direkte FMInside-Abfrage (versionslos und ursprünglicher Versionspfad)
lieferte beim Textabruf keinen Inhalt; ein direkter HTTP-Abruf des versionslosen
Links endete mit **403/Cloudflare**. Deshalb stammen die hier freigegebenen
Attribute ausschließlich aus dem gelieferten Original, nicht aus einem
behaupteten aktuellen FMInside-Scrape.

Gesucht wurden die exakte FM-ID, Samba Diop + Lorient/Brest, Samba Hane Diop,
Geburtsdatum und FM26/Football Manager sowie seitenbezogen FMInside und
Sortitoutsi. Die Suchergebnisse belegten keine eigene Brest-FM-ID.
Offside Scores zeigte für einen gleichnamigen Lorient-Spieler ein abweichendes
Datum (21.10.2003); dies wurde ausdrücklich **nicht** zum Matching verwendet.
Der direkt gelesene, eindeutige FM26-ID-Datensatz ist der entscheidende Nachweis.
