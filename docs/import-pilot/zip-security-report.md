# ZIP-Import: Sicherheitsfix und Nachtrag-14-Prüfung

Stand: 07.10.2026. Umsetzung der zugewiesenen Aufgabe; kein Pilot-Reimport, Reset, Push oder Hetznerzugriff. BVB-v3 bleibt unverändert das erste Live-Paket, der Pilot bleibt v2.

## 1. Fehlerantworten als Text

`game/club_import/package_views.py`: Die gemeinsame Creator-Hülle normalisiert jede zurückgegebene Fehlerantwort ab Status 400 auf `text/plain; charset=utf-8` und setzt `X-Content-Type-Options: nosniff`. Auch eigene Rollen-/Modus-403, die POST-405 und modulinterne Http404-Antworten werden so behandelt. Alle vorhandenen BadRequest-Pfade für Vorschau, Bestätigung und Nachpflege laufen über diese Grenze; keine feldbezogene HTML-Maskierung und keine Änderung gültiger Freitextwerte.

Vorher: `HttpResponseBadRequest(str(exc))` lieferte standardmäßig `text/html`.
Nachher: Dieselbe verständliche Fehlermeldung bleibt erhalten, ist aber ausschließlich Text; ein Paket-HTML-Marker wird nicht als HTML interpretiert.

Anmeldung, Rollenprüfung, CSRF-Middleware, Uploadlimit, signierter Vorschau-Token, Benutzerbindung und Vergleich von baseline/guard bleiben erhalten. Eine anonyme Anfrage wird weiter zur Anmeldung umgeleitet. Antworten der vorgeschalteten globalen CSRF-Middleware sind nicht vom Paketmodul erzeugt und wurden nicht global umgestellt.

## 2. Regressionen und Pakettext-Vorlagen

Neue Tests: `game/tests/test_package_security.py`, elf Methoden, gezielter Lauf erfolgreich (3,633 Sekunden).
Vollständiges gezieltes Protokoll: `docs/import-pilot/zip-security-targeted-tests.log`.

| Bereich | Tatsächlich geprüft |
|---|---|
| Datum | Harmloser HTML-Marker im Manifestdatum; Vorschau und Bestätigung: 400, Text/UTF-8/nosniff |
| Zahlenfeld | Marker in Stadionkapazität; beide Endpunkte: kontrolliertes 400 als Text |
| Kombinierter Fehlerfall | Datum, Kapazität, Vereinsname und Lückentext gleichzeitig; kein Importlauf, Spieler oder Arbeitslisteneintrag geschrieben |
| Zulässiger Freitext | Vereinsname und Lückentext passieren Validierung und Bestätigung unverändert; Vorschau und Arbeitsliste zeigen maskierte Zeichen statt fremder Elemente |
| Ruhmeshalle | Paket-Rekordwert, Kontext und Gegnername mit Marker; tatsächliche Seite maskiert |
| Transferhistorie | Paket-Vereinsnamen und Ablösetext mit Marker; tatsächliches Spielerprofil maskiert |
| Andere Fehler | 403, 404, 405, fehlender Upload, ungültiger Token, unvollständige Ligaangabe |
| Schutz | CSRF-freier POST wird abgelehnt; fremde Token-Benutzerbindung wird abgelehnt |

Geprüfte Vorlagen: `game/templates/game/package_preview.html`, `package_hub.html`, `management/halloffame.html`, `player_detail.html`; außerdem gemeinsames `game/templates/base.html`, `game/templatetags/package_display.py` und zugehörige Paket-Darstellungshelfer.

In den vier Fachvorlagen und ihren Pakettext-Projektionen keine `|safe`-, `mark_safe`- oder ausgeschaltete Autoescape-Stelle für Paketfreitext gefunden. Ruhmeshallenwerte bleiben normale Strings; Transfernamen und `fee_text` werden als normale Templatewerte ausgegeben. Die Skripte der Fachvorlagen betten keinen rohen Pakettext als HTML/JSON ein. Die `innerHTML`-Stellen im gemeinsamen Basistemplate gehören zum unabhängigen KI-Chat, nicht zu Paketwerten. Keine kosmetischen Template- oder CSS-Änderungen erforderlich.

## 3. N68: genau eine fachliche Validierungsänderung

Datei: `game/club_import/package_validation.py`.

Alt:

```python
if player["squad"]["team"] == "first" and player["ids"]["cmtracker"]["value"] is None:
    if f"tm:{tm}" not in locks:
        raise PackageError("Missing first-team CMTracker must have a player lock.")
```

Neu:

```python
if (player["squad"]["team"] == "first"
        and player["ids"]["cmtracker"]["value"] is None
        and player["ids"]["cmtracker"]["status"] != "nicht_vorhanden"):
    if f"tm:{tm}" not in locks:
        raise PackageError("Missing first-team CMTracker must have a player lock.")
```

Die Ausnahme betrifft nur bestätigtes CMTracker-Nichtvorhandensein. Der Test liefert den Nachweis im Identitätsblock. Keine neue Schema-/Nachweisregel erfunden; übrige Status- und FMI-Prüfungen bleiben unverändert.

| Nachtrag-14-Fall | Ergebnis |
|---|---|
| 1: Profi, FMInside vorhanden, CMTracker nicht_vorhanden samt Nachweis, keine Lücke | angenommen; keine Spielersperre; nur FM-Quellrating gespeichert; Stärke entspricht unverändertem strength_service |
| 2: Profi, CMTracker nicht_gefunden, ohne player_lock | weiterhin abgelehnt, keine Spieleranlage |
| 3: Profi ohne FMInside, mit player_lock | angenommen; Spieler einzeln gesperrt; kein blocking-Eintrag; ensure_ready lässt Liga zu |
| 4: Vorschau für Fälle 1 und 3 | null beziehungsweise genau ein player_lock |

`prospective_locks` und `lock_reasons` berücksichtigen schon vorher `nicht_gefunden`, fehlende Ratings bei vorhandenen IDs und fehlende berechnete Stärke. CMTracker-`nicht_vorhanden` allein erzeugt keine Sperre. Beide Helfer und die Stärkeformel wurden nicht verändert.

## 4. Liga-Startsperren

Die reine Paketprüfung verwirft sämtliche paketgelieferten Lücken der Schwere `blocking`, unabhängig von Art/Bezug/Feld. Test: `apply_package` bricht vor dem ersten Importlauf ab.

Die Schreibpfade im Paketimport erzeugen `blocking` an zwei Stellen: `issue_lifecycle.candidates` für Konflikte der Vereinsidentität und `package_service.sync_ids` bei Konflikten von `ClubExternalId`. Spieler-/Personen-ID-Konflikte ergeben `player_lock`; fehlende externe Vereinsreferenzen und Bilder ergeben Infos. Nachpflege kann bereits bestehende Sperren behandeln, erzeugt aber keine neue blocking-Schwere. Die Startsperre in `league_guard.ensure_ready` beachtet ausschließlich offene blocking-Einträge.

Damit kann ein angenommenes Paket bei einem **serverseitig erkannten Vereins-ID-Konflikt** einen sperrenden Eintrag veranlassen; es kann ihn nicht direkt als Paketlücke mitliefern. Dies ist ausdrücklich nicht die pauschale Aussage, ein Paket könne unter allen Bestandsbedingungen keinerlei Startsperre erzeugen. Direkte Admin-/Shell-Eingriffe außerhalb des Paketwegs können Daten natürlich ändern und sind nicht Gegenstand dieser Bestätigung.

## 5. Namen statt display_name: Fundstellen, keine Änderung

Grundlage: `Player.full_name` und `Player.__str__` verwenden Vor-/Nachnamen ohne display_name-Fallback (`game/models.py:2245–2258`). Deshalb zeigen auch indirekte `name`-Projektionen und gespeicherte Match-Snapshots diese Namen.

| Ansicht/Pfad | Konkrete Stellen |
|---|---|
| Kaderlisten, Leihen, U21 | `game/templates/game/club_profile/squad_page.html:34,50,58`; `game/views.py:2826–2854,2955,2967,3898,3935` |
| Spielerprofil | `game/templates/game/player_detail.html:8,35,38–39,202` (Titel, Bildtext, Namenszeile, Linktitel) |
| Aufstellung/Taktik | `game/tactics.py:815,849,856`; `game/views.py:6184–6207` (serialisierte Kadernamen) |
| Spielbericht/Bank/Ticker | `game/match_engine.py:271,741,3062` schreibt Vor-/Nachnamen in Berichtsdaten; `game/views.py:4499,5256–5257` ergänzt Bank/Namenslookup. Ticker verwendet die Namen aus diesen Ereignissen; historische Berichte bleiben unberührt |
| Scouting, Beobachtungsliste, Suche | `game/views_scouting.py:94,150,177,268,289,483,555,574`: Name aus full_name; Suchfilter nur Vor-/Nachname, nicht display_name |
| Transfermarkt/-verhandlung | `game/views_transfer_v2.py:192,235,283,522,787`; Treffer/Benachrichtigungen nutzen full_name |
| Liga-Spielerstatistik | `game/templates/game/liga/league_detail.html:556,584,618,646` |
| Startseite/Finanz- und Transfernachrichten | `game/templates/game/home.html:314`; `game/views.py:7119,7123,7211,7680,7706,7716` |
| Sportgericht | weitere Template-Fundstellen in `game/templates/game/management/sportgericht.html` |

Vollständiger Volltext-Fundstellenexport: `docs/import-pilot/package-name-display-inventory.csv` (Pfad, Zeile, Originalstelle). Der Export enthält konservativ auch Sortierung, URL-Slugs, interne Felder und Altpfade; nicht jede Zeile ist selbst eine sichtbare Ausgabe. Die Tabelle benennt die bestätigten Anzeige-/Suchpfade und verfolgt die indirekte Namensweitergabe. Über Anzeigeänderungen entscheidet Mark separat.

## 6. Neue Lückenbezüge: Anzeige bestätigt, Kollisionsfreiheit nicht

Testdaten enthalten alle vier U21-Positionsbezüge sowie `u21:tm:<ID>`, `u21:nr:<Nummer>` und die vier neuen Spielerfelder. Die Vorschau behält alle Art/Bezug/Feld-Kombinationen und zeigt Art/Feld/Text; die Arbeitsliste zeigt zusätzlich den Bezug. Anlage/Reconciliation bewahrt zehn eigenständige Einträge. Ohne kollidierenden externen Vereinsnamen entstehen keine falschen Vereinsreferenzen.

**Abweichung reproduziert:** Der externe Original-Vereinsname `TOR` ohne TM-ID ist ein Teilstring von `u21:TOR`. Sowohl die Vorschau-Kandidaten als auch `reference_issue` hängen dessen `external_reference` an den technischen U21-Eintrag; ein eigener `club_reference` fehlt dann. Die verlangte allgemeine Kollisionsfreiheit kann daher nicht bestätigt werden.

Der Test `test_reference_substring_collision_is_reported_not_silently_fixed` dokumentiert diesen Ist-Zustand ausdrücklich, nicht als gewünschtes Soll. Keine nicht freigegebene Zuordnungsänderung vorgenommen. Vorschlag zur getrennten Korrektur: U21-Hinweise und historische Vereinsverweise strukturell trennen; Bestands-/N47-Historie erhalten.

## 7. Weiterer bestehender Befund

Bei der Profilprüfung mit leerem Marktwertverlauf und positivem aktuellem Marktwert trat `KeyError: is_start_value` in `game/views.py:1083` auf: Der Fallback in `market_chart_points` enthält nur value/date, der folgende Code verlangt is_start_value. Außerhalb des freigegebenen Fixes, unverändert. Der erfolgreiche Escaping-Test verwendet einen gültigen realen Paket-Marktwertpunkt, nicht einen Mock des Profilrenderers.

## 8. Gesamtlauf und Betriebsgrenzen

Vollständiger aktueller Lauf: `python manage.py test game.tests --verbosity=0 --keepdb`.
Ungekürztes Protokoll: `docs/import-pilot/zip-security-full-tests.log`, einschließlich abschließendem TEST_EXIT_CODE. Nur der Abschluss dieses neuen Laufs gilt als Gesamtnachweis, nicht frühere 1685-/1682-Läufe.

**Ergebnis: 1696 Tests in 355,460 Sekunden, OK, TEST_EXIT_CODE=0.** Die protokollierten absichtlich ausgelösten Mock-Fehler anderer Regressionen sind keine fehlgeschlagenen Tests. Es wurde kein Fehler weggeschaltet und kein alter grüner Lauf als neuer Beleg verwendet.

Die Anwendung wurde nach der Codeänderung neu gestartet; Django-Systemprüfung ohne Fehler. Der nicht angemeldete Preview-Aufruf der Paketroute zeigt weiterhin die Anmeldung. Keine Authentifizierung für einen Screenshot umgangen. Im Haupt-Preview bestehen unabhängig vom Fix Fehler beim Ausliefern bestimmter `/static/assets/`-Bilder (Static-Finder liefert eine Liste statt Pfad); keine pauschale Behauptung fehlerfreier Assets. Die eigentlichen Paketansichten wurden in der isolierten Testdatenbank gerendert.

Keine Bibliotheksupdates oder Änderung von Bild-, Namens-, Stärke-, Sperr- oder Vereinswert-Regeln. Keine Rückschlüsse auf die ungeprüfte Hetzner-Konfiguration; die Proxy-/Zieladressprüfung bleibt Teil der manuellen Umstellung.
