"""Hintergrund-Jobs des Transfersystems v2 (Master-Spec §4.5).

Alle Jobs sind idempotent und einzeln aufrufbar; das Management-Command
run_transfer_v2_jobs bündelt sie für den Celery-Beat-Zeitplan.

    close_due_listings()        — fällige Auktionen abschließen (minütlich)
    expire_due_deals()          — abgelaufene Deal-Anfragen schließen (stündlich)
    end_due_loans()             — Leih-Enden am WP-/SE-Stichtag (täglich)
    execute_due_pendings()      — fällige WP-/SE-Transfers vollziehen (täglich)
    cleanup_expired_locks()     — abgelaufene Wechselsperren aufräumen (täglich)
    update_position_barometer() — Angebot/Nachfrage je Position (täglich)
"""
import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)


def close_due_listings(*, saison=None, now=None):
    """Schließt alle fälligen aktiven Auktionen (idempotent)."""
    from .models import TransferListing
    from .services import close_listing, TransferActionError

    now = now or timezone.now()
    due = TransferListing.objects.filter(
        status=TransferListing.STATUS_ACTIVE, ends_at__lte=now,
    ).values_list('pk', flat=True)
    done, fehler = 0, 0
    for pk in list(due):
        try:
            close_listing(TransferListing.objects.get(pk=pk), saison=saison)
            done += 1
        except TransferActionError as exc:
            # Fachlicher Konflikt (z. B. Deckung weggefallen) — loggen,
            # nächster Lauf versucht es erneut; Job bricht NIE ab.
            logger.warning('Listing %s nicht abschließbar: %s', pk, exc)
            fehler += 1
        except Exception:
            logger.exception('Fehler beim Abschluss von Listing %s', pk)
            fehler += 1
    return {'abgeschlossen': done, 'fehler': fehler}


def expire_due_deals(*, now=None):
    """Setzt abgelaufene offene Deal-Anfragen auf EXPIRED (Reservierung frei)."""
    from .models import DealRequest
    from .services import expire_deal

    now = now or timezone.now()
    due = DealRequest.objects.filter(
        status=DealRequest.STATUS_OPEN, expires_at__lte=now,
    ).values_list('pk', flat=True)
    done = 0
    for pk in list(due):
        expire_deal(DealRequest.objects.get(pk=pk))
        done += 1
    return {'abgelaufen': done}


def end_due_loans(*, saison=None, today=None):
    """Beendet Leihen, deren WP-/SE-Stichtag erreicht ist (Spieler kehrt zurück).

    Rückruf ist EINVERNEHMLICH (Spec §5.3) und endet sofort über
    services.respond_recall — hier zählt nur der Stichtag.
    """
    from .calendar_dates import next_execution_date
    from .models import Loan
    from .services import end_loan

    today = today or timezone.localdate()
    done = 0
    for loan in Loan.objects.filter(ended_at__isnull=True):
        stichtag = next_execution_date(loan.until)
        if stichtag > today:
            continue
        end_loan(loan)
        done += 1
    return {'beendet': done}


def expire_paused_loan_requests(*, saison=None):
    """Lässt offene Leihanfragen auslaufen, deren Markt pausiert ist.

    Master-Spec §5.4 / Abnahme 23: Ab der Leih-Deadline sind Abschlüsse
    gesperrt und OFFENE Anfragen laufen aus (Reservierung der Gebühr wird
    über expire_deal freigegeben). Rückrufe/Optionszüge bleiben unberührt.
    """
    from .calendar_dates import loan_market_paused
    from .models import DealRequest
    from .services import expire_deal

    done = 0
    qs = DealRequest.objects.filter(
        status=DealRequest.STATUS_OPEN, typ=DealRequest.TYP_LOAN,
    ).values_list('pk', 'loan_until')
    for pk, until in list(qs):
        if loan_market_paused(until or 'WP', saison):
            expire_deal(DealRequest.objects.get(pk=pk))
            done += 1
    return {'abgelaufen': done}


def execute_due_pendings(*, saison=None, today=None):
    """Vollzieht fällige WP-/SE-PendingTransfers."""
    from .execution import execute_pending
    from .models import PendingTransfer

    today = today or timezone.localdate()
    due = PendingTransfer.objects.filter(
        status=PendingTransfer.STATUS_PENDING, execute_at__lte=today,
    )
    done = 0
    for p in list(due):
        execute_pending(p, saison=saison)
        done += 1
    return {'vollzogen': done}


def cleanup_expired_locks(*, today=None):
    """Löscht abgelaufene TransferLock-Zeilen (Feld-Ablauf regelt is_transfer_locked)."""
    from .models import TransferLock

    today = today or timezone.localdate()
    deleted, _ = TransferLock.objects.filter(locked_until__lt=today).delete()
    return {'geloescht': deleted}


def update_position_barometer():
    """Aktualisiert Angebot/Nachfrage je Position (Master-Spec §5.5).

    Angebot = aktive Listings + aktive Leih-Listings je Position.
    Nachfrage = offene Deal-Anfragen, deren gewünschte (TO-)Spieler die
    Position spielen. Gewicht = geglättetes Verhältnis (0.8–1.2 geklemmt).
    """
    from .models import (DealRequest, DealRequestPlayer, LoanListing,
                         PositionBarometer, TransferListing)

    supply = {}
    for pos in (TransferListing.objects
                .filter(status=TransferListing.STATUS_ACTIVE)
                .values_list('player__position', flat=True)):
        supply[pos or '?'] = supply.get(pos or '?', 0) + 1
    for pos in (LoanListing.objects
                .filter(status=LoanListing.STATUS_ACTIVE)
                .values_list('player__position', flat=True)):
        supply[pos or '?'] = supply.get(pos or '?', 0) + 1

    demand = {}
    for pos in (DealRequestPlayer.objects
                .filter(request__status=DealRequest.STATUS_OPEN,
                        side=DealRequestPlayer.SIDE_TO)
                .values_list('player__position', flat=True)):
        demand[pos or '?'] = demand.get(pos or '?', 0) + 1

    updated = 0
    for pos in sorted(set(supply) | set(demand)):
        s, d = supply.get(pos, 0), demand.get(pos, 0)
        if s == 0 and d == 0:
            weight = Decimal('1.000')
        else:
            ratio = Decimal(d + 1) / Decimal(s + 1)
            weight = max(Decimal('0.800'), min(Decimal('1.200'), ratio))
        PositionBarometer.objects.update_or_create(
            position=pos, defaults={
                'supply': s, 'demand': d,
                'weight': weight.quantize(Decimal('0.001')),
            },
        )
        updated += 1
    return {'positionen': updated}


def respond_ai_deals(*, saison=None):
    """KI-Vereine beantworten offene Deal-Anfragen auf Basis der Schmerzgrenze."""
    from .ai_deals import respond_open_deals
    return respond_open_deals(saison=saison)


def run_all(*, saison=None):
    """Führt alle Jobs einmal aus (für das Management-Command)."""
    return {
        'listings': close_due_listings(saison=saison),
        'deals': expire_due_deals(),
        'loan_anfragen': expire_paused_loan_requests(saison=saison),
        'loans': end_due_loans(saison=saison),
        'pendings': execute_due_pendings(saison=saison),
        'locks': cleanup_expired_locks(),
        'barometer': update_position_barometer(),
        'ki_deals': respond_ai_deals(saison=saison),
    }
