# Websoccer — Premium AAA Django Football Manager

## Projektübersicht
Django-basierter Fußballmanager mit deutschen UI-Texten. Zielauflösung 1440×900 (locked golden master). Backend: Django 6, PostgreSQL. Frontend: reines HTML/CSS/JS ohne Framework.

## Betriebsentscheidungen
- **KI-Käufer scharf** (Juli 2026): `KI_KAEUFER.dry_run = False` (Admin-Entscheidung, gesetzt für Saison 0 mit Saison-Fallback; am 20.07.2026 erneut bestätigt, nachdem der Wert in der DB wieder auf `true` stand). Trockenlauf-Altbestand wurde beim Umschalten storniert.
- **Transferfenster offen** (20.07.2026): `transfer_window_open = True`, Fenster-ID `1-F1`. Achtung: Der KI-Käufer läuft NUR bei offenem Fenster — dry_run=False allein reicht nicht (Saison 0 lief deshalb ohne KI-Käufe; wurde per manuellem Nachlauf mit Saison-Tag 0 nachgeholt).
- **Saison 0 abgeschlossen, Saison 1 läuft** (20.07.2026): Alle 34 Spieltage simuliert, `finance_season_close` (Saison 0) und `finance_season_open` (Saison 1) gelaufen, `current_season = 1`. `kalibrierungs_report('0')` zeigt alle fünf Kennzahlen messbar.

## User Preferences
- Vorgeschlagene Folgeaufgaben (follow-up tasks / "Suggested next tasks") immer auf **Deutsch** formulieren.
