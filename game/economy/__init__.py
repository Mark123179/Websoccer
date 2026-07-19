"""Finanzsystem (Spec „Finanzsystem — Blueprint“, Phase 1).

Module:
    params        — EconomyParameter-Zugriff mit Saison-Fallback
    booking       — zentrale Buchungsfunktion book() (Ledger + Konto-Cache)
    salary        — log-progressive Gehaltsformel (Kap. 4)
    snapshot      — SeasonEconomySnapshot (MW-Median, Gehalts-Anker)
    matchday_run  — finance_matchday_run (Kap. 15, Phase-1-Umfang)
"""
