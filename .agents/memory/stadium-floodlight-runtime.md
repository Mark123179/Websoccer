---
name: Stadion-Flutlicht-Laufzeitvertrag
description: Regeln für unabhängigen Flutlichtzustand und begrenzte Three.js-Lichtquellen.
---

Flutlichter müssen aus dem jeweiligen Modell erkannt und ausdrücklich deklariert werden; Nachtlicht darf nicht aus willkürlich verteilten Lichtquellen stammen.

**Why:** Der Nutzer verlangte: „wir müssen Flutlichter aus dem Modell irgendwie erkennen und deklariere, sodass bei NAcht nicht willkürliches Licht von überall hinfällt.“

**How to apply:** Kandidaten aus Modellkomponenten und Geometrie prüfen und Montagepunkt, Modellbezug sowie Ausrichtung deklarieren. Generische Dach-/Mastpläne und frei berechnete Leuchtenpositionen nicht als Quellnachweis behandeln. Fehlende Modellleuchten benennen statt Ersatzlicht erfinden; die Zuordnung in einer Kontrollansicht sichtbar prüfen.

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

Bei dieser Begrenzung müssen repräsentative Lichtquellen an deklarierten realen Montagepunkten sitzen; ein geometrischer Gruppenmittelpunkt ohne Leuchte ist kein gültiger Ersatz.

**Why:** Die neue Nutzeranforderung verlangt nachgewiesene Modellleuchten, auch wenn die Laufzeit aus Leistungsgründen weniger Lichtquellen nutzt.

**How to apply:** Reale Leuchten als Gruppenrepräsentanten auswählen und die übrigen zugeordneten Köpfe dokumentieren; keine künstlichen Ecken oder Mittelpunkte als Lichtursprung erzeugen.

Quelllicht-Intensität ist Provenienz, nicht automatisch eine passende
Three.js-Helligkeit. Eine Browserkalibrierung darf Lichtstärke und Gruppengewicht
anpassen, aber keine erfundenen Montagepunkte, Lichtachsen oder unsichtbaren
Rasen-/Sitzemissionen hinzufügen.

**Why:** Unity- und Browserbeleuchtung sind nicht dieselbe Darstellungseinheit;
direktes Übernehmen bei anderem Distanzabfall kann das Bild überstrahlen oder
das Spielfeld trotz echter Quellen unlesbar machen.

**How to apply:** Intensitätskalibrierung und Gruppierung offenlegen. Originale
Positionen, Winkel und Richtungen erhalten; Tag/Nacht und Flutlicht separat
prüfen. Selbstleuchtende Editor-Materialien nicht ungeprüft in eine
quellgebundene Nachtstudie übernehmen.