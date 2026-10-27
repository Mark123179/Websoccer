# LaLiga – Workspace-Import vom 27.10.2026

## Ergebnis

Der vollständige, additive Import wurde gespeichert:

| Inhalt | Gespeicherter Umfang |
| --- | ---: |
| Liga | LaLiga, Spanien, Ebene 1, nicht spielbar |
| Vereine / Stadien / Importpakete | jeweils 20 |
| Unterschiedliche Spieleridentitäten | 930 |
| Spielereinträge in den Paketen | 947 |
| Beidseitig dokumentierte Leihen innerhalb der Lieferung | 17 |
| Vereinsrekorde | 480 |
| Historische Titel (`ClubTrophyEntry`, echte Geschichte) | 660 |
| Unterschiedliche gesperrte Spieler | 19 |

Es wurde keine Saison für LaLiga angelegt. Produktion wurde nicht verändert.
Die 216 Personenangaben der Pakete wurden über die bestehende historische
Identitätsverknüpfung verarbeitet; sie sind keine Zusage von 216 neuen Personen.

## Freigegebene Ausnahmen

Die FM-Zuordnungen folgender acht unterschiedlicher Spieler bleiben in Quarantäne:

- Adrián Pérez bei Athletic Bilbao und Adrián Pérez beim FC Sevilla.
- Toni Fernández und Joni Hernández beim FC Barcelona.
- Anxo Rodríguez und Noah Rodríguez bei Celta Vigo.
- Kayne van Oevelen beim FC Valencia.
- Álvaro García in den beiden Paketansichten Alavés/Villarreal.

Bei allen acht sind die aktive FM-ID und die aktuelle FM-Quellbewertung entfernt.
Die Spieler sind einzeln gesperrt; ihre Identitäten bleiben getrennt.
Die elf schon in den Originalpaketen enthaltenen Einzelsperren bleiben erhalten.

Für zwei Spieler wurden ausdrücklich die Hauptvereine statt widersprüchlicher
B-Team-Referenzen übernommen:

- Álvaro García: Deportivo Alavés → FC Villarreal, Nachwuchskader.
- Adrián Martín: Real Betis Sevilla → FC Getafe, Nachwuchskader.

Beide Leihen enden am 30.06.2027. Diese Ausnahmen erlauben keine allgemeine
Gleichsetzung von Hauptvereinen und B-Mannschaften.

## Nachfolgende FM-Quellenklärung

Die anschließende gezielte Nachpflege ist separat dokumentiert:
`docs/import-pilot/laliga-fm-identities-2026-10-27.md`.
Anxo und Álvaro sind nach exakter UID-/Geburtsdatumsprüfung freigegeben.
Noahs eigene ID ist korrigiert; wegen fehlenden belegten numerischen
FM-Potenzials bleibt er gesperrt. Die fünf übrigen FM-Quarantänen bleiben bestehen;
der Nutzer hat Geburtstagsausnahmen ausdrücklich abgelehnt.
Die nachstehenden Acht-Spieler-Prüfungen beschreiben den ursprünglichen Import,
nicht den späteren Nachpflege-Stand.

## Quellen und Reproduktion

Die beiden gelieferten äußeren ZIP-Dateien sind bytegleich. Das Original unter
`attached_assets/laliga_vereinspakete_2026-10-27_1793090727720.zip` blieb unverändert.
Seine SHA-256 lautet:

`ac87857f81e8929450b21a71973b664e1abbd61b8b435de98c491883d52c27eb`

Die ausführlichere Entscheidungsdatei ist
`attached_assets/laliga_entscheidungen_zur_durchsprache_1793090727720.md`.

`scripts/import_laliga_packages.py` erzeugt getrennte Importfassungen einschließlich
Quellenabweichungen und FM-Sperren. Der bestehende abgesicherte Batch-Importer
übernimmt diese innerhalb einer Transaktion.

- Probelauf: `python -m scripts.import_laliga_packages`
- Freigegebene Speicherung: `python -m scripts.import_laliga_packages --apply`
- Lokale Belege: `generated-artifacts/laliga-2026-10-27/`
- Maschinenberichte: `dry-run-report.json`, `applied-report.json`
- Ursprüngliche FM-Angaben und Leihreferenzen: `provenance.json`

Die generierten Dateien sind bewusst von Git und Deployment ausgeschlossen.
Die unveränderte Lieferung und dieses Dokument bleiben die dauerhaften Belege.
Ein erneuter Import der unbearbeiteten Originalpakete darf die Sperren oder die
freigegebenen Vereinszuordnungen nicht stillschweigend überschreiben.

## Verifikation

Der vollständige Probelauf und der anschließende echte Import bestätigten:

- Geschützte Bestandsvereine, Stadien, Manager, Saison- und Finanzdaten unverändert.
- Nicht betroffene Spieler unverändert.
- Exakte Wiederholung aller 20 Pakete verändert keine Spiel- oder Importdaten.
- Vollständige Vereinszugehörigkeit zur nicht spielbaren LaLiga.
- Alle acht zusätzlichen FM-Quarantänen wirksam, ohne aktuelle FM-Bewertungen.
- Beide freigegebenen Nachwuchsleihen korrekt gespeichert.

Direkte Datenbankabfragen nach dem Commit bestätigten zusätzlich 20 Vereine,
20 Stadien, 20 Importpakete, 480 Rekorde, 660 historische Titel, 19 unterschiedliche
gesperrte Spieler und keine LaLiga-Saison.

Die zwei neuen Paketvorbereitungstests bestanden. In einem ergänzenden Lauf
bestanden 47 von 49 Tests. Zwei unveränderte historische Identitätstests erwarten
global genau einen Spieler und erhalten sechs; beide Fehler wurden auch isoliert,
ohne die neuen Tests, reproduziert. Die transaktionalen Importprüfungen und die
gespeicherten Datenchecks waren davon unabhängig erfolgreich.
