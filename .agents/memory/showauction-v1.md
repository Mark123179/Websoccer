---
name: Show-Auktion V1 (TV-Transfershow)
description: Architektur-Invarianten und Stolperfallen des showauction-Moduls (16-Achsen-Config, Escrow, Coin-Ticket, Raum-Mechanik)
---

# Show-Auktion V1 — Invarianten

## Validator-Kontrakt (Stolperfalle)
`showauction.validator.validate_config(config)` **wirft** `django.core.exceptions.ValidationError`
(Liste deutscher Meldungen) und gibt bei Erfolg die **normalisierte Config (dict)** zurück —
KEINE Fehlerliste. Aufrufer müssen den Rückgabewert weiterverwenden (setdefault-Normalisierung).
Bedingungs-Overrides (`create_auction(conditions=…)`) werden in die Config eingesetzt und laufen
durch dieselbe Prüfung — nie einen zweiten Prüfpfad bauen.

## Escrow-Invariante (kein Kader/Budget-Re-Check im Settlement)
Die Geld+Slot-Reservierung des führenden Gebots bleibt bis `consume()` im Settlement aktiv und
zählt in `_check_kaderplatz`/Deckungsprüfungen aller Normaltransfers mit. Darum braucht `_settle`
keinen Kaderplatz-Re-Check. Freigegeben wird bei `bei_ueberbietung` nur die Reservierung des
ÜBERBOTENEN (der hat keinen Anspruch mehr). Buchung als `pflicht=True` außer bei
`sofortige_buchung` (Dutch prüft live).

## Locking / Nebenläufigkeit
Alle Gebots-/Abwicklungspfade serialisieren an der Auktionszeile (`select_for_update`).
Reihenfolge: Auktion → Club (in `book()`) → Spielerzeile; Coin-Zeile ist immer das LETZTE Lock.
Kein Deadlock-Zyklus möglich, weil der Auktionsspieler per `pool_status='show_auction'` (Raum)
für Transfer-/Scouting-Pfade unsichtbar ist. Idempotenz des Settlements: Status-Guard unter Lock
+ UniqueConstraint auf der Buchung (`referenz_typ='showauction_settle'`).

## Coin-Eintrittsticket
Verbrauchston: 1 Coin atomar mit dem ERSTEN Gebot je (Manager, Auktion), markiert via
`coin_charged` am Bid; kein Refund, auch nicht beim Platzen. `HoenessCoin` per
`select_for_update().get_or_create` (Djangos get_or_create ist race-safe). Verfügbarkeit =
amount − Scouting-Earmarks.

## Preis-Semantik (Test-Falle)
Dutch-Verfall: `schritt_prozent` ist % vom **MW-Snapshot**, nicht vom Startpreis.
Mindesterhöhung aufsteigend: `max(absolut, prozent × aktuelles Top)`. Preise entscheidet NUR der
Server (`buy_now` rechnet `dutch_price` selbst, Client-Betrag wird ignoriert).

## UI-Anbindung
Manager-Seiten setzen `game_header` via `build_game_header()` (sonst leerer globaler Header);
Creator-Seiten haben projektweit KEINEN game_header — nicht "nachrüsten".
Wechselsperre-Anzeige läuft über `player.transfer_lock_days_remaining`.

## Full-bleed-Bühne (User-Vorgabe 2026-08-04)
Die Bühnen-Seite ist bewusst full-bleed OHNE Scouting-Nav-Pills: `main.container` hat KEIN
Padding (nur margin-left: var(--sidebar)); die Einrückung trägt allein der ws-game-header
(margin 0 24px 22px). Restfläche der logischen Bühne (1884×1177.5) unter dem Header ≈ 1029px
Stage-Höhe. Alles scoped unter `.sxa-wrap--stage` (Golden-Master-Regel) — Detailseite behält
die zentrierte 1152px-Spalte MIT eigener Wrap-Klasse ohne Modifier.
