---
name: Software-WebGL-Aufnahmen
description: Screenshots von Three.js-Szenen in der Browserumgebung ohne Hardware-WebGL.
---

Die integrierte Preview-Screenshot-Umgebung konnte eine Three.js-Szene wegen fehlendem WebGL-Kontext nicht rendern. Ein lokales Headless-Chromium mit Software-WebGL konnte dieselbe Szene rendern.

**Why:** Die Standardaufnahme zeigt sonst nur einen leeren Hintergrund und ist als visueller Nachweis irreführend.

**How to apply:** Bei WebGL-Screenshot-Ausfall vor einem Darstellungsurteil eine alternative lokale WebGL-Aufnahme prüfen. Nur für Vorschauprüfung, nicht als Behauptung über Endgeräte oder Unity.