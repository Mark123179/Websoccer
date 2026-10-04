# Navigation: Golden- und Symbolmodus

## Vertrag

- Ausgeklappt bleibt der Standard, Sidebar: 232 logische Pixel.
- Nur der explizite Desktop-Symbolmodus reduziert sie auf 80 Pixel.
- Bei 1440×900 gewinnt der Inhalt 116,178 sichtbare Pixel; die Stage-Skalierung
  bleibt `matrix(0.764331, 0, 0, 0.764331, 0, 0)`.
- Wide-Shell-Zustand, Stage-Basis und vertikale Tracks werden nicht geändert.
- Bis einschließlich 760 Viewport-Pixel gelten die bisherigen mobilen Regeln.
- Die optionale Browserpräferenz wird vor dem ersten Layout geladen. Ungültiger
  oder verweigerter Speicher führt zur ausgeklappten Standardansicht; der
  Schalter funktioniert weiterhin ohne Speicherung.
- Spielvorschau-Anordnungen und deren Revision bleiben unberührt.

## Prüfung am 04.10.2026

Die authentifizierten Seiten wurden mit dem Django-Testclient exportiert.
Eine umschließende Transaktion wurde zurückgerollt, einschließlich
Session-/eventueller GET-Nebenwirkungen. Im Browser wurden nur die
Dokumentanfragen durch diese echten HTML-Antworten ersetzt; Styles, Skripte
und Bilder kamen vom laufenden Entwicklungsserver.

Vorher-Aufnahmen erfolgten vor der Shell-Änderung. Die ausgeklappte Nachher-
Geometrie sowie die Rückkehr nach einem vollständigen Umschaltzyklus sind
exakt gleich:

| Seite | Stage, Sidebar, Inhalt und Header | Referenzkacheln |
| --- | --- | --- |
| Übersicht | identisch | identisch |
| Taktik | identisch | Template-Grid identisch |
| Spielvorschau | identisch | alle drei Panels identisch |
| Vereinsdetails | identisch | visuell zusätzlich geprüft |
| Spielerdetails | identisch | visuell zusätzlich geprüft |
| Vereinsdatenbank / breite Tabelle | identisch | visuell zusätzlich geprüft |

Im Symbolmodus:

- Inhaltsbreite auf allen sechs Seiten um den erwarteten Wert erweitert.
- Keine Änderung von Stage-Skalierung, grundlegender Schriftgröße oder
  Headerhöhe; Übersichtskacheln und Vorschau-Panels behalten ihre Y-Positionen
  und Höhen.
- Keine neue horizontale Scrollbreite. Bereits vorhandener vertikaler
  Seitenüberlauf ist kein neuer Shell-Fehler und bleibt ausgeklappt gleich.
- Eine repräsentative gespeicherte Vorschau-Anordnung mit individuell
  verschobenem Wettbewerbselement wurde geladen, umgeschaltet und neu geladen.
  Die gespeicherte Zeichenfolge blieb exakt unverändert, die Panelhöhen gleich.
- Enter am Schalter, Reload-Persistenz, Hover-/Fokusbezeichnungen sowie Öffnen
  und Fokussieren der bestehenden Suche bestanden.
- 1920×1080, 2560×1440 und 390×844 geprüft; mobile Geometrie bleibt unabhängig
  vom gespeicherten Desktop-Zustand identisch.
- Abmeldung bleibt ein CSRF-geschütztes POST-Formular. Admin-/Creator-Links
  bleiben rollenabhängig. Diese Aktionen wurden nicht ausgeführt.

## Automatische Checks

```sh
node scripts/test_navigation_shell.cjs
python manage.py test game.tests.test_navigation_shell game.tests.test_match_preview_layout --verbosity=1 --keepdb
node scripts/test_match_preview_layout_revision.cjs
```

Alle drei Checks bestanden; der Django-Teillauf umfasst 23 Tests.
Die JavaScript-Tests prüfen insbesondere Initialisierung vor DOMContentLoaded,
ungültigen/verweigerten Speicher, Umschalten, Suchfokus und den mobilen Zustand.

Reproduzierbare Browsermessung für eine künftige Änderung:

```sh
# Vor der Änderung, bei laufendem Entwicklungsserver:
python scripts/capture_navigation_pages.py /tmp/navigation-before
node scripts/check_navigation_geometry.cjs baseline /tmp/navigation-before

# Nach der Änderung:
python scripts/capture_navigation_pages.py /tmp/navigation-after
node scripts/check_navigation_geometry.cjs verify /tmp/navigation-after
```

Erfordert die vorhandene `playwright-core`-Installation, Chromium und einen
bestehenden Admin mit Verein. Exportierte HTML-Dateien enthalten Spieldaten;
nicht ins Repository übernehmen. Die Browsermessung liest den Entwicklungs-
Host aus `REPLIT_DEV_DOMAIN`.

## Gesamtsuite und Simulationsregression

`python manage.py test game.tests --verbosity=0 --keepdb`:

- Mit Änderung: 1537 Tests, 9 Fehlschläge, 485 Fehler.
- Unveränderter Ausgangscode, separat aus Git exportiert, gleiche Laufzeit-
  Umgebung und derselbe `--keepdb`-Aufruf: 1533 Tests, 9 Fehlschläge, 486 Fehler.
- Alle 494 fehlerhaften Testnamen aus dem Änderungslauf kommen auch im
  Ausgangslauf vor; keine nur im Änderungslauf fehlerhaften Testnamen.
- Der zusätzliche Baseline-Fehler entstand ausschließlich durch ein im
  Export zunächst fehlendes `reports/live-ticker-pruefbelege.zip`.
  Nach Bereitstellung derselben Referenzdatei bestand der betroffene
  Baseline-Einzeltest.
- Insbesondere viele Ökonomie-Tests scheitern an fehlenden Testparametern,
  beispielsweise `KADER_MAX_BASIS`. Diese unabhängigen Probleme werden mit
  dieser reinen Shell-Änderung nicht behoben. Die Gesamtsuite ist nicht grün.

`bash scripts/run_regression_v3.sh --seasons 20` bestand mit dem bestehenden
Seed-Satz `1,7,21,42,99,2026`. Alle acht Kennzahlen lagen im Vergleich zum
vorherigen Lauf innerhalb des 5%-Korridors. Im neuen Multi-Seed-Lauf warnen
Remisquote (8,3%) und Verletzungen (5,2%) wegen Streuung zwischen den Seeds.
Das ist ein Verteilungsvergleich, kein Nachweis identischer Simulationsergebnisse.

Der Anwendungsworkflow wurde nach der Änderung neu gestartet und meldete
keine Systemcheck-/Startfehler. Keine Veröffentlichung, Datenmigration oder
Änderung an Simulation beziehungsweise Spielökonomie.