"""Finanz-Monitoring (Spec Kap. 12.5) — reine Aggregationen über das Ledger.

Klassifikation der Buchungstypen in Geldschöpfung (Geld betritt das System),
Geldvernichtung (Geld verlässt das System) und Zirkulation (Verein↔Verein,
geldmengenneutral). Diese Zuordnung existiert genau EINMAL hier — Views und
Commands importieren sie, statt sie zu duplizieren.

Alarmwerte (Spec 12.5, nur Anzeige, keine Automatik):
  · Geldmengenwachstum > 4 % pro Saison
  · Ablöse/MW-Median > 2,2 (Gesundheitsziel 1,3–1,8)
  · Totes Kapital steigend über 3 Saisons
"""
from decimal import Decimal
from statistics import median

from django.db.models import Q, Sum

# ── Typ-Klassifikation (Spec 12.5) ──────────────────────────────────────
SCHOEPFUNG_TYPEN = frozenset({
    'TICKET', 'UMFELD', 'SPONSOR_FIX', 'SPONSOR_VARIABEL',
    'TV_SOCKEL', 'TV_PLATZ', 'TV_KOEFF', 'FALLSCHIRM',
    'PRAEMIE_POKAL', 'PRAEMIE_SUPERCUP', 'PRAEMIE_INTL', 'ABFINDUNG',
})
ZIRKULATION_TYPEN = frozenset({
    'TRANSFER_EIN', 'TRANSFER_AUS', 'AUSBILDUNG_EIN', 'AUSBILDUNG_AUS',
})
VERNICHTUNG_TYPEN = frozenset({
    'GEHALT', 'BETRIEB', 'STADION_UNTERHALT', 'STADION_SPIELTAG',
    'AUSBAU', 'UMFELD_AUSBAU', 'SCOUTING', 'AUKTION', 'STRAFE',
    'VERBANDSABGABE',
})
# KORREKTUR_ADMIN ist bewusst unklassifiziert (manuelle Eingriffe).

# ── Alarmschwellen (Spec 12.5) ──────────────────────────────────────────
ALARM_GELDMENGENWACHSTUM = 0.04     # > 4 % pro Saison
ALARM_ABLOESE_MW_MEDIAN = 2.2       # Median-Ratio Ablöse/MW
GESUND_ABLOESE_MW = (1.3, 1.8)      # Gesundheitsziel
TOTES_KAPITAL_UMSATZ_FAKTOR = 2     # Kontostand > 2× Jahresumsatz


def klassifiziere(typ: str) -> str:
    """'schoepfung' | 'vernichtung' | 'zirkulation' | 'neutral'."""
    if typ in SCHOEPFUNG_TYPEN:
        return 'schoepfung'
    if typ in VERNICHTUNG_TYPEN:
        return 'vernichtung'
    if typ in ZIRKULATION_TYPEN:
        return 'zirkulation'
    return 'neutral'


def saison_geldfluesse(saison: str) -> dict:
    """Schöpfung/Vernichtung/Zirkulation einer Saison, je Buchungstyp.

    Returns dict mit 'schoepfung', 'vernichtung' (je: total, rows) und
    'netto' (Schöpfung − Vernichtung = Geldmengenänderung der Saison).
    Zirkulation wird als Volumen (nur positive Seite) ausgewiesen.
    """
    from game.models import FinanceTransaction

    agg = list(
        FinanceTransaction.objects.filter(saison=str(saison))
        .values('typ')
        .annotate(total=Sum('betrag'))
    )
    labels = dict(FinanceTransaction.TYP_CHOICES)

    schoepfung_rows, vernichtung_rows = [], []
    schoepfung = vernichtung = zirkulation_vol = Decimal('0')
    for r in agg:
        typ, total = r['typ'], r['total'] or Decimal('0')
        klasse = klassifiziere(typ)
        row = {'typ': typ, 'label': labels.get(typ, typ), 'total': total}
        if klasse == 'schoepfung':
            schoepfung += total
            schoepfung_rows.append(row)
        elif klasse == 'vernichtung':
            vernichtung += -total
            vernichtung_rows.append(row)
        elif klasse == 'zirkulation' and total > 0:
            zirkulation_vol += total

    schoepfung_rows.sort(key=lambda r: -abs(r['total']))
    vernichtung_rows.sort(key=lambda r: -abs(r['total']))
    return {
        'schoepfung': schoepfung,
        'schoepfung_rows': schoepfung_rows,
        'vernichtung': vernichtung,
        'vernichtung_rows': vernichtung_rows,
        'zirkulation_volumen': zirkulation_vol,
        'netto': schoepfung - vernichtung,
    }


def geldmengen_verlauf() -> list[dict]:
    """Geldmengenänderung (Netto Schöpfung−Vernichtung) je Saison + Wachstum.

    Wachstum wird gegen die approximierte Geldmenge zu Saisonbeginn gerechnet
    (heutige Geldmenge rückwärts um die Netto-Änderungen bereinigt).
    """
    from game.models import Club, FinanceTransaction

    saisons = sorted(
        {s for s in FinanceTransaction.objects.values_list('saison', flat=True)
         .distinct() if (s or '').isdigit()},
        key=int,
    )
    heute = Club.objects.aggregate(t=Sum('budget'))['t'] or Decimal('0')

    fluesse = {s: saison_geldfluesse(s) for s in saisons}
    verlauf = []
    ende = heute
    for s in reversed(saisons):
        netto = fluesse[s]['netto']
        start = ende - netto
        wachstum = float(netto / start) if start > 0 else None
        verlauf.append({
            'saison': s,
            'start': start,
            'ende': ende,
            'netto': netto,
            'wachstum': wachstum,
            'alarm': (wachstum is not None
                      and wachstum > ALARM_GELDMENGENWACHSTUM),
        })
        ende = start
    verlauf.reverse()
    return verlauf


def abloese_mw_median(saison: str) -> dict:
    """Median-Ratio Ablöse/Marktwert der Transfers einer Saison.

    Datenbasis: TRANSFER_AUS-Buchungen (Käuferseite, referenz_typ='transfer',
    referenz_id=Player-PK) der Saison. Marktwert = aktueller
    Player.market_value (historische MW werden nicht versioniert —
    bewusste Approximation, für den Alarmwert ausreichend).
    """
    from game.models import FinanceTransaction, Player

    txs = list(
        FinanceTransaction.objects
        .filter(saison=str(saison), typ='TRANSFER_AUS',
                referenz_typ='transfer', referenz_id__isnull=False)
        .values('referenz_id', 'betrag')
    )
    if not txs:
        return {'median': None, 'count': 0, 'alarm': False, 'gesund': None}

    mw_map = dict(
        Player.objects.filter(pk__in={t['referenz_id'] for t in txs})
        .values_list('pk', 'market_value')
    )
    ratios = []
    for t in txs:
        mw = mw_map.get(t['referenz_id'])
        if mw and mw > 0:
            ratios.append(float(abs(t['betrag'])) / float(mw))
    if not ratios:
        return {'median': None, 'count': 0, 'alarm': False, 'gesund': None}

    med = median(ratios)
    lo, hi = GESUND_ABLOESE_MW
    return {
        'median': med,
        'count': len(ratios),
        'alarm': med > ALARM_ABLOESE_MW_MEDIAN,
        'gesund': lo <= med <= hi,
    }


def totes_kapital_verlauf() -> dict:
    """Totes Kapital je Saison + Alarm „3 Saisons steigend" (Spec 12.5).

    Historische Kontostände werden pro Verein rückwärts aus dem heutigen
    Budget rekonstruiert (Saisonende S = heutiges Budget − Netto-Buchungen
    aller Saisons nach S) — gleiche Approximation wie geldmengen_verlauf,
    Buchungen ohne Saisonzuordnung/KORREKTUR-freie Lücken bleiben außen vor.
    Totes Kapital am Saisonende = Summe der Kontostände > 2× Jahresumsatz
    der Saison. Alarm, wenn die Summe über die letzten 3 Saisons strikt
    steigt (braucht mindestens 3 Saisons Datenbasis).
    """
    from game.models import Club, FinanceTransaction

    saisons = sorted(
        {s for s in FinanceTransaction.objects.values_list('saison', flat=True)
         .distinct() if (s or '').isdigit()},
        key=int,
    )
    if not saisons:
        return {'verlauf': [], 'alarm': False}

    agg = (
        FinanceTransaction.objects.filter(saison__in=saisons)
        .values('club_id', 'saison')
        .annotate(netto=Sum('betrag'),
                  umsatz=Sum('betrag', filter=Q(betrag__gt=0)))
    )
    netto_map, umsatz_map = {}, {}
    for r in agg:
        key = (r['club_id'], r['saison'])
        netto_map[key] = r['netto'] or Decimal('0')
        umsatz_map[key] = r['umsatz'] or Decimal('0')

    ende = {pk: (b or Decimal('0'))
            for pk, b in Club.objects.values_list('pk', 'budget')}
    verlauf_rev = []
    for s in reversed(saisons):
        summe = Decimal('0')
        count = 0
        for club_id, bal in ende.items():
            if bal > 0:
                umsatz = umsatz_map.get((club_id, s), Decimal('0'))
                if bal > TOTES_KAPITAL_UMSATZ_FAKTOR * umsatz:
                    summe += bal
                    count += 1
        verlauf_rev.append({'saison': s, 'summe': summe, 'count': count})
        for club_id in ende:
            ende[club_id] -= netto_map.get((club_id, s), Decimal('0'))

    verlauf = list(reversed(verlauf_rev))
    alarm = (
        len(verlauf) >= 3
        and verlauf[-3]['summe'] < verlauf[-2]['summe'] < verlauf[-1]['summe']
    )
    return {'verlauf': verlauf, 'alarm': alarm}


def totes_kapital(saison: str) -> dict:
    """Summe der Kontostände > 2× Jahresumsatz (Spec 12.5).

    Jahresumsatz = positive Ledger-Summe des Vereins in der Saison.
    """
    from game.models import Club, FinanceTransaction

    umsaetze = dict(
        FinanceTransaction.objects
        .filter(saison=str(saison), betrag__gt=0)
        .values_list('club_id')
        .annotate(s=Sum('betrag'))
        .values_list('club_id', 's')
    )
    summe = Decimal('0')
    clubs = []
    for club in Club.objects.filter(budget__gt=0).only('id', 'name', 'budget'):
        umsatz = umsaetze.get(club.pk, Decimal('0'))
        grenze = TOTES_KAPITAL_UMSATZ_FAKTOR * umsatz
        if club.budget > grenze:
            summe += club.budget
            clubs.append({'name': club.name, 'budget': club.budget,
                          'umsatz': umsatz})
    clubs.sort(key=lambda c: -c['budget'])
    return {'summe': summe, 'count': len(clubs), 'clubs': clubs[:10]}
