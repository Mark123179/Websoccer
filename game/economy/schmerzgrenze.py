"""Schmerzgrenze v2 — Bewertungsservice managerloser Vereine (Spec Kap. 9.2).

    Schmerzgrenze = max(Gegenwartswert, Zukunftswert) [× Kernspieler-Zuschlag]

    Gegenwartswert = max(
        MW × Stärkefaktor × Altersfaktor,
        MW_Kurve(Stärke) × Restnutzwert(Alter)
    )
    Zukunftswert   = MW_Kurve(Potential) × Realisierung(Alter, Potential − Stärke)
                     — nur falls Potential > Potential-Median und Potential > Stärke

Datenbasis: SeasonEconomySnapshot (mw_kurve_json = Median-MW je
5er-Stärkeband, staerke_median, potential_median) + verborgene wahre Werte
(PlayerStrengthProfile.base_strength, Player.potential). Die Bewertung
wird NIE persistiert und darf NIE an Manager-Clients geleakt werden
(Ablehnung eines hohen Gebots ist selbst Scouting-Information).

Bewertungssymmetrie: Dieselbe Formel wird in Phase 6 für KI-Käufe
wiederverwendet — deshalb reiner, zustandsloser Service.

Konstanten: EconomyParameter SCHMERZGRENZE_KONSTANTEN (inkl. Restnutzwert-
Tabelle, Seed-Erweiterung Phase 4).
"""
from decimal import Decimal

from .params import get_decimal, get_param
from .snapshot import ensure_season_snapshot


def _kurve_stuetzstellen(kurve_json):
    """Sortierte (Stärkeband, Median-MW)-Stützstellen aus dem Snapshot."""
    pts = []
    for k, v in (kurve_json or {}).items():
        try:
            pts.append((float(int(k)), float(v)))
        except (TypeError, ValueError):
            continue
    return sorted(pts)


def kurve_wert(kurve_json, x):
    """MW_Kurve(x): linear interpoliert; oberhalb des höchsten Bands
    mit dem letzten positiven Gradienten extrapoliert (Pflicht für
    Potentiale weit über dem Datenbestand, z. B. 190)."""
    pts = _kurve_stuetzstellen(kurve_json)
    if not pts:
        return None
    x = float(x)
    if x <= pts[0][0]:
        return Decimal(str(pts[0][1]))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return Decimal(str(y0 + (y1 - y0) * (x - x0) / (x1 - x0)))
    # Extrapolation: Gradient der letzten beiden Stützstellen; ist er
    # nicht positiv (Band-Rauschen), Gesamtgradient; sonst konstant.
    grad = 0.0
    if len(pts) >= 2:
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        grad = (yb - ya) / (xb - xa) if xb > xa else 0.0
        if grad <= 0 and pts[-1][0] > pts[0][0]:
            grad = (pts[-1][1] - pts[0][1]) / (pts[-1][0] - pts[0][0])
    grad = max(grad, 0.0)
    return Decimal(str(pts[-1][1] + grad * (x - pts[-1][0])))


def _altersfaktor(age, konst):
    tabelle = konst['altersfaktor']
    if age <= 21:
        return Decimal(str(tabelle['u21']))
    if age <= 25:
        return Decimal(str(tabelle['22-25']))
    if age <= 29:
        return Decimal(str(tabelle['26-29']))
    return Decimal(str(tabelle['30+']))


def _restnutzwert(age, konst):
    tabelle = konst['restnutzwert']
    if age <= 25:
        return Decimal(str(tabelle['u26']))
    key = str(int(age))
    if key in tabelle:
        return Decimal(str(tabelle[key]))
    return Decimal(str(tabelle['36+']))


def _realisierung(age, luecke, konst):
    r = konst['realisierung']
    wert = (Decimal(str(r['basis']))
            - Decimal(str(luecke)) * Decimal(str(r['luecke_abzug']))
            - Decimal(max(age - 17, 0)) * Decimal(str(r['alter_abzug'])))
    return min(max(wert, Decimal(str(r['min']))), Decimal(str(r['max'])))


def _wahre_werte(player):
    """(Stärke, Potential) aus den verborgenen Feldern; None wenn kein Profil."""
    profil = getattr(player, 'strength_profile', None)
    if profil is None or profil.base_strength is None:
        return None, None
    return Decimal(str(profil.base_strength)), Decimal(str(player.potential or 0))


def ist_kernspieler(player, staerke=None):
    """Top-3 (wahre Stärke) des Kaders oder höchstes U21-Potential (Spec 9.2)."""
    from game.models import Player, PlayerStrengthProfile

    if player.club_id is None:
        return False

    top3 = list(
        PlayerStrengthProfile.objects
        .filter(player__club_id=player.club_id)
        .order_by('-base_strength')
        .values_list('player_id', flat=True)[:3]
    )
    if player.pk in top3:
        return True

    top_u21 = (
        Player.objects
        .filter(club_id=player.club_id, age__lte=21)
        .order_by('-potential', 'pk')
        .values_list('pk', flat=True)
        .first()
    )
    return top_u21 == player.pk


def bewertung(player, *, saison=None, snapshot=None):
    """Schmerzgrenze v2 des Spielers (Decimal, €) — oder None ohne Datenbasis.

    Returns dict:
      schmerzgrenze, gegenwartswert, zukunftswert, kernspieler (bool).
    Nie an Clients ausliefern — nur serverseitige Entscheidungsgrundlage.
    """
    from game.finance import current_sim_season

    saison = str(saison) if saison is not None else (current_sim_season() or '0')
    snap = snapshot or ensure_season_snapshot(saison)
    konst = get_param('SCHMERZGRENZE_KONSTANTEN', saison)

    staerke, potential = _wahre_werte(player)
    if staerke is None:
        return None

    mw = player.market_value
    mw = max(Decimal(str(mw)), get_decimal('MW_MINIMUM', saison)) \
        if mw is not None else get_decimal('MW_MINIMUM', saison)
    age = int(player.age)

    staerke_median = Decimal(str(snap.staerke_median)) \
        if snap.staerke_median is not None else staerke
    staerkefaktor = Decimal('1') + max(
        Decimal('0'), (staerke - staerke_median) / Decimal('50')
    )

    pfad1 = mw * staerkefaktor * _altersfaktor(age, konst)
    kurve_staerke = kurve_wert(snap.mw_kurve_json, staerke)
    pfad2 = (kurve_staerke * _restnutzwert(age, konst)) \
        if kurve_staerke is not None else Decimal('0')
    gegenwartswert = max(pfad1, pfad2)

    zukunftswert = Decimal('0')
    pot_median = Decimal(str(snap.potential_median)) \
        if snap.potential_median is not None else None
    if (pot_median is not None and potential > pot_median
            and potential > staerke):
        kurve_pot = kurve_wert(snap.mw_kurve_json, potential)
        if kurve_pot is not None:
            zukunftswert = kurve_pot * _realisierung(
                age, potential - staerke, konst,
            )

    grenze = max(gegenwartswert, zukunftswert)
    kern = ist_kernspieler(player, staerke)
    if kern:
        grenze *= Decimal(str(konst['kernspieler_zuschlag']))

    return {
        'schmerzgrenze': grenze.quantize(Decimal('0.01')),
        'gegenwartswert': gegenwartswert.quantize(Decimal('0.01')),
        'zukunftswert': zukunftswert.quantize(Decimal('0.01')),
        'kernspieler': kern,
    }
