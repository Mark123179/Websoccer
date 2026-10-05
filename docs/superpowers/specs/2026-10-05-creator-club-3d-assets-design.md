# Freigegebene Erweiterung der Creator-Vereinsverwaltung

- Im bestehenden Bilder-Bereich zusätzliche PNG-Texturuploads für Home/Away/Third.
  Die vorhandenen 2D-Trikots und das Managerprofil bleiben unverändert.
- Öffentliche Pfade exakt `/static/game/images/3dkits/<FMI-ID>_<typ>.png`.
  Dauerhafte Speicherung unter ASSETS_ROOT/3dkits; nginx-Alias und Django-Finder
  bewahren diese URL ohne uploads in einem collectstatic-Build zu verlieren.
- PNG-Inhalt, Größe, Dimensionen und Lesbarkeit prüfen. Ungültige Uploads erhalten
  den Bestand. Gültige Uploads atomar ersetzen und die Vorschau cache-busten.
- Original und aktuelles Stadion als getrennte, schreibfreie 3D-Ansichten.
  Original nur bei tatsächlich vorhandener Originalquelle (derzeit Dortmund);
  aktuell aus gespeicherter Live-Scene, die abgeschlossene Ausbauten berücksichtigt.
  Laufende/geplante Ausbauten werden nicht angewandt. Fehlende Quellen klar melden,
  keine ersatzweise fremden Modelle.
- CMTracker-Vereins-ID nutzt das bestehende Datenbankfeld und den bestehenden
  Quellen-/ID-Speicherpfad. Vier IDs gemeinsam validieren und atomar speichern.
  Ein leerer Wert entfernt die ID. Kein automatisches Datenmatching oder Import.
- Schreibend nur Staff/Creator mit CSRF. Stadionviewer ebenfalls Staff-only.
  Keine Schemaänderung, Simulation, Wirtschafts- oder Ausbaubuchung.
- Prüfungen: Upload/Ersetzen/ungültige Datei, alle drei Typen, FMI-Zuordnung,
  Finder, Auth/CSRF, ID-Speichern/Leeren/Validierung, verfügbare und fehlende
  Modelle, tatsächlich geladene aktuelle Daten und unveränderte Originalquelle.
