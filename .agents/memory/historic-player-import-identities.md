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
oder Gesamtzahl. Eine erfolgreiche abgesicherte Bestandsverknüpfung beweist keine
allgemeine Importer-Korrektur.

Fehlende historische FM-IDs oder Geburtsdaten allein sind kein Widerspruch,
wenn eine identische kanonische TM-Identität eindeutig belegt ist.

**Why:** Historische Quellbelege können unvollständig sein, ohne dass die
bekannte kanonische Identität dadurch ihre Aussagekraft verliert.

**How to apply:** Bekannte IDs und Geburtsdaten auf Widersprüche prüfen,
fehlende Belege nicht mit abweichenden Belegen verwechseln. Niemals Namen
allein verwenden oder widersprüchliche Quellidentitäten auflösen.

Identitätsvorprüfungen einer gesamten Lieferung bleiben nach Teilimporten
nicht automatisch gültig: Ein zuvor importierter Verein kann neue historische
Rekordpersonen für einen noch ausstehenden Kader anlegen.

**Why:** Ein früheres Paket kann eine Rekordperson anlegen, deren aktive
Identität erst ein späteres Paket benötigt. Eine anfängliche Gesamtvorprüfung
kann diesen späteren Bestand noch nicht berücksichtigen.

**How to apply:** Noch ausstehende Pakete gegen den aktuellen Bestand erneut
prüfen und die Verknüpfung in der abschließenden Schreibtransaktion absichern.
Neu auflösbare Vereinsreferenzen getrennt von unveränderlichen historischen
Quellfakten vergleichen.

Kanonische IDs einer historischen Person bleiben bei dieser Person; die aktive
Identität wird über ihre Verknüpfung aufgelöst. Keine Übertragung oder Verdopplung
der ursprünglichen ID-Zeilen, auch wenn eine aktive Spiegel-ID ergänzt wird.

**Why:** Die XOR-Eigentümerbedingung erlaubt nur einen direkten Eigentümer.
Das Beibehalten der historischen Eigentümerschaft erhält zudem ursprüngliche
Quellbelege und vermeidet das Umschreiben geschützter Rekordbezüge.

**How to apply:** Verbraucher kanonischer Spieler-IDs müssen auch verknüpfte
historische Eigentümer berücksichtigen. Ein fehlender Eintrag direkt am aktiven
Spieler ist deshalb kein Beweis für eine freie oder unbekannte ID.
