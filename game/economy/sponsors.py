"""Sponsorsystem V2 (Spec Kap. 6) — 5 Slots, Verhandlung, SponsorContract.

Sponsorwert je Slot (6.1 V2):
    Slot-Wert = Gesamt-Sponsorwert × SPONSOR_SLOT_WEIGHTS[slot]
    Gesamt-Sponsorwert wie bisher: Sockel + MW-Anteil + Platzbonus

Jahresangebote (6.2 V2): N Angebote je Slot (SPONSOR_OFFERS_PER_SLOT),
generiert mit Sponsor-Pool (Modell Sponsor) oder fiktiven Namen.
fix_start = Startwert; fix_aktuell = nach Verhandlungsrunden.

Verhandlung (push_offer):
  Jede Runde: deterministischer Risiko-Roll (SHA-256-Seed, anti-Reload).
  Gewinn: fix_aktuell += fix_start * GAINS[runde].
  Pech (RISK_MODE='malus'): fix_aktuell -= fix_start * RISKS[runde].
  Pech (RISK_MODE='verlust'): Angebot zurückgezogen (status='abgesagt').

Buchungspfade:
  Fixanteil: per Spieltag aus SponsorContract.fix_saison (matchday_run).
  Sieggeld: nach jedem Ligasieg (matchday_run, Ref: fixture.pk).
  Zuschauer: nach Ticket-Booking (matchday_run, Ref: offer.pk).
  Zieljäger: am Saisonende via finance_season_close.

Rückwärtskompatibilität: V1-Pfad (SponsorOffer.gewaehlt, generate_offers,
get_active_offer, book_sieg_bonus, book_zuschauer_bonus,
book_zieljaeger_bonus, sponsor_fix_rate) bleibt vollständig erhalten.
"""
import hashlib
import random
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .params import get_param

# ── Slot-Konstanten ───────────────────────────────────────────────────────────

SLOTS = ['haupt', 'trikot', 'ausruester', 'stadion', 'tv']

SLOT_LABELS = {
    'haupt': 'Hauptsponsor',
    'trikot': 'Trikotsponsor',
    'ausruester': 'Ausrüster',
    'stadion': 'Stadionpartner',
    'tv': 'TV- & Medienpartner',
}

SLOT_TO_BEREICH = {
    'haupt': 'hauptsponsor',
    'trikot': 'trikotsponsor',
    'ausruester': 'ausruester',
    'stadion': 'stadionpartner',
    'tv': 'tv_medien',
}

EINHEIT_SIEG = 'sieg'
EINHEIT_TOR = 'tor'
EINHEIT_BESUCHER = 'besucher'
EINHEIT_ZIEL = 'ziel'

# Fiktive Sponsornamen-Pools je Typ (deterministische Auswahl per Seed).
_NAMEN = {
    'sicherheit': ['NordBank Gruppe', 'Aurora Versicherung', 'Continentale Energie',
                   'ProSecura AG', 'Helvetia Kapital'],
    'sieggeld': ['VictoryBet Sports', 'Adrenalin Drinks', 'TurboOil Motorsport',
                 'Sprint Telekom', 'PowerPlay Media'],
    'torgeld': ['GoalLine Sports', 'Tor-Energie GmbH', 'NetBuster Media',
                'Schusskraft AG', 'Stürmer Finance'],
    'zieljaeger': ['Zenith Automobile', 'Falcon Airways', 'Titan Industrie',
                   'Apex Consulting', 'Meridian Tech'],
    'zuschauer': ['StadionBräu Brauerei', 'FanFood Catering', 'Arena Mobility',
                  'CityTrans Verkehr', 'Tribüne Textil'],
}

# ── Zieljäger: Ziel-Tier → P(Ziel) Kalibrierungstabelle (SPEC §4) ─────────
# Fallback-Tier-Map für Umgebungen ohne EconomyParameter-Seed
_GOAL_TIER_PROB_FALLBACK: dict[str, float] = {
    'meister':          0.08,
    'top2':             0.14,
    'top4':             0.22,
    'top6':             0.34,
    'top_half':         0.50,
    'mittelfeld':       0.50,
    'klassenerhalt':    0.65,
    'avoid_relegation': 0.65,
    'aufstieg':         0.30,
    'abstieg_kampf':    0.55,
}
_DEFAULT_ZIEL_WKT = Decimal('0.35')


def _ziel_wkt_from_goal_tier(club, saison: str) -> Decimal:
    """P(Ziel) aus SeasonGoal.goal_tier.

    Liest SPEC-konforme Tier-Map aus EconomyParameter SPONSOR_ZIEL_PROB (dict);
    Fallback: _GOAL_TIER_PROB_FALLBACK. var_ziel = exaktes goal_tier aus SeasonGoal.
    """
    try:
        from game.models import SeasonGoal
        goal = SeasonGoal.objects.filter(
            club=club, season_number=int(saison),
        ).first()
        if goal and goal.goal_tier:
            # Tier-Map aus EconomyParameter (SPEC: SPONSOR_ZIEL_PROB ist ein dict)
            try:
                tier_map = get_param('SPONSOR_ZIEL_PROB', saison)
                if isinstance(tier_map, dict) and goal.goal_tier in tier_map:
                    return Decimal(str(tier_map[goal.goal_tier]))
            except Exception:
                pass
            # Fallback auf hardcoded Map
            if goal.goal_tier in _GOAL_TIER_PROB_FALLBACK:
                return Decimal(str(_GOAL_TIER_PROB_FALLBACK[goal.goal_tier]))
    except Exception:
        pass
    return _DEFAULT_ZIEL_WKT

# Fiktive Slot-Namens-Pools (V2) für Slots ohne DB-Sponsor
_NAMEN_V2 = {
    'haupt':      ['NordBank Gruppe', 'Zenith Automobile', 'Titan Industrie',
                   'Aurora Versicherung', 'Meridian Tech', 'Apex Consulting',
                   'VictoryBet Sports', 'Sprint Telekom'],
    'trikot':     ['Adrenalin Drinks', 'TurboOil Motorsport', 'PowerPlay Media',
                   'FanFood Catering', 'SportStyle GmbH', 'ProSecura AG'],
    'ausruester': ['Tribüne Textil', 'KickGear AG', 'SportBase GmbH',
                   'AthletiCo', 'FootWear Pro'],
    'stadion':    ['StadionBräu Brauerei', 'Arena Mobility', 'CityTrans Verkehr',
                   'Helvetia Kapital', 'UrbanPark GmbH'],
    'tv':         ['Continentale Energie', 'BroadVision TV', 'MediaPlus AG',
                   'StreamNet', 'FanChannel GmbH'],
}


# ── Sponsorwert (6.1) — V1 + V2 ──────────────────────────────────────────────

def kader_marktwert(club) -> Decimal:
    """Summe der Marktwerte aller Kaderspieler (NULL zählt nicht mit)."""
    from django.db.models import Sum
    from game.models import Player

    total = (
        Player.objects.filter(club=club)
        .aggregate(s=Sum('market_value'))['s']
    )
    return Decimal(total or 0)


def _liga_level_key(club) -> str:
    level = int(getattr(club.league, 'level', 1) or 1) if club.league_id else 2
    return 'liga1' if level <= 1 else 'liga2'


def _vorsaison_platz(club, saison: str) -> tuple[int, int]:
    """(Platz, Ligagröße) der Vorsaison; Fallback: projizierter Rang."""
    from game.models import LeagueStandings

    if saison.lstrip('-').isdigit():
        vorsaison = str(int(saison) - 1)
        standing = (
            LeagueStandings.objects
            .filter(club=club, season=vorsaison, position__gt=0)
            .select_related('league')
            .first()
        )
        if standing is not None:
            n = LeagueStandings.objects.filter(
                league=standing.league, season=vorsaison,
            ).count()
            return standing.position, max(n, 2)

    from game.season_goals import project_goal_for_club
    p = project_goal_for_club(club)
    return p['rank_in_league'], max(p['league_size'], 2)


def platzbonus(club, saison: str) -> Decimal:
    """Platzbonus(Vorsaison): Maximalbonus für Platz 1, linear bis 0."""
    if not club.league_id:
        return Decimal('0.00')
    maximum = Decimal(str(get_param('SPONSOR_PLATZBONUS_MAX', saison)))
    platz, n = _vorsaison_platz(club, saison)
    anteil = Decimal(max(0, n - platz)) / Decimal(n - 1)
    return (maximum * anteil).quantize(Decimal('0.01'))


def sponsorwert(club, saison: str) -> Decimal:
    """Gesamt-Sponsorwert (Spec 6.1)."""
    sockel = Decimal(str(get_param('SPONSOR_SOCKEL', saison)[_liga_level_key(club)]))
    mw_anteil = Decimal(str(get_param('SPONSOR_MW_ANTEIL', saison)))
    return (
        sockel + mw_anteil * kader_marktwert(club) + platzbonus(club, saison)
    ).quantize(Decimal('0.01'))


def sponsorwert_slot(club, saison: str, slot: str) -> int:
    """Sponsorwert für einen Slot in € (ganze Euros) — SPONSOR_SLOT_WEIGHTS."""
    weights = get_param('SPONSOR_SLOT_WEIGHTS', saison)
    weight = Decimal(str(weights.get(slot, 0.20)))
    return int((sponsorwert(club, saison) * weight).to_integral_value())


# ── Präsidenten-Erwartung (V1, für V2 weiterhin genutzt) ─────────────────────

def _liga_spieltage(club, saison: str) -> tuple[int, int]:
    """(Spieltage gesamt, Heimspiele) aus dem Spielplan der Vereinsliga."""
    from .tv import league_clubs_and_matchdays

    if not club.league_id:
        return 34, 17
    club_ids, max_md = league_clubs_and_matchdays(club.league, saison)
    n = len(club_ids) or 18
    heimspiele = max(1, max_md // 2 if max_md > 1 else n - 1)
    return max(max_md, 1), heimspiele


def erwartete_siege(club, saison: str) -> Decimal:
    """Erwartete Ligasiege aus dem Kaderstärken-Rang interpoliert."""
    from game.season_goals import project_goal_for_club

    quoten = get_param('SPONSOR_ERWARTETE_SIEGE', saison)
    top = Decimal(str(quoten['platz1']))
    bottom = Decimal(str(quoten['letzter']))

    p = project_goal_for_club(club)
    n = max(p['league_size'], 2)
    rang = min(max(p['rank_in_league'], 1), n)
    quote = top - (top - bottom) * Decimal(rang - 1) / Decimal(n - 1)

    spieltage, _ = _liga_spieltage(club, saison)
    return (quote * spieltage).quantize(Decimal('0.01'))


def erwartete_besucher(club, saison: str) -> Decimal:
    """Erwartete Saison-Gesamtbesucher der Liga-Heimspiele."""
    from .stadium import compute_demand

    try:
        stadium = club.stadium
    except Exception:
        return Decimal('0.00')

    demand = compute_demand(club, stadium, saison=saison)
    _, heimspiele = _liga_spieltage(club, saison)
    return (Decimal(demand['zuschauer_gesamt']) * heimspiele)\
        .quantize(Decimal('0.01'))


def erwartete_tore(club, saison: str) -> Decimal:
    """Erwartete eigene Pflichtspieltore (stärkebasiert, SPEC §4 Torgeld).

    Schätzung: Kaderstärke-Rang → Tore/Spiel × Spieltage.
    Kalibrierung: Stärke 70 ≈ 1.4 Tore/Spiel (Bundesliga-Niveau).
    """
    try:
        from game.season_goals import project_goal_for_club
        p = project_goal_for_club(club)
        spieltage, _ = _liga_spieltage(club, saison)
        n = max(p['league_size'], 2)
        rang = min(max(p['rank_in_league'], 1), n)
        # Top-Verein (Rang 1) ≈ 2.2 Tore/Spiel; Letzter ≈ 0.8 Tore/Spiel
        tore_pro_spiel = Decimal('2.2') - Decimal('1.4') * Decimal(rang - 1) / Decimal(n - 1)
        tore_pro_spiel = max(Decimal('0.5'), tore_pro_spiel)
        return (tore_pro_spiel * Decimal(spieltage)).quantize(Decimal('0.1'))
    except Exception:
        return Decimal('48')  # Bundesliga-Fallback


# ── V1-Angebotsgenerator (bleibt für Backward-Compat) ────────────────────────

def generate_offers(club, saison: str) -> list:
    """V1: Erzeugt 3–5 Jahresangebote (idempotent, status='legacy').

    Bleibt als Rückwärtskompatibilitäts-Pfad für die finance_season_open
    (bis zum vollständigen Rollout von V2).
    """
    from game.models import SponsorOffer

    saison = str(saison)
    vorhandene = list(
        SponsorOffer.objects.filter(club=club, saison=saison, status='legacy')
    )
    if vorhandene:
        return vorhandene

    rng = random.Random(f'sponsor:{club.pk}:{saison}')
    anzahl_cfg = get_param('SPONSOR_ANGEBOTE_ANZAHL', saison)
    anzahl = rng.randint(int(anzahl_cfg['min']), int(anzahl_cfg['max']))

    typen = ['sicherheit']
    andere = ['sieggeld', 'zieljaeger', 'zuschauer']
    rng.shuffle(andere)
    typen += andere[:max(0, anzahl - 1)]
    while len(typen) < anzahl:
        typen.append(rng.choice(andere))

    wert = sponsorwert(club, saison)
    streuung = float(get_param('SPONSOR_STREUUNG', saison))
    splits = get_param('SPONSOR_TYP_SPLIT', saison)
    ziel_wkt = Decimal(str(get_param('SPONSOR_ZIEL_WAHRSCHEINLICHKEIT', saison)))

    e_siege = None
    e_besucher = None

    offers = []
    namen_verbraucht = set()
    for typ in typen:
        ew = (wert * Decimal(str(1 + rng.uniform(-streuung, streuung))))\
            .quantize(Decimal('0.01'))
        split = Decimal(str(splits[typ]))
        fix = (ew * split).quantize(Decimal('0.01'))
        var_ew = ew - fix

        variable = {}
        if typ == 'sieggeld':
            if e_siege is None:
                e_siege = erwartete_siege(club, saison)
            einzel = (var_ew / e_siege).quantize(Decimal('0.01')) \
                if e_siege > 0 else Decimal('0.00')
            variable = {
                'einheit': EINHEIT_SIEG,
                'betrag': str(einzel),
                'erwartete_events': str(e_siege),
            }
        elif typ == 'zuschauer':
            if e_besucher is None:
                e_besucher = erwartete_besucher(club, saison)
            einzel = (var_ew / e_besucher).quantize(Decimal('0.0001')) \
                if e_besucher > 0 else Decimal('0.0000')
            variable = {
                'einheit': EINHEIT_BESUCHER,
                'betrag': str(einzel),
                'erwartete_events': str(e_besucher),
            }
        elif typ == 'zieljaeger':
            bonus = (var_ew / ziel_wkt).quantize(Decimal('0.01')) \
                if ziel_wkt > 0 else Decimal('0.00')
            from game.season_goals import project_goal_for_club
            p = project_goal_for_club(club)
            variable = {
                'einheit': EINHEIT_ZIEL,
                'betrag': str(bonus),
                'erwartete_events': str(ziel_wkt),
                'ziel_label': p['goal_tier_label'],
            }

        pool = [n for n in _NAMEN[typ] if n not in namen_verbraucht] or _NAMEN[typ]
        name = rng.choice(pool)
        namen_verbraucht.add(name)

        offers.append(SponsorOffer(
            club=club, saison=saison, typ=typ, sponsor_name=name,
            fix_betrag=fix, variable_json=variable, erwartungswert=ew,
            status='legacy',
        ))

    from game.models import SponsorOffer as _SO
    _SO.objects.bulk_create(offers)
    return list(_SO.objects.filter(club=club, saison=saison, status='legacy'))


# ── V2-Angebotsgenerator (slot-aware) ────────────────────────────────────────

def _pick_sponsor(slot: str, saison: str, rng: random.Random,
                  used_slugs: set):
    """Wählt einen aktiven Sponsor aus dem DB-Pool für den Slot."""
    from game.models import Sponsor

    bereich = SLOT_TO_BEREICH.get(slot, 'hauptsponsor')
    pool = list(
        Sponsor.objects.filter(bereich=bereich, aktiv=True)
        .exclude(slug__in=used_slugs)
        .values_list('id', 'slug', 'name')
    )
    if not pool:
        pool = list(
            Sponsor.objects.filter(bereich=bereich, aktiv=True)
            .values_list('id', 'slug', 'name')
        )
    if pool:
        pk, slug, name = rng.choice(pool)
        return pk, name
    return None, None


def _build_v2_offer(club, saison: str, slot: str, typ: str, wert_slot: int,
                    rng: random.Random, streuung: float, splits: dict,
                    ziel_wkt: Decimal, e_siege, e_besucher, e_tore,
                    sponsor_id, sponsor_name: str) -> 'SponsorOffer':
    """Baut ein einzelnes SponsorOffer-Objekt (V2, status='offen')."""
    from game.models import SponsorOffer

    factor = Decimal(str(1 + rng.uniform(-streuung, streuung)))
    ew_euros = int((Decimal(wert_slot) * factor).to_integral_value())
    split_ratio = Decimal(str(splits[typ]))
    fix_euros = int((Decimal(ew_euros) * split_ratio).to_integral_value())
    var_ew_euros = ew_euros - fix_euros

    var_rate_cent = 0
    var_ziel = ''
    variable_json = {}

    if typ == 'sieggeld':
        if e_siege is None or e_siege <= 0:
            e_siege = Decimal('10')
        einzel = Decimal(var_ew_euros) / e_siege
        var_rate_cent = max(0, int(einzel * 100))
        variable_json = {
            'einheit': EINHEIT_SIEG,
            'betrag': str(einzel.quantize(Decimal('0.01'))),
            'erwartete_events': str(e_siege),
        }
    elif typ == 'torgeld':
        if e_tore is None or e_tore <= 0:
            e_tore = Decimal('48')
        einzel = Decimal(var_ew_euros) / e_tore
        var_rate_cent = max(0, int(einzel * 100))
        variable_json = {
            'einheit': EINHEIT_TOR,
            'betrag': str(einzel.quantize(Decimal('0.01'))),
            'erwartete_events': str(e_tore),
        }
    elif typ == 'zuschauer':
        if e_besucher is None or e_besucher <= 0:
            e_besucher = Decimal('1000')
        einzel = Decimal(var_ew_euros) / e_besucher
        var_rate_cent = max(0, int(einzel * 10000))
        variable_json = {
            'einheit': EINHEIT_BESUCHER,
            'betrag': str(einzel.quantize(Decimal('0.0001'))),
            'erwartete_events': str(e_besucher),
        }
    elif typ == 'zieljaeger':
        try:
            from game.season_goals import project_goal_for_club
            p = project_goal_for_club(club)
            var_ziel = p.get('goal_tier', '')
            ziel_label = p.get('goal_tier_label', 'Saisonziel')
        except Exception:
            var_ziel = ''
            ziel_label = 'Saisonziel'
        bonus = int(Decimal(var_ew_euros) / ziel_wkt) if ziel_wkt > 0 else var_ew_euros
        var_rate_cent = max(0, bonus * 100)
        variable_json = {
            'einheit': EINHEIT_ZIEL,
            'betrag': str(bonus),
            'erwartete_events': str(ziel_wkt),
            'ziel_label': ziel_label,
        }

    ew_decimal = Decimal(ew_euros)
    fix_decimal = Decimal(fix_euros)

    return SponsorOffer(
        club=club,
        saison=saison,
        typ=typ,
        sponsor_id=sponsor_id,
        sponsor_name=sponsor_name,
        fix_betrag=fix_decimal,
        variable_json=variable_json,
        erwartungswert=ew_decimal,
        slot=slot,
        fix_start=fix_euros,
        fix_aktuell=fix_euros,
        var_rate=var_rate_cent,
        var_ziel=var_ziel,
        status='offen',
    )


def generate_offers_v2(club, saison: str) -> dict[str, list]:
    """V2: Generiert slot-aware Angebote für alle 5 Slots (idempotent).

    Gibt {slot: [SponsorOffer, ...]} zurück.
    Für jeden Slot werden SPONSOR_OFFERS_PER_SLOT[slot] Angebote erzeugt.
    Existieren bereits V2-Angebote für (club, saison, slot), werden
    sie zurückgegeben (status in ('offen','angenommen','abgesagt')).
    """
    from game.models import SponsorOffer

    saison = str(saison)

    streuung = float(get_param('SPONSOR_STREUUNG', saison))
    splits = get_param('SPONSOR_TYP_SPLIT', saison)
    ziel_wkt = Decimal(str(get_param('SPONSOR_ZIEL_PROB', saison)))
    offers_per_slot = get_param('SPONSOR_OFFERS_PER_SLOT', saison)

    result = {}
    for slot in SLOTS:
        existing = list(
            SponsorOffer.objects.filter(
                club=club, saison=saison, slot=slot,
            ).exclude(status='legacy').select_related('sponsor')
        )
        if existing:
            result[slot] = existing
            continue

        n_offers = int(offers_per_slot.get(slot, 2))
        rng = random.Random(f'sponsorv2:{club.pk}:{saison}:{slot}')

        wert_slot = sponsorwert_slot(club, saison, slot)

        # SPEC §4.2: torgeld nie bei TV/Medien-Slot
        andere = ['sieggeld', 'torgeld', 'zieljaeger', 'zuschauer']
        if slot == 'tv':
            andere = [t for t in andere if t != 'torgeld']
        rng.shuffle(andere)
        typen = ['sicherheit'] + andere[:max(0, n_offers - 1)]
        while len(typen) < n_offers:
            extra = rng.choice(andere)
            if extra not in typen or typen.count(extra) < 1:
                typen.append(extra)
        typen = typen[:n_offers]

        # Ziel-Wahrscheinlichkeit aus SeasonGoal.goal_tier (SPEC §4, Kap. 12)
        ziel_wkt = _ziel_wkt_from_goal_tier(club, saison)

        e_siege = None
        e_besucher = None
        e_tore = None
        try:
            if any(t == 'sieggeld' for t in typen):
                e_siege = erwartete_siege(club, saison)
            if any(t == 'zuschauer' for t in typen):
                e_besucher = erwartete_besucher(club, saison)
            if any(t == 'torgeld' for t in typen):
                e_tore = erwartete_tore(club, saison)
        except Exception:
            pass

        used_slugs: set[str] = set()
        new_offers = []
        for typ in typen:
            sponsor_id, sp_name = _pick_sponsor(slot, saison, rng, used_slugs)
            if sp_name is None:
                pool = _NAMEN_V2.get(slot, _NAMEN.get(typ, ['Sponsor AG']))
                pool_clean = [n for n in pool if n not in {
                    o.sponsor_name for o in new_offers
                }] or pool
                sp_name = rng.choice(pool_clean)
            if sponsor_id is None:
                pass
            else:
                from game.models import Sponsor
                try:
                    sp_obj = Sponsor.objects.get(pk=sponsor_id)
                    used_slugs.add(sp_obj.slug)
                except Exception:
                    sponsor_id = None

            offer = _build_v2_offer(
                club, saison, slot, typ, wert_slot, rng, streuung,
                splits, ziel_wkt, e_siege, e_besucher, e_tore, sponsor_id, sp_name,
            )
            new_offers.append(offer)

        SponsorOffer.objects.bulk_create(new_offers)
        result[slot] = list(
            SponsorOffer.objects.filter(
                club=club, saison=saison, slot=slot,
            ).exclude(status='legacy').select_related('sponsor')
        )

    return result


# ── V1-Auswahl (backward compat) ─────────────────────────────────────────────

class SponsorChoiceError(Exception):
    """Ungültige Sponsor-Wahl (bereits gewählt / falsche Saison)."""


def choose_offer(offer) -> None:
    """V1: Markiert ein Angebot als gewählt — bindend für die ganze Saison."""
    from game.models import SponsorOffer

    try:
        with transaction.atomic():
            locked = SponsorOffer.objects.select_for_update().get(pk=offer.pk)
            if locked.gewaehlt:
                return
            if SponsorOffer.objects.filter(
                club=locked.club, saison=locked.saison, gewaehlt=True,
            ).exclude(pk=locked.pk).exists():
                raise SponsorChoiceError(
                    'Für diese Saison wurde bereits ein Sponsor gewählt — '
                    'der Vertrag läuft die ganze Saison.'
                )
            locked.gewaehlt = True
            locked.angenommen_at = timezone.now()
            locked.save(update_fields=['gewaehlt', 'angenommen_at'])
    except IntegrityError:
        raise SponsorChoiceError(
            'Für diese Saison wurde bereits ein Sponsor gewählt — '
            'der Vertrag läuft die ganze Saison.'
        )
    offer.gewaehlt = True
    offer.angenommen_at = locked.angenommen_at


def get_active_offer(club, saison: str, autopick: bool = True):
    """V1: Gewähltes Angebot (legacy, mit Lazy-Generierung und Auto-Pick)."""
    from game.models import SponsorOffer

    saison = str(saison)
    chosen = SponsorOffer.objects.filter(
        club=club, saison=saison, gewaehlt=True,
    ).first()
    if chosen or not autopick:
        return chosen

    offers = generate_offers(club, saison)
    sicherheit = next(
        (o for o in offers if o.typ == 'sicherheit'), offers[0] if offers else None,
    )
    if sicherheit is None:
        return None
    try:
        choose_offer(sicherheit)
    except SponsorChoiceError:
        return SponsorOffer.objects.filter(
            club=club, saison=saison, gewaehlt=True,
        ).first()
    return sicherheit


# ── V2-Auswahl (SponsorContract) ─────────────────────────────────────────────

class SponsorAcceptError(Exception):
    """Ungültige Annahme (Angebot abgesagt / Slot belegt / Saison gesperrt)."""


def accept_offer_v2(offer, *, auto: bool = False,
                     fix_saison_override: int | None = None) -> 'SponsorContract':
    """V2: Nimmt ein SponsorOffer an — erstellt SponsorContract für den Slot.

    fix_saison_override: Wenn gesetzt, wird dieser Wert statt fix_aktuell als
    Vertragswert verwendet (SPEC §5.4 Auto-Wahl: Multi-Offer → fix_start).

    Raises SponsorAcceptError wenn:
      - offer.status != 'offen'
      - SponsorContract für (saison, club, slot) bereits vorhanden
      - Phasensperre verletzt (current_matchday >= 1 und not auto)
    """
    from game.models import SponsorContract, SponsorOffer

    with transaction.atomic():
        locked = SponsorOffer.objects.select_for_update().get(pk=offer.pk)

        if locked.status != 'offen':
            raise SponsorAcceptError(
                f'Angebot ist nicht mehr verfügbar (Status: {locked.status}).'
            )

        if SponsorContract.objects.filter(
            saison=locked.saison, club=locked.club, slot=locked.slot,
        ).exists():
            raise SponsorAcceptError(
                f'Slot {SLOT_LABELS.get(locked.slot, locked.slot)} ist bereits belegt.'
            )

        if not auto:
            _check_transfer_window(locked.club, locked.saison)

        locked.status = 'fixiert'
        locked.angenommen_at = timezone.now()
        locked.save(update_fields=['status', 'angenommen_at'])

        fix_saison = (
            fix_saison_override
            if fix_saison_override is not None
            else (locked.fix_aktuell if locked.fix_aktuell is not None else int(locked.fix_betrag))
        )
        contract = SponsorContract.objects.create(
            saison=locked.saison,
            club=locked.club,
            slot=locked.slot,
            sponsor_id=locked.sponsor_id,
            offer=locked,
            fix_saison=fix_saison,
            auto=auto,
        )

        # Alle anderen offenen Angebote im selben Slot → abgesagt
        from game.models import SponsorOffer as _SO
        _SO.objects.filter(
            club=locked.club, saison=locked.saison, slot=locked.slot, status='offen',
        ).exclude(pk=locked.pk).update(status='abgesagt')

        # Liga-Exklusivität (SPONSOR_EXCLUSIVITY="liga"): first-come-first-served
        if locked.sponsor_id and locked.club.league_id:
            _SO.objects.filter(
                sponsor_id=locked.sponsor_id,
                saison=locked.saison,
                club__league_id=locked.club.league_id,
                status='offen',
            ).exclude(club_id=locked.club_id).update(status='abgesagt')

    offer.status = 'fixiert'
    offer.angenommen_at = locked.angenommen_at
    return contract


def _check_transfer_window(club, saison: str):
    """Phasensperre: verhindert Annahme nach Spieltag 1 (Manager-seitig)."""
    from game.models import LeagueSeasonState

    if not club.league_id:
        return
    state = LeagueSeasonState.objects.filter(
        league=club.league, season=saison,
    ).first()
    if state and state.current_matchday >= 1:
        raise SponsorAcceptError(
            'Sponsoring-Fenster ist geschlossen — '
            'ab Spieltag 1 können keine neuen Verträge mehr abgeschlossen werden.'
        )


def push_offer_v2(offer) -> dict:
    """V2: Verhandlungsrunde — deterministischer Risiko-Roll (SPEC §5.2).

    Phasensperre: wird wie accept abgelehnt wenn Saison bereits läuft (matchday>=1).
    Mindestens 2 aktive (offen) Angebote im Slot erforderlich.
    Risiko = SPONSOR_PUSH_RISKS[runde] × riskmult(RISK_MODE) → Wahrscheinlichkeit
    für „verprellt" (Angebot zurückgezogen).
    Bei Erfolg: fix_aktuell *= (1 + gain%), mult *= (1 + gain%).

    Gibt zurück:
      {'gewinn': bool, 'neu_fix': int, 'delta': int, 'verprellt': bool,
       'runde': int, 'max_runden': int}
    """
    from game.models import SponsorOffer

    saison = str(offer.saison)

    try:
        max_runden = int(get_param('SPONSOR_PUSH_MAX_ROUNDS', saison))
        gains_raw  = list(get_param('SPONSOR_PUSH_GAINS', saison))
        risks_raw  = list(get_param('SPONSOR_PUSH_RISKS', saison))
        risk_mode  = str(get_param('SPONSOR_RISK_MODE', saison))
    except Exception:
        max_runden, gains_raw, risks_raw, risk_mode = 3, [7, 10, 12], [18, 38, 62], 'Standard'

    def _as_fraction(v) -> float:
        """Normalisiert Prozent-Ganzzahl (≥1) oder Dezimalwert (<1) auf [0,1]."""
        f = float(v)
        return f / 100.0 if f >= 1.0 else f

    RISK_MULTS = {'Entschärft': 0.6, 'Standard': 1.0, 'Hardcore': 1.4}
    riskmult = RISK_MULTS.get(risk_mode, 1.0)

    _check_transfer_window(offer.club, saison)

    with transaction.atomic():
        locked = SponsorOffer.objects.select_for_update().get(pk=offer.pk)

        if locked.status != 'offen':
            return {
                'gewinn': False,
                'neu_fix': locked.fix_aktuell if locked.fix_aktuell is not None else int(locked.fix_betrag),
                'delta': 0, 'verprellt': locked.status == 'verprellt',
                'runde': locked.runde, 'max_runden': max_runden,
            }

        if locked.runde >= max_runden:
            raise SponsorAcceptError(
                f'Maximale Verhandlungsrunden ({max_runden}) erreicht.'
            )

        aktive_count = SponsorOffer.objects.filter(
            club=locked.club, saison=locked.saison, slot=locked.slot, status='offen',
        ).count()
        if aktive_count < 2:
            raise SponsorAcceptError(
                'Das letzte verbliebene Angebot ist nicht verhandelbar (Auto-Annahme-Schutz).'
            )

        fix_start   = locked.fix_start   if locked.fix_start   is not None else int(locked.fix_betrag)
        fix_aktuell = locked.fix_aktuell if locked.fix_aktuell is not None else fix_start
        runde = locked.runde

        seed_hex = hashlib.sha256(f'push:{offer.pk}:{runde}'.encode()).hexdigest()
        roll = int(seed_hex[:8], 16) / 0xFFFFFFFF

        idx = min(runde, len(gains_raw) - 1)
        gain_frac = _as_fraction(gains_raw[idx])
        risk_frac = min(0.95, _as_fraction(risks_raw[idx]) * riskmult)

        verprellt = (roll < risk_frac)

        if verprellt:
            locked.status = 'verprellt'
            locked.runde  = runde
            locked.save(update_fields=['status', 'runde'])
            offer.status = 'verprellt'
            offer.runde  = runde
            return {
                'gewinn': False, 'neu_fix': fix_aktuell,
                'delta': 0, 'verprellt': True,
                'runde': runde, 'max_runden': max_runden,
            }

        delta   = max(10_000, round(fix_aktuell * gain_frac / 10_000) * 10_000)
        neu_fix = fix_aktuell + delta
        from decimal import Decimal as _D
        neu_mult = (_D(str(locked.mult or 1)) * _D(str(1 + gain_frac))).quantize(_D('0.0001'))

        locked.fix_start   = locked.fix_start or fix_start
        locked.fix_aktuell = neu_fix
        locked.mult        = neu_mult
        locked.runde       = runde + 1
        locked.save(update_fields=['fix_start', 'fix_aktuell', 'mult', 'runde'])

    offer.fix_aktuell = neu_fix
    offer.mult        = neu_mult
    offer.runde       = runde + 1
    return {
        'gewinn': True, 'neu_fix': neu_fix, 'delta': delta,
        'verprellt': False, 'runde': runde + 1, 'max_runden': max_runden,
    }


def get_active_contracts(club, saison: str) -> list:
    """Alle aktiven (nicht abgelaufenen) SponsorContracts für (club, saison)."""
    from game.models import SponsorContract

    return list(
        SponsorContract.objects.filter(
            club=club, saison=str(saison), abgelaufen=False,
        ).select_related('sponsor', 'offer')
    )


def finalize_contracts_for_club(club, saison: str, *,
                                 force_v2: bool = True) -> list:
    """Auto-Pick: Fehlende Slots mit dem Sicherheits-Angebot belegen.

    SPEC §5.4:
    - Manager-Clubs: sicherheit bevorzugt, sonst höchster Fix zum fix_start.
    - KI-Clubs (managed_by is None): zufällige Auswahl mit 40 % sicherheit-Präferenz,
      immer zum fix_start (keine Verhandlungsgewinne).
    """
    import random as _random
    from game.models import SponsorContract

    saison = str(saison)
    new_contracts = []

    # KI-Verein = kein Manager verknüpft (SPEC §5.4)
    is_ki = (getattr(club, 'managed_by_id', None) is None)
    # Deterministischer Seed damit Wiederholungen idempotent sind
    _rng = _random.Random(f'ki-finalize:{club.pk}:{saison}') if is_ki else None

    belegt = set(
        SponsorContract.objects.filter(
            club=club, saison=saison, abgelaufen=False,
        ).values_list('slot', flat=True)
    )

    if belegt == set(SLOTS):
        return []

    offers_by_slot = generate_offers_v2(club, saison)

    for slot in SLOTS:
        if slot in belegt:
            continue
        angebote = offers_by_slot.get(slot, [])
        offene = [o for o in angebote if o.status == 'offen']
        if not offene:
            continue

        if is_ki:
            # SPEC §5.4 KI: zufällig, 40 % Chance auf sicherheit-Typ
            sicher = [o for o in offene if o.typ == 'sicherheit']
            if sicher and _rng.random() < 0.40:
                picked = _rng.choice(sicher)
            else:
                picked = _rng.choice(offene)
            # KI fixiert immer zum Startwert
            override = picked.fix_start if picked.fix_start is not None else int(picked.fix_betrag)
        else:
            # SPEC §5.4 Manager-Club: sicherheit bevorzugt, sonst höchster Fix
            picked = next(
                (o for o in offene if o.typ == 'sicherheit'),
                max(offene, key=lambda o: o.fix_aktuell or o.fix_start or 0),
            )
            # Wenn mehrere aktiv: fix_start (Verhandlungsgewinne verfallen per SPEC §5.4)
            override = None
            if len(offene) > 1:
                override = picked.fix_start if picked.fix_start is not None else int(picked.fix_betrag)

        try:
            c = accept_offer_v2(picked, auto=True, fix_saison_override=override)
            new_contracts.append(c)
        except (SponsorAcceptError, IntegrityError):
            pass

    return new_contracts


# ── V1-Buchungspfade (backward compat) ───────────────────────────────────────

def sponsor_fix_rate(offer, saison: str) -> Decimal:
    """V1: Fixanteil je Spieltag."""
    spieltage, _ = _liga_spieltage(offer.club, saison)
    return (Decimal(offer.fix_betrag) / spieltage).quantize(Decimal('0.01'))


def _variable(offer) -> tuple[str | None, Decimal]:
    v = offer.variable_json or {}
    einheit = v.get('einheit')
    try:
        betrag = Decimal(str(v.get('betrag', '0')))
    except Exception:
        betrag = Decimal('0')
    return einheit, betrag


def _variable_v2(offer) -> tuple[str | None, Decimal]:
    """V2: Euro-Betrag pro Event aus variable_json['betrag'] × mult (SPEC §6).

    Quelle der Wahrheit: variable_json['betrag'] enthält den Euro-Betrag
    pro Ereignis (als String), der beim Angebot generiert wurde.
    var_rate ist Cent-/Promille-intern und wird NICHT direkt für Auszahlungen
    verwendet (um 100x / 10000x Überzahlung zu vermeiden).
    """
    typ_to_einheit = {
        'sieggeld':  EINHEIT_SIEG,
        'torgeld':   EINHEIT_TOR,
        'zuschauer': EINHEIT_BESUCHER,
        'zieljaeger': EINHEIT_ZIEL,
    }
    einheit = typ_to_einheit.get(offer.typ) if offer else None
    if einheit is None:
        return None, Decimal('0')
    try:
        vj = offer.variable_json or {}
        betrag_str = vj.get('betrag')
        if betrag_str:
            betrag = Decimal(str(betrag_str)) * Decimal(str(offer.mult or 1))
        else:
            # Fallback auf var_rate mit Skalierung (Cent → Euro)
            div = Decimal('10000') if einheit == EINHEIT_BESUCHER else Decimal('100')
            betrag = Decimal(str(offer.var_rate or 0)) / div * Decimal(str(offer.mult or 1))
    except Exception:
        betrag = Decimal('0')
    return einheit, betrag


def book_sieg_bonus(club, offer, saison: str, *, beschreibung: str,
                    referenz_typ: str, referenz_id: int | None,
                    spieltag: int | None = None):
    """V1: Sieggeld-Bonus für EINEN Pflichtspielsieg (idempotent)."""
    from game.models import FinanceTransaction
    from .booking import book

    einheit, betrag = _variable(offer)
    if einheit != EINHEIT_SIEG or betrag <= 0:
        return None
    if FinanceTransaction.objects.filter(
        club=club, typ='SPONSOR_VARIABEL',
        referenz_typ=referenz_typ, referenz_id=referenz_id,
    ).exists():
        return None
    return book(
        club, 'SPONSOR_VARIABEL', betrag,
        beschreibung=beschreibung[:200],
        saison=saison, spieltag=spieltag,
        referenz_typ=referenz_typ, referenz_id=referenz_id,
        pflicht=True,
    )


def book_zuschauer_bonus(club, offer, attendance: int, saison: str,
                         spieltag: int | None = None):
    """V1: Zuschauer-Bonus für EIN Liga-Heimspiel."""
    from .booking import book

    einheit, betrag = _variable(offer)
    if einheit != EINHEIT_BESUCHER or betrag <= 0 or attendance <= 0:
        return None
    summe = (betrag * attendance).quantize(Decimal('0.01'))
    if summe <= 0:
        return None
    return book(
        club, 'SPONSOR_VARIABEL', summe,
        beschreibung=(
            f'{offer.sponsor_name}: Zuschauerbonus '
            f'({attendance:,} Besucher)'.replace(',', '.')
        )[:200],
        saison=saison, spieltag=spieltag,
        referenz_typ='sponsor_zuschauer', referenz_id=offer.pk,
        pflicht=True,
    )


def book_zieljaeger_bonus(club, saison: str):
    """V1: Zielbonus bei Saisonende (idempotent je Verein/Saison)."""
    from game.models import FinanceTransaction, SeasonGoal, SponsorOffer
    from .booking import book

    saison = str(saison)
    offer = SponsorOffer.objects.filter(
        club=club, saison=saison, gewaehlt=True, typ='zieljaeger',
    ).first()
    if offer is None:
        return None

    einheit, betrag = _variable(offer)
    if einheit != EINHEIT_ZIEL or betrag <= 0:
        return None

    if not saison.lstrip('-').isdigit():
        return None
    goal = SeasonGoal.objects.filter(
        club=club, season_number=int(saison), achieved=True,
    ).first()
    if goal is None:
        return None

    if FinanceTransaction.objects.filter(
        club=club, saison=saison, typ='SPONSOR_VARIABEL',
        referenz_typ='sponsor_ziel', referenz_id=offer.pk,
    ).exists():
        return None

    ziel_label = (offer.variable_json or {}).get('ziel_label', 'Saisonziel')
    return book(
        club, 'SPONSOR_VARIABEL', betrag,
        beschreibung=f'{offer.sponsor_name}: Zielbonus ({ziel_label} erreicht)'[:200],
        saison=saison,
        referenz_typ='sponsor_ziel', referenz_id=offer.pk,
        pflicht=True,
    )


# ── V2-Buchungspfade ──────────────────────────────────────────────────────────

def sponsor_fix_rate_v2(contract, saison: str, matchday: int = 0,
                         total_matchdays: int = 0) -> Decimal:
    """V2: Fixanteil je Spieltag aus SponsorContract.fix_saison.

    Letzter Spieltag bekommt den Rundungs-Restbetrag, sodass
    sum(fix_rate, alle ST) == fix_saison exakt aufgeht (SPEC §6 Rounding).
    """
    from game.models import SponsorContract

    try:
        club = contract.club
    except Exception:
        club = SponsorContract.objects.select_related('club').get(pk=contract.pk).club

    spieltage = total_matchdays or _liga_spieltage(club, saison)[0]
    floor_rate = (Decimal(contract.fix_saison) / Decimal(spieltage)).quantize(Decimal('0.01'))

    if matchday and total_matchdays and matchday >= total_matchdays:
        # Letzter Spieltag: Restbetrag = fix_saison - (spieltage-1) × floor_rate
        rest = Decimal(contract.fix_saison) - floor_rate * (spieltage - 1)
        return max(rest, Decimal('0.00'))
    return floor_rate


def book_sieg_bonus_v2(club, contract, saison: str, *, beschreibung: str,
                        referenz_typ: str, referenz_id: int | None,
                        spieltag: int | None = None):
    """V2: Sieggeld aus SponsorContract → var_rate × mult (SPEC §6)."""
    from game.models import FinanceTransaction
    from .booking import book

    offer = contract.offer
    if offer is None or offer.typ != 'sieggeld':
        return None

    einheit, betrag = _variable_v2(offer)
    if einheit != EINHEIT_SIEG or betrag <= 0:
        return None

    if FinanceTransaction.objects.filter(
        club=club, typ='SPONSOR_VARIABEL',
        referenz_typ=referenz_typ, referenz_id=referenz_id,
    ).exists():
        return None

    return book(
        club, 'SPONSOR_VARIABEL', betrag,
        beschreibung=beschreibung[:200],
        saison=saison, spieltag=spieltag,
        referenz_typ=referenz_typ, referenz_id=referenz_id,
        pflicht=True,
    )


def book_zuschauer_bonus_v2(club, contract, attendance: int, saison: str,
                             spieltag: int | None = None):
    """V2: Zuschauer-Bonus aus SponsorContract → var_rate × mult (SPEC §6)."""
    from .booking import book

    offer = contract.offer
    if offer is None or offer.typ != 'zuschauer':
        return None

    einheit, betrag = _variable_v2(offer)
    if einheit != EINHEIT_BESUCHER or betrag <= 0 or attendance <= 0:
        return None
    summe = (betrag * attendance).quantize(Decimal('0.01'))
    if summe <= 0:
        return None

    name = contract.sponsor.name if contract.sponsor_id else offer.sponsor_name
    return book(
        club, 'SPONSOR_VARIABEL', summe,
        beschreibung=(
            f'{name}: Zuschauerbonus '
            f'({attendance:,} Besucher)'.replace(',', '.')
        )[:200],
        saison=saison, spieltag=spieltag,
        referenz_typ='sponsor_zuschauer_v2', referenz_id=contract.pk,
        pflicht=True,
    )


def book_torgeld_bonus_v2(club, contract, own_goals: int, saison: str,
                           spieltag: int | None = None):
    """V2: Torgeld aus SponsorContract → var_rate × Anzahl eigene Tore (SPEC §6)."""
    from game.models import FinanceTransaction
    from .booking import book

    offer = contract.offer
    if offer is None or offer.typ != 'torgeld':
        return None
    if own_goals <= 0:
        return None

    einheit, betrag = _variable_v2(offer)
    if einheit != EINHEIT_TOR or betrag <= 0:
        return None

    # Idempotenz: nur einmal pro Spieltag buchen
    if spieltag and FinanceTransaction.objects.filter(
        club=club, saison=saison, spieltag=spieltag, typ='SPONSOR_VARIABEL',
        referenz_typ='sponsor_torgeld_v2', referenz_id=contract.pk,
    ).exists():
        return None

    summe = (betrag * Decimal(own_goals)).quantize(Decimal('0.01'))
    if summe <= 0:
        return None

    name = contract.sponsor.name if contract.sponsor_id else offer.sponsor_name
    slot_label = SLOT_LABELS.get(contract.slot, contract.slot)
    return book(
        club, 'SPONSOR_VARIABEL', summe,
        beschreibung=(
            f'{name} ({slot_label}): Torgeld {own_goals} Tor(e) ST{spieltag}'
        )[:200],
        saison=saison, spieltag=spieltag,
        referenz_typ='sponsor_torgeld_v2', referenz_id=contract.pk,
        pflicht=True,
    )


def book_zieljaeger_bonus_v2(club, saison: str) -> list:
    """V2: Zielbonus aller aktiven Zieljäger-Contracts bei Saisonende (SPEC §6)."""
    from game.models import FinanceTransaction, SeasonGoal, SponsorContract
    from .booking import book

    saison = str(saison)
    if not saison.lstrip('-').isdigit():
        return []

    goal = SeasonGoal.objects.filter(
        club=club, season_number=int(saison), achieved=True,
    ).first()
    if goal is None:
        return []

    contracts = SponsorContract.objects.filter(
        club=club, saison=saison, abgelaufen=False,
    ).select_related('sponsor', 'offer')

    booked = []
    for contract in contracts:
        offer = contract.offer
        if offer is None or offer.typ != 'zieljaeger':
            continue
        einheit, betrag = _variable_v2(offer)
        if einheit != EINHEIT_ZIEL or betrag <= 0:
            continue
        if FinanceTransaction.objects.filter(
            club=club, saison=saison, typ='SPONSOR_VARIABEL',
            referenz_typ='sponsor_ziel_v2', referenz_id=contract.pk,
        ).exists():
            continue

        name = contract.sponsor.name if contract.sponsor_id else offer.sponsor_name
        ziel_label = offer.var_ziel or (offer.variable_json or {}).get('ziel_label', 'Saisonziel')
        tx = book(
            club, 'SPONSOR_VARIABEL', betrag,
            beschreibung=f'{name}/{SLOT_LABELS.get(contract.slot,"")}: '
                         f'Zielbonus ({ziel_label})'[:200],
            saison=saison,
            referenz_typ='sponsor_ziel_v2', referenz_id=contract.pk,
            pflicht=True,
        )
        booked.append(tx)

    return booked


def expire_contracts_v2(saison: str) -> int:
    """Setzt alle SponsorContracts der Saison auf abgelaufen=True (SPEC §9 sponsor_season_close)."""
    from game.models import SponsorContract

    count = SponsorContract.objects.filter(
        saison=str(saison), abgelaufen=False,
    ).update(abgelaufen=True)
    return count


def book_sponsor_matchday_v2(club, saison: str, matchday: int,
                              fixture, result: dict) -> list:
    """V2-Buchung aller aktiven SponsorContracts für einen Spieltag.

    Bucht:
      - SPONSOR_FIX: fix_saison / Spieltage (letzter ST: Restbetrag)
      - SPONSOR_VARIABEL (Sieggeld): bei Ligasieg
      - SPONSOR_VARIABEL (Torgeld): je eigenem Pflichtspieltor
      - SPONSOR_VARIABEL (Zuschauerbonus): nur beim Heimspiel
    """
    saison = str(saison)
    contracts = get_active_contracts(club, saison)
    if not contracts:
        return []

    # Spieltage gesamt — für Rounding-Remainder (letzter ST)
    total_matchdays, _ = _liga_spieltage(club, saison)

    # Heimspiel-Erkennung + Zuschauer aus MatchdayRevenue
    is_home = (fixture is not None and fixture.home_club_id == club.pk)
    attendance = 0
    if is_home:
        try:
            from game.models import FinanceTransaction, MatchdayRevenue
            tx_ticket = FinanceTransaction.objects.filter(
                club=club, saison=saison, spieltag=matchday,
                typ='TICKET', referenz_typ='matchday_revenue',
            ).first()
            if tx_ticket:
                attendance = MatchdayRevenue.objects.get(pk=tx_ticket.referenz_id).attendance
        except Exception:
            attendance = 0

    # Eigene Tore des Spieltags
    own_goals = 0
    if fixture is not None:
        if is_home:
            own_goals = fixture.home_goals or 0
        elif fixture.away_club_id == club.pk:
            own_goals = fixture.away_goals or 0

    booked = []
    for contract in contracts:
        name = contract.sponsor.name if contract.sponsor_id else (
            contract.offer.sponsor_name if contract.offer_id else f'Slot {contract.slot}'
        )
        slot_label = SLOT_LABELS.get(contract.slot, contract.slot)

        # ── Fixrate (mit Rounding-Remainder auf letztem Spieltag) ───────────
        fix_rate = sponsor_fix_rate_v2(
            contract, saison, matchday=matchday, total_matchdays=total_matchdays,
        )
        if fix_rate > 0:
            from .booking import book
            tx = book(
                club, 'SPONSOR_FIX', fix_rate,
                beschreibung=f'{name} ({slot_label}): Fixrate ST{matchday}'[:200],
                saison=saison, spieltag=matchday,
                referenz_typ='sponsorcontract', referenz_id=contract.pk,
                pflicht=True,
            )
            booked.append(tx)
            result['sponsor_fix'] = result.get('sponsor_fix', Decimal('0')) + tx.betrag

        # ── Sieggeld ─────────────────────────────────────────────────────────
        if fixture is not None and _club_won_fixture(club, fixture):
            sieg_tx = book_sieg_bonus_v2(
                club, contract, saison,
                beschreibung=f'{name} ({slot_label}): Siegprämie ST{matchday}'[:200],
                referenz_typ='sponsor_sieg_v2',
                referenz_id=fixture.pk,
                spieltag=matchday,
            )
            if sieg_tx is not None:
                booked.append(sieg_tx)
                result['sponsor_sieg'] = (
                    result.get('sponsor_sieg', Decimal('0')) + sieg_tx.betrag
                )

        # ── Torgeld ──────────────────────────────────────────────────────────
        if own_goals > 0:
            tor_tx = book_torgeld_bonus_v2(
                club, contract, own_goals, saison, spieltag=matchday,
            )
            if tor_tx is not None:
                booked.append(tor_tx)
                result['sponsor_torgeld'] = (
                    result.get('sponsor_torgeld', Decimal('0')) + tor_tx.betrag
                )

        # ── Zuschauerbonus: wird NACH _book_tickets in matchday_run.py gebucht ──
        # (Attendance existiert im Sponsor-Schritt noch nicht; Buchung erfolgt
        # in Schritt 3 via book_v2_zuschauer_after_tickets())

    return booked


def book_v2_zuschauer_after_tickets(club, saison: str, matchday: int,
                                     attendance: int, result: dict) -> None:
    """V2-Zuschauerbonus für alle aktiven Contracts — nach Ticket-Buchung aufrufen.

    Wird in matchday_run.py Schritt 3 (nach _book_tickets) aufgerufen,
    wenn Attendance aus MatchdayRevenue bekannt ist.
    """
    saison = str(saison)
    contracts = get_active_contracts(club, saison)
    for contract in contracts:
        zus_tx = book_zuschauer_bonus_v2(
            club, contract, attendance, saison, spieltag=matchday,
        )
        if zus_tx is not None:
            result['sponsor_zuschauer'] = (
                result.get('sponsor_zuschauer', Decimal('0')) + zus_tx.betrag
            )


def _club_won_fixture(club, fixture) -> bool:
    if fixture.home_goals is None or fixture.away_goals is None:
        return False
    if fixture.home_club_id == club.pk:
        return fixture.home_goals > fixture.away_goals
    if fixture.away_club_id == club.pk:
        return fixture.away_goals > fixture.home_goals
    return False
