# Spielstaerke-Playbook

Stand: 11.05.2026

Dieses Playbook beschreibt den aktuellen Arbeitsstand des Spielstaerkemodells. Es
ist die Referenz fuer kommende Sprints, solange keine bewusstere Version ersetzt.

## Grundprinzip

Die interne Staerke laeuft auf einer Skala von `0.00` bis `200.00` und bleibt fuer
Manager verborgen. Admins sehen die exakten Werte und die Zusammensetzung.

Marktwert hat keinen Einfluss auf sportliche Staerke. Marktwert bleibt ein Faktor
fuer Gehalt, Transferpsychologie, Prestige und Budgetplanung.

Die Spielstaerke entsteht in dieser Reihenfolge:

```text
Source-Base
-> Match-Peak aus Potential
-> RL-Formmodifier
-> WS-Positionsfit
-> WS-Frischeabzug
= effektive Spielstaerke fuer dieses WS-Spiel
```

Es gibt aktuell keinen Softcap und keinen harten Form-Cap. Werte nahe `200.00`
sollen selten bleiben, weil Potential, Form und Frische natuerlich begrenzt sind.
Das muss spaeter mit echten Massendaten geprueft werden.

## Source-Base und Potential

Base-Staerke:

```text
EA/SoFIFA/FIFAIndex-Staerke + FMInside-Staerke
```

Fallbacks:

```text
nur EA vorhanden: Base = EA * 2
nur FM vorhanden: Base = FM * 2
keine Quelle vorhanden: Base = 40.00 und Datenpruefung markieren
```

Potential-Ceiling:

```text
EA-Potential + FM-Potential
```

Bei FM-Potentialspannen wird die Spanne gespeichert. Beispiel Lennart Karl:

```text
EA-Potential: 88
FM-Potential: 75-90

Potential-Min: 88 + 75 = 163.00
Potential-Max: 88 + 90 = 178.00
```

`Potential-Max` ist die absolute Ausnahme-Obergrenze fuer ein einzelnes WS-Spiel,
nicht der normale Erwartungswert. `Potential-Min` zeigt den vorsichtigeren
Potentialbereich und kann spaeter fuer Admin-/Scoutinghinweise genutzt werden.

## Match-Peak

Der Match-Peak gilt nur fuer ein einzelnes WS-Spiel. Er veraendert weder Base noch
langfristige Entwicklung.

```text
Match-Peak = Base + zufaelliger Anteil der Potential-Luecke
Potential-Luecke = Potential-Ceiling - Base
```

Die Verteilung ist fliessend, nicht in festen Stufen. Kleine Peaks sind haeufig,
mittlere Peaks gelegentlich, grosse Peaks selten. `90-100 %` der Luecke sind sehr
selten. `100 %` ist moeglich, aber ein Ausnahmeabend.

Wichtig: Der Anteil bezieht sich nur auf die unbewiesene Potential-Luecke, nicht
auf das gesamte Koennen des Spielers. Ein Spieler mit `Base 140` und `Potential
178` ist bereits bei `Base 140`; ein Peak von `60 %` bedeutet `140 + 22.80`.

## RL-Formmodifier

Version 1 nutzt bewusst wenige robuste Daten:

```text
RL-Formmodifier = (Minutenmodifier + Ratingmodifier) * Liga-Koeffizient
```

Nicht in der V1-Formel:

- Startelfbonus
- Captainbonus
- gelbe/rote Karten
- SportDB-/Flashscore-Position
- xG, xA und weitere Playerstats

Die WS-Positionen werden im Websoccer gepflegt. Die reale API-Position ist fuer
die Staerkeformel kein Faktor.

### Minutenquote

```text
Minutenquote = gespielte Minuten / moegliche Minuten
```

Aktuelle Arbeitstabelle:

| Minutenquote letzte 3 Monate | Modifier |
|---:|---:|
| 90-100 % | +4.00 |
| 75-89 % | +2.50 |
| 60-74 % | +1.00 |
| 40-59 % | -1.00 |
| 20-39 % | -3.00 |
| 5-19 % | -6.00 |
| 0-4 % | -8.00 |

### Ratingmodifier

Das Rating wird minutengewichtet berechnet. Spiele ohne Rating zaehlen fuer die
Minutenquote, aber nicht fuer den Ratingdurchschnitt.

```text
gewichtetes Rating = Summe(Rating * Minuten mit Rating) / Summe(Minuten mit Rating)
Ratingmodifier = (gewichtetes Rating - Liga-Medianrating) * 5
```

Das Liga-Medianrating soll dynamisch aus allen importierten Spielern der Liga
berechnet werden. Keine Positionsgruppen fuer den Median, weil Fussballpositionen
zu schwammig sind und Flashscore das Rating bereits rollenbezogen bewertet.

### Liga-Koeffizient

Der Liga-Koeffizient wirkt nur auf die RL-Form, nicht auf die Base.

```text
Bundesliga-Arbeitswert: 1.00
```

Spaeter wird eine Liga-Tabelle gepflegt, zum Beispiel anhand UEFA-Koeffizienten
und interner Balancingwerte.

## Datenimport-Regeln

SportDB/Flashscore ist aktuell der wichtigste Formdaten-Pilot.

Lineup-Daten duerfen zum Finden des Spielers genutzt werden, reichen aber nicht
als Minuten-Wahrheit. Bankspieler koennen im Lineup-Payload auftauchen.

Prioritaet fuer Minuten:

```text
1. playerstats.matchMinutesPlayed
2. details-Wechselereignisse
3. sonst 0 Minuten
```

Playerstats werden in Version 1 nicht in die Staerkeformel eingerechnet. Wenn sie
geladen werden, sollen spaeter nur die Werte des konkreten Spielers extrahiert
werden. Der komplette Playerstats-Rohpayload soll nicht dauerhaft gespeichert
werden.

Aktueller Batch-Import:

```text
python manage.py import_sportdb_flashscore_team_form --refresh-existing
```

Stand 11.05.2026:

- Bayern und Dortmund wurden fuer die letzten 90 Tage Bundesliga importiert.
- 612 SportDB/Flashscore-Snapshots liegen vor.
- 23 Playerstats-Abfragen reichten fuer beide Vereine.
- Fuer jedes Vereinsspiel wird fuer jeden aktuellen RL-Spieler ein Snapshot
  geschrieben, auch bei 0 Minuten. Dadurch bleibt die Minutenquote korrekt.
- In der aktuellen Datenbasis haben 45 Spieler ein minutengewichtetes Rating.
  Der dynamische Bundesliga-Median liegt bei `7.20`.

Moegliche spaetere Playerstats fuer Rollenprofile:

- Offensive: xG, Schuesse, Schuesse aufs Tor
- Aufbau: xA, Paesse ins letzte Drittel, lange Paesse, Passgenauigkeit
- Defensive: Zweikaempfe, Tackles, Interceptions, Clearances, Fehler
- Torwart: Saves, Goals Prevented, xGOT faced

Diese Werte sind aktuell nur Kandidaten fuer Feinschliff, Managertexte oder
Rollenprofile, nicht fuer den V1-Formkern.

## Django-Verwaltung

Im Spielerprofil zeigt der Reiter `STAERKE` eine farbige Admin-Vorschau der
aktuellen Berechnung:

- Source-Base und Potential-Ceiling
- Potential-Luecke
- Minutenquote und Minutenmodifier
- gewichtetes Rating, Liga-Median und Ratingmodifier
- Liga-Koeffizient
- RL-Formmodifier
- Frischewert, Frischeabzug und Risiko
- Base + Form + Frische
- Beispiel-Peaks fuer `20 %`, `50 %`, `85 %` und `100 %` der Potential-Luecke

Die anpassbaren Werte liegen im Admin-Modell `Spielstaerke-Modifikatoren`.
Dort werden gepflegt:

- Ratingmodifier-Faktor
- Fallback-Liga-Medianrating
- Default-Frische
- Minutenquote-Regeln
- Frischeabzug- und Risiko-Regeln

## WS-Positionsfit

Die WS-Positionen werden manuell gepflegt:

- bis zu 3 Hauptpositionen
- bis zu 3 Nebenpositionen

Arbeitslogik:

```text
Hauptposition: kein Malus
Nebenposition: kleiner Malus
nicht gepflegte Feldposition: harter Malus
Torwart/Feldspieler-Fremdeinsatz: extremer Malus
```

Die genaue Punktzahl fuer Positionsmalus wird spaeter in der Match-Engine
balanciert.

## Frische

Frische ist kein Multiplikator mehr. Sie wirkt als Punktabzug, damit starke und
schwaechere Spieler bei gleicher Frische nicht unterschiedlich hart getroffen
werden.

Aktuelle Arbeitstabelle:

| Frische | Staerkeabzug | Risiko |
|---:|---:|---|
| 90-100 | 0.00 | keins |
| 85-89 | -0.50 | keins |
| 80-84 | -1.00 | keins |
| 75-79 | -1.50 | leicht |
| 70-74 | -2.00 | erhoeht |
| 65-69 | -3.00 | spuerbar |
| 60-64 | -4.00 | hoch |
| unter 60 | staerker | deutlich |

Risiko beginnt bei `75-79` leicht und steigt danach alle 5 Frischepunkte.

Frische-Regeneration wird spaeter separat modelliert. Aktuelle Richtung:

- alle Spieler starten zunaechst mit `100`
- Regeneration haengt spaeter von aktuellem Frischewert, WS-Spielzeit, Taktik,
  Angriffs-/Abwehrfokus, Einsatzart und Athletik ab
- Spieler naeher an `100` sollen leichter wieder voll werden als tief erschoepfte
  Spieler

## Verletzungen und Sperren

Real-Life-Verletzungen fuehren nicht zu automatischen WS-Sperren und nicht zu
direkter Staerkesenkung. Sie wirken indirekt ueber fehlende Minuten und damit
ueber RL-Form.

WS-Verletzungen und WS-Sperren sind eigene Spielmechaniken und werden separat im
Spielerprofil gepflegt.

## Beispiel Harry Kane

Arbeitsdaten:

```text
EA-Staerke: 90
FM-Staerke: 94
Base: 184.00

EA-Potential: 90
FM-Potential: 95
Potential-Ceiling: 185.00
```

Formbeispiel aus importierten SportDB-Daten:

```text
Minuten: 610 / 1080 = 56.48 %
Minutenmodifier: -1.00

gewichtetes Rating: 8.03
Liga-Median aktuell: 7.20
Ratingmodifier: (8.03 - 7.20) * 5 = +4.15

Liga-Koeffizient: 1.00
RL-Formmodifier: +3.15
```

Beispielrechnung mit Match-Peak `184.60` und Frische `100`:

```text
Match-Peak:       184.60
RL-Formmodifier:   +3.15
Frischeabzug:       0.00
Endstaerke:       187.75
```

## Beispiel Lennart Karl

Arbeitsdaten:

```text
EA/FIFAIndex-Staerke: 75
FMInside-Staerke: 65
Base: 140.00

EA-Potential: 88
FM-Potentialspanne: 75-90
Potential-Min: 163.00
Potential-Max: 178.00
```

Korrigierte SportDB/Flashscore-Minuten der letzten 3 Monate:

| Spiel | Minuten | Rating |
|---|---:|---:|
| Werder Bremen | 90 | 7.30 |
| Eintracht Frankfurt | 0 | - |
| Dortmund | 0 | - |
| B. Monchengladbach | 90 | 7.90 |
| Bayer Leverkusen | 61 | 6.50 |
| Union Berlin | 61 | 6.40 |
| Freiburg | 90 | 7.60 |
| St. Pauli | 0 | - |
| Stuttgart | 0 | - |
| Mainz | 0 | - |
| Heidenheim | 0 | - |
| Wolfsburg | 14 | 6.70 |

```text
Minuten: 406 / 1080 = 37.59 %
Minutenmodifier: -3.00

gewichtetes Rating: ca. 7.22
Liga-Median Beispiel: 6.80
Ratingmodifier: (7.22 - 6.80) * 5 = +2.10

Liga-Koeffizient: 1.00
RL-Formmodifier: -0.90
```

Beispielrechnungen mit Frische `100`:

```text
normaler Peak 20 %:
140.00 + 7.60 - 0.90 = 146.70

guter Peak 50 %:
140.00 + 19.00 - 0.90 = 158.10

sehr starker Peak 85 %:
140.00 + 32.30 - 0.90 = 171.40

Ausnahmepeak 100 %:
178.00 - 0.90 = 177.10
```

Karl bleibt meistens klar unter Kane, kann aber an besonderen Tagen deutlich ueber
seine Base hinauswachsen.

## Offene Balancing-Punkte

- exakte Peak-Verteilung und Wahrscheinlichkeit fuer `90-100 %`
- echte Liga-Medianratings aus Massendaten statt Beispielwert `6.80`
- finale Liga-Koeffizienten
- genaue Positionsmaluswerte
- finale Frischeverlust- und Regenerationsformel
- Monitoring, ob ohne Softcap zu viele Spieler Richtung `200.00` laufen

## Balancing-Warnungen aus Agentenreview

Das aktuelle Modell bleibt ohne Softcap festgehalten. Fuer spaetere Simtests muss
aber aktiv geprueft werden, ob sich zu viele Spieler in den Bereich `190+`,
`195+` oder `200.00` bewegen.

Kritische Punkte:

- Topspieler starten durch `EA + FM` bereits sehr hoch; starke RL-Form kann sie
  schnell in den Bereich `190+` bringen.
- Grosse Potentialluecken duerfen nicht nur Upside bedeuten. Talente sollen auch
  mehr Schwankung und geringere Verlaesslichkeit haben.
- FM-Potentialspannen duerfen Datenunsicherheit nicht automatisch belohnen. Die
  Obergrenze ist ein Ausnahme-Ceiling, kein normaler Erwartungswert.
- Dynamische Liga-Medianratings sind gut, brauchen aber ausreichend Datenmenge.
- Minutenquote soll Verfuegbarkeit und Trainervertrauen abbilden, darf Joker und
  junge Rotationsspieler aber nicht zu hart bestrafen.
- Peak-Chance sollte spaeter an Frische und reale Minutenstabilitaet gekoppelt
  werden, damit kaum eingesetzte Talente nicht zu oft als Upside-Lotterie dienen.

Empfohlene Monitoring-Kennzahlen fuer Simtests:

- Anteil Spieler pro Spieltag mit effektiver Staerke `>190`, `>195`, `=200`
- Anteil U21-Spieler in den Top-100-Matchstaerken
- durchschnittlicher Peakbonus nach Altersgruppe und Potentialluecke
- durchschnittlicher RL-Formmodifier nach Liga
- durchschnittliche Startelf-Frische und Rotationsverhalten

Moegliche Gegenmassnahme, falls Inflation entsteht:

- keine pauschale Rueckkehr zum harten Softcap
- zuerst Peak-Wahrscheinlichkeiten, Formmodifier-Faktor oder Hochwert-Kompression
  ab `190` testen
