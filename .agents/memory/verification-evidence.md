---
name: Verification evidence boundaries
description: User-required controls for parity, regression, baseline tests and diagnostic counts.
---

Verifikationsbehauptungen müssen die tatsächlich identischen Startbedingungen nennen: Seed-Satz, Saisonanzahl, sämtliche verwendeten Zufallszustände und bei Tests den Zustand der Testdatenbank.

**Why:** Der Nutzer korrigierte eine Abnahme, die unterschiedliche Saisonumfänge als Vorher/Nachher-Beleg verwendete, lokale Seeds mit vollständig kontrolliertem Zufall gleichsetzte und Testfehler ohne Baseline-Lauf als vorbestehend bezeichnete.

**How to apply:** Verteilungsvergleiche nicht als Parität verkaufen. Vorbestehende Testfehler nur nach einem tatsächlichen Baseline-Lauf unter passenden Bedingungen behaupten; frische und wiederverwendete Testdatenbanken getrennt ausweisen. Fachliche Gleichheit von Laufzeitabweichungen trennen.

Fehlende Parameterkataloge in einem wiederverwendeten Testbestand nicht durch Änderungen an den echten Spielparametern „reparieren“.

**Why:** Ein isolierter Testlauf hatte migrationsgeseedete Kataloge beim Aufräumen geleert. Der nächste Gesamtlauf meldete viele Folgefehler, obwohl der gespeicherte Migrationsstand vollständig war; wiederverwendete Migrationen füllen diese Daten nicht erneut.

**How to apply:** Zuerst Testisolation und tatsächlichen Fixture-Stand prüfen, dann den Nachweis auf einer eindeutig getrennten frischen Testdatenbank wiederholen. Entwicklungsbestand, Pilot und Live-Daten weder neu seeden noch zurücksetzen, um einen Test grün zu bekommen.

Ein absichtlich weiterlaufender Bestand ist kein eingefrorener Snapshot. Änderungen zwischen einer frühen Kontrollmessung und späterer Verifikation offen ausweisen; die frühe Kontrollmessung nicht still ersetzen.

**Why:** Bei der Pilot-Einrichtung änderte sich während der Zugangsdaten-Eingabe der Profil-Fingerprint, obwohl Pilot-Schreibrechte auf den Bestand ausgeschlossen waren.

**How to apply:** Frühen Vorher/Nachher-Vergleich und das engere Verifikationsintervall getrennt dokumentieren. Gleiche Zeilenzahlen nicht als identische Inhalte ausgeben und die genaue Ursache nicht aus einem aggregierten Fingerprint erraten.

Diagnosen nach betroffenen Spielen und Zahlentypen aufschlüsseln; mehrere Prüfer können denselben Fehler mehrfach melden. Dateninkonsistenz und Erzählerfehler nur über eine unabhängige Quellenprüfung unterscheiden.

**Why:** Der Nutzer wies darauf hin, dass Meldungszahlen kein Maß für betroffene Spiele sind und eine pauschale Einordnung als harmlose Altdaten ohne Gegenprüfung nicht belegt ist.

**How to apply:** Erwartet/erzählt mit konkreten Fällen zeigen, fehlende Felder von vorhandenen Nullwerten unterscheiden und konsistente Eingaben direkt gegen die unveränderte Erzähler-Baseline prüfen. Eine Ausnahme für inkonsistente Eingaben entschuldigt keine Fehler bei konsistenten Eingaben.

Alte Stadion-Silhouetten niemals nachträglich mit einem Inhaltsnachweis versehen; fehlende Exportnachweise erfordern einen neuen Renderlauf.

**Why:** Ein nachträglicher Hash würde nur die vorhandene Datei bestätigen, nicht ihre tatsächliche Zugehörigkeit zur protokollierten Kamera, Orientierung oder zum Dachzustand.

**How to apply:** Nachweise während des Exports erzeugen und vor der Kartenauswertung prüfen. Sie belegen die Zuordnung der exportierten Bytes, sind aber weder eine Signatur gegen absichtlich gefälschte Protokolle noch eine visuelle Nutzerabnahme.

Eine funktionierende Stadion-Paketvorschau belegt keine Lauffähigkeit mit
dem gespeicherten Umfeld, wenn ihr Hilfsskript Quelldaten bereinigt.

**Why:** Eine Paketvorschau entfernte eine ungültige Zweipunkt-Wasserfläche,
während dieselbe Fläche im lokalen Bestand den gemeinsamen Renderer stoppte.

**How to apply:** Vorschau-Transformationen mit der tatsächlichen Laufzeiteingabe
vergleichen. Ungültige Flächen melden; genehmigte Ausnahmen exakt auf Inhalt
und Verein begrenzen, statt Gebäude oder andere Defekte pauschal zu entfernen.