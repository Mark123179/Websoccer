---
name: Stadion-Flutlicht-Laufzeitvertrag
description: Regeln für unabhängigen Flutlichtzustand und begrenzte Three.js-Lichtquellen.
---

Flutlichter müssen aus dem jeweiligen Modell erkannt und ausdrücklich deklariert werden; Nachtlicht darf nicht aus willkürlich verteilten Lichtquellen stammen.

Bei der Voith-Arena sollen eingeschaltete Masten sichtbar leuchtende
Lampenflächen und dezente, weich auslaufende Lichtkegel haben.

**Why:** Nach der Stadionabnahme wirkte die Nachtansicht für den Nutzer,
als seien die Masten ausgeschaltet. Er wählte ausdrücklich „Leuchtende
Lampen und dezente Lichtkegel“ statt ausschließlich leuchtender Lampen.

**How to apply:** Sichtbare Lampen und Luftstreuung an belegten
Quellflächen/-achsen ergänzen, unabhängig vom Tag/Nacht-Zustand über den
Flutlichtschalter steuern. Diesen visuellen Wunsch nicht als Anlass nehmen,
die vorhandene Spielfeldbeleuchtung oder andere Stadien mitzuverändern.

Importierte Unity-Lichtkomponenten sind nicht automatisch der Nachweis für
die sichtbaren Flutlichtanlagen des neuen Modells.

**Why:** Die Heidenheimer Quelle enthielt Punkt-/Flächenlichter mit unpassender
Reichweite statt nutzbarer stadiongerichteter Spots, zugleich aber eindeutig
texturierte und geneigte Lampenflächen an vier Masten.

**How to apply:** Typ, Reichweite und Ausrichtung zuerst mit den tatsächlichen
Emitterflächen abgleichen. Bei ungeeigneten Komponenten dürfen geprüfte
UV-Lampenpunkte und Dreiecksnormalen die geometrischen Quellen belegen.
Die Browser-Helligkeit bleibt ausdrücklich eine Laufzeitkalibrierung, keine
Behauptung über die ursprüngliche Unity-Photometrie.

**Why:** Der Nutzer verlangte: „wir müssen Flutlichter aus dem Modell irgendwie erkennen und deklariere, sodass bei NAcht nicht willkürliches Licht von überall hinfällt.“

**How to apply:** Kandidaten aus Modellkomponenten und Geometrie prüfen und Montagepunkt, Modellbezug sowie Ausrichtung deklarieren. Generische Dach-/Mastpläne und frei berechnete Leuchtenpositionen nicht als Quellnachweis behandeln. Fehlende Modellleuchten benennen statt Ersatzlicht erfinden; die Zuordnung in einer Kontrollansicht sichtbar prüfen.

Die fehlenden Elversberger Leuchtennachweise liefert der Nutzer später nach.

**Why:** Auf die Erklärung der fehlenden konkreten Montagepositionen und
Ausrichtungen antwortete er: „ahso okay, liefere ich später nach.“

**How to apply:** Die angekündigte Nachlieferung als Quelle für die spätere
Deklaration prüfen; bis dahin keine erfundenen Positionen als Nachweis verwenden.

Der Nutzer erlaubt vorerst die sichtbaren schematischen Elversberger Masten:
„Nur 2D-Zoom merken; schematische Masten vorerst behalten“. Er wurde darüber
informiert, dass die V2-Angabe von vier 30-m-Masten zu generierten
Eckpositionen führt, nicht zu nachgewiesenen echten Montageorten.

**Why:** Auf die Herkunftserklärung wählte er ausdrücklich das vorläufige
Beibehalten und bat um eine Nachtansicht.

**How to apply:** Diese vorläufige Darstellung darf bleiben; Nachtaufnahmen
mit diesen Quellen als schematisch kennzeichnen. Die Freigabe ersetzt weder
die spätere Nachlieferung noch den Nachweis realer Leuchtenpositionen.

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
Modellspezifische Helligkeitskorrekturen nicht über gemeinsame Lichtwerte
erzwingen, damit andere Stadien unverändert bleiben. Bereits in Exportwerte
eingerechnete Faktoren mit Quellwertbeleg und idempotenter Anwendung absichern;
eine erneute Übergabe darf sie nicht ein zweites Mal multiplizieren.

Dachabschattung benötigt einen Vergleich mit weiterhin sichtbarem Dach,
bei dem ausschließlich dessen Schattenwurf abgeschaltet wird.

**Why:** Dach-an/Dach-aus verändert zugleich die Verdeckung gegenüber der
Kamera. Heller sichtbare Tribünenflächen nach dem Entfernen des Dachs allein
beweisen deshalb keine Änderung der Beleuchtung.

**How to apply:** Bei isolierten Schattenproben den zusätzlichen
Nicht-Schattenwerfer-Zustand mit identischer Kamera, Leuchtenauswahl,
Intensität und übrigen Schatten verwenden. Geometrische Bildverdeckung,
Raster-Schatten und photometrische Aussagen getrennt behandeln.