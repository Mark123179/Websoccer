"""Concurrency-Tests Transfersystem v2 — Kadergrenzen unter echten Races.

Zwei parallele Settlements desselben Vereins müssen über die Club-
Zeilensperre serialisiert werden: nur EIN Vollzug darf den letzten
Kaderplatz vergeben bzw. den Mindestkader-Puffer verbrauchen; der zweite
endet deterministisch im Konflikt-Pfad (EXPIRED bzw. Storno mit voller
Rückerstattung). Läuft mit echten Threads gegen Postgres-Zeilensperren.
"""
import threading
from datetime import timedelta
from decimal import Decimal

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from game.models import (
    Club, EconomyParameter, GameSeasonState, League, Player,
)
from game.transfer_v2 import services
from game.transfer_v2.execution import execute_pending
from game.transfer_v2.models import PendingTransfer, TransferListing


def _mk_club(name, budget='50000000.00'):
    league, _ = League.objects.get_or_create(
        name='TV2-Conc-Liga', country='Deutschland')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


def _mk_player(club, name, age=25):
    first, last = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=first, last_name=last, age=age,
        position='Sturm', main_position_1='ST',
        nationalities='Deutschland', market_value=Decimal('5000000'),
    )


def _run_parallel(fns):
    """Startet alle fns gleichzeitig (Barrier) und sammelt Exceptions."""
    errors = []
    barrier = threading.Barrier(len(fns), timeout=15)

    def _wrap(fn):
        def inner():
            try:
                barrier.wait()
                fn()
            except Exception as exc:  # noqa: BLE001 — für Assertion sammeln
                errors.append(exc)
            finally:
                connections.close_all()
        return inner

    threads = [threading.Thread(target=_wrap(fn)) for fn in fns]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return errors


class TransferConcurrencyTests(TransactionTestCase):
    # Flush zerstört migrationsgeseedete Daten (EconomyParameter etc.).
    # serialized_rollback erzeugt beim Testlauf-Start einen Snapshot; das
    # überschriebene _fixture_teardown spielt ihn nach JEDEM Test zurück —
    # sonst bliebe die --keepdb-Datenbank nach dem letzten Test geleert und
    # alle folgenden keepdb-Läufe (test-Workflow) würden brechen.
    serialized_rollback = True

    def _fixture_teardown(self):
        super()._fixture_teardown()
        conn = connections['default']
        serialized = getattr(conn, '_test_serialized_contents', None)
        if serialized:
            conn.creation.deserialize_db_from_string(serialized)

    def setUp(self):
        GameSeasonState.objects.get_or_create(current_season=0)
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 1})
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS', defaults={'value': 60})

    def test_parallel_sales_cannot_break_seller_minimum(self):
        # Verkäufer hat 2 Spieler, Mindestkader 1 → nur EIN Verkauf darf
        # durchgehen; der zweite Abschluss muss im Konflikt-Pfad enden
        # (EXPIRED + Escrow-Freigabe), egal welcher Thread zuerst committet.
        seller = _mk_club('FC Conc Verkauf')
        buyer_a = _mk_club('FC Conc Kauf A')
        buyer_b = _mk_club('FC Conc Kauf B')
        p1 = _mk_player(seller, 'Conc Eins')
        p2 = _mk_player(seller, 'Conc Zwei')

        l1 = services.create_listing(
            p1, seller, min_bid=Decimal('1000000'), duration_days=3)
        l2 = services.create_listing(
            p2, seller, min_bid=Decimal('1000000'), duration_days=3)
        services.place_bid(l1, buyer_a, Decimal('1000000'))
        services.place_bid(l2, buyer_b, Decimal('1000000'))
        TransferListing.objects.filter(pk__in=[l1.pk, l2.pk]).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        l1.refresh_from_db()
        l2.refresh_from_db()

        errors = _run_parallel([
            lambda: services.close_listing(l1),
            lambda: services.close_listing(l2),
        ])
        self.assertEqual(errors, [])

        l1.refresh_from_db()
        l2.refresh_from_db()
        seller.refresh_from_db()
        buyer_a.refresh_from_db()
        buyer_b.refresh_from_db()
        statuses = sorted([l1.status, l2.status])
        self.assertEqual(statuses, [TransferListing.STATUS_EXPIRED,
                                    TransferListing.STATUS_SOLD])
        # Mindestkader hält: genau ein Spieler hat den Verein verlassen.
        self.assertEqual(Player.objects.filter(club=seller).count(), 1)
        # Kein hängendes Escrow, Verkäufer genau einmal bezahlt.
        self.assertEqual(buyer_a.reserved, Decimal('0.00'))
        self.assertEqual(buyer_b.reserved, Decimal('0.00'))
        self.assertEqual(seller.budget, Decimal('51000000.00'))
        self.assertEqual(
            buyer_a.budget + buyer_b.budget, Decimal('99000000.00'))

    def test_parallel_pendings_cannot_exceed_receiver_limit(self):
        # Zwei fällige WP-Pendings zum selben Käufer, aber nur EIN freier
        # Kaderplatz → genau einer wird vollzogen, der andere storniert
        # (voller Refund), nie beide.
        seller_a = _mk_club('FC Conc Pend A')
        seller_b = _mk_club('FC Conc Pend B')
        buyer = _mk_club('FC Conc Ziel')
        # Verkäufer-Puffer, damit der Mindestkader nicht limitiert.
        _mk_player(seller_a, 'Puffer Eins')
        _mk_player(seller_b, 'Puffer Zwei')
        pa = _mk_player(seller_a, 'Pend Eins')
        pb = _mk_player(seller_b, 'Pend Zwei')
        _mk_player(buyer, 'Bestand Kader')

        la = services.create_listing(
            pa, seller_a, min_bid=Decimal('1000000'),
            buy_now=Decimal('10000000'), timing='WP', duration_days=3)
        lb = services.create_listing(
            pb, seller_b, min_bid=Decimal('1000000'),
            buy_now=Decimal('10000000'), timing='WP', duration_days=3)
        services.buy_now(la, buyer)
        services.buy_now(lb, buyer)
        # Käufer: 1 Bestandsspieler, Limit 2 → nur ein Zugang passt.
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS', defaults={'value': 2})
        PendingTransfer.objects.filter(
            status=PendingTransfer.STATUS_PENDING).update(
            execute_at=timezone.localdate())
        pend_a = PendingTransfer.objects.get(player=pa)
        pend_b = PendingTransfer.objects.get(player=pb)

        errors = _run_parallel([
            lambda: execute_pending(pend_a),
            lambda: execute_pending(pend_b),
        ])
        self.assertEqual(errors, [])

        pend_a.refresh_from_db()
        pend_b.refresh_from_db()
        buyer.refresh_from_db()
        seller_a.refresh_from_db()
        seller_b.refresh_from_db()
        statuses = sorted([pend_a.status, pend_b.status])
        self.assertEqual(statuses, [PendingTransfer.STATUS_CANCELLED_LIMIT,
                                    PendingTransfer.STATUS_EXECUTED])
        # Kaderlimit hält: genau ein Zugang.
        self.assertEqual(Player.objects.filter(club=buyer).count(), 2)
        # Geld: einer bezahlt (−10M), einer voll erstattet.
        self.assertEqual(buyer.budget, Decimal('40000000.00'))
        self.assertEqual(
            sorted([seller_a.budget, seller_b.budget]),
            [Decimal('50000000.00'), Decimal('60000000.00')])
