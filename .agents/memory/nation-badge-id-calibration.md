---
name: Nation-Badge-ID Calibration
description: Welche IDs in COUNTRY_FLAG_ASSETS korrekt sind, welche Lücken existieren, und wie weitere Korrekturen verlässlich durchgeführt werden.
---

## Gesicherte Erkenntnisse (2026-07-15)

**Badge-Datei-Lücken (keine Datei auf Server):**
- IDs 56–105: existieren NICHT (direkt nach 55 kommt 106)
- IDs 369, 372, 378, 381: CONCACAF-Lücken (Guatemala, Nicaragua, Trinidad/Tobago alt)
- IDs 803–1434: nach Serbia(802) direkt OFC ab 1435 (Montenegro, Zypern u.a. leer)

**Korrekturen Stand 2026-07-15 (46 Änderungen):**
- CONMEBOL: Argentinien=1650, Bolivien=1649, Chile=1652, Ecuador=1654
- OFC: Australien=1435, Neuseeland=1439 (restliche OFC geleert – falscher Bereich war 1322–1328)
- AFC-Kern: Indien=112, Indonesien=113, Iran=114, Irak=115, Japan=116, Kasachstan=119, Kuwait=120, Libanon=122, Katar=130, Saudi-Arabien=131, Thailand=140, UAE=143, Usbekistan=144, Vietnam=145
- Afrika-Kaskade: Benin=6, Botswana=8, BurkinaFaso=9, Burundi=10, Kamerun=11, KapVerde=12, Tschad=13
- UEFA: Albanien=584, Kosovo=583 (750/803/805 existieren nicht)
- CONCACAF: Kuba=367

**User hat manuell bestätigt:** Afghanistan=106, UAE=143

**Noch nicht zugeordnet / unsicher:**
- AFC: 107–111 (Bahrain?, Bangladesch?, Kambodscha?, China?), 117–118, 121, 123–129, 136–142, 146+
- Afrika: IDs an Pos. 14–21, 29–37, 40, 46, 53–55 (was falsch?)
- CONCACAF: 359–362, 365, 377, 382–389
- OFC: 1436–1444 (Fiji, PNG, Salomonen, Samoa, Tonga, Vanuatu – IDs unbekannt)

## Methodik

**Verlässlich:** User gibt Text-Liste `ID: Ländername` → exakte Anwendung ohne Fehler.  
**Unzuverlässig:** Automatische Bilderkennung kleiner Badge-Thumbnails → Positionsfehler von ±1 möglich.

**Why:** Badge-Labels in den Screenshots sind 6–8px groß; Verwechslungen (z.B. UAE=142 statt 143) entstehen durch Off-by-one beim Abzählen der Badge-Reihe.

**How to apply:** Immer auf Duplikate prüfen (zwei Länder gleiche ID = Anzeige-Fehler). Nach jedem Batch: `python manage.py test game.tests.test_nationality_normalization` prüfen, dann Testbeispiel für `test_returns_empty_string_when_no_asset_id` auf ein Land OHNE asset_id zeigen lassen.
