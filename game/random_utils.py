"""
game/random_utils.py — Zentrale deterministische Zufallshilfen.

Alle Module (Ticker, Elfmeter-RNG, Pokalauslosung, …) importieren
stable_seed() aus dieser Datei, damit ein gemeinsamer SHA-256-Seed
über Prozessneustarts hinweg stabil bleibt (kein PYTHONHASHSEED-Problem).
"""
from __future__ import annotations

import hashlib


def stable_seed(*parts: object) -> int:
    """SHA-256-basierter Seed — prozessübergreifend stabil.

    Nimmt beliebig viele Teile entgegen und bildet daraus einen
    deterministischen Integer-Seed:
        stable_seed("cup-draw", 42, "2026/27")
    Gleiche Eingabe → immer gleicher Integer.
    """
    raw = "|".join(str(p or "") for p in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")
