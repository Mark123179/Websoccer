---
name: Französische Liga und ungeklärte Samba-Diop-Quellen
description: Vollständiger Ligue-1-Paketumfang, Workspace-Grenze und ausdrücklich freigegebene Identitätsquarantäne.
---

Die gelieferte Ligue 1 als komplette eigene Liga im Workspace behandeln,
zunächst nicht spielbar. Nicht anhand älterer realer Ligazugehörigkeiten
einzelne gelieferte Vereine ausschließen.

**Why:** Der Nutzer lieferte die Sammlung ausdrücklich „als komplette Liga“
und bestätigte den Import mit den besprochenen Quellen-Ausnahmen. Die
Arbeitsrichtung bleibt die additive Übernahme ohne Aktivierung des Spielbetriebs.

**How to apply:** Bestehende Ligen und Spielstände schützen. Weder Saison
noch Spielplan für die neue Liga initialisieren oder Produktion ändern.

Die beiden Samba Diop aus Brest und Lorient sind getrennte Spieler.
Ihre ungeklärte gemeinsame FMInside-Zuordnung vorläufig bei beiden sperren;
die betroffenen FM-Werte dürfen nicht in die Stärke einfließen.

**Why:** Der Nutzer wählte ausdrücklich „Beide vorläufig sperren, Liga
importieren“. Gleichnamigkeit ist keine Freigabe für eine Zusammenführung
oder die Bevorzugung einer der beiden Quellen.

**How to apply:** Originalpakete unverändert als Beleg erhalten und die
bereinigte Importfassung getrennt kennzeichnen. Eine erneute Lieferung
derselben strittigen Zuordnung ist keine fachliche Klärung und keine
Freigabe zur Aufhebung der Einzelsperren.

Für Lorient liegt inzwischen ein belastbarer externer FM-Identitätsbeleg vor;
für Brest fehlt weiterhin eine eigene belegte FM-Zuordnung. Die ursprüngliche
gemeinsame Quarantäne ist damit nicht mehr gleichbedeutend mit einer bei
beiden gleichermaßen ungeklärten Identität. Quellenbericht:
`docs/import-pilot/samba-diop-identity-resolution.md`.

**Why:** Das direkt gelesene Sortitoutsi-FM26-Profil verknüpft die strittige
Unique-ID mit vollständigem Geburtsdatum und Lorient. Das FM-Spielstartalter
ist dagegen kein verlässlicher Vergleich zum Alter am späteren Importtag.

**How to apply:** Vor einer Übernahme den Bericht und den tatsächlichen
Workspace-Bestand prüfen. Ein fachlicher Identitätsnachweis ist kein
Nachweis einer bereits erfolgten Datenbankkorrektur. Brest nicht automatisch
mit freigeben; CMTracker nicht mitprojizieren.
