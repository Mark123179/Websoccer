# Import-Neuaufbau: Nachtrag 12 zur Übergabe

Stand: 06.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 11, zu Replits Bericht `docs/import-pilot/nachtrag11-bericht.md` und zum Kontrollbericht `Import_BVB_Pilot_Kontrolle.md`

Dieser Nachtrag legt fest, was Replit an der Anzeige korrigiert, bevor Mark den BVB abnimmt. Er führt die Titelkategorie `super_cup` und das Paket v3 ein. Bei Widersprüchen hat er Vorrang vor Teil A, Teil B, Teil C und den Nachträgen 1 bis 11.

Alle Entscheidungen hat Mark am 06.10.2026 einzeln getroffen.

## Ausgangslage

Die Kontrolle des Pilots gegen das Paket v2 hat ergeben: Die importierten Daten stimmen. Alle 17 Abweichungen liegen in der Anzeige. Die Punktnummern in diesem Nachtrag sind die des Kontrollberichts.

Geprüft im Code: Für die Punkte 1 bis 15 liegen die Werte vollständig in der Datenbank, verkürzt wird erst in Ansicht oder Vorlage. Eine Ausnahme ist Punkt 18 unten.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N54 | **Replit korrigiert vor der Abnahme die Punkte 1 bis 15 und die drei Navigationsfehler.** Paket, gespeicherte Werte und Stärkeformel bleiben unberührt. Punkt 16 wird auf dem Live-Server geprüft. Punkt 17 (Vereinswert) und die sechs Startwerte bleiben, wie sie sind |
| N55 | **„Meiste Titel" zeigt nur die Zahl.** Gilt für Spieler und Trainer. Der Zusatztext bleibt gespeichert. Der Import kürzt Zusatztexte nicht mehr |
| N56 | **Die Titel-Kacheln zählen aus den Einzeleinträgen, der Supercup zählt getrennt.** Neue Kategorie `super_cup`. BVB: 8 / 5 / 3 |
| N57 | **Echte Rekorde zeigen Saison und Datum mit Jahr.** Rekorde aus dem Spiel bleiben bei „Saison #4" |
| N58 | **Die Vereinsseite rechnet nach Mannschaft.** Der Jugend-Block rechnet aus der U21 und ist nur für Creator sichtbar |
| N59 | **Leihanzeige mit Besitzer, Beginn und „Ende Saison 1".** Gilt für Spielerprofil und Kaderseite |
| N60 | **Paket v3 kommt von Claude, Mark lädt es hoch.** Gegenüber v2 ändern sich nur sechs Titelkategorien |
| N61 | **Ablauf: Korrektur, Gegenprüfung, v3, Abnahme.** Ein Halt nach Replits Bericht |

## Zu N54: Korrekturen im Einzelnen

Alle Korrekturen sind Anzeige. Sie gelten im Paketmodus. Im Altmodus ändert sich nichts.

| Punkt | Seite | Soll | Hinweis zum Code |
|---|---|---|---|
| 1 | Ruhmeshalle, Verein | Kacheln „Meisterschaften", „Pokalsiege", „Internationale Titel" zählen nach N56 | Schlüssel `championships`, `cup_wins`, `international_titles`. Bisher nur aus Spielergebnissen gerechnet |
| 2 | Ruhmeshalle, Trainer | Die Kachel „Längste Siegesserie" zeigt `longest_win_streak_coach` (Tuchel, 11 Pflichtspielsiege in Folge, 2015/16) | Platzhalter `coach_empty_7` ohne Schlüssel |
| 3, 4 | Ruhmeshalle | Saison und Datum nach N57 | Vorlage `management/halloffame.html` gibt fertige Texte aus der Ansicht aus |
| 5 | Spielerprofil | Die Transferhistorie zeigt den gespeicherten Originaltext: „Leihe", „Leih-Ende", „Leihgebühr: 5,00 Mio. €" | `player_detail.html` schreibt bei `is_loan` fest „Leihe" |
| 6 | Spielerprofil | Bei gleichem Datum gilt die Reihenfolge des Pakets, neueste zuerst | Standardsortierung `-transfer_date, -id` dreht gleiche Tage um. Betroffen: Ramaj, 03.02.2025 |
| 7 | Vereinsseite | Das Gründungsjahr steht bei den Stammdaten (BVB: 1909) | `club.founded_year` ist gespeichert und wird nicht ausgegeben |
| 8 | Vereinsseite | Ein leeres Farbfeld wird nicht angezeigt | Ersatzwert `#d9ded9` in `club_detail.html` |
| 9 | Vereinsseite | Nach N58 | `club_profile.py` und `club_profile_highlights.py` teilen bei 21 Jahren |
| 10 | Spielerprofil, Kader | Nach N59 | Das Profil hat keinen Leih-Block |
| 11 | Spielerprofil | Beträge in deutscher Schreibweise: „40.000.000 €", „200.000 €" | Marktwert-Kopf, Quellverlauf, Gehalt |
| 12 | Ruhmeshalle, Arbeitsliste | Deutsche Bezeichnungen statt Rohschlüssel, Liste unten | Titelkategorien, Status, Schwere, Antragsformular |
| 13 | Ruhmeshalle | Die Einheit steht nur einmal: „85 Tore", nicht „85 Tore" mit Zusatz „Tore" | Wert und Einheit werden beide ausgegeben |
| 14 | Spielerprofil | Der Startwert-Punkt zeigt keinen Vereinsnamen, nur „Spielstartwert" | Ersatztext „Unbekannter Verein" bei leerem Verein |
| 15 | Vereinsseite | Ohne gespielte Partie steht „–" statt „90 %" und „1,80" | Highlights „Bester Passgeber", „Notenbester" |

Bezeichnungen zu Punkt 12:

| Rohwert | Anzeige |
|---|---|
| `championship` | Meisterschaft |
| `national_cup` | Nationaler Pokal |
| `super_cup` | Supercup |
| `international_cup` | International |
| `lower_tier` | Unterklassig |
| `Open` | Offen |
| `Player lock` | Einzelsperre |
| `Player ·`, `Coach ·`, `Club ·` | Spieler ·, Trainer ·, Verein · |

Navigation:

- Der Raumwechsel der Ruhmeshalle behält den gewählten Verein. Das gilt für Raumlinks, Pfeile, Modusknöpfe, „Abbrechen" und das Antragsformular.
- Links bleiben im Pilot. Feste Adressen wie `/clubs/…` und `/players/…` in `player_detail.html` und `home.html` werden über die URL-Namen erzeugt.
- Der Link im Bericht zeigt auf den BVB im Pilot (`club=8`).

Unverändert: „Jüngster Spieler" (Moukoko) bleibt gespeichert und wird nicht angezeigt (Nachtrag 8). Der Vereinswert rechnet wie bisher. Die Startwerte nach N10 bleiben mit 50.000 €, Datum 05.10.2026 und 250 € Gehalt.

## Zu N55: Meiste Titel und Zusatztext

- Die Kacheln „Meiste Titel Spieler" und „Meiste Titel" (Trainer) zeigen Zahl und Halter, keinen Zusatztext. BVB: 8 (Zorc) und 5 (Hitzfeld).
- Der Zusatztext bleibt als Beleg gespeichert.
- Punkt 18: Der Import schneidet `context_line` nach 200 Zeichen ab. Diese Kürzung entfällt. Reicht die Spalte nicht, wird sie über eine Migration erweitert, die nach N33 überall läuft.
- Im Pilot ist ein Rekord betroffen: `most_titles_player`, 233 Zeichen, es fehlt das Ende „cup, Champions League, Weltpokal." Replit trägt den Text aus dem gespeicherten Originalpaket nach. Das ist die einzige Änderung an einem gespeicherten Wert in diesem Nachtrag.

## Zu N56: Titelzählung und `super_cup`

| Kachel | zählt Einzeleinträge der Kategorie | BVB |
|---|---|---|
| Meisterschaften | `championship` | 8 |
| Pokalsiege | `national_cup` | 5 |
| Internationale Titel | `international_cup` | 3 |

- `super_cup` und `lower_tier` zählen in keiner der drei Kacheln. Sie stehen weiter im Trophäenschrank und in der Titelliste.
- Die Zählung ist abgeleitet. Es entsteht kein gespeicherter Rekord dafür.
- Im Spiel gewonnene Titel zählen wie bisher dazu.
- Der Import nimmt die Kategorie `super_cup` an. Gültig sind damit `championship`, `national_cup`, `super_cup`, `international_cup`, `lower_tier`.
- Gezählt wird nur über die Kategorie, nie über den Namen des Wettbewerbs.

## Zu N57: Saison und Datum echter Rekorde

Gilt für Rekorde mit Herkunft `real`:

| Feld | Anzeige | Beispiel |
|---|---|---|
| Saison | wie im Paket | „1978/79", „2011/12 bis 2012/13" |
| Datum | Tag, Monat, Jahr | 05.08.1978 |
| Zeitraum | beide Daten mit Jahr | 01.07.2008 – 30.06.2015 |
| Stand | mit Jahr | Stand 07.10.2021 |

Rekorde aus dem Spiel behalten „Saison #4" ohne Jahr. Der Test `test_club_wall_has_sixteen_slots_and_uses_season_without_year` bleibt gültig. Für echte Rekorde kommt ein Test dazu.

## Zu N58: Vereinsseite nach Mannschaft

- „Profis" ist die 1. Mannschaft: eigene und geliehene Spieler, ohne Verliehene. BVB: 28 Spieler, Ø Alter 24,4.
- Die Profi-Highlights rechnen nur aus diesen Spielern.
- Der Jugend-Block (Ø Alter Jugend, Jugend-Highlights, „Zur Jugend") rechnet aus der U21. Er ist nur für Creator sichtbar, solange die U21 nicht öffentlich ist.
- Die Altersgrenze 21 gilt im Paketmodus nicht mehr.

## Zu N59: Leihanzeige

Der Beginn ist das echte Datum laut Transfermarkt. Ein Enddatum gibt es im Spiel noch nicht, weil Saison 1 nicht terminiert ist. Alle laufenden Leihen enden mit Saison 1.

| Fall | Kopf | Zeile darunter |
|---|---|---|
| geliehen | WS-Verein Borussia Dortmund | „Leihe von FC Arsenal · seit 01.09.2026 · bis Ende Saison 1" |
| verliehen | WS-Verein Borussia Dortmund als Besitzer, Wettbewerb leer | „verliehen an FC Kopenhagen · seit 17.08.2026 · bis Ende Saison 1" |

- Der Beginn ist das Datum des obersten Leih-Eintrags der Transferhistorie, der kein „Leih-Ende" ist. Fehlt ein solcher Eintrag, entfällt „seit …".
- Fremde Vereine stehen mit ihrem Originalnamen und ohne Wappen.
- Dieselbe Zeile steht auf der Kaderseite beim Status.
- Das Paketdatum `loan_until` (30.06.2027) bleibt gespeichert und wird nicht angezeigt. Das echte Ende setzt das Spiel, sobald Saison 1 terminiert ist.

Soll für den BVB:

| Spieler | Leihe | seit |
|---|---|---|
| Ethan Nwaneri | geliehen von FC Arsenal | 01.09.2026 |
| Takato Yamamoto | geliehen von Gamba Osaka | 07.07.2026 |
| Daniel Sumbu | geliehen von SK Sturm Graz II | 01.07.2026 |
| Diant Ramaj | verliehen an FC Kopenhagen | 17.08.2026 |
| Almugera Kabar | verliehen an NEC Nijmegen | 14.08.2026 |
| Yan Couto | verliehen an Como 1907 | 06.08.2026 |
| Elias Benkara | verliehen an SpVgg Greuther Fürth | 28.08.2026 |

## Zu N60: Paket v3

Datei: `bvb_vereinspaket_2026-10-05_v3.zip`

| | v2 | v3 |
|---|---|---|
| `data_sha256` | `ab3925f4…51391` | `b938a48eab942e6daf6ab8884b4acb13165648c0961fc0b5efcbd8f425c17b50` |
| Titel `national_cup` | 11 | 5 |
| Titel `super_cup` | 0 | 6 |

Geändert sind genau sechs Werte: die Kategorie der Einträge „DFB-/DFL-Supercup" 1989/90, 1995/96, 1996/97, 2013/14, 2014/15 und 2019/20. Alle übrigen Zeilen von `data.json` sind gleich, im Manifest ändert sich nur die Prüfsumme. Die Lücken sind unverändert, auch der Info-Eintrag mit dem Feld `national_cup`.

Erwartung beim Hochladen von v3 auf den Pilot mit v2:

| Größe | Soll |
|---|---|
| geänderte Titel | 6 (Kategorie) |
| geänderte Spieler, Marktwertpunkte, Transfers, Rekorde, Stärken | 0 |
| Arbeitsliste | 0 neu / 128 weiterhin offen / 0 durch Paket erledigt / 0 wieder offen |
| Arbeitsliste danach | 156 Zeilen, 128 offen, 28 durch Paket erledigt |
| Einzelsperren | 2 |

Die Vorschau weist geänderte Titel aus. Zeigt sie eine andere Änderung, bestätigt Mark nicht.

## Zu N61: Ablauf

1. Replit setzt diesen Nachtrag um und liefert den Bericht. **Halt.** Replit liest v3 nicht ein.
2. Claude prüft alle Seiten und die Stärkentabelle erneut gegen das Paket.
3. Replit sichert den Pilot auf v2 als Dump. Mark lädt v3 über den Import-Knopf hoch und bestätigt nach der Vorschau.
4. Mark sieht sich die vier Seiten an und nimmt den BVB ab.

## Bericht

1. Gesamtlauf mit Anzahl der Tests und Ergebnis
2. Liste der geänderten Ansichten und Vorlagen je Punkt
3. Bildschirmfotos aus dem echten Pilot: Vereinsseite, Kader, die drei Räume der Ruhmeshalle, die Profile von Nwaneri, Ramaj, Couto und Wehrbein
4. Tabelle aller 51 Spieler als Datei: Name, TM-ID, FMInside-Rating und -Potenzial (mit Spanne), CMTracker-Rating und -Potenzial, Basis und Potenzial auf der Rohskala 0–200, Sperre mit Grund
5. Nachweis, dass außer dem Zusatztext von `most_titles_player` kein gespeicherter Wert geändert wurde: Fingerprints der Fachtabellen vorher und nachher
6. Name der Migration, falls `context_line` erweitert wurde
7. Liste der ersetzten festen Links
8. Nachweis, dass der Import die Kategorie `super_cup` annimmt und die Vorschau geänderte Titel ausweist, geprüft im getrennten Testbestand mit v2 → v3
9. Bestätigung, dass der Pilot weiter auf v2 steht

## Für das Werkzeug der zweiten Stufe

- Supercup-Wettbewerbe bekommen die Kategorie `super_cup`.
- „Meiste Titel" zählt alle Titel mit dem Verein, egal in welchem Wettbewerb. Eine Aufzählung im Zusatztext ist nicht nötig.
- Vereinsnamen ohne Leerzeichen am Ende („KRC Genk ").
- Der Lückentext bei Spielern ohne Marktwert nennt den Startwert nach N10 statt „Gehalt bleibt leer".

## Freigabe

Freigegeben: die Korrekturen nach N54 bis N59, die Migration für `context_line` falls nötig, das Nachtragen des einen Zusatztexts, die Annahme der Kategorie `super_cup`, der Test v2 → v3 im getrennten Testbestand, der Bericht.

Nicht freigegeben: Einlesen von v3 in den Pilot durch Replit, Reset-Befehl (T5), Sicherung der Dortmund-Szene, jede Änderung an der Stärkeformel, jede Änderung an der Vereinswert-Regel. Hetzner bleibt unberührt.
