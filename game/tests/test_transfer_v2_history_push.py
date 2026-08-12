"""Tests Transfersystem v2 — Historie, Push-Katalog, Ticker & Gerüchte (Task #823).

Deckt ab: Historie-Rendering/Filter/Pagination/Meldung, Push-Auslöser
(Beobachtungsliste, Pins, Gebote, Deals, Rückrufe, Meldungen), Gerüchte-Engine
(Wahrscheinlichkeit, 1-pro-Tag, Summenmodus, Outlet, Vereinsnews) und die
Ticker-Integration vollzogener Transfers.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from game.models import (
    Club, ClubNewsItem, EconomyParameter, GameSeasonState, League,
    MediaOutlet, Notification, Player, WatchlistEntry,
)
from game.transfer_v2 import events, services
from game.transfer_v2.models import (
    DealRequest, ListingPin, Loan, RumorNews, TransferListing, TransferRecord,
    TransferRecordPlayer, TransferReport,
)


def _mk_club(name, budget='80000000.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(
            name='TV2-Hist-Testliga', country='Deutschland')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


def _mk_player(club, name='Hans Historie', age=25, mw='5000000'):
    first, last = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=first, last_name=last, age=age,
        position='Sturm', main_position_1='ST',
        nationalities='Deutschland', market_value=Decimal(mw),
    )


class _FixedRandom:
    """Deterministischer Ersatz für random.Random in der Gerüchte-Engine."""

    def __init__(self, rolls, choice_index=0):
        self.rolls = list(rolls)
        self.choice_index = choice_index

    def random(self):
        return self.rolls.pop(0) if self.rolls else 0.99

    def choice(self, seq):
        return seq[self.choice_index % len(seq)]


class Base(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 0})
        self.seller = _mk_club('FC Abgabe')
        self.buyer = _mk_club('FC Aufnahme')
        self.player = _mk_player(self.seller)
        self.user = User.objects.create_user('histmgr', password='x')
        self.buyer.managed_by = self.user.manager_profile
        self.buyer.save(update_fields=['managed_by'])
        self.user2 = User.objects.create_user('histmgr2', password='x')
        self.seller.managed_by = self.user2.manager_profile
        self.seller.save(update_fields=['managed_by'])
        MediaOutlet.objects.get_or_create(
            name='Testkicker', slug='testkicker')

    def login(self):
        self.client.force_login(self.user)

    def _record(self, kind=TransferRecord.KIND_CASH, cash_b='5000000',
                cancelled=False, **kw):
        rec = TransferRecord.objects.create(
            kind=kind, club_a=self.seller, club_b=self.buyer,
            cash_b=Decimal(cash_b), is_cancelled=cancelled, **kw)
        TransferRecordPlayer.objects.create(
            record=rec, player=self.player, side=TransferRecordPlayer.SIDE_A,
            market_value_at_transfer=self.player.market_value)
        return rec

    def _record_side_b(self, cash_a='7000000'):
        """Angenommenes Kaufangebot: Initiator (club_a=buyer) kauft einen
        Spieler des Empfängers → Spieler steht auf SIDE_B und wechselt
        club_b → club_a. Der Spieler gehört dem seller (club_b)."""
        rec = TransferRecord.objects.create(
            kind=TransferRecord.KIND_CASH, club_a=self.buyer,
            club_b=self.seller, cash_a=Decimal(cash_a))
        TransferRecordPlayer.objects.create(
            record=rec, player=self.player, side=TransferRecordPlayer.SIDE_B,
            market_value_at_transfer=self.player.market_value)
        return rec


# ══════════════════════════════════════════════════════════════════════════
#  Historie
# ══════════════════════════════════════════════════════════════════════════

class HistoryViewTests(Base):
    def test_requires_login(self):
        r = self.client.get(reverse('transfer_history'))
        self.assertEqual(r.status_code, 302)

    def test_renders_cash_record(self):
        self._record()
        self.login()
        r = self.client.get(reverse('transfer_history'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Hans Historie')
        self.assertContains(r, 'FC Abgabe')
        self.assertContains(r, 'FC Aufnahme')
        self.assertContains(r, '5.000.000')

    def test_side_b_record_renders_reversed_direction(self):
        # Kaufangebot des Initiators (buyer=club_a) für einen Spieler des
        # Empfängers: Spieler wechselt club_b → club_a. Die Historie muss
        # FC Abgabe → FC Aufnahme zeigen, NICHT club_a → club_b.
        self._record_side_b()
        self.login()
        r = self.client.get(reverse('transfer_history'))
        self.assertEqual(r.status_code, 200)
        row = r.context['rows'][0]
        self.assertEqual(row['from_name'], 'FC Abgabe')
        self.assertEqual(row['to_name'], 'FC Aufnahme')
        self.assertIn('7.000.000', row['fee_fmt'])
        # Detail-Panels: der abgebende Verein (links) gibt den Spieler —
        # die B-Seite muss links landen, die leere A-Seite rechts.
        self.assertEqual(row['left_label'], 'FC Abgabe gibt')
        self.assertEqual(row['right_label'], 'FC Aufnahme gibt')
        self.assertEqual([p['name'] for p in row['left_rows']],
                         ['Hans Historie'])
        self.assertEqual(row['right_rows'], [])

    def test_side_a_record_keeps_panel_order(self):
        # Normale SIDE_A-Richtung: A-Spieler bleiben im linken Panel.
        self._record()
        self.login()
        r = self.client.get(reverse('transfer_history'))
        row = r.context['rows'][0]
        self.assertEqual(row['left_label'], 'FC Abgabe gibt')
        self.assertEqual([p['name'] for p in row['left_rows']],
                         ['Hans Historie'])
        self.assertEqual(row['right_rows'], [])

    def test_admin_record_shows_admin_fee(self):
        self._record(kind=TransferRecord.KIND_ADMIN, is_admin=True)
        self.login()
        r = self.client.get(reverse('transfer_history'))
        self.assertContains(r, '— (Admin)')

    def test_swap_summary_format(self):
        rec = self._record(kind=TransferRecord.KIND_SWAP, cash_b='0')
        p2 = _mk_player(self.buyer, name='Tausch Partner')
        TransferRecordPlayer.objects.create(
            record=rec, player=p2, side=TransferRecordPlayer.SIDE_B,
            market_value_at_transfer=p2.market_value)
        self.login()
        r = self.client.get(reverse('transfer_history'))
        self.assertContains(r, '1 ⇄ 1 Spieler')
        self.assertContains(r, 'Tauschgeschäft')

    def test_loan_filter_segment(self):
        self._record()  # CASH
        self._record(kind=TransferRecord.KIND_LOAN,
                     loan_event=TransferRecord.LOAN_EVENT_START,
                     loan_until='WP')
        self.login()
        r = self.client.get(reverse('transfer_history') + '?seg=leihen')
        self.assertContains(r, 'Leihstart')
        r2 = self.client.get(reverse('transfer_history') + '?seg=transfers')
        self.assertNotContains(r2, 'Leihstart')

    def test_only_mine_filter(self):
        other_a = _mk_club('FC Fremd A')
        other_b = _mk_club('FC Fremd B')
        rec = TransferRecord.objects.create(
            kind=TransferRecord.KIND_CASH, club_a=other_a, club_b=other_b,
            cash_b=Decimal('1000000'))
        px = _mk_player(other_a, name='Fremd Spieler')
        TransferRecordPlayer.objects.create(
            record=rec, player=px, side=TransferRecordPlayer.SIDE_A)
        self._record()
        self.login()
        r = self.client.get(reverse('transfer_history') + '?mine=1')
        self.assertContains(r, 'Hans Historie')
        self.assertNotContains(r, 'Fremd Spieler')

    def test_pagination_six_per_page(self):
        for i in range(8):
            self._record()
        self.login()
        r = self.client.get(reverse('transfer_history'))
        self.assertEqual(len(r.context['rows']), 6)
        r2 = self.client.get(reverse('transfer_history') + '?seg=transfers&page=2')
        self.assertEqual(len(r2.context['rows']), 2)

    def test_cancelled_record_marked(self):
        self._record(cancelled=True)
        self.login()
        r = self.client.get(reverse('transfer_history'))
        self.assertContains(r, 'Admin-storniert')


class ReportTests(Base):
    def test_report_requires_reason(self):
        rec = self._record()
        self.login()
        self.client.post(reverse('transfer_report_create'),
                         {'record_id': rec.pk, 'reason': '  '})
        self.assertEqual(TransferReport.objects.count(), 0)

    def test_report_created_and_confirmed(self):
        rec = self._record()
        self.login()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('transfer_report_create'),
                {'record_id': rec.pk, 'reason': 'Verdächtig günstig.'})
        rep = TransferReport.objects.get()
        self.assertEqual(rep.reporter_club, self.buyer)
        self.assertEqual(rep.status, TransferReport.STATUS_OPEN)
        # Push: Eingangsbestätigung an den Melder.
        self.assertTrue(Notification.objects.filter(
            recipient=self.user.manager_profile,
            title='Meldung eingegangen').exists())

    def test_report_routed_to_actionable_oversight_staff(self):
        # Aufsicht = Staff-Manager MIT Bearbeitungsrecht: nur sie bekommen
        # die Meldung — und können den Link auch wirklich öffnen.
        from django.contrib.auth.models import Permission
        staff = User.objects.create_user('aufsicht', password='x',
                                         is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(codename='view_transferreport'),
            Permission.objects.get(codename='change_transferreport'))
        # Staff OHNE Recht: bekommt keinen Link, den er nicht öffnen kann.
        bare = User.objects.create_user('nurstaff', password='x',
                                        is_staff=True)
        rec = self._record()
        self.login()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('transfer_report_create'),
                {'record_id': rec.pk, 'reason': 'Verdächtig günstig.'})
        rep = TransferReport.objects.get()
        n = Notification.objects.filter(
            recipient=staff.manager_profile,
            title='Neue Transfer-Meldung (Aufsicht)').first()
        self.assertIsNotNone(n)
        self.assertIn('Verdächtig günstig', n.body)
        self.assertIn(f'/admin/game/transferreport/{rep.pk}/change/', n.url)
        self.assertFalse(Notification.objects.filter(
            recipient=bare.manager_profile,
            title='Neue Transfer-Meldung (Aufsicht)').exists())
        # End-to-end: der Empfänger kann die Admin-Seite tatsächlich öffnen.
        self.client.logout()
        self.client.force_login(staff)
        r = self.client.get(n.url)
        self.assertEqual(r.status_code, 200)

    def test_report_resolution_pushes_reporter(self):
        # Admin-Workflow: Statuswechsel weg von OPEN setzt resolved_at und
        # informiert den Melder über das Ergebnis.
        from django.contrib.admin.sites import AdminSite
        from game.admin import TransferReportAdmin
        rec = self._record()
        rep = TransferReport.objects.create(
            record=rec, reporter_club=self.buyer, reason='Testmeldung.')
        ma = TransferReportAdmin(TransferReport, AdminSite())
        with self.captureOnCommitCallbacks(execute=True):
            changed = ma._resolve(None, rep, TransferReport.STATUS_DISMISSED)
        self.assertTrue(changed)
        rep.refresh_from_db()
        self.assertEqual(rep.status, TransferReport.STATUS_DISMISSED)
        self.assertIsNotNone(rep.resolved_at)
        n = Notification.objects.filter(
            recipient=self.user.manager_profile,
            title='Meldung bearbeitet').first()
        self.assertIsNotNone(n)
        self.assertIn('Abgewiesen', n.body)
        # Idempotent: gleicher Status erneut = kein zweiter Push.
        with self.captureOnCommitCallbacks(execute=True):
            unchanged = ma._resolve(None, rep, TransferReport.STATUS_DISMISSED)
        self.assertFalse(unchanged)
        self.assertEqual(Notification.objects.filter(
            recipient=self.user.manager_profile,
            title='Meldung bearbeitet').count(), 1)


# ══════════════════════════════════════════════════════════════════════════
#  Gerüchte-Engine
# ══════════════════════════════════════════════════════════════════════════

class RumorEngineTests(Base):
    def test_no_rumor_when_roll_fails(self):
        rng = _FixedRandom([0.99])  # > 0.60 (TRANSFER_DONE)
        r = events.emit_event(
            events.EVENT_TRANSFER_DONE, player=self.player,
            club_a=self.seller, club_b=self.buyer,
            affected_club=self.seller, betrag=Decimal('5000000'), rng=rng)
        self.assertIsNone(r)
        self.assertEqual(RumorNews.objects.count(), 0)

    def test_rumor_created_exact_sum(self):
        rng = _FixedRandom([0.01, 0.01])  # News ja, exakt ja
        r = events.emit_event(
            events.EVENT_TRANSFER_DONE, player=self.player,
            club_a=self.seller, club_b=self.buyer,
            affected_club=self.seller, betrag=Decimal('5000000'), rng=rng)
        self.assertIsNotNone(r)
        self.assertEqual(r.sum_mode, RumorNews.SUM_EXACT)
        self.assertIn('5.000.000', r.headline)
        self.assertEqual(r.outlet, 'Testkicker')
        self.assertEqual(r.affected_club, self.seller)

    def test_rumor_range_sum(self):
        rng = _FixedRandom([0.01, 0.99])  # News ja, exakt nein → Spanne
        r = events.emit_event(
            events.EVENT_TRANSFER_DONE, player=self.player,
            club_a=self.seller, club_b=self.buyer,
            affected_club=self.seller, betrag=Decimal('10000000'), rng=rng)
        self.assertEqual(r.sum_mode, RumorNews.SUM_RANGE)
        self.assertIn('Mio €', r.headline)
        self.assertIn('8', r.headline)   # 10 M − 20 %
        self.assertIn('12', r.headline)  # 10 M + 20 %

    def test_player_rumor_day_is_autofilled_and_db_required(self):
        # ORM-Erzeugung ohne Dedup-Tag: save() füllt ihn automatisch.
        r = RumorNews.objects.create(
            event_type=RumorNews.EVENT_TRANSFER_DONE, player=self.player,
            affected_club=self.seller, outlet='Testkicker',
            headline='Autofill-Test.', published_at=timezone.now())
        self.assertIsNotNone(r.published_day)
        # Umgehung von save() (bulk_create): CheckConstraint auf DB-Ebene
        # verweigert Spieler-Gerüchte ohne Dedup-Tag.
        from django.db import IntegrityError, transaction as _tx
        with self.assertRaises(IntegrityError), _tx.atomic():
            RumorNews.objects.bulk_create([RumorNews(
                event_type=RumorNews.EVENT_LISTING_CREATED,
                player=self.player, affected_club=self.seller,
                outlet='Testkicker', headline='Bypass-Versuch.',
                published_at=timezone.now(), published_day=None)])
        # Ohne Spieler bleibt NULL erlaubt (Admin-/Systemnews).
        r2 = RumorNews.objects.create(
            event_type=RumorNews.EVENT_TRANSFER_DONE, player=None,
            affected_club=self.seller, outlet='Testkicker',
            headline='Ohne Spieler.', published_at=timezone.now())
        self.assertIsNone(r2.published_day)

    def test_daily_dedup_is_db_enforced(self):
        # Parallel-Szenario: Beide Aufrufe passieren die exists()-Vorprüfung
        # (hier simuliert durch deren Umgehung) — der UniqueConstraint auf
        # (player, event_type, published_day) lässt trotzdem nur EIN
        # Gerücht zu; der zweite Aufruf endet sauber mit None.
        from unittest.mock import patch
        rng1 = _FixedRandom([0.01, 0.01])
        rng2 = _FixedRandom([0.01, 0.01])
        with patch.object(events, '_already_today', return_value=False):
            r1 = events.emit_event(
                events.EVENT_TRANSFER_DONE, player=self.player,
                club_a=self.seller, club_b=self.buyer,
                affected_club=self.seller, betrag=Decimal('5000000'),
                rng=rng1)
            r2 = events.emit_event(
                events.EVENT_TRANSFER_DONE, player=self.player,
                club_a=self.seller, club_b=self.buyer,
                affected_club=self.seller, betrag=Decimal('5000000'),
                rng=rng2)
        self.assertIsNotNone(r1)
        self.assertIsNone(r2)
        self.assertEqual(RumorNews.objects.filter(
            player=self.player,
            event_type=RumorNews.EVENT_TRANSFER_DONE).count(), 1)

    def test_max_one_rumor_per_operation_per_day(self):
        rng1 = _FixedRandom([0.01, 0.01])
        r1 = events.emit_event(
            events.EVENT_TRANSFER_DONE, player=self.player,
            club_a=self.seller, club_b=self.buyer,
            affected_club=self.seller, betrag=Decimal('5000000'), rng=rng1)
        self.assertIsNotNone(r1)
        rng2 = _FixedRandom([0.01, 0.01])
        r2 = events.emit_event(
            events.EVENT_TRANSFER_DONE, player=self.player,
            club_a=self.seller, club_b=self.buyer,
            affected_club=self.seller, betrag=Decimal('5000000'), rng=rng2)
        self.assertIsNone(r2)
        self.assertEqual(RumorNews.objects.count(), 1)

    def test_rumor_creates_club_news(self):
        rng = _FixedRandom([0.01, 0.01])
        events.emit_event(
            events.EVENT_TRANSFER_DONE, player=self.player,
            club_a=self.seller, club_b=self.buyer,
            affected_club=self.seller, betrag=Decimal('5000000'), rng=rng)
        item = ClubNewsItem.objects.get(club=self.seller)
        self.assertEqual(item.category, 'Transfergerücht')
        self.assertEqual(item.outlet, 'Testkicker')

    def test_templates_have_min_eight_variants(self):
        for ev, tpls in events._TEMPLATES.items():
            self.assertGreaterEqual(len(tpls), 8, ev)

    def test_engine_never_raises(self):
        # Kaputter Kontext (kein Spieler, kein Betrag) darf nie werfen.
        r = events.emit_event(
            events.EVENT_LISTING_CREATED, player=None, club_a=None,
            betrag=None, rng=_FixedRandom([0.01, 0.01]))
        self.assertTrue(r is None or isinstance(r, RumorNews))

    def test_loan_return_uses_return_pool(self):
        rng = _FixedRandom([0.01, 0.01], choice_index=0)
        r = events.emit_event(
            events.EVENT_LOAN_DONE, player=self.player,
            club_a=self.buyer, club_b=self.seller,
            affected_club=self.seller, betrag=None,
            loan_return=True, rng=rng)
        self.assertIsNotNone(r)
        self.assertIn('Leihe beendet', r.headline)
        self.assertIn('kehrt', r.headline)

    def test_loan_return_pool_has_min_eight_variants(self):
        self.assertGreaterEqual(len(events._TEMPLATES_LOAN_RETURN), 8)


class EventDirectionTests(Base):
    """Ereignis-Richtung aus Spieler-Sicht (Review-Punkte Task #823)."""

    def _capture(self):
        calls = []
        orig = events.emit_event

        def spy(event_type, **kw):
            calls.append((event_type, kw))
            return None
        return calls, spy

    def test_buy_offer_deal_emits_correct_direction(self):
        # Initiator (buyer) will einen Spieler des Empfängers (seller)
        # kaufen: to_players=[player]. Abgebend MUSS der seller sein.
        calls, spy = self._capture()
        with self.captureOnCommitCallbacks(execute=True):
            deal = services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('2000000'), from_players=[],
                to_players=[self.player])
        from unittest.mock import patch
        with patch.object(events, 'emit_event', side_effect=spy), \
                self.captureOnCommitCallbacks(execute=True):
            services.accept_deal(deal)
        done = [kw for et, kw in calls if et == events.EVENT_TRANSFER_DONE]
        self.assertEqual(len(done), 1)
        kw = done[0]
        self.assertEqual(kw['club_a'], self.seller)   # abgebend
        self.assertEqual(kw['club_b'], self.buyer)    # aufnehmend
        self.assertEqual(kw['affected_club'], self.seller)
        self.assertEqual(kw['player'], self.player)
        self.assertEqual(Decimal(str(kw['betrag'])), Decimal('2000000.00'))

    def test_sell_offer_deal_emits_correct_direction(self):
        # Initiator (buyer als Verkäufer) gibt eigenen Spieler ab:
        # from_players=[p2]. Abgebend MUSS der Initiator sein.
        p2 = _mk_player(self.buyer, name='Eigen Gewaechs')
        calls, spy = self._capture()
        with self.captureOnCommitCallbacks(execute=True):
            deal = services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_to=Decimal('3000000'), from_players=[p2],
                to_players=[])
        from unittest.mock import patch
        with patch.object(events, 'emit_event', side_effect=spy), \
                self.captureOnCommitCallbacks(execute=True):
            services.accept_deal(deal)
        done = [kw for et, kw in calls if et == events.EVENT_TRANSFER_DONE]
        self.assertEqual(len(done), 1)
        kw = done[0]
        self.assertEqual(kw['club_a'], self.buyer)    # abgebend (Initiator)
        self.assertEqual(kw['club_b'], self.seller)   # aufnehmend
        self.assertEqual(kw['player'], p2)
        self.assertEqual(Decimal(str(kw['betrag'])), Decimal('3000000.00'))

    def test_option_purchase_emits_transfer_done(self):
        loan = Loan.objects.create(
            player=self.player, owner_club=self.seller,
            loan_club=self.buyer, fee=Decimal('1000000'), until='WP',
            buy_option=Decimal('4000000'))
        self.player.club = self.buyer
        self.player.loan_status = 'loaned_in'
        self.player.loan_partner_club = self.seller
        self.player.save()
        calls, spy = self._capture()
        from unittest.mock import patch
        with patch.object(events, 'emit_event', side_effect=spy), \
                self.captureOnCommitCallbacks(execute=True):
            record = services.exercise_buy_option(loan, self.buyer)
        self.assertEqual(record.kind, TransferRecord.KIND_OPTION)
        done = [kw for et, kw in calls if et == events.EVENT_TRANSFER_DONE]
        self.assertEqual(len(done), 1)
        kw = done[0]
        self.assertEqual(kw['club_a'], self.seller)   # Stammverein gibt ab
        self.assertEqual(kw['club_b'], self.buyer)    # Leihverein kauft
        self.assertEqual(Decimal(str(kw['betrag'])), Decimal('4000000.00'))

    def test_loan_return_emits_return_event(self):
        loan = Loan.objects.create(
            player=self.player, owner_club=self.seller,
            loan_club=self.buyer, fee=Decimal('1000000'), until='WP')
        self.player.club = self.buyer
        self.player.loan_status = 'loaned_in'
        self.player.loan_partner_club = self.seller
        self.player.save()
        calls, spy = self._capture()
        from unittest.mock import patch
        with patch.object(events, 'emit_event', side_effect=spy), \
                self.captureOnCommitCallbacks(execute=True):
            services.end_loan(loan)
        ret = [kw for et, kw in calls if et == events.EVENT_LOAN_DONE]
        self.assertEqual(len(ret), 1)
        kw = ret[0]
        self.assertTrue(kw.get('loan_return'))
        self.assertEqual(kw['club_a'], self.buyer)    # Leihverein gibt ab
        self.assertEqual(kw['club_b'], self.seller)   # Stammverein empfängt
        self.assertEqual(kw['affected_club'], self.seller)


# ══════════════════════════════════════════════════════════════════════════
#  Push-Katalog
# ══════════════════════════════════════════════════════════════════════════

class PushCatalogTests(Base):
    def _watch(self, manager=None):
        WatchlistEntry.objects.create(
            manager=manager or self.user.manager_profile, player=self.player)

    def test_watchlist_push_on_listing(self):
        self._watch()
        with self.captureOnCommitCallbacks(execute=True):
            services.create_listing(
                self.player, self.seller, min_bid=Decimal('1000000'),
                duration_days=3)
        self.assertTrue(Notification.objects.filter(
            recipient=self.user.manager_profile,
            title__startswith='Beobachtet:').exists())

    def test_outbid_push(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        third = _mk_club('FC Dritte')
        u3 = User.objects.create_user('histmgr3', password='x')
        third.managed_by = u3.manager_profile
        third.save(update_fields=['managed_by'])
        with self.captureOnCommitCallbacks(execute=True):
            services.place_bid(listing, self.buyer, Decimal('1000000'))
        with self.captureOnCommitCallbacks(execute=True):
            services.place_bid(listing, third, Decimal('2000000'))
        n = Notification.objects.filter(
            recipient=self.user.manager_profile,
            title__startswith='Überboten:').first()
        self.assertIsNotNone(n)
        self.assertIn('2.000.000', n.body)

    def test_pinned_new_bid_push(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        # Verkäufer pinnt sein eigenes Listing.
        ListingPin.objects.create(listing=listing, club=self.seller)
        with self.captureOnCommitCallbacks(execute=True):
            services.place_bid(listing, self.buyer, Decimal('1000000'))
        self.assertTrue(Notification.objects.filter(
            recipient=self.user2.manager_profile,
            title__startswith='Gepinnt: neues Gebot').exists())

    def test_auction_won_and_ended_push(self):
        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()
        # Hooks laufen via on_commit → im TestCase explizit ausführen.
        with self.captureOnCommitCallbacks(execute=True):
            services.close_listing(listing)
        self.assertTrue(Notification.objects.filter(
            recipient=self.user.manager_profile,
            title__startswith='Zuschlag erhalten:').exists())

    def test_conflict_expiry_survives_notification_failure(self):
        # Konflikt-Pfad: Der Vollzug scheitert (Mindestkader), die Auktion
        # endet EXPIRED mit Escrow-Freigabe — ein kaputter Push darf das
        # NICHT zurückrollen.
        from unittest.mock import patch
        from game.models import EconomyParameter
        from game.transfer_v2 import escrow

        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        # ERST NACH Listing+Gebot verschärfen: der Vollzug (Settlement)
        # scheitert dann an der Kadergrenze → Konflikt-Pfad.
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN',
            defaults={'value': self.seller.player_set.count()})
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()
        with patch('game.notifications.notify_club',
                   side_effect=RuntimeError('Push kaputt')), \
                self.captureOnCommitCallbacks(execute=True):
            services.close_listing(listing)
        listing.refresh_from_db()
        self.assertEqual(listing.status, TransferListing.STATUS_EXPIRED)
        # Escrow vollständig freigegeben, Spieler unverändert beim Verkäufer.
        self.assertEqual(
            escrow._v2_reserved_total(self.buyer), Decimal('0.00'))
        self.player.refresh_from_db()
        self.assertEqual(self.player.club_id, self.seller.pk)

    def test_pending_cancel_survives_notification_failure(self):
        # WP-Storno am Stichtag (Kadergrenze): Ein kaputter Push darf
        # Storno + Erstattung NICHT zurückrollen.
        from unittest.mock import patch
        from game.models import EconomyParameter
        from game.transfer_v2 import jobs
        from game.transfer_v2.models import PendingTransfer

        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            buy_now=Decimal('10000000'), timing='WP', duration_days=3)
        with self.captureOnCommitCallbacks(execute=True):
            services.buy_now(listing, self.buyer)
        buyer_budget_before = type(self.buyer).objects.get(
            pk=self.buyer.pk).budget
        # Kaderlimit einfrieren → +1 verletzt es am Stichtag.
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MAX_BASIS',
            defaults={'value': self.buyer.player_set.count()})
        pending = PendingTransfer.objects.get(player=self.player)
        PendingTransfer.objects.filter(pk=pending.pk).update(
            execute_at=timezone.localdate())
        with patch('game.notifications.notify_club',
                   side_effect=RuntimeError('Push kaputt')), \
                self.captureOnCommitCallbacks(execute=True):
            jobs.execute_due_pendings()
        pending.refresh_from_db()
        self.player.refresh_from_db()
        self.buyer.refresh_from_db()
        self.assertEqual(pending.status,
                         PendingTransfer.STATUS_CANCELLED_LIMIT)
        self.assertEqual(self.player.club_id, self.seller.pk)
        # Käufer voll erstattet — Kaufpreis kam zurück.
        self.assertEqual(self.buyer.budget,
                         buyer_budget_before + Decimal('10000000.00'))

    def test_close_listing_hooks_skipped_on_rollback(self):
        # close_listing in einem umgebenden atomic-Block, der zurückgerollt
        # wird: Die Nach-Commit-Hooks dürfen NIE gelaufen sein.
        from django.db import transaction as _tx

        listing = services.create_listing(
            self.player, self.seller, min_bid=Decimal('1000000'),
            duration_days=3)
        services.place_bid(listing, self.buyer, Decimal('1000000'))
        TransferListing.objects.filter(pk=listing.pk).update(
            ends_at=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()
        before = Notification.objects.count()

        class _Boom(Exception):
            pass

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with _tx.atomic():
                    services.close_listing(listing)
                    raise _Boom()
            except _Boom:
                pass
        # Rollback → keine on_commit-Hooks ausgeführt, keine Pushes.
        self.assertEqual(callbacks, [])
        self.assertEqual(Notification.objects.count(), before)
        self.assertFalse(Notification.objects.filter(
            title__startswith='Zuschlag erhalten:').exists())

    def test_deal_received_and_declined_push(self):
        with self.captureOnCommitCallbacks(execute=True):
            deal = services.create_deal_request(
                self.buyer, self.seller, typ=DealRequest.TYP_CASH,
                cash_from=Decimal('2000000'), from_players=[],
                to_players=[self.player])
        self.assertTrue(Notification.objects.filter(
            recipient=self.user2.manager_profile,
            title__startswith='Deal-Anfrage von').exists())
        with self.captureOnCommitCallbacks(execute=True):
            services.decline_deal(deal)
        self.assertTrue(Notification.objects.filter(
            recipient=self.user.manager_profile,
            title__startswith='Anfrage abgelehnt').exists())

    def test_recall_pushes(self):
        loan = Loan.objects.create(
            player=self.player, owner_club=self.seller,
            loan_club=self.buyer, fee=Decimal('1000000'), until='WP')
        self.player.club = self.buyer
        self.player.loan_status = 'loaned_in'
        self.player.loan_partner_club = self.seller
        self.player.save()
        with self.captureOnCommitCallbacks(execute=True):
            services.request_recall(loan, self.seller)
        self.assertTrue(Notification.objects.filter(
            recipient=self.user.manager_profile,
            title__startswith='Rückruf-Anfrage:').exists())
        loan.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            services.respond_recall(loan, self.buyer, accept=True)
        self.assertTrue(Notification.objects.filter(
            recipient=self.user2.manager_profile,
            title__startswith='Rückruf angenommen:').exists())


# ══════════════════════════════════════════════════════════════════════════
#  Ticker
# ══════════════════════════════════════════════════════════════════════════

class TickerTests(Base):
    def test_completed_transfer_in_ticker(self):
        self._record()
        self.login()
        r = self.client.get(reverse('transfer_market'))
        text = ''.join(p['t'] for p in r.context['ticker'])
        self.assertIn('TRANSFER FIX', text)
        self.assertIn('Hans Historie', text)

    def test_side_b_record_ticker_shows_correct_destination(self):
        # SIDE_B-Deal: Spieler wechselt zum Initiator (club_a=buyer).
        # Ticker muss "zu FC AUFNAHME" zeigen, nicht "zu FC ABGABE".
        self._record_side_b()
        self.login()
        r = self.client.get(reverse('transfer_market'))
        text = ''.join(p['t'] for p in r.context['ticker'])
        self.assertIn('TRANSFER FIX', text)
        self.assertIn('zu FC AUFNAHME', text)
        self.assertNotIn('zu FC ABGABE', text)
        self.assertIn('7.000.000', text)

    def test_cancelled_record_not_in_ticker(self):
        self._record(cancelled=True)
        self.login()
        r = self.client.get(reverse('transfer_market'))
        text = ''.join(p['t'] for p in r.context['ticker'])
        self.assertNotIn('TRANSFER FIX', text)

    def test_fresh_rumor_in_ticker(self):
        RumorNews.objects.create(
            event_type=RumorNews.EVENT_TRANSFER_DONE, player=self.player,
            affected_club=self.seller, outlet='Testkicker',
            headline='Testschlagzeile über einen Wechsel.',
            published_at=timezone.now())
        self.login()
        r = self.client.get(reverse('transfer_market'))
        text = ''.join(p['t'] for p in r.context['ticker'])
        self.assertIn('GERÜCHT (Testkicker)', text)
        self.assertIn('Testschlagzeile', text)
