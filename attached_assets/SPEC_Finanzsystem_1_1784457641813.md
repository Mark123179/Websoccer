# SPEC: Finanzsystem — Blueprint · Online-Fußballmanager

Stand: 18.07.2026 · Status: final abgestimmt, bereit zur Implementierung
Diese Spec ist das Ergebnis der vollständigen Konzeptdiskussion inkl. einer 15-Saisons-Wirtschaftssimulation (94 Vereine, 5 Ligen). Alle Formeln sind durchgerechnet. Werte, die als `[KALIBRIERUNG]` markiert sind, sind Startwerte und werden über die EconomyParameter-Tabelle nachjustiert — niemals hartcodieren.

---

## 1. Designziele & Grundregeln

Das Finanzsystem soll: (a) keine Inflation erzeugen (Geldschöpfung ≈ Geldvernichtung pro Saison), (b) kleinen Vereinen einen langsamen, planbaren Aufbau ermöglichen — auch ohne sportliches Übererfüllen, (c) große Vereine sterblich halten (Erfolgspflicht statt Vermögensschutz), (d) den Spielspaß nicht durch künstliche Beschränkungen ersticken.

Unverhandelbare Grundregeln:

1. **Ein Topf pro Verein.** Kein Transferbudget, kein Gehaltsbudget — ein Kontostand, der Manager entscheidet frei.
2. **Kein Minus durch aktive Ausgaben.** Transfers, Ausbau, Auktionsgebote und alle anderen Manager-Ausgaben schlagen fehl, wenn die Deckung fehlt. Einzige Ausnahme: Pflichtbuchungen (Gehälter, Betriebskosten, Unterhalt) dürfen das Konto ins Minus buchen — dann greift das Zahlungsunfähigkeits-Verfahren (Kap. 12.4). Ratenzahlungen sind verboten.
3. **Keine Kredite, keine Bank, keine Börse, keine Zinsen.**
4. **KI-Transfers sind reine Geldgeschäfte.** Spielertausch existiert ausschließlich Manager-zu-Manager; bei jedem Tausch wird die Ausbildungsabgabe (5 %) auf den Marktwert jedes getauschten Spielers fällig (MW als einzige manipulationssichere Basis), als Geldbuchung beider Vereine. KI-Vereine tauschen nie und bieten nie auf Tausch-markierte Spieler.
5. **Keine Spielerverträge.** Gehälter hängen ausschließlich am Marktwert.
6. **Kein Ausgabendeckel für Manager.** Wer 400 Mio verdient hat, darf sie in einem Fenster ausgeben.
7. Sparen wird nie bestraft. Es gibt keinen automatischen Negativzins o. Ä. (Notfallregler existiert, ist aber hart deaktiviert, Kap. 11).

Zentrale Trennung der Systeme: **Fanbeliebtheit → Zuschauer** (Stadion), **Präsidenten-Erwartung → Geld** (Sponsoren; Erwartungserfüllung selbst wird nicht mit Geld, sondern mit einem Hoeneß-Coin belohnt — außerhalb dieser Spec).

---

## 2. EconomyParameter — die zentrale Regler-Tabelle

Alle Balancing-Werte leben in einer DB-Tabelle, pro Saison versioniert (Snapshot beim Saisonwechsel). Änderungen ohne Deployment möglich.

```python
class EconomyParameter(models.Model):
    saison   = models.ForeignKey("game.Season", on_delete=models.CASCADE)
    key      = models.CharField(max_length=64)
    value    = models.JSONField()          # Zahl, Objekt oder Tabelle
    class Meta:
        unique_together = ("saison", "key")
```

Startwerte (Details in den jeweiligen Kapiteln):

| Key | Startwert | Kapitel |
|---|---|---|
| GEHALT_BASIS | 18.0 (%) | 4 |
| GEHALT_PROGRESSION | 6.0 (%/MW-Dekade) | 4 |
| GEHALT_DIVISOR | 40 (Normspiele/Saison) | 4 |
| MEDIAN_DAEMPFUNG | 0.10 (max ±10 %/Saison) | 4 |
| NACHFRAGE_KOEFF / NACHFRAGE_EXP | 1414 / 0.575 | 5 |
| PREIS_REFERENZ | {steh: 18, sitz: 45, vip: 350} € | 5 |
| PREIS_ELASTIZITAET | 0.35 | 5 |
| UNTERHALT_PLATZ / KOSTEN_BESUCHER | 40 €/Saison / 5 €/Besucher | 5 |
| AUSBAU_BAENDER | Tabelle Kap. 5 | 5 |
| AUSBAU_FAKTOR_KATEGORIE | {steh: 0.6, sitz: 1.0, vip: 4.0} | 5 |
| STADION_MAX | 120000 | 5 |
| SPONSOR_SOCKEL | {liga1: 10, liga2: 3} Mio | 6 |
| SPONSOR_MW_ANTEIL | 0.07 `[KALIBRIERUNG]` | 6 |
| SPONSOR_STREUUNG | 0.10 | 6 |
| TV_TOEPFE | Tabelle Kap. 7 `[KALIBRIERUNG]` | 7 |
| TV_SPLIT_LIGA | {liga1: 0.8, liga2: 0.2} | 7 |
| TV_VERTEILUNG | {sockel: 0.5, platz: 0.3, koeff: 0.2} | 7 |
| FALLSCHIRM_QUOTE | 0.5 (einmalig) | 7 |
| POKAL_BASIS_ANTEIL | 0.00024 des Landestopfs | 8 |
| POKAL_TITEL_FAKTOR | 30 | 8 |
| SUPERCUP_FAKTOR | {sieger: 5, verlierer: 2.5} | 8 |
| CL_PRAEMIEN / EL_TEILER | Tabelle Kap. 8 | 8 |
| AUSBILDUNGSABGABE | 0.05 (an Ausbildungsvereine; nicht auszahlbare Anteile werden nicht erhoben) | 9 |
| BETRIEBSQUOTE | 0.34 `[KALIBRIERUNG]` | 10 |
| BETRIEB_SOCKEL | 5 Mio/Saison | 10 |
| VERBANDSABGABE_ENABLED | false (nur Admin) | 11 |
| KI_ANGEBOTS_KADENZ | Tabelle Kap. 9.3 `[KALIBRIERUNG]` | 9 |
| STARTBUDGET_QUOTE | 0.20 des proj. Jahresumsatzes | 13 |
| STARTBUDGET_MIN | 3 Mio | 13 |
| KADER_MAX_BASIS | 60 (Umfeld-erweiterbar) · Mindestkader 18 | 9 |
| SCHMERZGRENZE_KONSTANTEN | Altersfaktoren, Realisierung, Restnutzwert, Kernspieler ×1,5, Margen `[KALIBRIERUNG]` | 9 |
| ABFINDUNG_KARRIEREENDE | 0 (keine Zahlung — Alterungsrisiko ist Spielelement) | 4 |
| ABFINDUNG_TOD | WSC-Alterstabelle: 16–17: 6× · 18–20: 5× · 21–22: 4× · 23–24: 3,5× · 25–28: 3× · 29–32: 2,5× · 33+: 1,5× MW | 4 |
| MW_MINIMUM | 50.000 € (Untergrenze je Spieler, wie WSC) | 4 |

---

## 3. Geldkreislauf — Quellen und Senken

**Quellen (Schöpfung):** TV-/Ligagelder, Sponsoren, Ticketeinnahmen (+ Stadionumfeld-Umsätze), Pokal-/International-Prämien.
**Senken (Vernichtung):** Gehälter, Betriebskosten, Stadionunterhalt & Spieltagskosten, Auktionserlöse, Sportgericht-Strafen, Scoutinggebühren.
**Neutral (zirkuliert nur):** Ablösen zwischen Vereinen, Ausbildungsabgabe (reine Umverteilung an Ausbildungsvereine, Kap. 9.1), Stadion-/Umfeld-Ausbau ist Vernichtung (Geld verlässt das System an „Baufirmen“).

Gesundheitsziel: Geldmengenwachstum pro Saison ≈ MW-Drift (±2 %). Überwacht über das Ledger (Kap. 12).

---

## 4. Gehälter

**Buchung pro Pflichtspiel des Vereins, für jeden Kaderspieler, unabhängig vom Einsatz.** Mehr Pflichtspiele (Pokallauf, international) = mehr Gehaltskosten. Erfolg finanziert sich nie umsonst.

```
Jahresgehalt(Spieler) = MW × (BASIS + PROGRESSION × log10(MW / MEDIAN_ANKER)) / 100
Gehalt_pro_Pflichtspiel = Jahresgehalt / GEHALT_DIVISOR        # Divisor 40 = Normsaison
Untergrenze Prozentsatz: 12 %
```

**MEDIAN_ANKER** = Median-Marktwert aller Spieler der Sim, berechnet einmalig beim Saisonwechsel, gedämpft auf max. ±MEDIAN_DAEMPFUNG Bewegung pro Saison, eingefroren in `SeasonEconomySnapshot`. Median, nicht Durchschnitt (Ausreißer-robust). Effekt: Steigen die Marktwerte insgesamt, skaliert die größte Senke automatisch mit — selbststabilisierend.

Zwei unabhängige Regler: BASIS trifft alle (v. a. kleine Vereine), PROGRESSION trifft fast nur die Großen (+6 Prozentpunkte pro Verzehnfachung des MW). Kleine Vereine zahlen effektiv ~16–20 % des Kader-MW pro Saison, Topvereine ~28–30 %, ein 180-Mio-Star ~31 %.

Referenzwerte (Anker ≈ 3 Mio, echte Kader-MW):

| Verein | Kader-MW | Gehalt/Pflichtspiel | 34 Spiele | 46 Spiele |
|---|---|---|---|---|
| Man City | 1.440 Mio | ~9,5 Mio | ~322 Mio | ~436 Mio |
| PSG | 1.360 Mio | ~8,9 Mio | ~303 Mio | ~410 Mio |
| Hoffenheim | 309 Mio | ~1,7 Mio | ~59 Mio | ~80 Mio |
| Elversberg | 50 Mio | ~0,22 Mio | ~7,6 Mio | ~10,3 Mio |

**Karriereende & Todesfälle** (Ereignisse aus den Monats-Realdaten): Bei Karriereende erhält der Verein keine Zahlung (`ABFINDUNG_KARRIEREENDE = 0`) — alternde Kader sind ein bewusstes Risiko. Bei Todesfällen erhält der Verein eine Entschädigung nach der Alterstabelle (`ABFINDUNG_TOD`, Buchungstyp ABFINDUNG): unverschuldet und endgültig, die Staffel kompensiert den Zukunftsverlust; wegen der Seltenheit ökonomisch unbedenklich.

---

## 5. Stadion & Zuschauer

### 5.1 Nachfrage (kein Fanbasis-Stat!)

Es gibt keinen gepflegten oder wachsenden Fanbasis-Wert. Die Nachfrage wird pro Heimspiel live berechnet:

```
Basisnachfrage = NACHFRAGE_KOEFF × KaderMW^NACHFRAGE_EXP          # KaderMW in Mio
Nachfrage = Basisnachfrage × Beliebtheitsfaktor × Gegnerfaktor × Preisfaktor
Zuschauer = min(Nachfrage, Kapazität)   — kategorieweise (Steh/Sitz/VIP anteilig)
```

Faktoren: Beliebtheit (aus Fanbeliebtheits-System) 0,7–1,2 · Gegner-Attraktivität (Kader-MW-Verhältnis; Tabellennähe: Punktabstand ≤ 9 gilt als Topspiel, Websoccer-bewährt; Pokal-K.o.-Spiele immer attraktiv; Derby-Flag) 0,85–1,3 · Preisfaktor je Kategorie `(Referenzpreis / Preis)^PREIS_ELASTIZITAET`, geklemmt auf 0,5–1,3.

Plausibilitäts-Referenz der Basisnachfrage: City 92.600 · Real 90.000 · Bayern 76.400 · Hoffenheim 38.200 · Elversberg 13.400 · Heidenheim 11.000. Ein Verein wächst in die Nachfrage hinein, indem sein Kader besser wird — erst Erfolg, dann Ausbau.

### 5.2 Ticketpreise

Der Manager setzt die Preise je Kategorie **völlig frei** (UI im Stadion-Modul). Referenzpreise (Elastizitäts-Anker, ligaabhängig skalierbar): Steh 18 € / Sitz 45 € / VIP 350 €.

### 5.3 Kapazität, Mix, Ausbau

Sim-Start: **reale Kapazitäten inkl. realem Steh/Sitz/VIP-Mix pro Verein** (Importdaten, z. B. Signal Iduna Park 28.000/50.000/2.500). Danach baut der Manager frei, welche Kategorie er will — solange das Geld reicht. Maximum: 120.000 Plätze gesamt.

Ausbaukosten pro Platz (Sitzplatz-Basis; Steh ×0,6, VIP ×4,0), gestaffelt nach **Zielkapazität**:

| Kapazitätsband | € pro Sitzplatz |
|---|---|
| bis 20.000 | 1.500 |
| 20.001–40.000 | 2.500 |
| 40.001–60.000 | 3.500 |
| 60.001–80.000 | 5.000 |
| 80.001–100.000 | 7.000 |
| 100.001–120.000 | 9.000 |

Beispiel: Elversberg 10.000 → 25.000 ≈ 28 Mio · 10.000 → 120.000 ≈ 555 Mio. Ausbau ist eine Einmalzahlung (Geldvernichtung), Bauzeit optional (z. B. 1 Saison pro 15.000 Plätze).

### 5.4 Laufende Stadionkosten

`Unterhalt = Kapazität × UNTERHALT_PLATZ pro Saison` (anteilig pro Spieltag gebucht) plus `Spieltagskosten = Zuschauer × KOSTEN_BESUCHER pro Heimspiel`. Leere Plätze kosten, volle auch — das ist die natürliche Bremse gegen Überbau; es gibt keine künstliche Ausbauregel. Keine separate „Steuer“.

Stadionumfeld (bestehendes Modul): Ausbaustufen als Einmalinvestition, danach Zusatzeinnahme €/Besucher — dockt an dieselbe Zuschauerzahl an.

---

## 6. Sponsoren

### 6.1 Sponsorwert (Basis der Angebote)

```
Sponsorwert = SPONSOR_SOCKEL(Liga) + SPONSOR_MW_ANTEIL × KaderMW + Platzbonus(Vorsaison)
```

Keine Fanbeliebtheit im Sponsorwert. Liga-Level ergibt sich aus dem Ligakoeffizienten (Kap. 7).

### 6.2 Jahresangebote

Zu jedem Saisonstart erhält der Manager **3–5 generierte Angebote, Laufzeit genau 1 Saison**. Alle Angebote haben denselben Erwartungswert ≈ Sponsorwert, kalibriert auf die **Präsidenten-Erwartung** (der Präsident kennt die verborgenen Stärken; erwartete Siege/Platzierung/Titel fließen in die Bepreisung ein). ± SPONSOR_STREUUNG Zufall pro Angebot, damit es echte gute/schlechte Deals zu erkennen gibt.

Angebotstypen (Mischung pro Saison generieren):

| Typ | Struktur | Charakter |
|---|---|---|
| Sicherheit | 100 % fix | Absicherung |
| Sieggeld | ~50 % fix + X €/Pflichtspielsieg | Wette auf konstante Leistung |
| Zieljäger | ~60 % fix + Bonus für Titel/Zielerreichung (bei Kleinen: Nichtabstieg/Aufstieg) | Wette auf den großen Wurf |
| Zuschauer | ~50 % fix + X €/Stadionbesucher | belohnt Stadion-Strategie |

Weil die Erwartung eingepreist ist, gibt es kein „objektiv bestes“ Angebot: Für erwartete Meister ist variabel vor allem Risiko, für Underdogs vor allem Chance. Fixanteile werden in Spieltagsraten gebucht, variable Anteile eventbasiert.

---

## 7. TV-/Ligagelder & Ligakoeffizient

### 7.1 Landeskoeffizient

5-Jahreswertung pro Land aus den Europapokal-Ergebnissen seiner Vereine (Punkteschema analog UEFA). Beim Launch eines Landes geseedet mit realen UEFA-Werten. Der Koeffizienten-**Rang** bestimmt: (a) Größe des Ländertopfs, (b) CL-/EL-Startplätze. Zusätzlich: Vereins-5-Jahreswertung pro Verein (für die Verteilung innerhalb der Liga).

### 7.2 Ländertöpfe pro Saison `[KALIBRIERUNG]`

| Koeff.-Rang | Land (Start) | Gesamttopf | 1. Liga (80 %) | 2. Liga (20 %) |
|---|---|---|---|---|
| 1 | England | 2.200 Mio | 1.760 | 440 |
| 2 | Spanien | 1.930 Mio | 1.544 | 386 |
| 3 | Deutschland | 1.700 Mio | 1.360 | 340 |
| 4 | Italien | 1.500 Mio | 1.200 | 300 |
| 5 | Frankreich | 1.320 Mio | 1.056 | 264 |
| 6–9 | Portugal / NL / CH / AT | 300–520 Mio | | |

Töpfe hängen am **Rang**, nicht am Land — überholt Frankreich Italien, tauschen die Topfgrößen. Bewusst komprimiert (Faktor ~5 statt real ~13 zwischen Rang 1 und Kleinländern).

### 7.3 Verteilung innerhalb der Liga

`50 % Sockel (gleich für alle) + 30 % Platzierung (linear degressiv) + 20 % Vereins-5-Jahreswertung (linear degressiv nach Koeffizienten-Rang in der Liga)`. Ergibt Spreizung Platz 1 : letzter ≈ 2,6× (Bundesliga: ~109 Mio zu ~42 Mio). Sockel wird in Spieltagsraten gebucht, Platz- und Koeffanteil bei Saisonende.

### 7.4 Auf-/Abstieg

Aufsteiger erhalten sofort den vollen Sockel der neuen Liga (der Aufstiegs-Jackpot, keine Extra-Mechanik). Absteiger erhalten einmalig `FALLSCHIRM_QUOTE × letzte TV-Gesamtsumme` in der ersten Abstiegssaison — kauft genau ein Transferfenster Zeit, um Erstliga-Gehälter abzubauen (wichtig wegen Kein-Minus-Regel).

### 7.5 Rollout

Funktioniert ab Tag 1 mit nur der Bundesliga. Neue Ligen (7-von-10- bzw. 14-von-18-Freischaltung) docken über die Parametertabelle an, ohne Codeänderung.

---

## 8. Prämien (= Wettbewerbsgelder, nichts anderes)

Ligaerfolg wird **nicht** zusätzlich prämiert (bereits über Platzgeld, Koeffizient, Sponsorvariable, Zuschauer bezahlt). Präsidenten-Erwartung wird mit dem Hoeneß-Coin belohnt, nicht mit Geld.

### 8.1 Nationalpokal — Verdopplungsprinzip

```
Basis = POKAL_BASIS_ANTEIL × Landestopf          # DE: ~410k
Prämie(Runde r) = Basis × 2^(r−1)                # r = 1..6
Titelgeld = Basis × POKAL_TITEL_FAKTOR           # DE: ~12,3 Mio; Gesamtpfad ~35 Mio
```

Skaliert automatisch für jedes Land. Zweiter Pokal (England, falls gewünscht): gleiche Formel mit halber Basis. Supercup: Einzelspiel, Sieger 5× Basis, Verlierer 2,5×. Pokalrunden erzeugen zusätzliche Pflichtspiele (Gehalt!) und je nach Los zusätzliche Heimspiele (Tickets).

### 8.2 International (fester Europatopf, nicht koeffizientenabhängig)

| Ereignis | Champions League | Europa League (÷4) |
|---|---|---|
| Startgeld Gruppenphase | 30 Mio | 7,5 |
| Gruppensieg / Remis | 2,5 / 0,8 | 0,6 / 0,2 |
| Achtelfinale | 12 | 3 |
| Viertelfinale | 15 | 3,75 |
| Halbfinale | 20 | 5 |
| Finalteilnahme | 25 | 6,25 |
| Titel | +30 | +7,5 |

Maximalpfad CL ~140 Mio + 6–9 Zusatz-Heimspiele. Die Topvereine **brauchen** dieses Geld strukturell (Simulationsbefund): frühes CL-Aus = reales Defizit = Verkaufsdruck. Startplätze vergibt der Landeskoeffizient (Detail-Modus im Modul „Internationale Wettbewerbe“).

---

## 9. Transfermarkt

### 9.1 Grundsätze

Ablöse frei verhandelbar, **kein Ausgabendeckel, keine Eskalationsregel** für Manager.

**Ausbildungsabgabe (5 %):** Fällt bei jedem Transfer an — bei Geldtransfers auf die Ablöse, bei Tauschgeschäften auf den MW jedes getauschten Spielers. Käufer zahlt voll, Verkäufer erhält Ablöse − Abgabe (Buchungstyp AUSBILDUNG_AUS beim Zahler, AUSBILDUNG_EIN beim Empfänger).

*Verteilregel:* Ausbildungszeitraum = alle Saisons ab Sim-Start bzw. Sim-Eintritt des Spielers bis einschließlich der Saison seines 21. Geburtstags (reale Vor-Sim-Historie zählt nie). Pro angefangener Saison bei einem Verein ein gleicher Anteil. **Es wird kein Geld vernichtet:** Die Abgabe wird nur in Höhe der auszahlbaren Fremdanteile erhoben — Anteile, die auf den verkaufenden Verein selbst entfallen, und Anteile ohne Empfänger (Spieler ohne Sim-Ausbildungshistorie) werden gar nicht erst abgezogen. Die Abgabe gilt für alle Transfers der gesamten Karriere; die Empfängerliste ist auf die Vor-21-Stationen eingefroren. Reine Umverteilung, keine Senke.

*Beispiel (Koloto, Sim-Start mit 17 bei Basel):* Transfer mit 18 für 20 Mio → Basel ist einziger Ausbildungsverein und Verkäufer → **keine Abgabe, Basel erhält 20 Mio voll**. Tausch mit 19 (MW 15) → nur Basels Anteil (2 von 3 Saisons) fällig: ManUtd zahlt 500k an Basel. Geldtransfer mit 23 für 60 Mio → Fremdanteile 3/5 von 3,0 Mio: **Basel 1,2 Mio, Leipzig 600k, ManUtd erhält 58,2 Mio**. Datenbasis: Vereinshistorie je Spieler (`PlayerClubHistory(spieler, club, saison)`), ohnehin fürs Datencenter sinnvoll.

**Kaderplatz-Voraussetzung:** Käufe (KI wie Manager) nur bei freiem Kaderplatz. Standard-Kaderlimit 60 Spieler, erweiterbar über Stadionumfeld-Ausbauten (`KADER_MAX_BASIS = 60`; Erweiterungslogik im Umfeld-Modul). **Mindestkader 18:** Verkäufe, die den Kader unter 18 Spieler senken würden, sind blockiert — für Manager wie KI.

**Ablösefreie Wechsel:** Auch ohne Ablöse fällt die Ausbildungsabgabe an — Basis ist dann der aktuelle MW des Spielers (zahlt der aufnehmende Verein).

**Verkaufskategorien:** Der Manager markiert jeden Spieler als `GELD`, `TAUSCH`, `GELD_TAUSCH` oder `UVK` (unverkäuflich) und entscheidet, ob KI-Vereine diese Markierung sehen dürfen. Sichtbar geschaltet gilt: KI bietet ausschließlich auf GELD und GELD_TAUSCH; UVK- und TAUSCH-Spieler erhalten nie ein KI-Angebot (Postfach-Hygiene).

**Verbesserungsangebot-Toggle:** Bei jeder Ablehnung eines KI-Angebots wählt der Manager, ob ein Verbesserungsangebot erwünscht ist. „Nein" beendet die Verhandlung sofort (kein weiteres Angebot, Cooldown greift); „Ja" erlaubt der KI die nächste Verhandlungsrunde.

### 9.2 Schmerzgrenze v2 (Preislogik managerloser Vereine)

Der verkaufende Verein kennt die **verborgene Stärke und das Potential** (wie der Präsident). Manager sehen beides nicht — die Ablehnung eines hohen Gebots ist damit selbst Scouting-Information.

```
Schmerzgrenze = max(Gegenwartswert, Zukunftswert)

Gegenwartswert = max(
    MW × Stärkefaktor × Altersfaktor,
    MW_Kurve(Stärke) × Restnutzwert(Alter)      # bewertet Stärke, nicht den altersgedrückten MW
)
Zukunftswert  = MW_Kurve(Potential) × Realisierung(Alter, Potential − Stärke)
                # nur falls Potential > Potential-Median und Potential > Stärke

Stärkefaktor  = 1 + max(0, Stärke − Stärke_Median) / 50
Altersfaktor  = 1,6 (≤21) · 1,3 (22–25) · 1,0 (26–29) · 0,75 (30+)
Restnutzwert  = z. B. 0,55 bei 33 J. (fallend mit Alter)
Realisierung  = clamp(0,45 − Lücke×0,002 − max(Alter−17,0)×0,015 ; 0,08 ; 0,45)
```

**MW_Kurve** = Median-MW je Stärkeband, live aus der Spielertabelle beim Saisonwechsel berechnet (Snapshot). Ebenso Stärke-Median (~135) und Potential-Median (~150). Alle Anker atmen mit der Sim.

Kernspieler-Zuschlag: Für die Top-3 (Stärke) und das höchste U21-Potential des Kaders gilt zusätzlich ×1,5 auf die Schmerzgrenze (reiner Preis, keine Mengenbegrenzung).

Validierte Beispiele: 50k-Wunderkind (16 J., St. 95/Pot. 190) → ~22 Mio · Koloto-Typ (18 J., 3 Mio MW, St. 120/Pot. 185) → ~18–27 Mio · alternder Weltstar (33 J., 9 Mio MW, St. 178) → ~22 Mio · Durchschnittsspieler → ~1,0–1,1× MW · junge Niete → ~1,6× eines winzigen MW. Wild auf Talente bieten liefert Nieten billig und Perlen teuer — kein WSC-Talente-Poker.

### 9.3 KI-Vereine als Marktteilnehmer

**Grundsatz:** KI-Vereine geben ausschließlich Überschüsse nach allen Kosten aus, gezielt; sie horten nicht (Budgetregel: Puffer ≈ halbe Saison Fixkosten, Rest reinvestierbar). Implementierungs-Stufe 1: rein reaktive Verkäufer nach Schmerzgrenze. Stufe 2: aktive Käufer nach folgender Logik.

**Bewertungssymmetrie (volle Werte-Kenntnis):** KI-Vereine kennen die wahren Stärken und Potentiale **aller** Spieler der Sim. Verkauf und Kauf nutzen dieselbe Bewertungsformel (Schmerzgrenze v2, Kap. 9.2):

```
Verkäufer verlangt:  Bewertung × 1,1–1,3
Käufer bietet max.:  Bewertung × (1 ± STREUUNG)      # nie strukturell darüber — eine KI überzahlt nicht
Eröffnungsgebot:     ~70 % des Käufer-Maximums
```

Jedes KI-Angebot ist damit ein ernsthaftes Angebot aus derselben Rechnung, mit der die KI selbst verkaufen würde (Beispiel: Spieler mit Bewertung 22 Mio → Eröffnung ~15, Nachbesserung ~19, final 22). Nebeneffekt als Spielelement: Ein hohes KI-Gebot auf einen niedrig-MW-Spieler ist ein Informations-Signal an den Besitzer — durch den Talent-Slot (s. u.) bewusst selten.

**Keine In-Sim-Entwicklung:** Stärke, Potential und MW aller Spieler kommen monatlich aus realen Datenquellen (TM/FMI/CMT) und folgen der realen Karriere — Einsätze in der Sim verändern nichts. Der Zukunftswert ist damit eine reine Wette auf die reale Entwicklung; es gibt **keinen** vereinsspezifischen Entwicklungs- oder Spielzeitfaktor. Talente sind für jeden Käufer gleich viel wert — die Differenzierung zwischen Vereinen entsteht ausschließlich über Bedarfsfaktor, Dringlichkeitsdiskont und Budget. (Folge der Monatsupdates: Gehälter nutzen stets den aktuellen MW zum Buchungszeitpunkt; der Gehalts-Anker bleibt saisonfixiert.)

**Kaufentscheidung — drei Kauftypen mit absteigender Priorität** (die Bewertung sagt *wie viel*, die Kauftypen sagen *ob*):

| Typ | Bedingung | Gebotsgrenze | Limit |
|---|---|---|---|
| 1. Bedarfskauf | Positions-Tiefenanalyse zeigt echte Lücke (Stärketiefe < Liga-Soll); Trigger: eigener Verkauf, Verletzungen, Monatsupdate, Saisonstart | 100 % der Bewertung | bis Lücke geschlossen |
| 2. Qualitätskauf | keine Lücke, aber Spieler ≥ +10 Stärke über eigenem Positionsbesten UND Überschuss > 2× Puffer | 85 % der Bewertung („nur zum guten Preis") | max. 1 pro Fenster |
| 3. Talentkauf | Kaderplatz frei, Überschuss vorhanden, Saisonziel nicht gefährdet, Spieler ≤ 21 mit Potential deutlich über Kaderniveau | 90 % des Zukunftswerts | max. 1 pro Saison (Talent-Slot) |

Der Dringlichkeitsdiskont (0,3–1,0 aus Präsidenten-Erwartung/Saisonlage + Finanzpolster) wirkt als Torwächter: Ein Abstiegskandidat tätigt ausschließlich Bedarfskäufe mit Gegenwartswert-Fokus, nie Talent- oder Qualitätskäufe. Budgetgrenze immer: nur Überschüsse (Budgetregel oben) und nur bei freiem Kaderplatz (Kap. 9.1).

**Bedarfsrechnung (formal):**

```
Beste_11 = stärkste formationskonforme Elf des Vereins (nach wahrer Stärke —
           NICHT die tatsächlich aufgestellte Startelf)

Für jede Position der Beste_11:
  Stammlücke   = max(0, Liga_Soll − Stärke des Beste-11-Spielers)
                 # Liga_Soll = Median der Beste-11-Stärken aller Ligavereine (Saison-Snapshot)
  Backup vorhanden, wenn ein weiterer Spieler der Position existiert mit
                 Stärke ≥ Beste-11-Spieler − 25  ODER  Potential ≥ Beste-11-Niveau
                 # Talente zählen als Backup — kein Verein braucht zwei gleichstarke Torhüter
  Lückenscore  = 10 × kritische Tiefenlücke (2. TW fehlt / Position ohne jeden Backup)
               +  1 × Stammlücke

Akuter Bedarf (Kauftyp 1): kritische Tiefenlücke ODER Lückenscore ≥ Schwellwert.
Abarbeitung nach höchstem Lückenscore.
```

Das Liga-Soll ist der Liga-**Median** — ein Zweitligist hat automatisch bescheidenere Ansprüche als Bayern, ohne Sonderregeln. Kaderstruktur-Realismus: verlangt wird eine starke Elf plus Mindest-Backups (schwächere Routiniers oder Talente), nie doppelte Gleichstärke. Referenz-Testfall „Ito-Verkauf": Verkauf eines Beste-11-IV → Talent rückt auf → Stammlücke + ggf. Tiefenlücke → Bedarfskauf im nächsten Prüflauf; bester Kandidat per Nutzen-Ranking, KI-zu-KI sofort, Manager über Verhandlungsrunden; kein Kandidat erreichbar → Lücke bleibt, Prüflauf wiederholt sich je Spieltag.

**Angebotsreihenfolge:** Kandidaten je Lücke sortiert nach `Nutzen = (eigene Bewertung − erwartete Forderung) / Forderung`. Lehnt ein Manager ab (bzw. Toggle „Nein"), wandert die KI zum nächstbesten Kandidaten.

**KI-zu-KI-Clearing (ohne Verhandlungsrunden):** Beide Bewertungen sind systemseitig bekannt: `Käufer-Maximum ≥ Verkäufer-Forderung → sofortiger Deal zum Mittelwert (eine atomare Buchung); sonst kein Deal.` Verhandlungsrunden existieren nur gegenüber Managern.

**Angebots-Kadenz** (alle Werte in EconomyParameter, `[KALIBRIERUNG]`):

| Regel | Startwert |
|---|---|
| Prüflauf je KI-Verein | 1× pro Spieltag im Transferfenster + Trigger (Monats-Datenupdate, eigener Verkauf, Finanzlagenwechsel) |
| Offene Kaufangebote je KI-Verein | max. 1 gleichzeitig, max. 3 pro Fenster |
| Eingehende KI-Angebote je Manager-Verein | max. 2 offene gleichzeitig, max. 4 pro Fenster |
| Cooldown je Spieler nach Ablehnung | nach Kauftyp: Bedarf 7 Tage (nächster Kandidat sofort) · Qualität 14 Tage · Talent bis Fensterende |
| Gültigkeit eines Angebots | 72 h |
| Globaler Governor | KI-Kaufvolumen ≤ definierter Anteil des Gesamt-Transfervolumens (Monitoring-Alarm) |

**Creator-Mode — KI-Transferzentrale (Admin):** Live-Übersicht aller KI-Angebote: bietender Verein, Zielspieler, Besitzerverein, Kauftyp, Bewertung, aktuelle Gebotsstufe, Status (berechnet/versendet/abgelehnt/Deal). Drei Eingriffsstufen: einzelnes Angebot stornieren · einzelnen KI-Verein pausieren · globaler **Trockenlauf-Modus** (Angebote werden berechnet und geloggt, aber nicht versendet). Einführungspfad für Stufe 2: zuerst Trockenlauf am Live-Datenbestand, Admin-Review der berechneten Angebote, erst dann scharf schalten.

**Verhandlungsrunden (beide Richtungen, max. 3 Runden):** Die KI eröffnet bei ~70 % ihres Maximalgebots (= Bewertung × (1 ± STREUUNG), begrenzt durch den Kauftyp). Nach Ablehnung prüft sie die Dringlichkeit neu: bei akutem Bedarf Erhöhung auf ~90 %, sonst Rückzug. Ein drittes, finales Angebot (100 % des Maximums) gibt es nur bei hoher Dringlichkeit — danach greift der Cooldown. Das Maximum wird nie überschritten: Eine KI lässt sich nicht hochpokern. Auf alle Schritte ±5 % Zufallsstreuung, damit die Treppe nicht reverse-engineerbar ist (Ablehnen darf nie risikolos sein). Spiegelbildlich als Verkäufer: Auf ein Managergebot unterhalb der Schmerzgrenze antwortet die KI bei moderater Lücke mit einer Gegenforderung (Schmerzgrenze × 1,1; in Runde 2 ggf. × 1,0 bei Finanzdruck), sonst mit Absage.

Ziel-Erlebnis: ein Manager mit interessantem Kader erhält im Fenster etwa alle 1–2 Wochen ein Angebot — nie 16 pro Tag, nie wochenlang Funkstille. Damit ist das KI-Marktverhalten vollständig in dieser Spec definiert; ein separates Konzeptdokument ist nicht mehr nötig.

---

## 10. Betriebskosten

Größte Nicht-Gehalts-Senke (Verwaltung, Trainerteam, Mitarbeiter, Jugend, Reisen — kein eigenes Mitarbeiter-System nötig, Pauschallogik):

```
Betriebskosten = BETRIEB_SOCKEL(Liga) + BETRIEBSQUOTE × laufende Einnahmen
```

Gebucht pro Spieltagslauf als Quote auf die seit dem letzten Lauf verbuchten Einnahmen. `[KALIBRIERUNG]` — Startwert 34 %; dies ist der wichtigste Geldmengen-Regler (Simulationsbefund: ohne diese Senke wächst die Geldmenge um >40 %/Saison).

---

## 11. Auktionen & Notfallregler

**Auktionen** (bestehendes System) sind die einzige *dosierbare* Senke: Zuschlagserlöse werden vollständig vernichtet (Buchungstyp AUKTION). Volumen und Qualität der Auktionsspieler pro Saison steuert der Admin — das gezielte Ventil gegen Geldüberhänge, das dort absaugt, wo Geld liegt, freiwillig und mit Spielspaß. **Bewusste Admin-Aufgabe:** Die Simulation endet ohne Auktionen bei ~7 % Geldmengenwachstum pro Saison; regelmäßige Auktionen sind eingeplant, nicht optional — der Monitoring-Alarm (> 4 %) erinnert daran. Zwangsversteigerungen (Kap. 12.3) sind davon getrennt: deren Erlös geht an den Verein.

**Verbandsabgabe (Notfallregler):** Abgabe auf Kontostände oberhalb X × Jahresumsatz. Vollständig implementiert, aber `VERBANDSABGABE_ENABLED = false` als Hard-Default. **Aktivierung ausschließlich manuell durch den Admin** — kein Schwellwert-Automatismus, keine Selbstauslösung.

---

## 12. Ledger, Cashflow & Monitoring

### 12.1 Ledger als einzige Wahrheit

Jede Buchung ist ein Datensatz; der Kontostand ist die Summe des Ledgers (gecachtes Feld nur als Performance-Cache mit Integritätsprüfung, nie als führende Quelle).

```python
class FinanceTransaction(models.Model):
    club       = models.ForeignKey("game.Club", on_delete=models.PROTECT)
    saison     = models.ForeignKey("game.Season", on_delete=models.PROTECT)
    spieltag   = models.PositiveSmallIntegerField(null=True)
    typ        = models.CharField(max_length=32, choices=TYP_CHOICES)
    betrag     = models.DecimalField(max_digits=14, decimal_places=2)  # + Einnahme / − Ausgabe
    referenz_typ = models.CharField(max_length=32, blank=True)   # z. B. "match", "transfer", "ausbau"
    referenz_id  = models.PositiveIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Buchungstypen: `GEHALT, TICKET, UMFELD, SPONSOR_FIX, SPONSOR_VARIABEL, TV_SOCKEL, TV_PLATZ, TV_KOEFF, FALLSCHIRM, PRAEMIE_POKAL, PRAEMIE_SUPERCUP, PRAEMIE_INTL, TRANSFER_EIN, TRANSFER_AUS, AUSBILDUNG_AUS, AUSBILDUNG_EIN, AUKTION, STADION_UNTERHALT, STADION_SPIELTAG, AUSBAU, UMFELD_AUSBAU, BETRIEB, SCOUTING, STRAFE, ABFINDUNG, VERBANDSABGABE, KORREKTUR_ADMIN`.

### 12.2 Cashflow-Design (wegen Kein-Minus-Regel)

Einnahmen fließen stetig, nicht klumpig: TV-Sockel und Sponsor-Fix in Spieltagsraten **im selben Buchungslauf vor** den Gehältern; Tickets nach jedem Heimspiel; Prämien/variable Sponsoranteile eventbasiert; TV-Platz-/Koeffanteil bei Saisonende. So gerät kein solide wirtschaftender Verein unterjährig in Liquiditätsnot.

### 12.3 Zahlungsunfähigkeit

Die Grenze ist für jeden Verein dieselbe: **die 0** — Bayern bei −500.000 € steht im selben Verfahren wie Elversberg. Bucht eine Pflichtbuchung das Konto ins Minus: (1) automatischer **Sportgericht-Vermerk**, (2) der Manager hat **7 echte Tage**, den Kontostand zu bereinigen, (3) andernfalls **Zwangsversteigerung** admin-ausgewählter Spieler über das Auktionssystem — der Erlös geht an den Verein (reguläre Admin-Auktionen vereinsloser Spieler bleiben dagegen Senke). Eine gesonderte Transfersperre ist unnötig: Im Minus fehlt für jeden Kauf die Deckung, aktive Ausgaben schlagen per Grundregel 2 automatisch fehl. Einnahmen aus Verkäufen und Tausch(+Geld)-Geschäften sind jederzeit möglich — das ist der vorgesehene Weg zurück ins Plus.

### 12.4 Implementierungsregel Nebenläufigkeit

Jede Kontobuchung sperrt die Vereinszeile (SELECT … FOR UPDATE). Bei Buchungen mit zwei Vereinen (Transfer, Tausch, Ausbildungsabgabe) werden die Zeilen **immer in fester Reihenfolge** gesperrt: kleinere Club-ID zuerst. Das verhindert Deadlocks zwischen parallelem Spieltagslauf, Transfers und Auktionsenden (Lehre aus Scouting V1).

### 12.5 Monitoring (Datencenter / Admin)

Alles reine Aggregationen über das Ledger — kein zweites Datensystem:

Geldmenge gesamt (Verlauf) · Schöpfung vs. Vernichtung pro Saison, aufgeschlüsselt je Buchungstyp · Transfervolumen, Anzahl, Median-Ratio Ablöse/MW (Gesundheitsziel 1,3–1,8) · Kontoverteilung je Liga · „Totes Kapital“ (Summe Kontostände > 2× Jahresumsatz) · reichste/ärmste Vereine · Gehaltssumme, Ticketsumme, Sponsorsumme pro Saison. Aus demselben Ledger: **Kontoauszug für Manager** (jede Buchung sichtbar — Vertrauen der Community).

Alarmwerte (nur Anzeige, keine Automatik): Geldmengenwachstum > 4 %/Saison · Ablöse/MW-Median > 2,2 · Totes Kapital steigend über 3 Saisons.

---

## 13. Startbudgets

Nicht für alle gleich, sondern aus dem System abgeleitet:

```
Startbudget = STARTBUDGET_QUOTE × projizierter Jahresumsatz     # Untergrenze STARTBUDGET_MIN
proj. Umsatz = TV-Sockel + erwartetes Platzgeld (Präsidenten-Erwartung) + Sponsorwert + Ticketschätzung (Nachfrageformel)
```

Referenzwerte (Quote 20 %): City ~92 Mio · Real ~94 Mio · PSG ~84 Mio · Hoffenheim ~33 Mio · Elversberg ~7 Mio · Heidenheim ~6,5 Mio.

Begründung: Ein absolut gleiches Budget wäre real extrem ungleich (40 % Kaderwert für Elversberg, Rundungsfehler für City). Die Umsatzquote gibt jedem Verein dieselbe Handlungsfähigkeit in seiner Preisklasse. Bewusst **nicht** Kader-MW-basiert — sonst bekämen genau die strukturellen Defizitvereine (PSG, City) die dicksten Polster. Randfälle: Neue Ligen erhalten Startbudgets nach derselben Formel zum Launch-Zeitpunkt (kein Sonderfall). Vereinsübernahmen im laufenden Betrieb erhalten **kein** Startbudget — der neue Manager erbt den Ledger-Kontostand. **Genesis:** Beim Erst-Launch des Finanzsystems erhalten alle Bestandsvereine der laufenden Sim ihr Startbudget nach dieser Formel; eventuelle Alt-Kontostände werden ersetzt (Admin-Buchung KORREKTUR_ADMIN als erster Ledger-Eintrag).

---

## 14. Datenmodell-Ergänzungen (Übersicht)

`EconomyParameter` (Kap. 2) · `FinanceTransaction` (Kap. 12) · `SeasonEconomySnapshot(saison, mw_median, staerke_median, potential_median, mw_kurve_json, gehalts_anker)` · `SponsorOffer(club, saison, typ, fix_betrag, variable_json, gewaehlt, angenommen_at)` · `TVPot(saison, land, gesamt, rang)` · `LandKoeffizient(land, saison, punkte)` / `VereinKoeffizient(club, saison, punkte)` · Stadion-Modul erweitern: Kapazität & Preis je Kategorie (steh/sitz/vip), `StadiumExpansion(club, kategorie, plaetze, kosten, fertig_saison)`.

---

## 15. Celery-Jobs

| Job | Trigger | Aufgaben |
|---|---|---|
| `finance_matchday_run` | nach jedem Pflichtspiel(tag) | TV-Sockel-Rate + Sponsor-Fix-Rate buchen → Gehälter aller Kaderspieler buchen → bei Heimspiel: Zuschauer berechnen, Tickets + Umfeld buchen, Spieltagskosten buchen → Unterhalt-Rate buchen → Betriebskosten-Quote auf Einnahmen seit letztem Lauf buchen → Sieggeld-Sponsor prüfen |
| `finance_event` | Event (Pokalrunde erreicht, CL-Runde, Titel, Transfer, Auktionsende, Ausbau) | zugehörige Buchung(en) atomar ausführen (Transfer: TRANSFER_AUS + TRANSFER_EIN + AUSBILDUNG_AUS/_EIN in einer DB-Transaktion) |
| `finance_season_close` | Saisonende | TV-Platz-/Koeffanteil ausschütten · Fallschirme setzen · Landes-/Vereinskoeffizienten aktualisieren · Saison-Finanzreport erzeugen |
| `finance_season_open` | Saisonstart | MW-Median, Stärke-/Potential-Median, MW-Kurve berechnen & snapshotten (mit Dämpfung) · EconomyParameter-Snapshot anlegen · Sponsorangebote generieren (mit Präsidenten-Erwartung) · TV-Töpfe nach Koeffizienten-Rang zuordnen |
| `finance_integrity_check` | täglich | Ledger-Summe vs. Konto-Cache je Verein; Abweichung → Admin-Alarm |

---

## 16. Simulationserkenntnisse (15 Saisons, 94 Vereine)

Validiert: (a) Kleine Vereine wachsen **ohne** sportliches Übererfüllen — der „Soll-Erfüller“ Elversberg verdoppelt in 15 Saisons fast seinen Kader-MW und baut ~130 Mio Rücklage auf, rein aus strukturellem Überschuss. (b) Topvereine sind sterblich: 2 Saisons ohne CL kosten City ~100 Mio Kader-Substanz dauerhaft; PSG schrumpft über 15 Saisons von 1.200 auf ~830 Mio Kader-MW auf seine wirtschaftliche Wahrheit — bleibt Meister, wird aber nie unantastbar reich. (c) Eine Krisensaison im Mittelfeld (Hoffenheim, Platz 16) kostet ~40 Mio gegenüber Trend — Delle, kein Drama.

Aufgedeckt & behoben: ohne umsatzabhängige Betriebskosten und ohne aktiven Transfermarkt (Angebot!) wächst die Geldmenge explosiv (WSC-Syndrom). Mit BETRIEBSQUOTE 34 % Restwachstum ~7 %/Saison — die letzte Lücke schließen **Auktionen** (in der Sim nicht modelliert) und Feinjustierung.

Offene `[KALIBRIERUNG]`-Regler nach Launch, über Monitoring nachziehen: BETRIEBSQUOTE · TV_TOEPFE (absolute Höhe) · SPONSOR_MW_ANTEIL · Auktionsvolumen pro Saison · Angebots-Kadenz und Kauftyp-Schwellwerte der KI-Vereine (Kap. 9.3).

---

## 17. Implementierungsphasen

**Phase 0 — sofort, unabhängig vom Rest:** `PlayerClubHistory`-Tracking (Vereinshistorie je Spieler ab jetzt schreiben — jede Saison ohne Tracking ist für die Ausbildungsabgabe unwiederbringlich verloren).
**Phase 1 — Fundament:** EconomyParameter, FinanceTransaction-Ledger, Konto-Cache + Integritätscheck, `finance_matchday_run` mit Gehältern, TV-Sockel, Tickets (einfacher Nachfragefaktor), Betriebskosten. Manager-Kontoauszug.
**Phase 2 — Einnahmen komplett:** Sponsorangebote (inkl. Präsidenten-Erwartung), TV-Verteilung vollständig + Koeffizienten, Pokal-/Intl-Prämien, Fallschirm.
**Phase 3 — Stadionökonomie:** Kategorien & Preise (Manager-UI), volle Nachfrageformel, Ausbau-Bänder, Unterhalt — plus **Umbau des Stadionumfelds vom globalen Singleton auf per-Verein-Datenmodell** (eigener Posten, Voraussetzung für €/Besucher-Einnahmen und Kaderlimit-Erweiterung).
**Phase 4 — Transfermarkt:** Ablöseabwicklung + Ausbildungsabgabe, Verkaufskategorien & Kaderlimit, Schmerzgrenze v2 (Snapshot-Berechnungen), reaktive KI-Verkäufer (Stufe 1).
**Phase 5 — Ventile & Monitoring:** Auktions-Buchung als Senke, Monitoring-Dashboard im Datencenter, Verbandsabgabe (deaktiviert), Alarmwerte.
**Phase 6 — KI-Käufer (Stufe 2):** KI-Kauflogik nach Kap. 9.3, Start im Trockenlauf-Modus über die KI-Transferzentrale, Admin-Review, dann scharf schalten.
**Phase 7 — Kalibrierung:** Live-Daten gegen Simulationswerte, Reglerpflege über EconomyParameter und Monitoring.

---

## Anhang A — Entscheidungslog (das „Warum" hinter der Spec)

Für Implementierer: Diese Spec ist das Ergebnis einer langen Design-Diskussion. Wo eine Regel überraschend wirkt, steht hier die Begründung und die bewusst verworfene Alternative. Bei Unklarheiten gilt: im Zweifel im Sinne der Begründung entscheiden.

| Entscheidung | Begründung | Verworfene Alternative |
|---|---|---|
| Ein Topf pro Verein | Manager entscheidet frei, wo er investiert | getrennte Transfer-/Gehaltsbudgets |
| Gehalt pro Pflichtspiel, ganzer Kader | Erfolg (mehr Spiele) kostet automatisch mehr; koppelt Kosten an Spielbetrieb | Wochen-/Monatsgehalt |
| Log-progressive Gehaltsformel | bremst gezielt Topkader; stetig = keine Stufen-Exploits; real verdienen Stars überproportional | WSC-Flatfaktor (MW ÷ konstant); Staffeltarife |
| Median-Anker der Gehälter | tm-Marktwerte steigen real über Jahre; Senke skaliert automatisch mit — kein manuelles Nachdrehen wie im WSC | jährliche Handanpassung des Gehaltsfaktors |
| Zuschauer-Nachfrage aus Kader-MW | kein pflegebedürftiger Fanbasis-Stat; verhindert „alle bauen 120.000"-Exploit strukturell; Wachstumspfad: erst Erfolg, dann Ausbau | wachsende Fanbasis als eigener Wert |
| Freie Ticketpreise mit Elastizität | echte Managerentscheidung (Beliebtheit/Gegner beobachten) | Systempreise je Liga |
| Sponsorangebote auf Präsidenten-Erwartung gepreist | kein „objektiv bestes" Angebot; City kann nicht blind den Sieggeld-Vertrag nehmen; ein Erwartungssystem für Präsident + Sponsor | fixe Sponsortabellen; Fanbeliebtheit als Input |
| Prämien = nur Wettbewerbsgelder | Ligaerfolg wird bereits über Platzgeld/Koeffizient/Sponsorvariable/Zuschauer bezahlt — keine Doppelbezahlung; Erwartungserfüllung → Hoeneß-Coin (kein Geld) | Platzierungsprämien on top |
| TV: Ländertöpfe nach Koeffizienten-Rang, komprimierte Spreizung | kollektives Liga-Interesse; Kleinländer (Basel, Utrecht) bleiben spielbar (Faktor ~5 statt real ~13) | reale Verteilungsschlüssel |
| Betriebskosten als Umsatzquote (34 %) | Simulationsbefund: ohne diese Senke wächst die Geldmenge um >40 %/Saison (WSC-Syndrom); trifft Horter proportional | flache Geschäftspauschale; eigenes Mitarbeiter-Modul |
| Schmerzgrenze v2 mit Zukunftswert (MW-Kurve je Stärkeband) | reine MW-Multiplikatoren versagen bei 50k-Talenten (Basis zu klein) und alternden Stars (MW altersgedrückt, Verein kennt wahre Stärke — Ito-Fall) | Schmerzgrenze nur als MW-Faktor |
| KI kennt alle wahren Werte, eine Bewertungsformel beidseitig | jedes KI-Angebot ist ernsthaft (aus derselben Rechnung wie der Verkauf); hohes Gebot auf No-Name = bewusstes Info-Signal (Potentiale aus FM/EA sind ohnehin halböffentlich) | Informationsasymmetrie (KI sieht nur öffentliche Daten) + KI-Scouting |
| Drei Kauftypen (Bedarf 100 % / Qualität 85 % / Talent-Slot 90 %) | klare Antwort auf „wann kauft die KI überhaupt"; Abstiegskandidaten kaufen nie Talente (Dringlichkeitsdiskont als Torwächter) | ungeregeltes KI-Bieten |
| Bedarfsrechnung über Beste-11 + Mindest-Backups | kein Verein hält zwei gleichstarke Torhüter; reale Kader = starke Elf + schwächere Bank/Talente; Beste-11 ≠ tatsächliche Startelf (keine Phantom-Lücken durch Taktikexperimente) | Soll-Tiefe ×2 mit enger Stärketoleranz |
| Kein Ausgabendeckel, keine Eskalationsregel für Manager | wer 400 Mio verdient hat, darf sie ausgeben (kompletter Kaderumbruch legitim); Preisbremse liegt beim Verkäufer (Schmerzgrenze), nicht in künstlichen Regeln | 50 %-Fensterdeckel; +25 %-Eskalation pro Verkauf |
| KI-Vereine horten nie (Budgetregel: Puffer, Rest gezielt reinvestiert) | eliminiert den größten Geldüberhang aus der Simulation; übernommene Vereine haben gesunde Kasse | passive KI-Konten |
| Ausbildungsabgabe als reine Umverteilung (nichts wird vernichtet) | belohnt Ausbildungsvereine (Basel verdient an Koloto noch Jahre später); nicht auszahlbare Anteile werden gar nicht erhoben; Tausch-Basis = MW als einzige manipulationssichere Zahl | vernichtete Transfersteuer (Tausch-Umgehung; „Basel bekommt nur 19 von 20") |
| Tausch nur Manager-zu-Manager, KI nie | KI-Tauschbewertung ist fehleranfällig und exploitbar | KI-Tauschangebote |
| Auktionen als dosierbare Senke; Verbandsabgabe nur manuell durch Admin | Erlöse verlassen das System dort, wo Geld liegt — freiwillig, mit Spielspaß; kein Automatismus bestraft je einen Sparer (Stadion-Sparen ist erwünscht) | automatische Vermögensabgabe ab Schwellwert |
| Startbudget = 20 % des projizierten Jahresumsatzes | gleiche Handlungsfähigkeit in jeder Preisklasse; MW-Basis hätte genau den Defizitvereinen (PSG/City) die dicksten Polster gegeben | Einheitsbetrag; Kader-MW-Basis |
| Ledger als einzige Wahrheit | Kontostand = Summe der Buchungen, nie separat gepflegt; Monitoring & Manager-Kontoauszug sind reine Aggregationen | gepflegtes Konto-Feld + separate Statistik |
| Zahlungsgrenze 0 identisch für alle Vereinsgrößen, keine Zusatz-Transfersperre im Minus | jeder wirtschaftet in seinen Mitteln; Käufe scheitern im Minus ohnehin an fehlender Deckung (Grundregel 2), Verkäufe/Tausch bleiben als Weg ins Plus offen | größenrelative Warnstufen (open-football); Transfersperre bis Tilgung |
| Gehalts-MW bleibt live (Monatsupdates), kein Saison-Einfrieren | WSC-Praxis über 34 Saisons zeigt: Manager können mit unterjährigen MW-Sprüngen umgehen; Puffer halten ist Teil des Spiels | Saison-Snapshot der Gehalts-MW; Wachstumskappung |
| Zahlungsunfähigkeit als Verfahren (Vermerk → 7 Tage → Zwangsversteigerung), Pflichtbuchungen dürfen ins Minus | verweigerte Gehaltsbuchungen wären exploitbar (Konto absichtlich leerräumen); WSC-Vorbild §2(1) | Gehaltsbuchung schlägt fehl / verpufft |
| Preiselastizität am Liga-Referenzpreis verankert | Websoccer ankert an der eigenen Preishistorie — exploitbar durch langsames Hochschleichen der Preise | Eigenhistorie-Anker (Websoccer-Modell) |
| Karriereende ohne Abfindung, Todesfall mit WSC-Alterstabelle | Alterungsrisiko ist Spielelement; ein Todesfall ist unverschuldet und endgültig — Staffel kompensiert den Zukunftsverlust, Seltenheit macht die Geldschöpfung unbedenklich | Abfindung auch bei Karriereende (WSC) bzw. gar keine Entschädigung |
| Leihen, Einberufungen, Stadionpflege-Stufen bewusst ausgeklammert | eigenständige Module mit Finanz-Hooks (Leihgebühr, Einberufungsgebühr als dosierbare Senke — Preise noch festzulegen, Pflege-Auslastungseffekt) — Anbindung ans Ledger jederzeit möglich | Einbau in diese Spec |
