"""Transfersystem v2 — Backend-Fundament (Master-Spec §§2–6, Design-Spec §13).

Reine Backend-Schicht: Modelle, Zustandsautomaten, Escrow-/Buchungslogik,
Jugendabgabe, WP/SE-Vollzug, Leih-Grundregeln und Hintergrund-Jobs. Keine
UI (folgt in den Reiter-Aufgaben).

Verbindliche Regeln (Kurzreferenz):
- Mindestgebot ≥ 500.000 €, Mindesterhöhung max(100.000 €, 5 %) → auf 50.000 € gerundet.
- Anti-Sniping: Gebot < 60 min vor Ende → +24 h, unbegrenzt.
- Jugendabgabe: 8 % gesamt, min. 50.000 € je Ausbildungsverein.
- Wechselsperre 21 Tage nach jedem Vollzug.
- Kein Auto-Bieten.

Alle Geldflüsse laufen ausschließlich über game.economy.booking.book()/book_many()
und die Escrow-Schicht game.economy.reservations — nie direkt auf Club.budget.
"""
