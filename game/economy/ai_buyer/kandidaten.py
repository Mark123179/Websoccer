"""Kandidatensuche + Nutzen-Ranking des KI-Käufers (Spec Kap. 9.3).

Bewertungssymmetrie: Die KI kennt die wahren Werte ALLER Spieler und
nutzt dieselbe Bewertungsformel wie beim Verkauf (Schmerzgrenze v2).

Kandidatenregeln:
  · KI-Verkäufer (Club.managed_by IS NULL): alle Spieler erreichbar.
  · Manager-Vereine: NUR sale_visible_to_ai UND sale_category in
    (GELD, GELD_TAUSCH) — die KI tauscht nie (kein TAUSCH, kein UVK).
  · Vereinslose (Pool-)Spieler sind Scouting-Material, kein KI-Markt.
  · Mindestkader des Verkäufers respektieren, Cooldowns je (Käufer,
    Spieler) beachten (Talent-Cooldown = bis Fensterende via window_id).

Nutzen = (eigene Bewertung − erwartete Forderung) / Forderung.
Erwartete Forderung = Bewertung × 1,1–1,3 (deterministisch je Spieler
aus einem Seed — dieselbe Rechnung nutzt das KI-zu-KI-Clearing).
"""
import hashlib
from decimal import Decimal

from django.utils import timezone

from ..schmerzgrenze import bewertung, potential_200


def forderung_faktor(seed: str, player_id: int, params) -> Decimal:
    """Deterministischer Verkäufer-Forderungsfaktor in [min, max]."""
    fmin = Decimal(str(params.get('forderung_faktor_min', 1.1)))
    fmax = Decimal(str(params.get('forderung_faktor_max', 1.3)))
    digest = hashlib.sha256(f'{seed}:forderung:{player_id}'.encode()).hexdigest()
    anteil = Decimal(int(digest[:12], 16)) / Decimal(0xFFFFFFFFFFFF)
    return fmin + (fmax - fmin) * anteil


def erwartete_forderung(wertung, seed: str, player_id: int, params) -> Decimal:
    """Erwartete Verkäufer-Forderung = Schmerzgrenze × Faktor(1,1–1,3)."""
    faktor = forderung_faktor(seed, player_id, params)
    return (wertung['schmerzgrenze'] * faktor).quantize(Decimal('0.01'))


def _gesperrte_spieler_ids(buyer, window_id):
    """Spieler mit aktivem Cooldown oder offenem Angebot dieses Käufers."""
    from game.models import AITransferOffer

    jetzt = timezone.now()
    qs = AITransferOffer.objects.filter(buyer_club=buyer)
    offen = qs.filter(status__in=AITransferOffer.OFFENE_STATUS)
    cooldown = qs.filter(cooldown_until__gt=jetzt)
    talent = qs.filter(
        kauftyp=AITransferOffer.KAUFTYP_TALENT,
        status=AITransferOffer.STATUS_ABGELEHNT,
        window_id=window_id,
    )
    ids = set()
    for q in (offen, cooldown, talent):
        ids.update(q.values_list('player_id', flat=True))
    return ids


def _verkaeufer_ok(player, buyer, min_kader, kader_counts):
    """Verkäuferseitige Zulässigkeit (Kategorie-Gate + Mindestkader)."""
    club = player.club
    if club is None or club.pk == buyer.pk:
        return False
    if club.managed_by_id is not None:
        if not player.sale_visible_to_ai:
            return False
        if player.sale_category not in ('GELD', 'GELD_TAUSCH'):
            return False
    if kader_counts.get(club.pk, 0) - 1 < min_kader:
        return False
    return True


def _basis_queryset(buyer):
    from game.models import Player
    return (
        Player.objects
        .exclude(club=None)
        .exclude(club=buyer)
        .filter(strength_profile__isnull=False)
        .select_related('club', 'strength_profile')
        .prefetch_related('source_ratings')
    )


def _kader_counts(player_qs):
    """Kadergrößen aller betroffenen Verkäufervereine in einem Query."""
    from django.db.models import Count

    from game.models import Player
    club_ids = {p.club_id for p in player_qs}
    return dict(
        Player.objects.filter(club_id__in=club_ids)
        .values_list('club_id')
        .annotate(n=Count('id'))
        .values_list('club_id', 'n')
    )


def finde_kandidaten(buyer, *, kauftyp, params, saison, seed,
                     window_id='', position=None, min_staerke=None,
                     max_alter=None, min_potential=None, limit=25,
                     snapshot=None):
    """Kandidaten für einen Kauftyp, absteigend nach Nutzen sortiert.

    Args:
      kauftyp:      'bedarf' | 'qualitaet' | 'talent'
      position:     Slot-Code (HP-Pflicht) für Bedarf/Qualität
      min_staerke:  Mindest-Stärke (exklusiv bei Bedarf: > Beste-11-Spieler)
      max_alter:    Altersgrenze (Talentkauf)
      min_potential: Mindest-Potential (Talentkauf)

    Returns Liste von dicts:
      {'player', 'staerke', 'wertung', 'forderung', 'nutzen'}
    """
    from ..kader import min_squad_size

    qs = _basis_queryset(buyer)
    if position:
        from django.db.models import Q
        qs = qs.filter(
            Q(main_position_1=position) | Q(main_position_2=position)
            | Q(main_position_3=position)
        )
    if min_staerke is not None:
        qs = qs.filter(strength_profile__base_strength__gt=min_staerke)
    if max_alter is not None:
        qs = qs.filter(age__lte=max_alter)

    # min_potential ist auf der 200er-Skala (potential_200) und wird unten
    # in Python geprüft — das rohe DB-Feld `potential` (100er-Skala) dient
    # bei der Talentsuche nur als grobe Vorsortierung.
    if min_potential is not None:
        sortierung = '-potential'
    else:
        sortierung = '-strength_profile__base_strength'

    # Stärkste (bzw. potentialreichste) zuerst, Suchraum begrenzen.
    kandidaten = list(qs.order_by(sortierung)[:max(limit * 4, 100)])
    if not kandidaten:
        return []

    gesperrt = _gesperrte_spieler_ids(buyer, window_id)
    min_kader = min_squad_size(saison)
    counts = _kader_counts(kandidaten)

    ergebnis = []
    for player in kandidaten:
        if player.pk in gesperrt:
            continue
        if min_potential is not None:
            pot = potential_200(player)
            if pot is None or pot < Decimal(str(min_potential)):
                continue
        if not _verkaeufer_ok(player, buyer, min_kader, counts):
            continue
        wertung = bewertung(player, saison=saison, snapshot=snapshot)
        if wertung is None:
            continue
        forderung = erwartete_forderung(wertung, seed, player.pk, params)
        if forderung <= 0:
            continue
        nutzen = (wertung['schmerzgrenze'] - forderung) / forderung
        ergebnis.append({
            'player': player,
            'staerke': Decimal(str(player.strength_profile.base_strength)),
            'wertung': wertung,
            'forderung': forderung,
            'nutzen': nutzen,
        })
        if len(ergebnis) >= limit:
            break

    ergebnis.sort(key=lambda k: k['nutzen'], reverse=True)
    return ergebnis
