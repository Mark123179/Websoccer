# Websoccer Design System — "MatchEngine"

A complete design system for **Websoccer**, a premium AAA football-manager
browser game (product/brand mark: **MatchEngine**). The product is a German
Django web app where the player takes over a Bundesliga club and runs squad,
tactics, finances and the season simulation. The UI is a **dark "football
command center"**: a stadium-dark app shell, glass panels lined in cyan, green
reserved for pitch/fitness/positive values, and dense, scannable manager data.

> **Locked golden master:** the product targets a fixed **1440×900** (logical
> wide-shell up to ~1884px). It is a single-product app (no separate marketing
> site) with all-German UI copy.

## Sources

This system was reverse-engineered from the project's own code and assets:

- **GitHub:** `https://github.com/Mark123179/Websoccer` (branch `main`) — Django
  app under `core/` (config) and `game/` (all game logic, templates, static CSS
  and images). The visual system was lifted from
  `game/static/game/css/global-dashboard/*` and `game/templates/base.html`;
  brand/club/player assets from `game/static/game/images/*`; design intent from
  the repo's own `DESIGN.md`, `PROJEKTKONTEXT.md` and `DATEN_UND_ASSETS.md`.
- **Reference baseline screenshots** (in `_reference/` was deleted; originals in
  `screenshots/`): `overview_baseline.jpg`, `player_baseline.jpg`,
  `calendar_after.jpg` — the ground-truth renders the UI kit was matched to.
- The product cites two inspiration sites (not copied): `websoccer.ch`,
  `champions-football-manager.de`.

Reader with repo access: explore the URLs above to build higher-fidelity work —
especially `game/static/game/css/` for the full component CSS and
`game/templates/game/` for screen markup.

---

## CONTENT FUNDAMENTALS

**Language.** The entire product UI is in **German**. Labels, nav, buttons,
data headers — all German. Keep it that way: *Übersicht, Verein, Kader, Taktik,
Transfers, Jugend, Datencenter, Management, Community, Spielvorschau,
Spielbericht anzeigen, Anmelden, Abmelden.*

**Tone.** Two registers coexist:

- **Data/UI chrome — terse, factual, manager-grade.** Short uppercase
  micro-labels (FINANZEN, VEREINSWERT, ZUSCHAUER, NÄCHSTES SPIEL), compact
  figures with German number formatting (`205.000.000 €`, `938.950.000 €`,
  thousands `.`, decimals `,`). No fluff.
- **Personality — warm, hyped, footy-mate.** The in-app assistant **"KI-Kloppo"**
  (a Klopp-style coach) talks like an excited friend: *"Boah, endlich bist du
  da, Chef!"*, *"We go again!"*, *"Wahnsinn! Ich hab auf dich gewartet,
  Freund!"*. This is the brand's emotional layer — use it for greetings,
  empty-states and celebrations, never for data labels.

**Person.** Addresses the manager directly and informally — **"du" / "Chef" /
"Freund"**, never formal "Sie". The player *is* the manager.

**Casing.** Card/section titles are **UPPERCASE + tracked** (`VEREINSÜBERSICHT`).
Body and values are sentence/number case. Buttons are Title-case German.

**Emoji.** Used **sparingly and only in the personality layer** — Kloppo's
speech, chat lines (`👀`, `⚽`). Never in data tables, KPI labels or nav.

**Examples of real copy:** "Saisonvorbereitung · Creator Mode" (header
subtitle), "0 heute online" (presence), "Top-Torjäger · H. Kane · 18 Tore",
"Frische — Sehr frisch", "27. Spieltag", single-letter form codes **S/U/N**
(Sieg/Unentschieden/Niederlage = win/draw/loss).

---

## VISUAL FOUNDATIONS

**Colour & light.** Near-black stadium base (`#03070c` → `#07111a`) under
translucent **glass panels** (`rgba(9,23,34,.82)`). **Cyan `#22e6ff` is
functional light** — borders, accents, focus, KPI values, links — *not*
decoration. **Green `#30f29c` is sport-positive** — fitness, pitch, form,
market value, profit. **Yellow `#ffd166`** = caution / yellow card, **red
`#ff5570`** = danger / loss, and an **orange gradient** (`#ff9f1c→#d85d00`) is
reserved for count badges and the Creator-Mode button. Text is a cool near-white
`#f4fbff`, stepping down through `--muted` (64%) to `--faint` (38%) uppercase
micro-labels.

**Backgrounds — gradients, not photos.** The atmosphere is built from layered
CSS: a diagonal near-black base, a **cyan flood-light from the top-right**, a
**green pitch-glow from the bottom-left**, and a faint **fixed 56px engineering
grid** behind everything. Screens add a white "stadium-light" bloom at the top
edge and faint vertical "floodlight" stripes. Photographic backgrounds (real
stadium/pitch shots) exist in `assets/backgrounds/` for hero contexts but the
core shell is pure gradient. Imagery vibe: cool, electric, night-match — never
warm or sepia.

**Type.** One family — **Inter** — carries everything; hierarchy comes from
**weight and size**, not a second face. The UI runs **bold by default (700)**;
headings, KPI values, badges and VS marks are **black (900)**. Micro-labels are
12px / 900 / uppercase / +0.7px tracking. No serif, no display face.

**Spacing & shape.** Compact and dense: **16px** gap between cards, **18px**
card padding, **44px** page outer padding. **One 8px radius** on virtually
everything (cards, buttons, inputs, chips); **999px pills** only on badges,
status dots and progress tracks; **4px** on tiny calendar tiles.

**Cards.** Glass panel = translucent dark fill + **1px cyan hairline**
(`--line`) + **soft 70px drop shadow** (`--shadow`). Hero/VS/match cards add a
top-right white spec gradient. **Never nest a card inside a card.** Tables stay
compact with image columns and position badges.

**Borders, shadow & glow.** Hairlines are cyan at 18% opacity, lifting to 38%
(`--line-strong`) on hover/active. Depth is one big soft black shadow plus a
**cyan halo glow** (`--glow`) on crests, the brand mark and focused inputs.
Crests carry a `drop-shadow(0 0 18px cyan/28%)`.

**States.** *Hover* — lift border to `--line-strong`, brighten fill toward
`--cyan-soft`, icons gain a stronger cyan glow. *Active/press* — a 1px
`translateY` nudge on buttons. *Focus* — cyan ring + soft glow. *Active nav* —
cyan gradient fill, `--line-strong` border, **inset 3px cyan left bar** + a
glowing icon. *Selected table row* — faint cyan wash. Status changes (calendar
ready/open) use **inset box-shadow** rather than border width, to avoid layout
shift.

**Motion.** Restrained: 0.15s ease colour/border/background transitions, a tiny
press nudge. The only expressive animation is **KI-Kloppo's bounce-in + speech
bubble** after login. No infinite decorative loops, no parallax.

**Transparency & blur.** Panels are translucent over the gradient; calendar
arrows use `backdrop-filter: blur(12px)`. Used to make glass read as glass — not
as gratuitous frost.

**Layout rules (from the product's own contract).** Every main screen sits in a
fixed wide shell: a **232px fixed left sidebar** + a content artboard
(`shell − sidebar`). No `100vw` artboards, no per-page max-widths, no nested
scalers. Horizontal scroll only with cause. Dashboard bodies are multi-column
fraction grids (e.g. `1.25fr 0.95fr 0.9fr 0.8fr`).

---

## ICONOGRAPHY

Two icon systems ship in `assets/icons/`:

1. **Sidebar line icons** (`assets/icons/sidebar/*.svg`) — the primary set.
   Clean **24×24, `currentColor`, ~1.9 stroke** outline icons (übersicht,
   verein, kader, taktik, transfers, jugend, finanzen, scouting, training,
   mitarbeiter, wettbewerbe, einstellungen, handbuch, posteingang). Because they
   use `currentColor`, tint them via CSS `color`. This is what the baseline
   screenshots use, and what the UI kit reproduces (inlined in `icons.js` so the
   stroke can pick up `currentColor`). **Prefer this set.**
2. **Glowing nav PNGs** (`assets/icons/nav-*.png`) — an alternate, richer set:
   large raster icons rendered with a cyan drop-shadow glow, used in a variant
   of the sidebar. Heavier; use only when you specifically want the glow look.

There is **no icon font**. Unicode is used as light glyphs in the personality
layer only (`⚽`, `→`, chevrons drawn as CSS borders). When you need an icon the
set doesn't cover, draw a **24px / currentColor / ~1.9 stroke outline** SVG to
match — or pull the matching Lucide icon (same outline weight). Do **not**
introduce filled/duotone icon styles.

**Football imagery assets** (all keyed by Football-Manager `fm_inside_id`):
club **crests** `assets/crests/<id>.png` (e.g. 915 Bayern, 901 Leverkusen, 907
Dortmund, 912 Frankfurt, 944 Freiburg, 918 Mainz, 960 Stuttgart, 961 Wolfsburg,
908 M'gladbach, 905 Bochum), **competition logos** `assets/competitions/`
(bundesliga, champions-league, dfb-pokal, supercup), **player portraits**
`assets/players/<id>.png` (anonymized faces; missing → `assets/default_player.svg`),
and the **brand marks** in `assets/brand/` (the MatchEngine footballer logo at
several sizes + the `kloppo-avatar.png` assistant face).

---

## Implementation Notes

**This design system is a visual + CSS reference, not a React component library.**
The actual product runs on **Django templates + plain HTML/CSS** — no React in
production. Key points for implementation:

- Link `styles.css` (or copy `tokens/*.css`) to get all design tokens as CSS
  custom properties on `:root`. Then use the token variables in your Django
  templates and CSS files.
- The UI kit (`ui_kits/websoccer/index.html`) is pure HTML + CSS — no
  frameworks, no build step. It mirrors the exact markup and class patterns that
  Django templates produce. Use it as a copy-paste reference for your `.html`
  templates and accompanying `.css` files.
- **Target resolution:** 1440×900 as primary design canvas, desktop-first.
  This is a _design target_, not a hard technical lock — do **not** apply a
  `transform:scale()` viewport scaler. Use fluid CSS (`fr` units, `min()`,
  `max-width`) so the layout holds from ~900px upward without breaking.
- The React components in `components/` are **catalog entries for the DS tab
  only** (visual reference). Do not import them into the Django project. The
  equivalent HTML/CSS patterns are in the UI kit.

---

## Index / Manifest

**Root**
- `styles.css` — the single entry point consumers link; `@import`s only.
- `readme.md` — this guide.
- `SKILL.md` — Agent-Skill front-matter so the system works in Claude Code.

**`tokens/`** — design tokens, all `@import`ed by `styles.css`
- `fonts.css` (Inter webfont) · `colors.css` · `typography.css` ·
  `spacing.css` (radii/shadow/layout) · `backgrounds.css` (signature gradient
  recipes + `.ds-app-bg` / `.ds-stadium` helpers) · `base.css` (reset, body
  atmosphere, cyan scrollbars).

**`components/`** — reusable React primitives (`<Name>.jsx` + `.d.ts` +
`.prompt.md`), bundled to `window.WebsoccerDesignSystem_caf892`
- `core/` — Button, IconButton, Badge, Tag, ValuePill, FormDots, ProgressBar,
  StatusDot
- `surfaces/` — Panel, KpiCard
- `media/` — Crest, Avatar
- `forms/` — SearchField
- `navigation/` — NavItem, Tabs

**`ui_kits/websoccer/`** — interactive recreation of the game
- `index.html` — click-through app: Login → Übersicht dashboard → Kader →
  Spielerprofil, with the live sidebar + calendar header. Composes the
  component primitives. (`data.js`, `icons.js`, and the `*.jsx` screens.)

**`guidelines/`** — foundation specimen cards (Colors, Type, Spacing, Brand)
shown in the Design System tab.

**`assets/`** — `brand/`, `icons/` (+ `icons/sidebar/`), `crests/`,
`competitions/`, `players/`, `backgrounds/`, `default_player.svg`.
