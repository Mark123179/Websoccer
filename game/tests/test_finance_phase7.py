"""Tests Finanzsystem Phase 7 — Kalibrierung & Regler-Pflege (Spec Kap. 16/17).

Deckt ab: Regler-Registry ([KALIBRIERUNG]-Keys, Auktionsvolumen ohne Key),
Status-Semantik der fünf Kennzahlen (ok/warn/alarm/nicht_messbar — nie
stilles ok), MW-Drift aus Snapshots, Gehaltslasten-Gruppen (laufende
Saison = nicht messbar), Zuschauer-Plausibilität inkl. Ausreißer,
Management-Command (Text + JSON) sowie die Creator-Ansicht: Staff-Gate,
JSON-Typ-Validierung, KI_KAEUFER-dry_run-Bewahrung und Saison-Versionierung
über EconomyParameter (ältere Saisons bleiben unangetastet).
"""

import datetime
import json
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from game.economy import kalibrierung
from game.economy.params import get_param
from game.economy.sponsors import kader_marktwert
from game.economy.stadium import basisnachfrage
from game.models import (
    Club, EconomyParameter, FinanceTransaction, GameSeasonState, League,
    MatchdayRevenue, Player, SeasonEconomySnapshot, Stadium,
)

SPEC_KEYS = frozenset({
    'BETRIEBSQUOTE', 'TV_TOEPFE', 'SPONSOR_MW_ANTEIL',
    'KI_ANGEBOTS_KADENZ', 'KI_KAEUFER', 'SCHMERZGRENZE_KONSTANTEN',
})


def _mk_league(name='Phase7-Liga'):
    league, _ = League.objects.get_or_create(name=name, country='DE')
    return league


def _mk_club(name, budget='0.00'):
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=_mk_league(),
    )


def _mk_player(club, name, mw):
    vor, nach = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=vor, last_name=nach, position='MID',
        age=25, potential=50, market_value=Decimal(str(mw)),
    )


def _mk_stadium(club, standing=10000, seating=20000, vip=1000):
    stadium = Stadium.objects.filter(club=club).first()
    if stadium is None:
        stadium = Stadium(club=club, name=f'{club.name}-Arena', city='X')
    for seite in ('nord', 'ost', 'sued', 'west'):
        setattr(stadium, f'{seite}_standing', standing // 4)
        setattr(stadium, f'{seite}_seating', seating // 4)
        setattr(stadium, f'{seite}_vip', vip // 4)
    stadium.save()
    return stadium


def _gehalt(club, saison, betrag):
    FinanceTransaction.objects.create(
        club=club, saison=saison, typ='GEHALT',
        betrag=Decimal(str(-betrag)), beschreibung='Test-Gehalt',
        datum=datetime.date(2026, 7, 1),
    )


# ── Regler-Registry ─────────────────────────────────────────────────────

class ReglerRegistryTests(TestCase):

    def test_kalibrierung_keys_entsprechen_spec(self):
        self.assertEqual(kalibrierung.KALIBRIERUNG_KEYS, SPEC_KEYS)

    def test_auktionsvolumen_ist_empfehlung_ohne_key(self):
        eintrag = [r for r in kalibrierung.KALIBRIERUNG_REGLER
                   if r['key'] is None]
        self.assertEqual(len(eintrag), 1)
        self.assertTrue(eintrag[0]['kalibrierung'])
        self.assertEqual(eintrag[0]['titel'], 'Auktionsvolumen pro Saison')
        self.assertIn('geldmenge', eintrag[0]['wirkt_auf'])

    def test_alle_regler_keys_existieren_als_economy_parameter(self):
        for r in kalibrierung.KALIBRIERUNG_REGLER:
            if r['key']:
                self.assertTrue(
                    EconomyParameter.objects.filter(key=r['key']).exists(),
                    f"Registry-Key {r['key']} hat keine Seed-Zeile",
                )

    def test_regler_fuer_geldmenge(self):
        namen = kalibrierung.regler_fuer('geldmenge')
        self.assertIn('BETRIEBSQUOTE', namen)
        self.assertIn('Auktionsvolumen pro Saison', namen)

    def test_jede_kennzahl_hat_regler_verweis(self):
        report = kalibrierung.kalibrierungs_report('0')
        for k in report['kennzahlen']:
            self.assertTrue(k['regler'], f"{k['id']} ohne Regler-Verweis")


# ── Kennzahl 1: Geldmenge vs. MW-Drift ──────────────────────────────────

class GeldmengeTests(TestCase):

    def test_mw_drift_aus_zwei_snapshots(self):
        for saison, mw in (('0', '1000000'), ('1', '1100000')):
            SeasonEconomySnapshot.objects.create(
                saison=saison, mw_median=Decimal(mw),
                staerke_median=Decimal('60'),
                potential_median=Decimal('65'),
                gehalts_anker=Decimal(mw),
            )
        drift = kalibrierung.mw_drift_verlauf()
        self.assertAlmostEqual(drift['0'], 0.10, places=4)
        self.assertNotIn('1', drift)

    def test_ohne_ledger_nicht_messbar(self):
        k = kalibrierung.geldmenge_vs_mw_drift('42')
        self.assertEqual(k['status'], kalibrierung.STATUS_NICHT_MESSBAR)

    def _mit(self, wachstum, drift):
        verlauf = ([{'saison': '5', 'wachstum': wachstum, 'netto': 1}]
                   if wachstum is not None else [])
        with patch.object(kalibrierung.monitoring, 'geldmengen_verlauf',
                          return_value=verlauf), \
             patch.object(kalibrierung, 'mw_drift_verlauf',
                          return_value=({'5': drift} if drift is not None
                                        else {})):
            return kalibrierung.geldmenge_vs_mw_drift('5')

    def test_alarm_ueber_vier_prozent(self):
        self.assertEqual(self._mit(0.05, 0.05)['status'],
                         kalibrierung.STATUS_ALARM)

    def test_ok_innerhalb_zwei_pp(self):
        self.assertEqual(self._mit(0.02, 0.01)['status'],
                         kalibrierung.STATUS_OK)

    def test_warn_ausserhalb_zwei_pp(self):
        self.assertEqual(self._mit(0.03, 0.0)['status'],
                         kalibrierung.STATUS_WARN)

    def test_ohne_drift_nicht_messbar(self):
        self.assertEqual(self._mit(0.01, None)['status'],
                         kalibrierung.STATUS_NICHT_MESSBAR)


# ── Kennzahl 2: Ablöse/MW-Median ────────────────────────────────────────

class AbloeseMwTests(TestCase):

    def test_ohne_transfers_nicht_messbar(self):
        k = kalibrierung.abloese_mw('78')
        self.assertEqual(k['status'], kalibrierung.STATUS_NICHT_MESSBAR)
        self.assertIsNone(k['median'])

    def test_median_im_korridor_ok(self):
        club = _mk_club('Median FC')
        player = _mk_player(club, 'Eins Mann', 1_000_000)
        FinanceTransaction.objects.create(
            club=club, saison='78', typ='TRANSFER_AUS',
            betrag=Decimal('-1500000'), referenz_typ='transfer',
            referenz_id=player.pk, datum=datetime.date(2026, 7, 1),
        )
        k = kalibrierung.abloese_mw('78')
        self.assertEqual(k['status'], kalibrierung.STATUS_OK)
        self.assertAlmostEqual(k['median'], 1.5, places=2)
        self.assertEqual(k['count'], 1)


# ── Kennzahl 3: Gehaltslasten ───────────────────────────────────────────

class GehaltslastenTests(TestCase):

    def _vier_clubs(self, saison, quote_klein, quote_top):
        mws = (1_000_000, 2_000_000, 3_000_000, 10_000_000)
        clubs = []
        for i, mw in enumerate(mws):
            club = _mk_club(f'Gehalt{i} FC')
            _mk_player(club, f'Spieler Nr{i}', mw)
            clubs.append((club, mw))
        _gehalt(clubs[0][0], saison, mws[0] * quote_klein)
        _gehalt(clubs[1][0], saison, mws[1] * 0.20)
        _gehalt(clubs[2][0], saison, mws[2] * 0.25)
        _gehalt(clubs[3][0], saison, mws[3] * quote_top)
        return clubs

    def test_laufende_saison_nicht_messbar(self):
        club = _mk_club('Laufend FC')
        _mk_player(club, 'Aktuell Mann', 1_000_000)
        _gehalt(club, '0', 180_000)   # ohne GameSeasonState ist '0' aktuell
        k = kalibrierung.gehaltslasten('0')
        self.assertEqual(k['status'], kalibrierung.STATUS_NICHT_MESSBAR)
        self.assertTrue(k['laufend'])
        self.assertIsNotNone(k['quote_klein'])   # nachrichtlich vorhanden

    def test_abgeschlossene_saison_im_korridor_ok(self):
        self._vier_clubs('7', quote_klein=0.18, quote_top=0.29)
        k = kalibrierung.gehaltslasten('7')
        self.assertEqual(k['status'], kalibrierung.STATUS_OK)
        self.assertAlmostEqual(k['quote_klein'], 0.18, places=3)
        self.assertAlmostEqual(k['quote_top'], 0.29, places=3)
        self.assertEqual(k['gruppen_groesse'], 1)

    def test_warn_bei_leichter_abweichung(self):
        self._vier_clubs('7', quote_klein=0.25, quote_top=0.29)
        k = kalibrierung.gehaltslasten('7')
        self.assertEqual(k['status'], kalibrierung.STATUS_WARN)

    def test_alarm_ueber_zehn_pp(self):
        self._vier_clubs('7', quote_klein=0.35, quote_top=0.29)
        k = kalibrierung.gehaltslasten('7')
        self.assertEqual(k['status'], kalibrierung.STATUS_ALARM)

    def test_ohne_buchungen_nicht_messbar(self):
        k = kalibrierung.gehaltslasten('7')
        self.assertEqual(k['status'], kalibrierung.STATUS_NICHT_MESSBAR)


# ── Kennzahl 4: Zuschauer-Plausibilität ─────────────────────────────────

class ZuschauerTests(TestCase):

    def _heimspiel(self, ratio):
        club = _mk_club('Zuschauer FC')
        _mk_player(club, 'Zug Kraft', 5_000_000)
        stadium = _mk_stadium(club)
        basis = basisnachfrage(kader_marktwert(club))
        kapazitaet = float(stadium.capacity_standing
                           + stadium.capacity_seating
                           + stadium.capacity_vip)
        referenz = min(basis, kapazitaet)
        MatchdayRevenue.objects.create(
            stadium=stadium, match_label='Test-Heimspiel',
            attendance=int(referenz * ratio),
            auslastung_pct=Decimal('50.0'),
        )
        return referenz

    def test_ohne_daten_nicht_messbar(self):
        k = kalibrierung.zuschauer_plausibilitaet()
        self.assertEqual(k['status'], kalibrierung.STATUS_NICHT_MESSBAR)

    def test_plausible_quote_ok(self):
        self._heimspiel(0.8)
        k = kalibrierung.zuschauer_plausibilitaet()
        self.assertEqual(k['status'], kalibrierung.STATUS_OK)
        self.assertEqual(k['spiele'], 1)
        self.assertAlmostEqual(k['median'], 0.8, places=1)
        self.assertEqual(k['ausreisser'], [])

    def test_ausreisser_wird_warn_und_gelistet(self):
        self._heimspiel(2.0)
        k = kalibrierung.zuschauer_plausibilitaet()
        self.assertEqual(k['status'], kalibrierung.STATUS_WARN)
        self.assertEqual(len(k['ausreisser']), 1)
        self.assertEqual(k['ausreisser'][0]['club'], 'Zuschauer FC')


# ── Kennzahl 5 + Gesamt-Report ──────────────────────────────────────────

class ReportTests(TestCase):

    def test_ki_anteil_ohne_volumen_nicht_messbar(self):
        k = kalibrierung.ki_kaufvolumen('78')
        self.assertEqual(k['status'], kalibrierung.STATUS_NICHT_MESSBAR)

    def test_report_hat_fuenf_kennzahlen_und_konsistente_zaehler(self):
        report = kalibrierung.kalibrierungs_report('0')
        self.assertEqual(len(report['kennzahlen']), 5)
        self.assertEqual(
            [k['id'] for k in report['kennzahlen']],
            ['geldmenge', 'abloese_mw', 'gehaltslasten', 'zuschauer',
             'ki_anteil'],
        )
        summe = (report['alarm_count'] + report['warn_count']
                 + report['nicht_messbar_count']
                 + sum(1 for k in report['kennzahlen']
                       if k['status'] == kalibrierung.STATUS_OK))
        self.assertEqual(summe, 5)

    def test_command_text_und_json(self):
        out = StringIO()
        call_command('kalibrierungs_report', stdout=out)
        self.assertIn('Kalibrierungs-Report', out.getvalue())

        out = StringIO()
        call_command('kalibrierungs_report', '--json', stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(len(data['kennzahlen']), 5)


# ── Creator-Ansicht ─────────────────────────────────────────────────────

class KalibrierungViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            'kalib-staff', password='x', is_staff=True)
        cls.normal = User.objects.create_user('kalib-user', password='x')
        cls.url = reverse('creator_kalibrierung')

    def test_nur_staff(self):
        self.client.force_login(self.normal)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_get_zeigt_alle_abschnitte(self):
        self.client.force_login(self.staff)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Kennzahlen-Report', html)
        self.assertIn('Regler-Übersicht', html)
        self.assertIn('Kalibrierungs-Leitfaden', html)
        self.assertIn('KALIBRIERUNG', html)
        self.assertIn('BETRIEBSQUOTE', html)

    def _post(self, key, value):
        self.client.force_login(self.staff)
        return self.client.post(
            self.url, {'key': key, 'value': value}, follow=True)

    def test_speichern_versioniert_pro_saison(self):
        GameSeasonState.objects.create(current_season=1)
        alt = get_param('BETRIEBSQUOTE', '0')
        neu = float(alt) + 0.01
        r = self._post('BETRIEBSQUOTE', json.dumps(neu))
        self.assertContains(r, 'gespeichert')
        # Neue Saison-Zeile, Seed der Saison 0 unangetastet:
        self.assertEqual(get_param('BETRIEBSQUOTE', '1'), neu)
        self.assertEqual(get_param('BETRIEBSQUOTE', '0'), alt)
        self.assertTrue(EconomyParameter.objects.filter(
            saison='1', key='BETRIEBSQUOTE').exists())

    def test_typwechsel_abgelehnt(self):
        alt = get_param('BETRIEBSQUOTE', '0')
        r = self._post('BETRIEBSQUOTE', '"kaputt"')
        self.assertContains(r, 'Typwechsel abgelehnt')
        self.assertEqual(get_param('BETRIEBSQUOTE', '0'), alt)

    def test_bool_ist_kein_zahl_ersatz(self):
        r = self._post('BETRIEBSQUOTE', 'true')
        self.assertContains(r, 'Typwechsel abgelehnt')

    def test_ungueltiges_json_abgelehnt(self):
        r = self._post('BETRIEBSQUOTE', '{kaputt')
        self.assertContains(r, 'Ungültiges JSON')

    def test_unbekannter_key_abgelehnt(self):
        r = self._post('GIBTS_NICHT', '1')
        self.assertContains(r, 'Unbekannter Parameter-Key')

    def test_ki_kaeufer_dry_run_wird_bewahrt(self):
        kk = get_param('KI_KAEUFER', '0')
        manipuliert = dict(kk)
        manipuliert['dry_run'] = not kk.get('dry_run', True)
        self._post('KI_KAEUFER', json.dumps(manipuliert))
        neu = get_param('KI_KAEUFER', '0')
        self.assertEqual(neu.get('dry_run'), kk.get('dry_run', True))


# ── Ausbildungsabgabe MW-Snapshot ────────────────────────────────────────

class AusbildungsabgabeMwSnapshotTests(TestCase):
    """referenz_mw wird bei ablösefrei und Tausch auf mw_basis-Wert gesetzt."""

    @classmethod
    def setUpTestData(cls):
        from game.models import PlayerClubHistory

        league, _ = League.objects.get_or_create(name='Abgabe-Liga', country='DE')

        cls.kaeufer = Club.objects.create(
            name='Käufer FC', short_name='KAE', founded_year=1900,
            budget=Decimal('10000000.00'), league=league,
        )
        cls.verkaeufer = Club.objects.create(
            name='Verkäufer FC', short_name='VER', founded_year=1900,
            budget=Decimal('10000000.00'), league=league,
        )
        cls.club_b = Club.objects.create(
            name='Tausch-B FC', short_name='TAB', founded_year=1900,
            budget=Decimal('10000000.00'), league=league,
        )
        cls.ausbilder = Club.objects.create(
            name='Ausbilder FC', short_name='AUS', founded_year=1900,
            budget=Decimal('1000000.00'), league=league,
        )

        cls.user_a = User.objects.create_user('abg_mgr_a', password='x')
        cls.user_b = User.objects.create_user('abg_mgr_b', password='x')
        cls.verkaeufer.managed_by = cls.user_a.manager_profile
        cls.verkaeufer.save(update_fields=['managed_by'])
        cls.club_b.managed_by = cls.user_b.manager_profile
        cls.club_b.save(update_fields=['managed_by'])

    def _mk_spieler_mit_history(self, current_club, mw, ausbilder=None):
        """Spieler (age=18) mit einer Ausbildungsstation, damit Abgabe > 0."""
        from game.models import PlayerClubHistory

        p = Player.objects.create(
            club=current_club, first_name='Test', last_name='Abgabe',
            position='MID', age=18, potential=75,
            market_value=Decimal(str(mw)),
        )
        ausb = ausbilder or self.ausbilder
        # cutoff = saison(0) + (21-18) = 3 → season=0 <= 3 ✓
        PlayerClubHistory.objects.create(player=p, club=ausb, season=0)
        return p

    def test_free_transfer_setzt_referenz_mw(self):
        """AUSBILDUNG_AUS-Zeile trägt den mw_basis()-Wert als referenz_mw."""
        from game.economy.transfers import execute_free_transfer, mw_basis

        # Spieler ohne aktuellen Verein (kein Mindestkader-Problem)
        spieler = self._mk_spieler_mit_history(None, 2_000_000)
        spieler.club = None
        spieler.save(update_fields=['club'])

        basis = mw_basis(spieler, '0')
        execute_free_transfer(spieler, self.kaeufer, saison='0')

        tx = FinanceTransaction.objects.filter(
            club=self.kaeufer, typ='AUSBILDUNG_AUS',
        ).order_by('-id').first()
        self.assertIsNotNone(tx, 'AUSBILDUNG_AUS fehlt nach free transfer')
        self.assertEqual(tx.referenz_mw, basis,
                         'referenz_mw stimmt nicht mit mw_basis überein')

    def test_swap_setzt_referenz_mw_fuer_beide(self):
        """Beide AUSBILDUNG_AUS-Zeilen tragen jeweils den mw_basis()-Wert."""
        from game.economy.transfers import execute_swap, mw_basis

        spieler_a = self._mk_spieler_mit_history(self.verkaeufer, 1_500_000)
        spieler_b = self._mk_spieler_mit_history(self.club_b, 2_500_000)

        basis_a = mw_basis(spieler_a, '0')
        basis_b = mw_basis(spieler_b, '0')

        execute_swap(spieler_a, spieler_b, saison='0')

        tx_a = FinanceTransaction.objects.filter(
            club=self.verkaeufer, typ='AUSBILDUNG_AUS',
        ).order_by('-id').first()
        tx_b = FinanceTransaction.objects.filter(
            club=self.club_b, typ='AUSBILDUNG_AUS',
        ).order_by('-id').first()
        self.assertIsNotNone(tx_a, 'AUSBILDUNG_AUS für verkaeufer fehlt')
        self.assertIsNotNone(tx_b, 'AUSBILDUNG_AUS für club_b fehlt')
        self.assertEqual(tx_a.referenz_mw, basis_a,
                         'referenz_mw für Spieler A stimmt nicht')
        self.assertEqual(tx_b.referenz_mw, basis_b,
                         'referenz_mw für Spieler B stimmt nicht')

    def test_fussnote_saison_0_vorhanden(self):
        """abloese_mw() enthält für Saison 0 eine Backfill-Fußnote."""
        from game.economy.kalibrierung import abloese_mw
        result = abloese_mw('0')
        self.assertIn('fussnote', result)
        self.assertIn('Approximation', result['fussnote'])

    def test_fussnote_andere_saison_leer(self):
        """abloese_mw() enthält für andere Saisons keine Fußnote."""
        from game.economy.kalibrierung import abloese_mw
        result = abloese_mw('5')
        self.assertEqual(result.get('fussnote', ''), '')
