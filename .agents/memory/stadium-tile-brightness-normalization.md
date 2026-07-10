---
name: Management-Hub Stadion-Kachel Helligkeits-Normalisierung
description: Automatische Helligkeitsangleichung der Stadion-Kachel im Management-Hub gegenüber den übrigen (statischen) Kacheln
---

Jeder Verein hat ein eigenes, real fotografiertes Stadionbild (`ClubPublicProfile.stadium_image_static_path`, ~140 Bilder unter `game/static/game/images/stadiums/germany/`). Diese Fotos variieren stark in natürlicher Belichtung (Tag/Nacht), während alle übrigen Management-Hub-Kacheln fest kuratierte, einheitlich dunkel-moody Bilder nutzen (Ziel-Luminanz ≈ 34 auf 0–255-Graustufenskala). Dadurch fiel die Stadion-Kachel optisch als zu hell auf.

Lösung: `game/stadium_brightness.py` + `python manage.py build_stadium_brightness_map` (Pillow, 64×64-Graustufen-Mittelwert pro Bild) erzeugen offline eine JSON-Map (`game/static/game/data/stadium_brightness_map.json`) mit einem CSS-`brightness()`-Faktor pro Bildpfad (geclamped 0.45–1.30). Die View übergibt `stadium_bg_filter` an den Template-Inline-Style der `.mhub-card-bg`.

**Warum:** Ein einzelner, für alle Kacheln fixer Overlay-Gradient kann große Helligkeitsunterschiede zwischen Quellfotos nicht ausgleichen (linear, nicht normalisierend). Pro-Bild-Filter ist nötig, weil neue Vereinsfotos jederzeit hinzukommen können.

**How to apply:** Bei neuen Stadionbildern `build_stadium_brightness_map` erneut laufen lassen, sonst Fallback `brightness(1) contrast(1)` (neutral, evtl. wieder zu hell). Ziel-Luminanz 34 wurde aus den bestehenden kuratierten Kacheln (sportvorstand/finanzen/sponsoring/... ≈ 28–48) kalibriert — bei Redesign der übrigen Kacheln ggf. neu kalibrieren.
