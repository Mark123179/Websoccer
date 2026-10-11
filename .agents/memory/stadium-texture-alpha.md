---
name: Stadion-Texturmasken
description: Scheinbar schwebende weiße Flächen können Bodenmarkierungen mit ignorierter Alpha-Maske sein.
---

Bei schwarzen oder weißen Rechteckflächen in Originalstadien erst
Materialmaske und tatsächliche Geometrie prüfen, bevor weitere
Modellteile entfernt werden.

**Why:** Die weißen „Kanten in der Luft“ der Allianz-Arena-Vorschau
waren bodennahe Markierungsflächen. Ihre Textur enthält die eigentlichen
Linien, Logos und Gebrauchsspuren im Alpha-Kanal; ohne diesen erscheinen
die ganzen Trägerpolygone weiß. Das ist nicht derselbe Sachverhalt wie
unerwünschte Choreos oder absichtlich ausgeblendete Fangnetze.

**How to apply:** RGBA-Texturen vor einem kontrastierenden Hintergrund
ansehen und sichtbare Artefakte den Quellmeshes räumlich zuordnen.
Markierungen nicht allein wegen ihres fehlerhaften Vorschau-Aussehens
als Netzhalterungen oder beschädigte Geometrie deklarieren.

Die Bodenmarkierungen der Allianz Arena erhalten und ihre Transparenz
korrigieren, statt sie auszublenden.

**Why:** Der Nutzer wählte ausdrücklich „Transparenz im Renderer
korrigieren“ statt der angebotenen Entfernung dieser Bodenmarkierungen.

**How to apply:** Diese Entscheidung bei weiteren Paketkorrekturen
bewahren. Sie hebt die separate Ausblendung von Choreo und Fangnetzen
nicht auf und ist keine Freigabe für einen Spielimport.

Bei einer fehlerhaften Bodenmaske die übrigen Boden-Detailmaterialien
derselben Quelle ebenfalls auf Alpha-Masken prüfen, nicht nur das zuerst
auffällige weiße Material.

**Why:** Die erste, auf weiße Trägerflächen begrenzte Korrektur ließ
rechteckige Gebrauchsspuren und harte Streifen anderer Bodenmaterialien
zurück. Auch diese waren keine echten Lichtschatten, sondern unmaskierte
Originaltexturen.

**How to apply:** Originalmasken über einem kontrastierenden Hintergrund
ansehen und die ganze Materialfamilie in denselben Vorher-/Nachher-Ansichten
prüfen. Bei Raycast-Diagnosen ausgeblendete und durch die Ticker-Schnittebene
abgeschnittene Flächen ausschließen; ein Geometrietreffer allein beweist
bei transparenten Texturen keinen sichtbaren Bildbeitrag.

Eine Alpha-Korrektur ist keine Zusage, dass alle dunklen Bodenflecken
verschwinden: In der Allianz-Arena-Quelle liegt unter den Markierungen
auch eine anders texturierte Rasenunterlage. Ein sichtbares Rechteck
darf dieser Unterlage aber nicht allein aufgrund des Farbunterschieds
zugeordnet werden.

**Why:** Nach der vollständigen Bodenmasken-Korrektur verschwanden die
harten weiß-schwarzen Streifen, während Teile der dunkleren Rasenunterlage
weiter sichtbar blieben.

**How to apply:** Die korrigierte Ansicht tatsächlich ansehen und
verbleibende Materialkontraste offen benennen; keine vollständige
Bodenbereinigung allein aus aktivierter Transparenz ableiten.

Die Allianz-Arena-Rasenunterlage an das Spielfeld angleichen.

**Why:** Der Nutzer wählte ausdrücklich „Rasenunterlage an das Spielfeld
angleichen“ statt der Beibehaltung der originalen Rasenunterlage.

**How to apply:** Bei weiteren Paketänderungen diese optische Entscheidung
bewahren. Sie bleibt paketbezogen, ohne Freigabe für einen Spielimport.

Auch eine Rasenangleichung allein beweist nicht die Ursache sichtbarer
dunkler Rechtecke. Die auffälligen Bildflächen müssen unabhängig von
Materialnamen eindeutig dem tatsächlich gerenderten Objekt zugeordnet
werden.

**Why:** Das Angleichen der Unterlage und zusätzlich naheliegender
Bodenmaterialien ließ einige der beanstandeten Rechtecke sichtbar.
Die zuvor behauptete vollständige Zuordnung zur Rasenunterlage war
damit nicht belegt.

**How to apply:** Vor weiteren Materialänderungen die sichtbaren Flächen
isoliert identifizieren. Keine weitere vermeintlich fertige Version
liefern, nur weil Material- und Archivprüfungen bestanden sind.
