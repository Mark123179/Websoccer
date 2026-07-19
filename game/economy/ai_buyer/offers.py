"""Angebotslogik des KI-Käufers (Spec Kap. 9.3) — Erstellung, Eskalation,
Annahme/Ablehnung, KI-zu-KI-Clearing, Ablauf & Storno.

Käufer-Maximum je Kauftyp (Bewertungssymmetrie, Schmerzgrenze v2):
  Bedarf   → volle Bewertung (Schmerzgrenze)
  Qualität → quali_faktor  × Bewertung (Standard 0,85)
  Talent   → talent_faktor × Zukunftswert (Standard 0,90)

Gebotstreppe an Manager-Vereine: 70 % → 90 % → 100 % des Maximums,
±STREUUNG deterministisch aus noise_seed + Stufe (SHA-256 — identisches
Muster wie negotiation._streuung_faktor), quantisiert auf 10.000 €.
Stufe 2 nur bei akutem Bedarf (Kauftyp 'bedarf'), Stufe 3 nur bei hoher
Dringlichkeit (kritische Tiefenlücke ⇒ luecken_score ≥ 10).

Sicherheit: bewertung/max_gebot/noise_seed verlassen NIE den Server —
Manager-Payloads bauen ausschließlich auf offer_manager_payload() auf.
"""
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..negotiation import _quantisiere, _streuung_faktor
from ..transfers import TransferError, execute_money_transfer


class AIBuyerError(Exception):
    """Fachlicher KI-Käufer-Fehler (deutsche Meldung für die UI)."""


# Anteil des Käufer-Maximums je Gebotsstufe (Parameter-Keys in KI_KAEUFER).
_STUFEN_KEYS = {1: 'eroeffnung', 2: 'nachbesserung', 3: 'final'}
_STUFEN_DEFAULTS = {1: Decimal('0.70'), 2: Decimal('0.90'), 3: Decimal('1.00')}

# Hohe Dringlichkeit = kritische Tiefenlücke (Score-Anteil 10).
HOHE_DRINGLICHKEIT_SCORE = Decimal('10')


def max_gebot_fuer(kauftyp, wertung, params):
    """Käufer-Maximum je Kauftyp aus der Schmerzgrenzen-Bewertung."""
    from game.models import AITransferOffer

    if kauftyp == AITransferOffer.KAUFTYP_QUALITAET:
        basis = wertung['schmerzgrenze'] * Decimal(
            str(params.get('quali_faktor', 0.85)))
    elif kauftyp == AITransferOffer.KAUFTYP_TALENT:
        basis = wertung['zukunftswert'] * Decimal(
            str(params.get('talent_faktor', 0.90)))
    else:
        basis = wertung['schmerzgrenze']
    return Decimal(basis).quantize(Decimal('0.01'))


def gebot_fuer_stufe(offer, stufe, params):
    """Gebot der Stufe: max_gebot × Stufenanteil × (1±Streuung), ≤ max_gebot."""
    anteil = Decimal(str(params.get(
        _STUFEN_KEYS[stufe], _STUFEN_DEFAULTS[stufe])))
    faktor = _streuung_faktor(
        offer.noise_seed, stufe, float(params.get('streuung', 0.05)),
    )
    gebot = offer.max_gebot * anteil * faktor
    gebot = min(gebot, offer.max_gebot)
    return _quantisiere(gebot, params.get('gebot_quantisierung', 10000))


def offer_manager_payload(offer):
    """Manager-sichtbare Felder — NIEMALS bewertung/max_gebot/noise_seed."""
    return {
        'id': offer.pk,
        'player_id': offer.player_id,
        'player_name': offer.player.full_name,
        'buyer_club_id': offer.buyer_club_id,
        'buyer_club_name': offer.buyer_club.name,
        'kauftyp': offer.kauftyp,
        'kauftyp_label': offer.get_kauftyp_display(),
        'aktuelles_gebot': str(offer.aktuelles_gebot or ''),
        'stufe': offer.stufe,
        'status': offer.status,
        'gueltig_bis': (
            timezone.localtime(offer.gueltig_bis).strftime('%d.%m.%Y %H:%M')
            if offer.gueltig_bis else ''
        ),
        'eskalation_moeglich': offer.status == 'versendet'
                               and _naechste_stufe(offer) is not None,
    }


def _naechste_stufe(offer):
    """Nächste zulässige Gebotsstufe oder None (Dringlichkeits-Gates)."""
    from game.models import AITransferOffer

    if offer.stufe >= 3:
        return None
    if offer.kauftyp != AITransferOffer.KAUFTYP_BEDARF:
        return None  # Nachbessern gibt es nur bei akutem Bedarf.
    if offer.stufe == 2:
        score = offer.luecken_score or Decimal('0')
        if score < HOHE_DRINGLICHKEIT_SCORE:
            return None  # Finales Angebot nur bei hoher Dringlichkeit.
    return offer.stufe + 1


def _manager_kadenz_ok(seller, window_id, params, *, dry_run):
    """Kadenz-Limits des EMPFÄNGERS: max. 2 offene / 4 je Fenster
    pro Manager-Verein (Postfach-Hygiene, Spec 9.3 „nie Spam").

    Im Trockenlauf zählen 'berechnet'-Angebote mit (realistische
    Simulation), im Scharfbetrieb nur wirklich versendete.
    """
    from game.models import AITransferOffer

    status = (AITransferOffer.OFFENE_STATUS if dry_run
              else (AITransferOffer.STATUS_VERSENDET,))
    offen = AITransferOffer.objects.filter(
        seller_club=seller, status__in=status,
    ).count()
    if offen >= int(params.get('max_offen_manager', 2)):
        return False
    im_fenster = AITransferOffer.objects.filter(
        seller_club=seller, window_id=window_id,
    ).exclude(status=AITransferOffer.STATUS_STORNIERT).count()
    return im_fenster < int(params.get('max_pro_fenster_manager', 4))


def create_offer(buyer, player, *, kauftyp, wertung, params, saison,
                 window_id, dry_run, luecken_score=None, begruendung=''):
    """Angebot berechnen und (außer im Trockenlauf) an den Manager senden.

    Idempotent je (buyer, player): ein offenes Angebot wird aktualisiert
    statt dupliziert (partieller Unique-Index unique_open_ai_transfer_offer).
    """
    from game.models import AITransferOffer

    max_gebot = max_gebot_fuer(kauftyp, wertung, params)
    if max_gebot <= 0:
        raise AIBuyerError('Käufer-Maximum ist 0 — kein Angebot möglich.')
    if player.club_id and player.club.managed_by_id is not None:
        if not _manager_kadenz_ok(player.club, window_id, params,
                                  dry_run=dry_run):
            raise AIBuyerError(
                'Kadenz-Limit des Manager-Vereins erreicht — kein weiteres '
                'Angebot in dieses Postfach.'
            )

    with transaction.atomic():
        offer = (
            AITransferOffer.objects.select_for_update()
            .filter(buyer_club=buyer, player=player,
                    status__in=AITransferOffer.OFFENE_STATUS)
            .first()
        )
        if offer is None:
            offer = AITransferOffer(
                buyer_club=buyer, player=player,
                noise_seed=secrets.token_hex(16),
            )
        offer.seller_club = player.club
        offer.kauftyp = kauftyp
        offer.bewertung = wertung['schmerzgrenze']
        offer.max_gebot = max_gebot
        offer.stufe = 1
        offer.dry_run = dry_run
        offer.window_id = window_id
        offer.luecken_score = luecken_score
        offer.begruendung = begruendung
        offer.aktuelles_gebot = gebot_fuer_stufe(offer, 1, params)
        if dry_run:
            offer.status = AITransferOffer.STATUS_BERECHNET
            offer.gueltig_bis = None
        else:
            offer.status = AITransferOffer.STATUS_VERSENDET
            offer.gueltig_bis = timezone.now() + timedelta(
                hours=int(params.get('gueltigkeit_stunden', 72)),
            )
        offer.save()
    return offer


def manager_annehmen(offer, *, saison=None, spieltag=None):
    """Manager nimmt das KI-Angebot an → Transfer zum aktuellen Gebot.

    Deckungslücke beim Käufer (InsufficientFunds/TransferError) storniert
    das Angebot sauber statt zu crashen.
    """
    from game.models import AITransferOffer

    from ..booking import InsufficientFunds

    with transaction.atomic():
        o = (AITransferOffer.objects.select_for_update()
             .select_related('player', 'buyer_club', 'seller_club')
             .get(pk=offer.pk))
        if o.status != AITransferOffer.STATUS_VERSENDET:
            raise AIBuyerError('Dieses Angebot ist nicht mehr offen.')
        if o.gueltig_bis and o.gueltig_bis < timezone.now():
            o.status = AITransferOffer.STATUS_ABGELAUFEN
            o.save(update_fields=['status', 'updated_at'])
            raise AIBuyerError('Dieses Angebot ist abgelaufen.')
        if o.player.club_id != o.seller_club_id:
            o.status = AITransferOffer.STATUS_STORNIERT
            o.begruendung += '\nStorno: Spieler hat den Verein verlassen.'
            o.save(update_fields=['status', 'begruendung', 'updated_at'])
            raise AIBuyerError('Der Spieler hat den Verein bereits verlassen.')

        try:
            transfer = execute_money_transfer(
                o.player, o.buyer_club, o.aktuelles_gebot,
                saison=saison, spieltag=spieltag,
            )
        except (InsufficientFunds, TransferError) as exc:
            o.status = AITransferOffer.STATUS_STORNIERT
            o.begruendung += f'\nStorno bei Annahme: {exc}'
            o.save(update_fields=['status', 'begruendung', 'updated_at'])
            raise AIBuyerError(
                'Der Transfer ist gescheitert — das Angebot wurde storniert.'
            )
        o.status = AITransferOffer.STATUS_DEAL
        o.save(update_fields=['status', 'updated_at'])
        return {'offer': o, 'transfer': transfer}


def manager_ablehnen(offer, *, params, saison=None):
    """Manager lehnt ab → KI prüft Dringlichkeit neu (Gebotstreppe).

    Bei zulässiger nächster Stufe wird nachgebessert (neues Gebot,
    Gültigkeit verlängert), sonst Rückzug + Cooldown je Kauftyp.
    """
    from game.models import AITransferOffer

    with transaction.atomic():
        o = (AITransferOffer.objects.select_for_update()
             .select_related('player', 'buyer_club')
             .get(pk=offer.pk))
        if o.status != AITransferOffer.STATUS_VERSENDET:
            raise AIBuyerError('Dieses Angebot ist nicht mehr offen.')

        naechste = _naechste_stufe(o)
        if naechste is not None:
            o.stufe = naechste
            o.aktuelles_gebot = gebot_fuer_stufe(o, naechste, params)
            o.gueltig_bis = timezone.now() + timedelta(
                hours=int(params.get('gueltigkeit_stunden', 72)),
            )
            o.save(update_fields=[
                'stufe', 'aktuelles_gebot', 'gueltig_bis', 'updated_at',
            ])
            return {'offer': o, 'ergebnis': 'nachgebessert'}

        cooldowns = params.get('cooldown_tage', {}) or {}
        tage = int(cooldowns.get(o.kauftyp, 0) or 0)
        o.status = AITransferOffer.STATUS_ABGELEHNT
        if tage > 0:
            o.cooldown_until = timezone.now() + timedelta(days=tage)
        o.save(update_fields=['status', 'cooldown_until', 'updated_at'])
        return {'offer': o, 'ergebnis': 'zurueckgezogen'}


def ki_zu_ki_clearing(buyer, kandidat, *, kauftyp, params, saison,
                      window_id, dry_run, spieltag=None,
                      luecken_score=None, begruendung=''):
    """Sofort-Clearing KI-zu-KI (kein Postfach): Deal, wenn Käufer-Max ≥
    Verkäufer-Forderung — Preis = Mittelwert beider Werte.

    kandidat: dict aus kandidaten.finde_kandidaten (player/wertung/forderung).
    Returns dict {'offer', 'ergebnis': 'deal'|'kein_deal'|'berechnet',
                  'preis': Decimal|None}.
    """
    from game.models import AITransferOffer

    from ..booking import InsufficientFunds

    player = kandidat['player']
    wertung = kandidat['wertung']
    forderung = kandidat['forderung']
    max_gebot = max_gebot_fuer(kauftyp, wertung, params)

    if max_gebot < forderung:
        return {'offer': None, 'ergebnis': 'kein_deal', 'preis': None}

    preis = _quantisiere(
        (max_gebot + forderung) / 2, params.get('gebot_quantisierung', 10000),
    )
    grund = (begruendung + f'\nKI-zu-KI-Clearing: Forderung '
             f'{forderung:.0f} €, Max {max_gebot:.0f} €, '
             f'Preis {preis:.0f} €.').strip()

    if dry_run:
        offer = create_offer(
            buyer, player, kauftyp=kauftyp, wertung=wertung, params=params,
            saison=saison, window_id=window_id, dry_run=True,
            luecken_score=luecken_score, begruendung=grund,
        )
        offer.aktuelles_gebot = preis
        offer.save(update_fields=['aktuelles_gebot', 'updated_at'])
        return {'offer': offer, 'ergebnis': 'berechnet', 'preis': preis}

    try:
        transfer = execute_money_transfer(
            player, buyer, preis, saison=saison, spieltag=spieltag,
        )
    except (InsufficientFunds, TransferError):
        return {'offer': None, 'ergebnis': 'kein_deal', 'preis': None}

    offer = AITransferOffer.objects.create(
        buyer_club=buyer, seller_club=offer_seller(transfer, player),
        player=player, kauftyp=kauftyp,
        bewertung=wertung['schmerzgrenze'], max_gebot=max_gebot,
        aktuelles_gebot=preis, stufe=1,
        status=AITransferOffer.STATUS_DEAL, dry_run=False,
        window_id=window_id, noise_seed=secrets.token_hex(16),
        luecken_score=luecken_score, begruendung=grund,
    )
    return {'offer': offer, 'ergebnis': 'deal', 'preis': preis}


def offer_seller(transfer, player):
    """Verkäuferverein eines abgewickelten Transfers (aus den Buchungen)."""
    for tx in transfer.get('transactions', []):
        if tx.typ == 'TRANSFER_EIN':
            return tx.club
    return player.club


def expire_offers(now=None):
    """Versendete Angebote mit abgelaufener Frist auf 'abgelaufen' setzen."""
    from game.models import AITransferOffer

    now = now or timezone.now()
    return (
        AITransferOffer.objects
        .filter(status=AITransferOffer.STATUS_VERSENDET,
                gueltig_bis__lt=now)
        .update(status=AITransferOffer.STATUS_ABGELAUFEN, updated_at=now)
    )


def storniere_offene_fuer_spieler(player, grund='Spieler hat den Verein gewechselt.'):
    """Alle offenen KI-Angebote auf einen Spieler stornieren.

    Wird bei JEDEM abgeschlossenen Vereinswechsel gerufen
    (transfers._complete_move) — Angebote an den Ex-Verein sind obsolet.
    """
    from game.models import AITransferOffer

    offene = AITransferOffer.objects.filter(
        player=player, status__in=AITransferOffer.OFFENE_STATUS,
    )
    n = 0
    for offer in offene:
        offer.status = AITransferOffer.STATUS_STORNIERT
        offer.begruendung = (offer.begruendung + f'\nStorno: {grund}').strip()
        offer.save(update_fields=['status', 'begruendung', 'updated_at'])
        n += 1
    return n
