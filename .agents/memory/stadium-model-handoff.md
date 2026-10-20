---
name: Stadionmodell-Übergabe an Claude
description: Produktzweck der Registry als Übergabestelle für extern vorbereitete Stadionmodelle.
---

## Künftige gemeinsame Stadionarbeit

Der Nutzer möchte die nächsten Stadien gemeinsam mit Replit Agent statt
mit Claude erstellen: „erstelle mit dir die nächsten statt mit Claude“.

**Why:** Ausdrückliche Änderung der bisherigen Arbeitsteilung durch den Nutzer.

**How to apply:** Weitere Stadionarbeiten hier gemeinsam vorbereiten und
durchführen; keine Claude-Übergabe als Voraussetzung verlangen. Bestehende
Quell-, Prüf- und Freigabeanforderungen bleiben bestehen.

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

Bei Stadionpaketen mit Diff-Dateien und vollständigen Nachher-Dateien
beide Fassungen auf Übereinstimmung prüfen, statt sie als austauschbar
zu behandeln.

**Why:** Ein korrigiertes Frankfurt-Paket enthielt eine ältere Diff-Datei
und eine neuere vollständige Umfeld-Datei. Nur die vollständige Fassung
erhielt das Altverhalten einschließlich vorzeichenbehafteter Null und
der frühen Prüfung ungültiger Achsen.

**How to apply:** Tests gegen die tatsächlich für den Einbau gewählte
Fassung ausführen. Abweichende Diffs aus dem geprüften Endstand neu
erzeugen; unveränderte Bestandsfehler mit einem Kontrolllauf unterscheiden.

## Kurvenlage und abgeleitete Heimkurvenmarkierung

Bei angeforderten Stadionpaket-Korrekturen zugleich eine aktualisierte
Anweisung für Claude zu zukünftigen Arbeiten liefern.

**Why:** Der Nutzer hat diesen Ablauf wiederholt vorgegeben:
„wie immer, korrigieren und anweisungen an Claude für zukünftige Arbeiten“.

**How to apply:** Die konkret freigegebenen Korrekturen ausführen und
die daraus verbindlichen Anforderungen als übergebbare Anweisung
festhalten; eine Paketprüfung allein erweitert nicht die Freigabe.

Kurvenzuordnungen gegen einen offiziellen Stadionplan und geografische
Umfeldanker prüfen, nicht allein gegen die automatisch aus der Rohblaupause
abgeleitete Heimkurve. Eine falsche Darstellung rechtfertigt keinen
pauschalen Nord-/Süd-Tausch der wirtschaftlichen Kapazitäten.

**Why:** Der offizielle MHPArena-Plan ordnet die Cannstatter Heimkurve dem
Carl-Benz-Center-Ende (NW), die Untertürkheimer Kurve samt Gästebereich dem
SCHARRena-Ende (SO) zu. Das Stuttgart-Paket folgte dagegen einer aus dem
Roh-Sitzraster abgeleiteten SUED-Heimkurve und spiegelte damit das Umfeld
längs zum Quellmodell. Die wirtschaftlichen Stehplatzkapazitäten hatten
die große Heimseite bereits im NORD. Roh-Rastergrößen und wirtschaftliche
Kapazitäten waren hier keine austauschbaren Belege.

**How to apply:** Quellmodell, geografische Umfeldtransformation,
explizite Heimkurvenmetadaten und Kapazitätsdaten getrennt vergleichen.
Ein technisch gültiges Achsenpaar beweist nur Labelkonsistenz, nicht die
richtige reale Lage. Quelle: offizieller Blockplan auf
https://www.mhparena-stuttgart.de/arena/arenaplan .
