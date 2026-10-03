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