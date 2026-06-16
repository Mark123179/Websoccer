"""Quell-Adapter — je Datenquelle ein Modul mit gekapselten Selektoren.

Die Selektoren jeder Quelle (Transfermarkt, FMInside) bleiben strikt im
jeweiligen Adapter. Der übrige Code kennt nur die normalisierten Rückgabewerte.

SoFIFA-/EA-Ratings werden hier bewusst NICHT live gescrapt (Cloudflare, nicht
verifizierbar) — sie kommen über den CMTracker-/SoFIFA-CSV-Export in die DB.
"""
