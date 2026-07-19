"""Zentrale Buchungsstelle für Vereins-Finanztransaktionen.

Seit dem Finanzsystem Phase 1 (Spec Kap. 12) ist das FinanceTransaction-
Ledger die einzige Wahrheit: game.economy.booking.book() schreibt Ledger-
Zeile UND Konto-Cache (Club.budget) atomar.

log_club_transaction() bleibt als DEPRECATED-Kompatibilitäts-Wrapper für
Alt-Aufrufer erhalten und delegiert an book() — Achtung: es mutiert damit
jetzt AUCH das Budget. Aufrufer dürfen das Budget nicht mehr selbst
verändern (sonst Doppelbuchung). Neue Aufrufer nutzen direkt
game.economy.booking.book().

Saison-Konvention: numerische Sim-Saison als String
(GameSeasonState.current_season, z. B. "0", "1").
"""

# Mapping Alt-Kategorie (ClubFinancialTransaction) → neuer Buchungstyp.
LEGACY_CATEGORY_TO_TYP = {
    'ticketverkauf':     'TICKET',
    'sponsor':           'SPONSOR_FIX',
    'tv_gelder':         'TV_SOCKEL',
    'transfer_einnahme': 'TRANSFER_EIN',
    'leih_einnahme':     'TRANSFER_EIN',
    'praemie':           'PRAEMIE_POKAL',
    'sonstige_einnahme': 'KORREKTUR_ADMIN',
    'transfer_ausgabe':  'TRANSFER_AUS',
    'profigehalt':       'GEHALT',
    'jugendgehalt':      'GEHALT',
    'stadionkosten':     'AUSBAU',
    'stadionumfeld':     'UMFELD_AUSBAU',
    'sonstige_ausgabe':  'KORREKTUR_ADMIN',
}


def current_sim_season():
    """Aktuelle Sim-Saison als String ("0", "1", …); leer wenn kein Zustand."""
    from game.models import GameSeasonState
    state = GameSeasonState.objects.only('current_season').first()
    return str(state.current_season) if state else ''


def log_club_transaction(club, category, description, amount,
                         date=None, season=None):
    """DEPRECATED — delegiert an game.economy.booking.book().

    Schreibt eine Ledger-Zeile UND aktualisiert Club.budget atomar.
    Der Aufrufer darf das Budget NICHT zusätzlich selbst mutieren.
    Buchung erfolgt als Pflichtbuchung (kein Deckungs-Abbruch), damit
    Alt-Aufrufer, die die Deckung bereits selbst geprüft haben, ihr
    Verhalten behalten.
    """
    from game.economy.booking import book

    typ = LEGACY_CATEGORY_TO_TYP.get(category, 'KORREKTUR_ADMIN')
    return book(
        club, typ, amount,
        beschreibung=description,
        saison=season,
        datum=date,
        referenz_typ=f'legacy:{category}',
        pflicht=True,
    )
