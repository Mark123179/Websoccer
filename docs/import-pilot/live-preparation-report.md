# Live-Umstellung: Vorbereitung und Aussagegrenzen

Stand: 07.10.2026. Keine Umstellung ausgeführt.

## Lieferung

- [Manuelle Elf-Schritte-Anleitung](live-umstellung-anleitung.md): aktueller Abnahmestand, Migrationen im Altmodus, private Live-Sicherung und echte Wiederherstellungsprüfung durch Mark, separate Reset-Freigabe, Paket-/Bildschalter, ausgehende Proxys und Zieladress-Overrides, BVB-v3 zuerst, danach Nachfüllen.
- [Lokale konkrete Tabellenliste](reset-preview-local.json): 161 Tabellen, davon 139 zur späteren Leerung, 20 vollständig erhalten, Managerprofile mit N17-Neustartwerten und Länderkoeffizienten mit Saison-0-Regel. Keine Inhalts-Fingerprints, Kontowerte oder Zugangsdaten im öffentlichen JSON.
- Lesendes Kommando `preview_club_reset`: PostgreSQL-Read-only-Snapshot, alle tatsächlichen Tabellen einschließlich Nebenapps und leerer Tabellen, Prüfung tatsächlicher Profilspalten und geschützter FK-Beziehungen. Pilot und eingeschalteter Paketmodus werden abgelehnt. Unklassifizierte Daten blockieren den SQL-Entwurf.
- `--sql`: ausschließlich nicht ausgeführter Text, keine Schreiboption. Vorher-Fingerprint-Guards, Tabellenlocks, Kind-vor-Eltern-Löschreihenfolge soweit ohne Zyklus möglich, vollständige Transaktion, Schutzdaten-/Leerheitsprüfungen. Keine deaktivierten Constraints/Trigger, kein CASCADE, keine Sequenz-Rücksetzung.
- Isolierte private Wiederherstellungsprüfung durch Mark mit `--restore-check-name import_restore_check_<Kennung>`: nur lesend; weder Pilot noch vorhandene Standarddatenbank als Prüfkopie erlauben; dort keine SQL-Ausgabe.

**Diese Zahlen und Schemaprüfungen gelten nur für den konfigurierten lokalen Altbestand.** Hetzner-Konfiguration, Daten, Migrationsstand, Dateien und Restore wurden nicht geprüft. SQL-Bereitschaft ist keine Ausführungsfreigabe und kein Nachweis eines tatsächlich getesteten Resets.

## Schutz- und Szenenplan

Bestehende Konten, Passwortdaten, Rollen und Rechtezuordnungen bleiben in derselben Datenbank unverändert, ebenso ihr ContentType-/Permission-ID-Bezug und der technische Migrationsstand. Keine Pilot-Kopie oder Rechte-Neuzuordnung in den Live-Reset mischen. Persönliche Profilfelder bleiben; XP, Titel-/Saisonstände, Login-/Inaktivitätszähler und alter Vereinsbezug werden nach der bestätigten Feldliste zurückgesetzt. Keine Coin-Neuanlage.

Referee-/Sponsor-Kataloge und alle elf bestätigten Parameter-/Regeltabellen werden geschützt, Länderkoeffizienten nur Saison 0. Die Anleitung nennt die komplette Profilfeldentscheidung einschließlich level=1/xp=0/xp_max=800.

Dortmund-Geometrie und Design hängen an der alten Stadion-ID. Private Vollsicherung der DB plus aller tatsächlichen Asset-/Medienquellen und separater identitätsgebundener Szenenexport sind deshalb vor Reset vorgeschrieben. Nach Erstimport keine alte PK blind zurückladen, keine alten Budgets/Ausbau-/Spielstände aus dem Dump als Paket importieren. Globale Umfeldkonfiguration ist geschützt; weitere tatsächlich verwendete clubgebundene Szenendaten zusätzlich sichern. Wiederzuordnung und visueller Abgleich durch Mark, nicht hier ausgeführt.

## Nachweise

- Drei gezielte Tests zunächst erfolgreich; im Test Datenbankabfragen aufgezeichnet: keine DELETE/UPDATE/INSERT/TRUNCATE/DROP-Anweisung der Vorschau, Profil-XP und Club bleiben unverändert. SQL-Erzeugung benötigt keine zusätzliche DB-Abfrage. Pilot-/Modusabweichungen, ungeeignete Prüfdatenbanknamen, fehlende Schreiboption und blockierter SQL-Entwurf abgedeckt.
- Aktueller Gesamtnachweis: `python manage.py test game.tests --verbosity=0 --noinput`, **1699 Tests in 385,489 Sekunden, OK, TEST_EXIT_CODE=0**. Vollständiges Protokoll: `live-preparation-full-tests.log`. Dieser frische Lauf enthält auch alle drei neuen Tests mit korrigierter Isolation.
- Der erste Gesamtlauf verwendete eine durch das Aufräumen der neuen TransactionTestCases geleerte `--keepdb`-Testdatenbank und war rot. Protokoll: `live-preparation-depleted-testdb.log`. Ursache waren fehlende migrationsgeseedete Kataloge, keine behaupteten vorbestehenden Fachfehler.
- Testisolation korrigiert: vorhandene Projektkonvention zur Wiederherstellung des serialisierten Seed-Stands nach jeder TransactionTestCase verwendet. Wiederholung auf frischer, eindeutig getrennter `test_`-Datenbank; kein Nachseeden von Entwicklungs-/Pilot-/Live-Daten.
- App neu gestartet, Django-Systemprüfung ohne Fehler; anonyme Start-/Anmeldeseite visuell geprüft. Der bereits bekannte unabhängige Static-Finder-Fehler für einzelne `/static/assets/`-Pfade besteht weiterhin. Keine pauschale Behauptung fehlerfreier Bilder.

## Nicht ausgeführt / separate weitere Arbeit

Kein tatsächlicher Reset oder Probe-Reset mit dem Entwurf, keine Pilot-Sicherung, kein Paketimport, kein v3-Pilot-Upload, kein Push/Pull, kein Hetznerzugriff, keine tatsächliche Umschaltung, keine private Live-Sicherung/Wiederherstellung.

Separat vorgeschlagen: SQL-Entwurf ausschließlich mit künstlichen Daten auf eindeutig isolierter Testdatenbank prüfen; Vollständigkeit der vorgesehenen Bundesliga-Teilnehmer technisch vor dem Ligastart erzwingen. Der bestehende Guard prüft nur offene blocking-Einträge. Bis zur technischen Ergänzung bleibt die 18-Vereine-Bedingung eine ausdrücklich dokumentierte Betreiberprüfung; automatische Simulationsschreiber bleiben pausiert.

Keine Änderungen an Stärkeformeln, Vereinswert-Regel, Match-Engine, Bibliotheken, Anzeigennamen, Bildern oder Nachpflege. Der Pilot bleibt v2; Original-BVB-v3 bleibt das erste Live-Paket. Zusätzliche Bildinfos getrennt von den 128 Paket-Arbeitslisteneinträgen zählen.
