---
name: Stadionumfeld (Vereinsumfeld & Stadion-Szene)
description: Non-obvious gotchas for the Management-Hub "Stadionumfeld" scene — global layout singleton vs. real per-club levels, REAL wall-clock facility construction (FacilityConstruction), admin rail vs. manager rail, missing source assets, save whitelist.
---

# Stadionumfeld — 1:1 Design-Import-Szene

Management-Hub-Kachel `/management/stadionumfeld/`. Portierung des Replit-Design-Exports
"Vereinsumfeld und Stadion-UI" nach Django (vanilla JS class `VU` in
`game/static/game/js/stadionumfeld.js`, gescoptes CSS auf `.vu-page`).

## Zwei Datenquellen: globaler Singleton (Layout) + Pro-Club-Override (Levels)
- `StadionumfeldConfig.get_solo()` hält NUR NOCH Layout/Deko (badgePos, positions, day,
  heimspiel, tod, wetter, selected). Superuser-Edits im Rail gelten dafür global.
- `levels`/`capacity`/`building`/`budget`/`facilities` sind KEIN Singleton-State: `_build_club_scene_state(club, stadium)`
  in `views_management.py` liefert echte Pro-Verein-Werte (nlz/training, geschaeft=office_level,
  medizin, scouting=`ScoutingDepartment.level`, frei=0, capacity=capacity_total, budget, plus je
  Einrichtung eine `facilities`-Meta mit Kosten/Bauzeit/affordable/can_upgrade/is_building/tiers).
  Injektion via `{{ club_state|json_script:"vu-club-state-data" }}` → `window.__VU_CLUB_STATE__`; die
  `VU`-Klasse ÜBERSCHREIBT im Konstruktor `state.levels/building/capacity` hart aus diesem Objekt und
  legt `clubFacilities/clubBudget(_fmt)` für die Manager-Rail an. Diese Keys sind NICHT in
  `STADIONUMFELD_ALLOWED_KEYS`/`_doSave()` → read-only, die Szene schreibt sie nie in den Singleton.
- **Why:** Layout global/admin-kuratiert; Stufen/Kapazität/Budget/Ausbau müssen die REALEN Daten des
  eingeloggten Vereins zeigen (Anforderung „alles verknüpfen").
- **How to apply:** Neue facility-/kapazitätsbezogene Werte in `_build_club_scene_state` ergänzen,
  NICHT in den Singleton/Save-Payload. WICHTIG: Der ADMIN-Rail (startBuild/finishBuild/advanceDay/
  setLevel) ist rein session-lokale Vorschau (persistiert nichts). Der MANAGER-Rail (Nicht-Admin,
  `buildManagerRail`/`doUpgrade`) ist der ECHTE Ausbau-Pfad → siehe „Echter Ausbau" unten.

## Echter Ausbau (Wanduhr-Bauzeit) — FacilityConstruction
- Manager-Ausbau (`facility_upgrade`, POST `/management/stadion/einrichtung-ausbauen/`): Geld wird
  SOFORT abgebucht + ein `FacilityConstruction`-Auftrag (status=active, started_at/completes_at)
  angelegt; die Stufe bleibt ALT während der Bauzeit (Szene zeigt „+"-Zustand). Stufe steigt + Boni
  greifen ERST bei Ablauf via `resolve_due_constructions(club)`.
- `resolve_due_constructions()` läuft lazy am Anfang von `management_hub`, `management_stadionumfeld`
  UND `facility_upgrade`. Es „claimt" jeden fälligen Auftrag per bedingtem UPDATE (active→done) und
  hebt `Stadium.<facility>_level` nur bei erfolgreichem Claim + `aktuell < target_level` (absoluter
  Set, kein Increment → idempotent, kein Doppelhochstufen bei parallelen Requests).
- Concurrency-Invariante: Geld über `Club.select_for_update()` als EINZIGE Serialisierungsstelle;
  „bereits im Bau" NACH dem Lock via `exists()`; partielle Unique-Constraint
  `(club, facility) WHERE status='active'` + `IntegrityError`-catch als Backstop. Der Resolver nimmt
  BEWUSST keinen Row-Lock (Lock-Reihenfolge). PFLICHT: `stadium.refresh_from_db()` NACH dem Club-Lock
  (der lock-freie Resolver kann zwischen Refresh und Lock die Stufe angehoben haben → sonst stiller
  Geldverlust).
- Frontend rechnet NIE mit Geld: `affordable`/Kosten kommen serverseitig; der „Ausbauen"-Button postet
  nur `facility` (+ CSRF). Scouting/frei/stadion sind `upgradeable:false` → `meta.note` („folgt noch"),
  aber generisch designt (`FacilityConstruction.facility` ist ein freier Key).
- FACILITY_MAX_LEVEL=3; `FACILITY_FIELD_MAP` (js-id→Stadium-Feld) und `FACILITY_SRV_TO_JS`
  (server→js, office→geschaeft) sind Modul-Konstanten in `views_management.py`.

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
