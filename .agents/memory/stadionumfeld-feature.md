---
name: Stadionumfeld (Vereinsumfeld & Stadion-Szene)
description: Non-obvious gotchas for the Management-Hub "Stadionumfeld" 1:1 design-import scene (global singleton, admin rail, missing source assets, save whitelist).
---

# Stadionumfeld — 1:1 Design-Import-Szene

Management-Hub-Kachel `/management/stadionumfeld/`. Portierung des Replit-Design-Exports
"Vereinsumfeld und Stadion-UI" nach Django (vanilla JS class `VU` in
`game/static/game/js/stadionumfeld.js`, gescoptes CSS auf `.vu-page`).

## Zwei Datenquellen: globaler Singleton (Layout) + Pro-Club-Override (Levels)
- `StadionumfeldConfig.get_solo()` hält NUR NOCH Layout/Deko (badgePos, positions, day,
  heimspiel, tod, wetter, selected). Superuser-Edits im Rail gelten dafür global.
- `levels`/`capacity`/`building` sind KEIN Singleton-State mehr: `_build_club_scene_state(stadium)`
  in `views_management.py` liefert echte Pro-Verein-Werte (nlz/training, geschaeft=office_level,
  medizin, scouting=`ScoutingDepartment.level`, frei=0, capacity=capacity_total). Injektion via
  `{{ club_state|json_script:"vu-club-state-data" }}` → `window.__VU_CLUB_STATE__`; die `VU`-Klasse
  ÜBERSCHREIBT im Konstruktor `state.levels/building/capacity` hart aus diesem Objekt (nach dem
  Singleton-Merge, damit Club-Daten gewinnen). Diese Keys wurden aus `STADIONUMFELD_ALLOWED_KEYS`
  UND aus dem `_doSave()`-Payload entfernt → sie sind read-only, die Szene kann sie nicht mehr
  in den Singleton zurückschreiben.
- **Why:** Layout soll global/admin-kuratiert bleiben, aber die Facility-Stufen + Kapazität müssen
  die REALEN Daten des eingeloggten Vereins zeigen (Anforderung „alles verknüpfen").
- **How to apply:** Neue facility-/kapazitätsbezogene Werte in `_build_club_scene_state` ergänzen,
  NICHT in den Singleton/Save-Payload. Admin-Rail-Buttons (startBuild/finishBuild/advanceDay/
  setLevel) sind seitdem rein session-lokale Vorschau (persistieren nichts) — kein Bug, sondern
  Folge des entfernten Save-Pfads.

## Admin-Gate: Server ist die echte Grenze, Client nur kosmetisch
- `management_stadionumfeld` liefert `is_admin=request.user.is_superuser`; `stadionumfeld_save`
  prüft `is_superuser` erneut und gibt sonst 403. Der JS-`IS_ADMIN`-Flag blendet nur Rail/
  Drag/Handles aus (`save()` = no-op ohne Admin). Nie auf den Client-Flag als Sicherheit verlassen.

## Save-Whitelist = stiller Datenverlust bei neuen Keys
- `STADIONUMFELD_ALLOWED_KEYS` in `game/views_management.py` filtert den POST-Payload.
  Wird dem JS-State ein neuer top-level Key hinzugefügt, ohne ihn hier einzutragen, wird er
  beim Speichern **still verworfen** (Superuser-Edit persistiert nicht, ohne Fehler).
- **How to apply:** Jeder neue persistierte State-Key MUSS parallel in die Whitelist.

## Fehlende Quell-Assets sind ABSICHT (1:1-Import, nicht erfinden)
- `baufeld1.png` fehlt im Design-Export selbst (nur baufeld2–6 existieren). Das HTML referenziert
  es für die NLZ-Bauansicht → **404 beim JS-Preload ist erwartet/harmlos**, nur sichtbar wenn NLZ
  im Bau-Zustand/Stufe 0 ist (nicht Default). Alle übrigen Facility-Bilder (nlz/training/geschaeft/
  medizin/scouting/stadion inkl. Stufen 1–3 + „+"-Bauzustände) EXISTIEREN inzwischen — die frühere
  Notiz „Medizin nur Stufe-1" ist überholt (per 2026-07 alle medizin1/2/3 + plus-Varianten da).
- **Why:** 1:1-Import — fehlende Vorlage-Assets NICHT fabrizieren; als echte Content-Lücke behandeln.

## JS-Class-Falle: Instanz-Property darf Methodennamen nicht überschatten
- Konstruktor setzte `this.mount = domEl`, was die Lifecycle-Methode `mount()` überschattete →
  `app.mount is not a function` beim Boot. Methode heißt jetzt `init()`. Bei Edits an der `VU`-Klasse
  keine Property so benennen wie eine Methode.

## State sicher ins Template
- State kommt via `{{ vu_state|json_script:"vu-state-data" }}` + `JSON.parse(...textContent)`,
  nicht via `{{ ...|safe }}` (verhindert `</script>`-Breakout, auch wenn nur Superuser schreiben).
