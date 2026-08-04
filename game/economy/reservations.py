"""Generische Geld- und Kaderplatz-Reservierungen (Escrow-Fundament).

Reservierungen sind KEINE Buchungen: Sie verändern weder Ledger noch
Konto-Cache, sondern reduzieren die "verfügbare" Sicht in allen
Deckungs- und Limit-Prüfungen:

- booking._create_booking: aktive Ausgaben (pflicht=False) scheitern,
  wenn Kontostand − aktive Reservierungen den Betrag nicht deckt.
- transfers._check_kaderplatz: reservierte Plätze belegen das Kaderlimit.
- scouting.service.available_budget: zieht Reservierungen ebenfalls ab.

Lebenszyklus einer Reservierung (Spec Show-Auktion §8.2):
    reserve(club, referenz='showauction:bid:42', zweck='showauction',
            betrag=Decimal('1000000'), slots=1)
    adjust(referenz, betrag=...)   # z. B. verdeckte Gebotsänderung
    release(referenz)              # Überbietung / Auktionsende / Platzen
    consume(referenz)              # Zuschlag: Reservierung geht in Buchung über

Nebenläufigkeit: Die Funktionen sperren selbst NICHT — der Aufrufer hält
bereits die maßgebliche Zeile (Auktions- bzw. Club-Lock). Referenzen sind
über einen partiellen UniqueConstraint (status='active') doppelt-sicher.
"""
from decimal import Decimal

from django.db.models import Sum

from game.models import FinanceReservation

ZERO = Decimal('0.00')


def _active():
    return FinanceReservation.objects.filter(
        status=FinanceReservation.STATUS_ACTIVE,
    )


def reserved_money(club, exclude_referenz=None):
    """Summe aktiver Geld-Reservierungen eines Vereins."""
    qs = _active().filter(club=club)
    if exclude_referenz:
        qs = qs.exclude(referenz=exclude_referenz)
    return qs.aggregate(s=Sum('betrag'))['s'] or ZERO


def reserved_slots(club, exclude_referenz=None):
    """Summe aktiver Kaderplatz-Reservierungen eines Vereins."""
    qs = _active().filter(club=club)
    if exclude_referenz:
        qs = qs.exclude(referenz=exclude_referenz)
    return qs.aggregate(s=Sum('slots'))['s'] or 0


def reserve(club, *, referenz, zweck, betrag=ZERO, slots=0):
    """Legt eine aktive Reservierung an (oder aktualisiert die bestehende).

    Idempotent pro Referenz: Existiert bereits eine aktive Reservierung
    mit derselben Referenz, werden Betrag/Slots aktualisiert.
    """
    betrag = Decimal(betrag)
    if betrag < 0:
        raise ValueError('Reservierungsbetrag darf nicht negativ sein.')
    obj = _active().filter(referenz=referenz).first()
    if obj is not None:
        obj.betrag = betrag
        obj.slots = slots
        obj.zweck = zweck
        obj.save(update_fields=['betrag', 'slots', 'zweck', 'updated_at'])
        return obj
    return FinanceReservation.objects.create(
        club=club,
        zweck=zweck,
        referenz=referenz,
        betrag=betrag,
        slots=slots,
    )


def adjust(referenz, *, betrag=None, slots=None):
    """Passt Betrag/Slots einer aktiven Reservierung an (None = unverändert)."""
    obj = _active().filter(referenz=referenz).first()
    if obj is None:
        return None
    fields = []
    if betrag is not None:
        betrag = Decimal(betrag)
        if betrag < 0:
            raise ValueError('Reservierungsbetrag darf nicht negativ sein.')
        obj.betrag = betrag
        fields.append('betrag')
    if slots is not None:
        obj.slots = slots
        fields.append('slots')
    if fields:
        obj.save(update_fields=fields + ['updated_at'])
    return obj


def _finish(referenz, new_status):
    updated = _active().filter(referenz=referenz).update(status=new_status)
    return updated > 0


def release(referenz):
    """Gibt eine aktive Reservierung frei (Überbietung/Ende/Platzen)."""
    return _finish(referenz, FinanceReservation.STATUS_RELEASED)


def consume(referenz):
    """Markiert eine Reservierung als verbraucht (Zuschlag → Buchung)."""
    return _finish(referenz, FinanceReservation.STATUS_CONSUMED)
