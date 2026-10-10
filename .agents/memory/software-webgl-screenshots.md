---
name: Software-WebGL-Aufnahmen
description: Screenshots von Three.js-Szenen in der Browserumgebung ohne Hardware-WebGL.
---

Die integrierte Preview-Screenshot-Umgebung konnte eine Three.js-Szene wegen fehlendem WebGL-Kontext nicht rendern. Ein lokales Headless-Chromium mit Software-WebGL konnte dieselbe Szene rendern.

**Why:** Die Standardaufnahme zeigt sonst nur einen leeren Hintergrund und ist als visueller Nachweis irreführend.

**How to apply:** Bei WebGL-Screenshot-Ausfall vor einem Darstellungsurteil eine alternative lokale WebGL-Aufnahme prüfen. Nur für Vorschauprüfung, nicht als Behauptung über Endgeräte oder Unity.

Eine generische 3D-Ladefehlermeldung ist auch kein Beweis für fehlendes WebGL: zuerst die Modulauflösung der eingebetteten Szene prüfen.

**Why:** Beim Übernehmen der Dortmund-Miniatur wurde die Szenendatei erfolgreich geladen, aber die auf der ursprünglichen Seite vorhandene Three.js-Importmap fehlte auf der neuen Seite. Der abgefangene Importfehler erschien nur als allgemeiner Stadion-Ladefehler.

**How to apply:** Beim Wiederverwenden von 3D-Ansichten deren Bootstrap-Abhängigkeiten mitnehmen. Vor einer Hardware-Diagnose prüfen, ob ein Canvas erzeugt wurde und die Szene den Ladezustand verlassen hat.

Bei einer nach dem ersten Bild pausierten WebGL-Szene kann die Software-Browseraufnahme hängen bleiben, obwohl die Szene fertig und fehlerfrei gerendert ist. Ein direkter Canvas-Bildexport mit nur im Prüfbrowser erhaltenem Zeichenpuffer liefert einen visuellen Nachweis.

**Why:** Die Screenshot-Aufnahme wartete erfolglos auf stabile Browserframes; derselbe angemeldete Test konnte den tatsächlich gerenderten Canvas auf Desktop und Mobilgerät exportieren.

**How to apply:** Die Aufnahme vom Rendererzustand unterscheiden. Für die Prüfung den Zeichenpuffer im Browser erhalten und den Canvas exportieren; diese Speicheroption nicht allein für Screenshots dauerhaft in die Anwendung einbauen. Der Export belegt den Canvas, nicht die umgebende Oberfläche.

Bei komplexen Schatten-/Instanzszenen können mehrere erfolgreiche Canvas-Exporte zusammen die Laufzeitgrenze eines Shellaufrufs überschreiten.

**Why:** Eine vollständige Desktop-/Mobilreihe mit Software-WebGL überschritt die Grenze, obwohl die ersten fünf Bilder korrekt gespeichert waren. GPU-Synchronisation beim Export ist keine Hardware-FPS-Messung.

**How to apply:** Aufnahmereihen nach Szenarien aufteilen oder als überwachte Hintergrundarbeit ausführen und Ergebnisse nach jedem Bild sichern; einen Timeout nicht ohne Prüfung als Szenendefekt werten.

Ein erstmaliger Lichtprofilwechsel kann in Software-WebGL mehrere Sekunden im Renderaufruf verbringen, während spätere Aufrufe derselben Szene deutlich schneller sind.

**Why:** Bei der Bild-/Stadionansicht benötigte der erste Nachtwechsel ungefähr fünf Sekunden, spätere Nacht-Aufrufe nur Millisekunden. Neue Licht-/Schatten-Shader-Varianten verfälschen eine einzelne vermeintliche Framezeit.

**How to apply:** Kalte Shader-Kompilierung, warme Renderaufrufe und GPU-Synchronisation getrennt berichten. Einen einmaligen langen Profilwechsel nicht als dauerhafte Szenen-FPS interpretieren und keine Hardware-Leistung aus SwiftShader versprechen.

Der Standard-Prüfbrowser kann ohne nutzbaren WebGL-Kontext starten, obwohl
derselbe Editor mit dem lokalen Chromium korrekt als WebGL-Szene lädt.

**Why:** Ein Editorwechsel zeigte im Standard-Prüfbrowser nur die Karte und
einen uninitialisierten Canvas. Der explizite lokale Chromium-Start mit
SwiftShader stellte dieselbe Integration korrekt dar.

**How to apply:** Zuerst WebGL2-Verfügbarkeit und den tatsächlich gestarteten
Renderer prüfen. Falls nötig `/repl/tools/bin/chromium` mit
`--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader` verwenden.
Eine solche Karte nicht als erfolgreiche 3D-Aufnahme oder ohne weitere
Diagnose als Produktdefekt behandeln.