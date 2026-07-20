# Websoccer — Premium AAA Django Football Manager

## Projektübersicht
Django-basierter Fußballmanager mit deutschen UI-Texten. Zielauflösung 1440×900 (locked golden master). Backend: Django 6, PostgreSQL. Frontend: reines HTML/CSS/JS ohne Framework.

## Betriebsentscheidungen
- **KI-Käufer scharf seit Saison 1** (Juli 2026): `KI_KAEUFER.dry_run = False` (Admin-Entscheidung, gesetzt für Saison 0 mit Saison-Fallback). Trockenlauf-Altbestand wurde beim Umschalten storniert (0 offene Angebote). Damit ist die Kalibrierungs-Kennzahl Ablöse/MW-Median ab Saison 1 messbar.

## User Preferences
- Vorgeschlagene Folgeaufgaben (follow-up tasks / "Suggested next tasks") immer auf **Deutsch** formulieren.
