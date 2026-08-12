# TRANSFERSYSTEM — Spezifikation für den 1:1-Nachbau (Websoccer/MatchEngine)

> **Verbindlich.** Dieses Dokument beschreibt exakt den Stand des Prototyps `Transfersystem.dc.html`.
> Der Nachbau in der Django-App erfolgt **1:1 ohne Interpretationen, Ergänzungen oder Weglassungen**.
> Der Prototyp ist die visuelle Referenz (Layout, Farben, Abstände, Texte); dieses Dokument die Regel-Referenz.
> Bestehende Bereiche **Scouting** und **Beobachtungsliste** bleiben unberührt und werden nur als Reiter eingehängt.

---

## 1. Rahmen

- Einstieg über den bestehenden Management-Bereich; Content-Bereich (ohne Sidebar/Kalender) wie im Prototyp.
- **7 Reiter in einer Leiste:** Transfermarkt · Leihmarkt · Meine Deals (mit orangenem Zähler-Badge = offene erhaltene Anfragen) · Kader anbieten · Historie · Scouting (Bestand) · Beobachtungsliste (Bestand).
- **Budget-Kopf rechts oben, immer sichtbar, live:**
  - Kontostand (weiß) · Reserviert (gold) · Verfügbar (cyan, hervorgehobene Box) = Kontostand − Reserviert.
  - Reserviert steigt bei: eigenem Höchstgebot (nur Differenz bei Erhöhung), gesendeter Deal-Anfrage (Geldanteil), gesendeter Leihanfrage (Gebühr).
  - Reserviert sinkt bei: Überbotenwerden, Zurückziehen einer Anfrage, Auktionsende, Admin-Storno, Vollzug (dann echte Buchung vom Konto).
- Alle UI-Texte deutsch, Zahlen deutsch formatiert (`21.500.000 €`). Design-System „MatchEngine" (dunkle Glass-Panels, Cyan-Hairlines, Grün = positiv, Gold = Warnung/Zeit, Rot = Gefahr/Live).
- **Verlinkungen überall:** Spielername/Spielerbild → Spielerprofil (`player_detail`); Vereinsname/Wappen → Vereinsprofil; Marktwert → transfermarkt.de-Schnellsuche mit Spielernamen (neuer Tab). Cyan-Hover auf allen klickbaren Namen.
- **Flaggen als Bilder** (flagcdn bzw. lokale Assets), nie als Emoji. Spieler ohne Foto: dunkler Silhouetten-Platzhalter (`player_placeholder.svg`), nie weiß.
- **Positionsfarben immer:** Hauptposition(en) grün `#30f29c`, Nebenposition(en) gelb `#ffd166`; bis zu 3 HPs und 3 NPs als Kommaliste (z. B. „ZM,OM · DM"). Tooltips „Hauptposition"/„Nebenposition".
- Spielernamen in kompakten Listen gekürzt: „J. Rieder".

## 2. Transfermarkt (Reiter 1)

### 2.1 Transfer-Ticker
- Rotes „TRANSFER-TICKER"-Label mit blinkendem Punkt, Endlos-Laufband (~38 s/Loop).
- Inhalt: Gebots-Erhöhungen, Endspurt-Meldungen, Anti-Sniping-Verlängerungen, Vereinslosen-Angebote, neue Listings, Leih-Deadline.
- **Farbregeln im Ticker:** Spielernamen cyan + klickbar (Spielerprofil), Vereinsnamen grün + klickbar (Vereinsprofil), Deadlines/Fristen gold-gelb, Rest gedämpftes Weiß.
- Per Tweak/Einstellung abschaltbar.

### 2.2 Headliner
- Überschrift „HEADLINER — Die 3 als Nächstes ablaufenden Auktionen".
- Genau 3 Karten (die zeitlich nächsten Auktionsenden), pulsierender roter Schein (Animation ~2,8 s).
- Karte: roter Farbverlaufs-Strich oben; Badge „LIVE-AUKTION" (rot, nowrap); optional Badge „+24h ×n" (gold, nowrap, **Hover-Tooltip:** „Anti-Sniping: Jedes Gebot in der letzten Stunde verlängert die Auktion automatisch um 24 Stunden — ×n zeigt, wie oft bereits verlängert wurde."); großer Countdown rechts oben.
- Countdown-Farben (gilt überall): < 1 h rot + blinkend · < 12 h gold · sonst weiß; Format `MM:SS min` unter 1 h, `Xh Ym`, `X T Y h`; „beendet" nach Ablauf; Vereinslose ohne Gebot: „24h ab 1. Gebot".
- Inhalt: Spielerfoto (72×90, klickbar), Name (klickbar), Flagge, Alter, HP/NP farbig, Wappen + Verkäufer (klickbar), MW als tm.de-Link + Trendpfeil (▲ grün / ▼ rot), Höchstgebot (grün, groß) mit Bieterverein („Du führst!" grün bei eigener Führung), Sofortkauf-Preis, „📌 n gepinnt".
- Buttons: „Bieten" (cyan, primär) + „Sofortkauf" (ghost) bzw. deaktiviert „Kein Sofortkauf".

### 2.3 Filterleiste (kompakt, einzeilig umbruchfähig)
- Chips „Alle / Vereinsspieler / Vereinslose"; Chips „Zeitpunkt: alle / Sofort / Winterpause / Saisonende"; Positions-Dropdown (TW…ST); MW-von/bis-Eingaben (Mio).
- **Jeder aktive Filter-Chip ist per erneutem Klick abwählbar** (zurück auf „alle"). Gilt für alle Chip-Filter im gesamten System (auch Leihmarkt).
- Rechts Zähler „X von Y Listings sichtbar". Filter wirkt **nur** auf „Alle Listings" (Headliner und Gepinnt bleiben immer sichtbar).

### 2.4 Listing-Sektionen
- **Gepinnt** (cyan Titel): eigene markierte Listings. Pin-Button (📌) je Zeile toggelt; Pin = Push-Abo für alle Ereignisse des Listings. Öffentlich sichtbar: Anzahl Pins.
- **Alle Listings**: Tabelle mit Spalten Spieler (Foto, Flagge, Name, Alter, HP/NP) · Verein (Wappen, Name, „RL: Real-Life-Verein") · Marktwert (tm.de-Link + Trend) · Zeitpunkt (Pill: Sofort cyan / WP & SE gold; darunter „auf TL seit …") · Mindestgebot · Höchstgebot (grün, unterstrichen, **Klick klappt Gebotsverlauf auf**) · Sofortkauf · Restzeit · 📌 Pins · Aktion.
- Aktion: „Bieten" (kompakt) bei fremden Listings; „Eigenes" (Label) bei eigenen. Keine horizontale Scrollbar bei ≥ ~1010 px.
- **Gebotsverlauf (aufklappbar):** Verein · Betrag (grün) · Zeitstempel, neueste zuerst; „Noch keine Gebote." wenn leer.

### 2.5 Auktions-/Gebotsregeln
- **Mindestgebot beim Einstellen: ≥ 500.000 €** (Systemminimum; UI erzwingt es).
- Mindesterhöhung: `max(100.000 €, 5 % des Höchstgebots)`, gerundet auf 50.000 €.
- **Gebote sind bindend**, nicht zurückziehbar; Betrag wird sofort hart reserviert. Freigabe nur durch Überbietung, Auktionsende oder Admin-Storno.
- **Kein Auto-Bieten.** (Feature existiert nicht — nirgends anbieten.)
- **Anti-Sniping:** Jedes Gebot < 60 min vor Ende verlängert um +24 h; Zähler „+24h ×n" öffentlich; unbegrenzt oft.
- **Sofortkauf:** optionaler Festpreis; Kauf beendet Auktion sofort, alle fremden Reservierungen werden freigegeben. Ausgeblendet/ersetzt sobald Höchstgebot ≥ Sofortkaufpreis.
- **Vereinslose Spieler:** Sektion „Vereinslose" via Filter; keine Laufzeit bis zum ersten Gebot, dann 24-h-Auktion; Erlös geht an den Verband; Wechsel sofort; keine Jugendabgabe.
- **Nach Zuschlag/Sofortkauf:** Wechselsperre 21 Tage (Vermerk **im Spielerprofil**), Historie-Eintrag wird immer erzeugt, Beobachter + Bieter erhalten Push.

### 2.6 Deal-Sheet „Gebot abgeben / Sofortkauf" (Modal, ohne Scrollbalken)
- Spielerkarte (Foto, Name, Alter, HP/NP, Verein) · Gebotsfeld (€) mit Hinweis „Mindestens X · Mindesterhöhung …".
- Abrechnungsblock: Gebotssumme · **Jugendspielerabgabe** (Summe, gold) mit Aufschlüsselung je Ausbildungsverein („↳ Verein · x % · Betrag") · „Auszahlung an Verkäufer" (grün) · Transferzeitpunkt (cyan). Vereinslose: Hinweis „Erlös geht an den Verband. Wechsel sofort."
- Gelbe Warnbox: bindend, harte Reservierung, Wechselsperre 21 Tage. CTA „Gebot verbindlich abgeben" / „Jetzt kaufen — X €".

### 2.7 Jugendspielerabgabe (global gültige Regeln)
- Gesamtabgabe 8 % der Ablöse, verteilt auf Ausbildungsvereine (z. B. 5 % + 3 %); Abzug direkt von der Ablöse des abgebenden Vereins.
- **Mindestabgabe je Ausbildungsverein: 50.000 €**, auch wenn die Prozente weniger ergeben (durch das 500.000-€-Mindestgebot unkritisch).
- **Bei Tauschgeschäften:** Bemessungsgrundlage je abgegebenem Spieler = Marktwert + anteiliger Geldanteil der Gegenseite (Geld ÷ Anzahl abgegebener Spieler). Reiner Tausch ohne Geld → Marktwert. Jede Seite zahlt für ihre eigenen abgegebenen Spieler. Reicht der Geldeingang nicht, wird der Rest vom Konto abgebucht.
- Eigengewächse: keine Abgabe. Leihen: nie Abgabe.
- Anzeige immer transparent: „Wer zahlt an wen" + tatsächlicher Geldfluss („erhält X − Y Abgabe = Z werden tatsächlich überwiesen").

### 2.8 Transfergerüchte
- Karten-Reihe (horizontal scrollbar) aus den **Vereinsnews**: Outlet-Badge (cyan), rotes Label „TRANSFERGERÜCHT", Schlagzeile, **Spielerbild** rechts eingeblendet (nie Wappen).
- Betrifft ein Gerücht den eigenen Verein: 3 Reaktions-Buttons **Dementieren / Kein Kommentar / Bestätigen** (einmalig).
- Reaktion erzeugt **keine Folge-News**; sie färbt nur den Kartenrahmen: Dementi = fetter roter Rahmen (3 px), Bestätigt = fetter grüner Rahmen.

## 3. Leihmarkt (Reiter 2)

- Banner: „LEIHMARKT OFFEN — Leih-Deadline zur Winterpause: 28.11.2026 (5 Spieltage vor WP)"; danach keine neuen Leihen bis WP; Rückrufe & Optionszüge jederzeit.
- Tabelle: Spieler (Foto/Flagge/Name/Alter/HP-NP) · Stammverein (Wappen, klickbar) · Leihgebühr (0 € grün + Badge „Partnerverein") · Dauer (bis WP 20.12. / bis SE 24.05.) · Kaufoption · MW (tm.de-Link) · Button „Leihanfrage".
- Filter-Chips: Alle / bis WP / bis SE / mit Kaufoption (abwählbar).
- Regeln: Mindest-Leihgebühr 1.000.000 € (0 € nur bei Vereinspartnerschaft); Leihspieler zählt beim aufnehmenden Verein auf die Kadergrenze; Limits max. 6 rein / 6 raus, max. 2 je Vereinspaar.
- **„Leihanfrage" erzeugt einen Eintrag unter Meine Deals → Anfragen gesendet** (Gebühr wird reserviert, 7 Tage Laufzeit, Zusammenfassungs-Popup wie bei Deals). Eingehende Leihanfragen erscheinen unter „Anfragen erhalten".

## 4. Meine Deals (Reiter 3) — 5 Segmente (Chips mit Badge)

### 4.1 Meine Gebote
- Zeile: Spieler · Verkäufer · Mein Gebot · Höchstgebot (grün) · Status-Pill „Führend" (grün) / „Überboten" (gold) + Reservierungstext · Countdown · Aktion.
- Aktion: „Erhöhen" (öffnet Deal-Sheet vorbefüllt) — **bei beendeter Auktion stattdessen nur rotes ×** (aus Liste entfernen).
- Fußnote: Gebote bindend, Freigabe nur durch Überbietung/Ende/Admin-Storno.

### 4.2 Anfragen erhalten
- Gleiches Zeilenformat wie „gesendet": Wappen · „Von X · Typ" · „Zeitpunkt: …" (cyan) · Live-Countdown (gold, `T h m s`) · Buttons Annehmen (grün) / Ablehnen (rot) direkt in der Zeile.
- **Klick auf die Zeile → Deal-Zusammenfassungs-Popup** (siehe 4.6) mit Annehmen/Ablehnen; Manager-Nachricht als kursives Zitat.
- Annahme: Vollzug sofort, Geldflüsse buchen, **Historie-Eintrag erzeugen** (Transfer- bzw. Leih-Historie), Wechselsperre 21 Tage, Absender-Push.

### 4.3 Anfragen gesendet
- Zeile: Wappen · „An X · Typ (Tausch / Geld / Tausch/Geld / Leihanfrage)" · „Zeitpunkt: … (cyan) · Reserviert: … (gold)" · Live-Countdown „läuft ab in T h m s" (sekündlich) · „Zurückziehen".
- Anfragen laufen nach **7 Tagen** ab. Zurückziehen jederzeit vor Annahme → Reservierung sofort frei.
- Button „Neue Anfrage (Deal-Builder)". Klick auf Zeile → Zusammenfassungs-Popup (mit „Anfrage zurückziehen").

### 4.4 Kaufoptionen
- Links „Eigene Kaufoptionen": Spieler (Flagge, HP/NP farbig), fixierter Optionspreis, ziehbar bis Saisonende letzte Sekunde; Button „Option ziehen" → Deal-Sheet (fixierte Summe, Jugendabgabe-Aufschlüsselung, Warnbox „beendet Leihe sofort, erzeugt Transfer-Eintrag, Deckungsprüfung beim Ziehen, Wechselsperre 21 Tage"). Zug bucht Konto + **erzeugt Historie-Eintrag**.
- Rechts „Fremde Optionen auf eigene Spieler": rein informativ (gelber Rahmen).

### 4.5 Laufende Leihen
- Zwei Panels „Verliehen (raus)" / „Ausgeliehen (rein)". Karte: **Spielerbild vorn**, Flagge + Name, Pfeil →/← mit **Wappen vor dem Vereinsnamen**, Zeile Alter · HP/NP farbig · MW, Zeile Konditionen (bis, Gebühr, Kaufoption grün). Badge „mit Option".
- „Zurückrufen" nur einvernehmlich (Leihverein muss zustimmen, Push).
- **Klick auf die Karte → Leistungs-Popup seit Leihbeginn:** Tabelle je Wettbewerb (Logo) mit Spiele · Tore (grün) · Vorlagen · Minuten · Ø-Note (cyan) · 🟨 · 🟥 + Gesamtzeile (Ø-Note spielgewichtet).

### 4.6 Deal-Zusammenfassungs-Popup (gesendet & erhalten identisch)
- Kopf: Wappen + „Deal-Zusammenfassung — Anfrage an/von X"; Unterzeile Typ · Zeitpunkt (cyan) · Countdown (gold) · ggf. Reserviert (gold).
- **Keine Differenz-/Paketwert-Berechnung.** Stattdessen „Zusammenfassung des Deals": links „SC Freiburg gibt", rechts „X gibt", verbunden mit ⇄; je Spieler: Flagge, Name (klickbar), Alter, HP/NP farbig, MW (tm.de-Link); „+ Geldbetrag" (grün).
- Darunter „Jugendspielerabgabe — wer zahlt an wen" (zwei Spalten je Seite, Zeilen „Spieler ↳ an Verein (x %) − Betrag"; „Keine — nur Eigengewächse im Paket.") und grüne Abrechnungsbox mit tatsächlichem Geldfluss je Seite.
- Fußzeile: Schließen + (gesendet) Zurückziehen bzw. (erhalten) Annehmen/Ablehnen.

## 5. Deal-Builder (Modal „Neue Anfrage")

- **Zielauswahl als Dropdown-Kaskade:** Land (mit Flagge) → Liga (mit Liga-Logo) → Verein (mit Wappen neben dem Select). Feld „Geführt von": Manager-Name (cyan Pill) oder Badge „KI-GEFÜHRT" (grün). Ligen ohne angebundene Vereine: Hinweistext.
- **Transferzeitpunkt-Chips: Sofort / Winterpause / Saisonende** (Pflichtangabe, default Sofort) — wird in Anfrage, Listenzeile und Popup angezeigt.
- Zwei Paket-Spalten (eigenes Paket / Wunschpaket), je mit Segment-Reitern **Profis / U21** und **scrollbarer Spielerliste** (ausgelegt auf bis zu 70 Spieler). Zeile: Foto, Flagge, gekürzter Name, Alter, HP/NP farbig (bis 3/3), MW; Auswahl links cyan, rechts gold.
- **Max. 5 Spieler je Seite** (höchstens 5-gegen-5); 6. Klick → Hinweis-Toast. Zähler „n/5" je Spalte.
- Geldbetrag beidseitig frei (eigenes Geld + „Geld vom Empfänger"). Wunschspieler sind unverbindlich markiert — bindend erst durch Annahme der Gegenseite.
- Unten „Zusammenfassung des Deals" (wie 4.6, live) inkl. Jugendabgabe-Vorschau und Geldfluss.
- Senden nur wenn beide Seiten Inhalt haben (Spieler und/oder Geld); reserviert den eigenen Geldanteil; Ziel-Manager erhält Push (KI: Antwort binnen 24 h); Anfrage erscheint sofort unter „Anfragen gesendet".
- Gesperrte Spieler (verliehen, wechselgesperrt) sind nicht wählbar.

## 6. Kader anbieten (Reiter 4)

- Statusboard („Kommunikation, kein Zwang"), Segment-Reiter **Profis / U21**, Kaderstand-Zeile (Minimum 19 · Obergrenze 60 · verliehen/ausgeliehen).
- Zeile je Spieler: Foto, Name, Alter · HP/NP farbig · MW · Hinweis-Pill (gold „verliehen bis SE" / rot „wechselgesperrt bis …" — blockiert alle Aktionen) · Status-Chips **Alle Angebote / Tausch / Geld / Tausch/Geld / Leihe / UVK** (Standard: UVK) · **👁 n** · „Auf TL stellen".
- **👁-Klick** klappt Beobachter-Leiste auf: Chips mit Wappen + Vereinsname + Manager-Name (klickbar), „+ n weitere"; darunter Hinweis: Beobachter erhalten automatisch Push bei „auf TL gestellt (inkl. Mindestgebot)", „auf Leihmarkt gestellt", „Status geändert".
- „Speichern" persistiert das Board (öffentlich sichtbar) + Push an Beobachter geänderter Spieler. „Forum-Post generieren" → Modal mit fertig formatiertem BB-Code-Text (alle Spieler mit Status ≠ UVK) + „In Zwischenablage kopieren".

### 6.1 Modal „Auf Transfermarkt stellen" (ohne Scrollbalken, 680 px)
- Mindestgebot (€, **≥ 500.000 €**) · Sofortkaufpreis (optional) · Zeitpunkt-Chips (Sofort/WP/SE) · Dauer-Chips (1/2/3/5/7 Tage).
- Zwei Spalten: **Preisfindungs-Hilfe** (Spanne vergleichbarer Transfers + 3 Referenzen; bei < 3 Treffern: „keine Anzeige statt schlechter Daten"; Fußnote „Orientierungshilfe — der Markt entscheidet". **Im Hintergrund fließt ein Positionsbarometer in die Berechnung ein:** Angebot/Nachfrage je Position aus den Transfers der laufenden Saison gewichtet die Spanne nach oben/unten — das Barometer bekommt KEINE eigene UI) und **Jugendspielerabgabe bei Verkauf** (je Ausbildungsverein Prozent + €-Abzug live aus dem Mindestgebot, einzeilig; „Deine Auszahlung" grün; Eigengewächs: „keine Abgabe"; Hinweis Mindestabgabe 50.000 €).
- Grüne Checkliste: nicht verliehen · keine Wechselsperre · kein offener Vollzug · Kaderminimum gewahrt · Mindestgebot ≥ 500.000 €.
- „Listing erstellen" → Listing aktiv, Wechsel zum Transfermarkt, Beobachter-Push.

## 7. Historie (Reiter 5) — öffentlich einsehbar

- Chips **Transfers / Leihen** + Toggle „Nur meine" (abwählbar). **Seitennummerierung** (6 Einträge/Seite, Seiten-Chips, „Seite x von y · n Transfers"); auf lange Saisons ausgelegt.
- **Transfers-Tabelle:** Datum · Spieler (Foto, Flagge, klickbarer Name, Alter, HP/NP farbig) · Von → Nach (Wappen + klickbare Vereinsnamen) · Ablöse · Zeitpunkt · rotes **!**-Icon (rund, Hover-Glow, Tooltip „Transfer melden"). **Keine Jugendabgabe-Spalte.**
- **Tauschgeschäfte** als eigener Zeilentyp: „Tauschgeschäft · n ⇄ n Spieler", Vereine mit ⇄, Ablöse-Spalte = Geldanteil („+ X €" / „reiner Tausch").
- **Klick auf Zeile klappt Zusammenfassung auf** (Format wie 4.6): beide Seiten mit Spielern (Flagge/Alter/HP-NP/MW-Link) + Geld, darunter „Jugendspielerabgabe" (Zeilen „**Verein** zahlt: Spieler ↳ an Ausbildungsverein (x %) − Betrag", nur sofern angefallen) + Transferzeitpunkt.
- Admin-Transfers: Ablöse „— (Admin)". **Jeder Vollzug (Kauf, Sofortkauf, Tausch, Optionszug) erzeugt automatisch einen Eintrag.**
- **Leihen-Tabelle:** Datum · Spieler (Foto/Flagge/Name klickbar/Alter/HP-NP) · Stammverein → Leihverein · Gebühr · Bis · Typ (Leihstart cyan / Kaufoption gezogen grün / Rückkehr grau). Jeder Leihvollzug erzeugt einen Eintrag.
- „Melden" → Modal mit Pflicht-Begründung → geht an die Transferaufsicht (Creator-Mode), Melder erhält Ergebnis-Push.

## 8. Push-Nachrichten (Auslöser-Katalog)

1. Beobachteter Spieler: auf TL gestellt (inkl. Mindestgebot) / auf Leihmarkt gestellt / Kader-Status geändert.
2. Gepinntes Listing: jedes Ereignis (neues Gebot, Verlängerung, Sofortkauf, Ende).
3. Eigenes Gebot überboten / Zuschlag erhalten / Auktion beendet.
4. Deal-/Leihanfrage erhalten, angenommen, abgelehnt, zurückgezogen, abgelaufen.
5. Rückruf-Anfrage bei Leihen (Zustimmung erforderlich).
6. Meldung an Transferaufsicht: Eingangsbestätigung + Ergebnis.

## 9. Creator-Mode — Transferaufsicht (noch zu designen, Regeln stehen fest)

- **Melde-Queue:** alle „Melden"-Einreichungen mit Transfer-Snapshot (Zusammenfassung wie 4.6), Melder, Pflicht-Begründung, Zeitstempel.
- Aktionen je Meldung: **Abweisen** (Push an Melder) · **In Überprüfung stellen** → der Transfer erscheint im **Sportgericht** (bestehender Bereich); es gibt **keinen öffentlichen Status in der Historie** — die Prüfung läuft ausschließlich über Sportgericht/Creator-Mode.
- **Admin-Storno:** macht einen Transfer rückgängig (Spieler zurück, Geldflüsse inkl. Jugendabgabe zurückbuchen, Reservierungen freigeben, Historie-Eintrag als „storniert (Admin)" kennzeichnen, Wechselsperre aufheben, Pushes an beide Vereine).
- **Admin-Transfer:** manueller Transfer ohne Ablöse (in Historie „— (Admin)"), ohne Jugendabgabe.
- Aufsicht kann Auktionen vorzeitig beenden/stornieren (Reservierungen freigeben) und Vereinslosen-Pool verwalten.
- Sichtbarkeit: nur Creator-Rolle; alle Aktionen werden protokolliert.

## 10. Feste Zahlen (Kurzreferenz)

| Regel | Wert |
|---|---|
| Mindestgebot beim Einstellen | 500.000 € |
| Mindesterhöhung | max(100.000 €, 5 %), gerundet auf 50.000 € |
| Anti-Sniping-Fenster / Verlängerung | 60 min / +24 h, unbegrenzt |
| Listing-Dauern | 1 / 2 / 3 / 5 / 7 Tage; Vereinslose 24 h ab 1. Gebot |
| Jugendabgabe | 8 % gesamt (z. B. 5 % + 3 %), min. 50.000 € je Ausbildungsverein |
| Wechselsperre nach Transfer | 21 Tage (Vermerk im Spielerprofil) |
| Deal-/Leihanfrage-Laufzeit | 7 Tage, jederzeit zurückziehbar |
| Tausch | max. 5 gegen 5, Geld beidseitig möglich |
| Leihe | Mindestgebühr 1.000.000 € (0 € nur Partnerverein), Limits 6 rein/6 raus, 2 je Vereinspaar |
| Leih-Deadline | 28.11.2026 (5 Spieltage vor WP), danach bis WP keine neuen Leihen |
| Kader | Minimum 19, Obergrenze 60; Leihspieler zählt beim aufnehmenden Verein |
| Historie-Paginierung | 6 Einträge/Seite |

## 11. Bewusst NICHT enthalten / offene Punkte

- **Kein Auto-Bieten** (abgeschafft, nirgends wieder einführen).
- Kein „Endspurt"-Bereich, keine Differenz-/Paketwert-Anzeige, keine Folge-News bei Gerüchte-Reaktionen, keine Jugendabgabe-Spalte in der Historie.
- Headliner nur im klassischen Look (Broadcast/Hero/LED-Varianten verworfen).
- **Todo (außerhalb dieses Prototyps):** „Angebot machen"-Shortcut im Spielerprofil (öffnet Deal-Builder vorbefüllt); Wechselsperre-Anzeige im Spielerprofil; Verzahnung Beobachtungsliste ↔ Pins; Creator-Mode-UI (§ 9).

---

## 12. Klauseln (Phase 2 — Regeln festgelegt, UI noch nicht im Prototyp)

Beide Klauseln werden **beim Verkauf im Deal-Sheet bzw. Deal-Builder fixiert**, sind
**öffentlich in der Historie sichtbar** und wandern in das Spielerprofil des Spielers.

### 12.1 Weiterverkaufsbeteiligung
- Verkäufer behält **5–20 %** (frei verhandelbar, in 1-%-Schritten) am **nächsten** Verkauf des Spielers.
- **Bemessungsgrundlage = Gesamtgegenwert des Weiterverkaufs** (identische Logik wie die Jugendabgabe, § 2.7):
  - Verkauf gegen Geld → x % der Ablöse.
  - Tausch mit Geld → x % von (Marktwertsumme der erhaltenen Spieler + erhaltener Geldanteil).
  - **Reiner Tausch → x % der Marktwertsumme der erhaltenen Spieler, zahlbar in Geld vom Konto.**
  - Begründung: ohne diese Regel wäre der Tausch das Schlupfloch, um jede Klausel zu umgehen — genau das Problem, das bei der Jugendabgabe schon so gelöst ist.
- **Reihenfolge der Abzüge beim Weiterverkauf:** 1. Jugendabgabe (8 %, min. 50.000 € je Ausbildungsverein) → 2. Weiterverkaufsbeteiligung → 3. Restbetrag an den verkaufenden Verein.
- Gilt nur für den **ersten** Weiterverkauf, danach erlischt sie. Keine Beteiligung an Leihgebühren.
- Bei Optionszug einer Kaufoption gilt sie ebenfalls (Optionspreis = Ablöse).
- **Anzeige:** eigene Zeile im Abrechnungsblock des Deal-Sheets und im Zusammenfassungs-Popup unter „Wer zahlt an wen": „↳ an <Verein> · Weiterverkaufsbeteiligung x % · Betrag" (gold).

### 12.2 Rückkaufoption
- Verkäufer sichert sich beim Verkauf einen **fixierten Rückkaufpreis** + **Frist** (Standard: bis Ende der Folgesaison).
- Ziehbar jederzeit innerhalb der Frist; Zug erzeugt einen normalen Transfer (Historie-Eintrag, Wechselsperre 21 Tage, Jugendabgabe auf den Rückkaufpreis).
- **Weiterverkauf-Schutz (einzige exploit-freie Variante):** Will der haltende Verein den Spieler verkaufen oder listen, erhält der Optionsinhaber ein **Vorkaufsrecht über 48 h** — er kann zum **niedrigeren** Wert aus (Höchstgebot | Rückkaufpreis) zuschlagen. Läuft das Fenster ungenutzt ab, erlischt die Rückkaufoption.
- Auktion/Listing des Spielers bleibt in dieser Zeit gesperrt; der Optionsinhaber erhält Push, der haltende Verein sieht den laufenden 48-h-Countdown.
- Nur **eine** Rückkaufoption je Spieler gleichzeitig; sie erlischt mit Ablauf der Frist, mit dem Zug oder mit ungenutztem Vorkaufsrecht.

### 12.3 UI-Erweiterungen für Phase 2 (wenn gebaut)
- Deal-Sheet / Deal-Builder: aufklappbarer Block „Klauseln" mit Slider „Weiterverkaufsbeteiligung 0–20 %" und Feldern „Rückkaufpreis" + „Frist" (Chips: Ende dieser Saison / Ende Folgesaison).
- Spielerprofil: Klausel-Badges („15 % Weiterverkauf an SC Freiburg", „Rückkauf 9.000.000 € bis 24.05.2028").
- Meine Deals → neues Segment „Klauseln" (eigene aktive Klauseln + fremde Klauseln auf eigenen Spielern), gleiche Panel-Optik wie § 4.4.
- Historie: Klausel-Zeilen in der aufgeklappten Zusammenfassung; Vorkaufsrechts-Fenster als goldene Statuszeile.

---

## 13. Umsetzungshinweise für den Nachbau (Django/Replit)

### 13.1 Was der Prototyp ist
- `Transfersystem.dc.html` (bzw. `Transfersystem-standalone.html`) ist ein **vollständig klickbarer Frontend-Prototyp** mit Mock-Daten (React-artige Logik in einer Klasse, alle Styles inline).
- **Alle Layouts, Farben, Abstände, Schriftgrößen, Texte, Icons, Reihenfolgen und Interaktionen sind verbindlich** und werden 1:1 in Django-Templates + CSS übertragen. Keine Interpretation, keine „Verbesserungen", keine erfundenen Zusatzfelder.
- Die Mock-Daten (Spielernamen, Vereine, Beträge) sind **Beispiele** — die Struktur dahinter ist verbindlich, die Werte kommen aus der DB.

### 13.2 Design-Tokens (aus dem Design-System „MatchEngine")
| Zweck | Wert |
|---|---|
| Panel-Fläche | `rgba(9,23,34,.82)` |
| Hairline | `rgba(44,231,255,.18)`, hover/aktiv `rgba(44,231,255,.38)` |
| Schatten | `0 18px 70px rgba(0,0,0,.46)` |
| Text | `#f4fbff` · muted `rgba(244,251,255,.64)` · faint `rgba(244,251,255,.38)` |
| Cyan (funktional) | `#22e6ff` |
| Grün (positiv/HP) | `#30f29c` |
| Gold (Zeit/Warnung/NP) | `#ffd166` |
| Rot (Gefahr/Live) | `#ff5570`, Text-Rot `#ff8ba0` |
| Primärbutton | `linear-gradient(180deg,#1bd9ee,#06879a)` + `1px solid rgba(93,249,255,.46)` |
| Badge-Orange | `linear-gradient(180deg,#ff9f1c,#d85d00)` |
| Radius | 8px (alles), 999px (Pills/Badges), 3–4px (Mini-Badges) |
| Schrift | Inter; UI 700, Headings/Werte/Badges 900; Micro-Labels 9,5–11px / 900 / uppercase / +0.4–0.8px |
| Card-Padding / Gap | 18px / 12–14px |

### 13.3 Datenmodell (Minimum, additiv zum Bestand)
- `TransferListing`: player, seller (nullable = vereinslos), min_bid (≥ 500.000), buy_now (nullable), timing (`SOFORT|WP|SE`), created_at, ends_at (nullable bis 1. Gebot), extensions (int), status (`ACTIVE|SOLD|CANCELLED|EXPIRED`).
- `TransferBid`: listing, club, amount, created_at (bindend, kein Auto-Bieten).
- `ListingPin`: listing, club (öffentliche Anzahl, Push-Abo).
- `SquadOffer`: player, status (`ALL|SWAP|CASH|SWAP_CASH|LOAN|UVK`, default UVK), updated_at.
- `DealRequest`: from_club, to_club, typ (`SWAP|CASH|SWAP_CASH|LOAN`), timing, cash_from, cash_to, message, expires_at (created + 7 Tage), status (`OPEN|ACCEPTED|DECLINED|WITHDRAWN|EXPIRED`); `DealRequestPlayer`: request, player, side (`FROM|TO`), max 5 je Seite.
- `Loan`: player, owner_club, loan_club, fee, until (`WP|SE`), buy_option (nullable), started_at, ended_at, recall_requested.
- `TransferRecord`: date, kind (`CASH|SWAP|LOAN|OPTION|ADMIN`), timing, cash_a, cash_b, club_a, club_b; `TransferRecordPlayer`: record, player, side, market_value_at_transfer; `YouthLevyPayment`: record, payer_club, receiver_club, percent, amount (min. 50.000).
- `TransferReport`: record, reporter_club, reason (Pflicht), status (`OPEN|DISMISSED|UNDER_REVIEW`) → „UNDER_REVIEW" verlinkt in das **Sportgericht**, **kein** öffentlicher Status in der Historie.
- `ClubBudget`-Erweiterung: `reserved` (harte Reservierungen) — Verfügbar = Kontostand − Reserviert.
- Phase 2: `SellOnClause` (player, beneficiary_club, percent, active), `BuybackClause` (player, holder_club, price, deadline, preemption_until).

### 13.4 Cronjobs / Hintergrundtasks
1. **Auktionsabschluss** (minütlich): abgelaufene Listings zuschlagen → Geld buchen, Jugendabgabe verteilen, Historie-Eintrag, Wechselsperre 21 Tage, Reservierungen freigeben, Pushes.
2. **Anfragen-Ablauf** (stündlich): `DealRequest` > 7 Tage → EXPIRED, Reservierung freigeben, Push.
3. **Leih-Rückläufe** (täglich): Leihen zum WP-/SE-Datum beenden, Historie-Eintrag „Rückkehr".
4. **Marktwert-/Positionsbarometer-Job** (täglich): Angebot/Nachfrage je Position aus den Transfers der laufenden Saison → gewichtet die Preisfindungs-Hilfe (keine eigene UI).
5. **Leih-Deadline-Wächter**: ab 5 Spieltage vor WP keine neuen Leihen zulassen.
6. Phase 2: **Vorkaufsrecht-Fenster** (48 h) überwachen, danach Rückkaufoption löschen.

### 13.5 Asset-Pfade (bestehend im Repo)
- Wappen `game/static/game/images/crests/<fm_inside_id>.png` · Spielerfotos `.../players/<id>.png` · Fallback `default_player.svg` (dunkle Silhouette, **nie weiß**) · Wettbewerbe `.../competitions/*.png` · Flaggen als Bild (flagcdn oder lokal), **nie Emoji**.
- Marktwert-Link: `https://www.transfermarkt.de/schnellsuche/ergebnis/schnellsuche?query=<Spielername>` (neuer Tab).
- **Nationalflaggen:** im Prototyp `https://flagcdn.com/w40/<iso2>.png`; im Nachbau die vorhandenen `staticfiles/assets/flags/<asset_id>.png` über die bestehende Nationalitäts-Zuordnung. Darstellung immer 18×12 px, `border-radius:2px`, `object-fit:cover`, 1px dunkler Rahmen — **niemals Emoji-Flaggen**.

### 13.6 Abnahme-Checkliste (jeder Punkt muss im Nachbau erfüllt sein)
1. 7 Reiter, „Meine Deals" mit Badge; Budget-Kopf rechnet live (Reservierungen).
2. Ticker: Spieler cyan/klickbar, Vereine grün/klickbar, Deadlines gold.
3. Genau 3 Headliner (nächste Auktionsenden), Puls, Countdown-Farbregeln, „+24h ×n" mit Anti-Sniping-Tooltip.
4. Filter-Chips **abwählbar**, wirken nur auf „Alle Listings"; Sektionen nur Gepinnt + Alle (kein Endspurt).
5. Keine horizontale Scrollbar in „Alle Listings" ab ~1010 px; Vereinsnamen vollständig lesbar.
6. Gebotsverlauf per Klick auf das Höchstgebot; **kein Auto-Bieten** an irgendeiner Stelle.
7. Deal-Sheet ohne Scrollbalken; Jugendabgabe aufgeschlüsselt inkl. „wer zahlt an wen" + tatsächlichem Geldfluss; Mindestgebot 500.000 €, Mindestabgabe 50.000 €.
8. Gerüchte mit **Spielerbild**; Reaktion färbt nur den Rahmen (rot/grün), **keine Folge-News**.
9. Leihmarkt-Anfragen erscheinen in „Anfragen gesendet"; erhaltene Leihanfragen in „Anfragen erhalten".
10. Erhaltene und gesendete Anfragen im **identischen Zeilenformat**, Klick öffnet Zusammenfassungs-Popup **ohne Differenzrechner**, mit Live-Countdown (T h m s).
11. Deal-Builder: Land/Liga/Verein als Dropdowns mit Flagge/Logo/Wappen, Profis-/U21-Reiter, scrollbare Listen (bis 70 Spieler), max. 5 je Seite, Zeitpunkt-Chips, Live-Zusammenfassung mit Jugendabgabe.
12. Kader anbieten: Profis/U21, Status-Chips (Default UVK), 👁-Aufklappen mit Verein + Manager, Push-Hinweis, „Auf TL stellen" mit Preisfindungs-Hilfe **und** Jugendabgabe-Vorschau, Forum-Post-Generator.
13. Laufende Leihen: Spielerbild + Wappen vor Vereinsnamen, Klick → Leistungs-Popup je Wettbewerb.
14. Historie: Paginierung (6/Seite), Tausch-Zeilen (n ⇄ n), aufklappbare Zusammenfassung **mit** Jugendabgabe, rotes **!**-Melden-Icon mit Tooltip, **keine** Status-Spalte.
15. Jeder Vollzug (Kauf, Sofortkauf, Tausch, Optionszug, Leihe) erzeugt automatisch einen Historie-Eintrag.
16. Push-Katalog (§ 8) vollständig implementiert.
