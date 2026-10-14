# Neue Anweisung für Claude nach dem Bremen-Review

Ergänzt die Anweisungen nach Freiburg und Wolfsburg. Weitere Stadionpakete
für die bestehende Registry vorbereiten, ohne vereinsspezifische Renderer-Patches.

## Bremen: verbindlicher Zielstand

- FMI **948**, SV Werder Bremen, Weserstadion.
- Im **Blaupausenrahmen**: Heimkurve **SUED**, Haupttribüne **WEST**,
  Gegentribüne **OST**. SUED entspricht der realen Ostkurve, WEST der
  realen Südtribüne, OST der realen Nordtribüne, NORD der realen Westkurve.
  Diese Rahmenlabels niemals mit geografischen Tribünennamen gleichsetzen.
- Modellachsen `+x OST`, `-x WEST`, `+z NORD`, `-z SUED`;
  Umfeldachsen `{"NORD":"+z","WEST":"-x"}`. Kein Drehen/Spiegeln des Modells.
- Lokal **42.100 Plätze**. Öffentliche 41.800, rohe 42.294 und die
  39.095 Sitzplatzeinträge der Quelle sind keine Importwerte.
- Haupt-/Gegentribünenmetadaten lokal unter Zeilensperre und mit Backup
  korrigiert. Heimkurve war bereits SUED und bleibt ohne Metadatenänderung so.

## Wirtschaftliche Zuteilung nicht ungefragt korrigieren

- Der Paketbericht beschreibt einen anderen öffentlichen Datenstand.
  Sein Vorschlag OST → SUED ist **nicht** auf den lokalen Bestand übertragbar.
- Lokal liegen wirtschaftlich 7.367 Stehplätze auf NORD und 1.579 auf SUED,
  keine auf OST. Diese Verteilung bleibt ausdrücklich unverändert.
- Keine Kapazitäten, Blocktypen, Reihen, Plätze, RLE, Designs, Ausbauten
  oder wirtschaftlichen Stadionfelder verändern.
- Eine Verlagerung von Stehplätzen wäre ein eigener fachlicher Auftrag.
  Renderzellen und wirtschaftliche Plätze getrennt ausweisen.

## Umfeld-Ausnahmen brauchen echte Freigabe

- Bremen `bg.water[2]` = `[[-159.1,-491.1],[-137.3,-447.5]]` hat nur
  zwei Punkte und ist keine Fläche. Genau dieser Eintrag wurde nach
  ausdrücklichem Nutzerauftrag lokal entfernt, mit Backup und Schutzvergleich.
- Keine zusätzliche Uferkante oder Wasserfläche erfinden.
- Status **beantragt erlaubt keine Entfernung**, auch nicht für eine
  vermeintlich unverbindliche Vorschau. Ohne Freigabe abbrechen und melden.
- Ausnahmen an FMI, Ebene, exakten Inhalt und Quellzustand binden.
  Ein Freigabefeld allein darf keine beliebigen anderen Flächen freigeben.
- Bereits korrigierte Eingaben unverändert akzeptieren. Geänderte,
  verschobene oder weitere Defekte ablehnen, bevor Ausgaben geschrieben werden.
- Gebäudeüberlappungen nur melden, niemals automatisch filtern.
- Bremen vollständig gültiges Umfeld: **1.351 Gebäude, 263 Straßen,
  59 Grünflächen, 3 Wasserflächen**.

## Licht, Dach und Quellen

- Bremen-Lichtfaktor **2,5** bereits in Fixture-Intensitäten eingerechnet:
  Quellwerte 25 → 62,5 bzw. 80 → 200. Nicht erneut multiplizieren.
- Zwölf Laufzeitquellen repräsentieren 63 dokumentierte Quellleuchten.
  Montageorte, Richtungen, Farben, Winkel, Reichweiten und Gruppen erhalten.
- Rasen und Linien sind nachts lesbar; die Gegentribüne bleibt sichtbar
  dunkler als die seitlichen Bereiche. Das ist kein Beleg für eine unabhängig
  geprüfte reale Lichtverteilung oder Dachabschattung.
- Dachtrennung geprüft: **58.109 Dachdreiecke**; keine Rang- oder
  Treppendreiecke versehentlich ausgeblendet. Betonfamilie front3_0…9
  bleibt Körper, front3_10…50 folgt Dach.
- Vier modellierte Flutlichtmasten und Tafeln samt Halterungen folgen Dach.
  Gästeblock-Fangnetz bleibt wie geliefert ausgeschlossen. Keine Neuverortung
  der historischen Gäste-Crowd und keine ungefragte Geometrieänderung.
- Original-Unity-Bundle fehlt hier: Binary-/Manifestprüfung nicht als
  neue unabhängige Bundle-Extraktion ausgeben.
- Fremde öffentliche Meldungen über aktuelle Sperrungen oder Schäden
  nicht ungeprüft als Produktzustand oder Modellkorrektur übernehmen.

## Übergabe

- Neue Ansichten mit aktuellem Projekt-Renderer und korrigiertem lokalem
  Umfeld erstellen; historische Paketbilder klar als Vorzustand kennzeichnen.
- Alte 2D-Blockreferenz bleibt für unveränderte Geometrie gültig; ihre
  öffentlichen Kapazitäts-/Zuteilungshinweise beschreiben nicht den lokalen Stand.
- Assets und Manifestkopien unverändert erhalten, vollständige Prüfsummen
  erneuern. Keine erneute Lichtkalibrierung erforderlich.
- Korrekturdokument und aktuelle Bilder definieren den neuen Paketstand.
- Private Backups, Sitzungen und Zugangsdaten nicht ins Paket.
- **Nicht erfolgt:** Registrierung, Assetupload, externe Serverübertragung,
  Veröffentlichung. Diese Schritte bleiben separat freizugeben.
