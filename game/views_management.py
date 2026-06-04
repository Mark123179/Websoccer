import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import MatchdayRevenue, StadiumExpansion
from .stadium_costs import MAX_KAPAZITAET, get_expansion_cost, get_kostenmatrix
from .stadium_revenue import record_matchday_revenue
from .views import current_manager_club


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

    # Tageseinnahmen-Schätzung (basierend auf Auslastungsformel / echten Daten)
    if recent_revenues:
        einnahmen = float(recent_revenues[0].revenue_total)
    else:
        einnahmen = (
            stadium.capacity_standing * auslastung_faktor * float(stadium.price_standing) +
            stadium.capacity_seating  * auslastung_faktor * float(stadium.price_seating)  +
            stadium.capacity_vip      * auslastung_faktor * float(stadium.price_vip)
        )
    saisoneinnahmen = einnahmen * 17

    # ROI: Saisoneinnahmen / Gesamtinvestition aller Ausbauten × 100
    gesamtinvestition = sum(
        ex.cost for ex in stadium.expansions.all()
    ) or Decimal('0')
    roi = round(float(saisoneinnahmen) / float(gesamtinvestition) * 100, 1) \
        if gesamtinvestition > 0 else None

    # Fan-Erlebnis-Werte
    cap = stadium.capacity_total or 1
    standing_ratio = stadium.capacity_standing / cap
    seating_vip_ratio = (stadium.capacity_seating + stadium.capacity_vip) / cap
    lawn = stadium.lawn_quality

    gauge_atmosphaere = min(100, round(standing_ratio * 65 + lawn * 0.35))
    gauge_komfort     = min(100, round(seating_vip_ratio * 70 + lawn * 0.30))

    # Stadionumfeld-Einrichtungen
    facilities = [
        {
            'num': 1, 'key': 'nlz', 'label': 'NLZ',
            'sublabel': 'Nachwuchsleistungszentrum',
            'level': stadium.nlz_level,
            'pin_x': 22, 'pin_y': 18,
        },
        {
            'num': 2, 'key': 'medizin', 'label': 'Medizin',
            'sublabel': 'Medizinische Abteilung',
            'level': stadium.medizin_level,
            'pin_x': 78, 'pin_y': 42,
        },
        {
            'num': 3, 'key': 'training', 'label': 'Trainingsgelände',
            'sublabel': 'Trainingsgelände',
            'level': stadium.training_level,
            'pin_x': 50, 'pin_y': 76,
        },
        {
            'num': 4, 'key': 'office', 'label': 'Geschäftsstelle',
            'sublabel': 'Geschäftsstelle',
            'level': stadium.office_level,
            'pin_x': 20, 'pin_y': 64,
        },
    ]

    return render(request, 'game/management/stadium.html', {
        'club':                  club,
        'stadium':               stadium,
        'stands':                stands,
        'expansions':            expansions,
        'revenue_entries':       revenue_entries,
        'kostenmatrix_json':     json.dumps(kostenmatrix),
        'facilities':            facilities,
        'max_kapazitaet':        MAX_KAPAZITAET,
        'einnahmen_schaetzung':  einnahmen,
        'saisoneinnahmen':       saisoneinnahmen,
        'roi':                   roi,
        'gauge_auslastung':      gauge_auslastung,
        'gauge_atmosphaere':     gauge_atmosphaere,
        'gauge_komfort':         gauge_komfort,
        'hat_echte_auslastung':  bool(recent_revenues),
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

    try:
        p_steh = float(request.POST['price_standing'])
        p_sitz = float(request.POST['price_seating'])
        p_vip  = float(request.POST['price_vip'])
    except (KeyError, ValueError):
        messages.error(request, 'Ungültige Preiseingabe.')
        return redirect('stadium_detail')

    if any(p < 0 for p in (p_steh, p_sitz, p_vip)):
        messages.error(request, 'Ticketpreise dürfen nicht negativ sein.')
        return redirect('stadium_detail')
    if p_vip < p_sitz or p_sitz < p_steh:
        messages.warning(request, 'Hinweis: VIP-Preise sollten höher als Sitz- und Stehpreise sein.')

    from decimal import Decimal
    stadium.price_standing = Decimal(str(round(p_steh, 2)))
    stadium.price_seating  = Decimal(str(round(p_sitz, 2)))
    stadium.price_vip      = Decimal(str(round(p_vip, 2)))
    stadium.save(update_fields=['price_standing', 'price_seating', 'price_vip'])
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
