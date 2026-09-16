---
name: Stadion-Flutlicht-Laufzeitvertrag
description: Regeln für unabhängigen Flutlichtzustand und begrenzte Three.js-Lichtquellen.
---

Flutlicht ist ein eigener Laufzeitzustand und darf nicht aus Tag/Nacht abgeleitet
werden. Ein reiner Flutlichtwechsel verändert bestehende Lichtintensitäten und
Leuchtenemissionen, ohne Geometrie, Kamera oder Design neu aufzubauen.

**Why:** Tag/Nacht steuert Himmel und Grundambiente, während Flutlicht auch am Tag
separat schaltbar sein muss. Außerdem erzeugen große Rim-Stadien über 100 sichtbare
Leuchtenköpfe; ebenso viele SpotLights überschreiten auf schwächeren WebGL-Geräten
Shader-/Uniform-Grenzen.

**How to apply:** Den Flutlichtzustand bei jedem Kamera-/Szenen-Rebuild erneut
anwenden. Sichtbare Rim-Leuchten dürfen vollständig gerendert werden, funktionale
SpotLights aber deterministisch auf höchstens drei pro Stadionseite (zwölf gesamt)
begrenzen. Tages-/Nachtambiente und Belichtung nicht mit dem Flutlichtschalter
koppeln.