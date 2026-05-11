# Websoccer Visual Asset Agent

## Zweck

Der Visual Asset Agent ist die wiederverwendbare Projektrolle fuer alle grafischen Aufgaben im Websoccer:

- UI-Icons
- Sidebar- und Navigationssymbole
- Badges, Statussymbole und kleine Piktogramme
- Dashboard-Illustrationen
- Platzhaltergrafiken
- Wappen-, Kit-, Flaggen- und Spielerbild-Aufbereitung
- spaetere Stadion-, Stadt- und Wettbewerbsbilder

Ziel ist ein konsistenter, hochwertiger Manager-Dashboard-Look.

## Stilrichtung

Der aktuelle Zielstil:

- dunkles Manager-Dashboard
- sportlich, technisch, hochwertig
- cyan/PlayStation-Blue Akzente
- klare Kanten, wenig Dekoration
- Icons mit einheitlicher Strichstaerke
- keine zufaellig zusammengewuerfelten Icon-Stile

Die Referenz ist eine Mischung aus:

- moderner Football-Manager-/Websoccer-Oberflaeche
- dunklem Dashboard mit Neon-Cyan-Akzenten
- PlayStation-inspirierter Klarheit bei Flaechen, Pill-Buttons und 8px-Panels

## Asset-Quellen

### Lokale Pflichtassets

Diese Asset-Typen werden lokal ueber IDs zugeordnet:

- Spielerbilder
- Vereinswappen
- Flaggen
- Nationenlogos
- Kits
- Trophies
- spaeter Stadion- und Stadtbilder

Die bestehende lokale Struktur liegt unter:

```text
C:/Users/mashu/Documents/Codex/Websoccer/Images/
  2D Kits/
  Flaggen/
  Nationen/
  Players/
  Trophies/
  Wappen/
```

### Externe Assets

Externe Assets duerfen verwendet werden.

Wichtig: Wenn ein Fremdasset genutzt wird, muss es sichtbar dokumentiert werden:

- Quelle/URL
- Asset-Name
- Lizenz oder Nutzungsstatus, falls erkennbar
- Datum der Uebernahme
- Einsatzort im Projekt

Fuer allgemeine Logos und Icon-Recherche ist `https://api.svgl.app` bevorzugt.

## Asset-Log

Fuer externe oder manuell uebernommene Assets wird ein Asset-Log gepflegt:

```text
ASSET_LOG.md
```

Empfohlenes Format:

```md
## <Asset-Name>

- Quelle:
- Lizenz/Nutzungsstatus:
- Lokaler Pfad:
- Einsatzort:
- Uebernommen am:
- Hinweise:
```

## SVG-Regeln

UI-Icons sollen bevorzugt als echte SVGs gebaut werden:

- klare `viewBox`, meistens `0 0 24 24`
- `currentColor` fuer Stroke/Fill, wenn das Icon im UI gefaerbt werden soll
- einheitliche Strichstaerke, bevorzugt `1.75` oder `2`
- keine eingebetteten Rasterbilder fuer reine UI-Icons
- keine unnoetigen Metadaten
- sprechende Dateinamen

Bildassets duerfen als SVG-Wrapper um lokale PNGs/JPGs existieren, wenn das dem aktuellen Asset-System hilft.

## Namenskonventionen

Empfohlene Pfade im Django-Projekt:

```text
game/static/game/images/icons/<name>.svg
game/static/game/images/players/<player_fm_inside_id>.svg
game/static/game/images/crests/<club_fm_inside_id>.svg
game/static/game/images/kits/<club_fm_inside_id>_<home|away|third>.svg
game/static/game/images/flags/<nation_id>.svg
game/static/game/images/trophies/<trophy_id>.svg
```

## Erste Icon-Aufgabe

Sidebar-Iconset fuer:

- Uebersicht
- Kader
- Taktik
- Training
- Transfers
- Scouting
- Jugend
- Finanzen
- Verein
- Mitarbeiter
- Wettbewerbe
- Posteingang
- Einstellungen

Alle Icons sollen als konsistentes Set funktionieren:

- 24x24 SVG
- cyan faerbbar via `currentColor`
- dunkles Dashboard geeignet
- gleiche optische Groesse
- gleiche Linienlogik

## Arbeitsweise

Bei jedem Grafikauftrag:

1. Zweck und Einsatzort klaeren.
2. Bestehende lokale Assets pruefen.
3. Externe Assets nur nutzen, wenn sie passen und dokumentierbar sind.
4. Einheitliche Dateinamen und Pfade verwenden.
5. UI nach Einbindung im Browser pruefen.
6. Aenderung als eigenen Git-Schritt committen.
