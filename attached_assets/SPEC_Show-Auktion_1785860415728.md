# SPEC_Show-Auktion.md

**Modul:** Show-Auktion (Transfers → Auktionen)
**Version:** 1.0
**Stand:** 4. August 2026
**Status:** implementierungsbereit
**Abhängigkeiten:** Finanzsystem (Buchungsservice, Escrow), Transfersystem v2 (Kaderlimit, Wechselsperre, Transferhistorie), Forum (Glocken-Benachrichtigungen), Spielerdatenbank

---

## 1. Zweck & Abgrenzung

Die Show-Auktion ist ein **eigenständiges, creator-kuratiertes Event-Modul** unter dem Navigationspunkt *Transfers → Auktionen*. Sie ist **nicht** Teil des offenen Transfermarkts und teilt mit ihm keine Models.

**Was sie ist:** Ein bis fünf handverlesene Spieler werden in unregelmäßigen Abständen (ein- bis zweimal pro Saison, rein manuell) in parallelen Auktionen unterschiedlichen Typs versteigert, präsentiert im Stil einer TV-Transfershow.

**Was sie nicht ist:** Kein zweiter Transfermarkt, kein Dauerbetrieb, kein Automatismus.

**Geldfluss:** Der Erlös ist eine **Senke**. Es gibt keinen abgebenden Verein, das Geld verlässt den Wirtschaftskreislauf vollständig. Damit wirkt jede Show-Auktion als Inflationsbremse.

**Geteilte Infrastruktur (verbindlich):** Geldreservierung, Deckungsprüfung, Kaderlimit-Prüfung und Buchung laufen ausschließlich über den zentralen Buchungsservice des Finanzsystems. Es darf **keine** zweite Wahrheit über Kontostand oder Kaderbelegung entstehen. Ein Manager, der gleichzeitig im Normalmarkt und in Show-Auktionen bietet, muss eine gemeinsame Sicht auf „verfügbar" haben.

---

## 2. Begriffe

| Begriff | Bedeutung |
|---|---|
| **Preset** | Benannter Auktionstyp = gespeicherte Belegung der 16 Achsen. Im Creator Mode anlegbar/änderbar. |
| **Auktion** | Instanz eines Presets für genau einen Spieler. Enthält eine **eingefrorene Kopie** der Preset-Konfiguration. |
| **Bühne** | Übersichtsseite („Auktionshaus"), zeigt 1–5 laufende Auktionen als Hologramme. |
| **Detailseite** | „Transfer Update — Die Show", Einzelansicht einer Auktion. |
| **Raum** | Statuszustand des Spielers während einer Auktion; er ist aus allen Standardabfragen entfernt. |
| **Korridor** | Verborgener Zielbereich der Bereichsauktion. |
| **Senke** | Geldabfluss aus dem Wirtschaftskreislauf ohne Empfänger. |

---

## 3. Die Achsen-Grammatik

Ein Auktionstyp ist **vollständig durch Parameter beschreibbar**. Es gibt keinen typspezifischen Code. Neue Typen entstehen im Creator Mode durch Belegung dieser Achsen — ohne Migration, ohne Deployment.

| # | Achse | Zulässige Werte | Bemerkung |
|---|---|---|---|
| 1 | **Gebotsrichtung** | `aufsteigend` · `verdeckt` · `fallend` · `fest` | Bestimmt Slot A im Template |
| 2 | **Sichtbarkeit** | `hoechstgebot_und_bieter` · `nur_hoechstgebot` · `nur_gebotsanzahl` · `nichts` | Bestimmt, was Slot A anzeigt |
| 3 | **Endebedingung** | `deadline` · `haltezeit` · `erster_zuschlag` · `preisboden` | Bestimmt Slot B |
| 4 | **Verlängerung** | `aus` · `{minuten: X, fenster: Y}` | Gebot innerhalb der letzten Y Minuten verlängert um X |
| 5 | **Haltezeit-Verlauf** | `konstant: X` · `degressiv: [Stufenliste]` | Nur bei Endebedingung `haltezeit` |
| 6 | **Gebote pro Manager** | `unbegrenzt` · `genau_1` · `max_N` | |
| 7 | **Gebot änderbar** | `ja` · `nein` | Nur sinnvoll bei `genau_1`/`max_N` |
| 8 | **Mindesterhöhung** | `keine` · `fix: X` · `prozent: P` · `max_fix_prozent: {X, P, rundung: R}` | |
| 9 | **Startpreis** | `absolut: X` · `prozent_mw: P` | |
| 10 | **Preisverfall** | `aus` · `{schritt_prozent, intervall_minuten, boden_prozent_mw}` | Nur bei Richtung `fallend` |
| 11 | **Zuschlagspreis** | `eigenes_gebot` · `zweithoechstes_plus_erhoehung` | |
| 12 | **Teilnahmebedingung** | Liste aus: `max_mw_schnitt` · `coins` · `freie_kaderplaetze` · `mindestkontostand` · `liga` | Orthogonal, auf jeden Typ kombinierbar |
| 13 | **Darstellung** | `{farbe_hex, regeltext, icon}` | Farbe fest am Typ |
| 14 | **Maximallaufzeit** | `aus` · `tage: N` | Optional, Default `aus` |
| 15 | **Gewinnerermittlung** | `hoechstes_gebot` · `naechstliegend_verborgenes_ziel` · `erster_zuschlag` | |
| 16 | **Reservierungsfreigabe** | `bei_ueberbietung` · `bei_auktionsende` · `sofortige_buchung` | |

### 3.1 Globale Regeln (kein Achsenwert, gelten immer)

- **Gleichstand → Losentscheid.** Es gibt niemals mehrere Gewinner. Keine Stichauktion.
- **Parameter-Einfrieren:** Beim Anlegen einer Auktion wird die Preset-Konfiguration als Snapshot in die Auktion kopiert. Spätere Änderungen am Preset wirken **nie** rückwirkend auf laufende Auktionen.
- **Kein Tausch.** Gebote sind ausschließlich Geldleistungen.
- **Kein Multi-Lot.** Eine Auktion = ein Spieler = ein Gewinner.
- **Keine Ablehnung / kein Hammer.** Es gibt keinen Verkäufer, der zuschlagen oder ablehnen könnte. Jedes gültige Gebot ist legitim.

### 3.2 Ausdrücklich nicht in der Grammatik

Diese Punkte wurden geprüft und bewusst ausgeschlossen. Sie nachträglich einzuführen bricht das Datenmodell:

- Mehrere Gewinner / Paket-Lose
- Spieler-im-Gebot (Tauschangebote)
- Gegenzug-Auktionen (Verkäufer erteilt manuell Zuschlag oder lehnt ab)

---

## 4. Start-Presets

Fünf Presets zum Start. Jeder stellt eine andere Frage an den Manager. Weitere Typen (z. B. Deadline mit Sniping-Schutz, Undercover mit Zweitpreis-Zuschlag, Festpreis) werden über den Creator Mode nachgerüstet — **ohne Code**.

### 4.1 Halte-Auktion (Flaggschiff)

**Farbe:** Gelb `#ffd400` · **Frage:** Wer hält am längsten durch?

| Achse | Wert |
|---|---|
| 1 Gebotsrichtung | `aufsteigend` |
| 2 Sichtbarkeit | `hoechstgebot_und_bieter` |
| 3 Endebedingung | `haltezeit` |
| 4 Verlängerung | `aus` (die Haltezeit ist der Mechanismus) |
| 5 Haltezeit-Verlauf | `degressiv: [24h, 12h, 6h, 3h, 1h]` |
| 6 Gebote pro Manager | `unbegrenzt` |
| 7 Änderbar | `nein` |
| 8 Mindesterhöhung | `max_fix_prozent: {100.000 €, 5 %, rundung: 50.000 €}` |
| 9 Startpreis | `prozent_mw: 60 %` |
| 11 Zuschlagspreis | `eigenes_gebot` |
| 14 Maximallaufzeit | `aus` |
| 15 Gewinnerermittlung | `hoechstes_gebot` |
| 16 Reservierungsfreigabe | `bei_ueberbietung` |

**Treppenlogik:** Die Stufe richtet sich nach der Anzahl abgegebener Gebote. Vor dem ersten Gebot läuft Stufe 1 ab Auktionsstart. Gebot 1 → 24h, Gebot 2 → 12h, Gebot 3 → 6h, Gebot 4 → 3h, ab Gebot 5 → 1h.
`ends_at = zeitpunkt_letztes_gebot + aktuelle_stufe` (bzw. `starts_at + stufe_1`, solange kein Gebot vorliegt).

**Ohne Gebot:** Läuft Stufe 1 ohne ein einziges Gebot ab, **platzt** die Auktion.

**Bewusst keine Maximallaufzeit:** Die degressive Treppe ist die Bremse. Nach vier Geboten steht die Haltezeit bei 1h — eine „ewige" Auktion erfordert dann stündliche Gebote und ist damit eine Schlacht, kein Stillstand. Für künftige Presets mit **konstanter** Haltezeit ist Achse 14 zwingend zu setzen.

### 4.2 Undercover

**Farbe:** Rot `#e8392f` · **Frage:** Was ist er dir wirklich wert?

| Achse | Wert |
|---|---|
| 1 Gebotsrichtung | `verdeckt` |
| 2 Sichtbarkeit | `nur_gebotsanzahl` |
| 3 Endebedingung | `deadline` (Standard 3 Tage) |
| 4 Verlängerung | `aus` |
| 6 Gebote pro Manager | `genau_1` |
| 7 Änderbar | `ja` (bis Auktionsende) |
| 8 Mindesterhöhung | `keine` |
| 9 Startpreis | `prozent_mw: 60 %` (= Mindestgebot) |
| 11 Zuschlagspreis | `eigenes_gebot` |
| 15 Gewinnerermittlung | `hoechstes_gebot` |
| 16 Reservierungsfreigabe | `bei_auktionsende` |

**Anzeige:** Der Marktwert übernimmt die Hero-Position (die große Zahl). Das Gebotsfeld zeigt `?? ??? ??? €` plus Anzahl abgegebener Gebote. Der Hitzemesser zeigt **nur den Zeiger**, niemals Zahlen (Label „Gerüchteküche").

**Ohne Gebot:** platzt.

### 4.3 Holländisch

**Farbe:** Orange `#ff7a1a` · **Frage:** Wie lange traust du dich zu warten?

| Achse | Wert |
|---|---|
| 1 Gebotsrichtung | `fallend` |
| 2 Sichtbarkeit | `nur_hoechstgebot` (= aktueller Preis) |
| 3 Endebedingung | `erster_zuschlag` (alternativ `preisboden`) |
| 6 Gebote pro Manager | `unbegrenzt` (faktisch genau eines, das erste beendet) |
| 8 Mindesterhöhung | `keine` |
| 9 Startpreis | `prozent_mw: 200 %` |
| 10 Preisverfall | `{schritt_prozent: 2, intervall_minuten: 30, boden_prozent_mw: 50}` |
| 11 Zuschlagspreis | `eigenes_gebot` (= aktueller Preis) |
| 15 Gewinnerermittlung | `erster_zuschlag` |
| 16 Reservierungsfreigabe | `sofortige_buchung` |

**Preisformel (nicht getickt, sondern berechnet):**

```
schritte      = floor((jetzt - starts_at) / intervall_minuten)
preis_roh     = startpreis - (schritte * schritt_prozent/100 * startpreis)
aktueller_preis = max(preisboden, preis_roh)
```

Frontend und Backend verwenden **dieselbe Formel**. Es gibt keinen gespeicherten Zwischenstand, damit der angezeigte Preis nie vom gebuchten abweichen kann. Der Server ist die Autorität: beim Zuschlag wird der Preis serverseitig neu berechnet.

Startpreis 200 % → Boden 50 % bei 2 %/30 Min ergibt 75 Schritte = 37,5 Stunden Gesamtlaufzeit.

**Preisboden erreicht ohne Zuschlag:** platzt.

**Sonderfall Reservierung:** Es gibt kein Gebot vor dem Zuschlag. Geprüft und gebucht wird im Moment des Klicks, unter Zeilensperre. Keine Reservierung.

### 4.4 Bereichsauktion

**Farbe:** Creme `#f2efe6` · **Frage:** Triffst du den Korridor?

| Achse | Wert |
|---|---|
| 1 Gebotsrichtung | `verdeckt` |
| 2 Sichtbarkeit | `nur_gebotsanzahl` |
| 3 Endebedingung | `deadline` (Standard 3 Tage) |
| 6 Gebote pro Manager | `genau_1` |
| 7 Änderbar | `ja` (bis Auktionsende) |
| 8 Mindesterhöhung | `keine` |
| 9 Startpreis | kein Mindestgebot erforderlich (frei) |
| 11 Zuschlagspreis | `eigenes_gebot` |
| 15 Gewinnerermittlung | `naechstliegend_verborgenes_ziel` |
| 16 Reservierungsfreigabe | `bei_auktionsende` |

**Korridor:** Wird beim Anlegen der Auktion **vom System zufällig gezogen** und niemals angezeigt.

```
mitte  = uniform(spanne_min, spanne_max) * marktwert      # Default 80 % … 130 %
breite = breite_prozent * marktwert                        # Default 10 %
korridor = [mitte - breite/2, mitte + breite/2]
```

`spanne_min`, `spanne_max` und `breite_prozent` sind im Creator Mode pro Auktion editierbar, falls der Markt andere Werte hergibt.

**Gewinnerermittlung (harte Hürde):**
1. Nur Gebote **innerhalb** des Korridors qualifizieren.
2. Unter den Qualifizierten gewinnt das Gebot mit dem kleinsten `|gebot − mitte|`.
3. Gleichstand → Los.
4. **Trifft kein Gebot den Korridor, platzt die Auktion.** Kein Auffangnetz. Der Spieler bleibt unverkauft, alle Reservierungen werden freigegeben.

Der Gewinner zahlt **sein eigenes Gebot**, nicht die Korridormitte.

**Anzeige:** Wie Undercover — Marktwert als Hero-Zahl, Gebotsfeld verdeckt. Der Korridor wird auch nach Auktionsende nicht offengelegt (verhindert Rückschlüsse auf den Zufallsgenerator über mehrere Auktionen).

### 4.5 Blitz

**Farbe:** Magenta `#ff2d78` · **Frage:** Bist du gerade da?

| Achse | Wert |
|---|---|
| 1 Gebotsrichtung | `aufsteigend` |
| 2 Sichtbarkeit | `hoechstgebot_und_bieter` |
| 3 Endebedingung | `deadline` (90 Minuten) |
| 4 Verlängerung | `{minuten: 5, fenster: 5}` — unbegrenzt oft |
| 6 Gebote pro Manager | `unbegrenzt` |
| 8 Mindesterhöhung | `max_fix_prozent: {50.000 €, 3 %, rundung: 50.000 €}` |
| 9 Startpreis | `prozent_mw: 60 %` |
| 11 Zuschlagspreis | `eigenes_gebot` |
| 15 Gewinnerermittlung | `hoechstes_gebot` |
| 16 Reservierungsfreigabe | `bei_ueberbietung` |

Der einzige Typ mit synchronem Moment. Snipen ist durch die Verlängerung folgenlos.

**Ohne Gebot:** platzt.

### 4.6 Farbvergabe

| Typ | Farbe |
|---|---|
| Halte-Auktion | Gelb `#ffd400` |
| Undercover | Rot `#e8392f` |
| Bereich | Creme `#f2efe6` |
| Holländisch | Orange `#ff7a1a` |
| Blitz | Magenta `#ff2d78` |

**Regel:** Farbe ist eine feste Eigenschaft des Typs. Eine Bereichsauktion ist immer creme.
**Reserviert:** Cyan `#22e6ff` ist im Design-System die funktionale Lichtfarbe (Buttons, Links, Fokus) und darf **nie** Typfarbe werden. Grün `#30f29c` und Orange `#ff9f1c` sind für HP/NP-Positionen belegt — das Typ-Orange `#ff7a1a` ist bewusst dunkler gewählt.

---

## 5. Medienmarke

Die Medienmarke („Präsentiert von") ist **unabhängig vom Auktionstyp** und wird **pro Auktion** gesetzt.

- Feld: Bild-Upload per Browse/Drag&Drop im Creator Mode
- Keine Freistellung, keine Hintergrundentfernung (Logo-Slots werden nie durch `auto-cutout` geschickt)
- **Der Slot sitzt auf einer dunklen Trägerfläche**, damit jedes Logo auf jeder Typfarbe lesbar bleibt (verhindert weißes Logo auf Creme)
- Leerer Slot ist zulässig; das Layout darf dabei nicht brechen

---

## 6. Datenmodell

### 6.1 `ShowAuctionPreset`

| Feld | Typ | Bemerkung |
|---|---|---|
| `id` | PK | |
| `name` | CharField | z. B. „Halte-Auktion" |
| `slug` | SlugField, unique | |
| `color_hex` | CharField(7) | Typfarbe, fest |
| `rules_text` | TextField | Typspezifische Erklärung für das Regelpanel |
| `config` | JSONField | Belegung der 16 Achsen, schema-validiert |
| `is_active` | Boolean | |
| `sort_order` | Integer | |

**Warum `config` als JSONField und nicht als Spalten:** Der Creator Mode muss neue Typen ohne Migration anlegen können. Bei Spalten bräuchte jede neue Achse ein Deployment. Das Schema wird beim Speichern validiert (Pydantic/jsonschema), damit ungültige Kombinationen gar nicht erst entstehen.

**Validierungsregeln (Auszug):**
- `haltezeit_verlauf` nur bei `endebedingung = haltezeit`
- `preisverfall` nur bei `gebotsrichtung = fallend`
- `gebot_aenderbar = ja` nur bei `gebote_pro_manager != unbegrenzt`
- `endebedingung = haltezeit` + `haltezeit_verlauf = konstant` ⇒ `maximallaufzeit` ist Pflicht
- `gewinnerermittlung = naechstliegend_verborgenes_ziel` ⇒ `sichtbarkeit ∈ {nur_gebotsanzahl, nichts}` und `gebote_pro_manager = genau_1`

### 6.2 `ShowAuction`

| Feld | Typ | Bemerkung |
|---|---|---|
| `id` | PK | |
| `preset` | FK → Preset, `SET_NULL` | nur Referenz/Herkunft |
| `config_snapshot` | JSONField | **eingefrorene Kopie** bei Anlage — maßgeblich |
| `color_hex` | CharField(7) | eingefroren |
| `rules_text` | TextField | eingefroren |
| `player` | FK → Player | |
| `hero_image` | ImageField | Ganzkörper/Teilkörper, freigestellt |
| `media_logo` | ImageField, nullable | Medienmarke |
| `status` | Choice | `draft` · `scheduled` · `running` · `settled` · `failed` · `cancelled` |
| `starts_at` | DateTime | |
| `ends_at` | DateTime, nullable | berechnet, bei Haltezeit veränderlich |
| `start_price` | Decimal | aufgelöst aus Achse 9 |
| `hidden_target` | Decimal, nullable | Korridormitte (Bereich) |
| `hidden_width` | Decimal, nullable | Korridorbreite (Bereich) |
| `hold_step_index` | Integer | aktuelle Treppenstufe |
| `extension_count` | Integer | Zähler Verlängerungen |
| `conditions` | JSONField | Teilnahmebedingungen (Achse 12) |
| `winner_club` | FK, nullable | |
| `winning_amount` | Decimal, nullable | |
| `settled_at` | DateTime, nullable | |
| `created_by` | FK → User | |

**Index:** `(status, ends_at)` — trägt den Beat-Task.

### 6.3 `ShowAuctionBid`

| Feld | Typ | Bemerkung |
|---|---|---|
| `auction` | FK → ShowAuction | |
| `club` | FK → Club | |
| `amount` | Decimal | |
| `created_at` / `updated_at` | DateTime | |
| `is_active` | Boolean | verdeckte Gebote: das jeweils gültige |
| `is_leading` | Boolean | nur bei aufsteigenden Typen |
| `reservation_ref` | CharField | Referenz zur Reservierung im Finanzsystem |

**Constraint:** Bei `gebote_pro_manager = genau_1` unique auf `(auction, club)` mit `is_active=True`.

### 6.4 `ShowAuctionWatch`

| Feld | Typ |
|---|---|
| `auction` | FK |
| `club` | FK |
| `source` | `bid` · `manual` |
| `created_at` | DateTime |

**Constraint:** unique `(auction, club)`.

### 6.5 Spielerstatus („Raum")

Der Spieler erhält beim **Anlegen** der Auktion (nicht erst beim Start) einen Statuswechsel, der ihn aus **allen** Standardabfragen entfernt: Scouting, Transfermarkt, Spielersuche, Vereinslosen-Liste.

**Empfohlene Umsetzung:** eigener Statuswert am Spieler (z. B. `player_status = 'show_auction'`) plus Anpassung des Default-Managers/QuerySets, damit die Ausblendung **nicht** in jeder einzelnen Query wiederholt werden muss. Ein reines Flag, das jede Query respektieren muss, ist fehleranfällig — die eine vergessene Query fällt erst auf, wenn ein Auktionsspieler gescoutet wurde.

**Rückführung:** Bei `settled` → regulärer Transfer. Bei `failed`/`cancelled` → zurück in den Normalbestand.

**Replit:** Die konkreten Anschlusspunkte (welche Manager/QuerySets betroffen sind) sind im Code zu ermitteln; diese Spec gibt nur die Regel vor.

---

## 7. Lebenszyklus

```
draft ──► scheduled ──► running ──► settled   (Zuschlag)
                            └─────► failed    (geplatzt)
  └──────────────────────────────► cancelled  (Creator bricht ab)
```

| Übergang | Auslöser | Wirkung |
|---|---|---|
| → `draft` | Creator legt an | Spieler betritt den **Raum**, Korridor wird gezogen (Bereich), Config eingefroren |
| → `scheduled` | Creator bestätigt | `starts_at` gesetzt |
| → `running` | Beat-Task / Lazy | Auktion erscheint auf der Bühne, Gebote möglich |
| → `settled` | Endebedingung + Gewinner | Buchung, Transfer, Reservierungen frei |
| → `failed` | Endebedingung ohne gültigen Gewinner | Spieler zurück, alle Reservierungen frei |
| → `cancelled` | Creator | wie `failed` |

### 7.1 Zuschlag (`settled`)

1. Gewinner nach Achse 15 ermitteln, bei Gleichstand losen
2. Zuschlagspreis nach Achse 11 bestimmen
3. **Buchung über den zentralen Buchungsservice**, Referenz `showauction:{auction_id}:settle` (unique)
4. Betrag als Senke ausbuchen — kein Empfängerkonto
5. Spieler verlässt den Raum, regulärer Transfer zum Gewinnerverein
6. **Transferhistorie:** Eintrag „Vereinslos → Gewinnerverein" mit Ablösesumme
7. **Wechselsperre 21 Tage** greift wie bei jedem Transfer
8. **Keine Jugendabgabe** (entfällt bei Vereinslosen, deckungsgleich mit Transfersystem v2)
9. Alle übrigen Reservierungen (Geld + Kaderplatz) freigeben
10. Benachrichtigung an alle Beobachter

### 7.2 Platzen (`failed`)

Mögliche Ursachen: kein Gebot abgegeben · Bereichsauktion ohne Korridortreffer · Holländische erreicht den Preisboden ohne Zuschlag.

Wirkung: Spieler verlässt den Raum und geht unverändert in den Normalbestand zurück, sämtliche Reservierungen werden freigegeben, Benachrichtigung an alle Beobachter. Der Spieler darf **ohne Wartefrist** erneut angesetzt werden.

---

## 8. Gebotslogik

### 8.1 Prüfreihenfolge (verbindlich)

Jede Gebotsabgabe läuft in **einer** Transaktion unter Zeilensperre auf die Auktion (`select_for_update`). Zwei gleichzeitige Gebote auf denselben Betrag sind sonst ein realer Fehlerfall, besonders bei Blitz.

1. Auktion existiert, `status = running`, innerhalb des Zeitfensters
2. **Teilnahmebedingungen** (Achse 12) erfüllt — sonst Abbruch mit konkretem Grund
3. **Gebote-pro-Manager-Limit** (Achse 6) / Änderbarkeit (Achse 7)
4. **Betragsvalidierung**
   - aufsteigend: `betrag ≥ aktuelles_hoechstgebot + mindesterhoehung`, mindestens `start_price`
   - verdeckt: `betrag ≥ start_price` (falls gesetzt)
   - fallend: `betrag = serverseitig berechneter aktueller Preis`
5. **Kaderplatz verfügbar:** `limit_aus_vereinsumfeld − belegt − reserviert ≥ 1`
6. **Deckung:** `kontostand − reserviert ≥ betrag`
7. Reservierung setzen (Geld + Kaderplatz) bzw. bei `sofortige_buchung` direkt buchen
8. Vorheriges Höchstgebot: Reservierung freigeben, `is_leading = False`
9. Watchlist-Eintrag anlegen (`source = bid`), falls nicht vorhanden
10. Benachrichtigung an den Überbotenen
11. `ends_at` neu berechnen (Haltezeit-Treppe bzw. Verlängerung), `hold_step_index` / `extension_count` hochzählen

### 8.2 Änderung eines verdeckten Gebots

Bei Undercover und Bereich ist das Gebot bis Auktionsende änderbar (Achse 7 = `ja`).

- Die Reservierung wird auf den neuen Betrag **angepasst**, nach oben wie nach unten, jeweils mit erneuter Deckungsprüfung.
- Wer sein Gebot senkt, bekommt Geld frei. Das erlaubt theoretisch, Geld kurzzeitig zu „parken" — akzeptiert, weil der Manager dafür mit seiner Siegchance bezahlt.
- Es entsteht **kein** neuer Datensatz; das bestehende aktive Gebot wird aktualisiert (`updated_at`).

---

## 9. Geld & Kaderplatz

**Grundsatz: hart.** Bei Gebotsabgabe wird geprüft, ob Geld und Kaderplatz vorhanden sind, und beides wird reserviert.

| Was | Regel |
|---|---|
| **Geld** | `verfügbar = kontostand − reserviert`. Reservierung beim Gebot, Freigabe nach Achse 16. |
| **Kaderplatz** | Reservierung gegen die Vereinsumfeld-Obergrenze. Freigabe nach Achse 16. |

**Warum auch der Kaderplatz reserviert wird:** Ohne Platzreservierung kann ein Manager mit 59/60 Spielern bieten, parallel im Normalmarkt zwei Spieler kaufen und die Show-Auktion gewinnen. Im Moment des Zuschlags gäbe es dann nur schlechte Auflösungen — Zuschlag platzen lassen (ruiniert die Show), Limit brechen (ruiniert die Ökonomie) oder an den Zweitbieter geben (der längst anderweitig gebunden ist). Mit Reservierung kann die Situation nicht entstehen.

**Freigabezeitpunkt je Typ:**

| Typ | Achse 16 |
|---|---|
| Halte-Auktion | `bei_ueberbietung` |
| Blitz | `bei_ueberbietung` |
| Undercover | `bei_auktionsende` |
| Bereich | `bei_auktionsende` |
| Holländisch | `sofortige_buchung` (keine Reservierung) |

**Akzeptierte Nebenwirkung:** Bei fünf parallelen Auktionen kann ein Manager mit knappem Budget realistisch nur an ein bis zwei teilnehmen. Das ist beabsichtigt — es stellt die Auktionen gegeneinander in Konkurrenz.

---

## 10. Beendigung

**Kein Task pro Auktion.** Ein einziger Celery-Beat-Task, Intervall 60 Sekunden, plus Lazy-Auswertung beim Seitenaufruf.

```python
# Beat, alle 60s
faellige = ShowAuction.objects.filter(status='running', ends_at__lte=now())
# zusätzlich: scheduled → running
```

**Warum kein `apply_async(eta=...)` pro Auktion:** Bei der Halte-Auktion verschiebt sich das Ende mit jedem Gebot. Man müsste den alten Task revoken und neu planen. Redis verliert Tasks bei Neustart, Revokes gehen verloren, und im Zweifel existieren zwei Tasks für dieselbe Auktion — mit doppeltem Zuschlag und doppelter Buchung. Der Beat ist zustandslos und übersteht jeden `docker compose up -d --force-recreate`.

**Lazy-Auswertung:** Wer eine Auktion aufruft, deren `ends_at` in der Vergangenheit liegt, löst die Auswertung sofort selbst aus. Deckt die Lücke zwischen zwei Beat-Läufen.

**Idempotenz:** Buchungsreferenz `showauction:{auction_id}:settle` mit Unique-Constraint. Damit ist doppeltes Beenden strukturell unmöglich, auch wenn Beat und Lazy gleichzeitig zuschlagen.

**Bewusst nicht umgesetzt:** adaptiver Beat (Intervall abhängig von der nächsten Fälligkeit). Optimierung eines Problems, das bei fünf Auktionen nicht existiert, und sie fügt genau den Zustand hinzu, den der Beat vermeidet. Nachrüstbar, falls jemals 50 parallele Auktionen laufen.

---

## 11. Teilnahmebedingungen

Bedingungen sind **orthogonal** zum Typ und pro Auktion frei kombinierbar. Sie sind **keine** eigenen Auktionstypen — eine Undercover-Auktion mit MW-Limit und eine Holländische mit Coin-Einsatz sind normale Instanzen mit gesetzter Achse 12.

| Bedingung | Parameter | Prüfung |
|---|---|---|
| `max_mw_schnitt` | Betrag | Ø Marktwert des Kaders ≤ Grenze |
| `coins` | Anzahl | Hoeneß-Coins vorhanden (Verbrauch: siehe offener Punkt O2) |
| `freie_kaderplaetze` | Anzahl | mindestens N freie Plätze |
| `mindestkontostand` | Betrag | verfügbar ≥ Betrag |
| `liga` | Liga-IDs | Verein spielt in einer der Ligen |

**Darstellung:** Bedingungen erhalten **keine eigene Farbwelt**. Sie erscheinen als Chip neben dem Typ-Chip („NUR BIS Ø 8 MIO." / „1 COIN").

**Pflicht auf der Detailseite:** Ist ein Manager nicht teilnahmeberechtigt, muss das **vor** dem Klick auf „Gebot abgeben" sichtbar sein — eine Zeile im Regelpanel mit konkretem Grund. Der Gebots-Button ist deaktiviert.

---

## 12. Benachrichtigungen & Beobachtungsliste

**Ein Mechanismus, keine Sonderregeln:**

- **Ein Gebot setzt den Manager automatisch auf die Beobachtungsliste** (`source = bid`). Manuell wieder entfernbar.
- Der Beobachten-Button setzt denselben Eintrag (`source = manual`).

**Kanal:** ausschließlich **In-Game-Glocke** über die Benachrichtigungs-Infrastruktur des Forums.

**Ereignisse:** neues Gebot · Überbietung · Auktionsstart · Auktionsende · Auktion geplatzt · Endspurt-Beginn.

**Nicht bündeln.** Anders als Forumsbenachrichtigungen werden Auktions-Ereignisse einzeln zugestellt. „3 neue Auktions-Ereignisse" ist bei 1h Haltezeit wertlos — es zählt, *welche* Auktion und *wie viel Zeit* noch bleibt.

**Nicht im Scope (Vorhaben):** E-Mail-Benachrichtigung, Web-Push via Service Worker / VAPID-Keys.

---

## 13. Bietergefecht-Hitzemesser

Bleibt erhalten (bei verdeckten Typen als „Gerüchteküche"). Score 0–100:

| Zutat | Formel | Max |
|---|---|---|
| Menge | `12 · ln(1 + gebote)` | 40 |
| Konkurrenz | `verschiedene_bieter · 6` | 30 |
| Frische | letztes Gebot < 10 Min → 30 · < 1 h → 20 · < 6 h → 10 | 30 |

**Schwellen:** ≥ 80 Glutheiß · ≥ 55 Hitzig · ≥ 30 Es köchelt · sonst Ruhig.

**Bei verdeckten Typen wird ausschließlich der Zeiger gezeigt, niemals Zahlen.**

---

## 14. Frontend-Bindung

Das Template kennt **keine Auktionstypen**. Es rendert drei Slots, deren Ausprägung sich aus den Achsen ableitet.

| Slot | Speist sich aus | Varianten |
|---|---|---|
| **A · Preis** | Achse 1 + 2 | offenes Höchstgebot + Bieterwappen · verdeckt (`?? ??? ??? €` + Gebotsanzahl) · fallender Preis (live berechnet) |
| **B · Zeit** | Achse 3 + 4 + 5 | harte Deadline · Halte-Timer („Gebot hält noch") · kein Timer |
| **C · Aktion** | Achse 6 + 7 + 15 | Gebot abgeben (mit Mindesterhöhung) · Verdecktes Gebot abgeben/ändern · Zuschlagen |

**Hero-Zahl:** Bei offenen Typen steht das aktuelle Höchstgebot groß; der Marktwert rückt kleiner nach oben. Bei verdeckten Typen übernimmt der **Marktwert** die Hero-Position.

**Bühne:** bleibt wie geliefert — statusfrei. Sortierung nach geringster Restzeit (Mitte = am dringendsten), Typ-Chip in Typfarbe, Endspurt-Badge in der letzten Stunde, Name + Live-Countdown. **Keine** manager-bezogenen Statusanzeigen (bewusste Entscheidung, siehe E19).

**Entfernt:** Kloppo-Moderationstexte, TV-Laufband.

**Datenfelder Detailseite** (alle aus der bestehenden Spielerdatenbank verlinkt, keine Duplikate anlegen): Name, Nationalität + Flagge, Alter, Größe, Positionen HP grün `#30f29c` / NP orange `#ff9f1c` inkl. Spielfeld-Darstellung wie im Spielerprofil, RL-Verein + Wappen + Liga + Ligalogo, Marktwert, Auktionstyp, aktuelles Gebot, Restzeit, Startgebot, Mindesterhöhung, Auktionsbeginn/-ende.

**Regelpanel:** Standardregeln (immer) + typspezifischer Text aus `rules_text` + ggf. Sperrgrund.
Standardregeln:
- Der Gebotsbetrag muss jederzeit vollständig auf eurem Konto verfügbar sein.
- Euer Kaderlimit darf nicht überschritten werden.
- (bei aufsteigenden Typen) Jedes Gebot muss das aktuelle Gebot um die Mindesterhöhung übertreffen.

**Bilder:** Hero-Bild wird beim Anlegen hochgeladen und **serverseitig** freigestellt (z. B. `rembg`), analog zur Browser-Demo mit Torso-Normierung und Bodenverankerung. Es landet **nie** in der Spielerdatenbank — dort bleiben die FM-CutOuts. Logo-Slots werden nie freigestellt.

---

## 15. Creator Mode

**Auktion anlegen:**
1. Spieler über **Textsuchfeld** aus der bestehenden Datenbank auswählen und verknüpfen — keine Neuanlage von Spielern
2. Preset wählen
3. Parameter überschreiben (Startpreis, Laufzeit, Mindesterhöhung, Korridorspanne …) — der Snapshot friert die Werte ein
4. Teilnahmebedingungen setzen
5. Hero-Bild hochladen (Freistellung serverseitig)
6. Medienlogo hochladen
7. `starts_at` setzen → `scheduled`

**Preset-Verwaltung:** Anlegen, Bearbeiten, Deaktivieren von Auktionstypen über die 16 Achsen. Änderungen wirken **nur auf neue** Auktionen.

---

## 16. Nicht im Scope

| Punkt | Grund |
|---|---|
| E-Mail-Benachrichtigung, Web-Push/VAPID | Vorhaben |
| Kloppo-Moderationstexte, TV-Laufband | gestrichen |
| Manager-Status auf der Bühne | Aufwand/Nutzen, nachrüstbar ohne Datenmodell-Änderung |
| Auktions-Historie, Hall of Fame, Datencenter-Anbindung | eigenes Feature |
| Tausch, Multi-Lot, Verkäufer-Hammer/Ablehnung | strukturell ausgeschlossen |
| Automatischer Auktions-Rhythmus | rein manuell durch den Creator |

---

## 17. Offene Punkte

| # | Punkt | Anmerkung |
|---|---|---|
| O1 | Rechtliche Absicherung Medienmarken | Impressum + Aufklärung + Takedown auf Zuruf; Entscheidung getroffen, Umsetzung außerhalb dieses Moduls |
| O2 | Hoeneß-Coins | Modul ist auf 5 %. Achse 12 sieht die Bedingung vor; ob Coins beim Gebot **verbraucht** oder nur **geprüft** werden, ist mit dem Coin-Modul zu klären |
| O3 | Konkrete Anschlusspunkte des „Raums" | Welche Manager/QuerySets den Auktionsstatus ausblenden müssen, ist im Bestand zu ermitteln |
| O4 | Liga-Logos und fehlende Vereinswappen | Assets nachliefern (Premier League, Liverpool, Arsenal) |
| O5 | Demo-Daten entfernen | Kimmich/Saliba-Testauktionen aus dem Template vor Produktion raus |

---

## Anhang A — Entscheidungslog

| # | Entscheidung | Begründung |
|---|---|---|
| **E01** | Show-Auktion ist ein eigenständiges Modul unter *Transfers → Auktionen*, kein Sonderfall des offenen Markts | Eigene Auktionstypen, eigene Bühnenfelder, eigene Bedingungen; ein gemeinsames Model würde ein Flag-Monster erzeugen |
| **E02** | Escrow, Kaderlimit und Buchung kommen aus dem gemeinsamen Finanz-Kern | Zwei Wahrheiten über dasselbe Konto sind der klassische Ökonomie-Killer |
| **E03** | Erlös ist eine Senke, kein Empfängerkonto | Kein abgebender Verein vorhanden; wirkt zusätzlich als Inflationsbremse |
| **E04** | Das Template kennt keine Typen, sondern drei Slots (Preis/Zeit/Aktion) | Neue Typen kosten null Frontend-Arbeit |
| **E05** | Variante A: parametrisierte Typen statt fester Dramaturgie-Typen | Mark will viele Typen und einen Creator-Mode-Baukasten |
| **E06** | Geschlossene Achsen-Grammatik (16 Achsen), Typ = Preset | Nur so ist der Baukasten echt und nicht Attrappe |
| **E07** | Kein Multi-Lot, kein Tausch, keine Ablehnung/Hammer | Mehrere Gewinner ausgeschlossen; Gebote sind reine Geldleistungen; ohne Verkäufer gibt es nichts abzulehnen |
| **E08** | Gleichstand → Losentscheid (globale Regel) | Ersetzt die Stichauktion, macht „mehrere Gewinner" strukturell unmöglich |
| **E09** | MW-Limit und Coins sind Teilnahmebedingungen (Achse 12), keine Typen | Orthogonal kombinierbar; als Typ geführt bräuchte man jede Kombination doppelt |
| **E10** | Bereichsauktion: Achse 14/15 „nächstliegend an verborgenem Ziel" | Erster Fall, in dem nicht das höchste Gebot gewinnt |
| **E11** | Bereich als **harte Hürde** mit Platzen-Möglichkeit | Ohne Scheitern wäre der Korridor Deko und alle bieten ihren Bauchwert |
| **E12** | Korridor wird vom System zufällig gezogen, Spanne im Creator Mode editierbar | Sonst spielen Manager gegen Marks Gewohnheiten statt gegen den Zufall |
| **E13** | Gewinner der Bereichsauktion zahlt sein eigenes Gebot | Sonst wäre die Gebotshöhe folgenlos |
| **E14** | Fünf Start-Presets: Halte · Undercover · Holländisch · Bereich · Blitz | Jeder stellt eine andere Frage; klassische Deadline entfällt, da vom Normalmarkt abgedeckt |
| **E15** | Keine Maximallaufzeit für die degressive Halte-Auktion | Die Treppe ist die Bremse; Achse 14 bleibt optional für künftige konstante Presets |
| **E16** | Parameter werden bei Anlage eingefroren (Snapshot) | Preset-Änderungen dürfen laufende Auktionen nicht rückwirkend verändern |
| **E17** | Harte Reservierung von Geld **und** Kaderplatz bei Gebotsabgabe | Verhindert den unlösbaren Zuschlag-ohne-Platz-Fall |
| **E18** | Achse 16 „Reservierungsfreigabe" als eigener Parameter, inkl. `sofortige_buchung` | Holländisch hätte sonst einen Sonderfall im Code erzeugt |
| **E19** | Bühne bleibt statusfrei | Aufwand/Nutzen; nachrüstbar ohne Datenmodell-Änderung. Empfehlung war das Gegenteil |
| **E20** | Sperrgrund muss auf der Detailseite vor dem Gebots-Button sichtbar sein | Minimalkompensation für E19 |
| **E21** | Ein Gebot setzt automatisch auf die Beobachtungsliste | Ein Mechanismus statt zweier paralleler Regeln |
| **E22** | Kanal ausschließlich In-Game-Glocke, ungebündelt | E-Mail/VAPID = Vorhaben |
| **E23** | Ein Beat-Task alle 60 Sekunden + Lazy-Auswertung, kein Task pro Auktion | Zustandslos, übersteht Neustarts; ETA-Tasks erzeugen Doppelzuschläge |
| **E24** | Adaptiver Beat bewusst nicht gebaut | Optimierung eines nicht existierenden Problems, fügt Zustand hinzu |
| **E25** | Idempotenz-Referenz `showauction:{id}:settle` | Doppeltes Beenden strukturell unmöglich |
| **E26** | Holländischer Preis wird berechnet, nicht getickt | Anzeige und Buchung können nicht divergieren |
| **E27** | Gebote unter Zeilensperre (`select_for_update`) | Race Conditions bei Blitz sind real |
| **E28** | Farbe ist feste Eigenschaft des Typs | Bereichsauktion ist immer creme |
| **E29** | Medienmarke ist ein freies Upload-Feld pro Auktion, unabhängig vom Typ | Bei 15 Typen sind 15 Marken nicht pflegbar |
| **E30** | Logo-Slot auf dunkler Trägerfläche | Verhindert weißes Logo auf Creme |
| **E31** | Cyan bleibt funktionale Lichtfarbe, nie Typfarbe | Design-System-Konsistenz |
| **E32** | Spieler werden händisch aus der bestehenden DB verknüpft (Textsuche), keine Neuanlage | |
| **E33** | Spieler wird beim **Anlegen** der Auktion in den „Raum" verschoben, nicht erst beim Start | Sonst wird er zwischen Anlage und Start regulär verpflichtet |
| **E34** | Sperre über Statuswechsel statt Flag | Ein Flag muss jede Query respektieren; die eine vergessene fällt zu spät auf |
| **E35** | Nach Zuschlag regulärer Transfer mit Transferhistorie „Vereinslos → Gewinnerverein", 21-Tage-Wechselsperre, keine Jugendabgabe | Deckungsgleich mit Transfersystem v2 |
| **E36** | Auktionen laufen unregelmäßig und rein manuell (1–2× pro Saison) | Kein Automatismus, kein Dauerbetrieb |
| **E37** | Historie/Hall of Fame/Datencenter sind ein eigenes Feature | Nicht Teil dieses Moduls |
| **E38** | Hitzemesser bleibt, Kloppo-Texte und TV-Laufband entfallen | Hitzemesser ist Datenableitung, kein Moderationstext |
| **E39** | Rechtefrage Medienlogos: Impressum + Aufklärung + Takedown auf Zuruf | Entscheidung von Mark, außerhalb des Moduls |
| **E40** | Undercover mit Zweitpreis-Zuschlag bewusst nicht im Start-Set | Erste Bewährungsprobe für den Creator-Mode-Baukasten |
