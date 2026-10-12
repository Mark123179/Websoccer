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
