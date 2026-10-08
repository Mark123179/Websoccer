---
name: Spielfeldzentrierte Spielansicht und Ortskulisse
description: Verbindliche Bildhierarchie, nicht abgenommene Umfeldversuche und bisherige Entscheidungen zu gelieferten Vereinsbildern.
---

## Aktuelles Ziel

„Hauptteil des Bildes soll weiterhin das Spielfeld sein, dort soll der 2D Modus auch ablaufen.“ Darum das 3D-Stadion: sichtlicher Unterschied zwischen Elversberg vor etwa 14.000 und einem Stadion vor etwa 80.000, Dach an/aus sowie Tag/Nacht auswählbar. Die möglichst fotorealistische echte Umgebung soll Dortmund, Elversberg und später London oder Braga erkennbar machen.

**Why:** Der Nutzer lehnte auch die letzte Foto-/3D-Gesamtansicht ab: „das ist es nicht.“ Seine zweite neue Referenz zeigt ungefähr die gewünschte Nähe. Er betonte, dass der genaue Weg zum Ziel noch offen ist.

**How to apply:** Spielfeld und Lesbarkeit des 2D-Spiels zuerst gestalten; Stadion als räumlichen Rahmen, Ortskulisse nachgeordnet. Echte Stadionformen und einen vergleichbaren Feldmaßstab verwenden, nicht bloß eine generische Schüssel kapazitätsabhängig skalieren. Zuerst Bildaufbau visuell klären; keinen weiteren vollständigen Grafikumbau als bereits freigegeben behandeln und die bisherigen Bilder nicht zur unveränderlichen Zielkamera machen.

## Einheitliches Spielfeld

Die spielfeldzentrierte Vergleichsstudie erhielt die positive Rückmeldung
„sehr stark“. Danach verlangte der Nutzer beide Stadien bei Nacht.

**Why:** Das ist eine bestätigte positive Gestaltungsrichtung nach den zuvor
abgelehnten Umfeldversuchen, aber keine ausdrückliche Auswahl einer der beiden
Kameras oder Freigabe des produktiven Rollouts.

**How to apply:** Den feldzentrierten Bildaufbau beibehalten. Weitere Zustände
anhand tatsächlich gerenderter Ansichten zeigen; offene Kameraauswahl und
fehlende Umfeld-/Leuchtenquellen nicht als bereits abgenommen ausgeben.

„Das Spielfeld muss aber in jedem Stadion gleich groß sein, sonst bekommen wir beim Ablauf im 2D Modus probleme?!“

**Why:** Der Nutzer machte die Gleichheit ausdrücklich zur Bedingung für den 2D-Spielablauf.

**How to apply:** Einheitliche Spielkoordinaten und bei gleicher Ansicht/Fenstergröße identische sichtbare Feldgröße, Position und Perspektive vorsehen. Vereine, Kapazitäten und Ausbauten ändern nur den Stadionrahmen; keine vereinsabhängige Kameraeinpassung. Responsive Anpassungen skalieren alle Ebenen gemeinsam. Fremde Modellmaße an den gemeinsamen Spielfeldvertrag anschließen, nicht die Spielkoordinaten an jeden Import anpassen.

## Bisheriger Bildansatz

„Wir nehmen unser Stadionmodell und das Spielfeld wie gehabt und das Umfeld machen wir als zwei Bilder Tag & Nacht je Verein.“ „Ich werde die Bilder liefern.“

**Why:** Der Nutzer verwarf die modellierte 3D-Umgebung als ungenau, unansehnlich und zu teuer. Die bisherigen Vorgaben für Web-Modellbibliothek, Vegetations-Impostors, Autos und geografische Modellpakete sind für diesen Ersatzansatz überholt; diese Archive nicht erneut anfordern.

**How to apply:** Gelieferte Hintergrundbilder vereinsbezogen verwenden; darüber das echte Stadion und Spielfeld rendern. Keine eigenen Ersatzbilder generieren. Der produktive Neon-Editor bleibt ohne separate Freigabe unverändert; der bisher freigegebene Erprobungsumfang ist der geschützte Admin-Test.

„Das Umfeld-Bild darf kein Stadion enthalten.“ „Das Bild hängt nur noch am Gelände, nicht am Stadion. Baut der Spieler im Editor aus, muss nichts neu erzeugt werden.“

**Why:** Ein KI-generiertes Stadion weicht vom echten Modell ab und erzeugt sichtbare Überlagerungsränder. Der Hintergrund muss unabhängig vom Ausbauzustand bleiben.

**How to apply:** Das dargestellte Vereinsstadion nicht im Hintergrund vorzeichnen. Für zukünftige Bildvorbereitung feste Referenzkamera und exakte Stadion-Silhouettenmaske verwenden; Nutzer liefert die fertigen Bilder. Stadionausbau darf weder Bilderneuerstellung noch eine neue Ausrichtung anhand veränderter Stadiongrenzen auslösen.

Die bisherigen beiden 3D-Umfeld-Darstellungen und die anschließende Foto-/3D-Gesamtansicht sind nicht visuell abgenommen.

**Why:** Der Nutzer hat die Ansätze abgelehnt; bestandene technische Prüfungen waren keine Bestätigung der Optik.

**How to apply:** Neue tatsächlich gerenderte Bild-/Modellansichten zur visuellen Beurteilung vorlegen, ohne eine Nutzerabnahme aus Funktionstests abzuleiten.

Für die bisherige bildbasierte Studie hat der Nutzer die feste Kamera und das Entfallen des Höhenreglers im Admin-Test ausdrücklich bestätigt.

**Why:** Zwei feste Hintergrundbilder reichen nicht für wechselnde Blickwinkel mit korrekt ausgerichtetem 3D-Stadion.

**How to apply:** Die Kamera an den gelieferten Bildern kalibrieren und bei Größenänderungen sowie Stadionausbau registriert halten. Den Dachschalter erhalten; die Orbitkamera des produktiven Editors ist von dieser Freigabe nicht betroffen.
