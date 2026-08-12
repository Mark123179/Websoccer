"""Escrow-/Reservierungsschicht des Transfersystems v2.

Reservierungen laufen über die bestehende generische
game.economy.reservations-Schicht (FinanceReservation). Zusätzlich pflegt
Task #819 einen Cache-Wert Club.reserved (Master-Spec §4.1: "reserved" als
Feld), damit der Budget-Kopf ohne Aggregat-Query rechnet.

Invariante (Master-Spec §4.1):
    reserved = Summe der Geldanteile aller FÜHRENDEN eigenen Gebote
             + aller OFFENEN gesendeten Deal-/Leihanfragen (Geldanteil des Initiators)

Referenz-Namensschema (für FinanceReservation.referenz):
    'tv2:bid:<listing_id>'      — führendes Gebot eines Vereins auf ein Listing
    'tv2:deal:<deal_id>'        — offene gesendete Deal-/Leihanfrage
"""
from decimal import Decimal

from django.db.models import Sum

from game.economy import reservations

ZERO = Decimal('0.00')
ZWECK = 'transfer_v2'


def bid_ref(listing_id, club_id):
    """Reservierungs-Referenz eines Vereins-Gebots auf ein Listing.

    Je (Listing, Verein) eindeutig — ein Verein kann auf viele Listings
    gleichzeitig bieten, aber je Listing hält es höchstens EIN führendes
    Gebot (nur dessen Reservierung ist aktiv).
    """
    return f'tv2:bid:{listing_id}:{club_id}'


def deal_ref(deal_id):
    return f'tv2:deal:{deal_id}'


def available(club, *, exclude_referenz=None):
    """Verfügbar = Kontostand − ALLE aktiven Reservierungen.

    Harte Deckungsgrundlage: zählt jede aktive FinanceReservation des
    Vereins (auch fremde Subsysteme wie Show-Auktion), nicht nur den
    v2-Cache — sonst würde ein v2-Gebot Deckung sehen, die book_many
    beim Settlement wieder abzieht.

    exclude_referenz: eigene Reservierung, die für DIESE Prüfung nicht
    doppelt zählen darf (Selbst-Überbieten, eigener Deal-Vollzug).
    """
    budget = club.budget if club.budget is not None else ZERO
    reserviert = reservations.reserved_money(
        club, exclude_referenz=exclude_referenz)
    return Decimal(str(budget)) - Decimal(str(reserviert))


def reserved_for(referenz):
    """Betrag der aktiven Reservierung unter dieser Referenz (0, wenn keine).

    Für Deckungsprüfungen, bei denen die EIGENE bestehende Reservierung
    nicht doppelt zählen darf (z. B. Selbst-Überbieten des Führenden).
    """
    from game.models import FinanceReservation
    betrag = (
        FinanceReservation.objects
        .filter(referenz=referenz, status=FinanceReservation.STATUS_ACTIVE)
        .values_list('betrag', flat=True).first()
    )
    return Decimal(str(betrag)) if betrag is not None else ZERO


def _v2_reserved_total(club):
    """Summe der aktiven v2-Reservierungen (die Wahrheit hinter dem Cache)."""
    from game.models import FinanceReservation
    total = (
        FinanceReservation.objects
        .filter(club=club, status=FinanceReservation.STATUS_ACTIVE, zweck=ZWECK)
        .aggregate(s=Sum('betrag'))['s']
    ) or ZERO
    return Decimal(str(total))


def _sync_reserved_cache(club):
    """Schreibt Club.reserved aus den aktiven v2-FinanceReservation-Zeilen.

    Muss innerhalb derselben Transaktion wie die Reservierungsänderung
    laufen (Aufrufer hält den Club-Lock). Identische Aggregation wie
    recalc_reserved — der Cache spiegelt NUR zweck='transfer_v2'; andere
    Reservierungszwecke deckt die Buchungsschicht selbst ab.
    """
    total = _v2_reserved_total(club)
    if club.reserved != total:
        club.reserved = total
        club.save(update_fields=['reserved'])
    return total


def reserve_money(club, referenz, betrag):
    """Legt/aktualisiert eine Geld-Reservierung an und führt den Cache nach."""
    betrag = Decimal(str(betrag))
    reservations.reserve(club, referenz=referenz, zweck=ZWECK, betrag=betrag)
    return _sync_reserved_cache(club)


def release_money(club, referenz):
    """Gibt eine Reservierung frei und führt den Cache nach."""
    reservations.release(referenz)
    return _sync_reserved_cache(club)


def consume_money(club, referenz):
    """Markiert eine Reservierung als verbraucht (Zuschlag) + Cache nachführen."""
    reservations.consume(referenz)
    return _sync_reserved_cache(club)


def recalc_reserved(club):
    """Idempotente Reparatur: berechnet Club.reserved aus der Wahrheit neu.

    Wahrheit sind die aktiven FinanceReservation-Zeilen des Vereins mit
    zweck='transfer_v2'. Gibt (alter_wert, neuer_wert) zurück.
    """
    alt = Decimal(str(club.reserved or ZERO))
    neu = _v2_reserved_total(club)
    if alt != neu:
        club.reserved = neu
        club.save(update_fields=['reserved'])
    return alt, neu
