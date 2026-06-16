---
name: Club import name confirmation
description: How a manually-named new import club later gets its name confirmed from the Transfermarkt-detected name, and why the provisional flag gates it.
---

# Creator-Import: vorläufiger Vereinsname → TM-Bestätigung

Beim Modus „Neuen Verein anlegen" gibt der Admin den Namen manuell ein. Dieser
ist nur vorläufig und wird später durch den von Transfermarkt erkannten
Kadernamen bestätigt/aktualisiert.

## Regel
- `create_or_promote_target_club` setzt `Club.import_name_provisional = True` bei
  **created** UND **promoted**.
- Der lokale Importer erfasst den Kader-Header-Vereinsnamen
  (`TransfermarktAdapter.squad_club_name`, Selector `h1.data-header__headline-wrapper`)
  und sendet ihn beim `complete`-Aufruf als `tm_club_name`.
- `importer_complete` speichert `tm_club_name` am Job und benennt `Club.name`/
  `short_name` **nur dann** um (und löscht das Flag), wenn `import_name_provisional`
  True ist — alles in einem `transaction.atomic()` mit Lease-Lock.

**Why:** Der Befüll-Modus („Bestehenden Verein") nutzt einen vom Admin gewählten
echten Verein (Flag bleibt False) — der darf NIE umbenannt werden. Das Flag ist
die einzige zuverlässige Unterscheidung zwischen „frisch angelegt, Name vorläufig"
und „bestehend, Name final".

**How to apply:** Bei Änderungen am complete-Pfad oder am Anlegen/Hochstufen das
Flag korrekt mitführen. Fehlender/leerer `tm_club_name` ist no-op
(rückwärtskompatibel mit älteren Importern) — diese Nicht-Destruktivität ist Teil
des Vertrags und muss erhalten bleiben.
