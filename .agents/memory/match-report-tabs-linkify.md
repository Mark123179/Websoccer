---
name: Spielbericht-Tabs per URL-Hash + Linkify-Muster
description: Screenshot-Verifikation einzelner Spielbericht-Tabs via #hash; sicheres Namens-Verlinken im Ticker-Kommentar.
---

## Tab-Navigation per URL-Hash
`match_report_v2.js` liest `window.location.hash` beim Laden und aktiviert den passenden Tab.
**How to apply:** Screenshots einzelner Tabs ohne Klick-Interaktion: `/matches/<id>/report/#aufstellungen`, `#statistik`, `#ticker`, `#spieler`. `match_report_by_id` hat kein `@login_required` → Screenshot-Browser (ausgeloggt) kann direkt zugreifen (sieht Nicht-Admin-Ansicht).

## Sicheres Namens-Verlinken in Kommentartexten (_linkify_commentary)
Regel: Text zuerst `escape()`n, Spielernamen identisch escapen, dann Regex-Ersetzung mit `\w`-Lookarounds und **längsten Namen zuerst**; erst das fertige Ergebnis `mark_safe()`.
**Why:** Entities (z. B. `O&#x27;Neill`) müssen auf beiden Seiten übereinstimmen, sonst matcht der Name nicht; ungeescapter Input + mark_safe wäre XSS.

## Bedingte Link-Wrapper bei Altdaten
Alte Berichte haben keine Spieler-IDs → Zeilen als `{% if x.id %}<a…{% else %}<div…{% endif %}` mit symmetrischem Schließ-Block rendern, nie hart verlinken.
