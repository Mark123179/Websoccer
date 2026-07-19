"""Prüflauf-Orchestrierung des KI-Käufers (Spec Kap. 9.3).

Läuft je Spieltag NACH der Finanzabrechnung (Hook in season_service,
außerhalb der Finanz-Transaktion) sowie manuell via Command ai_buyer_run.

Reihenfolge je KI-Verein (managed_by IS NULL, nicht pausiert):
  1. Fenster-Gate (GameSeasonState.transfer_window_open)
  2. Abgelaufene Angebote schließen
  3. Budget: Überschuss = Konto − Fixkosten-Puffer (½ Saison)
  4. Bedarfsanalyse (Beste-11 vs. Liga-Soll) → akute Lücken nach Score
  5. Bedarfskäufe: je Lücke bester Nutzen-Kandidat; KI-Verkäufer →
     Sofort-Clearing, Manager-Verkäufer → Angebot (Kadenz max_offen_ki /
     max_pro_fenster_ki)
  6. Ohne akuten Bedarf: Qualitätskauf (Überschuss > Faktor×Puffer,
     max. 1/Fenster) bzw. Talentkauf (max. 1 Deal/Saison) — beide nur,
     wenn der Dringlichkeits-Torwächter es erlaubt (kein Abstiegskandidat,
     Saisonziel nicht gefährdet).

Globaler Governor: KI-Kaufvolumen ≤ governor_anteil des
Gesamt-Transfervolumens der Saison — überschritten ⇒ keine neuen Käufe
+ Monitoring-Alarm im Report.

Idempotenz: AIBuyerRun-Unique je (club, saison, spieltag) für
trigger='spieltag' — Doppel-Hooks sind unschädlich.
"""
import logging
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum

from ..params import get_param
from ..snapshot import ensure_season_snapshot
from .bedarf import bedarfs_analyse, dringlichkeit, liga_soll
from .budget import fixkosten_puffer, ueberschuss
from .kandidaten import finde_kandidaten
from .offers import (
    AIBuyerError,
    create_offer,
    expire_offers,
    ki_zu_ki_clearing,
    max_gebot_fuer,
)

logger = logging.getLogger(__name__)


def _params(saison):
    return get_param('KI_KAEUFER', saison)


def _season_state():
    from game.models import GameSeasonState
    state, _ = GameSeasonState.objects.get_or_create(pk=1)
    return state


def governor_status(saison, params=None):
    """KI-Kaufvolumen vs. Gesamt-Transfervolumen der Saison.

    Returns dict: {'ki_volumen', 'gesamt_volumen', 'anteil', 'limit',
                   'ueberschritten'}.
    """
    from game.models import AITransferOffer, FinanceTransaction

    params = params or _params(saison)
    limit = Decimal(str(params.get('governor_anteil', 0.5)))

    gesamt = (
        FinanceTransaction.objects
        .filter(saison=str(saison), typ='TRANSFER_EIN')
        .aggregate(s=Sum('betrag'))['s'] or Decimal('0')
    )
    ki = (
        AITransferOffer.objects
        .filter(status=AITransferOffer.STATUS_DEAL, dry_run=False,
                created_at__isnull=False)
        .filter(player__isnull=False)
        .filter(buyer_club__managed_by__isnull=True)
        .filter(window_id__startswith=f'{saison}-')
        .aggregate(s=Sum('aktuelles_gebot'))['s'] or Decimal('0')
    )
    anteil = (ki / gesamt) if gesamt > 0 else Decimal('0')
    return {
        'ki_volumen': ki,
        'gesamt_volumen': gesamt,
        'anteil': anteil,
        'limit': limit,
        'ueberschritten': gesamt > 0 and anteil > limit,
    }


def _offene_ki_angebote(club, *, dry_run):
    """Zahl offener aktiver Angebote des KI-Vereins (Kadenz max_offen_ki).

    Im Scharfbetrieb zählen nur versendete Angebote; Trockenlauf-Angebote
    (Status 'berechnet') blockieren die Kadenz des Scharfbetriebs nicht,
    zählen aber im Trockenlauf selbst (realistische Simulation).
    """
    from game.models import AITransferOffer

    status = (AITransferOffer.OFFENE_STATUS if dry_run
              else (AITransferOffer.STATUS_VERSENDET,))
    return AITransferOffer.objects.filter(
        buyer_club=club, status__in=status,
    ).count()


def _fenster_angebote(club, window_id, kauftyp=None):
    """Angebote des Vereins im laufenden Fenster (Kadenz max_pro_fenster)."""
    from game.models import AITransferOffer

    qs = AITransferOffer.objects.filter(
        buyer_club=club, window_id=window_id,
    ).exclude(status=AITransferOffer.STATUS_STORNIERT)
    if kauftyp:
        qs = qs.filter(kauftyp=kauftyp)
    return qs.count()


def _talent_deal_in_saison(club, saison):
    from game.models import AITransferOffer
    return AITransferOffer.objects.filter(
        buyer_club=club, kauftyp=AITransferOffer.KAUFTYP_TALENT,
        status=AITransferOffer.STATUS_DEAL,
        window_id__startswith=f'{saison}-',
    ).exists()


def _kaderplatz_frei(club, saison):
    """Käufer-Kaderplatz-Gate (Spec 9.1): Käufe nur mit freiem Platz."""
    from ..kader import effective_squad_limit, squad_count
    return squad_count(club) < effective_squad_limit(club, saison)


def _kauf_versuchen(club, kandidatenliste, *, kauftyp, params, saison,
                    window_id, dry_run, spieltag, budget_max,
                    luecken_score=None, begruendung=''):
    """Besten bezahlbaren Kandidaten kaufen/anbieten.

    Returns dict {'aktion': 'deal'|'angebot'|'berechnet'|None, …}.
    """
    if not _kaderplatz_frei(club, saison):
        return {'aktion': None, 'grund': 'kader_voll'}
    for kandidat in kandidatenliste:
        # Bezahlbarkeit am eigenen Käufer-Maximum messen (mehr zahlt die KI
        # nie — weder Clearing-Preis noch Gebotstreppe überschreiten es).
        # Die erwartete Forderung (1,1–1,3×) ist nur Ranking-Heuristik.
        max_gebot = max_gebot_fuer(kauftyp, kandidat['wertung'], params)
        if max_gebot <= 0 or max_gebot > budget_max:
            continue
        player = kandidat['player']
        seller = player.club
        if seller.managed_by_id is None:
            ergebnis = ki_zu_ki_clearing(
                club, kandidat, kauftyp=kauftyp, params=params,
                saison=saison, window_id=window_id, dry_run=dry_run,
                spieltag=spieltag, luecken_score=luecken_score,
                begruendung=begruendung,
            )
            if ergebnis['ergebnis'] in ('deal', 'berechnet'):
                return {
                    'aktion': ergebnis['ergebnis'],
                    'player_id': player.pk,
                    'player': player.full_name,
                    'seller': seller.name,
                    'preis': str(ergebnis['preis']),
                }
            continue  # kein Deal (Forderung über Max) → nächster Kandidat
        # Manager-Verein → Angebot (Postfach bzw. Trockenlauf-Berechnung).
        try:
            offer = create_offer(
                club, player, kauftyp=kauftyp, wertung=kandidat['wertung'],
                params=params, saison=saison, window_id=window_id,
                dry_run=dry_run, luecken_score=luecken_score,
                begruendung=begruendung,
            )
        except AIBuyerError:
            continue
        return {
            'aktion': 'berechnet' if dry_run else 'angebot',
            'offer_id': offer.pk,
            'player_id': player.pk,
            'player': player.full_name,
            'seller': seller.name,
            'gebot': str(offer.aktuelles_gebot),
        }
    return {'aktion': None}


def run_club_pruflauf(club, *, saison, spieltag, trigger='spieltag',
                      params=None, state=None, soll=None, snapshot=None,
                      governor=None):
    """Prüflauf eines KI-Vereins. Returns AIBuyerRun oder None (Duplikat)."""
    from game.models import AIBuyerRun

    params = params or _params(saison)
    state = state or _season_state()
    dry_run = bool(params.get('dry_run', True))
    window_id = state.transfer_window_id or f'{saison}-F1'
    snapshot = snapshot or ensure_season_snapshot(saison)

    report = {
        'dry_run': dry_run,
        'window_id': window_id,
        'entscheidungen': [],
        'kaeufe': [],
    }

    run = AIBuyerRun(
        club=club, saison=str(saison), spieltag=int(spieltag or 0),
        trigger=trigger, dry_run=dry_run, window_id=window_id,
    )
    try:
        # Eigener atomarer Block: der Duplikat-IntegrityError darf eine
        # umgebende Transaktion (z. B. Spieltags-Hook) nicht zerbrechen.
        with transaction.atomic():
            run.save()
    except IntegrityError:
        return None  # Spieltagslauf existiert schon (Doppel-Hook).

    def _log(text):
        report['entscheidungen'].append(text)

    try:
        if not state.transfer_window_open:
            _log('Transferfenster geschlossen — keine Aktivität.')
            return run

        if governor is None:
            governor = governor_status(saison, params)
        if governor['ueberschritten']:
            _log('[ALARM] Governor überschritten '
                 f'({governor["anteil"]:.0%} > {governor["limit"]:.0%}) — '
                 'keine neuen Käufe.')
            report['governor'] = {
                'anteil': str(governor['anteil']),
                'limit': str(governor['limit']),
            }
            return run

        if not _kaderplatz_frei(club, saison):
            _log('Kein freier Kaderplatz — keine Käufe.')
            return run

        anker = snapshot.gehalts_anker
        budget = ueberschuss(club, saison, params, anker=anker)
        report['budget'] = {k: str(v) for k, v in budget.items()}
        if budget['ueberschuss'] <= 0:
            _log(f'Kein Überschuss (Konto {budget["konto"]}, '
                 f'Puffer {budget["puffer"]}) — keine Käufe.')
            return run

        if soll is None:
            soll = liga_soll(club.league)
        report['liga_soll'] = str(soll)

        analyse = bedarfs_analyse(club, soll, params)
        if analyse['elf'] is None:
            _log('Leerer Kader — keine Bedarfsanalyse möglich.')
            return run

        polster_ok = budget['ueberschuss'] > 0
        lage = dringlichkeit(club, params, polster_ok=polster_ok)
        report['dringlichkeit'] = {
            'faktor': str(lage['faktor']),
            'abstiegskandidat': lage['abstiegskandidat'],
            'ziel_gefaehrdet': lage['ziel_gefaehrdet'],
            'rank': lage['rank'],
        }

        seed = f'{club.pk}:{window_id}'
        max_offen = int(params.get('max_offen_ki', 1))
        max_fenster = int(params.get('max_pro_fenster_ki', 3))

        # ── 1) Bedarfskäufe (höchster Lückenscore zuerst) ────────────────
        akut = analyse['akut']
        report['akute_luecken'] = [
            {'position': l['position'], 'score': str(l['score']),
             'kritisch': l['kritisch']}
            for l in akut
        ]
        rest_budget = budget['ueberschuss']
        for luecke in akut:
            if _offene_ki_angebote(club, dry_run=dry_run) >= max_offen:
                _log('Kadenz: offenes Angebot vorhanden — Bedarf pausiert.')
                break
            if _fenster_angebote(club, window_id) >= max_fenster:
                _log('Kadenz: Fensterlimit erreicht — Bedarf pausiert.')
                break
            kandidaten = finde_kandidaten(
                club, kauftyp='bedarf', params=params, saison=saison,
                seed=seed, window_id=window_id,
                position=luecke['position'],
                min_staerke=luecke['staerke'], snapshot=snapshot,
            )
            if not kandidaten:
                _log(f'Bedarf {luecke["position"]} (Score {luecke["score"]}): '
                     'keine Kandidaten.')
                continue
            ergebnis = _kauf_versuchen(
                club, kandidaten, kauftyp='bedarf', params=params,
                saison=saison, window_id=window_id, dry_run=dry_run,
                spieltag=spieltag, budget_max=rest_budget,
                luecken_score=luecke['score'],
                begruendung=(f'Bedarfskauf {luecke["position"]}: '
                             f'Lückenscore {luecke["score"]:.1f}, '
                             f'Liga-Soll {Decimal(str(soll)):.1f}.'),
            )
            if ergebnis['aktion'] is None:
                _log(f'Bedarf {luecke["position"]}: kein bezahlbarer '
                     'Kandidat.')
                continue
            report['kaeufe'].append({'typ': 'bedarf', **ergebnis})
            if ergebnis['aktion'] == 'deal':
                club.refresh_from_db(fields=['budget'])
                rest_budget = ueberschuss(
                    club, saison, params, anker=anker,
                )['ueberschuss']
                if rest_budget <= 0:
                    _log('Überschuss aufgebraucht — Prüflauf beendet.')
                    break

        # ── 2) Qualität/Talent nur ohne akuten Bedarf + Torwächter ──────
        if akut:
            return run
        if lage['abstiegskandidat'] or lage['ziel_gefaehrdet']:
            _log('Torwächter: nur Bedarfskäufe erlaubt '
                 '(Abstiegskandidat/Saisonziel gefährdet).')
            return run
        if _offene_ki_angebote(club, dry_run=dry_run) >= max_offen:
            return run
        if _fenster_angebote(club, window_id) >= max_fenster:
            return run

        elf_staerken = analyse['elf']['staerken']
        kader_niveau = (sum(elf_staerken) / len(elf_staerken)
                        if elf_staerken else Decimal('0'))

        # Qualitätskauf: deutlicher Überschuss + max. 1 je Fenster.
        quali_schwelle = budget['puffer'] * Decimal(
            str(params.get('quali_ueberschuss_faktor', 2)))
        if (budget['ueberschuss'] > quali_schwelle
                and _fenster_angebote(club, window_id, 'qualitaet') < 1):
            delta = Decimal(str(params.get('quali_staerke_delta', 10)))
            beste = None
            for position, posbest in analyse['posbester'].items():
                kandidaten = finde_kandidaten(
                    club, kauftyp='qualitaet', params=params, saison=saison,
                    seed=seed, window_id=window_id, position=position,
                    min_staerke=posbest + delta - 1, limit=5,
                    snapshot=snapshot,
                )
                for k in kandidaten:
                    if k['staerke'] >= posbest + delta and (
                            beste is None
                            or k['nutzen'] > beste[1]['nutzen']):
                        beste = (position, k)
            if beste is not None:
                position, kandidat = beste
                ergebnis = _kauf_versuchen(
                    club, [kandidat], kauftyp='qualitaet', params=params,
                    saison=saison, window_id=window_id, dry_run=dry_run,
                    spieltag=spieltag, budget_max=budget['ueberschuss'],
                    begruendung=(f'Qualitätskauf {position}: '
                                 f'+{delta} über Positionsbestem.'),
                )
                if ergebnis['aktion'] is not None:
                    report['kaeufe'].append({'typ': 'qualitaet', **ergebnis})
                    return run
            else:
                _log('Qualitätskauf: kein Kandidat ≥ Positionsbester '
                     f'+{params.get("quali_staerke_delta", 10)}.')

        # Talentkauf: max. 1 Deal je Saison (Talent-Slot).
        if not _talent_deal_in_saison(club, saison):
            max_alter = int(params.get('talent_max_alter', 21))
            pot_delta = Decimal(str(params.get('talent_potential_delta', 15)))
            kandidaten = finde_kandidaten(
                club, kauftyp='talent', params=params, saison=saison,
                seed=seed, window_id=window_id, max_alter=max_alter,
                min_potential=kader_niveau + pot_delta, limit=10,
                snapshot=snapshot,
            )
            if kandidaten:
                ergebnis = _kauf_versuchen(
                    club, kandidaten, kauftyp='talent', params=params,
                    saison=saison, window_id=window_id, dry_run=dry_run,
                    spieltag=spieltag, budget_max=budget['ueberschuss'],
                    begruendung=(f'Talentkauf: Potential ≥ Kaderniveau '
                                 f'({kader_niveau:.1f}) + {pot_delta}.'),
                )
                if ergebnis['aktion'] is not None:
                    report['kaeufe'].append({'typ': 'talent', **ergebnis})
        return run
    finally:
        run.report = report
        run.save(update_fields=['report'])


def run_ai_buyer_matchday(league, *, saison, spieltag, trigger='spieltag'):
    """Prüflauf aller KI-Vereine einer Liga (Hook nach der Finanzrunde).

    Returns dict: {'laeufe': int, 'uebersprungen': int, 'governor': dict}.
    """
    from game.models import Club

    params = _params(saison)
    state = _season_state()
    expire_offers()

    governor = governor_status(saison, params)
    ergebnis = {'laeufe': 0, 'uebersprungen': 0, 'governor': {
        'anteil': str(governor['anteil']),
        'ueberschritten': governor['ueberschritten'],
    }}
    if governor['ueberschritten']:
        logger.warning(
            '[ALARM] KI-Käufer-Governor überschritten: %s > %s',
            governor['anteil'], governor['limit'],
        )

    if not state.transfer_window_open:
        return ergebnis

    soll = liga_soll(league)
    snapshot = ensure_season_snapshot(saison)
    clubs = (
        Club.objects
        .filter(league=league, managed_by__isnull=True,
                ai_buyer_paused=False)
        .select_related('stadium', 'league')
    )
    for club in clubs:
        run = run_club_pruflauf(
            club, saison=saison, spieltag=spieltag, trigger=trigger,
            params=params, state=state, soll=soll, snapshot=snapshot,
            governor=governor,
        )
        if run is None:
            ergebnis['uebersprungen'] += 1
        else:
            ergebnis['laeufe'] += 1
    return ergebnis
