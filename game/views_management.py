import json
from decimal import Decimal

# ── Stadionumfeld: Einrichtungsdaten ──────────────────────────────────────────
def _fmt_euro(amount):
    return f"{amount:,}".replace(",", ".")

FACILITY_DATA = {
    'nlz': [
        {'desc': 'Basis-NLZ aktiv. Kaderlimit: 60 Spieler (Jugend & Profi).',                                                'cost': 0,         'days': 0},
        {'desc': 'Erweitertes NLZ. Kaderlimit: 63 Spieler.',                                                                 'cost': 3000000,   'days': 3},
        {'desc': 'Professionelles NLZ. Kaderlimit: 66 Spieler. Entwicklungsbonus +5 % für alle U-18-Spieler.',              'cost': 5000000,   'days': 5},
        {'desc': 'Elite-Akademie. Kaderlimit: 70 Spieler. Maximale Jugendentwicklung, Talente reifen schneller.',           'cost': 7000000,   'days': 7},
    ],
    'medizin': [
        {'desc': 'Basisversorgung. Verletzungen werden standardmäßig behandelt, keine Verkürzung der Ausfallzeiten.',        'cost': 0,         'days': 0},
        {'desc': 'Modernes Reha-Center. −5 % Verletzungsanfälligkeit. Ausfallzeiten verkürzen sich um 1–2 Tage.',           'cost': 5000000,   'days': 3},
        {'desc': 'Sportmedizinisches Zentrum. −10 % Anfälligkeit. Ausfallzeiten −2–3 Tage. Präventionsprogramm aktiv.',     'cost': 7000000,   'days': 5},
        {'desc': 'Elite-Medizin. −20 % Anfälligkeit. Ausfallzeiten −3–4 Tage. Individualpflege + beschleunigte Reha.',     'cost': 12000000,  'days': 7},
    ],
    'training': [
        {'desc': 'Einfaches Trainingsgelände. Frischewerte werden nur in 5er-Schritten angezeigt.',                          'cost': 0,         'days': 0},
        {'desc': 'Modernisiertes Gelände. Frischeanzeige auf 1–2 Punkte genau. Konditionstraining besser planbar.',          'cost': 5000000,   'days': 3},
        {'desc': 'Profianlagen. Exakte Frischeanzeige + Frischeverlust pro Spiel um 1–2 Punkte reduziert.',                  'cost': 7000000,   'days': 5},
        {'desc': 'Top-Trainingszentrum. Exakte Anzeige + täglich 1–2 Frischepunkte automatisch regeneriert.',               'cost': 9000000,   'days': 7},
    ],
    'office': [
        {'desc': 'Kleine Geschäftsstelle. Kein Platz für zusätzliche Trainer oder Co-Trainer.',                              'cost': 0,         'days': 0},
        {'desc': 'Erweitertes Büro. Jugendtrainer übernimmt automatisch Aufstellung & Taktik für die Jugendmannschaft.',     'cost': 3000000,   'days': 3},
        {'desc': 'Professionelles Büro. Co-Trainer erinnert an wichtige Spieler & markiert die Top-5-Standardschützen.',    'cost': 5000000,   'days': 5},
        {'desc': 'Vollausgestattete Geschäftsstelle. Co-Trainer analysiert Top-3-Standardschützen für Jugend & Profi.',     'cost': 7000000,   'days': 7},
    ],
}

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import MatchdayRevenue, StadiumExpansion, StadionumfeldConfig
from .stadium_costs import MAX_KAPAZITAET, get_expansion_cost, get_kostenmatrix
from .stadium_revenue import record_matchday_revenue
from .views import current_manager_club, build_game_header


def _get_stadium_or_none(club):
    if not club:
        return None
    try:
        return club.stadium
    except Exception:
        return None


# ------------------------------------------------------------------ #
#  Management Hub                                                      #
# ------------------------------------------------------------------ #

@login_required(login_url='/auth/login/')
def management_hub(request):
    club    = current_manager_club(user=request.user)
    stadium = _get_stadium_or_none(club)

    # Stadionbild: aus PublicProfile des Clubs oder generisches Fallback
    stadium_bg = None
    if club:
        pp = getattr(club, 'public_profile', None)
        if pp and pp.stadium_image_static_path:
            stadium_bg = pp.stadium_image_static_path

    return render(request, 'game/management/hub.html', {
        'club':       club,
        'stadium':    stadium,
        'stadium_bg': stadium_bg,
    })


# ------------------------------------------------------------------ #
#  Stadion-Detailseite                                                 #
# ------------------------------------------------------------------ #

@login_required(login_url='/auth/login/')
def stadium_detail(request):
    club    = current_manager_club(user=request.user)
    stadium = _get_stadium_or_none(club)

    if not stadium:
        messages.error(request, 'Dein Verein hat noch kein Stadion.')
        return redirect('management_hub')

    expansions     = stadium.expansions.all()[:10]
    kostenmatrix   = get_kostenmatrix(stadium.capacity_total)
    revenue_entries = stadium.revenue_entries.all()[:10]

    # Letzte Auslastung für Tribünen-Balken
    last_entry     = stadium.revenue_entries.order_by('-created_at').first()
    last_pct       = float(last_entry.auslastung_pct) if last_entry else 0.0

    def _bar(capacity, pct):
        attended = int(round(capacity * pct / 100))
        bar_pct  = round(min(100, pct))
        return {'capacity': capacity, 'attended': attended, 'bar_pct': bar_pct}

    # Tribünen-Übersicht als strukturiertes Dict für das Template
    stands = [
        {
            'key':      'nord',
            'label':    'Nordkurve',
            'standing': stadium.nord_standing,
            'seating':  stadium.nord_seating,
            'vip':      stadium.nord_vip,
            'total':    stadium.nord_standing + stadium.nord_seating + stadium.nord_vip,
            'bar_steh': _bar(stadium.nord_standing, last_pct),
            'bar_sitz': _bar(stadium.nord_seating,  last_pct),
            'bar_vip':  _bar(stadium.nord_vip,      last_pct),
        },
        {
            'key':      'ost',
            'label':    'Osttribüne',
            'standing': stadium.ost_standing,
            'seating':  stadium.ost_seating,
            'vip':      stadium.ost_vip,
            'total':    stadium.ost_standing + stadium.ost_seating + stadium.ost_vip,
            'bar_steh': _bar(stadium.ost_standing, last_pct),
            'bar_sitz': _bar(stadium.ost_seating,  last_pct),
            'bar_vip':  _bar(stadium.ost_vip,      last_pct),
        },
        {
            'key':      'sued',
            'label':    'Südkurve',
            'standing': stadium.sued_standing,
            'seating':  stadium.sued_seating,
            'vip':      stadium.sued_vip,
            'total':    stadium.sued_standing + stadium.sued_seating + stadium.sued_vip,
            'bar_steh': _bar(stadium.sued_standing, last_pct),
            'bar_sitz': _bar(stadium.sued_seating,  last_pct),
            'bar_vip':  _bar(stadium.sued_vip,      last_pct),
        },
        {
            'key':      'west',
            'label':    'Westtribüne',
            'standing': stadium.west_standing,
            'seating':  stadium.west_seating,
            'vip':      stadium.west_vip,
            'total':    stadium.west_standing + stadium.west_seating + stadium.west_vip,
            'bar_steh': _bar(stadium.west_standing, last_pct),
            'bar_sitz': _bar(stadium.west_seating,  last_pct),
            'bar_vip':  _bar(stadium.west_vip,      last_pct),
        },
    ]

    # Auslastung: aus echten Spieltags-Daten ableiten oder Schätzformel
    recent_revenues = list(revenue_entries)
    if recent_revenues:
        avg_auslastung = float(
            sum(r.auslastung_pct for r in recent_revenues) / len(recent_revenues)
        )
        gauge_auslastung = round(avg_auslastung)
        auslastung_faktor = avg_auslastung / 100.0
    else:
        from .stadium_revenue import calculate_auslastung, get_competition_factor
        auslastung_faktor = calculate_auslastung(
            fan_popularity=club.fan_popularity,
            price_standing=float(stadium.price_standing),
            price_seating=float(stadium.price_seating),
            competition_factor=1.0,
            opponent_strength=65.0,
        )
        gauge_auslastung = round(auslastung_faktor * 100)

    # Einnahmen bei Vollauslastung (Stehplätze + Sitzplätze + VIP × Preis)
    einnahmen_vollauslastung = (
        stadium.capacity_standing * float(stadium.price_standing) +
        stadium.capacity_seating  * float(stadium.price_seating)  +
        stadium.capacity_vip      * float(stadium.price_vip)
    )

    # Saisoneinnahmen: tatsächliche Summe aller verbuchten Spiele
    saisoneinnahmen_aktuell = float(
        sum(r.revenue_total for r in recent_revenues)
    ) if recent_revenues else 0

    # Stadionkosten laufende Saison (Betriebskosten je Heimspiel × Spiele)
    games_played = len(recent_revenues)
    stadionkosten_saison = (
        stadium.capacity_standing * 3 +
        stadium.capacity_seating  * 7 +
        stadium.capacity_vip      * 25
    ) * games_played

    # Liga-Durchschnitt Ticketpreise (alle Stadien in der gleichen Liga)
    from django.db.models import Avg
    from .models import Stadium as StadiumModel
    _liga_qs = StadiumModel.objects.filter(club__league=club.league)
    _liga_avgs = _liga_qs.aggregate(
        avg_standing=Avg('price_standing'),
        avg_seating=Avg('price_seating'),
        avg_vip=Avg('price_vip'),
    )
    liga_avg_standing = round(float(_liga_avgs['avg_standing'] or stadium.price_standing), 2)
    liga_avg_seating  = round(float(_liga_avgs['avg_seating']  or stadium.price_seating),  2)
    liga_avg_vip      = round(float(_liga_avgs['avg_vip']      or stadium.price_vip),      2)

    # Fan-Erlebnis-Werte
    cap = stadium.capacity_total or 1
    standing_ratio = stadium.capacity_standing / cap
    seating_vip_ratio = (stadium.capacity_seating + stadium.capacity_vip) / cap
    lawn = stadium.lawn_quality

    gauge_atmosphaere = min(100, round(standing_ratio * 65 + lawn * 0.35))
    gauge_komfort     = min(100, round(seating_vip_ratio * 70 + lawn * 0.30))

    # Stadionumfeld-Einrichtungen
    _raw_facilities = [
        ('nlz',      1, 'NLZ',             'Nachwuchsleistungszentrum', stadium.nlz_level,      22, 18),
        ('medizin',  2, 'Medizin',         'Medizinische Abteilung',    stadium.medizin_level,  78, 42),
        ('training', 3, 'Trainingsgelände','Trainingsgelände',           stadium.training_level, 50, 76),
        ('office',   4, 'Geschäftsstelle', 'Geschäftsstelle',            stadium.office_level,   20, 64),
    ]
    facilities = []
    for key, num, label, sublabel, lvl, px, py in _raw_facilities:
        levels_data = FACILITY_DATA[key]
        tooltip_levels = [
            {'level': i, 'desc': d['desc'], 'cost_fmt': _fmt_euro(d['cost']), 'days': d['days']}
            for i, d in enumerate(levels_data)
        ]
        facilities.append({
            'num':             num,
            'key':             key,
            'label':           label,
            'sublabel':        sublabel,
            'level':           lvl,
            'pin_x':           px,
            'pin_y':           py,
            'desc':            levels_data[lvl]['desc'],
            'upgrade_cost_fmt': _fmt_euro(levels_data[lvl + 1]['cost']) if lvl < 3 else '',
            'upgrade_days':    levels_data[lvl + 1]['days'] if lvl < 3 else 0,
            'tooltip_levels':  tooltip_levels,
        })

    return render(request, 'game/management/stadium.html', {
        'club':                  club,
        'stadium':               stadium,
        'stands':                stands,
        'expansions':            expansions,
        'revenue_entries':       revenue_entries,
        'kostenmatrix_json':     json.dumps(kostenmatrix),
        'facilities':            facilities,
        'max_kapazitaet':        MAX_KAPAZITAET,
        'einnahmen_vollauslastung': einnahmen_vollauslastung,
        'saisoneinnahmen':          saisoneinnahmen_aktuell,
        'stadionkosten_saison':     stadionkosten_saison,
        'games_played':             games_played,
        'liga_avg_standing':        liga_avg_standing,
        'liga_avg_seating':         liga_avg_seating,
        'liga_avg_vip':             liga_avg_vip,
        'gauge_auslastung':         gauge_auslastung,
        'gauge_atmosphaere':        gauge_atmosphaere,
        'gauge_komfort':            gauge_komfort,
        'hat_echte_auslastung':     bool(recent_revenues),
    })


# ------------------------------------------------------------------ #
#  Ticketpreise setzen                                                 #
# ------------------------------------------------------------------ #

@login_required(login_url='/auth/login/')
@require_POST
def stadium_set_prices(request):
    club    = current_manager_club(user=request.user)
    stadium = _get_stadium_or_none(club)
    if not stadium:
        return redirect('management_hub')

    fields_to_save = []
    raw = {
        'price_standing': request.POST.get('price_standing', '').strip(),
        'price_seating':  request.POST.get('price_seating',  '').strip(),
        'price_vip':      request.POST.get('price_vip',      '').strip(),
    }

    parsed = {}
    for field, val in raw.items():
        if val == '':
            continue
        try:
            parsed[field] = float(val)
        except ValueError:
            messages.error(request, f'Ungültige Eingabe für {field}.')
            return redirect('stadium_detail')

    if not parsed:
        messages.warning(request, 'Keine Preise eingegeben — nichts geändert.')
        return redirect('stadium_detail')

    for field, p in parsed.items():
        if p < 0:
            messages.error(request, 'Ticketpreise dürfen nicht negativ sein.')
            return redirect('stadium_detail')
        setattr(stadium, field, Decimal(str(round(p, 2))))
        fields_to_save.append(field)

    # Konsistenzhinweis nur wenn alle drei bekannt
    p_steh = float(parsed.get('price_standing', stadium.price_standing))
    p_sitz = float(parsed.get('price_seating',  stadium.price_seating))
    p_vip  = float(parsed.get('price_vip',      stadium.price_vip))
    if p_vip < p_sitz or p_sitz < p_steh:
        messages.warning(request, 'Hinweis: VIP-Preise sollten höher als Sitz- und Stehpreise sein.')

    stadium.save(update_fields=fields_to_save)
    messages.success(request, 'Ticketpreise erfolgreich aktualisiert.')
    return redirect('stadium_detail')


# ------------------------------------------------------------------ #
#  Stadionausbau                                                       #
# ------------------------------------------------------------------ #

@login_required(login_url='/auth/login/')
@require_POST
def stadium_expand(request):
    club    = current_manager_club(user=request.user)
    stadium = _get_stadium_or_none(club)
    if not stadium:
        return redirect('management_hub')

    stand     = request.POST.get('stand', '').upper()
    seat_type = request.POST.get('seat_type', '').upper()
    try:
        anzahl = int(request.POST.get('seats_added', 0))
    except ValueError:
        anzahl = 0

    # Validierung
    valid_stands     = {'NORD', 'OST', 'SUED', 'WEST'}
    valid_seat_types = {'STEH', 'SITZ', 'VIP'}

    if stand not in valid_stands or seat_type not in valid_seat_types:
        messages.error(request, 'Ungültige Tribüne oder Platztyp.')
        return redirect('stadium_detail')

    if anzahl <= 0 or anzahl > 50_000:
        messages.error(request, 'Anzahl muss zwischen 1 und 50.000 liegen.')
        return redirect('stadium_detail')

    aktuelle_kapazitaet = stadium.capacity_total
    if aktuelle_kapazitaet + anzahl > MAX_KAPAZITAET:
        verbleibend = MAX_KAPAZITAET - aktuelle_kapazitaet
        messages.error(
            request,
            f'Maximale Kapazität ({MAX_KAPAZITAET:,}) würde überschritten. '
            f'Noch {verbleibend:,} Plätze möglich.'
        )
        return redirect('stadium_detail')

    kosten = get_expansion_cost(aktuelle_kapazitaet, seat_type, anzahl)

    if club.budget < kosten:
        messages.error(
            request,
            f'Budget reicht nicht. Benötigt: {kosten:,.0f} € — '
            f'Verfügbar: {club.budget:,.0f} €'
        )
        return redirect('stadium_detail')

    # Budget abziehen
    club.budget -= kosten
    club.save(update_fields=['budget'])

    # Kapazität erhöhen
    feld_map = {
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
    feld = feld_map[(stand, seat_type)]
    setattr(stadium, feld, getattr(stadium, feld) + anzahl)
    stadium.save(update_fields=[feld])

    # Ausbau-Eintrag anlegen
    StadiumExpansion.objects.create(
        stadium   = stadium,
        stand     = stand,
        seat_type = seat_type,
        seats_added = anzahl,
        cost      = kosten,
    )

    stand_labels = {'NORD': 'Nordkurve', 'OST': 'Osttribüne', 'SUED': 'Südkurve', 'WEST': 'Westtribüne'}
    type_labels  = {'STEH': 'Stehplätze', 'SITZ': 'Sitzplätze', 'VIP': 'VIP-Plätze'}
    messages.success(
        request,
        f'+{anzahl:,} {type_labels[seat_type]} in der {stand_labels[stand]} '
        f'für {kosten:,.0f} € erfolgreich gebaut.'
    )
    return redirect('stadium_detail')


# ------------------------------------------------------------------ #
#  Spieltags-Einnahmen manuell verbuchen (Manager-Aktion)              #
# ------------------------------------------------------------------ #

@login_required(login_url='/auth/login/')
@require_POST
def stadium_record_revenue(request):
    """
    Verbucht Spieltags-Einnahmen für ein Heimspiel ohne verknüpftes MatchResult.
    Der Manager trägt Gegner-Stärke und Wettbewerb manuell ein.
    """
    club    = current_manager_club(user=request.user)
    stadium = _get_stadium_or_none(club)
    if not stadium:
        return redirect('management_hub')

    competition_name = request.POST.get('competition_name', '').strip() or 'Freundschaftsspiel'
    try:
        opponent_strength = float(request.POST.get('opponent_strength', 65))
        opponent_strength = max(0.0, min(100.0, opponent_strength))
    except (ValueError, TypeError):
        opponent_strength = 65.0

    try:
        entry = record_matchday_revenue(
            club=club,
            match_result=None,
            opponent_strength=opponent_strength,
            competition_name=competition_name,
        )
        messages.success(
            request,
            f'Spieltags-Einnahmen verbucht: {entry.revenue_total:,.0f} € '
            f'({entry.auslastung_pct} % Auslastung, {entry.attendance:,} Zuschauer)'
        )
    except Exception as exc:
        messages.error(request, f'Fehler beim Verbuchen: {exc}')

    return redirect('stadium_detail')


# ------------------------------------------------------------------ #
#  Kostenberechnung API (JSON, für Live-Vorschau)                      #
# ------------------------------------------------------------------ #

@login_required(login_url='/auth/login/')
def stadium_cost_api(request):
    club    = current_manager_club(user=request.user)
    stadium = _get_stadium_or_none(club)
    if not stadium:
        return JsonResponse({'error': 'Kein Stadion'}, status=404)

    seat_type = request.GET.get('seat_type', 'SITZ').upper()
    try:
        anzahl = int(request.GET.get('anzahl', 0))
    except ValueError:
        anzahl = 0

    if anzahl <= 0:
        return JsonResponse({'kosten': 0, 'preis_pro_platz': 0})

    kosten = get_expansion_cost(stadium.capacity_total, seat_type, anzahl)
    return JsonResponse({
        'kosten':         float(kosten),
        'kosten_fmt':     f'{kosten:,.0f}',
        'preis_pro_platz': float(kosten / anzahl) if anzahl else 0,
    })


@login_required
@require_POST
def facility_upgrade(request):
    club    = current_manager_club(user=request.user)
    stadium = _get_stadium_or_none(club)
    if not stadium or not club:
        return redirect('management_hub')

    key = request.POST.get('facility', '')
    field_map = {
        'nlz':      'nlz_level',
        'medizin':  'medizin_level',
        'training': 'training_level',
        'office':   'office_level',
    }
    if key not in field_map:
        messages.error(request, 'Unbekannte Einrichtung.')
        return redirect('stadium_detail')

    field   = field_map[key]
    current = getattr(stadium, field)

    if current >= 3:
        messages.error(request, 'Einrichtung ist bereits auf Maximalstufe.')
        return redirect('stadium_detail')

    kosten = Decimal(FACILITY_DATA[key][current + 1]['cost'])

    if club.budget < kosten:
        messages.error(
            request,
            f'Budget reicht nicht. Benötigt: {kosten:,.0f} € — '
            f'Verfügbar: {club.budget:,.0f} €'
        )
        return redirect('stadium_detail')

    club.budget -= kosten
    club.save(update_fields=['budget'])

    setattr(stadium, field, current + 1)
    stadium.save(update_fields=[field])

    label_map = {
        'nlz': 'NLZ', 'medizin': 'Medizin',
        'training': 'Trainingsgelände', 'office': 'Geschäftsstelle',
    }
    messages.success(
        request,
        f'{label_map[key]} auf Stufe {current + 1} ausgebaut. '
        f'{kosten:,.0f} € abgebucht.'
    )
    return redirect('stadium_detail')


# ------------------------------------------------------------------ #
#  Präsident-Büro — Saisonziele & Hoeneß-Coin                         #
# ------------------------------------------------------------------ #

COIN_SHOP = []


@login_required(login_url='/auth/login/')
def president_office(request):
    from .models import SeasonGoal, HoenessCoin
    from .season_goals import (
        current_season_number,
        declare_goal_for_club,
        is_season_started,
        required_max_rank,
        TIER_LABELS,
    )

    club = current_manager_club(user=request.user)
    if not club:
        messages.error(request, 'Dir ist noch kein Verein zugewiesen.')
        return redirect('management_hub')

    manager = club.managed_by
    season = current_season_number()
    season_started = is_season_started(season)

    # Coin-Guthaben
    coin_balance = 0
    coin = None
    if manager:
        coin, _ = HoenessCoin.objects.get_or_create(manager=manager)
        coin_balance = coin.amount

    # Das Saisonziel bleibt unter Verschluss, bis der Admin die Saison
    # offiziell startet. Erst dann wird es verkündet (und festgeschrieben).
    goal = None
    tier = tier_label = tier_class = None
    req_rank = league_size = None

    if season_started:
        goal = SeasonGoal.objects.filter(club=club, season_number=season).first()
        if not goal:
            goal = declare_goal_for_club(club, season_number=season)
        tier = goal.goal_tier
        tier_label = goal.goal_tier_label
        tier_class = f'tier-{tier}'
        req_rank = goal.required_max_rank
        league_size = goal.league_size

    # Zufriedenheit: vereinsgebunden aus PresidentSatisfaction (Default 100)
    from .models import PresidentSatisfaction
    satisfaction = 100
    if manager:
        sat = PresidentSatisfaction.objects.filter(manager=manager, club=club).first()
        satisfaction = sat.value if sat else 100

    # Ziel-Historie (letzte Saisons)
    history = list(
        SeasonGoal.objects
        .filter(club=club)
        .exclude(season_number=season)
        .order_by('-season_number')[:5]
    )

    return render(request, 'game/management/president.html', {
        'club':               club,
        'manager':            manager,
        'season':             season,
        'season_started':     season_started,
        'coin_balance':       coin_balance,
        'goal':               goal,
        'tier':               tier,
        'tier_label':         tier_label,
        'tier_class':         tier_class,
        'league_size':        league_size,
        'required_max_rank':  req_rank,
        'satisfaction':       satisfaction,
        'history':            history,
        'coin_shop':          COIN_SHOP,
    })


# ------------------------------------------------------------------ #
#  Sportgericht                                                         #
# ------------------------------------------------------------------ #

def _inactivity_status(manager, squad_scope, season):
    """Berechnet Inaktivitätsstatus für eine Mannschaft.

    Gibt dict zurück mit:
      consecutive   – aktuelle aufeinanderfolgende Fehlstarts
      season_total  – Fehlstarts in der Saison
      consec_limit  – Schwelle für Entlassung (hintereinander)
      season_limit  – Schwelle für Entlassung (pro Saison)
      penalty_pts   – Anzahl Strafpunkte des Managers
      light         – 'green' | 'yellow' | 'red'
    """
    from .models import InactivityRecord, InactivityPenalty

    penalty_pts = InactivityPenalty.objects.filter(manager=manager).count()
    consec_limit = 2 if penalty_pts > 0 else 3
    season_limit = 4 if penalty_pts > 0 else 5

    season_records = list(
        InactivityRecord.objects.filter(
            manager=manager, squad_scope=squad_scope, season=season
        ).order_by('recorded_at')
    )
    season_total = len(season_records)

    all_records = list(
        InactivityRecord.objects.filter(
            manager=manager, squad_scope=squad_scope
        ).order_by('-recorded_at')
    )
    consecutive = 0
    for r in all_records:
        if r.season == season or consecutive > 0:
            consecutive += 1
        else:
            break

    if consecutive >= consec_limit or season_total >= season_limit:
        light = 'red'
    elif consecutive >= max(1, consec_limit - 1) or season_total >= max(1, season_limit - 2):
        light = 'yellow'
    else:
        light = 'green'

    return {
        'consecutive': consecutive,
        'season_total': season_total,
        'consec_limit': consec_limit,
        'season_limit': season_limit,
        'penalty_pts': penalty_pts,
        'light': light,
    }


@login_required(login_url='/auth/login/')
def management_sportgericht(request):
    from .models import SupportTicket, InactivityRecord, GameSeasonState, Club

    my_club = current_manager_club(user=request.user)
    # Vereinslose Manager dürfen die Seite sehen (Aktivitätscheck + Support)
    my_manager = my_club.managed_by if my_club else None

    season_state = GameSeasonState.objects.first()
    season = str(season_state.current_season) if season_state else ''

    # ── Aktivitätscheck: nur Manager mit mind. 1 Nichtaufstellung ─────
    _light_order = {'red': 0, 'yellow': 1, 'green': 2}
    all_manager_rows = []
    for club in Club.objects.filter(managed_by__isnull=False).select_related('managed_by'):
        mgr = club.managed_by
        p = _inactivity_status(mgr, 'pro', season)
        u = _inactivity_status(mgr, 'u21', season)
        # Nur anzeigen wenn mind. 1 Nichtaufstellung in der Saison
        if p['season_total'] == 0 and u['season_total'] == 0:
            continue
        worst = min(p['light'], u['light'], key=lambda l: _light_order[l])
        all_manager_rows.append({
            'club': club,
            'manager': mgr,
            'profi': p,
            'u21': u,
            'worst_light': worst,
            'is_own': my_club is not None and club.pk == my_club.pk,
        })
    # Sortierung: rot → gelb → grün, eigener Verein immer ganz oben
    all_manager_rows.sort(key=lambda r: (
        0 if r['is_own'] else 1,
        _light_order[r['worst_light']],
        r['manager'].name,
    ))

    # ── Tickets: nur wenn Manager einem Verein zugewiesen ─────────────
    open_tickets = []
    closed_tickets = []
    if my_manager:
        open_tickets = SupportTicket.objects.filter(
            manager=my_manager,
            status__in=['open', 'in_progress'],
        )
        closed_tickets = SupportTicket.objects.filter(
            manager=my_manager,
            status='closed',
        )[:3]

    my_row = next((r for r in all_manager_rows if r['is_own']), None)

    return render(request, 'game/management/sportgericht.html', {
        'club': my_club,
        'all_manager_rows': all_manager_rows,
        'profi_status': my_row['profi'] if my_row else {},
        'u21_status': my_row['u21'] if my_row else {},
        'open_tickets': open_tickets,
        'closed_tickets': closed_tickets,
        'season': season,
    })


@login_required(login_url='/auth/login/')
def sportgericht_ticket_submit(request):
    """POST: Neues Support-Ticket einreichen."""
    from .models import SupportTicket

    if request.method != 'POST':
        return redirect('management_sportgericht')

    club = current_manager_club(user=request.user)
    if not club:
        messages.error(request, 'Dir ist noch kein Verein zugewiesen.')
        return redirect('management_hub')

    manager = club.managed_by
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    screenshot = request.FILES.get('screenshot')

    if not title or not description:
        messages.error(request, 'Titel und Beschreibung sind Pflichtfelder.')
        return redirect('management_sportgericht')

    ticket = SupportTicket.objects.create(
        manager=manager,
        title=title,
        description=description,
        screenshot=screenshot,
        status='open',
    )
    messages.success(request, f'Ticket #{ticket.pk} wurde erfolgreich eingereicht.')
    return redirect('management_sportgericht')


@login_required(login_url='/auth/login/')
def coin_shop_purchase(request):
    """POST-Handler für den Kauf einer Shop-Aktion mit Hoeneß-Coins."""
    from django.db import transaction as db_transaction
    from .models import HoenessCoin, CoinTransaction

    if request.method != 'POST':
        return redirect('president_office')

    club = current_manager_club(user=request.user)
    if not club or not club.managed_by:
        messages.error(request, 'Dir ist noch kein Verein zugewiesen.')
        return redirect('president_office')

    manager = club.managed_by
    action_key = request.POST.get('action_key', '')

    shop_item = next((s for s in COIN_SHOP if s['key'] == action_key), None)
    if not shop_item:
        messages.error(request, 'Unbekannte Aktion.')
        return redirect('president_office')

    with db_transaction.atomic():
        coin, _ = HoenessCoin.objects.select_for_update().get_or_create(manager=manager)

        if coin.amount < shop_item['cost']:
            messages.error(
                request,
                f'Nicht genug Hoeneß-Coins. Du brauchst {shop_item["cost"]}, hast aber nur {coin.amount}.',
            )
            return redirect('president_office')

        coin.amount -= shop_item['cost']
        coin.save()

        CoinTransaction.objects.create(
            manager=manager,
            amount=-shop_item['cost'],
            reason=shop_item['reason'],
            description=f'{shop_item["label"]} aktiviert für {club.name}',
        )

    messages.success(
        request,
        f'✓ {shop_item["label"]} erfolgreich aktiviert! −{shop_item["cost"]} Hoeneß-Coin.',
    )
    return redirect('president_office')


# ──────────────────────────────────────────────────────────────────────────
#  FINANZEN
# ──────────────────────────────────────────────────────────────────────────

_INCOME_CATS = {
    'ticketverkauf':     ('Ticketverkauf',        '🎟',  'fn-icon-green'),
    'sponsor':           ('Sponsoren',             '🤝',  'fn-icon-amber'),
    'tv_gelder':         ('TV-Gelder',             '📺',  'fn-icon-blue'),
    'transfer_einnahme': ('Transfers',             '💸',  'fn-icon-violet'),
    'leih_einnahme':     ('Leihen',                '🔄',  'fn-icon-teal'),
    'praemie':           ('Prämien',               '🏆',  'fn-icon-amber'),
    'sonstige_einnahme': ('Sonstige',              '➕',  'fn-icon-gray'),
}
_EXPENSE_CATS = {
    'transfer_ausgabe':  ('Transfers',             '💸',  'fn-icon-rose',   '#ef4444'),
    'profigehalt':       ('Profigehälter',         '👕',  'fn-icon-orange', '#f97316'),
    'jugendgehalt':      ('Jugendgehälter',        '🌱',  'fn-icon-teal',   '#14b8a6'),
    'stadionkosten':     ('Stadionkosten',         '🏟',  'fn-icon-blue',   '#3b82f6'),
    'stadionumfeld':     ('Stadionumfeld',         '🔧',  'fn-icon-violet', '#8b5cf6'),
    'sonstige_ausgabe':  ('Sonstiges',             '📌',  'fn-icon-gray',   '#6b7280'),
}


@login_required(login_url='/auth/login/')
def management_finanzen(request):
    import json
    from decimal import Decimal
    from django.core.paginator import Paginator
    from .models import ClubFinancialTransaction, ClubSponsor, GameSeasonState

    club = current_manager_club(user=request.user)
    if not club:
        return redirect('management_hub')

    season_state = GameSeasonState.objects.first()
    season = str(season_state.current_season) if season_state else ''

    # ── Transaktionen ────────────────────────────────────────────────
    all_txs = ClubFinancialTransaction.objects.filter(club=club).order_by('-date', '-created_at')
    season_txs = list(all_txs.filter(season=season))

    total_income  = sum(t.amount for t in season_txs if t.amount  > 0) or Decimal('0')
    total_expenses = abs(sum(t.amount for t in season_txs if t.amount < 0)) or Decimal('0')
    net = total_income - total_expenses

    def _mio(val):
        return f'{float(val)/1_000_000:.1f}'.replace('.', ',')

    def _fmt(val):
        v = float(val)
        if v >= 1_000_000:
            return f'{v/1_000_000:.1f} Mio €'.replace('.', ',')
        if v >= 1_000:
            return f'{v/1_000:.0f} Tsd €'
        return f'{v:,.0f} €'

    # ── Income rows ──────────────────────────────────────────────────
    income_agg = {}
    for t in season_txs:
        if t.amount > 0:
            income_agg[t.category] = income_agg.get(t.category, Decimal('0')) + t.amount

    income_rows = []
    for cat, amt in sorted(income_agg.items(), key=lambda x: -x[1]):
        meta = _INCOME_CATS.get(cat, (cat, '•', 'fn-icon-gray'))
        pct = round(float(amt) / float(total_income) * 100) if total_income else 0
        income_rows.append({
            'label': meta[0], 'icon': meta[1], 'icon_class': meta[2],
            'amount_fmt': _fmt(amt), 'pct': pct,
        })

    # ── Expense rows ─────────────────────────────────────────────────
    expense_agg = {}
    for t in season_txs:
        if t.amount < 0:
            expense_agg[t.category] = expense_agg.get(t.category, Decimal('0')) + abs(t.amount)

    expense_rows = []
    for cat, amt in sorted(expense_agg.items(), key=lambda x: -x[1]):
        meta = _EXPENSE_CATS.get(cat, (cat, '•', 'fn-icon-gray', '#6b7280'))
        pct = round(float(amt) / float(total_expenses) * 100) if total_expenses else 0
        expense_rows.append({
            'label': meta[0], 'icon': meta[1], 'icon_class': meta[2],
            'amount_fmt': _fmt(amt), 'amount': float(amt),
            'chart_color': meta[3], 'pct': pct,
        })

    expense_rows_json = json.dumps([{
        'label': r['label'], 'amount': r['amount'], 'chart_color': r['chart_color'],
    } for r in expense_rows])

    # ── Sponsors ─────────────────────────────────────────────────────
    sponsor_order = {'tv': 0, 'trikot': 1, 'haupt': 2, 'ausrüster': 3, 'sonstig': 4}
    sponsors_raw = list(ClubSponsor.objects.filter(club=club, is_active=True, season=season))
    sponsors_raw.sort(key=lambda s: sponsor_order.get(s.sponsor_type, 9))
    for sp in sponsors_raw:
        sp.amount_mio = f'{float(sp.amount_per_season)/1_000_000:.1f}'.replace('.', ',')

    # ── Kapitalverlauf ───────────────────────────────────────────────
    chart_range = request.GET.get('range', 'season')
    if chart_range == 'complete':
        chart_qs = list(all_txs.order_by('date', 'created_at'))
    elif chart_range == 'last5':
        try:
            s_int = int(season)
            seasons_5 = [str(s_int - i) for i in range(5)]
            chart_qs = list(all_txs.filter(season__in=seasons_5).order_by('date', 'created_at'))
        except (ValueError, TypeError):
            chart_qs = list(all_txs.filter(season=season).order_by('date', 'created_at'))
    else:
        chart_qs = list(all_txs.filter(season=season).order_by('date', 'created_at'))

    chart_net = sum(t.amount for t in chart_qs) if chart_qs else Decimal('0')
    start_balance = club.budget - chart_net
    running = float(start_balance)
    chart_points = []
    if chart_qs:
        chart_points.append({
            'date': chart_qs[0].date.strftime('%d.%m.%Y'),
            'label': 'Saisonbeginn',
            'balance': round(running / 1_000_000, 2),
            'amount': 0,
            'category': '',
        })
    for t in chart_qs:
        running += float(t.amount)
        chart_points.append({
            'date': t.date.strftime('%d.%m.%Y'),
            'label': t.description[:30],
            'balance': round(running / 1_000_000, 2),
            'amount': float(t.amount),
            'category': t.get_category_display(),
        })

    # ── Pagination ───────────────────────────────────────────────────
    PER_PAGE = 10
    MAX_PAGES = 5
    page_num = max(1, min(int(request.GET.get('page', 1)), MAX_PAGES))
    paginator = Paginator(all_txs, PER_PAGE)
    total_pages = min(paginator.num_pages, MAX_PAGES)
    page_obj = paginator.get_page(page_num)
    page_range = list(range(1, total_pages + 1))

    return render(request, 'game/management/finanzen.html', {
        'club':             club,
        'season':           season,
        'budget_mio':       _mio(club.budget),
        'income_mio':       _mio(total_income),
        'expense_mio':      _mio(total_expenses),
        'net_mio':          _mio(abs(net)),
        'net':              net,
        'income_rows':      income_rows,
        'expense_rows':     expense_rows,
        'expense_rows_json': expense_rows_json,
        'sponsors':         sponsors_raw,
        'page_obj':         page_obj,
        'page_num':         page_num,
        'total_pages':      total_pages,
        'page_range':       page_range,
        'chart_range':      chart_range,
        'chart_points_json': json.dumps(chart_points),
    })


@login_required(login_url='/auth/login/')
def management_halloffame(request):
    from datetime import date
    from django.db.models import Sum
    from .models import (
        ManagerCareerStation, PlayerSeasonStat,
        PlayerTransferHistory, ClubTrophy,
    )

    club = current_manager_club(user=request.user)
    today = date.today()

    # ── Dienstältester Manager ────────────────────────────────────────
    longest_manager = None
    if club:
        best, best_days = None, -1
        for s in ManagerCareerStation.objects.filter(club=club).select_related('manager'):
            if not s.started_at:
                continue
            end = s.ended_at if s.ended_at else today
            days = (end - s.started_at).days
            if days > best_days:
                best_days, best = days, s
        if best:
            end_date = best.ended_at if best.ended_at else today
            longest_manager = {
                'name': best.manager.name,
                'days': best_days,
                'started': best.started_at.strftime('%d.%m.%Y'),
                'ended': end_date.strftime('%d.%m.%Y'),
                'active': best.ended_at is None,
            }

    # ── Rekordtorschütze (aktuelle Kader-Spieler dieses Vereins) ─────
    top_scorer = None
    if club:
        row = (
            PlayerSeasonStat.objects
            .filter(player__club=club)
            .values('player__first_name', 'player__last_name')
            .annotate(total=Sum('goals'))
            .order_by('-total')
            .first()
        )
        if row and row['total']:
            top_scorer = {
                'name': f"{row['player__first_name']} {row['player__last_name']}",
                'value': row['total'],
            }

    # ── Rekordspieler (meiste Einsätze) ──────────────────────────────
    most_appearances = None
    if club:
        row = (
            PlayerSeasonStat.objects
            .filter(player__club=club)
            .values('player__first_name', 'player__last_name')
            .annotate(total=Sum('matches'))
            .order_by('-total')
            .first()
        )
        if row and row['total']:
            most_appearances = {
                'name': f"{row['player__first_name']} {row['player__last_name']}",
                'value': row['total'],
            }

    # ── Vereinstitel gesamt ───────────────────────────────────────────
    total_titles = 0
    if club:
        total_titles = (
            ClubTrophy.objects.filter(club=club)
            .aggregate(t=Sum('count'))['t'] or 0
        )

    # ── Größter Transfer (Abgang) ─────────────────────────────────────
    biggest_transfer = None
    if club:
        t = (
            PlayerTransferHistory.objects
            .filter(from_club=club, fee_eur__isnull=False)
            .select_related('player')
            .order_by('-fee_eur')
            .first()
        )
        if t:
            fee_m = t.fee_eur / 1_000_000
            biggest_transfer = {
                'name': f"{t.player.first_name} {t.player.last_name}",
                'value': f"{fee_m:,.0f} Mio. €".replace(',', '.'),
            }

    # ── Meiste Vorlagen ───────────────────────────────────────────────
    most_assists = None
    if club:
        row = (
            PlayerSeasonStat.objects
            .filter(player__club=club)
            .values('player__first_name', 'player__last_name')
            .annotate(total=Sum('assists'))
            .order_by('-total')
            .first()
        )
        if row and row['total']:
            most_assists = {
                'name': f"{row['player__first_name']} {row['player__last_name']}",
                'value': row['total'],
            }

    context = {
        'club': club,
        'longest_manager': longest_manager,
        'top_scorer': top_scorer,
        'most_appearances': most_appearances,
        'most_assists': most_assists,
        'total_titles': total_titles,
        'biggest_transfer': biggest_transfer,
    }
    return render(request, 'game/management/halloffame.html', context)


# ------------------------------------------------------------------ #
#  Job-Angebote — freie Vereine ohne Manager                          #
# ------------------------------------------------------------------ #

@login_required(login_url='/auth/login/')
def management_job_offers(request):
    from .models import Club, SeasonGoal, COUNTRY_FLAG_ASSETS, LeagueStandings, CupSeason
    from .season_goals import current_season_number
    from .services import record_club_assignment

    manager_profile = getattr(request.user, 'manager_profile', None)
    current_club = current_manager_club(user=request.user)

    if request.method == 'POST' and manager_profile:
        try:
            club_id = int(request.POST.get('club_id', 0))
            target_club = Club.objects.get(
                pk=club_id,
                managed_by__isnull=True,
                job_availability_type__in=[Club.JOB_FREE_PICK, Club.JOB_NORMAL, Club.JOB_TOP],
            )
            record_club_assignment(manager_profile, target_club)
            messages.success(request, f'Du hast den Posten bei {target_club.name} angetreten!')
        except Club.DoesNotExist:
            messages.error(request, 'Dieser Verein ist nicht mehr verfügbar.')
        except Exception as exc:
            messages.error(request, f'Bewerbung fehlgeschlagen: {exc}')
        return redirect('management_hub')

    from .models import Player as _Player
    free_clubs_qs = (
        Club.objects
        .filter(
            managed_by__isnull=True,
            job_availability_type__in=[Club.JOB_FREE_PICK, Club.JOB_NORMAL, Club.JOB_TOP],
        )
        .select_related('league', 'stadium', 'public_profile')
        .prefetch_related('cup_participations__competition')
        .order_by('league__country', 'league__name', 'name')
    )

    season = str(current_season_number())

    # Build top-player map: {club_id: Player} — single query, best base_strength per club
    _club_ids = list(free_clubs_qs.values_list('pk', flat=True))
    _top_player_map = {}
    for _p in (
        _Player.objects
        .filter(club_id__in=_club_ids, strength_profile__isnull=False)
        .select_related('strength_profile')
        .order_by('club_id', '-strength_profile__base_strength')
    ):
        _top_player_map.setdefault(_p.club_id, _p)

    # Build standings lookup: {club_id: standing_row}
    standing_map = {}
    standing_qs = LeagueStandings.objects.filter(
        season=season,
        club__in=free_clubs_qs,
    ).select_related('league')
    for s in standing_qs:
        standing_map[s.club_id] = s

    # Collect unique countries and leagues for filter dropdowns
    countries = sorted({c.league.country for c in free_clubs_qs if c.league})
    leagues   = sorted({c.league.name   for c in free_clubs_qs if c.league})

    club_rows = []
    for c in free_clubs_qs:
        stadium = _get_stadium_or_none(c)
        stadium_name     = stadium.name           if stadium else '—'
        stadium_capacity = stadium.capacity_total if stadium else 0

        stadium_img = ''
        try:
            stadium_img = c.public_profile.stadium_image_static_path or ''
        except Exception:
            pass

        flag_code = None
        flag_asset_path = ''
        try:
            entry = COUNTRY_FLAG_ASSETS.get(c.league.country, {})
            flag_code = entry.get('code')
            _aid = entry.get('asset_id', '')
            if _aid:
                flag_asset_path = f'game/images/flags/{_aid}.png'
        except Exception:
            pass

        standing = standing_map.get(c.pk)
        table_pos = standing.position if standing else None
        table_pts = standing.points   if standing else None

        # Determine situation label from table position
        situation_label = ''
        situation_cls   = ''
        if standing and c.league:
            total_teams = c.league.max_teams or 18
            rel = c.league.relegation_spots or 2
            cl  = c.league.cl_spots or 1
            pos = standing.position
            if pos <= cl:
                situation_label = 'Champions League'
                situation_cls   = 'sit-cl'
            elif pos <= (cl + (c.league.el_spots or 1)):
                situation_label = 'Europa League'
                situation_cls   = 'sit-el'
            elif pos >= total_teams - rel + 1:
                situation_label = 'Abstiegskampf'
                situation_cls   = 'sit-rel'
            elif pos >= total_teams - rel - 1:
                situation_label = 'Gefährdete Zone'
                situation_cls   = 'sit-warn'
            elif pos <= 5:
                situation_label = 'Spitzengruppe'
                situation_cls   = 'sit-top'
            else:
                situation_label = 'Mittelfeld'
                situation_cls   = 'sit-mid'

        # Cup participation — collect actual names
        cup_parts = list(c.cup_participations.all())
        club_country = c.league.country if c.league else ''

        national_cups = [
            {'name': cs.competition.name, 'logo': cs.competition.logo_static_path or ''}
            for cs in cup_parts
            if cs.competition.competition_type == 'cup'
            and cs.competition.country == club_country
        ]

        # First matching international competition name + logo
        intl_comp_name = ''
        intl_comp_logo = ''
        for cs in cup_parts:
            n = cs.competition.name.lower()
            if 'champions' in n or 'europa' in n or 'conference' in n:
                intl_comp_name = cs.competition.name
                intl_comp_logo = cs.competition.logo_static_path or ''
                break

        _tp = _top_player_map.get(c.pk)
        club_rows.append({
            'club':              c,
            'stadium_name':      stadium_name,
            'stadium_capacity':  stadium_capacity,
            'stadium_img':       stadium_img,
            'flag_code':         flag_code,
            'flag_asset_path':   flag_asset_path,
            'table_pos':         table_pos,
            'table_pts':         table_pts,
            'situation_label':   situation_label,
            'situation_cls':     situation_cls,
            'league_name':       c.league.name if c.league else '—',
            'league_logo':       c.league.logo_static_path if c.league else '',
            'national_cups':     national_cups,
            'national_cup_names': [x['name'] for x in national_cups],
            'intl_comp_name':    intl_comp_name,
            'intl_comp_logo':    intl_comp_logo,
            'availability':      c.job_availability_type,
            'top_player_name':    _tp.full_name if _tp else '',
            'top_player_portrait': _tp.portrait_static_path if _tp else '',
        })

    return render(request, 'game/management/job_offers.html', {
        'current_club': current_club,
        'club_rows':    club_rows,
        'countries':    countries,
        'leagues':      leagues,
    })


# ── Stadionumfeld (Vereinsumfeld & Stadion-Szene) ─────────────────────────────
# Globale Szene aus dem Replit-Design-Export. Superuser sehen die rechte
# Editor-Leiste (Ecken ziehen, Fans, Tag/Nacht, Slider); ihre Änderungen gelten
# global für ALLE Vereine (ein Singleton). Alle anderen sehen die Szene ohne Leiste.
STADIONUMFELD_ALLOWED_KEYS = {
    'heimspiel', 'tod', 'wetter', 'day', 'capacity',
    'levels', 'building', 'positions', 'badgePos', 'selected',
}


@login_required(login_url='/auth/login/')
def management_stadionumfeld(request):
    club = current_manager_club(user=request.user)
    config = StadionumfeldConfig.get_solo()
    return render(request, 'game/management/stadionumfeld.html', {
        'club':        club,
        'is_admin':    request.user.is_superuser,
        'state_json':  json.dumps(config.state or {}),
        'game_header': build_game_header(
            'Stadionumfeld',
            'Vereinsgelände · 6 Baufelder + Stadion',
            back_url='/management/',
        ),
    })


@login_required(login_url='/auth/login/')
@require_POST
def stadionumfeld_save(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'forbidden'}, status=403)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid json'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'invalid payload'}, status=400)
    clean = {k: v for k, v in payload.items() if k in STADIONUMFELD_ALLOWED_KEYS}
    config = StadionumfeldConfig.get_solo()
    config.state = clean
    config.save(update_fields=['state', 'updated_at'])
    return JsonResponse({'ok': True})


