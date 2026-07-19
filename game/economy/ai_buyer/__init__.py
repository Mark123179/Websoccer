"""KI-Käufer Stufe 2 (Spec Kap. 9.3) — aktive KI-Vereine als Marktteilnehmer.

Public API (re-exportiert):
  bedarf     — beste_elf, liga_soll, bedarfs_analyse, dringlichkeit
  budget     — fixkosten_puffer, ueberschuss
  kandidaten — finde_kandidaten, erwartete_forderung
  offers     — create_offer, manager_annehmen, manager_ablehnen,
               ki_zu_ki_clearing, expire_offers, storniere_offene_fuer_spieler
  pruflauf   — run_ai_buyer_matchday, run_club_pruflauf, governor_status

Auslieferungszustand: KI_KAEUFER['dry_run'] = True (Trockenlauf) —
Angebote werden berechnet und geloggt (Status 'berechnet'), aber nicht
versendet, bis der Admin in der KI-Transferzentrale scharf schaltet.
"""
from .bedarf import beste_elf, liga_soll, bedarfs_analyse, dringlichkeit
from .budget import fixkosten_puffer, ueberschuss
from .kandidaten import finde_kandidaten, erwartete_forderung
from .offers import (
    AIBuyerError,
    create_offer,
    expire_offers,
    ki_zu_ki_clearing,
    manager_ablehnen,
    manager_annehmen,
    storniere_offene_fuer_spieler,
)
from .pruflauf import governor_status, run_ai_buyer_matchday, run_club_pruflauf

__all__ = [
    'beste_elf', 'liga_soll', 'bedarfs_analyse', 'dringlichkeit',
    'fixkosten_puffer', 'ueberschuss',
    'finde_kandidaten', 'erwartete_forderung',
    'AIBuyerError', 'create_offer', 'expire_offers', 'ki_zu_ki_clearing',
    'manager_ablehnen', 'manager_annehmen', 'storniere_offene_fuer_spieler',
    'governor_status', 'run_ai_buyer_matchday', 'run_club_pruflauf',
]
