# Websoccer – Projektkontext

## Was ist Websoccer?

Django-basiertes Fußballmanager-Browsergame. Der Spieler übernimmt einen Bundesliga-Verein, führt Kader, Taktik, Finanzen und kämpft um Titel. Ziel: vollständig spielbare Manager-Simulation mit Saisonbetrieb, Match-Simulation, Transfers und Entwicklungssystemen.

## Tech-Stack (Stand 2026)

- **Backend:** Python / Django 6.0.x
- **Datenbank:** PostgreSQL auf Supabase (via `DATABASE_URL` Secret; fällt auf SQLite zurück wenn kein Secret gesetzt)
- **Frontend:** Django Templates + HTML/CSS (kein JS-Framework)
- **Hosting/Dev:** Replit (Nix, pnpm, `.pythonlibs`)
- **App-Struktur:**
  - `core/` — Django-Projektkonfiguration, Settings, URLs
  - `game/` — gesamte Spiellogik, Models, Views, Templates, Static

## Wo die durable Entscheidungen liegen

Alle non-offensichtlichen Architektur- und Design-Entscheidungen sind in `.agents/memory/` gespeichert:

- Wide-Shell-Scope (1440×900 Layout-Grenze)
- Asset-ID-System (`fm_inside_id` → Bildpfade)
- Design-Token (CSS-Variablen)
- Wirtschafts-Balancing-Prinzipien
- Technische Fallstricke (CSRF, Bayern-Fallback, CSS-Cache-Bust)

## Referenzprojekte (Inspiration, kein Kopieren)

- `https://websoccer.ch`
- `https://champions-football-manager.de`

Muster die funktionieren: umfangreiches Datencenter, klarer Spielbetrieb, Manager-Profil, Community/News.

## Spielstärke & Wirtschaft

- Stärkemodell: → `SPIELSTAERKEMODELL.md`
- Asset-ID-Mapping: → `DATEN_UND_ASSETS.md`
- Design-System: → `DESIGN.md`
