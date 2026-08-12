"""Jugendspielerabgabe v2 — Single Source of Truth (Master-Spec §5.6).

Regeln:
- Gesamtabgabe 8 % der Bemessungsgrundlage, verteilt auf die
  Ausbildungsvereine (aus PlayerClubHistory bis einschl. Saison des 21.
  Geburtstags — identischer Ausbildungszeitraum wie das Bestands-System).
- Mindestabgabe 50.000 € JE Ausbildungsverein (auch wenn die Prozente
  weniger ergäben).
- Eigengewächse (keine Fremd-Ausbildungsvereine): keine Abgabe.
- Leihen / Vereinslose: nie Abgabe (Aufrufer entscheidet das über die
  Bemessungsgrundlage bzw. ruft die Funktion gar nicht auf).
- Abzug direkt von der Ablöse des ABGEBENDEN Vereins.

`calc_youth_levy` ist die EINZIGE Berechnungsquelle: UI-Vorschau (Deal-
Sheet, Deal-Builder, "Auf TL stellen") und Buchung rufen dieselbe Funktion.
"""
from decimal import Decimal, ROUND_HALF_UP

from game.economy.params import get_decimal

CENT = Decimal('0.01')


def _q(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _saison_int(saison):
    from game.finance import current_sim_season
    s = str(saison) if saison is not None else (current_sim_season() or '0')
    try:
        return int(s), s
    except (TypeError, ValueError):
        return 0, s


def calc_youth_levy(player, bemessungsgrundlage, *, zahler_club=None, saison=None):
    """Berechnet die Jugendabgabe für EINEN abgegebenen Spieler.

    Args:
        player: der abgegebene Spieler.
        bemessungsgrundlage: Ablöse (Geldkauf) bzw. bei Tausch MW +
            anteiliges Geld (der Aufrufer liefert die fertige Basis; §5.6).
        zahler_club: der abgebende (zahlende) Verein — sein Eigenanteil in
            der Ausbildungshistorie wird nie erhoben. Default: player.club.
        saison: Sim-Saison-String (Default: aktuelle).

    Returns:
        dict:
            gesamt_pct: Decimal (z. B. 8.000),
            betraege_je_ausbildungsverein: {club_id: Decimal},
            summe: Decimal (tatsächlich zu zahlende Summe an Fremdvereine),
            anteile_gesamt: int, anteile_fremd: int.
    """
    from game.models import PlayerClubHistory

    if zahler_club is None:
        zahler_club = player.club

    pct = get_decimal('JUGENDABGABE_PCT', saison)  # 0.08
    min_je = get_decimal('JUGENDABGABE_MIN_JE_VEREIN', saison)  # 50000

    leer = {
        'gesamt_pct': (pct * Decimal('100')),
        'betraege_je_ausbildungsverein': {},
        'summe': Decimal('0.00'),
        'anteile_gesamt': 0,
        'anteile_fremd': 0,
    }

    basis = Decimal(str(bemessungsgrundlage))
    if basis <= 0:
        return leer

    saison_num, _ = _saison_int(saison)
    cutoff = saison_num + (21 - int(player.age))

    stationen = list(
        PlayerClubHistory.objects
        .filter(player=player, season__lte=cutoff)
        .values_list('club_id', flat=True)
    )
    n = len(stationen)
    if n == 0:
        return leer  # Keine Sim-Ausbildungshistorie → Eigengewächs, keine Abgabe.

    zahler_id = zahler_club.pk if zahler_club is not None else None
    counts = {}
    for club_id in stationen:
        if club_id == zahler_id:
            continue  # Eigenanteil des abgebenden Vereins wird nie erhoben.
        counts[club_id] = counts.get(club_id, 0) + 1

    if not counts:
        # Nur Eigenanteile → keine Fremd-Ausbildungsvereine → keine Abgabe.
        return {**leer, 'anteile_gesamt': n}

    abgabe_gesamt = pct * basis
    anteil_pro_station = abgabe_gesamt / n

    betraege = {}
    for club_id, cnt in counts.items():
        roh = anteil_pro_station * cnt
        # Mindestabgabe 50.000 € JE Ausbildungsverein.
        betrag = max(_q(roh), _q(min_je))
        betraege[club_id] = betrag

    summe = sum(betraege.values(), Decimal('0.00'))
    return {
        'gesamt_pct': (pct * Decimal('100')),
        'betraege_je_ausbildungsverein': betraege,
        'summe': _q(summe),
        'anteile_gesamt': n,
        'anteile_fremd': sum(counts.values()),
    }


def swap_bemessung(player, gegenseite_geld, anzahl_abgegeben):
    """Bemessungsgrundlage je abgegebenem Spieler beim Tausch (§5.6).

    = Marktwert + (Geldanteil der Gegenseite ÷ Anzahl abgegebener Spieler).
    Reiner Tausch (kein Geld) → nur Marktwert.
    """
    mw = Decimal(str(player.market_value or 0))
    if mw <= 0:
        from game.economy.params import get_decimal as _gd
        mw = _gd('MW_MINIMUM', None)
    geld = Decimal(str(gegenseite_geld or 0))
    n = max(int(anzahl_abgegeben or 1), 1)
    return _q(mw + (geld / n))
