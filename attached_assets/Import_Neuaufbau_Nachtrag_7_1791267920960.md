# Import-Neuaufbau: Nachtrag 7 zur Übergabe

Stand: 06.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 6 und zu Replits T1-Bericht vom 06.10.2026

Dieser Nachtrag nimmt T1 mit Korrekturen ab und gibt T2 unter einer Bedingung frei. Er hat bei Widersprüchen Vorrang vor Teil A, Teil B, Teil C und den Nachträgen 1 bis 6. Am BVB-Referenzpaket und am Paketformat ändert er nichts.

Alle Entscheidungen hat Mark am 06.10.2026 einzeln getroffen.

## Befund, der die Korrektur auslöst

T1 schaltet das neue Schema über `IMPORT_REBUILD_SCHEMA`: Im Pilot kennt der Code die neuen Spalten, im alten Bestand nicht. Die Migration `0187_import_rebuild_n28_n31` liegt aber als normale Migration in `game/migrations/`. Zwei Stellen führen `migrate` aus, ohne den Schalter zu kennen:

- `scripts/post-merge.sh` bei jedem Zusammenführen einer Replit-Aufgabe, auf dem Schema `public`
- `deploy.sh` auf dem Server bei jedem Deploy

Damit bekäme eine Datenbank Pflichtspalten ohne Vorgabewert, die der Code im Altmodus nicht kennt (`import_state`, `import_lock`, `selection_evidence`, `status`, `identity_kind`, `origin`, `is_loan`, `is_start_value`, `payload_hash` und weitere). Jedes Anlegen eines Vereins, Spielers, Marktwertpunkts, Transfers oder einer externen ID schlüge fehl. Außerdem hinge jede künftige Migration eines anderen Themas hinter `0187`.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N32 | **T1 ist abgenommen, mit den Korrekturen aus N33.** Die sieben Berichtspunkte sind erfüllt. Die Abweichung in `public.game_managerprofile` ist als `last_seen` der laufenden Anwendung erklärt und unkritisch |
| N33 | **Der Schema-Schalter entfällt. Der Code kennt die neuen Spalten und Tabellen überall, umschaltbar bleibt nur das Verhalten.** Die Migration läuft überall dort, wo `migrate` läuft, auch auf dem alten Replit-Stand. Das ändert N14 in einem Punkt: Der alte Stand bekommt zusätzliche, leere Spalten und zwei leere Tabellen. Seine Daten bleiben unverändert |
| N34 | **Hetzner: keine Sperre in `deploy.sh`.** Zwischen Replit und dem Server gibt es keine automatische Verbindung. Ein Deploy entsteht nur, wenn Mark auf GitHub pusht und auf dem Server pullt. Mark hat dazu keine Bedenken |
| N35 | **`real_life_club` wird sofort stillgelegt.** Der neue Import füllt die Spalte nicht. Die vier Leser werden schon in T2 auf den Stammverein umgestellt. Replits Vorschlag (vorerst Spiegel) ist nicht gewählt |
| N36 | **Prüfpool.** Fehlt ein Spieler bei einem erneuten Upload vor Ligastart im Paket, verlässt er den Verein, bleibt in der Datenbank und kommt in den Prüfpool. Dort ist er nicht scoutbar. Erst wenn er wieder einem Verein zugeordnet ist, gelten für ihn die normalen Regeln |
| N37 | **Ablauf:** Replit behebt die Punkte aus N33, führt T1 zusammen und lässt die bestehenden Tests im Altmodus laufen. Sind sie grün, geht es ohne Halt in T2. Sind sie rot, Halt mit Bericht. Nächster regulärer Halt am Ende von T2 |

## Zu N33: Was zu korrigieren ist

1. **Schema immer, Verhalten per Schalter.** `game/import_schema.py` wird ohne Bedingung geladen. Ein einziger Verhaltensschalter (Name nach Replits Wahl) ist im Pilot an und sonst aus. Hinter ihm liegt alles, was sich gegenüber heute anders verhält: der neue Paketweg, das Speichern von Marktwert- und Quellstand-Snapshots ohne Kürzung und ohne Nebenwirkung, die Prüfung der Einzelsperre, das Lesen von `import_state` und `squad_team`. Im Altmodus verhält sich das Spiel exakt wie vor T1.
2. **`0187` nicht nachträglich ändern.** Sie ist im Pilot-Schema bereits eingespielt. Korrekturen kommen als Folge-Migration.
3. **Vorgaben für bestehende Zeilen** in der Folge-Migration: `import_lock` = false für alle vorhandenen Spieler; `import_state` = `spielbar` für vorhandene Vereine, `nicht_spielbar` nur für bisherige Platzhalter (`is_import_placeholder`). Vorgabe der Spalte `import_lock` für neue Zeilen: false. Der Import setzt die Sperre ausdrücklich, wenn eine Einzelsperre vorliegt.
4. **Leih-Pool-Abfrage.** `is_in_loan_pool` trifft derzeit auch Spieler, die bei einem importierten Leihverein spielen. Im Leih-Pool ist nach E69 und N29 nur, wer verliehen ist und keinen Spielverein hat, weil der Leihverein nicht importiert ist.
5. **Keine Drift.** `makemigrations --check` meldet in beiden Modi keine Abweichung. Die bestehenden Tests (`python manage.py test game.tests`) laufen im Altmodus grün.
6. **Feldliste nachziehen.** In den Tabellenzeilen stehen `position`, `primary_position` und `source_positions` noch mit „überschreiben"; nach N30 sind sie unberührt. Reste zu `nur_verweis` und zu Echtwelt-Leihdaten im Fließtext entfernen.
7. **Schalter mit Ablaufdatum.** Der Bericht nennt jede Stelle, an der der Verhaltensschalter abgefragt wird. Mit der Übernahme wird er eingeschaltet und danach samt Altzweigen entfernt.

Die temporären Sicherungen `t1_saved_*` im Pilot-Schema dürfen entfernt werden, sobald die Korrekturen eingespielt und die Tests grün sind.

## Zu N34: Was das praktisch heißt

Ab dem Zusammenführen von T1 enthält der Hauptstand die Migrationen dieses Umbaus. Der erste Push nach GitHub mit anschließendem Pull und `deploy.sh` auf dem Server spielt sie dort ein. Solange Mark nicht deployt, bleibt Hetzner unberührt. Der erste Deploy danach ist Teil der Übernahme.

## Zu N35: Die vier Leser

- `game/views_scouting.py`: Scouting-Karte, Scouting-Suche, Transfer-Scouting (Verein, Wappen, Liga)
- `game/views.py`: Spielerprofil (Wappenquelle)
- `game/admin.py`: Spielerformular, Filter, Stärkevorschau, Datenprüfung
- Altschreiber `game/club_import/fmid_csv_service.py`, `game/club_import/import_service.py`, `game/economy/severance.py`

Im neuen Modus lesen sie den Stammverein (`owner_club`, bei nicht importiertem Stammverein TM-ID und Originalname). Im Altmodus bleibt das bisherige Verhalten. Die Spalte selbst bleibt bis zum späteren Aufräumen stehen.

## Zu N36: Der Prüfpool im Einzelnen

- Gilt nur vor Ligastart. Nach Ligastart bleibt der Kader bei einem erneuten Upload unberührt (N30).
- Die Vorschau zeigt vor der Bestätigung, welche Spieler den Verein verlassen.
- Der Spieler behält Identität, externe IDs, Quellwerte und Historie. Er hat keinen Spielverein und steht mit einem Info-Eintrag auf der Arbeitsliste.
- Der Prüfpool ist ein eigener Zustand. Er ist weder der Leih-Pool noch der Scouting-Pool.
- Wieder zugeordnet wird der Spieler auf zwei Wegen (Lesart von Claude zu Marks „sobald er wieder zugeordnet wurde"): automatisch über die TM-ID, wenn das Paket eines anderen Vereins ihn enthält, oder von Hand über die Arbeitsliste.
- Nach der Zuordnung gelten die normalen Regeln. Steht er dann bei einem nicht spielbaren Verein, gehört er zum Scouting-Pool.

## Umfang von T2

Unverändert aus Teil A, mit allen Nachträgen:

- Paket prüfen: Format, Version, Prüfsumme, Pflichtfelder, Summe der zwölf Stadionwerte, höchstens drei Haupt- und drei Nebenpositionen, dritte Stelle nur ROV, ROM, LOV, LOM
- Ein zentraler Paketweg, eine Transaktion je Paket, identischer zweiter Upload ändert nichts
- Abgleich nur über externe IDs, kein Namensabgleich
- Startwert 50.000 € für Spieler ohne TM-Marktwert (N10), Gehalt nach Marktwert
- Verweis-Vereine als TM-ID plus Name, Fremdschlüssel beim Import nachtragen (N29); Namen ohne TM-ID auf die Arbeitsliste (N11)
- Leihstand einmalig setzen (N31), Leih-Pool, Prüfpool (N36)
- Schreibmaske nach Ligastart (N30)
- Einzelsperre für Spieler mit Lücke `player_lock`, Arbeitsliste aus den Lücken des Pakets
- Stärke für alle Spieler mit Quellwerten über den bestehenden Berechnungsweg
- Umstellung der Leser von `real_life_club` (N35)

Der Creator-Upload mit Vorschau ist T3. In T2 wird das BVB-Paket im Pilot über den Paketweg eingelesen.

## Bericht am Ende von T2

1. Ergebnis der Korrekturen aus N33, Liste der Stellen mit Verhaltensschalter, Testergebnis im Altmodus
2. BVB im Pilot eingelesen: Anzahl Spieler, Personen, Marktwertpunkte (davon Startwerte), Transfers, Rekorde, Titel, Einträge der Arbeitsliste nach Schwere
3. Kader: 1. Mannschaft, U21, Leih-Pool, Geliehene, jeweils mit Namen der Leihfälle
4. Zweiter Upload desselben Pakets: Nachweis, dass keine Zeile entsteht oder sich ändert
5. Stärke: für wie viele Spieler berechnet, welche gesperrt, Stichprobe von fünf Spielern mit Quellwerten und Ergebnis
6. Verweis-Vereine: Anzahl verschiedener TM-IDs, Anzahl Namen ohne TM-ID, Nachweis, dass keine zusätzliche Zeile in `game_club` entstanden ist
7. Bestätigung, dass der alte Replit-Stand weiter läuft und seine Daten unverändert sind

## Freigabe

Freigegeben: die Korrekturen aus N33, das Zusammenführen von T1 und, bei grünen Tests im Altmodus, T2. Nicht freigegeben: Creator-Upload und Vorschau (T3), Anzeige (T4), Reset-Befehl (T5), Sicherung der Dortmund-Szene.
