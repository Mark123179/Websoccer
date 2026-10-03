"""match_story — Live-Ticker-Erzähler für BLUEPRINT.

Baut aus report_data (+ TacticSetup) einmalig die Ereignisliste eines Spiels:
Sequenzen aus Beats, jede Zeile mit Minute, Akteuren, Sichtbarkeit, Abspiel-Offset
und Dauer. Django-frei, deterministisch (Seed = match id).
"""
from .narrator import narrate  # noqa: F401
