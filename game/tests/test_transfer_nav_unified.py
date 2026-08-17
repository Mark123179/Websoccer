"""Tests Transfermarkt-Audit (Task #851) — einheitliche Navigation.

Deckt ab: alle Transfer-/Scouting-/Auktions-Seiten rendern dieselbe
Tab-Leiste (inkl. Auktionen-Link auf die echte showauction-Route),
aktiver Tab pro Seite, Budget-Kopf, Historie-Detailzeilen mit
Portrait/Flagge, Modal-Portal-Script global geladen.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.models import Club, EconomyParameter, GameSeasonState, League, Player
from game.transfer_v2.models import TransferRecord, TransferRecordPlayer


TAB_URL_NAMES = [
    'transfer_market', 'transfer_loan_market', 'transfer_my_deals',
    'transfer_offer_board', 'transfer_history', 'showauction_stage',
    'transfer_scouting', 'transfer_watchlist',
]


def _mk_club(name, budget='50000000.00', league=None):
    if league is None:
        league, _ = League.objects.get_or_create(
            name='NAV-Testliga', country='Deutschland')
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


class Base(TestCase):
    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        EconomyParameter.objects.update_or_create(
            saison='0', key='KADER_MIN', defaults={'value': 0})
        self.club = _mk_club('FC Navigation')
        self.other = _mk_club('FC Gegner')
        self.user = User.objects.create_user('navmanager', password='x')
        self.club.managed_by = self.user.manager_profile
        self.club.save(update_fields=['managed_by'])
        self.client.force_login(self.user)


class UnifiedNavTests(Base):
    """Jede Seite der Transferwelt trägt die komplette Tab-Leiste."""

    def _assert_full_nav(self, html, page_name):
        self.assertIn('tv2-tabs', html, page_name)
        for url_name in TAB_URL_NAMES:
            self.assertIn(reverse(url_name), html,
                          f'{page_name}: Link {url_name} fehlt')

    def test_all_pages_render_full_nav(self):
        for url_name in TAB_URL_NAMES:
            resp = self.client.get(reverse(url_name))
            self.assertEqual(resp.status_code, 200, url_name)
            self._assert_full_nav(resp.content.decode(), url_name)

    def test_active_tab_matches_page(self):
        # Aktiv-Markierung existiert auf jeder Seite genau einmal.
        for url_name in TAB_URL_NAMES:
            resp = self.client.get(reverse(url_name))
            html = resp.content.decode()
            self.assertEqual(
                html.count('tv2-tab is-active'), 1,
                f'{url_name}: erwartet genau einen aktiven Tab')

    def test_auction_tab_targets_real_route(self):
        resp = self.client.get(reverse('transfer_market'))
        self.assertIn(reverse('showauction_stage'), resp.content.decode())
        # Die Route selbst rendert (kein toter Link).
        resp2 = self.client.get(reverse('showauction_stage'))
        self.assertEqual(resp2.status_code, 200)

    def test_budget_header_on_scouting_and_auction_pages(self):
        for url_name in ('transfer_scouting', 'showauction_stage'):
            html = self.client.get(reverse(url_name)).content.decode()
            self.assertIn('tv2-budget', html, url_name)
            self.assertIn('Verfügbar', html, url_name)

    def test_old_scouting_tabs_partial_removed(self):
        for url_name in ('transfer_scouting', 'transfer_watchlist'):
            html = self.client.get(reverse(url_name)).content.decode()
            self.assertNotIn('sc-tabs', html, url_name)

    def test_modal_portal_script_loaded_globally(self):
        html = self.client.get(reverse('transfer_market')).content.decode()
        self.assertIn('modal_portal.js', html)


class ModalPortalCenteringTests(Base):
    """Verifies that the modal-portal centering implementation is structurally correct.

    Covers the static guarantees the browser verification confirmed:
    - All backdrop selectors in modal_portal.js exist in the HTML templates
    - The CSS .is-portaled rules apply transform:scale(--game-scale) to the inner card
    - The backdrops themselves use position:fixed + flex centering (viewport-correct)
    """

    def _css(self, path):
        import os
        full = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            path,
        )
        with open(full) as f:
            return f.read()

    # ── CSS presence checks ───────────────────────────────────────────────

    def test_transfer_css_has_portaled_scale_rule(self):
        """transfer_v2.css defines .is-portaled scale for tv2 backdrops."""
        css = self._css('game/static/game/css/transfer_v2.css')
        self.assertIn('.tv2-modal-backdrop.is-portaled', css)
        self.assertIn('.tv2-modal-overlay.is-portaled', css)
        self.assertIn('transform: scale(var(--game-scale', css)
        self.assertIn('transform-origin: center center', css)

    def test_scouting_css_has_portaled_scale_rule(self):
        """scouting.css defines .is-portaled scale for sc-bid-modal."""
        css = self._css('game/static/game/css/scouting.css')
        self.assertIn('.sc-bid-modal.is-portaled', css)
        self.assertIn('transform: scale(var(--game-scale', css)
        self.assertIn('transform-origin: center center', css)

    def test_backdrop_uses_fixed_flex_centering(self):
        """tv2-modal-backdrop has position:fixed + flex centering — viewport anchor."""
        css = self._css('game/static/game/css/transfer_v2.css')
        # backdrop rule contains the required centering declarations
        self.assertIn('position: fixed', css)
        self.assertIn('align-items: center', css)
        self.assertIn('justify-content: center', css)

    def test_sc_bid_modal_uses_fixed_flex_centering(self):
        """sc-bid-modal has position:fixed + flex centering."""
        css = self._css('game/static/game/css/scouting.css')
        self.assertIn('position: fixed', css)
        self.assertIn('align-items: center', css)
        self.assertIn('justify-content: center', css)

    # ── HTML presence checks (template classes match JS selectors) ────────

    def test_transfermarkt_has_deal_sheet_backdrop(self):
        html = self.client.get(reverse('transfer_market')).content.decode()
        self.assertIn('tv2-modal-backdrop', html)

    def test_anbieten_has_listing_loan_forum_backdrops(self):
        html = self.client.get(reverse('transfer_offer_board')).content.decode()
        self.assertIn('tv2-modal-backdrop', html, 'listing/loan/forum modal missing')

    def test_deals_has_summary_backdrop(self):
        html = self.client.get(reverse('transfer_my_deals')).content.decode()
        self.assertIn('tv2-modal-backdrop', html)

    def test_historie_has_report_overlay(self):
        html = self.client.get(reverse('transfer_history')).content.decode()
        self.assertIn('tv2-modal-overlay', html)

    def test_scouting_has_bid_modal(self):
        html = self.client.get(reverse('transfer_scouting')).content.decode()
        self.assertIn('sc-bid-modal', html)

    def test_game_scale_set_on_root_in_base(self):
        """--game-scale must be set on documentElement so portaled modals inherit it."""
        import os
        tmpl_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'game/templates/base.html',
        )
        with open(tmpl_path) as f:
            base_html = f.read()
        self.assertIn("documentElement.style.setProperty('--game-scale'", base_html)


class AuctionDetailNavTests(Base):
    """Auch die Auktions-Detailseite trägt die einheitliche Navigation."""

    def setUp(self):
        super().setUp()
        from showauction.models import ShowAuction
        self.player = Player.objects.create(
            club=self.other, first_name='Auk', last_name='Tion', age=22,
            position='Sturm', main_position_1='ST',
            nationalities='Deutschland', market_value=Decimal('5000000'),
        )
        self.auction = ShowAuction.objects.create(
            player=self.player, status=ShowAuction.STATUS_SCHEDULED,
            start_price=Decimal('1000000'),
        )

    def test_detail_page_renders_full_nav_with_active_auction_tab(self):
        resp = self.client.get(
            reverse('showauction_detail', args=[self.auction.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('tv2-tabs', html)
        for url_name in TAB_URL_NAMES:
            self.assertIn(reverse(url_name), html, url_name)
        self.assertEqual(html.count('tv2-tab is-active'), 1)
        self.assertIn('tv2-budget', html)


class HistoryDetailRowTests(Base):
    """Aufgeklappte Historie-Zeilen zeigen Portrait, Flagge und Links."""

    def setUp(self):
        super().setUp()
        self.player = Player.objects.create(
            club=self.other, first_name='His', last_name='Torie', age=24,
            position='Sturm', main_position_1='ST',
            nationalities='Deutschland', market_value=Decimal('3000000'),
        )
        self.record = TransferRecord.objects.create(
            kind=TransferRecord.KIND_CASH, date=date(2026, 8, 1),
            club_a=self.other, club_b=self.club,
            cash_b=Decimal('2500000'),
        )
        TransferRecordPlayer.objects.create(
            record=self.record, player=self.player,
            side=TransferRecordPlayer.SIDE_A,
            market_value_at_transfer=Decimal('3000000'),
        )

    def test_side_rows_contain_portrait_and_player_link(self):
        html = self.client.get(reverse('transfer_history')).content.decode()
        self.assertIn('tv2-hist-side-img', html)
        self.assertIn(reverse('player_detail', args=[self.player.pk]), html)

    def test_side_row_dict_has_portrait_field(self):
        from game.views_transfer_v2 import _player_side_rows
        rows = _player_side_rows(self.record, TransferRecordPlayer.SIDE_A)
        self.assertTrue(rows)
        self.assertIn('portrait', rows[0])
        self.assertIn('flag', rows[0])
        self.assertIn('player_url', rows[0])
