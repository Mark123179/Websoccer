---
name: Insolvenz-Verfahren & Zwangsversteigerung V1
description: Design-Entscheidungen Finanzsystem Phase 5 — Vermerk-Hooks, Zwangsversteigerung, Auktions-Senke, Verbandsabgabe, Monitoring
---

# Insolvenz-Verfahren & Zwangsversteigerung V1 (Phase 5, Spec 11/12.3/12.5)

## Vermerk-Hooks (Zahlungsunfähigkeit)
- Hooks leben IM heißen Buchungspfad (`_create_booking`), unter der bereits gesperrten Club-Zeile — keine neue Lock-Reihenfolge, keine Extra-Queries: reine Vorzeichen-Guards (Pflichtbuchung ≥0→<0 öffnet Vermerk, jede Buchung <0→≥0 schließt ihn).
- **Why:** Spec 12.4 Lock-Reihenfolge (Club-Row serialisiert Geld pro Verein); Hook außerhalb der Transaktion wäre racy.
- DB-Backstop: Partial-Unique-Constraint „ein offener Vermerk pro Verein".
- Frist = 7 echte Kalendertage (nicht Spieltage).

## Zwangsversteigerung
- Erlös geht an den Verein → Settlement via `execute_money_transfer` (TRANSFER_AUS/EIN, Zirkulation) — NICHT die AUKTION-Senke. Nur Scouting-Auktionen vernichten Geld (Typ `AUKTION`).
- Gebote verdeckt, KEINE Budget-Reservierung; Deckung wird erst beim Zuschlag geprüft; scheitert sie (TransferError/InsufficientFunds), Kaskade zum nächsthöheren Gebot, sonst unsold.
- **Konto während Laufzeit bereinigt (budget ≥ 0 oder Case resolved) → Auktion wird ABGEBROCHEN (cancelled), nicht zugeschlagen.** Verkäufe sind der vorgesehene Weg zurück ins Plus; Zwangsvollstreckung gilt nur anhaltender Zahlungsunfähigkeit.
- Mindestkader-Guard beim Ansetzen zählt bereits laufende Auktionen mit.
- Auflösung täglich per Celery-Beat (`resolve_forced_auctions`).

## Verbandsabgabe (12.5)
- HART deaktiviert: Seed `VERBANDSABGABE.enabled=False` (Saison '0', Fallback vererbt auf alle Saisons); Runner wirft bei disabled, `--dry-run` rechnet trotzdem. Aktivierung = bewusste Param-Änderung, kein Code.
- Formel: satz × (kontostand − faktor × Jahresumsatz); Jahresumsatz = positive Ledger-Summe der Saison.

## Monitoring (Creator-Finanzanalyse)
- Geldmengen-Verlauf = Rückwärtsrechnung von heutiger Geldmenge über Saison-Nettoflüsse (Approximation, ignoriert KORREKTUR_ADMIN); Alarm >4 %/Saison.
- Ablöse/MW-Median nutzt TRANSFER_AUS mit referenz_typ='transfer' + aktuellen MW als Näherung; Ziel 1,3–1,8, Alarm >2,2.
- Totes Kapital: Kontostand > 2× Jahresumsatz.
