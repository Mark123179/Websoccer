"""Stadionökonomie — Nachfrage, Unterhalt, Spieltagskosten, Umfeld (Spec Kap. 5).

Es gibt KEINEN gepflegten Fanbasis-Wert: Die Nachfrage wird pro Heimspiel
live berechnet (Kap. 5.1):

    Basisnachfrage = NACHFRAGE_KOEFF × KaderMW_Mio ^ NACHFRAGE_EXP
    Nachfrage      = Basis × Beliebtheitsfaktor × Gegnerfaktor × Preisfaktor
    Zuschauer      = min(Nachfrage, Kapazität)   — kategorieweise

Die Gesamtnachfrage verteilt sich anteilig auf die Kategorien (Steh/Sitz/
VIP) nach deren Kapazitätsanteil; jede Kategorie hat ihren eigenen
Preisfaktor (Referenzpreis / Preis)^PREIS_ELASTIZITAET, geklemmt 0,5–1,3,
und wird einzeln an der Kategorie-Kapazität gekappt.

Alle Regler leben in EconomyParameter (Seed-Migrationen 0120/0125) —
keine Code-Defaults für Balancing-Werte.
"""
from decimal import Decimal

from .params import get_decimal, get_param

KATEGORIEN = ('steh', 'sitz', 'vip')

_CAPACITY_ATTR = {
    'steh': 'capacity_standing',
    'sitz': 'capacity_seating',
    'vip':  'capacity_vip',
}
_PRICE_ATTR = {
    'steh': 'price_standing',
    'sitz': 'price_seating',
    'vip':  'price_vip',
}

# Stadionumfeld-Einrichtungen mit Ausbaustufen auf dem Stadium-Modell.
UMFELD_LEVEL_FELDER = ('nlz_level', 'medizin_level', 'training_level', 'office_level')


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ── Nachfragefaktoren (Kap. 5.1) ─────────────────────────────────────────────

def basisnachfrage(kader_mw_eur, saison: str | None = None) -> float:
    """NACHFRAGE_KOEFF × KaderMW_Mio ^ NACHFRAGE_EXP (KaderMW in Mio €)."""
    koeff = float(get_param('NACHFRAGE_KOEFF', saison))
    exp = float(get_param('NACHFRAGE_EXP', saison))
    mw_mio = float(kader_mw_eur) / 1_000_000.0
    if mw_mio <= 0:
        return 0.0
    return koeff * (mw_mio ** exp)


def beliebtheitsfaktor(fan_popularity: int) -> float:
    """Fanbeliebtheit 1–100 → Faktor 0,7–1,2 (linear)."""
    pop = _clamp(float(fan_popularity or 0), 1.0, 100.0)
    return 0.7 + (pop / 100.0) * 0.5


def _topspiel(club, opponent_club, saison, punktabstand: int) -> bool:
    """Punktabstand ≤ Schwelle in derselben Liga-Tabelle = Topspiel."""
    from game.models import LeagueStandings

    if not club.league_id or club.league_id != opponent_club.league_id:
        return False
    rows = {
        r.club_id: r
        for r in LeagueStandings.objects.filter(
            league_id=club.league_id,
            season=str(saison),
            club_id__in=[club.pk, opponent_club.pk],
        )
    }
    heim, gast = rows.get(club.pk), rows.get(opponent_club.pk)
    if heim is None or gast is None:
        return False
    if heim.played == 0 and gast.played == 0:
        return False
    return abs(heim.points - gast.points) <= punktabstand


def _derby(club, opponent_club) -> bool:
    """Derby-Ableitung: gleiche Stadionstadt (kein gepflegtes Derby-Feld)."""
    try:
        heim_stadt = (club.stadium.city or '').strip().casefold()
        gast_stadt = (opponent_club.stadium.city or '').strip().casefold()
    except Exception:
        return False
    return bool(heim_stadt) and heim_stadt == gast_stadt


def gegnerfaktor(club, opponent_club=None, opponent_strength=None,
                 is_pokal_ko: bool = False, saison: str | None = None) -> float:
    """Gegner-Attraktivität 0,85–1,3 (Kap. 5.1).

    Mit ``opponent_club``: Basis aus dem Kader-MW-Verhältnis (Gegner/Heim,
    Verhältnis 0–2 linear auf mw_min–mw_max), plus additive Zuschläge für
    Topspiel (Punktabstand ≤ Schwelle), Pokal-K.o. und Derby; Gesamtklemme.

    Fallbacks: nur ``opponent_strength`` (0–100) → linear mw_min–mw_max;
    ganz ohne Kontext → neutral 1,0 (+ Pokal-Zuschlag, falls gesetzt).
    """
    p = get_param('GEGNERFAKTOR', saison)
    mw_min, mw_max = float(p['mw_min']), float(p['mw_max'])

    if opponent_club is not None:
        from .sponsors import kader_marktwert
        heim_mw = float(kader_marktwert(club))
        gast_mw = float(kader_marktwert(opponent_club))
        if heim_mw > 0:
            ratio = _clamp(gast_mw / heim_mw, 0.0, 2.0)
            faktor = mw_min + (mw_max - mw_min) * (ratio / 2.0)
        else:
            faktor = 1.0
        if _topspiel(club, opponent_club, saison or _saison(), int(p['topspiel_punktabstand'])):
            faktor += float(p['topspiel'])
        if _derby(club, opponent_club):
            faktor += float(p['derby'])
    elif opponent_strength is not None:
        anteil = _clamp(float(opponent_strength), 0.0, 100.0) / 100.0
        faktor = mw_min + (mw_max - mw_min) * anteil
    else:
        faktor = 1.0

    if is_pokal_ko:
        faktor += float(p['pokal'])

    return _clamp(faktor, float(p['min']), float(p['max']))


def preisfaktor(preis, referenzpreis, saison: str | None = None) -> float:
    """(Referenzpreis / Preis)^PREIS_ELASTIZITAET, geklemmt 0,5–1,3."""
    elastizitaet = float(get_param('PREIS_ELASTIZITAET', saison))
    preis = float(preis)
    referenzpreis = float(referenzpreis)
    if preis <= 0:
        return 1.3  # Freikarten → maximale Nachfrage (obere Klemme)
    return _clamp((referenzpreis / preis) ** elastizitaet, 0.5, 1.3)


def _saison() -> str:
    from .params import current_season
    return current_season()


def compute_demand(club, stadium, *, opponent_club=None, opponent_strength=None,
                   is_pokal_ko: bool = False, saison: str | None = None) -> dict:
    """Volle Nachfrageberechnung für ein Heimspiel (Kap. 5.1).

    Rückgabe: Faktoren + je Kategorie Kapazität/Preis/Preisfaktor/Nachfrage/
    Zuschauer/Einnahmen sowie Gesamtwerte und Auslastung in Prozent.
    """
    from .sponsors import kader_marktwert

    referenz = get_param('PREIS_REFERENZ', saison)

    basis = basisnachfrage(kader_marktwert(club), saison)
    beliebtheit = beliebtheitsfaktor(club.fan_popularity)
    gegner = gegnerfaktor(
        club, opponent_club=opponent_club, opponent_strength=opponent_strength,
        is_pokal_ko=is_pokal_ko, saison=saison,
    )
    nachfrage_gesamt = basis * beliebtheit * gegner

    kapazitaet_gesamt = stadium.capacity_total
    kategorien = {}
    zuschauer_gesamt = 0
    einnahmen_gesamt = Decimal('0.00')

    for kat in KATEGORIEN:
        kapazitaet = getattr(stadium, _CAPACITY_ATTR[kat])
        preis = getattr(stadium, _PRICE_ATTR[kat])
        anteil = (kapazitaet / kapazitaet_gesamt) if kapazitaet_gesamt else 0.0
        pf = preisfaktor(preis, referenz[kat], saison)
        nachfrage = nachfrage_gesamt * anteil * pf
        zuschauer = min(int(nachfrage), kapazitaet)
        einnahmen = (Decimal(zuschauer) * Decimal(preis)).quantize(Decimal('0.01'))
        kategorien[kat] = {
            'kapazitaet': kapazitaet,
            'preis': Decimal(preis),
            'preisfaktor': pf,
            'nachfrage': nachfrage,
            'zuschauer': zuschauer,
            'einnahmen': einnahmen,
        }
        zuschauer_gesamt += zuschauer
        einnahmen_gesamt += einnahmen

    auslastung_pct = (
        round(zuschauer_gesamt / kapazitaet_gesamt * 100.0, 1)
        if kapazitaet_gesamt else 0.0
    )

    return {
        'basis': basis,
        'beliebtheit': beliebtheit,
        'gegner': gegner,
        'kategorien': kategorien,
        'zuschauer_gesamt': zuschauer_gesamt,
        'einnahmen_gesamt': einnahmen_gesamt,
        'auslastung_pct': auslastung_pct,
    }


# ── Laufende Stadionkosten (Kap. 5.4) ────────────────────────────────────────

def unterhalt_rate(stadium, saison: str | None = None) -> Decimal:
    """Unterhalt = Kapazität × UNTERHALT_PLATZ pro Saison, anteilig je
    Spieltag (gleiches Spieltagsraster wie Gehälter: GEHALT_DIVISOR)."""
    platz = get_decimal('UNTERHALT_PLATZ', saison)
    divisor = get_decimal('GEHALT_DIVISOR', saison)
    return (Decimal(stadium.capacity_total) * platz / divisor).quantize(Decimal('0.01'))


def spieltagskosten(zuschauer: int, saison: str | None = None) -> Decimal:
    """Spieltagskosten = Zuschauer × KOSTEN_BESUCHER je Heimspiel."""
    satz = get_decimal('KOSTEN_BESUCHER', saison)
    return (Decimal(int(zuschauer)) * satz).quantize(Decimal('0.01'))


# ── Stadionausbau: Bauzeit & Fertigstellung (Kap. 5.3) ───────────────────────

# Tribüne+Platztyp → Stadium-Kapazitätsfeld (für die Fertigstellung).
EXPANSION_FELD_MAP = {
    ('NORD', 'STEH'): 'nord_standing',
    ('NORD', 'SITZ'): 'nord_seating',
    ('NORD', 'VIP'):  'nord_vip',
    ('OST',  'STEH'): 'ost_standing',
    ('OST',  'SITZ'): 'ost_seating',
    ('OST',  'VIP'):  'ost_vip',
    ('SUED', 'STEH'): 'sued_standing',
    ('SUED', 'SITZ'): 'sued_seating',
    ('SUED', 'VIP'):  'sued_vip',
    ('WEST', 'STEH'): 'west_standing',
    ('WEST', 'SITZ'): 'west_seating',
    ('WEST', 'VIP'):  'west_vip',
}

# Bauzeit-Raster (Kap. 5.3): 1 Saison pro 15.000 Plätze. Eine "Saison"
# entspricht im Wanduhr-Raster der Einrichtungs-Bauzeiten (FACILITY_DATA,
# max. 7 Tage je Vollausbau-Stufe) 7 Bautagen. Strukturkonstante wie
# FACILITY_DATA — kein Balancing-Regler.
BAUZEIT_SAISON_PLAETZE = 15_000
BAUZEIT_TAGE_PRO_SAISON = 7


def expansion_bauzeit_tage(anzahl: int) -> int:
    """Wanduhr-Bautage eines Ausbaus (aufgerundet, min. 1 Tag)."""
    import math
    if anzahl <= 0:
        return 0
    return max(1, math.ceil(anzahl * BAUZEIT_TAGE_PRO_SAISON / BAUZEIT_SAISON_PLAETZE))


def pending_expansion_seats(stadium) -> int:
    """Bestellte, aber noch nicht fertiggestellte Plätze."""
    from django.db.models import Sum
    from game.models import StadiumExpansion

    return (
        StadiumExpansion.objects
        .filter(stadium=stadium, applied=False)
        .aggregate(s=Sum('seats_added'))['s']
        or 0
    )


def resolve_due_expansions(stadium) -> int:
    """Wendet fällige Stadionausbauten an (Wanduhr-Bauzeit abgelaufen).

    Idempotent + rennsicher: jeder Auftrag wird per bedingtem UPDATE
    „geclaimt" (applied False → True); die Kapazität wird per F()-Ausdruck
    erhöht (Muster: resolve_due_constructions). Gibt die Zahl der
    angewendeten Aufträge zurück und refresht die übergebene Instanz.
    """
    from django.db import transaction
    from django.db.models import F
    from django.utils import timezone
    from game.models import Stadium, StadiumExpansion

    if stadium is None:
        return 0

    due = StadiumExpansion.objects.filter(
        stadium=stadium,
        applied=False,
        completes_at__lte=timezone.now(),
    )
    angewendet = 0
    for e in due:
        feld = EXPANSION_FELD_MAP.get((e.stand, e.seat_type))
        if feld is None:
            continue
        with transaction.atomic():
            claimed = StadiumExpansion.objects.filter(
                pk=e.pk, applied=False,
            ).update(applied=True)
            if not claimed:
                continue
            Stadium.objects.filter(pk=stadium.pk).update(
                **{feld: F(feld) + e.seats_added},
            )
            angewendet += 1
    if angewendet:
        stadium.refresh_from_db()
    return angewendet


# ── Stadionumfeld-Zusatzeinnahme (Kap. 5.4) ──────────────────────────────────

def umfeld_stufen(stadium) -> int:
    """Summe der Ausbaustufen aller Umfeld-Einrichtungen des Stadions."""
    return sum(int(getattr(stadium, feld) or 0) for feld in UMFELD_LEVEL_FELDER)


def umfeld_einnahme(stadium, zuschauer: int, saison: str | None = None) -> Decimal:
    """Zusatzeinnahme €/Besucher: Stufensumme × UMFELD_EURO_BESUCHER_JE_STUFE
    × Zuschauer — dockt an dieselbe Zuschauerzahl an wie die Tickets."""
    stufen = umfeld_stufen(stadium)
    if stufen <= 0 or zuschauer <= 0:
        return Decimal('0.00')
    satz = get_decimal('UMFELD_EURO_BESUCHER_JE_STUFE', saison)
    return (Decimal(stufen) * satz * Decimal(int(zuschauer))).quantize(Decimal('0.01'))
