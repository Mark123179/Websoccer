---
name: Transfer v2 Creator-Aufsicht & KI-Regeln
description: Durable Regeln für Admin-Storno, KI-Deal-Antworten, KI-Käufer dry_run-Split; Regressions-Vergleichskette
---

# Transfer v2 — Aufsichts- & KI-Regeln

## Admin-Storno = Ganz-oder-gar-nicht
Rückabwicklung eines TransferRecords bricht hart ab, wenn ein Spieler nicht mehr beim aufnehmenden Verein ist — nie Teil-Storno. Rückzahlungen des Geld-Empfängers sind Pflichtbuchungen (dürfen ins Minus).
**Why:** Teil-Storni hinterlassen inkonsistente Geld/Spieler-Zustände, die niemand mehr auflösen kann.

## Leihen nie über das Vereinspaar auflösen
Aktive Loan-Zeilen IMMER über den Spieler des Records suchen (und owner/loan-Club defensiv gegen den Record prüfen), nie per owner_club+loan_club-Paar.
**Why:** Leih-Limits erlauben mehrere gleichzeitige Leihen zwischen denselben zwei Vereinen; ein Paar-Lookup beendet die falsche Leihe.

## Admin-Transfer ist Aufsichtsakt
KIND_ADMIN bewegt Spieler ohne Buchung, ohne Jugendabgabe und ohne Wechselsperre — bewusst kein normaler Transfer.

## KI-Antworten auf Deal-Anfragen
KI-Vereine antworten nach 24h Bedenkzeit; gefordert = Schmerzgrenze der abzugebenden Spieler; ohne Bewertungs-Datenbasis wird IMMER abgelehnt (KI verkauft nie blind). accept-Fehler (Kaderlimit/Deckung) enden als Decline, nie als hängender OPEN-Deal. dry_run (KI_KAEUFER) = reiner Zähl-Lauf ohne Schreibzugriff.

## KI-Käufer dry_run-Split
Trockenlauf erzeugt weiterhin AITransferOffer STATUS_BERECHNET (speist die Creator-KI-Transferzentrale); nur der Scharfbetrieb erzeugt v2-DealRequests (mit Escrow-Reservierung). Kadenz-Zähler müssen Alt-Angebote UND offene v2-Deals gemeinsam zählen, solange Altbestände existieren. KI gibt weiterhin keine Auktionsgebote ab.

## Legacy-Verhandlung: UI weg, Views bleiben
TransferNegotiation/AITransferOffer-Views nicht löschen — Wirtschaftslogik/Tests nutzen sie direkt; nur die Kader-UI-Einbindung wurde entfernt. Aufräumen offener Altvorgänge via idempotentem Command (close_legacy_transfer_flows).

## Regressions-Vergleichskette
run_regression_v3.sh vergleicht immer gegen den LETZTEN Lauf.
**Why:** Ein kurzer Smoke-Lauf (--seasons 2) verschmutzt die Kette und erzeugt Schein-Alarme in beide Richtungen.
**How to apply:** Validierung nur mit --seasons 20; nach einem Kurz-Lauf Alarme gegen den letzten 20-Saisons-Lauf manuell nachrechnen.
