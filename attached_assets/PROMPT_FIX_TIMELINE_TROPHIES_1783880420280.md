# Korrektur-Prompt für Replit — Timeline & Trophäensammlung exakt nachbauen

Wichtig vorab: Die Referenzdatei `design_reference/Managerprofil.dc.html` ist **kein 1:1 kopierbares HTML** — sie ist ein Design-Tool-Format mit Template-Platzhaltern (`{{ … }}`) und einer JS-Logikklasse am Dateiende. Du musst Markup/JS nativ in Django-Template + Vanilla-JS nachbauen, aber **alle Inline-Style-Werte wörtlich übernehmen**. Maßgeblich ist ausschließlich der Frame `data-screen-label="2a FM Broadcast v2 — Managerprofil"`.

Korrigiere jetzt exakt Folgendes:

---

## A) Karriere-Timeline — aktuell falsch, bitte komplett nach dieser Spezifikation

1. **Zeit-Domäne fixieren.** t0 = 2023-07-15, t1 = 2026-08-20 (Karrierebeginn bis kurz nach heute). **Entferne die Jahres-Ticks 2010/11 … 2022/23 komplett.** Auf der Achse gibt es nur:
   - 3 klickbare Saison-Labels: `2023/24`, `2024/25`, `2025/26` — je zentriert auf der Saisonmitte, 10px/900/+1,1px, Farbe rgba(244,251,255,.5), Hover cyan, Position unten im Track (bottom:5px).
   - den **HEUTE-Marker** am aktuellen Datum: vertikale gestrichelte Linie `2px dashed rgba(34,230,255,.32)` + Pill auf der Achse (`background:#22e6ff; color:#061018; font:900 9px; border-radius:999px; padding:4px 9px; box-shadow:0 0 18px rgba(34,230,255,.55)`).

2. **Track-Geometrie.** Scroll-Container (`overflow-x:auto; overflow-y:hidden`), innerer Track: `width:2900px; height:352px; position:relative`. Achse: absolute, `top:50%`, `height:2px`, `background:linear-gradient(90deg, rgba(44,231,255,.06), rgba(44,231,255,.42) 10%, rgba(44,231,255,.42) 90%, rgba(44,231,255,.06))`. Die Kopfzeile (Titel + Filter + Buttons) ist eine **eigene Zeile über dem Track** — Karten dürfen sie niemals überlappen.

3. **Positionslogik (JS, exakt so):**
   ```js
   const t0 = Date.parse('2023-07-15'), t1 = Date.parse('2026-08-20');
   const padL = 56, padR = 96, cardW = 234, gap = 16, baseW = 2900;
   const X = t => padL + (Date.parse(t) - t0) / (t1 - t0) * (baseW - padL - padR);
   // Events chronologisch sortieren; Index gerade => Spur OBEN, ungerade => UNTEN
   // Anti-Kollision je Spur: x = Math.max(x, xPrev + cardW + gap)
   ```
   Spur oben: Wrapper `position:absolute; left:Xpx; bottom:50%; width:234px` (Karte, darunter Stiel). Spur unten: `top:50%` (Stiel, darunter Karte). Stiel: `width:2px; height:20px; margin-left:25px; opacity:.55` in Tonfarbe. Achsenpunkt: 9px-Kreis mit `box-shadow:0 0 12px <Tonfarbe>` bei `left:X+26`.

4. **Event-Karte (234px) — exakte Struktur:**
   - Kopfzeile (flex, gap 7px): Icon-Chip `20×20, border-radius:5px` (SVG 11–12px) + Kategorie-Label `9px/900/+1px` + Datum rechts (`margin-left:auto`, 9,5px/700).
   - Titel `13px/900/1.2` (margin-top 7px) · Beschreibung `10,5px/600/1.45` mit `margin-right:40px`.
   - Vereinswappen `30×30` absolut unten-rechts (`right:10px; bottom:8px`) mit `drop-shadow(0 2px 8px rgba(0,0,0,.6))` — **fehlt aktuell, ergänzen.**
   - `border-radius:8px; padding:10px 12px 12px; border:1px solid <Ton 50 %>; box-shadow:0 12px 34px <Ton 12–16 %>`.

5. **SOLID-Farbflächen statt dunklem Glas** (derzeit falsch — die Karten sind dunkel mit kleinem Farb-Chip):
   | Kategorie | background | Textfarbe |
   |---|---|---|
   | TITEL, HISTORIE | `linear-gradient(165deg, #ffd166, #e0a034)` | `#061018` (Beschreibung `rgba(6,16,24,.75)`) |
   | VEREIN, LIGA | `linear-gradient(165deg, #4fe9ff, #149dc0)` | `#061018` |
   | JUGEND, aktuelles Amt | `linear-gradient(165deg, #54f5ad, #17b06c)` | `#061018` |
   | FINALE verloren, ENTLASSUNG/STATUS | `linear-gradient(165deg, #ff6d84, #c22e46)` | `#fff` (Beschreibung `rgba(255,255,255,.85)`) |

   Icon-Chip auf Solid-Karten: `background:rgba(6,16,24,.22); color:#061018` (bei Rot: weiß).

6. **Daten säubern:** Keine Karte ohne Titel/Datum rendern (aktuell gibt es links eine leere Mini-Karte und Karten mit „–"). Titel-Events brauchen ein echtes Datum (Verleihdatum aus der DB), nicht „–". Amtsantritt-Karten: „Übernahme von <Verein> — bis <Datum>" bzw. „— aktuell im Amt" (grün).

7. **Saison-Zoom:** Klick auf ein Saison-Label ⇒ Domäne = diese Saison (01.07.–30.06.), `baseW = 1256`, Ticks = Monats-Labels Jul…Jun (nicht klickbar), in der Kopfzeile erscheint ein goldener Reset-Chip `SAISON 2024/25 ✕` (Pill, `border:1px solid rgba(255,209,102,.5); background:rgba(255,209,102,.12); color:#ffd166`). Klick auf ✕ ⇒ zurück zur Gesamtansicht.

8. Filter-Chips bleiben: ALLE · VEREIN · TITEL · FINALE · JUGEND · STATUS (aktiv: `background:rgba(34,230,255,.16); border-color:rgba(44,231,255,.55); color:#22e6ff`). Nach Filterung Positionen neu berechnen.

---

## B) Trophäensammlung — aktuell falsch, bitte exakt so

- Karte in der linken Spalte (336px), Kopf: `TROPHÄENSAMMLUNG` (11px/900/+1px, --muted) + Link „Alle ansehen" (cyan, 10px/800).
- **Grid: `display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; padding:14px 16px 16px;`** — bei mehr als 3 Trophäentypen entstehen automatisch weitere 3er-Reihen. Kein einzelner Slot in eigener voller Breite (derzeit hängt der 4. Slot allein darunter).
- Slot (flex column, zentriert, gap 6px):
  1. Wettbewerbslogo `54×54, object-fit:contain` mit `filter:drop-shadow(0 0 14px rgba(255,209,102,.28))` — **Logos in Originalfarbe, nicht ausgegraut/desaturiert** (aktuell wirken sie grau).
  2. Zähler-Pill: `padding:2px 8px; border-radius:999px; background:linear-gradient(180deg, #ff9f1c, #d85d00); color:#fff; font:900 9px` — Format `5×` (Multiplikationszeichen ×, kein „x"). Derzeit ist die Pill weiß/farblos — falsch.
  3. Name + Jahr: `9,5px/700, color:var(--muted), text-align:center`, zweizeilig (z. B. „Bundesliga" / „2025").

---

## C) Kleinere Abweichungen in der KPI-Leiste

- **SIEGQUOTE-Zelle:** unter dem Wert einen gestapelten Balken ergänzen: `display:flex; height:5px; border-radius:999px; overflow:hidden` mit drei Segmenten in Sieg-/Unentschieden-/Niederlagen-Anteilen (`#30f29c`, `rgba(244,251,255,.3)`, `#ff5570`), darunter „65 S · 24 U · 30 N" (9px/700 faint, echte Werte).
- **TROPHÄEN-Zelle:** Zahl 21px/900 cyan + daneben 3 Mini-Wettbewerbslogos `18×18` (farbig) + Link „Alle ansehen".
- **HIGHSCORE-Zelle:** nie leer — Wert 21px/900 in `#ffd166`, darunter grüner Trend (falls vorhanden) und „Platz <n>"; ohne Daten `–` + „Platz –".
- **MANAGERLEVEL:** Level-Chip 32×32 (Cyan-Box), daneben zweizeilig „NÄCHSTES / LEVEL: <n+1>", darunter XP-Bar 5px (Cyan-Gradient + Glow) + „<xp> / <next> XP".

Teste danach: 1) keine Jahres-Ticks vor 2023, 2) Karten überlappen die Kopfzeile nicht, 3) Titel-Karten sind vollflächig gold mit dunklem Text und Wappen unten rechts, 4) Trophäen-Grid 3-spaltig mit orangenen Zähler-Pills, 5) Saison-Zoom + Reset-Chip funktionieren.
