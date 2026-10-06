# Import-Pilot: Bericht zu Nachtrag 12

Stand: 06.10.2026. Umfang: N54–N61. **Halt zur Gegenprüfung durch Claude. Kein Import des Supercup-Korrekturpakets in den echten Pilot.**

## 1. Gesamtlauf

- `python manage.py test game.tests --verbosity=0 --keepdb`: **1677 Tests, OK**, 451.434 Sekunden.

- Gegenüber dem vorigen vollständigen Lauf: neun zusätzliche Nachtrag-12-Tests. Der bestehende SIM-Saison-ohne-Jahr-Test bleibt grün.

- Nach der abschließenden, ausschließlich paketbezogenen Umbruch-/Schriftkorrektur: alle neun Anzeige-Tests erneut grün; kein weiterer Backend-Code verändert.

- Zusätzlich geprüft: Django-Systemcheck, migrationsfreie Modellkonsistenz, Diff-Whitespace; zwei neu gestartete Webdienste laufen.

- Vollständiges Protokoll: `n12-full-suite.log`. Die absichtlich provozierten Fehlerpfad-Tracebacks sind Testfälle, keine fehlgeschlagenen Tests.

## 2. Ansichten und Vorlagen je Punkt
| Punkt | Dateien unter game/ | Änderung |
|---|---|---|
| 1 | `views_management.py` | Titel aus Kategorie-Einzeleinträgen; vorhandene SIM-Titel zusätzlich, ohne Doppelzählung. |
| 2 | `views_management.py` | Trainerplatz 7 zeigt longest_win_streak_coach; Antragsauswahl verwendet denselben Schlüssel. |
| 3, 4 | `views_management.py` | Reale Saison unverändert; Datum/Zeitraum mit Jahr. SIM-Format Saison #4 bleibt bestehen. |
| 5 | `player_detail.html` | Gespeicherter Ablösetext einschließlich Leih-Ende und Leihgebühr statt festem Leihe. |
| 6 | `club_import/presentation.py; views.py` | Gleicher Tag: Reihenfolge aus Originalpaket; Ramaj-Leihe vor Kauf am 03.02.2025. |
| 7, 8 | `club_detail.html` | Gründungsjahr 1909; leere Tertiärfarbe ausgeblendet. |
| 9 | `club_profile.py; club_profile_highlights.py; identity_card.html; club_detail.html` | Profis nach erster Mannschaft: 28, Ø24,4. U21-Alter, Highlights und Jugendlink nur Creator. |
| 10 | `presentation.py; views.py; player_detail.html; squad_page.html; _loan_card.html` | Besitzer/Partner-Originalnamen, echtes Beginn-Datum, bis Ende Saison 1; keine Anzeige loan_until. |
| 11 | `templatetags/package_display.py; player_detail.html` | Deutsche Tausenderpunkte bei Kopf-Marktwert, Verlauf und Gehalt. |
| 12 | `package_display.py; package_hub.html; halloffame.html; package_preview.html` | Deutsche Kategorien, Offen/Einzelsperre und Antragsgruppen. Quellschlüssel unverändert. |
| 13 | `views_management.py` | Einheit wird nicht wiederholt, auch wenn sie innerhalb des Original-Werttextes steht. |
| 14 | `player_detail.html` | Startwert-Punkt ohne Vereinszeile; Spielstartwert bleibt gekennzeichnet. |
| 15 | `club_profile_highlights.py` | Nicht belegte Passquote/Note: Gedankenstrich statt erfundener Werte. |
| N55 | `models.py; migrations/0191_clubrecord_context_text.py; package_service.py` | Meiste Titel: nur Zahl/Halter, Beleg erhalten; Kontext ohne 200-Zeichen-Kürzung. |
| N56/N60 | `package_validation.py; package_service.py; package_preview.py; package_preview.html` | super_cup gültig; sechs Kategorieänderungen sichtbar. Keine Duplikate; Kategorie-Upload resavet keine anderen Fakten; Stale-Preview-Guard umfasst Titel. |
| Navigation | `halloffame.html; views_management.py; home.html; player_detail.html; N11-Bericht` | Verein bleibt bei Raum, Pfeilen, Modus, Abbrechen und Formular; URL-Namen berücksichtigen Pilot-Präfix; Bericht club=8. |

## 3. Echter Pilot: unverändert v2

- Aktiver Paket-Hash: `ab3925f40f1b84ddd103a25928d61aa7feb3c36d9036890ff802131896751391`.

- Arbeitsliste: **156 Zeilen / 128 offen / 28 durch Paket erledigt**. **49 Stärken, zwei Einzelsperren**. Keine zusätzliche Sperre oder neu erzeugte Vereinsreferenz.

- Die echten Pilot-Kacheln zeigen aktuell **8 / 11 / 3**: v2 enthält elf national_cup-Einträge. Das ist kein Namensfehler und wird nicht vorweg manipuliert.

- **8 / 5 / 3** ist nach dem getrennt getesteten Kategorie-Upload korrekt. Sechs Supercup-Titel bleiben in Titelliste und Trophäenschrank, zählen aber nicht in den drei Kacheln.

- BVB-ID ist 8. Keine Managerzuweisung oder sonstige Kontoänderung für die Fotos. Nur eine befristete technische Browser-Sitzung wurde verwendet und anschließend entfernt.

## 4. Alle 51 Spieler

- Datei: `n12-staerken-51.csv`, UTF-8 mit BOM, Semikolon für Tabellenprogramme.

- Enthält Name, TM-ID, beide Quell-Ratings/Potenziale, FMInside-Spanne, gemeinsame Rohbasis und Rohpotenzial 0–200, Sperre und Grund.

- 51 Zeilen; 49 mit beiden berechenbaren Rohwerten, zwei gesperrt. Fehlende Quellen bleiben leer, keine Stärke wird erfunden. Export verwendet ausschließlich die unveränderten reinen Rechenfunktionen, keine persistierende Neuberechnung.

- CSV-SHA256: `9ed5052bedd1647e032dd3b5dac0c45b6f661d9e7da28bacbc97671bb85d2251`.
| Stichprobe | Basis | Potenzial |
|---|---:|---:|
| Ethan Nwaneri | 145 | 181 |
| Samuele Inácio | 120 | 166 |
| Luca Reggiani | 116 | 152 |
| Luke Fahrenhorst | 90 | 160 |
| Bennedikt Wüstenhagen | 92 | 100 |

## 5. Fingerprints und einzige autorisierte Datenänderung

- Vorher/nachher: **144 Game-Fachtabellen**. **143 identisch**, ausschließlich game_clubrecord anders.

- Rekord `most_titles_player`, interne ID 125: context_line **200 → 233 Zeichen**, direkt aus gespeichertem Originalpaket.

- Zeilenvergleich vor/nachher bestätigt: ausschließlich context_line verändert. updated_at identisch; keine anderen Rekordfelder, Paketzeilen, Spieler, Werte, Transfers, Stärken oder Arbeitslistentexte verändert.

- game_clubrecord: jeweils 24 Zeilen; MD5 vorher `5e2d90d0fa2fe439a0e4acfa3097c33e`, nachher `6540261c37fa269b50007cf3f9ee1f7a`.

- Maschinenbelege: `n12-before.json`, `n12-after.json`, `n12-context-repair.json`. Tabellenhashes enthalten vollständige Zeilen inklusive IDs und Zeitstempeln; keine Rohdaten der Konten exportiert.

- Der aktive Altbestand wurde ebenfalls lesend erfasst: `n12-public-before.json` / `n12-public-after.json`. Migrationseintrag/-Sequenz erwartbar geändert; sämtliche Rechte-/Rollen-/Constraint-Metadaten identisch. Zusätzlich weicht der Managerprofil-Hash während laufender Hauptapp-Aktivität ab. Aus dem aggregierten Vorher-Hash allein lässt sich keine einzelne Spalte zuordnen; keine falsche Behauptung vollständiger Bytegleichheit. Dieser Altbestand-Unterschied betrifft nicht den getrennten Pilot.

## 6. Migration

- `game.0191_clubrecord_context_text`: context_line von CharField(200) zu TextField.

- In Hauptschema und Pilot angewendet, unabhängig vom Verhaltensschalter. Kein Daten-Reset, keine Rückmigration; alte Migrationen unverändert.

## 7. Ersetzte feste Links
| Datei | Vorher | URL-Name / Korrektur |
|---|---|---|
| `home.html` | `2× /clubs/ (Vereinsauswahl/Transfermarkt)` | `club_list` |
| `home.html` | `/clubs/{{ primary_club.id }}/` | `club_detail` |
| `home.html` | `/players/{{ spotlight.player_id }}/` | `player_detail` |
| `home.html` | `4× /clubs/{{ next/last_match_home/away_club.id }}/` | `club_detail` |
| `home.html` | `/players/{{ row.player.id }}/` | `player_detail` |
| `home.html` | `/liga/2/` | `league_detail` |
| `home.html` | `/clubs/{{ item.club_id }}/ und 2× /clubs/ (Nachrichten/Live)` | `club_detail / club_list` |
| `player_detail.html` | `/clubs/{{ player.club.id }}/` | `club_detail` |
| `Nachtrag-11-Bericht` | `/import-pilot/management/halloffame/?club=1` | `club=8, Markdown und HTML` |

## 8. Getrennter Testbestand: v2 → v3

- SHA256 von v3-data.json korrekt: `b938a48eab942e6daf6ab8884b4acb13165648c0961fc0b5efcbd8f425c17b50`. Vollvergleich bestätigt **genau sechs geänderte Werte**, ausschließlich competition.category. Manifest: nur data_sha256.
| Wettbewerb | Saison | Vorher | Nachher |
|---|---|---|
| DFB-/DFL-Supercup | 1989/90 | national_cup | super_cup |
| DFB-/DFL-Supercup | 1995/96 | national_cup | super_cup |
| DFB-/DFL-Supercup | 1996/97 | national_cup | super_cup |
| DFB-/DFL-Supercup | 2013/14 | national_cup | super_cup |
| DFB-/DFL-Supercup | 2014/15 | national_cup | super_cup |
| DFB-/DFL-Supercup | 2019/20 | national_cup | super_cup |

- Unit-Test: Vorschau schreibfrei, genau sechs Titeländerungen, null sonstige angezeigte Änderungen; Arbeitsliste 0 neu / 128 weiterhin offen / 0 erledigt / 0 wieder offen.

- Nach Testimport: 30 Titel, davon fünf national_cup und sechs super_cup. Derselbe Titel behält seine Zeilen-ID; kein doppelter Titel.

- Vollständige Game-Tabellenhashes vor/nachher unterscheiden sich nur bei SourceImportRun (neues Archiv), sechs ClubTrophyEntry-Kategorien und abgeleitetem ClubTrophy-Cache. **Spieler, Marktwertpunkte, Transfers, Rekorde, Stärken und Arbeitsliste vollständig identisch**.

- Erneute Bestätigung desselben Pakets: unverändert, keine Schreiboperation. Gleichzeitige Titeländerung verändert den Vorschau-Guard. Vorhandene SIM-Titel werden zusätzlich und ohne doppelte Zählung berücksichtigt.

- Belege: `n12-v3-diff.json`, `game/tests/test_package_display.py`, N12_V3_EVIDENCE im Gesamtlauf.

## 9. Bildschirmfotos aus dem echten Pilot

- Neun vollständige Seitenfotos unter `n12-screenshots/`, zusätzlich als `n12-screenshots.zip`. Im HTML-Bericht direkt eingebettet.

- Nach Browserbefund wurden ausschließlich die zwei Paketvorlagen lesbarer gemacht: Plakettentexte kleiner/mehrzeilig, Halternamen ohne Ellipse; breitere Transferkarte, Gebühren in eigener Zeile und vollständige Liste scrollbar; Marktwert-Quellzeilen ohne überlappende Spalten. Fotos 03–09 danach erneuert, Vereins-/Kaderfotos unverändert gültig.

- Browser-Nachprüfung erfolgreich: geforderte Werte vollständig lesbar, keine Nachbarüberlagerung. Einzelne lange Wörter brechen in den schmalen Plaketten weiterhin mitten im Wort um; 2–3 Pixel rechnerischer Textüberhang ohne abgeschnittenen Pflichtwert bleiben als kleine typografische Einschränkung dokumentiert.

- `01-club-8.png`

- `02-club-8-squad.png`

- `03-hall-player.png`

- `04-hall-coach.png`

- `05-hall-club.png`

- `06-player-283-nwaneri.png`

- `07-player-284-ramaj.png`

- `08-player-286-couto.png`

- `09-player-288-wehrbein.png`

## 10. Abgrenzung und Halt

- Punkt 16 (Bilder/Flaggen/Wappen) bleibt zur Prüfung auf dem Live-Server. Fehlende lokale Bilder werden nicht ergänzt und sind kein Abnahmebeleg für Live.

- Vereinswert-Regel und Stärkeformel unverändert. Jüngster Spieler bleibt gespeichert, nicht angezeigt. Alle sechs Startwerte bleiben 50.000 €, 05.10.2026, Gehalt 250 €.

- Kein Supercup-Paketimport in den Pilot, kein Reset/T5, keine Dortmund-Szenensicherung, keine Hetzner-Änderung und keine Veröffentlichung.

- **Hier ist der vereinbarte Halt.** Zuerst Claude-Gegenprüfung; anschließend erst die freigegebene v2-Sicherung und der Upload mit Bestätigung durch Mark.
