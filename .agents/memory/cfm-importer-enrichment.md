---
name: CFM-Importer enrichment & resilience
description: How the local Playwright importer enriches FMInside/SoFIFA and survives Cloudflare; key architectural constraints
---

## Wer scrapt — und wer nicht
- **Nur der lokale Playwright-Importer** (`tools/cfm_importer`) scrapt FMInside/SoFIFA. Der Django-Server scrapt NICHT (kommt durch Cloudflare/JS nicht durch).
- Die manuelle **FMI-ID/SoFIFA-ID-Eingabe** in der Kontrollphase (`creator_import_candidate_update`, action `set_source_ids`) **speichert nur die ID** in `fmi_raw['id']`/`sofifa_raw['id']` und ruft `refresh_candidate` — sie holt KEINE CA/PA/Attribute nach.
  - **Folge:** Eine vom Admin eingetragene FM-ID füllt keine Werte, solange es keinen Importer-Durchlauf "per ID nachladen" gibt. Für neue Spieler kennt der Importer keine FM-ID.

## FMInside-Matching-Policy (bewusste Entscheidung)
- **Namen sind nicht eindeutig** → ein reiner Namens-Treffer wird NIE akzeptiert.
- Reihenfolge in `FMInsideAdapter.lookup`: bekannte **FM-ID → direkter Aufruf** `/players/{id}-{slug}`; sonst Namenssuche, deren Treffer per **Geburtsdatum auf der Detailseite** bestätigt werden muss (max `MAX_DETAIL_CHECKS=5` Detailseiten). Kein DOB / kein bestätigter / mehrere bestätigte Treffer → `None` + Warnung "prüfbedürftig".
- DOB-Scraping ist **defensiv** (`_scrape_dob` probiert Profil-Selektoren, dann Body-Text via `_first_dob`). Wenn FMInside-Selektoren nicht passen, wird nie bestätigt → eher "prüfbedürftig" als falsch. **Why:** lieber manuell nachpflegen als falschen Spieler übernehmen.

## Navigations-Resilienz (`base.safe_goto`)
- Ersetzt das frühere `goto + detect_block` in allen Adaptern.
- 404/410 → sofort `PageError` (kein Retry, kein Raten). 5xx/Timeout → Backoff+Retry (`request.nav_retries`). 403/429 oder Challenge-Titel → erst `challenge_wait_seconds` auf Auto-Auflösung warten, dann bei sichtbarem Browser (`headless:false` + `manual_unblock:true`) **manuell lösen + ENTER**; sonst Backoff/`BlockedError`.
- **Operativer Trick:** einmalig im selben persistenten Edge-Profil (`user_data_dir`) `sofifa.com` öffnen und Cloudflare lösen — der Clearance-Cookie bleibt im Profil, danach laufen die Spieler durch.
