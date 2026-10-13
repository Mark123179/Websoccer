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

Interne Vereinsnummern aus externen Stadionpaketen nicht ungeprüft
übernehmen. Den Zielverein über die kanonische FMI-ID auflösen.

**Why:** Ein Leverkusen-Paket nannte eine interne Vereinsnummer aus
einem anderen Datenbestand. Die FMI-ID stimmte, die lokale Vereinsnummer
jedoch nicht. Eine Korrektur nach der fremden Nummer könnte den falschen
Verein verändern.

**How to apply:** Vor Registrierung oder Geometriekorrekturen die
Zielidentität anhand der FMI-ID prüfen. Listenindizes für Umfeldkorrekturen
nur verwenden, wenn die betroffenen Quelldaten nachweislich übereinstimmen;
ein Paket allein erteilt keine Freigabe für Datenlöschungen.

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
