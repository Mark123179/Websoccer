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
