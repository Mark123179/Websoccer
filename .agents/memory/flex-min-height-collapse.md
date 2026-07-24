---
name: Flex-Kollaps bei min-height-Containern
description: Warum flex:1-Kinder in Containern mit nur min-height (ohne height) unsichtbar kollabieren können — Sponsoring-Artboard-Bug.
---

# Flex-Kollaps: `flex:1` in Container mit nur `min-height`

**Regel:** In einem `display:flex; flex-direction:column`-Container, der nur `min-height` (kein explizites `height`) hat, darf ein Kind NICHT `flex:1` bekommen, wenn es sichtbaren Inhalt tragen soll. Artboard-Seiten (`.dashboard-artboard`) im Websoccer nutzen stattdessen simples Block-Layout: `min-height:960px; background:…` auf dem Artboard, normale Blocks/Grids darin.

**Why:** `flex:1` = `flex:1 1 0` → `flex-basis:0`. Ohne definiertes `height` gibt es keinen verteilbaren Flex-Raum, das Kind bleibt effektiv bei 0px Höhe — Inhalt unsichtbar, obwohl er im DOM steht und CSS lädt. Der Sponsoring-Seiten-Bug (Juli 2026): Seite komplett dunkel unter dem Kalender, obwohl HTML/CSS/JS korrekt; ein Inline-Diagnose-Div mit `z-index:999` war sichtbar, der `flex:1`-Wrapper nicht.

**How to apply:** Bei "Seite rendert nichts, aber DOM/CSS ok" zuerst prüfen: Ist der unsichtbare Container ein Flex-Kind mit `flex:1` in einem Container ohne explizites `height`? Referenz-Muster: `job-angebote.css` / `management-hub.css` (Block bzw. row-flex mit absolut positioniertem BG).

**Diagnose-Trick (bewährt):** Temporär `@login_required` entfernen + Bayern-Fallback für `club`, oder temp `/dev-login-tmp/`-View (force login + redirect) — dann sieht das Screenshot-Tool die echte eingeloggte Seite. Danach IMMER zurückbauen (Decorator rein, Temp-View/URL löschen, mit anonym-302 + 404 verifizieren).
