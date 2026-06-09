import os
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    Club, COUNTRY_FLAG_ASSETS, DataSource, League, Player,
    PlayerSourceRating, PlayerStrengthProfile, PlayerFormSnapshot, Stadium,
    ClubPublicProfile, ClubTrophy, ClubSponsor,
    SeasonGoal, ManagerProfile, ManagerCareerStation, HoenessCoin,
    CoinTransaction, PresidentSatisfaction, TacticSetup,
    PlayerEditLog, PlayerRLFormProfile,
)
from . import strength_engine as se
from .strength_service import compute_strength_for_player, compute_rl_form_for_player
from .management.commands.import_player_source_ratings import (
    FMI_ATTR_MAP, FMI_GK_MAP, SOFIFA_ATTR_MAP, SOFIFA_GK_MAP,
)

# Welche Attributspalten liefert welche Quelle (FMInside vs. SoFIFA)?
FM_OUTFIELD_COLS = set(FMI_ATTR_MAP.values())
EA_OUTFIELD_COLS = set(SOFIFA_ATTR_MAP.values())
FM_GK_COLS = set(FMI_GK_MAP.values())
EA_GK_COLS = set(SOFIFA_GK_MAP.values())

# Anzeige-Reihenfolge + deutsche Labels der Quell-Attribute.
SOURCE_OUTFIELD_LABELS = [
    ('tempo', 'Tempo'),
    ('ausdauer', 'Ausdauer'),
    ('kraft', 'Kraft'),
    ('technik', 'Technik'),
    ('dribbling', 'Dribbling'),
    ('passspiel', 'Passspiel'),
    ('flanken', 'Flanken'),
    ('abschluss', 'Abschluss'),
    ('kopfball', 'Kopfball'),
    ('zweikampf', 'Zweikampf'),
    ('defensivstellung', 'Defensivstellung'),
    ('uebersicht', 'Übersicht'),
    ('teamwork', 'Teamwork'),
    ('ecken', 'Ecken'),
    ('freistoss', 'Freistoß'),
    ('elfmeter', 'Elfmeter'),
]
SOURCE_GK_LABELS = [
    ('tw_reflexe', 'Reflexe'),
    ('tw_fangsicherheit', 'Fangsicherheit'),
    ('tw_eins_gegen_eins', '1-gegen-1'),
    ('tw_stellungsspiel', 'Stellungsspiel'),
    ('tw_passen', 'Passen'),
]
# Quell-Key (PlayerSourceRating.source) -> DataSource-Code fuer ExternalId-Sync.
SOURCE_DATASOURCE_CODE = {
    PlayerSourceRating.SOURCE_FM: DataSource.CODE_FMINSIDE,
    PlayerSourceRating.SOURCE_EA: DataSource.CODE_SOFIFA,
}


def _parse_source_int(raw, hi):
    """Parse einen Attributwert; '' -> None, sonst auf 0..hi geklemmt."""
    raw = (raw or '').strip()
    if raw == '':
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return max(0, min(hi, value))


def _save_player_source_ratings(request, player):
    """Speichert die im Creator-Source-Tab editierten Quelldaten."""
    is_gk = player.position == 'TW'
    specs = [
        ('fm', PlayerSourceRating.SOURCE_FM,
         FM_GK_COLS if is_gk else FM_OUTFIELD_COLS),
        ('ea', PlayerSourceRating.SOURCE_EA,
         EA_GK_COLS if is_gk else EA_OUTFIELD_COLS),
    ]
    existing = {r.source: r for r in player.source_ratings.all()}

    for prefix, source_key, cols in specs:
        row = existing.get(source_key)
        # Snapshot BEFORE any in-place modifications (row object is mutated below)
        _snap_r = row.rating if row else None
        _snap_p = row.potential if row else None
        _is_new = (row is None)

        rating = _parse_source_int(request.POST.get(f'src_{prefix}_rating'), 100)
        if rating is None:
            # Rating ist Pflichtfeld: ohne vorhandene Zeile nichts anlegen.
            if row is None:
                continue
        else:
            if row is None:
                row = PlayerSourceRating(
                    player=player, source=source_key, rating=rating,
                )
            else:
                row.rating = rating

        row.potential = _parse_source_int(
            request.POST.get(f'src_{prefix}_potential'), 100,
        )
        for col in cols:
            setattr(
                row, col,
                _parse_source_int(request.POST.get(f'src_{prefix}_{col}'), 99),
            )

        url = (request.POST.get(f'src_{prefix}_url') or '').strip()
        row.source_url = url
        row.save()

        # --- Geschichte-Log: Source-Ratings ---
        src_label = 'FM Inside' if source_key == PlayerSourceRating.SOURCE_FM else 'EA FC'
        src_lines = []
        if _is_new:
            src_lines.append(f'{src_label}: Quelldaten erstmals angelegt (Rating {row.rating})')
        else:
            if _snap_r != row.rating:
                src_lines.append(f'{src_label} Rating: {_snap_r if _snap_r is not None else "–"} → {row.rating}')
            if _snap_p != row.potential:
                src_lines.append(f'{src_label} Potential: {_snap_p if _snap_p is not None else "–"} → {row.potential}')
        if src_lines:
            _log_user = request.user if request.user.is_authenticated else None
            PlayerEditLog.objects.create(
                player=player, changed_by=_log_user,
                category=PlayerEditLog.CATEGORY_SOURCE,
                summary='\n'.join(src_lines),
            )

        # Kanonische externe ID konsistent halten (nur falls schon vorhanden).
        ext = player.external_ids.filter(
            source__code=SOURCE_DATASOURCE_CODE[source_key],
        ).first()
        if ext and ext.profile_url != url:
            ext.profile_url = url
            ext.save(update_fields=['profile_url', 'updated_at'])

    # Transfermarkt-Link direkt am Spieler.
    player.transfermarkt_profile_url = (
        request.POST.get('tm_url') or ''
    ).strip()
    player.save(update_fields=['transfermarkt_profile_url'])


def _build_source_tab_context(player):
    """Baut die GET-Anzeige fuer den Source-Tab (2 Quellen nebeneinander)."""
    is_gk = player.position == 'TW'
    labels = SOURCE_GK_LABELS if is_gk else SOURCE_OUTFIELD_LABELS
    fm_cols = FM_GK_COLS if is_gk else FM_OUTFIELD_COLS
    ea_cols = EA_GK_COLS if is_gk else EA_OUTFIELD_COLS

    rows = {r.source: r for r in player.source_ratings.all()}
    fm_row = rows.get(PlayerSourceRating.SOURCE_FM)
    ea_row = rows.get(PlayerSourceRating.SOURCE_EA)

    attr_rows = []
    for col, label in labels:
        attr_rows.append({
            'col': col,
            'label': label,
            'fm_supported': col in fm_cols,
            'ea_supported': col in ea_cols,
            'fm_value': getattr(fm_row, col) if fm_row else None,
            'ea_value': getattr(ea_row, col) if ea_row else None,
        })

    source_meta = {
        'fm': {
            'rating': fm_row.rating if fm_row else None,
            'potential': fm_row.potential if fm_row else None,
            'url': fm_row.source_url if fm_row else '',
        },
        'ea': {
            'rating': ea_row.rating if ea_row else None,
            'potential': ea_row.potential if ea_row else None,
            'url': ea_row.source_url if ea_row else '',
        },
    }
    return {
        'source_attr_rows': attr_rows,
        'source_meta': source_meta,
        'source_is_gk': is_gk,
    }

def _build_strength_tab_context(player):
    """
    Berechnet den vollständigen Stärke-Berechnungsweg für den Creator-Tab.
    Nur lesend – keine DB-Schreiboperationen.
    """
    is_gk = player.position == 'TW'

    # ── Quell-Ratings abrufen ───────────────────────────────────────────────
    rows = {r.source: r for r in player.source_ratings.all()}
    fm_row = rows.get(PlayerSourceRating.SOURCE_FM)
    ea_row = rows.get(PlayerSourceRating.SOURCE_EA)

    fmi_rating    = fm_row.rating    if fm_row else None
    fmi_potential = fm_row.potential if fm_row else None
    ea_rating     = ea_row.rating    if ea_row else None
    ea_potential  = ea_row.potential if ea_row else None

    # ── Basis & Potential (0–200) ────────────────────────────────────────────
    base_200 = se.calculate_base_200(fmi_rating, ea_rating)
    potential_200 = se.calculate_potential_200(fmi_potential, ea_potential, base_200)
    gap = (potential_200 - base_200) if (potential_200 is not None and base_200 is not None) else None
    constancy_label = se.get_constancy_label(gap)

    # ── Kombinierte Attribute (nur Berechnungs-relevante Attrs: 13 Feld / 5 TW) ─
    # Ecken, Freistoß, Elfmeter fließen in kein Positionsprofil ein → nicht hier.
    STR_OUTFIELD_LABELS = [
        ('tempo',          'Tempo'),
        ('ausdauer',       'Ausdauer'),
        ('kraft',          'Kraft'),
        ('technik',        'Technik'),
        ('dribbling',      'Dribbling'),
        ('passspiel',      'Passspiel'),
        ('flanken',        'Flanken'),
        ('abschluss',      'Abschluss'),
        ('kopfball',       'Kopfball'),
        ('zweikampf',      'Zweikampf'),
        ('defensivstellung', 'Defensivstellung'),
        ('uebersicht',     'Übersicht'),
        ('teamwork',       'Teamwork'),
    ]
    if is_gk:
        attr_cols = [col for col, _ in SOURCE_GK_LABELS]
        attr_labels = {col: lbl for col, lbl in SOURCE_GK_LABELS}
    else:
        attr_cols = [col for col, _ in STR_OUTFIELD_LABELS]
        attr_labels = {col: lbl for col, lbl in STR_OUTFIELD_LABELS}

    def _row_attrs(row, cols):
        if row is None:
            return {c: None for c in cols}
        return {c: getattr(row, c, None) for c in cols}

    fmi_attrs = _row_attrs(fm_row, attr_cols)
    ea_attrs  = _row_attrs(ea_row,  attr_cols)

    combined_attrs = se.get_combined_attributes(fmi_attrs, ea_attrs, attr_cols)
    combined_attrs_dict = {a['col']: a['combined'] for a in combined_attrs}

    for a in combined_attrs:
        a['label'] = attr_labels.get(a['col'], a['col'])

    # ── Positionsprofile ────────────────────────────────────────────────────
    main_positions = player.main_positions
    secondary_positions = player.secondary_positions
    # HP1 aus main_positions für Profil-Hervorhebung in der Tabelle
    hp1 = main_positions[0] if main_positions else ''
    hp1_profile_key = se.POSITION_TO_PROFILE.get(hp1)
    # played_pos = registrierte Spielposition (kann von HP1 abweichen)
    played_pos = player.position or hp1

    profile_rows = []
    for pkey in se.PROFILE_KEYS_ORDERED:
        score = se.get_position_profile(combined_attrs_dict, pkey)
        profile_rows.append({
            'key':             pkey,
            'label':           se.PROFILE_LABELS[pkey],
            'score':           round(score, 2) if score is not None else None,
            'is_primary':      pkey == hp1_profile_key,
            'is_secondary':    any(
                se.POSITION_TO_PROFILE.get(p) == pkey
                for p in secondary_positions
            ),
        })

    # Profil-Score für die Stärke-Range: basiert auf played_pos, nicht HP1
    played_profile_key = se.POSITION_TO_PROFILE.get(played_pos)
    played_profile_score = se.get_position_profile(combined_attrs_dict, played_profile_key) if played_profile_key else None

    # ── Positions-Fit ────────────────────────────────────────────────────────
    # Vergleicht registrierte Spielposition mit den natürlichen Positionen
    pos_fit_factor, pos_fit_label, pos_unknown = se.get_position_fit(
        played_pos, main_positions, secondary_positions,
    )

    # ── Frische-Fit ─────────────────────────────────────────────────────────
    try:
        sp = player.strength_profile
        freshness_val = float(sp.freshness) if sp.freshness is not None else None
    except PlayerStrengthProfile.DoesNotExist:
        freshness_val = None

    freshness_factor, freshness_range_label = se.get_freshness_fit(freshness_val)

    # ── RL-Form ──────────────────────────────────────────────────────────────
    # no_mapping vs. no_data klar trennen:
    # no_mapping=True → kein API-Football-Mapping → score=0, factor=1.00 (keine Strafe)
    # no_data=True    → Mapping vorhanden, keine Einsätze → score=−2 (korrekte Strafe)
    api_qs = player.form_snapshots.filter(source=PlayerFormSnapshot.SOURCE_API_FOOTBALL)
    has_api_mapping = api_qs.exists()
    snapshots_data = [
        {'rating': s.rating, 'minutes_played': s.minutes_played}
        for s in api_qs.order_by('-fixture_date')[:10]
    ]
    rl_form_result = se.calculate_rl_form_from_snapshots(
        snapshots_data, no_mapping=not has_api_mapping
    )
    rl_form_factor = se.get_rl_form_fit(rl_form_result['score'])
    rl_form_result['factor'] = rl_form_factor
    rl_form_result['match_count'] = len(snapshots_data)
    rl_form_result['score_label'] = f'{rl_form_result["score"]:+d}'

    # ── Per-Profil Fit + Effektive Range (zweiter Durchlauf, nach allen Fits) ─
    sec_profile_set = {
        se.POSITION_TO_PROFILE.get(p)
        for p in secondary_positions if p
    } - {None}

    for row in profile_rows:
        pkey = row['key']
        if is_gk and pkey != 'TW':
            row['fit_factor'] = 0.30
            row['fit_pct'] = '30 %'
        elif not is_gk and pkey == 'TW':
            row['fit_factor'] = 0.25
            row['fit_pct'] = '25 %'
        elif row['is_primary']:
            row['fit_factor'] = 1.00
            row['fit_pct'] = '100 %'
        elif pkey in sec_profile_set:
            row['fit_factor'] = 0.90
            row['fit_pct'] = '90 %'
        else:
            row['fit_factor'] = 0.70
            row['fit_pct'] = '70 %'

        if base_200 is not None and row['score'] is not None:
            r_min, r_max = se.get_strength_range(
                base_200, potential_200, row['score'],
                row['fit_factor'], freshness_factor, rl_form_factor,
            )
        else:
            r_min, r_max = None, None
        row['range_min'] = r_min
        row['range_max'] = r_max

    # ── Stärke-Range ────────────────────────────────────────────────────────
    # Unbekannte Position → kein stilles Fallback; Range explizit nicht berechenbar
    if pos_fit_factor is not None:
        str_min, str_max = se.get_strength_range(
            base_200, potential_200, played_profile_score,
            pos_fit_factor,
            freshness_factor,
            rl_form_factor,
        )
    else:
        str_min, str_max = None, None

    # ── Sync-Status: gespeicherter Profilwert vs. Engine-Berechnung ─────────
    stored_profile = getattr(player, 'strength_profile', None)
    if stored_profile is not None:
        stored_base  = float(stored_profile.base_strength)
        stored_final = float(stored_profile.final_strength)
        stored_at    = stored_profile.updated_at
        if base_200 is not None:
            sync_delta = abs(stored_base - base_200)
            if sync_delta <= 2:
                sync_status = 'ok'
            elif sync_delta <= 10:
                sync_status = 'warn'
            else:
                sync_status = 'danger'
        else:
            sync_delta = None
            sync_status = 'no_engine_data'
    else:
        stored_base  = None
        stored_final = None
        stored_at    = None
        sync_delta   = None
        sync_status  = 'no_profile'

    return {
        'str_base': {
            'fmi':      fmi_rating,
            'ea':       ea_rating,
            'combined': base_200,
        },
        'str_potential': {
            'fmi':            fmi_potential,
            'ea':             ea_potential,
            'combined':       potential_200,
            'gap':            gap,
            'constancy_label': constancy_label,
        },
        'str_combined_attrs':  combined_attrs,
        'str_profile_rows':    profile_rows,
        'str_position_fit': {
            'pos':            played_pos,
            'profile_key':    played_profile_key or '?',
            'profile_label':  se.PROFILE_LABELS.get(played_profile_key, '?'),
            'factor':         pos_fit_factor,
            'label':          pos_fit_label,
            'unknown':        pos_unknown,
        },
        'str_freshness': {
            'value':       freshness_val,
            'factor':      freshness_factor,
            'range_label': freshness_range_label,
            'no_data':     freshness_val is None,
        },
        'str_rl_form':  rl_form_result,
        'str_range': {
            'min':         str_min,
            'max':         str_max,
            'computable':  str_min is not None,
        },
        'str_sync': {
            'stored_base':  stored_base,
            'stored_final': stored_final,
            'stored_at':    stored_at,
            'delta':        round(sync_delta, 1) if sync_delta is not None else None,
            'status':       sync_status,
        },
    }


STATIC_BASE = 'game/static'
POSITION_CHOICES = [
    ('', '----------'),
    ('TW', 'TW'), ('IV', 'IV'), ('LI', 'LI'), ('LV', 'LV'),
    ('RV', 'RV'), ('LOV', 'LOV'), ('ROV', 'ROV'), ('DM', 'DM'),
    ('ZM', 'ZM'), ('LM', 'LM'), ('RM', 'RM'), ('LOM', 'LOM'),
    ('ROM', 'ROM'), ('OM', 'OM'), ('LF', 'LF'), ('RF', 'RF'), ('ST', 'ST'),
]
NATIONALITY_CHOICES = [''] + sorted(COUNTRY_FLAG_ASSETS.keys())


def _static_file_path(rel_path):
    full = os.path.join(STATIC_BASE, rel_path)
    return rel_path if os.path.exists(full) else ''


def _save_as_jpg(file_obj, dest_path):
    from PIL import Image as PILImage
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    img = PILImage.open(file_obj).convert('RGB')
    img.save(dest_path, 'JPEG', quality=90)


def _save_as_png(file_obj, dest_path):
    from PIL import Image as PILImage
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    img = PILImage.open(file_obj).convert('RGBA')
    img.save(dest_path, 'PNG')


def creator_index(request):
    country_filter = request.GET.get('country', '').strip()
    league_filter = request.GET.get('league', '').strip()

    # ── Level 3: Vereine einer Liga ──────────────────────────────────────────
    if league_filter:
        league = get_object_or_404(League, id=league_filter)
        clubs = list(league.club_set.order_by('name'))
        flag_code = (
            COUNTRY_FLAG_ASSETS.get(league.country or '', {}).get('code', '').lower()
        )
        return render(request, 'creator/index.html', {
            'level': 3,
            'league': league,
            'clubs': clubs,
            'country': league.country,
            'flag_code': flag_code,
        })

    # ── Level 2: Ligen eines Landes ──────────────────────────────────────────
    if country_filter:
        leagues_qs = League.objects.filter(country=country_filter).order_by('name')
        flag_code = (
            COUNTRY_FLAG_ASSETS.get(country_filter, {}).get('code', '').lower()
        )
        leagues_data = []
        for lg in leagues_qs:
            leagues_data.append({
                'league': lg,
                'club_count': lg.club_set.count(),
            })
        return render(request, 'creator/index.html', {
            'level': 2,
            'country': country_filter,
            'flag_code': flag_code,
            'leagues_data': leagues_data,
        })

    # ── Level 1: Länder ───────────────────────────────────────────────────────
    from django.db.models import Count
    country_rows = (
        League.objects
        .values('country')
        .annotate(league_count=Count('id'))
        .order_by('country')
    )
    countries_data = []
    for row in country_rows:
        name = row['country'] or 'Unbekannt'
        code = COUNTRY_FLAG_ASSETS.get(name, {}).get('code', '').lower()
        countries_data.append({
            'name': name,
            'code': code,
            'league_count': row['league_count'],
        })
    return render(request, 'creator/index.html', {
        'level': 1,
        'countries_data': countries_data,
        'total_clubs': Club.objects.count(),
        'total_players': Player.objects.count(),
    })


def creator_club_edit(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)

    players = Player.objects.filter(club=club).order_by('last_name', 'first_name')

    kits = []
    for kit_type, label in [('home', 'Heim'), ('away', 'Auswärts'), ('third', 'Third')]:
        found_path = None
        for ext in ['png', 'svg']:
            rel = f'game/images/kits/{club.fm_inside_id}_{kit_type}.{ext}'
            if os.path.exists(os.path.join(STATIC_BASE, rel)):
                found_path = rel
                break
        kits.append({'type': kit_type, 'label': label, 'path': found_path})

    stadium_path = _static_file_path(profile.stadium_image_static_path) if profile.stadium_image_static_path else ''
    city_path = _static_file_path(profile.city_image_static_path) if profile.city_image_static_path else ''
    crest_path = club.crest_static_path

    try:
        stadium = club.stadium
    except Stadium.DoesNotExist:
        stadium = None

    trophies = ClubTrophy.objects.filter(club=club).order_by('sort_order', 'competition_name')
    sponsors = ClubSponsor.objects.filter(club=club).order_by('sponsor_type', 'name')
    goals = SeasonGoal.objects.filter(club=club).order_by('-season_number')
    all_clubs = Club.objects.exclude(id=club_id).order_by('name')

    active_tab = request.GET.get('tab', 'bilder')

    return render(request, 'creator/club_edit.html', {
        'club': club,
        'profile': profile,
        'players': players,
        'kits': kits,
        'stadium_path': stadium_path,
        'city_path': city_path,
        'crest_path': crest_path,
        'stadium': stadium,
        'trophies': trophies,
        'sponsors': sponsors,
        'goals': goals,
        'all_clubs': all_clubs,
        'active_tab': active_tab,
        'all_leagues': League.objects.order_by('name'),
        'sponsor_type_choices': ClubSponsor.TYPE_CHOICES,
        'goal_tier_choices': SeasonGoal.TIER_CHOICES,
    })


@require_POST
def creator_upload_stadium(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect('creator_club_edit', club_id=club_id)
    rel = f'game/images/stadiums/germany/{club.fm_inside_id}.jpg'
    _save_as_jpg(f, os.path.join(STATIC_BASE, rel))
    profile.stadium_image_static_path = rel
    profile.save(update_fields=['stadium_image_static_path'])
    messages.success(request, 'Stadionbild gespeichert.')
    return redirect('creator_club_edit', club_id=club_id)


@require_POST
def creator_upload_city(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    ClubPublicProfile = apps.get_model('game', 'ClubPublicProfile')
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect('creator_club_edit', club_id=club_id)
    rel = f'game/images/city/{club.fm_inside_id}.jpg'
    _save_as_jpg(f, os.path.join(STATIC_BASE, rel))
    profile.city_image_static_path = rel
    profile.save(update_fields=['city_image_static_path'])
    messages.success(request, 'Citypic gespeichert.')
    return redirect('creator_club_edit', club_id=club_id)


@require_POST
def creator_upload_kit(request, club_id, kit_type):
    club = get_object_or_404(Club, id=club_id)
    if kit_type not in ['home', 'away', 'third']:
        messages.error(request, 'Ungültiger Trikot-Typ.')
        return redirect('creator_club_edit', club_id=club_id)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect('creator_club_edit', club_id=club_id)
    for ext in ['png', 'svg', 'jpg', 'webp']:
        old = os.path.join(STATIC_BASE, f'game/images/kits/{club.fm_inside_id}_{kit_type}.{ext}')
        if os.path.exists(old):
            os.remove(old)
    dest = os.path.join(STATIC_BASE, f'game/images/kits/{club.fm_inside_id}_{kit_type}.png')
    _save_as_png(f, dest)
    messages.success(request, f'Trikot ({kit_type}) gespeichert.')
    return redirect('creator_club_edit', club_id=club_id)


@require_POST
def creator_upload_crest(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect('creator_club_edit', club_id=club_id)
    for ext in ['png', 'svg', 'jpg', 'webp']:
        old = os.path.join(STATIC_BASE, f'game/images/crests/{club.fm_inside_id}.{ext}')
        if os.path.exists(old):
            os.remove(old)
    dest = os.path.join(STATIC_BASE, f'game/images/crests/{club.fm_inside_id}.png')
    _save_as_png(f, dest)
    messages.success(request, 'Vereinswappen gespeichert.')
    return redirect('creator_club_edit', club_id=club_id)


@login_required
@require_POST
def creator_upload_league_logo(request, league_id):
    league = get_object_or_404(League, id=league_id)
    f = request.FILES.get('image')
    if not f:
        messages.error(request, 'Keine Datei ausgewählt.')
        return redirect(f'/creator/leagues/{league_id}/?tab=stammdaten')
    if league.logo_static_path:
        old = os.path.join(STATIC_BASE, league.logo_static_path)
        if os.path.exists(old):
            os.remove(old)
    dest = os.path.join(STATIC_BASE, f'game/images/competitions/{league_id}.png')
    _save_as_png(f, dest)
    league.logo_static_path = f'game/images/competitions/{league_id}.png'
    league.save(update_fields=['logo_static_path'])
    messages.success(request, 'Liga-Logo gespeichert.')
    return redirect(f'/creator/leagues/{league_id}/?tab=stammdaten')


def _write_edit_log(player, user, category, summary):
    """Schreibt einen Eintrag in PlayerEditLog."""
    PlayerEditLog.objects.create(
        player=player,
        changed_by=user if user and user.is_authenticated else None,
        category=category,
        summary=summary,
    )


def _build_geschichte_tab_context(player):
    """Letzte 150 Änderungseinträge für den Geschichte-Tab."""
    logs = (
        player.edit_logs
        .select_related('changed_by')
        .order_by('-changed_at')[:150]
    )
    return {'edit_logs': list(logs)}


def _build_rl_form_tab_context(player):
    """Kontext für den RL-Form-Tab (API-Football-Daten)."""
    try:
        rl_profile = player.rl_form_profile
    except PlayerRLFormProfile.DoesNotExist:
        rl_profile = None

    snapshots = list(
        player.form_snapshots
        .filter(source=PlayerFormSnapshot.SOURCE_API_FOOTBALL)
        .order_by('-fixture_date')[:10]
    )

    snapshots_data = [
        {'rating': s.rating, 'minutes_played': s.minutes_played}
        for s in snapshots
    ]
    has_mapping = bool(
        rl_profile
        and rl_profile.api_football_player_id
        and rl_profile.api_football_team_id
    )
    breakdown = se.calculate_rl_form_from_snapshots(
        snapshots_data, no_mapping=not has_mapping
    )

    fit_factor = se.get_rl_form_fit(breakdown['score'])

    from .api_football import get_today_usage, DAILY_LIMIT, WARN_THRESHOLD
    api_usage_today = get_today_usage()

    return {
        'rl_profile':       rl_profile,
        'rl_snapshots':     snapshots,
        'rl_breakdown':     breakdown,
        'rl_fit_factor':    fit_factor,
        'rl_form_scale':    se.RL_FORM_SCALE,
        'rl_form_fit':      se.RL_FORM_FIT,
        'api_usage_today':  api_usage_today,
        'api_daily_limit':  DAILY_LIMIT,
        'api_warn_threshold': WARN_THRESHOLD,
    }


def creator_player_edit(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    all_clubs = Club.objects.order_by('name')

    if request.method == 'POST':
        # --- Snapshot vor Änderungen (für Geschichte-Log) ---
        _old = {
            'first_name':   player.first_name,
            'last_name':    player.last_name,
            'club':         player.club.name if player.club_id else '',
            'rl_club':      player.real_life_club.name if player.real_life_club_id else '',
            'dob':          str(player.date_of_birth or ''),
            'height_cm':    str(player.height_cm or ''),
            'nationalities': player.nationalities or '',
            'strong_foot':  player.strong_foot or '',
            'market_value': str(player.market_value or ''),
            'salary':       str(player.salary_per_match or ''),
            'contract':     str(player.contract_until or ''),
            'main_pos':     [player.main_position_1 or '', player.main_position_2 or '', player.main_position_3 or ''],
            'sec_pos':      [player.secondary_position_1 or '', player.secondary_position_2 or '', player.secondary_position_3 or ''],
            'injury_type':  player.ws_injury_type or '',
            'injury_days':  str(player.ws_injury_days_remaining or 0),
            'suspension':   player.ws_suspension_reason or '',
            'sus_matches':  str(player.ws_suspension_matches_remaining or 0),
        }

        player.first_name = request.POST.get('first_name', player.first_name).strip()
        player.last_name = request.POST.get('last_name', player.last_name).strip()

        club_id = request.POST.get('club')
        if club_id:
            try:
                player.club = Club.objects.get(id=int(club_id))
            except Club.DoesNotExist:
                pass

        rl_club_id = request.POST.get('real_life_club')
        if rl_club_id:
            try:
                player.real_life_club = Club.objects.get(id=int(rl_club_id))
            except Club.DoesNotExist:
                pass
        elif rl_club_id == '':
            player.real_life_club = None

        for field in ['main_position_1', 'main_position_2', 'main_position_3',
                      'secondary_position_1', 'secondary_position_2', 'secondary_position_3',
                      'strong_foot']:
            val = request.POST.get(field, '')
            setattr(player, field, val)

        dob = request.POST.get('date_of_birth', '')
        if dob:
            from datetime import date as date_type
            try:
                from datetime import datetime
                player.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
                from datetime import date
                today = date.today()
                player.age = today.year - player.date_of_birth.year - (
                    (today.month, today.day) < (player.date_of_birth.month, player.date_of_birth.day)
                )
            except ValueError:
                pass

        height = request.POST.get('height_cm', '')
        if height:
            try:
                player.height_cm = int(height)
            except ValueError:
                pass

        nat1 = request.POST.get('nationality_1', '').strip()
        nat2 = request.POST.get('nationality_2', '').strip()
        nats = [n for n in [nat1, nat2] if n]
        player.nationalities = ','.join(nats)

        for dec_field in ['market_value', 'salary_per_match']:
            val = request.POST.get(dec_field, '').strip().replace(',', '.')
            if val:
                try:
                    setattr(player, dec_field, Decimal(val))
                except InvalidOperation:
                    pass

        contract = request.POST.get('contract_until', '')
        if contract:
            try:
                from datetime import datetime
                player.contract_until = datetime.strptime(contract, '%Y-%m-%d').date()
            except (ValueError, AttributeError):
                pass

        player.ws_injury_type = request.POST.get('ws_injury_type', '').strip()
        try:
            player.ws_injury_days_remaining = int(request.POST.get('ws_injury_days_remaining', 0))
        except ValueError:
            pass

        player.ws_suspension_reason = request.POST.get('ws_suspension_reason', '').strip()
        try:
            player.ws_suspension_matches_remaining = int(request.POST.get('ws_suspension_matches_remaining', 0))
        except ValueError:
            pass

        player.save()

        # --- Geschichte-Log: Diff per Kategorie ---
        _new_name = f'{player.first_name} {player.last_name}'
        _old_name = f'{_old["first_name"]} {_old["last_name"]}'
        _profil_lines = []
        if _new_name != _old_name:
            _profil_lines.append(f'Name: {_old_name} → {_new_name}')
        if str(player.date_of_birth or '') != _old['dob']:
            _profil_lines.append(f'Geburtsdatum: {_old["dob"] or "–"} → {player.date_of_birth or "–"}')
        if str(player.height_cm or '') != _old['height_cm']:
            _profil_lines.append(f'Größe: {_old["height_cm"] or "–"} cm → {player.height_cm or "–"} cm')
        if (player.nationalities or '') != _old['nationalities']:
            _profil_lines.append(f'Nationalität: {_old["nationalities"] or "–"} → {player.nationalities or "–"}')
        if (player.strong_foot or '') != _old['strong_foot']:
            _profil_lines.append(f'Starker Fuß: {_old["strong_foot"] or "–"} → {player.strong_foot or "–"}')
        if _profil_lines:
            _write_edit_log(player, request.user, PlayerEditLog.CATEGORY_PROFIL, '\n'.join(_profil_lines))

        _verein_lines = []
        _new_club = player.club.name if player.club_id else ''
        _new_rl_club = player.real_life_club.name if player.real_life_club_id else ''
        if _new_club != _old['club']:
            _verein_lines.append(f'WS-Verein: {_old["club"] or "–"} → {_new_club or "–"}')
        if _new_rl_club != _old['rl_club']:
            _verein_lines.append(f'RL-Verein: {_old["rl_club"] or "–"} → {_new_rl_club or "–"}')
        if str(player.market_value or '') != _old['market_value']:
            _verein_lines.append(f'Marktwert: {_old["market_value"] or "–"} → {player.market_value or "–"} €')
        if str(player.salary_per_match or '') != _old['salary']:
            _verein_lines.append(f'Gehalt: {_old["salary"] or "–"} → {player.salary_per_match or "–"} €')
        if str(player.contract_until or '') != _old['contract']:
            _verein_lines.append(f'Vertrag bis: {_old["contract"] or "–"} → {player.contract_until or "–"}')
        if _verein_lines:
            _write_edit_log(player, request.user, PlayerEditLog.CATEGORY_VEREIN, '\n'.join(_verein_lines))

        _new_main = [player.main_position_1 or '', player.main_position_2 or '', player.main_position_3 or '']
        _new_sec  = [player.secondary_position_1 or '', player.secondary_position_2 or '', player.secondary_position_3 or '']
        _pos_lines = []
        if _new_main != _old['main_pos']:
            _pos_lines.append(
                f'HP: {"/".join(p for p in _old["main_pos"] if p) or "–"} → '
                f'{"/".join(p for p in _new_main if p) or "–"}'
            )
        if _new_sec != _old['sec_pos']:
            _pos_lines.append(
                f'NP: {"/".join(p for p in _old["sec_pos"] if p) or "–"} → '
                f'{"/".join(p for p in _new_sec if p) or "–"}'
            )
        if _pos_lines:
            _write_edit_log(player, request.user, PlayerEditLog.CATEGORY_POSITION, '\n'.join(_pos_lines))

        _verletzung_lines = []
        if (player.ws_injury_type or '') != _old['injury_type']:
            _verletzung_lines.append(f'Verletzung: {_old["injury_type"] or "–"} → {player.ws_injury_type or "–"}')
        if str(player.ws_injury_days_remaining or 0) != _old['injury_days']:
            _verletzung_lines.append(f'Verletzungstage: {_old["injury_days"]} → {player.ws_injury_days_remaining}')
        if (player.ws_suspension_reason or '') != _old['suspension']:
            _verletzung_lines.append(f'Sperre: {_old["suspension"] or "–"} → {player.ws_suspension_reason or "–"}')
        if str(player.ws_suspension_matches_remaining or 0) != _old['sus_matches']:
            _verletzung_lines.append(f'Sperr-Spiele: {_old["sus_matches"]} → {player.ws_suspension_matches_remaining}')
        if _verletzung_lines:
            _write_edit_log(player, request.user, PlayerEditLog.CATEGORY_VERLETZUNG, '\n'.join(_verletzung_lines))

        portrait_file = request.FILES.get('portrait')
        if portrait_file and player.fm_inside_id:
            dest = os.path.join(STATIC_BASE, f'game/images/players/{player.fm_inside_id}.png')
            _save_as_png(portrait_file, dest)
            _write_edit_log(player, request.user, PlayerEditLog.CATEGORY_BILD, 'Portraitbild aktualisiert.')

        _save_player_source_ratings(request, player)

        _sr_result = compute_strength_for_player(player)
        if _sr_result['computable']:
            try:
                _sr_profile = player.strength_profile
            except PlayerStrengthProfile.DoesNotExist:
                _sr_profile = PlayerStrengthProfile(
                    player=player,
                    form_modifier=Decimal('0.00'),
                    freshness=Decimal('100.00'),
                )
            _sr_profile.base_strength = _sr_result['base_strength']
            _sr_profile.save()

        # --- RL-Form-Mapping speichern (immer, auch bei reinen Team-Name/Saison-Edits) ---
        _rl_player_id = request.POST.get('rl_api_player_id', '').strip()
        _rl_team_id   = request.POST.get('rl_api_team_id', '').strip()
        _rl_team_name = request.POST.get('rl_api_team_name', '').strip()
        _rl_season    = request.POST.get('rl_api_season', '').strip()
        if 'rl_api_player_id' in request.POST or 'rl_api_team_id' in request.POST:
            try:
                _rl_prof = player.rl_form_profile
            except PlayerRLFormProfile.DoesNotExist:
                _rl_prof = PlayerRLFormProfile(player=player)
            try:
                _rl_prof.api_football_player_id = int(_rl_player_id) if _rl_player_id else None
            except ValueError:
                pass
            try:
                _rl_prof.api_football_team_id = int(_rl_team_id) if _rl_team_id else None
            except ValueError:
                pass
            _rl_prof.api_football_team_name = _rl_team_name
            try:
                from datetime import date as _date_cls
                _current_season = _date_cls.today().year if _date_cls.today().month >= 7 else _date_cls.today().year - 1
                _rl_prof.api_football_season = int(_rl_season) if _rl_season else _current_season
            except ValueError:
                pass
            has_full_mapping = bool(_rl_prof.api_football_player_id and _rl_prof.api_football_team_id)
            if has_full_mapping and _rl_prof.rl_form_status == PlayerRLFormProfile.STATUS_NOT_MAPPED:
                _rl_prof.rl_form_status = PlayerRLFormProfile.STATUS_NOT_FETCHED
            elif not has_full_mapping:
                _rl_prof.rl_form_status = PlayerRLFormProfile.STATUS_NOT_MAPPED
            _rl_prof.save()
            compute_rl_form_for_player(player)

        action = request.POST.get('action', 'save')
        if action == 'save_new':
            messages.success(request, f'{player.first_name} {player.last_name} gespeichert.')
            return redirect('creator_new_player', club_id=player.club_id)
        elif action == 'save_continue':
            messages.success(request, 'Gespeichert.')
            return redirect('creator_player_edit', player_id=player.id)
        else:
            messages.success(request, f'{player.first_name} {player.last_name} gespeichert.')
            return redirect('creator_club_edit', club_id=player.club_id)

    nats = [n.strip() for n in (player.nationalities or '').split(',') if n.strip()]
    nat1 = nats[0] if len(nats) > 0 else ''
    nat2 = nats[1] if len(nats) > 1 else ''

    portrait_path = player.portrait_static_path if player.fm_inside_id else ''

    context = {
        'player': player,
        'all_clubs': all_clubs,
        'position_choices': POSITION_CHOICES,
        'nationality_choices': NATIONALITY_CHOICES,
        'nat1': nat1,
        'nat2': nat2,
        'portrait_path': portrait_path,
    }
    context.update(_build_source_tab_context(player))
    context.update(_build_strength_tab_context(player))
    context.update(_build_rl_form_tab_context(player))
    context.update(_build_geschichte_tab_context(player))
    return render(request, 'creator/player_edit.html', context)


@require_POST
@login_required
def creator_player_fetch_rl_form(request, player_id):
    """Lädt RL-Form-Daten für einen Spieler aus API-Football (team-basiert)."""
    import time
    from decimal import Decimal as _Dec, InvalidOperation
    from datetime import date as _date
    import requests as _requests
    from django.conf import settings as _settings

    player = get_object_or_404(Player, id=player_id)

    try:
        rl_prof = player.rl_form_profile
    except PlayerRLFormProfile.DoesNotExist:
        messages.error(request, 'Kein RL-Form-Mapping vorhanden. Bitte zuerst API-Football-IDs speichern.')
        return redirect(f'/creator/players/{player_id}/?tab=rlform')

    if not rl_prof.api_football_player_id or not rl_prof.api_football_team_id:
        messages.error(request, 'Player-ID und Team-ID müssen gesetzt sein.')
        return redirect(f'/creator/players/{player_id}/?tab=rlform')

    if not _settings.API_FOOTBALL_KEY:
        messages.error(request, 'API_FOOTBALL_KEY nicht gesetzt. Bitte Env-Secret anlegen.')
        return redirect(f'/creator/players/{player_id}/?tab=rlform')

    from .api_football import get_team_fixtures, get_fixture_player_stats

    team_id   = rl_prof.api_football_team_id
    player_id_api = rl_prof.api_football_player_id

    from .api_football import record_api_call as _record_api_call
    fixtures = None
    try:
        fixtures = get_team_fixtures(team_id, season=rl_prof.api_football_season, last=10)
    except _requests.RequestException as exc:
        rl_prof.rl_form_status = PlayerRLFormProfile.STATUS_API_ERROR
        rl_prof.save(update_fields=['rl_form_status'])
        messages.error(request, f'API-Football Netzwerkfehler beim Laden der Fixtures: {exc}')
        return redirect(f'/creator/players/{player_id}/?tab=rlform')
    finally:
        _record_api_call(1)

    saved = 0
    for fixture in fixtures:
        fix_id       = fixture['fixture']['id']
        fix_date_str = fixture['fixture']['date'][:10]
        fix_date     = _date.fromisoformat(fix_date_str)
        league_id    = fixture.get('league', {}).get('id', 0)
        home         = fixture.get('teams', {}).get('home', {})
        away         = fixture.get('teams', {}).get('away', {})
        team_name    = rl_prof.api_football_team_name or str(team_id)
        opp_name     = away.get('name', '') if home.get('id') == team_id else home.get('name', '')

        player_stats_list = None
        try:
            player_stats_list = get_fixture_player_stats(fix_id, team_id)
            time.sleep(0.2)
        except _requests.RequestException:
            pass
        finally:
            _record_api_call(1)
        if player_stats_list is None:
            continue

        for entry in player_stats_list:
            if entry.get('player', {}).get('id') != player_id_api:
                continue
            stats = (entry.get('statistics') or [{}])[0]
            games = stats.get('games') or {}
            goals = stats.get('goals') or {}
            cards = stats.get('cards') or {}
            minutes = games.get('minutes') or 0
            raw_rating = games.get('rating')
            try:
                rating = _Dec(str(raw_rating)).quantize(_Dec('0.01')) if raw_rating else None
            except InvalidOperation:
                rating = None
            substituted_in = bool(games.get('substitute', False))

            PlayerFormSnapshot.objects.update_or_create(
                player=player,
                source=PlayerFormSnapshot.SOURCE_API_FOOTBALL,
                fixture_id=str(fix_id),
                defaults={
                    'fixture_date':           fix_date,
                    'league_api_football_id': league_id,
                    'team_api_football_id':   team_id,
                    'team_name':              team_name,
                    'opponent_name':          opp_name,
                    'minutes_played':         minutes,
                    'possible_minutes':       90,
                    'started':                minutes > 0 and not substituted_in,
                    'substituted_in':         substituted_in,
                    'captain':                bool(games.get('captain', False)),
                    'position':               games.get('position') or '',
                    'rating':                 rating,
                    'goals':                  goals.get('total') or 0,
                    'assists':                goals.get('assists') or 0,
                    'yellow_cards':           cards.get('yellow') or 0,
                    'red_cards':              cards.get('red') or 0,
                    'raw_payload':            entry,
                },
            )
            saved += 1

    compute_rl_form_for_player(player, mark_fetched=True)
    messages.success(request, f'RL-Form aktualisiert: {saved} Snapshot(s) gespeichert.')
    return redirect(f'/creator/players/{player_id}/?tab=rlform')


@require_POST
@login_required
def creator_player_recalculate_strength(request, player_id):
    """
    POST: Berechnet die Stärke eines Spielers via strength_engine neu und
    schreibt das Ergebnis in PlayerStrengthProfile.base_strength.
    form_modifier und freshness bleiben unverändert.
    """
    from decimal import Decimal
    from .models import strength_decimal

    player = get_object_or_404(Player, id=player_id)
    result = compute_strength_for_player(player)

    if not result['computable']:
        messages.warning(
            request,
            f'{player.first_name} {player.last_name}: '
            'Stärke nicht berechenbar — Quelldaten fehlen.'
        )
        return redirect('creator_player_edit', player_id=player.id)

    try:
        profile = player.strength_profile
    except PlayerStrengthProfile.DoesNotExist:
        profile = PlayerStrengthProfile(
            player=player,
            form_modifier=Decimal('0.00'),
            freshness=Decimal('100.00'),
        )

    _old_base = profile.base_strength if profile.pk else None
    profile.base_strength = result['base_strength']
    profile.save()

    _staerke_lines = [f'base_strength: {_old_base if _old_base is not None else "–"} → {profile.base_strength}']
    _staerke_lines.append(f'final_strength: {profile.final_strength}')
    _write_edit_log(player, request.user, PlayerEditLog.CATEGORY_STAERKE, '\n'.join(_staerke_lines))

    messages.success(
        request,
        f'Stärke neu berechnet: {player.first_name} {player.last_name} — '
        f'base_strength = {result["base_strength"]}, '
        f'final_strength = {profile.final_strength}'
    )
    return redirect('creator_player_edit', player_id=player.id)


def creator_new_player(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    all_clubs = Club.objects.order_by('name')

    if request.method == 'POST':
        from datetime import date
        player = Player(
            first_name=request.POST.get('first_name', '').strip(),
            last_name=request.POST.get('last_name', '').strip(),
            club=club,
            age=0,
        )
        club_id_post = request.POST.get('club')
        if club_id_post:
            try:
                player.club = Club.objects.get(id=int(club_id_post))
            except Club.DoesNotExist:
                pass

        for field in ['main_position_1', 'main_position_2', 'main_position_3',
                      'secondary_position_1', 'secondary_position_2', 'secondary_position_3',
                      'strong_foot']:
            setattr(player, field, request.POST.get(field, ''))

        dob = request.POST.get('date_of_birth', '')
        if dob:
            try:
                from datetime import datetime
                player.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
                today = date.today()
                player.age = today.year - player.date_of_birth.year - (
                    (today.month, today.day) < (player.date_of_birth.month, player.date_of_birth.day)
                )
            except ValueError:
                pass

        height = request.POST.get('height_cm', '')
        if height:
            try:
                player.height_cm = int(height)
            except ValueError:
                pass

        nat1 = request.POST.get('nationality_1', '').strip()
        nat2 = request.POST.get('nationality_2', '').strip()
        player.nationalities = ','.join(n for n in [nat1, nat2] if n)

        for dec_field in ['market_value', 'salary_per_match']:
            val = request.POST.get(dec_field, '').replace(',', '.')
            if val:
                try:
                    setattr(player, dec_field, Decimal(val))
                except InvalidOperation:
                    pass

        player.ws_injury_type = request.POST.get('ws_injury_type', '').strip()
        player.ws_suspension_reason = request.POST.get('ws_suspension_reason', '').strip()

        player.save()
        messages.success(request, f'{player.first_name} {player.last_name} hinzugefügt.')

        action = request.POST.get('action', 'save')
        if action == 'save_new':
            return redirect('creator_new_player', club_id=player.club_id)
        elif action == 'save_continue':
            return redirect('creator_player_edit', player_id=player.id)
        return redirect('creator_club_edit', club_id=player.club_id)

    return render(request, 'creator/player_edit.html', {
        'player': None,
        'club': club,
        'all_clubs': all_clubs,
        'position_choices': POSITION_CHOICES,
        'nationality_choices': NATIONALITY_CHOICES,
        'nat1': '',
        'nat2': '',
        'portrait_path': '',
    })


def _redirect_tab(club_id, tab):
    from django.urls import reverse
    return redirect(reverse('creator_club_edit', args=[club_id]) + f'?tab={tab}')


@require_POST
def creator_save_stammdaten(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)

    club.name = request.POST.get('name', club.name).strip()
    club.short_name = request.POST.get('short_name', club.short_name).strip()

    founded = request.POST.get('founded_year', '').strip()
    if founded:
        try:
            club.founded_year = int(founded)
        except ValueError:
            pass

    budget_raw = request.POST.get('budget', '').strip().replace(',', '.')
    if budget_raw:
        try:
            club.budget = Decimal(budget_raw)
        except InvalidOperation:
            pass

    fan = request.POST.get('fan_popularity', '').strip()
    if fan:
        try:
            club.fan_popularity = max(1, min(100, int(fan)))
        except ValueError:
            pass

    league_id = request.POST.get('league', '').strip()
    if league_id:
        try:
            club.league = League.objects.get(id=int(league_id))
        except (League.DoesNotExist, ValueError):
            pass

    club.save()

    profile.city_name = request.POST.get('city_name', '').strip()
    profile.city_country = request.POST.get('city_country', '').strip()
    lat = request.POST.get('map_lat', '').strip()
    lng = request.POST.get('map_lng', '').strip()
    try:
        profile.map_lat = float(lat) if lat else None
    except ValueError:
        profile.map_lat = None
    try:
        profile.map_lng = float(lng) if lng else None
    except ValueError:
        profile.map_lng = None

    partner_id = request.POST.get('partner_club', '').strip()
    if partner_id:
        try:
            profile.partner_club = Club.objects.get(id=int(partner_id))
        except (Club.DoesNotExist, ValueError):
            profile.partner_club = None
    else:
        profile.partner_club = None

    profile.save()
    messages.success(request, 'Stammdaten gespeichert.')
    return _redirect_tab(club_id, 'stammdaten')


# ─── Club: Infrastruktur ──────────────────────────────────────────────────────

@require_POST
def creator_save_infrastruktur(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    try:
        stadium = club.stadium
    except Stadium.DoesNotExist:
        stadium = Stadium(club=club, name=club.name, city='')

    sname = request.POST.get('stadium_name', '').strip()
    if sname:
        stadium.name = sname
    scity = request.POST.get('stadium_city', '').strip()
    if scity:
        stadium.city = scity

    for field in ['nlz_level', 'medizin_level', 'training_level', 'office_level']:
        val = request.POST.get(field, '').strip()
        if val:
            try:
                setattr(stadium, field, max(0, min(3, int(val))))
            except ValueError:
                pass

    stadium.save()
    messages.success(request, 'Infrastruktur gespeichert.')
    return _redirect_tab(club_id, 'infrastruktur')


# ─── Club: Pokale ─────────────────────────────────────────────────────────────

@require_POST
def creator_add_trophy(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    comp = request.POST.get('competition_name', '').strip()
    if not comp:
        messages.error(request, 'Wettbewerbsname erforderlich.')
        return _redirect_tab(club_id, 'pokale')

    count_raw = request.POST.get('count', '1').strip()
    try:
        count = max(1, int(count_raw))
    except ValueError:
        count = 1

    asset_id = request.POST.get('trophy_asset_id', '').strip()
    if not asset_id:
        asset_id = ClubTrophy.COMPETITION_DEFAULT_ASSETS.get(comp, '')

    sort_raw = request.POST.get('sort_order', '0').strip()
    try:
        sort_order = int(sort_raw)
    except ValueError:
        sort_order = 0

    ClubTrophy.objects.create(
        club=club,
        competition_name=comp,
        count=count,
        trophy_asset_id=asset_id,
        sort_order=sort_order,
    )
    messages.success(request, f'Pokal "{comp}" hinzugefügt.')
    return _redirect_tab(club_id, 'pokale')


@require_POST
def creator_delete_trophy(request, club_id, trophy_id):
    club = get_object_or_404(Club, id=club_id)
    trophy = get_object_or_404(ClubTrophy, id=trophy_id, club=club)
    name = trophy.competition_name
    trophy.delete()
    messages.success(request, f'"{name}" entfernt.')
    return _redirect_tab(club_id, 'pokale')


@require_POST
def creator_edit_trophy(request, club_id, trophy_id):
    club = get_object_or_404(Club, id=club_id)
    trophy = get_object_or_404(ClubTrophy, id=trophy_id, club=club)

    comp = request.POST.get('competition_name', '').strip()
    if comp:
        trophy.competition_name = comp

    count_raw = request.POST.get('count', '').strip()
    if count_raw:
        try:
            trophy.count = max(1, int(count_raw))
        except ValueError:
            pass

    asset_id = request.POST.get('trophy_asset_id', '').strip()
    trophy.trophy_asset_id = asset_id

    sort_raw = request.POST.get('sort_order', '').strip()
    if sort_raw:
        try:
            trophy.sort_order = int(sort_raw)
        except ValueError:
            pass

    trophy.save()
    messages.success(request, f'"{trophy.competition_name}" aktualisiert.')
    return _redirect_tab(club_id, 'pokale')


# ─── Club: Sponsoring ─────────────────────────────────────────────────────────

@require_POST
def creator_add_sponsor(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    name = request.POST.get('name', '').strip()
    sponsor_type = request.POST.get('sponsor_type', 'sonstig').strip()
    amount_raw = request.POST.get('amount_per_season', '0').strip().replace(',', '.')
    season = request.POST.get('season', '').strip()

    if not name:
        messages.error(request, 'Sponsorname erforderlich.')
        return _redirect_tab(club_id, 'sponsoring')

    try:
        amount = Decimal(amount_raw)
    except InvalidOperation:
        amount = Decimal('0')

    ClubSponsor.objects.create(
        club=club,
        name=name,
        sponsor_type=sponsor_type,
        amount_per_season=amount,
        season=season,
        is_active=True,
    )
    messages.success(request, f'Sponsor "{name}" hinzugefügt.')
    return _redirect_tab(club_id, 'sponsoring')


@require_POST
def creator_delete_sponsor(request, club_id, sponsor_id):
    club = get_object_or_404(Club, id=club_id)
    sponsor = get_object_or_404(ClubSponsor, id=sponsor_id, club=club)
    name = sponsor.name
    sponsor.delete()
    messages.success(request, f'Sponsor "{name}" entfernt.')
    return _redirect_tab(club_id, 'sponsoring')


@require_POST
def creator_toggle_sponsor(request, club_id, sponsor_id):
    club = get_object_or_404(Club, id=club_id)
    sponsor = get_object_or_404(ClubSponsor, id=sponsor_id, club=club)
    sponsor.is_active = not sponsor.is_active
    sponsor.save(update_fields=['is_active'])
    status = 'aktiviert' if sponsor.is_active else 'deaktiviert'
    messages.success(request, f'Sponsor "{sponsor.name}" {status}.')
    return _redirect_tab(club_id, 'sponsoring')


# ─── Club: Saisonziele ────────────────────────────────────────────────────────

@require_POST
def creator_add_goal(request, club_id):
    club = get_object_or_404(Club, id=club_id)

    season_raw = request.POST.get('season_number', '1').strip()
    goal_tier = request.POST.get('goal_tier', '').strip()
    rank_raw = request.POST.get('rank_in_league', '1').strip()

    if not goal_tier:
        messages.error(request, 'Zielkategorie erforderlich.')
        return _redirect_tab(club_id, 'saisonziele')

    try:
        season_number = int(season_raw)
    except ValueError:
        season_number = 1

    try:
        rank_in_league = int(rank_raw)
    except ValueError:
        rank_in_league = 1

    if SeasonGoal.objects.filter(club=club, season_number=season_number).exists():
        messages.error(request, f'Für Saison {season_number} existiert bereits ein Ziel.')
        return _redirect_tab(club_id, 'saisonziele')

    required_max = request.POST.get('required_max_rank', '').strip()
    try:
        req_rank = int(required_max)
    except ValueError:
        req_rank = 0

    SeasonGoal.objects.create(
        club=club,
        season_number=season_number,
        goal_tier=goal_tier,
        rank_in_league=rank_in_league,
        required_max_rank=req_rank,
    )
    messages.success(request, f'Saisonziel für Saison {season_number} gesetzt.')
    return _redirect_tab(club_id, 'saisonziele')


@require_POST
def creator_delete_goal(request, club_id, goal_id):
    club = get_object_or_404(Club, id=club_id)
    goal = get_object_or_404(SeasonGoal, id=goal_id, club=club)
    sn = goal.season_number
    goal.delete()
    messages.success(request, f'Saisonziel Saison {sn} entfernt.')
    return _redirect_tab(club_id, 'saisonziele')


# ═══════════════════════════════════════════════════════════════════════════════
#  Creator Mode — Manager-Profile-Editor
# ═══════════════════════════════════════════════════════════════════════════════

def _redirect_manager_tab(manager_id, tab):
    from django.urls import reverse
    return redirect(f"{reverse('creator_manager_edit', args=[manager_id])}?tab={tab}")


def creator_manager_list(request):
    managers = list(
        ManagerProfile.objects
        .select_related('user', 'favourite_club')
        .order_by('name')
    )
    club_map = {c.managed_by_id: c for c in Club.objects.filter(managed_by__isnull=False).select_related('league')}
    # Build (manager, club_or_None) rows for the template
    manager_rows = [(m, club_map.get(m.id)) for m in managers]
    return render(request, 'creator/manager_list.html', {
        'manager_rows': manager_rows,
        'total_managers': len(managers),
        'total_with_club': sum(1 for m in managers if m.id in club_map),
    })


def creator_manager_edit(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    active_tab = request.GET.get('tab', 'profil')

    # Managed club (Club.managed_by OneToOneField → ManagerProfile)
    managed_club = Club.objects.filter(managed_by=manager).select_related('league').first()
    career_stations = manager.career_stations.select_related('club').order_by('order')
    try:
        coin_balance = manager.hoeness_coins.amount
    except HoenessCoin.DoesNotExist:
        coin_balance = 0
    coin_transactions = CoinTransaction.objects.filter(manager=manager).order_by('-created_at')[:30]
    satisfactions = PresidentSatisfaction.objects.filter(manager=manager).select_related('club').order_by('value')
    all_clubs = Club.objects.select_related('league').order_by('name')
    free_clubs = Club.objects.filter(managed_by__isnull=True).select_related('league').order_by('name')

    # Compute avatar URL if profile_image is set
    avatar_url = None
    if manager.profile_image:
        avatar_url = manager.profile_image

    return render(request, 'creator/manager_edit.html', {
        'manager': manager,
        'active_tab': active_tab,
        'managed_club': managed_club,
        'career_stations': career_stations,
        'coin_balance': coin_balance,
        'coin_transactions': coin_transactions,
        'coin_reason_choices': CoinTransaction.REASON_CHOICES,
        'satisfactions': satisfactions,
        'all_clubs': all_clubs,
        'free_clubs': free_clubs,
        'trainer_type_choices': ManagerProfile.TRAINER_TYPE_CHOICES,
        'avatar_url': avatar_url,
    })


@require_POST
def creator_save_manager_profil(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Name darf nicht leer sein.')
        return _redirect_manager_tab(manager_id, 'profil')
    if ManagerProfile.objects.filter(name=name).exclude(id=manager_id).exists():
        messages.error(request, f'Name „{name}" ist bereits vergeben.')
        return _redirect_manager_tab(manager_id, 'profil')

    trainer_type = request.POST.get('trainer_type', manager.trainer_type)
    nationality_flag = request.POST.get('nationality_flag', '').strip()
    nationality_name = request.POST.get('nationality_name', '').strip()
    member_since = request.POST.get('member_since', '') or None
    highscore = request.POST.get('highscore', '').strip()
    name_confirmed = request.POST.get('name_confirmed', '0') == '1'
    fav_club_id = request.POST.get('favourite_club', '') or None

    try:
        level = max(1, int(request.POST.get('level', manager.level)))
    except (ValueError, TypeError):
        level = manager.level
    try:
        xp = max(0, int(request.POST.get('xp', manager.xp)))
    except (ValueError, TypeError):
        xp = manager.xp
    try:
        xp_max = max(1, int(request.POST.get('xp_max', manager.xp_max)))
    except (ValueError, TypeError):
        xp_max = manager.xp_max

    manager.name = name
    manager.trainer_type = trainer_type
    manager.nationality_flag = nationality_flag
    manager.nationality_name = nationality_name
    manager.highscore = highscore
    manager.name_confirmed = name_confirmed
    manager.level = level
    manager.xp = xp
    manager.xp_max = xp_max
    if fav_club_id:
        manager.favourite_club_id = fav_club_id
    else:
        manager.favourite_club = None
    if member_since:
        from datetime import date
        try:
            manager.member_since = date.fromisoformat(member_since)
        except ValueError:
            pass
    else:
        manager.member_since = None

    manager.save()
    messages.success(request, 'Profil gespeichert.')
    return _redirect_manager_tab(manager_id, 'profil')


@require_POST
def creator_save_manager_club(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    action = request.POST.get('action', '')

    if action == 'unassign':
        old_club = Club.objects.filter(managed_by=manager).first()
        if old_club:
            old_club.managed_by = None
            old_club.save(update_fields=['managed_by'])
            messages.success(request, f'Verein „{old_club.name}" wurde vom Manager getrennt.')
        else:
            messages.error(request, 'Kein Verein zugeordnet.')

    elif action == 'assign':
        club_id = request.POST.get('club_id', '')
        if not club_id:
            messages.error(request, 'Kein Verein ausgewählt.')
            return _redirect_manager_tab(manager_id, 'verein')
        new_club = get_object_or_404(Club, id=club_id)

        # Remove manager from current club first
        old_club = Club.objects.filter(managed_by=manager).exclude(id=new_club.id).first()
        if old_club:
            old_club.managed_by = None
            old_club.save(update_fields=['managed_by'])

        # Remove existing manager from new club if occupied
        if new_club.managed_by and new_club.managed_by_id != manager_id:
            displaced = new_club.managed_by
            messages.warning(request, f'Manager „{displaced.name}" wurde von „{new_club.name}" entfernt.')

        new_club.managed_by = manager
        new_club.save(update_fields=['managed_by'])
        messages.success(request, f'Manager erfolgreich „{new_club.name}" zugeordnet.')

    return _redirect_manager_tab(manager_id, 'verein')


@require_POST
def creator_add_career_station(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    city_name = request.POST.get('city_name', '').strip()
    if not city_name:
        messages.error(request, 'Stadtname ist Pflichtfeld.')
        return _redirect_manager_tab(manager_id, 'karriere')

    club_id = request.POST.get('club_id', '') or None
    custom_club_name = request.POST.get('custom_club_name', '').strip()
    city_country = request.POST.get('city_country', '').strip()
    started_at = request.POST.get('started_at', '') or None
    ended_at = request.POST.get('ended_at', '') or None
    games_played = max(0, int(request.POST.get('games_played', 0) or 0))
    order = max(1, int(request.POST.get('order', 1) or 1))
    map_x = max(0, int(request.POST.get('map_x', 271) or 271))
    map_y = max(0, int(request.POST.get('map_y', 214) or 214))

    from datetime import date
    started = None
    if started_at:
        try:
            started = date.fromisoformat(started_at)
        except ValueError:
            pass
    ended = None
    if ended_at:
        try:
            ended = date.fromisoformat(ended_at)
        except ValueError:
            pass

    club = Club.objects.filter(id=club_id).first() if club_id else None

    ManagerCareerStation.objects.create(
        manager=manager,
        club=club,
        custom_club_name=custom_club_name,
        city_name=city_name,
        city_country=city_country,
        order=order,
        map_x=map_x,
        map_y=map_y,
        started_at=started,
        ended_at=ended,
        games_played=games_played,
    )
    messages.success(request, f'Karrierestation „{city_name}" hinzugefügt.')
    return _redirect_manager_tab(manager_id, 'karriere')


@require_POST
def creator_delete_career_station(request, manager_id, station_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    station = get_object_or_404(ManagerCareerStation, id=station_id, manager=manager)
    city = station.city_name
    station.delete()
    messages.success(request, f'Station „{city}" entfernt.')
    return _redirect_manager_tab(manager_id, 'karriere')


@require_POST
def creator_save_coins(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    try:
        new_amount = max(0, int(request.POST.get('amount', 0) or 0))
    except (ValueError, TypeError):
        messages.error(request, 'Ungültiger Betrag.')
        return _redirect_manager_tab(manager_id, 'coins')

    reason = request.POST.get('reason', CoinTransaction.REASON_WIN)
    description = request.POST.get('description', '').strip() or 'Admin-Korrektur'

    coin, _ = HoenessCoin.objects.get_or_create(manager=manager, defaults={'amount': 0})
    old_amount = coin.amount
    diff = new_amount - old_amount
    coin.amount = new_amount
    coin.save()

    if diff != 0:
        CoinTransaction.objects.create(
            manager=manager,
            amount=diff,
            reason=reason,
            description=description,
        )
    messages.success(request, f'Guthaben auf {new_amount} gesetzt (Δ {diff:+d}).')
    return _redirect_manager_tab(manager_id, 'coins')


@require_POST
def creator_save_satisfaction(request, manager_id, sat_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    sat = get_object_or_404(PresidentSatisfaction, id=sat_id, manager=manager)
    try:
        value = max(0, min(100, int(request.POST.get('value', sat.value) or sat.value)))
    except (ValueError, TypeError):
        value = sat.value
    sat.value = value
    sat.save(update_fields=['value', 'updated_at'])
    messages.success(request, f'Zufriedenheit auf {value} % gesetzt.')
    return _redirect_manager_tab(manager_id, 'praesident')


@require_POST
def creator_add_satisfaction(request, manager_id):
    manager = get_object_or_404(ManagerProfile, id=manager_id)
    club_id = request.POST.get('club_id', '')
    if not club_id:
        messages.error(request, 'Verein fehlt.')
        return _redirect_manager_tab(manager_id, 'praesident')
    club = get_object_or_404(Club, id=club_id)
    try:
        value = max(0, min(100, int(request.POST.get('value', 100) or 100)))
    except (ValueError, TypeError):
        value = 100
    sat, created = PresidentSatisfaction.objects.get_or_create(
        manager=manager, club=club,
        defaults={'value': value},
    )
    if not created:
        sat.value = value
        sat.save(update_fields=['value', 'updated_at'])
    messages.success(request, f'Zufriedenheit für „{club.name}" auf {sat.value} % gesetzt.')
    return _redirect_manager_tab(manager_id, 'praesident')


# ═══════════════════════════════════════════════════════════════════════════════
# CREATOR MODE — LIGA-EDITOR
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def creator_league_edit(request, league_id):
    from collections import defaultdict
    from datetime import date
    from django.contrib.staticfiles import finders
    from game.match_readiness import has_valid_lineup
    from game.models import SeasonFixture, SQUAD_PRO

    league = get_object_or_404(League, id=league_id)
    active_tab = request.GET.get('tab', 'stammdaten')

    clubs = list(
        league.club_set.order_by('name').prefetch_related('tactic_setups')
    )

    # Aufstellungs-Status für jeden Verein (Vereine-Tab)
    from .match_readiness import has_valid_lineup
    from .tactics import SQUAD_PRO
    for club in clubs:
        setup = None
        for ts in club.tactic_setups.all():
            if ts.squad_scope == SQUAD_PRO:
                setup = ts
                break
        if setup and has_valid_lineup(setup, club=club):
            if setup.is_confirmed:
                club.lineup_status = 'confirmed'
            else:
                club.lineup_status = 'auto'
        else:
            club.lineup_status = 'missing'

    logo_path = league.logo_static_path or ''

    spielplan_seasons = []
    spielplan_matchdays = []
    spielplan_selected = None
    spielplan_total_played = 0
    spielplan_total_fixtures = 0
    spielplan_total_matchdays = 0
    spielplan_current_matchday = None
    show_confirm_reset = False
    confirm_reset_season = None
    confirm_reset_params = {}

    if active_tab == 'spielplan':
        spielplan_seasons = list(
            SeasonFixture.objects.filter(league=league)
            .values_list('season', flat=True)
            .distinct()
            .order_by('-season')
        )
        spielplan_selected = request.GET.get('season') or (
            spielplan_seasons[0] if spielplan_seasons else None
        )
        # Confirm-reset flow: if ?confirm_reset=1 and existing unplayed fixtures
        if request.GET.get('confirm_reset') == '1':
            season_param = request.GET.get('season', '')
            existing = SeasonFixture.objects.filter(league=league, season=season_param)
            if existing.exists() and not existing.filter(is_played=True).exists():
                show_confirm_reset = True
                confirm_reset_season = season_param
                # Pass through all generator params so the confirm form is accurate
                confirm_reset_params = {
                    'rounds':       request.GET.get('rounds', '2'),
                    'start_date':   request.GET.get('start_date', ''),
                    'start_time':   request.GET.get('start_time', '15:30'),
                    'day_interval': request.GET.get('day_interval', '7'),
                    'round_break':  request.GET.get('round_break', '0'),
                }

        if spielplan_selected:
            fixtures_qs = (
                SeasonFixture.objects
                .filter(league=league, season=spielplan_selected)
                .select_related('home_club', 'away_club')
                .order_by('matchday', 'id')
            )
            by_md = defaultdict(list)
            for f in fixtures_qs:
                # Per-fixture flags: only green when the manager confirmed FOR THIS specific game
                f.home_lineup_status = 'confirmed' if f.home_lineup_set else 'missing'
                f.away_lineup_status = 'confirmed' if f.away_lineup_set else 'missing'
                by_md[f.matchday].append(f)
            for md in sorted(by_md.keys()):
                md_fixtures = by_md[md]
                played = sum(1 for f in md_fixtures if f.is_played)
                total = len(md_fixtures)
                spielplan_matchdays.append({
                    'matchday': md,
                    'fixtures': md_fixtures,
                    'played': played,
                    'total': total,
                })
                if played > 0:
                    spielplan_current_matchday = md
            spielplan_total_fixtures = sum(b['total'] for b in spielplan_matchdays)
            spielplan_total_played = sum(b['played'] for b in spielplan_matchdays)
            spielplan_total_matchdays = len(spielplan_matchdays)

    return render(request, 'creator/league_edit.html', {
        'league': league,
        'clubs': clubs,
        'active_tab': active_tab,
        'logo_path': logo_path,
        'spielplan_seasons': spielplan_seasons,
        'spielplan_selected': spielplan_selected,
        'spielplan_matchdays': spielplan_matchdays,
        'spielplan_total_played': spielplan_total_played,
        'spielplan_total_fixtures': spielplan_total_fixtures,
        'spielplan_total_matchdays': spielplan_total_matchdays,
        'spielplan_current_matchday': spielplan_current_matchday,
        'show_confirm_reset': show_confirm_reset,
        'confirm_reset_season': confirm_reset_season,
        'confirm_reset_params': confirm_reset_params,
        'today_iso': date.today().isoformat(),
    })


@login_required
@require_POST
def creator_league_save_stammdaten(request, league_id):
    league = get_object_or_404(League, id=league_id)
    league.name = request.POST.get('name', league.name).strip() or league.name
    league.country = request.POST.get('country', league.country).strip()
    league.logo_static_path = request.POST.get('logo_static_path', '').strip()
    league.coefficient_source = request.POST.get('coefficient_source', '').strip()
    try:
        league.strength_coefficient = Decimal(request.POST.get('strength_coefficient', '1.00'))
    except InvalidOperation:
        pass
    for field in ('cl_spots', 'el_spots', 'conference_spots', 'relegation_spots'):
        try:
            setattr(league, field, int(request.POST.get(field, getattr(league, field))))
        except (ValueError, TypeError):
            pass
    league.save()
    messages.success(request, f'Liga „{league.name}" gespeichert.')
    return redirect(f'/creator/leagues/{league_id}/?tab=stammdaten')


@login_required
@require_POST
def creator_league_spielplan_generate(request, league_id):
    from datetime import date, datetime, time as dt_time
    from game.models import SeasonFixture
    from game.schedule_generator import create_round_robin_schedule, matchday_date

    league = get_object_or_404(League, id=league_id)
    clubs = list(league.club_set.order_by('name'))

    season = request.POST.get('season', '').strip()
    confirm_reset = request.POST.get('confirm_reset') == '1'

    if not season or len(clubs) < 2:
        messages.error(request, 'Saison angeben und mindestens 2 Vereine in der Liga.')
        return redirect(f'/creator/leagues/{league_id}/?tab=spielplan')

    try:
        rounds = max(1, min(4, int(request.POST.get('rounds', 2))))
    except (ValueError, TypeError):
        rounds = 2
    try:
        start_date_val = datetime.strptime(request.POST.get('start_date', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        start_date_val = date.today()
    try:
        parts = request.POST.get('start_time', '15:30').split(':')
        start_time_val = dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        start_time_val = dt_time(15, 30)
    try:
        day_interval = max(1, int(request.POST.get('day_interval', 7)))
    except (ValueError, TypeError):
        day_interval = 7
    try:
        round_break = max(0, int(request.POST.get('round_break', 0)))
    except (ValueError, TypeError):
        round_break = 0

    existing = SeasonFixture.objects.filter(league=league, season=season)
    if existing.exists():
        played_count = existing.filter(is_played=True).count()
        if played_count > 0:
            messages.error(
                request,
                f'Saison „{season}" hat {played_count} gespielte Partie(n) — '
                f'Zurücksetzen nicht möglich.',
            )
            return redirect(f'/creator/leagues/{league_id}/?tab=spielplan&season={season}')
        if not confirm_reset:
            unplayed = existing.filter(is_played=False).count()
            messages.warning(
                request,
                f'__CONFIRM_RESET__{season}__{unplayed}',
            )
            return redirect(
                f'/creator/leagues/{league_id}/?tab=spielplan&season={season}&confirm_reset=1'
                f'&rounds={rounds}'
                f'&start_date={start_date_val.isoformat()}'
                f'&start_time={start_time_val.strftime("%H:%M")}'
                f'&day_interval={day_interval}'
                f'&round_break={round_break}'
            )
        existing.delete()

    try:
        schedule = create_round_robin_schedule([c.pk for c in clubs], rounds=rounds)
    except ValueError as exc:
        messages.error(request, f'Spielplan-Generator Fehler: {exc}')
        return redirect(f'/creator/leagues/{league_id}/?tab=spielplan')

    n = len(clubs)
    matchdays_per_round = n if n % 2 == 1 else n - 1
    fixtures_to_create = []
    for spieltag, pairs in sorted(schedule.items()):
        match_date = matchday_date(spieltag, start_date_val, day_interval, matchdays_per_round, round_break)
        for home_id, away_id in pairs:
            fixtures_to_create.append(SeasonFixture(
                league=league, season=season, matchday=spieltag,
                home_club_id=home_id, away_club_id=away_id,
                scheduled_date=match_date, scheduled_time=start_time_val,
            ))
    SeasonFixture.objects.bulk_create(fixtures_to_create)
    messages.success(
        request,
        f'Spielplan Saison „{season}" generiert: {len(schedule)} Spieltage, '
        f'{len(fixtures_to_create)} Partien.',
    )
    return redirect(f'/creator/leagues/{league_id}/?tab=spielplan&season={season}')


@login_required
def creator_league_fixture_save(request, league_id):
    import json
    from django.http import JsonResponse
    from django.db import transaction
    from game.models import SeasonFixture
    from datetime import datetime, time as dt_time

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    league = get_object_or_404(League, id=league_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Ungültiges JSON'}, status=400)

    rows = data.get('fixtures', [])
    errors = []
    updates = []

    for row in rows:
        fid = row.get('id')
        try:
            fixture = SeasonFixture.objects.get(pk=fid, league=league)
        except SeasonFixture.DoesNotExist:
            errors.append(f'Fixture {fid} nicht gefunden.')
            continue

        sd = (row.get('scheduled_date') or '').strip()
        st = (row.get('scheduled_time') or '').strip()
        hg = row.get('home_goals')
        ag = row.get('away_goals')
        ip = bool(row.get('is_played', False))

        if sd:
            try:
                fixture.scheduled_date = datetime.strptime(sd, '%Y-%m-%d').date()
            except ValueError:
                errors.append(f'Ungültiges Datum bei Fixture {fid}: {sd}')
                continue
        else:
            fixture.scheduled_date = None

        if st:
            try:
                parts = st.split(':')
                fixture.scheduled_time = dt_time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                errors.append(f'Ungültige Uhrzeit bei Fixture {fid}: {st}')
                continue
        else:
            fixture.scheduled_time = None

        try:
            fixture.home_goals = int(hg) if (hg is not None and str(hg) != '') else None
            if fixture.home_goals is not None and (fixture.home_goals < 0 or fixture.home_goals > 99):
                raise ValueError
        except (ValueError, TypeError):
            errors.append(f'Ungültige Heim-Tore bei Fixture {fid}: {hg}')
            continue
        try:
            fixture.away_goals = int(ag) if (ag is not None and str(ag) != '') else None
            if fixture.away_goals is not None and (fixture.away_goals < 0 or fixture.away_goals > 99):
                raise ValueError
        except (ValueError, TypeError):
            errors.append(f'Ungültige Gast-Tore bei Fixture {fid}: {ag}')
            continue
        fixture.is_played = ip
        updates.append(fixture)

    if errors:
        return JsonResponse({'error': '\n'.join(errors)}, status=400)

    with transaction.atomic():
        for f in updates:
            f.save(update_fields=[
                'scheduled_date', 'scheduled_time',
                'home_goals', 'away_goals', 'is_played',
            ])

    return JsonResponse({'ok': True, 'saved': len(updates)})


@login_required
def creator_player_search_api_football(request, player_id):
    """AJAX-Endpoint: Sucht API-Football-Spieler-Kandidaten per Name + Team.

    GET-Parameter:
        name        Spielername (mind. 3 Zeichen)
        team_name   Team-Name als optionaler Client-seitiger Filter (kein extra API-Call)
        season      Saison-Jahr (default 2024)

    Returns JSON:
        {ok: true, results: [{player_id, player_name, team_id, team_name, season, nationality, age}]}
        {ok: false, error: "..."}
    """
    import requests as _requests
    from django.conf import settings as _settings
    from .api_football import search_player

    get_object_or_404(Player, id=player_id)

    name = request.GET.get('name', '').strip()
    team_filter = request.GET.get('team_name', '').strip().lower()
    try:
        season = int(request.GET.get('season', 2024))
    except (TypeError, ValueError):
        season = 2024

    if len(name) < 3:
        return JsonResponse({'ok': False, 'error': 'Mindestens 3 Zeichen eingeben.'})

    key = getattr(_settings, 'API_FOOTBALL_KEY', '')
    if not key:
        return JsonResponse({'ok': False, 'error': 'API_FOOTBALL_KEY nicht gesetzt.'})

    from .api_football import record_api_call as _record_api_call
    raw = None
    try:
        raw = search_player(name, season=season)
    except _requests.HTTPError as exc:
        return JsonResponse({'ok': False, 'error': f'API-Fehler: {exc}'})
    except _requests.RequestException as exc:
        return JsonResponse({'ok': False, 'error': f'Netzwerkfehler: {exc}'})
    finally:
        _record_api_call(1)

    results = []
    for entry in raw:
        p = entry.get('player', {})
        for stat in entry.get('statistics', []):
            team = stat.get('team', {})
            league = stat.get('league', {})
            team_name_api = team.get('name', '')
            if team_filter and team_filter not in team_name_api.lower():
                continue
            results.append({
                'player_id':   p.get('id'),
                'player_name': p.get('name', ''),
                'nationality': p.get('nationality', ''),
                'age':         p.get('age'),
                'team_id':     team.get('id'),
                'team_name':   team_name_api,
                'season':      league.get('season', season),
                'league_name': league.get('name', ''),
            })

    from .api_football import get_today_usage as _get_today_usage, DAILY_LIMIT as _DAILY_LIMIT
    results = results[:20]
    return JsonResponse({'ok': True, 'results': results,
                         'usage_today': _get_today_usage(), 'daily_limit': _DAILY_LIMIT})
