---
name: Stadionmodell-Übergabe an Claude
description: Produktzweck der Registry als Übergabestelle für extern vorbereitete Stadionmodelle.
---

Der Nutzer erklärt den Zweck der Stadionmodell-Registry:
„claude braucht die Registry damit er dir die Arbeit abnehmen kann und du
nicht jedes Stadion machen musst.“

**Why:** Die externe Vorbereitung soll weitere Stadien ohne wiederholte
vereinsbezogene Arbeit am Anwendungscode ermöglichen.

**How to apply:** Künftige Modellübergaben an diesem Zweck ausrichten:
einen klaren Datenvertrag und prüfbare Pakete erhalten, statt pro Verein
erneut feste Sonderfälle einzubauen. Das ist keine pauschale Freigabe
für Vereinsanlagen oder Änderungen an Spieldaten.

Neue Stadionpakete dürfen den gemeinsamen Spielfeldvertrag nicht unbemerkt
verletzen. Unbekannte Liniengeometrie muss ausdrücklich als nicht automatisch
messbar gemeldet werden; ein Paket darf deshalb weder still bestehen noch
ungefragt skaliert werden.

**Why:** Der Nutzer nennt die gleichen Spielfeldmaße als kritische Voraussetzung
für den späteren 2D-Spielablauf, unabhängig von den unterschiedlichen Rasenflächen.

**How to apply:** Die Mittellinienmaße der Quellgeometrie belegen, nicht die
Gesamt-Bounding-Box einschließlich Linienbreite, Eckbögen und Hintertormarkierungen.
Fehlende ignorierte Prüfartefakte sind kein Nachweis; an den Originalen neu messen.

Interne IDs aus externen Stadionpaketen stimmen nicht mit denen der
eigenen Datenbank überein. Sie müssen bei jeder Übergabe auf die lokalen
Datensätze abgebildet werden.

**Why:** Der Nutzer stellt ausdrücklich klar: „Die ID´s werden nie
stimmen....die müssen wir dann eben an unsere Datenbank anpassen.“
Leverkusen und Frankfurt lieferten tatsächlich fremde interne
Vereinsnummern. Eine Übernahme nach diesen Nummern könnte einen
falschen Verein verändern.

**How to apply:** Vor Registrierung oder Geometriekorrekturen die
Quellidentität (z. B. FMI-ID plus Vereinsidentität) mit dem lokalen Verein
abgleichen und dessen Vereins- und Stadion-IDs aus der eigenen Datenbank
lesen; bei fehlender oder widersprüchlicher Zuordnung abbrechen.
Kapazität und Design lokal lesen, nicht aus der Paketvorschau übernehmen.
Listenindizes für Umfeldkorrekturen nur verwenden, wenn die betroffenen
Quelldaten nachweislich übereinstimmen; ein Paket allein erteilt keine
Freigabe für Datenlöschungen.

Eine ausdrücklich erlaubte Zwischenübernahme trotz bekanntem Dachmangel
ist nicht mit fachlicher Dachabnahme gleichzusetzen.

**Why:** Bei der BayArena verlangte der Nutzer nach dem Hinweis auf die
ungeklärte Dachdeckung „und direkt übernehmen“. Der gelieferte Stand darf
also genutzt werden, ohne die Dachfrage als gelöst auszugeben.

**How to apply:** Diese bewusste Zwischenfreigabe bei späteren Dachprüfungen
berücksichtigen. Korrekturen weiterhin an der Originalquelle belegen;
die Freigabe nicht auf andere Stadionpakete übertragen.

Eine fehlende Dachhaut in einer exportierten Stadionansicht beweist nicht,
dass die Originalquelle keine Dachhaut enthält. Exportierte Wurzeln müssen
gegen die gesamte Quellhierarchie abgeglichen werden.

**Why:** Bei der BayArena lag die echte Dachhaut unter einer im
Standardexport ausgelassenen Zusatzwurzel. Die vorläufig übernommene
Fassung war deshalb ohne Deckung, obwohl sie im Original vorhanden war.

**How to apply:** Vor Rekonstruktionen alle Quellwurzeln samt Meshes,
Materialien und Transparenz isoliert prüfen. Ergänzende Wurzeln gezielt
für das betroffene Modell exportieren, nicht pauschal für andere Stadien.

Videotafeln und Videowürfel gehören zum Dachzustand: Dach an bedeutet
sichtbar, Dach aus bedeutet ausgeblendet.

**Why:** Der Nutzer möchte Videotafeln immer ans Dach hängen: „bei Dach on =
Videowürfel da, bei Dach aus, ist er weg“. Beim Frankfurter Modell war
dieser Schalter für den hängenden Videowürfel bereits nachprüfbar.

**How to apply:** Bei künftigen Stadionpaketen vorhandene Tafeln und ihre
Halterungen anhand der Quelle dem Dachschalter zuordnen und beide Zustände
im Editor sowie Ticker prüfen. Fehlende Quelltafeln nicht erfinden; bei
unklarer Montage vor einer geometrischen Änderung Rückfrage stellen.
