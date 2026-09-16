---
name: Stadion-Umgebungslichtvertrag
description: Dauerregeln für Tag/Nacht-Presets, Tonemapping und in-place Lichtwechsel.
---

Tag und Nacht verwenden abgestimmte Presets aus Hemisphere-, Ambient-, Key-,
Fill- und Materiallicht. Der Wechsel wird in derselben Three.js-Stage angewandt
und darf Kamera, Geometrie oder Bemalung nicht ersetzen.

**Why:** Ein Stage-Rebuild beim Lichtwechsel erschwert identische
Vergleichsperspektiven und kann Kamera- oder Designzustand verlieren. ACES
Filmic Tone Mapping schützt helle Flutlichtflächen, komprimiert aber sehr dunkle
Rasen-, Dach- und Fassadenfarben stark; ein einzelner hoher Exposure-Wert macht
dann helle Flächen kaputt, ohne alle Schatten sinnvoll zu öffnen.

**How to apply:** Neue Lichtstimmungen als vollständige, testbare Presets
definieren und per Laufzeitmethode anwenden. Exposure nur als separaten
Nutzermultiplikator auf den preset-eigenen Wert rechnen. Dunkle Flächen über
abgestufte reale Lichtquellen und kleine Material-Helligkeitsböden lesbar
halten; Flutlichtzustand weiterhin unabhängig behandeln.