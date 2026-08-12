---
name: Transfersystem v2 Fundament
description: Durable Invarianten des v2-Transfer-Backends — Deckung, Autorisierung, Jugendabgabe-Bemessung, Settlement-Determinismus.
---

# Transfersystem v2 — Durable Invarianten

## Deckung / Escrow
- Deckungsprüfungen rechnen gegen ALLE aktiven Reservierungen des Vereins (auch fremde Subsysteme), nicht nur den eigenen Teilbestand; die eigene Reservierung für genau dieselbe Zahlung wird ausgenommen.
- **Why:** Sonst sieht ein Gebot Deckung, die beim Vollzug fehlt, oder die eigene Reservierung zählt doppelt.
- **How to apply:** Escrow VOR der Buchung in derselben Transaktion konsumieren — Rollback stellt sie wieder her.

## Autorisierung & Zustand
- Jeder spielerbewegende Pfad validiert unter Zeilen-Lock bei ERSTELLUNG **und erneut bei ANNAHME/SETTLEMENT** — Sperre, Leihe und Pending können zwischenzeitlich entstehen.
- **Falle Leihe:** Beim geliehenen Spieler zeigt das club-Feld auf den AUFNEHMENDEN Verein — Eigentums-Checks über club allein reichen nicht.
- Typ-Schemata und Geldbeträge werden in der Service-Schicht hart erzwungen (nie nur im Formular): keine negativen/0-€-Preise, Sofortkauf ≥ Mindestgebot.

## Jugendabgabe
- Bemessung: reiner Geld-Deal = NUR gezahlter Preis (anteilig je Spieler); Tausch = Marktwert + anteiliges Gegenseiten-Geld. Nie MW auf einen Kaufpreis addieren.
- Test-Falle: Spieler-Anlage erzeugt automatisch eine Vereinsstation — manuelle Historie in Tests muss die Auto-Station einkalkulieren; eine Leihe erzeugt beim Leihverein eine weitere Station.

## Settlement-Determinismus
- Kadergrenzen sind zum Settlement HART. Aufgeschobene (WP/SE-)Vollzüge desselben Historieneintrags bilden EINE Einheit: Netto-Kadereffekt je Verein prüfen, alle Beine gemeinsam vollziehen oder gemeinsam stornieren (mit vollständiger Geld-/Abgaben-Rückabwicklung) — nie einseitig.
- Auktions-Abschlusskonflikte (Kader, Deckung, Spielerzustand) enden deterministisch: Auktion ohne Zuschlag beenden + SÄMTLICHES Bieter-Escrow freigeben. Ein Retry-Loop, der bindendes Escrow festhält, ist verboten.
- Ablauf-Jobs, die harte Reservierungen freigeben, dürfen nie nur täglich laufen.

## WP/SE-Stichtage
- Kein Kalendermodell für Winterpause/Saisonende; die Terminlogik nähert über Spielplan-Daten und ist bewusst in einem einzigen Modul gekapselt — bei echten Kalenderdaten nur dort umstellen.
