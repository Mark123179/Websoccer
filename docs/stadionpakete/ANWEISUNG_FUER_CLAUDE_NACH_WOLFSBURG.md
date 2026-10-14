# Neue Anweisung für Claude nach dem Wolfsburg-Review

Diese Anweisung ergänzt `ANWEISUNG_FUER_CLAUDE_NACH_FREIBURG.md`.
Weitere Pakete für die bestehende Registry vorbereiten, ohne vereinsspezifische
Änderungen am gemeinsamen Renderer.

## Wolfsburg: verbindliche Ergebnisse

- FMI **961**, VfL Wolfsburg, Volkswagen Arena.
- Heimkurve **NORD**, Haupttribüne **WEST**, Gegentribüne **OST**.
- Modellachsen: `+x OST`, `-x WEST`, `+z NORD`, `-z SUED`;
  `surroundingsAxes={"NORD":"+z","WEST":"-x"}`.
- Die lokale Kapazität ist **30.000**. Die 28.917 aus der öffentlichen
  Vorschau und die 31.334 Quellsitze sind keine Importwerte.
- Lokale Orientierungsmetadaten wurden mit Backup und Schutzvergleich
  korrigiert. Keine wirtschaftlichen Blockzuordnungen oder Plätze tauschen.
- Das Quellobjekt `bg.water[5]` hat nur zwei Punkte
  (`[-358.3,-223.3]`, `[-375.7,-150.5]`). Es ist keine darstellbare Fläche.
  Seine Entfernung ist für Wolfsburg ausdrücklich freigegeben und im
  Korrekturbeleg dokumentiert. Nicht durch eine erfundene Wasserfläche ersetzen.
- Dieser Befund betrifft auch den lokalen Bestand; eine bereinigte
  Paketvorschau allein behebt nicht die Anwendung.

## Keine Vorschau-Bereinigung als unveränderten Bestand ausgeben

- Ungültige Polygone führen normalerweise zum klaren Abbruch, nicht zum
  stillen Entfernen. Eine freigegebene Ausnahme muss Quelle, exakten Inhalt,
  Grund und betroffene Datenebenen nennen.
- Gebäudeüberlappungen nur melden. Keine Gebäude automatisch ausfiltern.
- Neue Bilder mit vollständigem **gültigem** Umfeld erstellen. Wolfsburg:
  90 Gebäude, 518 Straßen, 107 Grünflächen, 11 Wasserflächen.
- Alte Rohdaten und Bilder als historische Belege erhalten und kennzeichnen.
- Die Freigabe für Wolfsburg gilt nicht für andere Stadien oder Flächen.

## Licht und Dach

- Lichtkalibrierung bereits enthalten: **60 → 90, Faktor 1,5**.
  Nicht erneut multiplizieren; Freiburgs Faktor 8 gilt hier nicht.
- Zwölf Laufzeitquellen repräsentieren 141 dokumentierte Quellleuchten.
- Tag/Nacht und Flutlicht unabhängig prüfen, mit dem aktuellen Projektcode.
  Unterschiede in Rendererhashes untersuchen, nicht automatisch als
  funktionale Unterschiede oder als Gleichheit behandeln.
- Dachregel ist technisch geprüft: 79.359 Dachdreiecke, keine Ränge oder
  Treppen versehentlich im Dach. Bewusste Quellmesh-Kompromisse erhalten:
  Dachstützen, Fassaden-/Dachlogos und kleine Gitterroste folgen dem Dach.
- Fangnetze und Abspannung bleiben wie geliefert ausgeschlossen.
  Keine ungefragte Geometrieänderung aus dieser Korrektur ableiten.

## Reproduzierbarkeit und Übergabe

- Das korrigierte Vorschauwerkzeug darf nur die exakt dokumentierte,
  freigegebene Wolfsburg-Wasserfläche entfernen; bei Abweichungen abbrechen.
- Bereits korrigierte Eingaben erkennen. Andere degenerierte Polygone
  ablehnen; keine zweite oder allgemeine automatische Bereinigung.
- Original-/Browserwerte der Leuchten erhalten. Kalibrierungsskripte müssen
  neben Intensität auch stabile ID, Montageort, Richtung, Farbe, Reichweite,
  Winkel und Gruppierung gegen Quellen prüfen, bevor sie schreiben.
- Original-Unity-Bundle wurde hier nicht geliefert. Die Kontrolle des
  Exportbinarys ist keine unabhängige Neuprüfung der Bundle-Extraktion.
- Manifestkopien identisch halten; Assets und Prüfsummen vollständig liefern.
- Aktuelle 2D-Referenz, Editor, Ticker Dach an/aus, Nacht mit/ohne Flutlicht,
  Tag mit Flutlicht, Draufsicht und Gegenseite gemeinsam bereitstellen.
- **Nicht erfolgt:** neue Modellregistrierung, Assetupload, externe
  Serverübertragung oder Veröffentlichung. Diese Schritte separat freigeben.
- Private Datenbankbackups niemals in ein Übergabepaket aufnehmen.
