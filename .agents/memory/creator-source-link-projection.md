---
name: Creator-Source als ID-Projektion
description: Freigegebene rein lesende Ableitung von Profil-Links aus den kanonischen Spieler-IDs im Paketmodus.
---

Im Paketmodus stammen die drei Source-Identitäten aus der kanonischen ID-Tabelle, nicht aus Spieler-Spiegelfeldern oder Rating-Adressen. Fehlende Profil-Links dürfen rein für die Anzeige aus vorhandenen IDs abgeleitet werden; IDs und Adressen bleiben in dieser Ansicht schreibgeschützt.

**Why:** Der Nutzer hat die Anzeige aller drei IDs und die Ableitung fehlender Links ausdrücklich freigegeben, ohne Quelldaten zurückzuschreiben.

**How to apply:** Gespeicherte Profil-/Quelladressen bevorzugen. Abgeleitete Adressen kennzeichnen und niemals bei einem Formular-Save als neue Quellwerte persistieren. Keine fehlenden IDs aus Altspalten erraten. Altmodus unverändert lassen.

Versionsunabhängige FMInside- und CMTracker-Links führen zur aktuellen Quell-Datenbank, nicht zwingend zum historischen importierten Ratingstand.

**Why:** Das vermeidet erfundene oder fest eingefrorene Datenbankversionen. Der öffentliche CMTracker-Pfad `/en/players/<ID>` wurde für Kobel bestätigt.

**How to apply:** Den Unterschied in der Source-Ansicht erklären; gespeicherte Ratingwerte nicht beim Anzeigen oder Öffnen eines Links aktualisieren.
