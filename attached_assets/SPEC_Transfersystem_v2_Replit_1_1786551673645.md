# SPEC – Transfersystem v2.0 · Master-Dokument für Replit

**Version:** 2.0 · **Stand:** 25.07.2026 · ersetzt SPEC_Transfersystem.md v1.0
**Projekt:** Blueprint · Online-Fußballmanager (Repo `Mark123179/Websoccer`, branch `main`)

---

## 0. Quellen & Rangfolge (zuerst lesen)

Dieses Dokument gehört zum Übergabepaket **`Transfermarkt-System_Prototyp.zip`** (Claude-Design). Es gilt folgende **verbindliche Rangfolge** bei Widersprüchen:

1. **`Transfersystem-standalone.html`** – der klickbare Prototyp. Verbindliche **visuelle** Referenz: Layout, Farben, Abstände, Texte, Reihenfolgen, Interaktionen. 1:1 nachbauen, jeden Reiter durchklicken.
2. **`TRANSFERSYSTEM_SPEC.md`** (im Zip) – die verbindliche **Regel- und UI-Referenz** von Claude-Design. Sie ist **aktueller als v1.0** dieses Spec-Strangs; wo sie etwas anders regelt als frühere Absprachen, **gewinnt sie** (Konfliktliste in §1).
3. **Dieses Dokument** – Backend-/Logik-Vertiefung: Zustandsautomaten, Vollzugslogik WP/SE, Reservierungs-Invarianten, Gerüchte-Wahrscheinlichkeiten, Celery/Race-Safety, Creator-Mode-Regeln, Konfigurations-Settings, Entscheidungslog. Es **ergänzt** die Design-Spec, ersetzt sie nicht.

Weitere Paket-Dateien: `README_REPLIT.md` (Arbeitsauftrag + Umsetzungsreihenfolge – befolgen), `Transfersystem.dc.html` (lesbare Quelldatei zum Nachschlagen exakter Werte/Styles), `github.md` (Screen-Map: welcher Prototyp-Bereich auf welche Repo-Dateien zeigt), `_ds/` (Design-System-Tokens), `assets/`, `support.js`.

**Grundsatz aus dem README, hier bekräftigt:** 1:1 nachbauen. Keine Interpretationen, keine „Verbesserungen", keine erfundenen Felder oder Buttons. Was nicht in Prototyp/Spec steht, wird nicht gebaut. Django-Templates + CSS im bestehenden Projekt, kein React in Produktion. Komplett Deutsch, Zahlen deutsch formatiert (`21.500.000 €`). Scouting und Beobachtungsliste bleiben unberührt und werden nur als Reiter eingehängt.

### 0.1 Assets

- **Alle Bild-Assets können direkt aus dem mitgelieferten `assets/`-Ordner übernommen werden** – Wappen (`assets/crests/<fm_inside_id>.png`), Spielerfotos (`assets/players/<id>.png`), Platzhalter (`default_player.svg` / `player_placeholder.svg` – dunkle Silhouette, nie weiß), Wettbewerbslogos (`assets/competitions/`). Die Pfade spiegeln die Repo-Struktur (`game/static/game/images/crests/`, `.../players/`, `.../competitions/`); im Produktivsystem auf die Repo-/`/assets/`-Pfade verweisen, die Dateien im Zip sind identisch.
- **Nationalflaggen:** Der Prototyp lädt `https://flagcdn.com/w40/<iso2>.png` (nur dafür braucht der Prototyp Internet). **Im Nachbau stattdessen die vorhandenen Repo-Assets `staticfiles/assets/flags/<asset_id>.png`** über die bestehende Nationalitäts-Zuordnung (`.agents/memory/nation-badge-id-calibration.md`) verwenden. Darstellung wie im Prototyp: 18×12 px, `border-radius:2px`, `object-fit:cover`, 1 px dunkler Rahmen. **Niemals Emoji-Flaggen.**
- Marktwert-Link überall: `https://www.transfermarkt.de/schnellsuche/ergebnis/schnellsuche?query=<Spielername>` (neuer Tab).

---

## 1. Konfliktauflösung: Was gegenüber v1.0 geändert ist (Design gewinnt)

| Thema | v1.0 (alt) | **v2.0 gültig (Design-Spec)** |
|---|---|---|
| Auto-Bieten / Maximalgebot | vorgesehen | **Gestrichen. Existiert nicht, nirgends anbieten oder wieder einführen.** Alle Gebote manuell. |
| „Endspurt"-Sektion (<12h) | vorgesehen | **Gestrichen.** Sektionen im Transfermarkt: nur Headliner · Gepinnt · Alle Listings. („ENDSPURT" kommt nur als Wort im Ticker-Text vor.) |
| Gerüchte-Reaktion | erzeugt Folge-News | **Keine Folge-News.** Reaktion (Dementieren / Kein Kommentar / Bestätigen, einmalig) färbt nur den Kartenrahmen: Dementi = roter 3-px-Rahmen, Bestätigt = grüner Rahmen. |
| Deal-Zusammenfassung | MW-Summen + Differenz-Anzeige | **Kein Differenz-/Paketwert-Rechner.** Nur „X gibt / Y gibt"-Gegenüberstellung mit ⇄, je Spieler MW als tm.de-Link, + Geldbeträge. |
| Mindestgebot beim Einstellen | frei | **Systemminimum 500.000 €** (UI erzwingt es). |
| Jugendspielerabgabe | „x % via Finanz-Endpunkt" abstrakt | **Konkret: 8 % gesamt** auf Ausbildungsvereine verteilt (z. B. 5 % + 3 %), **Mindestabgabe 50.000 € je Ausbildungsverein**, Abzug von der Ablöse des abgebenden Vereins. Eigengewächse: keine Abgabe. Leihen: nie. Vereinslose: keine. Tausch-Bemessung siehe §5.6. |
| Tausch-Paketgröße | unbegrenzt | **Max. 5 gegen 5 Spieler**, Geld beidseitig möglich. |
| Historie | „Überprüft"-Status öffentlich | **Kein öffentlicher Prüfstatus.** Prüfung läuft ausschließlich über Creator-Mode/Sportgericht. Historie: Paginierung 6/Seite, Tausch-Zeilen `n ⇄ n`, aufklappbare Zusammenfassung mit Jugendabgabe, rotes !-Melden-Icon, **keine** Status-/Jugendabgabe-Spalte. |
| Admin-Transfer | Summe + Abgabe konfigurierbar | **Ohne Ablöse, ohne Jugendabgabe**; Historie zeigt „— (Admin)". |
| Weiterverkaufsklausel | Backlog, Modell offen | **Phase 2, Regeln fixiert** (§9) – Weiterverkaufsbeteiligung 5–20 % + Rückkaufoption mit 48-h-Vorkaufsrecht. **Noch nicht bauen.** |
| Preisfindungs-Hilfe | Positions-/Alter-/MW-Band | zusätzlich **Positionsbarometer** (Angebot/Nachfrage je Position, täglicher Job) gewichtet die Spanne – **ohne eigene UI**. |
| Headliner-Look | offen | Nur klassischer Look (Broadcast/Hero/LED-Varianten verworfen). |

**Unverändert gültig aus v1.0** (von der Design-Spec bestätigt): kein Transferfenster, Zeitpunkte Sofort/WP/SE, Auktionsdauern 1/2/3/5/7 Tage, Verkäufer-Hammer jederzeit, Anti-Sniping +24 h unbegrenzt bei Gebot < 60 min vor Ende, Mindesterhöhung `max(100.000 €, 5 %)` gerundet auf 50.000 €, Gebote bindend + harte Reservierung, Geld fließt sofort auch bei WP-/SE-Vollzug, Wechselsperre 21 Tage, Vereinslose (MW-Mindestgebot, 24 h ab 1. Gebot, Erlös an Verband, Wechsel sofort), Leihgebühr min. 1 Mio (0 € nur Partnerverein), Leih-Limits 6 rein/6 raus/2 je Paar, Leih-Deadline 5 Spieltage vor WP/SE, Rückruf nur einvernehmlich (jederzeit, auch in der Deadline-Phase), Kaufoption bis letzte Sekunde mit Deckungsprüfung, Kader-Minimum 19 / Obergrenze aus Vereinsumfeld, kein Listing-Limit, keine Ratenzahlung, keine Kaufpflicht, keine Verkäufergebühr.

---

## 2. Feste Zahlen (Kurzreferenz, deckungsgleich mit Design-Spec §10)

| Regel | Wert |
|---|---|
| Mindestgebot beim Einstellen | 500.000 € |
| Mindesterhöhung | max(100.000 €, 5 % des Höchstgebots), gerundet auf 50.000 € |
| Anti-Sniping | Gebot < 60 min vor Ende → +24 h, unbegrenzt oft, Zähler „+24h ×n" öffentlich |
| Listing-Dauern | 1/2/3/5/7 Tage · Vereinslose: 24 h ab 1. Gebot |
| Jugendabgabe | 8 % gesamt, min. 50.000 € je Ausbildungsverein; Eigengewächse/Leihen/Vereinslose: keine |
| Wechselsperre | 21 reale Tage nach jedem Vollzug (Vermerk im Spielerprofil) |
| Anfrage-Laufzeit | 7 Tage (Deal & Leihe), jederzeit vor Annahme zurückziehbar |
| Tausch | max. 5 ⇄ 5, Geld beidseitig |
| Leihe | Gebühr ≥ 1.000.000 € (0 € nur Partnerverein) · Limits 6 rein / 6 raus / 2 je Vereinspaar |
| Leih-Deadline | 5 Spieltage vor WP bzw. SE (Datum bei Spielplan-Generierung fixiert; danach keine neuen Leihen bis zum Stichtag; Rückrufe & Optionszüge bleiben erlaubt) |
| Kader | Minimum 19 · Obergrenze aus Vereinsumfeld-Ausbaustufen (Bestandswerte im Code verifizieren, vermutlich 60/63/67/70 – Prototyp zeigt 60 als Beispielwert) · Leihspieler zählt beim aufnehmenden Verein |
| Historie | 6 Einträge/Seite |
| KI-geführte Vereine | antworten auf Anfragen binnen 24 h (KI-Transferzentrale) |

---

## 3. Sofortkauf-Flow (präzisiert, verbindlich)

Die **Sofortkaufsumme selbst ist der Hyperlink/Button** (in Headliner-Karte und Listing-Zeile). Ablauf:

1. Klick auf die Sofortkaufsumme → **Bestätigungs-Deal-Sheet** öffnet sich: „Sofortkauf zu {Summe} — sicher?" mit vollständiger Zusammenfassung (Spielerkarte, Sofortkaufsumme, Jugendabgabe-Aufschlüsselung „wer zahlt an wen", Auszahlung an Verkäufer, Transferzeitpunkt, gelbe Warnbox: bindend, Wechselsperre 21 Tage). CTA: **„Jetzt kaufen — {Summe} €"**.
2. Bestätigung → Deckungsprüfung gegen Verfügbar (= Kontostand − Reserviert). Nicht gedeckt → Fehlermeldung, kein Kauf.
3. Gedeckt → **sofortige Abwicklung in einer Transaktion**: Summe wird **direkt vom Konto abgebucht** (keine Reservierungsphase beim Sofortkauf), Jugendabgabe verteilt, **Auktion ist in diesem Moment beendet** (Status SOLD), alle Fremdgebots-Reservierungen werden freigegeben, Historie-Eintrag entsteht, Wechselsperre 21 Tage gesetzt, Pushes an Verkäufer, alle Bieter (Zuschlag an Verein X) und Pin-Beobachter.
4. Bei `timing = WP/SE`: Geld fließt trotzdem sofort (Schritt 3), nur der Spielerwechsel wird als PendingTransfer zum Stichtag vollzogen (§4.4).
5. Sofortkauf ist ausgeblendet/ersetzt, sobald das Höchstgebot ≥ Sofortkaufpreis ist (Design-Spec §2.5).

---

## 4. Datenmodell & Zustandslogik (Backend-verbindlich)

Basis ist Design-Spec §13.3 (additiv zum Bestand). Ergänzungen/Präzisierungen, damit das Backend vollständig ist:

### 4.1 Modelle (final)

- `TransferListing` – wie Design §13.3. Präzisierung: `ends_at` ist bei Vereinslosen `NULL` bis zum 1. Gebot (dann `now + 24h`); bei normalen Listings `listed_at + duration`.
- `TransferBid` – wie Design §13.3 (bindend, kein `max_amount`-Feld – Auto-Bieten existiert nicht).
- `ListingPin`, `SquadOffer`, `DealRequest` + `DealRequestPlayer` (max 5 je Seite, DB-Constraint + UI), `TransferRecord` + `TransferRecordPlayer` + `YouthLevyPayment`, `TransferReport` – wie Design §13.3.
- **`LoanListing` (Ergänzung, fehlt in Design §13.3, wird vom Leihmarkt-Reiter benötigt):** player, owner_club, fee_asking (≥ 1.000.000 bzw. 0 nur Partner), until (`WP|SE`), buy_option_price (nullable), status (`ACTIVE|LOANED|WITHDRAWN`), created_at.
- `Loan` – wie Design §13.3, plus `started_via` (LoanListing- oder DealRequest-Referenz).
- **`TransferLock` (Ergänzung):** player, locked_until, source_record. Wechselsperre braucht Persistenz; Anzeige im Spielerprofil („wechselgesperrt bis TT.MM.") ist offenes Todo laut Design §11.
- **`PendingTransfer` (Ergänzung):** record-Vorstufe für WP-/SE-Vollzug: player, from_club, to_club, execute_at (fixes WP-/SE-Datum aus Spielplan-Generierung), source (Listing/Deal/Option), status (`PENDING|EXECUTED|CANCELLED_ADMIN`).
- **`ClubPartnership` (Ergänzung):** club_a, club_b, active. Bis das Partnerverein-Feature im Vereinsprofil existiert, pflegt der Creator-Mode dieses Minimal-Modell; der 0-€-Leihgebühr-Check prüft dagegen (bei Listing-Erstellung UND bei Annahme erneut).
- **`RumorNews` (Ergänzung):** event_type, ref (GenericFK), outlet, headline, sum_mode (`EXACT|RANGE`), reaction (`NULL|DENIED|NO_COMMENT|CONFIRMED`), reaction_at, published_at. Gerüchte werden als Vereinsnews-Einträge ausgespielt (Quelle laut github.md: bestehende Vereinsnews-Templates) und im Transfermarkt als Karten-Reihe gerendert (Design §2.8, mit Spielerbild, nie Wappen).
- `ClubBudget.reserved` – wie Design §13.3. **Invariante:** `reserved` = Summe der Geldanteile aller eigenen Gebote mit Status „führend" + aller offenen gesendeten Deal-/Leihanfragen. Nach jeder Statusänderung transaktional nachführen; zusätzlich eine idempotente `recalc_reserved(club)`-Funktion als Reparatur-/Testwerkzeug bereitstellen. **Verfügbar = Kontostand − Reserviert**, live im Budget-Kopf (weiß/gold/cyan).

### 4.2 Zustandsautomat TransferListing

```
ACTIVE ─(ends_at erreicht, Höchstgebot vorhanden)────► SOLD
ACTIVE ─(Verkäufer nimmt Höchstgebot an, „Hammer")───► SOLD      # jederzeit, beendet auch jede Anti-Sniping-Kette
ACTIVE ─(Sofortkauf bestätigt, §3)───────────────────► SOLD
ACTIVE ─(ends_at erreicht, kein Gebot)───────────────► EXPIRED   # sofortiges Neu-Listen erlaubt
ACTIVE ─(Verkäufer zieht zurück, NUR bei 0 Geboten)──► CANCELLED
ACTIVE ─(Admin)──────────────────────────────────────► CANCELLED
ACTIVE ─(Gebot < 60 min vor ends_at)──► ACTIVE, ends_at += 24h, extensions += 1
```

Nach dem ersten Gebot sind min_bid, buy_now, timing und Dauer unveränderlich. Gebote sind bindend und nicht zurückziehbar; Reservierung wird nur durch Überbietung, Auktionsende oder Admin-Storno frei.

### 4.3 Zustandsautomat DealRequest

```
OPEN ─(Empfänger nimmt an; Deckungsprüfung Empfänger-Geldanteil)─► ACCEPTED → Vollzug
OPEN ─(ablehnen)─► DECLINED · ─(Initiator zieht zurück)─► WITHDRAWN · ─(7 Tage)─► EXPIRED
```

Bei OPEN ist der eigene Geldanteil des Initiators reserviert; DECLINED/WITHDRAWN/EXPIRED geben sofort frei. Annahme scheitert mit Fehlermeldung, wenn der Empfänger seinen Geldanteil nicht decken kann oder ein beteiligter Spieler inzwischen gesperrt/verliehen/verkauft ist (Re-Validierung aller Bedingungen bei Annahme). Wunschspieler der Gegenseite sind bis zur Annahme unverbindlich.

### 4.4 Vollzug & PendingTransfer (WP/SE)

- Geldflüsse (Ablöse, Jugendabgabe, Leihgebühr) werden **immer sofort** bei Zuschlag/Annahme gebucht – ausschließlich über die Buchungsschicht des Finanzsystems mit eigenen Buchungsarten, nie direkt auf `balance`.
- Bei WP/SE bleibt der Spieler bis `execute_at` beim abgebenden Verein spielberechtigt; bis dahin: kein erneutes Listen/Verkaufen/Verleihen. Erlaubte Kombination: Leihe bis WP + Verkauf zur WP. Sofortverkauf während laufender Leihe ist nicht möglich.
- Kaderzählung: eigene anwesende + ausgeliehene (rein) − verliehene (raus). Kauf/Leihe-rein blockiert, wenn Obergrenze überschritten würde; Verkauf/Leihe-raus blockiert, wenn Kader < 19 fiele. **Edge-Case WP/SE-Vollzug:** Prüfung erneut bei `execute_at`; bei Verstoß **kein Auto-Storno**, sondern automatischer Kadergrenzen-Vermerk in der Creator-Mode-Transferaufsicht + Push an beide Vereine (Verfahren/Sanktionen später mit Sportgericht-Modul).
- Jeder Vollzug (Kauf, Sofortkauf, Tausch, Optionszug, Leihstart, Leihende, Rückkehr) erzeugt automatisch den passenden Historie-Eintrag; Wechselsperre 21 Tage für **alle** durch den Vollzug wechselnden Spieler (Tausch: beide Seiten; Leih-Rückkehr: keine Sperre).

---

## 5. Backend-Regeln im Detail

### 5.1 Reservierung (Escrow)
Hart: Gebot/Anfrage nur, wenn `Verfügbar ≥ Betrag`. Bei Gebotserhöhung wird nur die **Differenz** zusätzlich reserviert. Paralleles Bieten ist möglich, aber nur bis zur Budgetgrenze. Sofortkauf bucht direkt ab (§3), ohne Reservierungsschritt.

### 5.2 Vereinslose
Dauerhafte FREE_AGENT-Listings (Filter „Vereinslose"), Mindestgebot = aktueller Marktwert, „24h ab 1. Gebot" als Countdown-Text vor dem ersten Gebot. Erlös an den Verband (Systemsenke, Buchungsart gem. Finanzsystem), Wechsel immer sofort, keine Jugendabgabe, Wechselsperre normal. Vereinslosen-Pool wird über den Creator-Mode verwaltet.

### 5.3 Leihen
Leihanfragen (aus Leihmarkt oder Deal-Builder) erscheinen unter Meine Deals → Anfragen gesendet/erhalten, Gebühr wird reserviert, 7 Tage Laufzeit. Gehalt zahlt ab Vollzug immer der Verein, bei dem der Spieler spielt (aufnehmender Verein). Leihgebühr fließt sofort an den Stammverein. Kaufoption: Preis bei Abschluss fixiert, einseitig durch Leihverein ziehbar bis zur letzten Sekunde vor Leihende, Deckungsprüfung beim Ziehen, Zug beendet die Leihe sofort und erzeugt einen Transfer-Eintrag (mit Jugendabgabe auf den Optionspreis). Rückruf nur einvernehmlich (Anfrage → Push → Annehmen/Ablehnen), jederzeit, auch während der Leih-Deadline-Phase.

### 5.4 Leih-Deadline
Ab 5 Spieltagen vor WP bzw. SE keine neuen Leih-**Abschlüsse** (Vollzug zählt). Banner im Leihmarkt mit Datum (Format wie Prototyp). Aktive LoanListings bleiben sichtbar mit „Leihmarkt pausiert bis {Datum}"-Badge; neue Leihanfragen gesperrt; offene unbeantwortete Leihanfragen laufen mit Deadline-Eintritt automatisch aus (EXPIRED, Reservierung frei).

### 5.5 Wechselsperre
21 reale Tage ab Vollzug: kein Verkauf, kein Tausch, keine neue Leihe, kein Listing. Anzeige als rote Pill im Kader-anbieten-Board (blockiert alle Aktionen) und als Vermerk im Spielerprofil (Todo außerhalb des Prototyps). Leih-Rückkehr löst keine Sperre aus.

### 5.6 Jugendspielerabgabe (Single Source of Truth)
Ein Berechnungsendpunkt `finance.calc_youth_levy(player, bemessungsgrundlage)` → `{gesamt_pct=8, betraege_je_ausbildungsverein (min. 50.000 €), summe}`. UI (Deal-Sheet, Deal-Builder-Live-Vorschau, „Auf TL stellen"-Vorschau, Historie-Aufklappung) und Buchung rufen **dieselbe** Funktion auf. Bemessung bei Tausch: je abgegebenem Spieler = MW + (Geldanteil der Gegenseite ÷ Anzahl abgegebener Spieler); reiner Tausch → MW; jede Seite zahlt für ihre eigenen abgegebenen Spieler; reicht der Geldeingang nicht, wird der Rest vom Konto abgebucht. Eigengewächse/Leihen/Vereinslose: keine Abgabe. **Abgleich-Auftrag:** Die Levy-Parameter in `SPEC_Finanzsystem.md` sind auf diese Werte (8 % gesamt, 50.000 € Mindestabgabe je Verein, Tausch-Bemessungsregel) zu synchronisieren – bei Abweichung gilt v2.0.

### 5.7 Gerüchte-Engine (Backend zur Design-§2.8-UI)
Event-getriebener Task bei `LISTING_CREATED, BID_PLACED, DEAL_SENT, TRANSFER_DONE, LOAN_DONE`:
1. **Roll 1 – erscheint eine News?** `p_news[event]`, Creator-Mode-konfigurierbar. Startwerte: LISTING_CREATED 15 % · BID_PLACED 8 % · DEAL_SENT 5 % (stille Anfragen leaken seltener als öffentliche Gebote) · TRANSFER_DONE 60 % · LOAN_DONE 40 %. Max. 1 Gerücht pro Vorgang und Tag.
2. **Outlet:** zufällig gleichverteilt aus dem `media/{name}_media.png`-Pool (keine Seriositäts-Stufen).
3. **Roll 2 – Summe:** mit `p_exact` (Start 50 %) exakte Summe, sonst Spanne: zufälliges Fenster innerhalb ±20 % der korrekten Summe, auf glatte Werte gerundet („18–22 Mio"), nie breiter.
4. Texte aus Template-Pools je Event-Typ (je ≥ 8 deutsche Varianten, Platzhalter `{spieler} {verein_a} {verein_b} {summe|spanne} {position} {alter}`).
5. Ausspielung als Vereinsnews-Eintrag + Karte in der Transfermarkt-Gerüchtereihe (Outlet-Badge cyan, rotes „TRANSFERGERÜCHT"-Label, Spielerbild). Betrifft es den eigenen Verein: einmalige Reaktion Dementieren / Kein Kommentar / Bestätigen → färbt nur den Kartenrahmen (rot/grün), **keine Folge-News**. Ticker (Design §2.1) speist sich aus denselben Events (Gebote, Verlängerungen, Vereinslose, neue Listings, Leih-Deadline).

### 5.8 Preisfindungs-Hilfe & Positionsbarometer
Vergleichsspanne aus der Transferhistorie: gleiche Hauptposition, Alter ± 2, MW-Band ± 30 %, intern zusätzlich Stärkeband ± 5 HS (HS wird nie ausgewiesen). < 3 Treffer → keine Anzeige. Täglicher Job berechnet je Position ein Angebot/Nachfrage-Barometer aus den Saison-Transfers und gewichtet die Spanne nach oben/unten – **ohne eigene UI**. Fußnote im Modal: „Orientierungshilfe — der Markt entscheidet."

### 5.9 KI-geführte Vereine
Deal-Builder zeigt „KI-GEFÜHRT" (grünes Badge). Anfragen an KI-Vereine beantwortet die KI-Transferzentrale (Finanzsystem-Spec: Schmerzgrenzen-Logik, Dry-Run-fähig) **binnen 24 h** (Annahme/Ablehnung nach Pain-Threshold-Bewertung des Pakets inkl. Geldanteilen). KI-Vereine geben keine eigenen Gebote in Spieler-Auktionen ab (v2-Umfang; Erweiterung später über KI-Transferzentrale).

---

## 6. Hintergrund-Tasks, Signals, Race-Safety

**Celery Beat:** `close_expired_listings` (minütlich, schlägt zu / lässt auslaufen) · `expire_deal_requests` (stündlich) · `end_loans` + `execute_pending_transfers` (täglich + an den fixen WP-/SE-Daten) · `release_transfer_locks` (täglich) · `position_barometer` (täglich) · `loan_deadline_guard` (schaltet Leihmarkt-Sperre an den fixierten Deadline-Daten). **Event-getrieben (Django-Signals, nicht Beat):** `rumor_roll`, Push-Versand, Ticker-Einträge.

**Race-Safety (Pflicht):** Gebot, Sofortkauf, Hammer, Annahme und Auktionsabschluss laufen jeweils in einer DB-Transaktion mit `select_for_update()` auf Listing/Deal **und** beteiligten `ClubBudget`-Zeilen. Der Abschluss-Task ist idempotent (prüft `status=ACTIVE` und `ends_at <= now` innerhalb des Locks). Sofortkauf vs. gleichzeitiges Gebot: wer den Lock zuerst hält, gewinnt; der Verlierer erhält eine saubere Fehlermeldung („Auktion soeben beendet"). Alle Zeiten in UTC speichern, Anzeige Europe/Berlin, Anti-Sniping-Fenster ausschließlich serverseitig berechnen.

---

## 7. Push-Katalog (verbindlich = Design-Spec §8)

1. Beobachteter Spieler: auf TL gestellt (inkl. Mindestgebot) / auf Leihmarkt gestellt / Kader-Status geändert. 2. Gepinntes Listing: jedes Ereignis (neues Gebot, Verlängerung, Sofortkauf, Ende). 3. Eigenes Gebot überboten / Zuschlag erhalten / Auktion beendet. 4. Deal-/Leihanfrage erhalten, angenommen, abgelehnt, zurückgezogen, abgelaufen. 5. Rückruf-Anfrage (Zustimmung erforderlich). 6. Meldung an die Transferaufsicht: Eingangsbestätigung + Ergebnis. — Zusätzlich aus §4.4: Kadergrenzen-Vermerk-Push an beide Vereine und Admin-Storno-/Admin-Transfer-Push an beide Parteien. Keine weiteren Push-Typen erfinden.

---

## 8. Creator-Mode – Transferaufsicht (Regeln fix, UI noch zu designen)

Wie Design-Spec §9, ergänzt um Backend-Details: Melde-Queue **chronologisch ohne Auto-Vorsortierung** (bewusste Entscheidung), je Meldung Transfer-Snapshot im Popup-Format, Melder + Pflicht-Begründung; Aktionen Abweisen (Push an Melder) / **In Überprüfung stellen** → Transfer erscheint im Sportgericht, kein öffentlicher Status in der Historie. Admin-Storno = vollständige Rückabwicklung (Spieler zurück, alle Geldflüsse inkl. Jugendabgabe zurückbuchen, Reservierungen freigeben, Historie-Kennzeichnung „storniert (Admin)", Wechselsperren aufheben, Pushes). Admin-Transfer ohne Ablöse/Abgabe („— (Admin)"). Auktionen vorzeitig beenden/stornieren, Vereinslosen-Pool verwalten, `ClubPartnership` pflegen, Kadergrenzen-Vermerke einsehen und „Im Sportgericht anmerken". **Settings-Panel** (statt Hardcode): `p_news`-Werte, `p_exact`, Leih-Limits, Leih-Deadline-Spieltagszahl, Wechselsperren-Dauer, Mindest-Leihgebühr, Mindestgebot-Minimum, Mindesterhöhungs-Parameter, Ticker an/aus-Default. Alle Aktionen protokolliert, nur Creator-Rolle.

---

## 9. Phase 2 – Klauseln (Regeln fixiert, NICHT bauen ohne ausdrücklichen Auftrag)

Gilt exakt Design-Spec §12: **Weiterverkaufsbeteiligung** 5–20 % (1-%-Schritte) am nächsten Verkauf, Bemessung wie Jugendabgabe (Tausch-Schlupfloch geschlossen), Abzugsreihenfolge 1. Jugendabgabe → 2. Beteiligung → 3. Rest an Verkäufer, erlischt nach dem ersten Weiterverkauf, gilt auch beim Optionszug, nie auf Leihgebühren. **Rückkaufoption** mit fixiertem Preis + Frist (Standard: Ende Folgesaison), 48-h-Vorkaufsrecht zum niedrigeren Wert aus (Höchstgebot | Rückkaufpreis) bei Verkaufsabsicht, danach Erlöschen; eine Option je Spieler. Datenmodell-Vorbereitung (`SellOnClause`, `BuybackClause`) darf angelegt werden, UI und Logik erst auf Auftrag.

---

## 10. Umsetzungsreihenfolge & Abnahme

**Reihenfolge = README_REPLIT.md:** (1) Datenmodell + Migrationen + `ClubBudget.reserved` → (2) Transfermarkt (Listen, Filter, Gebotsverlauf, Deal-Sheet, Jugendabgabe) → (3) Cronjob Auktionsabschluss + Historie + Wechselsperre → (4) Kader anbieten (Board, TL-Modal, 👁, Forum-Post) → (5) Meine Deals + Deal-Builder → (6) Leihmarkt + laufende Leihen + Leistungs-Popup → (7) Historie → (8) Push-Katalog + Ticker + Gerüchte → (9) Creator-Mode. Migrationsnummern fortlaufend nach aktuellem Repo-Stand; nach Deploy zwingend `collectstatic` (neue JS/CSS für Countdowns, Aufklapp-Verlauf, Ticker).

**Abnahme = Design-Spec §13.6 (alle 16 Punkte) plus Backend-Punkte:**
17. Reservierungs-Invariante: `recalc_reserved` liefert nach beliebiger Aktionsfolge denselben Wert wie das laufend gepflegte Feld.
18. Sofortkauf-Flow gem. §3: Summe als Link → Bestätigungs-Sheet → Direktabbuchung → Auktion sofort SOLD, Fremdreservierungen frei.
19. Race-Test: zwei gleichzeitige Gebote / Gebot + Sofortkauf in der letzten Sekunde führen nie zu Doppelzuschlag oder hängenden Reservierungen.
20. WP-/SE-Vollzug: Geld sofort, Spielerwechsel am Stichtag, Sperren bis Vollzug, Kader-Edge-Case erzeugt Vermerk statt Storno.
21. Jugendabgabe: UI-Vorschau und Buchung nutzen nachweislich denselben Endpunkt; Tausch-Bemessung stichprobengeprüft; Finanzsystem-Spec synchronisiert.
22. Anti-Sniping: Gebot 59:59 vor Ende verlängert, Gebot 60:01 vorher nicht; Hammer beendet jede Kette.
23. Leih-Deadline: Abschlüsse gesperrt, offene Anfragen laufen aus, Rückrufe/Optionszüge funktionieren weiter.

---

## Anhang A – Entscheidungslog v2.0 (Änderungen gegenüber v1.0)

| # | Entscheidung | Ersetzt/Verworfen |
|---|---|---|
| A-05 v2 | **Kein Auto-Bieten** – Feature vollständig gestrichen, nirgends wieder einführen | v1.0 A-05 (Auto-Bieten mit verdecktem Maximalgebot) |
| A-17 v2 | Gerüchte-Reaktion färbt nur den Kartenrahmen, **keine Folge-News**; Gerüchte-Karten mit Spielerbild aus den Vereinsnews | v1.0 Folge-News-Mechanik |
| A-24 | Mindestgebot beim Einstellen 500.000 € (Systemminimum) | freies Mindestgebot |
| A-25 | Jugendabgabe konkret: 8 % gesamt, min. 50.000 € je Ausbildungsverein, Tausch-Bemessung MW + anteiliges Geld; Eigengewächse/Leihen/Vereinslose frei; Finanzsystem-Spec wird darauf synchronisiert | abstrakter Verweis „x % via Endpunkt" |
| A-26 | Tausch max. 5 ⇄ 5; Deal-Zusammenfassung ohne Differenz-/Paketwert-Rechner | unbegrenzte Pakete; MW-Differenz-Anzeige |
| A-27 | Keine „Endspurt"-Sektion; Transfermarkt-Sektionen: Headliner · Gepinnt · Alle | v1.0 Endspurt (<12h) |
| A-28 | Historie mit Paginierung (6/Seite), Tausch-Zeilen, aufklappbarer Zusammenfassung; kein öffentlicher Prüfstatus – Prüfung nur via Creator-Mode/Sportgericht; Admin-Transfers ohne Ablöse/Abgabe | öffentliches „Überprüft"-Flag; konfigurierbare Admin-Transfer-Summe |
| A-29 | Sofortkauf-Flow: Summe ist der Hyperlink → Bestätigungs-Deal-Sheet → Direktabbuchung → Auktion sofort beendet, Fremdreservierungen frei | Sofortkauf ohne definierten Bestätigungs-/Buchungsfluss |
| A-30 | Assets direkt aus dem Paket-`assets/`-Ordner (spiegelt Repo-Pfade); Flaggen im Nachbau aus `staticfiles/assets/flags/` statt flagcdn, nie Emoji | – |
| A-31 | Phase-2-Klauseln (Weiterverkaufsbeteiligung 5–20 %, Rückkaufoption mit 48-h-Vorkaufsrecht) regelseitig fixiert, Umsetzung nur auf ausdrücklichen Auftrag | v1.0 A-21 „Modell offen" |
| A-32 | Preisfindungs-Hilfe mit unsichtbarem Positionsbarometer (täglicher Job); KI-geführte Vereine antworten binnen 24 h via KI-Transferzentrale | – |

Alle übrigen v1.0-Entscheidungen (A-01–A-04, A-06–A-16, A-18–A-20, A-22, A-23) gelten unverändert fort.
