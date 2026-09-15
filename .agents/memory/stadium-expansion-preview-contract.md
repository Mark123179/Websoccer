---
name: Stadionausbau-Vorschauvertrag
description: Nicht offensichtliche Regeln für sichtbare Ausbaugröße und interaktive Sitzkamera.
---

Die sichtbare Größe eines transienten Stadionausbaus ist absolut: 1.000
zusätzliche Plätze entsprechen einer sichtbaren Reihe über der gewählten
Tribüne. Die wirtschaftliche Vorschaukapazität wird davon getrennt und bleibt
exakt die eingegebene Platzmenge.

**Why:** Breite Blueprint-Raster können pro Datenreihe mehr als 10.000 Plätze
enthalten. Wird die Geometrie daraus abgeleitet, sehen 10.000 und 20.000 Plätze
fast identisch aus. Eine Proportion zur bestehenden Kapazität wäre ebenfalls
falsch, weil derselbe Ausbau bei kleinen und großen Vereinen unterschiedlich
groß würde.

**How to apply:** Neue Ausbau-, Rang- oder Kapazitätslogik muss sichtbare Reihen
und Kapazität getrennt behandeln. Nach 42 sichtbaren Reihen beginnt ein neuer
Rang; die Gesamtgrenze bleibt unabhängig davon bestehen.

Interaktive Pointer-Handler der Sitzkamera müssen an jedes neu erzeugte
WebGL-Canvas gebunden werden; Bewegungs- und Abschlussereignisse dürfen am
Fenster weiterlaufen.

**Why:** Der Renderer ersetzt das Canvas bei jedem Stage-Neuaufbau. Eine
Bindung nur an einen früheren Canvas-Zustand oder indirekt an den Host führte
trotz sichtbarer Bühne zu wirkungslosen Ziehgesten.

**How to apply:** Beim Erzeugen eines Canvas Start-/Reset-/Wheel-Handler erneut
binden; globale Move-/Up-Handler beim Dispose entfernen.