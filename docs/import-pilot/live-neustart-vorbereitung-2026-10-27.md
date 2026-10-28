# Live-Neustart mit vollständigem Importbestand: Vorbereitung

Stand: 27.10.2026. **Nur Vorbereitung freigegeben. Kein Reset, kein Moduswechsel,
kein Live-Import ausgeführt. Der Stand ist noch nicht resetbereit.**

**Nachtrag 28.10.2026:** Der nachfolgende Bestand bleibt der historische
Workspace-Nachweis. Der aktuelle kombinierte Übergabe- und Prüfstand wird
separat in [Übernahmepaket und Paritätsnachweis](live-neustart-uebernahmepaket-2026-10-28.md)
dokumentiert. Daraus folgt weiterhin keine Reset- oder Produktionsfreigabe.

Aktueller Zusatzauftrag: mindestens den tatsächlich vorhandenen Workspace-Stand
für Live bereitstellen. Die fehlende Schweiz separat ausweisen, nicht zum
pauschalen Hindernis für die Übernahme dieses vorhandenen Stands machen.
Die [neue Server-Sicherungsprüfung](server-sicherungspruefung-2026-10-27.md)
deckt sämtliche vorhandenen Vereinsszenen ab. Die alte getrennte
Reset-/Nachfüll-Reihenfolge ist kein Ausführungsweg für die Gesamtübernahme.

## Ursache der leeren Live-Spielerprofile

Der Betreiber hat vom Live-Server folgende rein lesende Ergebnisse geliefert:
Paketmodus `False`, null Importläufe, Jobe Bellingham mit HP DM, ohne NP,
einem Marktwertpunkt und null Transfers. Der Code-Pull überträgt weder die
Workspace-Datenbank noch ihre Vereinspakete.

Der Nutzer wählte anschließend „Neustart mit Importdaten vorbereiten“.
Das ist keine Freigabe zur Ausführung des destruktiven Resets.

## Aktuell nachgewiesener Workspace-Bestand

Mit `python manage.py live_restart_inventory` rein lesend ermittelt:

| Größe | Nachweis |
| --- | ---: |
| Erfolgreich angewandte Importläufe | 99 |
| Unterschiedliche importierte Vereine | 94 |
| Zugeordnete/zugehörige Spieler | 4.624 |
| Gesperrte Spieler | 61 |
| Marktwertpunkte dieser Spieler | 53.305 |
| Transferhistorien-Einträge dieser Spieler | 28.393 |
| Vereine mit konsistenten Paketarchiv-/Quellhash-Metadaten | 94 |

| Liga | Vereine |
| --- | ---: |
| 1. Bundesliga | 18 |
| 2. Bundesliga | 18 |
| Premier League | 20 |
| Ligue 1 | 18 |
| LaLiga | 20 |

**Die Schweiz ist in dieser abgefragten Arbeitsdatenbank nicht enthalten.**
Gemergte Recherche-/Importskripte sind kein Beleg für einen ausgeführten Import.
Vor einer vollständigen Übergabe müssen die schweizerischen Lieferungen und
ihre Rekordkorrekturen eigenständig abgeglichen werden. Nicht unbemerkt auslassen
und nicht als bereits übernommen ausweisen.

Jobe als Abnahmestichprobe über **TM-ID 796297**, niemals über eine lokale PK:

- HP ZM und DM; NP OM
- 13 Marktwertpunkte; 4 Transferhistorien-Einträge

Diese Zahlen sind ein Inventar des aktuellen Workspace, **kein abschließend
freigegebener Sollstand für den vollständigen Neustart**.

## Neues rein lesendes Inventarkommando

Workspace:

```bash
python manage.py live_restart_inventory
```

Server nach Übernahme dieses Codes:

```bash
docker compose exec -T web python manage.py live_restart_inventory
```

Das Kommando besitzt keinen Schreib-, Import-, Reset- oder Ausführungsmodus.
Es gibt keine Konten, Zugangsdaten oder Rohdumps aus. Eine eigenständige
PostgreSQL-Ausführung nutzt einen wiederholbaren Read-only-Snapshot.

Der Bericht enthält pro Verein die TM-ID, Liga, Importzustand, archivierte
Quell-Prüfsumme und einen gesonderten kanonischen Hash der gespeicherten
Paketdaten. **Der kanonische Hash ist nicht die Prüfsumme der ursprünglichen
`data.json`-Bytes.** Konsistente Metadaten beweisen weder die ursprünglichen
ZIP-Bytes noch die Übernahme späterer manueller Nachpflege.

## Voraussetzungen vor jeder Reset-Freigabe

1. **Übernahmebestand vervollständigen und transportierbar sichern.**
   Alle gewünschten Ligen, aktuelle Paketstände und manuelle Korrekturen
   inventarisieren. Quarantänen, NULL-Werte und genehmigte Leih-Ausnahmen
   erhalten. Originalpakete nicht stillschweigend überschreiben.
   Der ursprüngliche LaLiga-Quarantäneimport darf bestätigte FM-Nachpflege
   nicht zurücksetzen. Auch Schweizer Rekordkorrekturen müssen mitkommen.
   Ein alter Paket-Reimport ist deshalb kein Nachweis des neuesten Stands.
2. **Transport auf einer isolierten Prüfkopie erproben.**
   Übernahme nach stabilen Quell-IDs statt Workspace-PKs; Abgleich der
   Positionsfelder, Marktwert-/Transferhistorien, IDs, Ratings, Potenziale,
   Sperren, Vereinsdaten, Rekorde und Titel. Liga-Zustand beachten:
   die zusätzlichen Ligen nicht eigenmächtig spielbar schalten oder starten.
   Ein solches vollständiges Transportpaket wurde mit dieser Vorbereitung
   noch nicht erstellt oder abgenommen.
   Für die spätere Gesamtübernahme Reset, Initialisierung und Schutzprüfung
   in einer rückrollbaren Einheit vorsehen, nicht zuerst einen leeren
   Live-Spielbestand committen.
3. **Serverseitige Sicherungen und echte Wiederherstellung nachweisen.**
   Alle Schreiber pausieren, DB-Dump, Medien, Assets, Konfiguration und
   separate Vereins-Stadionszenen privat sichern; in eine neue Prüf-DB
   wiederherstellen und Inventare vergleichen. Keine Dumps oder `.env`
   in Git/Chat/Library stellen. Alle tatsächlich vorhandenen Vereins-
   Geometrien und Sitzdesigns berücksichtigen, nicht nur Dortmund.
4. **Aktuelle Sicherheit und Testbasis prüfen.**
   Historische grüne Testzahlen aus der Anleitung vom 07.10. sind keine
   aktuelle Freigabe. Die bestehenden Test-/Audit-Workflows enthalten
   Fehlerberichte; deren Ursachen und Relevanz müssen vor einer
   Ausführungsfreigabe geprüft sein. Die sechs unten genannten gezielten
   Tests ersetzen keinen erforderlichen aktuellen Gesamtnachweis.
5. **Frische Live-Reset-Vorschau und konkrete Freigabe.**
   `preview_club_reset` bei weiterhin ausgeschaltetem Paketmodus ausführen.
   Die genaue Lösch-/Schutzliste, Sicherungs- und Wiederherstellungsbelege
   dem Betreiber vorlegen. Erst nach seiner separaten Zustimmung darf der
   Operator einen daraus erzeugten SQL-Entwurf ausführen.

**Bis alle Punkte erledigt sind: kein Reset, kein Umschalten des Paketmodus,
kein pauschaler Workspace-Dump über Live und kein Start der Simulation.**

## Was ein späterer Reset betrifft

Die Schutzliste aus `live-umstellung-anleitung.md` bleibt verbindlich:
Konten/Rechte, technische Schemahistorie, freigegebene Kataloge und persönliche
Managerfelder erhalten. Spielbestand einschließlich Spiele, Vereins-/Spieler-
Zeilen, Finanzen, Historien und clubgebundener Editorstände wird entfernt;
Manager-Spielwerte werden gemäß der expliziten Liste zurückgesetzt.
Dateien werden nicht gelöscht. Der genaue aktuelle Umfang muss aus der
Live-Vorschau kommen, nicht aus den Workspace-Zahlen dieses Berichts.

Die bestehende Anleitung erklärt private Sicherung, Wiederherstellung,
Read-only-Vorschau und Schutzliste. **Ihre alte Nachfüll-Reihenfolge ersetzt
nicht die jetzt notwendige vollständige Übergabe des aktuellen Bestands.**
Keinen Löschbefehl allein aufgrund dieses Berichts ausführen.

## Prüfung dieser Vorbereitung

```bash
python manage.py test \
  game.tests.test_live_restart_inventory \
  game.tests.test_reset_preview \
  --settings=core.package_test_settings --noinput
```

Ergebnis: sechs Tests erfolgreich auf einer neu angelegten isolierten
SQLite-Testdatenbank. Geprüft sind schreibfreies Inventar, explizite
Archiv-Metadatenprobleme, fehlender Apply-Modus und die bestehenden
Reset-Vorschau-Schutzregeln. Kein Live-Zugriff, kein Live-Restore und
keine Reset-Ausführungsprobe durch diese Tests.
