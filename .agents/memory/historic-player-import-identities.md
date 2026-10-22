---
name: Historische Spieleridentitäten beim Kaderimport
description: Rekord-Personen können kanonische IDs eines später importierten aktiven Spielers bereits belegen.
---

Eine fehlende aktive Spielerzeile bedeutet nicht, dass ihre TM-/FM-Identität frei
ist: Historische Rekord-Personen derselben Identitätsart können diese IDs bereits
besitzen. Vorprüfungen dürfen kanonische IDs ohne aktive Spielerzuordnung nicht
auslassen.

**Why:** Beim additiven Kaderimport wurde eine belegte TM-ID übersprungen und
trotzdem eine aktive Spielerzeile ohne TM-ID gespeichert. Nur der unabhängige
Vergleich aller erwarteten Spieleridentitäten verhinderte einen unvollständigen
Import im Hauptbestand.

**How to apply:** Bei nachweislich derselben TM- und FM-Identität und ohne
widersprechendes bekanntes Geburtsdatum die Rekord-Person erhalten und mit dem
aktiven Spieler verknüpfen; Quellnachweise und bestehende Rekordbezüge bewahren.
Keine Zusammenführung anhand des Namens. Mehrdeutigkeit oder abweichende
Quell-IDs bleiben ein harter Stopp. Nach jedem Import alle erwarteten TM-IDs,
kanonischen Quell-IDs und Wiederholbarkeit prüfen, nicht nur die Laufmeldung
oder Gesamtzahl. Der reguläre Paketimport übernimmt diesen Übergang noch nicht
zuverlässig; eine erfolgreiche abgesicherte Bestandsverknüpfung beweist keine
allgemeine Importer-Korrektur.

Für den St.-Pauli-Import hat der Nutzer die Verknüpfung von Hrgota mit der
vorhandenen Rekordperson ausdrücklich freigegeben, obwohl deren historische
FM-ID und Geburtsdatum fehlten; die kanonische TM-Identität war eindeutig.

**Why:** Der Nutzer wählte „Verknüpfen und St. Pauli importieren“ nach
Erläuterung dieses Falls.

**How to apply:** Diesen Fall als freigegebene Verknüpfung behandeln, nicht
als allgemeine Erlaubnis für Namensmatching oder das Auflösen widersprüchlicher
Quellidentitäten. Historische Personen und ihre Rekordbezüge erhalten.

Identitätsvorprüfungen einer gesamten Lieferung bleiben nach Teilimporten
nicht automatisch gültig: Ein zuvor importierter Verein kann neue historische
Rekordpersonen für einen noch ausstehenden Kader anlegen.

**Why:** Erst das Magdeburger Paket legte eine Rekordperson an, deren aktive
Identität anschließend beim St.-Pauli-Import benötigt wurde. Die anfängliche
Gesamtvorprüfung konnte diesen späteren Bestand noch nicht berücksichtigen.

**How to apply:** Noch ausstehende Pakete gegen den aktuellen Bestand erneut
prüfen und die Verknüpfung in der abschließenden Schreibtransaktion absichern.
Neu auflösbare Vereinsreferenzen getrennt von unveränderlichen historischen
Quellfakten vergleichen.
