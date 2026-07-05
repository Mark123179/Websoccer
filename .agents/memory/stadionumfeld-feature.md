---
name: Stadionumfeld (Vereinsumfeld & Stadion-Szene)
description: Non-obvious gotchas for the Management-Hub "Stadionumfeld" 1:1 design-import scene (global singleton, admin rail, missing source assets, save whitelist).
---

# Stadionumfeld — 1:1 Design-Import-Szene

Management-Hub-Kachel `/management/stadionumfeld/`. Portierung des Replit-Design-Exports
"Vereinsumfeld und Stadion-UI" nach Django (vanilla JS class `VU` in
`game/static/game/js/stadionumfeld.js`, gescoptes CSS auf `.vu-page`).

## Globaler Singleton, nicht pro Verein
- Persistenz über `StadionumfeldConfig.get_solo()` (ein Datensatz für ALLE Vereine).
  Superuser-Edits im rechten Rail gelten global. Es gibt bewusst KEINEN Pro-Club-State.
- **Why:** Anforderung war eine globale, vom Admin kuratierte Szene, kein per-Manager-Zustand.

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
  im Bau-Zustand ist (nicht Default). Ebenso: Medizin nur Stufe-1-Bild vorhanden (1+/2/2+/3 folgen).
- **Why:** 1:1-Import — fehlende Vorlage-Assets NICHT fabrizieren; als echte Content-Lücke behandeln.

## JS-Class-Falle: Instanz-Property darf Methodennamen nicht überschatten
- Konstruktor setzte `this.mount = domEl`, was die Lifecycle-Methode `mount()` überschattete →
  `app.mount is not a function` beim Boot. Methode heißt jetzt `init()`. Bei Edits an der `VU`-Klasse
  keine Property so benennen wie eine Methode.

## State sicher ins Template
- State kommt via `{{ vu_state|json_script:"vu-state-data" }}` + `JSON.parse(...textContent)`,
  nicht via `{{ ...|safe }}` (verhindert `</script>`-Breakout, auch wenn nur Superuser schreiben).
