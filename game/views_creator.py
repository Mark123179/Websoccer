import os
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Club, COUNTRY_FLAG_ASSETS, DataSource, League, Player,
    PlayerSourceRating, PlayerSourceRatingSnapshot, PlayerStrengthProfile,
    PlayerFormSnapshot, PlayerSeasonStat, Stadium,
    ClubPublicProfile, ClubTrophy, ClubSponsor,
    SeasonGoal, ManagerProfile, ManagerCareerStation, HoenessCoin,
    CoinTransaction, PresidentSatisfaction, TacticSetup,
    PlayerEditLog, PlayerRLFormProfile, GameSeasonState,
    MediaOutlet, Referee,
)
from . import strength_engine as se
from .strength_service import compute_strength_for_player, compute_rl_form_for_player
from .club_import.validation import validate_db_player, LEVEL_ERROR as VALIDATION_LEVEL_ERROR
from .management.commands.import_player_source_ratings import (
    FMI_ATTR_MAP, FMI_GK_MAP, SOFIFA_ATTR_MAP, SOFIFA_GK_MAP,
)

# Welche Attributspalten liefert welche Quelle (FMInside vs. CMTracker)?
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
    PlayerSourceRating.SOURCE_CMTRACKER: DataSource.CODE_CMTRACKER,
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
        ('ea', PlayerSourceRating.SOURCE_CMTRACKER,
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

        _version_labels = {
            'fm': 'FMInside Scraper',
            'ea': 'CMTracker',
        }
        row.source_version = _version_labels.get(prefix, prefix)
        row.checked_at = timezone.now().date()
        row.save()

        # --- Geschichte-Log: Source-Ratings ---
        src_label = 'FM Inside' if source_key == PlayerSourceRating.SOURCE_FM else 'CMTracker'
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
    ea_row = rows.get(PlayerSourceRating.SOURCE_CMTRACKER)

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
            'checked_at': fm_row.checked_at if fm_row else None,
            'source_version': fm_row.source_version if fm_row else '',
        },
        'ea': {
            'rating': ea_row.rating if ea_row else None,
            'potential': ea_row.potential if ea_row else None,
            'url': ea_row.source_url if ea_row else '',
            'checked_at': ea_row.checked_at if ea_row else None,
            'source_version': ea_row.source_version if ea_row else '',
        },
    }
    fm_snapshots = list(
        PlayerSourceRatingSnapshot.objects.filter(
            player=player,
            source__code=DataSource.CODE_FMINSIDE,
        ).order_by('-recorded_at', '-id')[:10]
    )
    ea_snapshots = list(
        PlayerSourceRatingSnapshot.objects.filter(
            player=player,
            source__code=DataSource.CODE_CMTRACKER,
        ).order_by('-recorded_at', '-id')[:10]
    )
    return {
        'source_attr_rows': attr_rows,
        'source_meta': source_meta,
        'source_is_gk': is_gk,
        'source_fm_snapshots': fm_snapshots,
        'source_ea_snapshots': ea_snapshots,
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
    ea_row = rows.get(PlayerSourceRating.SOURCE_CMTRACKER)

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
    freshness_bonus, _freshness_bonus_label = se.get_freshness_bonus(freshness_val)

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
    rl_form_bonus  = se.get_rl_form_bonus(rl_form_result['score'])
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
                row['fit_factor'], freshness_bonus, rl_form_bonus,
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
            freshness_bonus,
            rl_form_bonus,
        )
    else:
        str_min, str_max = None, None

    # ── Sync-Status: gespeicherter Profilwert vs. Engine-Berechnung ─────────
    stored_profile = getattr(player, 'strength_profile', None)
    if stored_profile is not None:
        stored_base  = float(stored_profile.base_strength)
        stored_final = float(stored_profile.final_strength)
        stored_at    = stored_profile.updated_at
        if str_min is not None:
            sync_delta = abs(stored_base - str_min)
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
            'bonus':       freshness_bonus,
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


def _assets_root():
    from .asset_urls import assets_root
    return assets_root()


def _asset_dest(*parts):
    """Baut einen vollständigen Dateisystempfad unter ASSETS_ROOT und legt
    das Verzeichnis bei Bedarf an."""
    path = os.path.join(_assets_root(), *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


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
        ctx = {
            'level': 3,
            'league': league,
            'clubs': clubs,
            'country': league.country,
            'flag_code': flag_code,
        }
        if league.id == 1:
            ctx['vereinslose_count'] = Player.objects.filter(
                club__isnull=True
            ).exclude(loan_status='extern_loan').count()
        return render(request, 'creator/index.html', ctx)

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


@staff_member_required
def creator_simulation_diagnostics(request):
    """Read-only Simulation-Diagnose (Creator Mode, nur Staff-Nutzer).

    Liest ausschließlich Bestandsdaten und ruft das reine Diagnose-Paket auf;
    keine Schreibaktionen, keine Simulation, keine Management Commands.
    """
    from .simulation_diagnostics import build_simulation_diagnostics_report
    report = build_simulation_diagnostics_report()
    return render(request, 'creator/simulation_diagnostics.html', {'report': report})


@staff_member_required
def creator_system_diagnostics(request):
    """Read-only Systemanalyse (Creator Mode, nur Staff-Nutzer)."""
    from .system_diagnostics import build_system_diagnostics_report
    report = build_system_diagnostics_report()
    return render(request, 'creator/system_diagnostics.html', {'report': report})


@login_required
def creator_vereinslose(request):
    from django.core.paginator import Paginator
    from .models import PlayerSourceRating

    q_name  = request.GET.get('name', '').strip()
    q_pos   = request.GET.get('pos', '').strip()
    q_nat   = request.GET.get('nat', '').strip()
    q_min   = request.GET.get('ea_min', '').strip()
    q_max   = request.GET.get('ea_max', '').strip()
    page_nr = request.GET.get('page', 1)

    qs = Player.objects.filter(club__isnull=True).exclude(
        loan_status='extern_loan'
    ).exclude(pool_status='show_auction').order_by('last_name', 'first_name')

    if q_name:
        from django.db.models import Q
        qs = qs.filter(Q(first_name__icontains=q_name) | Q(last_name__icontains=q_name))
    if q_pos:
        qs = qs.filter(position=q_pos)
    if q_nat:
        qs = qs.filter(nationalities__icontains=q_nat)

    if q_min or q_max:
        ea_ids = PlayerSourceRating.objects.filter(source=PlayerSourceRating.SOURCE_CMTRACKER)
        if q_min:
            try:
                ea_ids = ea_ids.filter(rating__gte=int(q_min))
            except ValueError:
                pass
        if q_max:
            try:
                ea_ids = ea_ids.filter(rating__lte=int(q_max))
            except ValueError:
                pass
        qs = qs.filter(id__in=ea_ids.values('player_id'))

    ea_map = {
        sr.player_id: sr.rating
        for sr in PlayerSourceRating.objects.filter(
            source=PlayerSourceRating.SOURCE_CMTRACKER, player_id__in=qs.values('id')
        )
    }

    paginator = Paginator(qs, 60)
    page_obj = paginator.get_page(page_nr)

    players_with_rating = [
        (p, ea_map.get(p.id, ''))
        for p in page_obj
    ]

    POSITIONS = ['TW','IV','LA','RA','DM','ZM','OM','LA','RA','ST']
    pos_choices = ['TW','IV','LV','RV','LA','RA','DM','ZM','OM','ST']

    return render(request, 'creator/vereinslose.html', {
        'page_obj': page_obj,
        'players_with_rating': players_with_rating,
        'total': qs.count(),
        'q_name': q_name,
        'q_pos': q_pos,
        'q_nat': q_nat,
        'q_min': q_min,
        'q_max': q_max,
        'pos_choices': pos_choices,
    })


def creator_club_edit(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    profile, _ = ClubPublicProfile.objects.get_or_create(club=club)

    players = list(
        Player.objects.filter(club=club)
        .prefetch_related('source_ratings')
        .order_by('last_name', 'first_name')
    )

    import_defekte = []
    for _p in players:
        _errs = [i for i in validate_db_player(_p) if i['level'] == VALIDATION_LEVEL_ERROR]
        if _errs:
            import_defekte.append({'player': _p, 'errors': _errs})

    kits = []
    for kit_type, label in [('home', 'Heim'), ('away', 'Auswärts'), ('third', 'Third')]:
        found_path = None
        for ext in ['png', 'svg']:
            rel = f'game/images/kits/{club.fm_inside_id}_{kit_type}.{ext}'
            if os.path.exists(os.path.join(STATIC_BASE, rel)):
                found_path = rel
                break
        kits.append({'type': kit_type, 'label': label, 'path': found_path})

    from .asset_urls import club_stadium_url as _stadium_url, club_city_url as _city_url
    stadium_path = _stadium_url(club.fm_inside_id) if club.fm_inside_id else ''
    city_path = _city_url(club.fm_inside_id) if club.fm_inside_id else ''
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

    from .models import ClubPlayerImportJob
    from .club_import import validation as _val

    latest_import_job = (
        ClubPlayerImportJob.objects
        .filter(ws_club=club, status=ClubPlayerImportJob.STATUS_COMPLETED)
        .order_by('-updated_at')
        .first()
    )
    import_error_count = 0
    import_warning_count = 0
    if latest_import_job:
        vi = latest_import_job.validation_issues or []
        import_error_count, import_warning_count = _val.count_levels(vi)

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
        'import_defekte': import_defekte,
        'latest_import_job': latest_import_job,
        'import_error_count': import_error_count,
        'import_warning_count': import_warning_count,
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
    if not club.fm_inside_id:
        messages.error(request, 'Kein fm_inside_id gesetzt – Bild kann nicht gespeichert werden.')
        return redirect('creator_club_edit', club_id=club_id)
    dest = _asset_dest('clubs', 'stadiums', f'{club.fm_inside_id}_stadium.jpg')
    _save_as_jpg(f, dest)
    profile.stadium_image_static_path = f'clubs/stadiums/{club.fm_inside_id}_stadium.jpg'
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
    if not club.fm_inside_id:
        messages.error(request, 'Kein fm_inside_id gesetzt – Bild kann nicht gespeichert werden.')
        return redirect('creator_club_edit', club_id=club_id)
    dest = _asset_dest('clubs', 'cities', f'{club.fm_inside_id}.jpg')
    _save_as_jpg(f, dest)
    profile.city_image_static_path = f'clubs/cities/{club.fm_inside_id}.jpg'
    profile.save(update_fields=['city_image_static_path'])
    messages.success(request, 'Stadtbild gespeichert.')
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
    stem = club._asset_stem()
    dest = _asset_dest('clubs', 'kits', f'{stem}_{kit_type}.png')
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
    if not club.fm_inside_id:
        messages.error(request, 'Kein fm_inside_id gesetzt – Wappen kann nicht gespeichert werden.')
        return redirect('creator_club_edit', club_id=club_id)
    dest = _asset_dest('clubs', 'logos', f'{club.fm_inside_id}_club.png')
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
    dest = _asset_dest('competitions', f'{league_id}_comp.png')
    _save_as_png(f, dest)
    league.logo_static_path = f'competitions/{league_id}_comp.png'
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
            'loan_club':    player.loan_partner_club.name if player.loan_partner_club_id else '',
            'dob':          str(player.date_of_birth or ''),
            'height_cm':    str(player.height_cm or ''),
            'nationalities': player.nationalities or '',
            'strong_foot':  player.strong_foot or '',
            'market_value': str(player.market_value or ''),
            'salary':       str(player.salary_per_match or ''),
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
                # Creator-Edits sind Datenkorrekturen — keine Vereinsstation
                # in der Ausbildungshistorie erzeugen.
                player._suppress_club_history = True
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

        loan_club_id = request.POST.get('loan_partner_club')
        if loan_club_id:
            try:
                player.loan_partner_club = Club.objects.get(id=int(loan_club_id))
            except Club.DoesNotExist:
                pass
        elif loan_club_id == '':
            player.loan_partner_club = None

        for field in ['main_position_1', 'main_position_2', 'main_position_3',
                      'secondary_position_1', 'secondary_position_2', 'secondary_position_3',
                      'strong_foot']:
            val = request.POST.get(field, '')
            setattr(player, field, val)

        # HP darf nie gleichzeitig NP sein — Duplikate aus NP entfernen
        _hp_set = {player.main_position_1, player.main_position_2, player.main_position_3} - {''}
        _raw_sec = [player.secondary_position_1, player.secondary_position_2, player.secondary_position_3]
        _deduped_sec = [p for p in _raw_sec if p and p not in _hp_set]
        while len(_deduped_sec) < 3:
            _deduped_sec.append('')
        player.secondary_position_1 = _deduped_sec[0]
        player.secondary_position_2 = _deduped_sec[1]
        player.secondary_position_3 = _deduped_sec[2]

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
        _new_loan_club = player.loan_partner_club.name if player.loan_partner_club_id else ''
        if _new_club != _old['club']:
            _verein_lines.append(f'WS-Verein: {_old["club"] or "–"} → {_new_club or "–"}')
        if _new_rl_club != _old['rl_club']:
            _verein_lines.append(f'RL-Verein: {_old["rl_club"] or "–"} → {_new_rl_club or "–"}')
        if _new_loan_club != _old['loan_club']:
            _verein_lines.append(f'Leihverein: {_old["loan_club"] or "–"} → {_new_loan_club or "–"}')
        if str(player.market_value or '') != _old['market_value']:
            _verein_lines.append(f'Marktwert: {_old["market_value"] or "–"} → {player.market_value or "–"} €')
        if str(player.salary_per_match or '') != _old['salary']:
            _verein_lines.append(f'Gehalt: {_old["salary"] or "–"} → {player.salary_per_match or "–"} €')
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
            dest = _asset_dest('players', f'face_{player.fm_inside_id}.png')
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
        _tab = request.POST.get('tab', '')
        _redirect = redirect(
            reverse('creator_player_edit', args=[player.id])
            + (f'?tab={_tab}' if _tab else '')
        )
        if action == 'save_new':
            messages.success(request, f'{player.first_name} {player.last_name} gespeichert.')
            return _redirect
        elif action == 'save_continue':
            messages.success(request, 'Gespeichert.')
            return _redirect
        else:
            messages.success(request, f'{player.first_name} {player.last_name} gespeichert.')
            return _redirect

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
    return redirect(reverse('creator_player_edit', args=[player.id]) + '?tab=staerke')


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
        # Creator-Neuanlagen sind Datenpflege — keine Vereinsstation
        # in der Ausbildungshistorie erzeugen.
        player._suppress_club_history = True

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


@require_POST
@login_required
def creator_player_delete(request, player_id):
    """
    POST: Löscht einen Spieler endgültig samt aller abhängigen Datensätze
    (alle Relationen sind on_delete=CASCADE; PlayerImportCandidate wird per
    SET_NULL entkoppelt). Danach Umleitung auf die Kaderseite des bisherigen
    Vereins, sonst auf die Spielersuche.
    """
    from django.db import transaction
    player = get_object_or_404(Player, id=player_id)
    club_id = player.club_id
    name = f'{player.first_name} {player.last_name}'.strip() or 'Spieler'

    with transaction.atomic():
        player.delete()

    messages.success(request, f'{name} gelöscht.')
    if club_id:
        return _redirect_tab(club_id, 'kader')
    return redirect('creator_search')


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
    budget_target = None
    if budget_raw:
        try:
            budget_target = Decimal(budget_raw)
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

    # Kontostand wird nie direkt gesetzt — Differenz als Admin-Korrektur
    # über das Ledger buchen (Ledger = einzige Wahrheit, Spec Kap. 12.1).
    if budget_target is not None:
        from game.economy.booking import book
        delta = budget_target - (club.budget or Decimal('0.00'))
        if delta != 0:
            book(
                club, 'KORREKTUR_ADMIN', delta,
                beschreibung=f'Creator: Kontostand auf {budget_target:,.2f} € gesetzt',
                referenz_typ='creator_stammdaten',
                pflicht=True,
            )

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


# ─── Club: Quellen & IDs ──────────────────────────────────────────────────────

@require_POST
def creator_save_source_ids(request, club_id):
    """Speichert fm_inside_id, transfermarkt_id und api_football_id des Vereins."""
    from django.db import IntegrityError
    club = get_object_or_404(Club, id=club_id)

    def _parse_bigint(raw):
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            v = int(raw)
            return v if v > 0 else None
        except ValueError:
            return False  # Sentinel: ungültig

    fmi_raw = request.POST.get('fm_inside_id', '')
    tm_raw  = request.POST.get('transfermarkt_id', '')
    af_raw  = request.POST.get('api_football_id', '')

    fmi = _parse_bigint(fmi_raw)
    tm  = _parse_bigint(tm_raw)
    af  = _parse_bigint(af_raw)

    if fmi is False or tm is False or af is False:
        messages.error(request, 'Ungültige ID — nur positive ganze Zahlen erlaubt.')
        return _redirect_tab(club_id, 'bilder')

    club.fm_inside_id      = fmi
    club.transfermarkt_id  = tm
    club.api_football_id   = af

    try:
        club.save(update_fields=['fm_inside_id', 'transfermarkt_id', 'api_football_id'])
        messages.success(request, 'Quellen & IDs gespeichert.')
    except IntegrityError:
        messages.error(request, 'Eine dieser IDs ist bereits einem anderen Verein zugewiesen.')

    return _redirect_tab(club_id, 'bilder')


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

    capacity_fields = [
        'nord_standing', 'nord_seating', 'nord_vip',
        'ost_standing', 'ost_seating', 'ost_vip',
        'sued_standing', 'sued_seating', 'sued_vip',
        'west_standing', 'west_seating', 'west_vip',
    ]
    for field in capacity_fields:
        val = request.POST.get(field, '').strip()
        if val != '':
            try:
                setattr(stadium, field, max(0, min(500_000, int(val))))
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


# ─── Sponsoring V2: Creator-Controls ─────────────────────────────────────────

@staff_member_required
@require_POST
def creator_sponsoring_deactivate(request):
    """Sponsor (Stammdaten) deaktivieren: aktiv=False — greift ab nächster Generierung."""
    from game.models import Sponsor as SponsorPool
    sponsor_id = request.POST.get('sponsor_id', '').strip()
    sponsor = get_object_or_404(SponsorPool, pk=sponsor_id)
    sponsor.aktiv = False
    sponsor.save(update_fields=['aktiv'])
    messages.success(request, f'Sponsor „{sponsor.name}" deaktiviert (greift ab nächster Generierung).')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)


@staff_member_required
@require_POST
def creator_sponsoring_slot_reset(request, club_id):
    """Slot-Reset: Contracts + Offers der Saison löschen und neu würfeln."""
    from game.models import (
        SponsorOffer as SponsorOfferModel,
        SponsorContract as SponsorContractModel,
        GameSeasonState,
    )
    from game.economy.sponsors import generate_offers_v2

    club = get_object_or_404(Club, pk=club_id)
    slot = request.POST.get('slot', '').strip()
    season_state = GameSeasonState.objects.first()
    season = str(season_state.current_season) if season_state else '1'

    valid_slots = ('haupt', 'trikot', 'ausruester', 'stadion', 'tv')
    if slot not in valid_slots and slot != '':
        messages.error(request, f'Ungültiger Slot „{slot}".')
        return _redirect_tab(club_id, 'sponsoring')

    # Contracts + Offers der laufenden Saison löschen
    qs_contracts = SponsorContractModel.objects.filter(club=club, saison=season)
    qs_offers    = SponsorOfferModel.objects.filter(club=club, saison=season)
    if slot:
        qs_contracts = qs_contracts.filter(slot=slot)
        qs_offers    = qs_offers.filter(slot=slot)
    n_c = qs_contracts.count()
    n_o = qs_offers.count()
    qs_contracts.delete()
    qs_offers.delete()

    # Neu würfeln — generate_offers_v2 ist idempotent: nach dem Löschen generiert sie neue
    try:
        generate_offers_v2(club, season)
        msg = f'Slot-Reset: {n_c} Vertrag/Verträge + {n_o} Angebote entfernt, neu generiert.'
        messages.success(request, msg)
    except Exception as exc:
        messages.warning(request, f'Slot-Reset: Löschen OK ({n_c}/{n_o}), Neugenerierung fehlgeschlagen: {exc}')

    return _redirect_tab(club_id, 'sponsoring')


@staff_member_required
@require_POST
def creator_sponsoring_risk_mode(request):
    """SPONSOR_RISK_MODE Regler: Entschärft / Standard / Hardcore."""
    from game.economy.params import get_param as _get_param
    from game.models import EconomyParameter, GameSeasonState

    mode = request.POST.get('risk_mode', 'Standard').strip()
    if mode not in ('Entschärft', 'Standard', 'Hardcore'):
        messages.error(request, f'Ungültiger Risk-Mode: {mode!r}')
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
        return redirect(next_url)

    season_state = GameSeasonState.objects.first()
    season = str(season_state.current_season) if season_state else '1'

    EconomyParameter.objects.update_or_create(
        key='SPONSOR_RISK_MODE', saison=season,
        defaults={'value': mode},
    )
    messages.success(request, f'SPONSOR_RISK_MODE auf „{mode}" gesetzt (Saison {season}).')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)


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

    from game.competition_assets import competition_logo_static_path as _comp_logo_url
    logo_path = _comp_logo_url(league) if league else ''

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

    cup_seasons = []
    all_leagues = []
    if active_tab == 'pokal' and league.is_cup:
        from .models import CupSeason
        cup_seasons = list(
            CupSeason.objects
            .filter(competition=league)
            .order_by('-season')
            .prefetch_related('participants', 'rounds__fixtures__home_club', 'rounds__fixtures__away_club', 'rounds__fixtures__winner_club')
            .select_related('winner_club')
        )
        all_leagues = list(League.objects.order_by('name'))

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
        'cup_seasons': cup_seasons,
        'all_leagues': all_leagues,
    })


@login_required
@require_POST
def creator_league_save_stammdaten(request, league_id):
    league = get_object_or_404(League, id=league_id)
    league.name = request.POST.get('name', league.name).strip() or league.name
    league.country = request.POST.get('country', league.country).strip()
    # logo_static_path wird ausschließlich über den Upload-Endpunkt gesetzt — nie aus dem Stammdaten-Formular überschreiben.
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
@require_POST
def creator_league_season_reset(request, league_id):
    """Setzt eine Saison vollständig zurück — Fixtures, Tabelle, Stats, Snapshots."""
    from game.models import (
        SeasonFixture, LeagueStandings, PlayerFormSnapshot,
        PlayerSeasonStat, LeagueSeasonState,
    )

    league = get_object_or_404(League, id=league_id)
    season = request.POST.get('season', '').strip()

    if not season:
        messages.error(request, 'Keine Saison angegeben.')
        return redirect(f'/creator/leagues/{league_id}/?tab=spielplan')

    fixture_ids = list(
        SeasonFixture.objects
        .filter(league=league, season=season)
        .values_list('id', flat=True)
    )
    if not fixture_ids:
        messages.warning(request, f'Saison „{season}" hat keine Fixtures — nichts zu tun.')
        return redirect(f'/creator/leagues/{league_id}/?tab=spielplan')

    fixture_id_strs = [f'ws_liga_{fid}' for fid in fixture_ids]

    snap_count = PlayerFormSnapshot.objects.filter(
        source='ws_liga',
        fixture_id__in=fixture_id_strs,
    ).delete()[0]

    club_ids = list(league.club_set.values_list('id', flat=True))
    stat_count = PlayerSeasonStat.objects.filter(
        player__club_id__in=club_ids,
        competition=league.name,
    ).delete()[0]

    standing_count = LeagueStandings.objects.filter(
        league=league, season=season,
    ).delete()[0]

    LeagueSeasonState.objects.filter(league=league, season=season).delete()

    fixture_count = SeasonFixture.objects.filter(
        league=league, season=season,
    ).delete()[0]

    messages.success(
        request,
        f'Saison „{season}" zurückgesetzt: '
        f'{fixture_count} Fixtures, {standing_count} Tabelleneinträge, '
        f'{snap_count} Snapshots, {stat_count} Saisonstatistiken gelöscht. '
        f'Neuen Spielplan jetzt generieren.',
    )
    return redirect(f'/creator/leagues/{league_id}/?tab=spielplan')


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

    seen = set()
    results = []
    for entry in raw:
        p = entry.get('player', {})
        for stat in entry.get('statistics', []):
            team = stat.get('team', {})
            league = stat.get('league', {})
            team_name_api = team.get('name', '')
            if team_filter and team_filter not in team_name_api.lower():
                continue
            dedup_key = (p.get('id'), team.get('id'))
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
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


@login_required
@require_POST
def creator_player_save_rl_mapping(request, player_id):
    """AJAX-Endpoint: Speichert RL-Mapping-Felder direkt nach 'Übernehmen'.

    POST-Parameter: rl_api_player_id, rl_api_team_id, rl_api_team_name, rl_api_season
    Returns JSON: {ok: true} | {ok: false, error: "..."}
    """
    player = get_object_or_404(Player, id=player_id)

    _rl_player_id = request.POST.get('rl_api_player_id', '').strip()
    _rl_team_id   = request.POST.get('rl_api_team_id', '').strip()
    _rl_team_name = request.POST.get('rl_api_team_name', '').strip()
    _rl_season    = request.POST.get('rl_api_season', '').strip()

    try:
        _rl_prof = player.rl_form_profile
    except PlayerRLFormProfile.DoesNotExist:
        _rl_prof = PlayerRLFormProfile(player=player)

    try:
        _rl_prof.api_football_player_id = int(_rl_player_id) if _rl_player_id else None
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Ungültige Player-ID.'})
    try:
        _rl_prof.api_football_team_id = int(_rl_team_id) if _rl_team_id else None
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Ungültige Team-ID.'})

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
    return JsonResponse({'ok': True})


# ── Geführter Import-Hub ──────────────────────────────────────────────────────

@login_required
def creator_import_hub(request):
    """Geführter Einstieg für die drei Import-Quellen in der richtigen Reihenfolge.

    Schritt 1: tm.de (Verein + Spieler inkl. Geburtsdatum)
    Schritt 2: FMI-CSV (FM-IDs + Identität)
    Schritt 3: CMTracker-CSV (Ratings, Matching über Geburtsdatum)
    """
    return render(request, 'creator/import_hub.html')


# ── CMTracker-CSV-Upload ─────────────────────────────────────────────────────────

@login_required
def creator_sofifa_import(request):
    """Browser-Upload für den CMTracker-Rating-Import im Creator-Mode.

    Schritt 1 (GET / POST action=upload):  Formular mit Datei-Auswahl.
    Schritt 2 (POST action=preview):       Dry-Run; Vorschau im Browser.
    Schritt 3 (POST action=confirm):       Echter Import inkl. Stärke-Neuberechnung.

    Nur Staff-Nutzer dürfen globale Ratings importieren.
    """
    from django.http import HttpResponseForbidden
    from .sofifa_import_service import run_sofifa_import

    if not request.user.is_staff:
        return HttpResponseForbidden('Nur Staff-Nutzer können Ratings importieren.')

    ctx = {'step': 'upload'}

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Schritt 2: Dry-Run / Vorschau ────────────────────────────────────
        if action == 'preview':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                ctx['upload_error'] = 'Bitte eine CSV-Datei auswählen.'
                return render(request, 'creator/sofifa_import.html', ctx)

            if csv_file.size > 5 * 1024 * 1024:
                ctx['upload_error'] = 'Datei zu groß (max. 5 MB).'
                return render(request, 'creator/sofifa_import.html', ctx)

            try:
                raw_bytes = csv_file.read()
                try:
                    csv_text = raw_bytes.decode('utf-8-sig')
                except UnicodeDecodeError:
                    csv_text = raw_bytes.decode('latin-1')
            except Exception as exc:
                ctx['upload_error'] = f'Datei konnte nicht gelesen werden: {exc}'
                return render(request, 'creator/sofifa_import.html', ctx)

            result = run_sofifa_import(csv_text, dry_run=True)
            if result['fatal_error']:
                ctx['upload_error'] = result['fatal_error']
                return render(request, 'creator/sofifa_import.html', ctx)

            request.session['sofifa_csv_preview'] = csv_text

            ctx.update({
                'step': 'preview',
                'stats': result['stats'],
                'row_results': result['row_results'],
                'filename': csv_file.name,
            })
            return render(request, 'creator/sofifa_import.html', ctx)

        # ── Schritt 3: Echter Import ─────────────────────────────────────────
        elif action == 'confirm':
            csv_text = request.session.pop('sofifa_csv_preview', None)
            if not csv_text:
                ctx['upload_error'] = (
                    'Sitzung abgelaufen – bitte die CSV erneut hochladen.'
                )
                return render(request, 'creator/sofifa_import.html', ctx)

            result = run_sofifa_import(csv_text, dry_run=False)
            if result['fatal_error']:
                ctx['upload_error'] = result['fatal_error']
                return render(request, 'creator/sofifa_import.html', ctx)

            ctx.update({
                'step': 'done',
                'stats': result['stats'],
                'row_results': result['row_results'],
            })
            return render(request, 'creator/sofifa_import.html', ctx)

        # ── Abbrechen ────────────────────────────────────────────────────────
        elif action == 'cancel':
            request.session.pop('sofifa_csv_preview', None)
            return redirect('creator_sofifa_import')

    return render(request, 'creator/sofifa_import.html', ctx)


def creator_fmid_csv_import(request):
    """Browser-Upload für die FM-ID-/Identitäts-CSV (eine CSV pro Verein).

    Schritt 1 (GET / action=upload):  Verein wählen + Datei auswählen.
    Schritt 2 (action=preview):       Dry-Run; Vorschau im Browser.
    Schritt 3 (action=confirm):       Echter Import (Identität + FM-ID).

    Die CSV setzt nur Identität + ``fm_inside_id`` — keine Stärke/Attribute.
    Verliehene Spieler (Verein ≠ Zielverein) landen im Vereinslos-Pool.
    Nur Staff-Nutzer dürfen importieren.
    """
    from django.http import HttpResponseForbidden
    from .club_import.fmid_csv_service import run_fmid_csv_import

    if not request.user.is_staff:
        return HttpResponseForbidden('Nur Staff-Nutzer können importieren.')

    clubs = (
        Club.objects.filter(is_import_placeholder=False)
        .order_by('name')
        .values('id', 'name')
    )
    ctx = {'step': 'upload', 'clubs': list(clubs)}

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'cancel':
            request.session.pop('fmid_csv_preview', None)
            request.session.pop('fmid_csv_club', None)
            return redirect('creator_fmid_csv_import')

        # ── Schritt 2: Dry-Run / Vorschau ───────────────────────────────────
        if action == 'preview':
            club_id = request.POST.get('club_id', '').strip()
            target = Club.objects.filter(id=club_id).first() if club_id else None
            if target is None:
                ctx['upload_error'] = 'Bitte einen Zielverein auswählen.'
                return render(request, 'creator/fmid_csv_import.html', ctx)

            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                ctx['upload_error'] = 'Bitte eine CSV-Datei auswählen.'
                return render(request, 'creator/fmid_csv_import.html', ctx)
            if csv_file.size > 5 * 1024 * 1024:
                ctx['upload_error'] = 'Datei zu groß (max. 5 MB).'
                return render(request, 'creator/fmid_csv_import.html', ctx)

            try:
                raw_bytes = csv_file.read()
                try:
                    csv_text = raw_bytes.decode('utf-8-sig')
                except UnicodeDecodeError:
                    csv_text = raw_bytes.decode('latin-1')
            except Exception as exc:  # noqa: BLE001
                ctx['upload_error'] = f'Datei konnte nicht gelesen werden: {exc}'
                return render(request, 'creator/fmid_csv_import.html', ctx)

            result = run_fmid_csv_import(csv_text, target, dry_run=True)
            if result['fatal_error']:
                ctx['upload_error'] = result['fatal_error']
                return render(request, 'creator/fmid_csv_import.html', ctx)

            request.session['fmid_csv_preview'] = csv_text
            request.session['fmid_csv_club'] = target.id
            ctx.update({
                'step': 'preview',
                'stats': result['stats'],
                'row_results': result['row_results'],
                'filename': csv_file.name,
                'target_club': target,
            })
            return render(request, 'creator/fmid_csv_import.html', ctx)

        # ── Schritt 3: Echter Import ────────────────────────────────────────
        elif action == 'confirm':
            csv_text = request.session.pop('fmid_csv_preview', None)
            club_id = request.session.pop('fmid_csv_club', None)
            target = Club.objects.filter(id=club_id).first() if club_id else None
            if not csv_text or target is None:
                ctx['upload_error'] = (
                    'Sitzung abgelaufen – bitte die CSV erneut hochladen.'
                )
                return render(request, 'creator/fmid_csv_import.html', ctx)

            result = run_fmid_csv_import(csv_text, target, dry_run=False)
            if result['fatal_error']:
                ctx['upload_error'] = result['fatal_error']
                return render(request, 'creator/fmid_csv_import.html', ctx)

            ctx.update({
                'step': 'done',
                'stats': result['stats'],
                'row_results': result['row_results'],
                'target_club': target,
            })
            return render(request, 'creator/fmid_csv_import.html', ctx)

    return render(request, 'creator/fmid_csv_import.html', ctx)


# ── Kanonischer Vereins-CSV-Import (Vollanlage / Aktualisierung) ──────────────

@login_required
def creator_club_csv_import(request):
    """Browser-Upload für den kanonischen Vereins-CSV- und ZIP-Import (import_ready).

    Akzeptiert sowohl flache import_ready-CSVs als auch WS_CLUB_IMPORT_V2-ZIPs.
    Bei ZIPs wird das Manifest (Vereinsname, Spieleranzahl, Saison, import_ready)
    in der Vorschau angezeigt, bevor der Import gestartet wird.

    Schritt 1 (GET / action=upload):  Datei (CSV oder ZIP) + Modus + Dry-Run.
    Schritt 2 (action=preview):       Dry-Run; Validierungsbericht + Zielverein
                                      + Manifest-Info bei ZIPs.
    Schritt 3 (action=confirm):       Echter Import inkl. Zähler.

    Spielstand/Ökonomie wird in keinem Modus angefasst. Nur Staff-Nutzer.
    """
    from django.http import HttpResponseForbidden
    from .club_import import validation
    from .club_import.club_csv_import import (
        MODE_FULL, MODE_UPDATE, ClubImportError, import_club_csv,
    )
    from .club_import.zip_import import read_zip

    if not request.user.is_staff:
        return HttpResponseForbidden('Nur Staff-Nutzer können importieren.')

    ctx = {'step': 'upload', 'mode': MODE_FULL}

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'cancel':
            request.session.pop('club_csv_preview', None)
            request.session.pop('club_csv_mode', None)
            return redirect('creator_club_csv_import')

        # ── Schritt 2: Dry-Run / Validierungsbericht ─────────────────────────
        if action == 'preview':
            mode = request.POST.get('mode', MODE_FULL)
            if mode not in (MODE_FULL, MODE_UPDATE):
                mode = MODE_FULL
            ctx['mode'] = mode
            dry_run_only = request.POST.get('dry_run_only') == 'on'
            ctx['dry_run_only'] = dry_run_only

            upload_file = request.FILES.get('csv_file')
            if not upload_file:
                ctx['upload_error'] = 'Bitte eine CSV- oder ZIP-Datei auswählen.'
                return render(request, 'creator/club_csv_import.html', ctx)
            if upload_file.size > 20 * 1024 * 1024:
                ctx['upload_error'] = 'Datei zu groß (max. 20 MB).'
                return render(request, 'creator/club_csv_import.html', ctx)

            raw_bytes = upload_file.read()
            filename = upload_file.name
            manifest_info = None

            is_zip = filename.lower().endswith('.zip')
            try:
                if is_zip:
                    csv_text, manifest = read_zip(raw_bytes)
                    manifest_info = {
                        'club': manifest.club,
                        'season': manifest.season,
                        'player_count': manifest.player_count,
                        'import_ready': manifest.import_ready,
                        'package_name': manifest.package_name,
                        'source_as_of': manifest.source_as_of,
                    }
                else:
                    try:
                        csv_text = raw_bytes.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        csv_text = raw_bytes.decode('latin-1')
            except ClubImportError as exc:
                ctx['upload_error'] = str(exc)
                return render(request, 'creator/club_csv_import.html', ctx)
            except Exception as exc:  # noqa: BLE001
                ctx['upload_error'] = f'Datei konnte nicht gelesen werden: {exc}'
                return render(request, 'creator/club_csv_import.html', ctx)

            try:
                result = import_club_csv(csv_text, mode=mode, dry_run=True)
            except (ClubImportError, ValueError) as exc:
                ctx['upload_error'] = str(exc)
                return render(request, 'creator/club_csv_import.html', ctx)

            errors, warnings = validation.count_levels(result['validation_issues'])
            request.session['club_csv_preview'] = csv_text
            request.session['club_csv_mode'] = mode
            ctx.update({
                'step': 'preview',
                'club': result['club'],
                'validation_issues': result['validation_issues'],
                'error_count': errors,
                'warning_count': warnings,
                'parse_warnings': result['parse_warnings'],
                'player_count': len(result['players']),
                'filename': filename,
                'is_zip': is_zip,
                'manifest_info': manifest_info,
                'dry_run_only': dry_run_only,
            })
            return render(request, 'creator/club_csv_import.html', ctx)

        # ── Schritt 3: Echter Import ─────────────────────────────────────────
        elif action == 'confirm':
            csv_text = request.session.pop('club_csv_preview', None)
            mode = request.session.pop('club_csv_mode', None) or MODE_FULL
            ctx['mode'] = mode
            if not csv_text:
                ctx['upload_error'] = (
                    'Sitzung abgelaufen – bitte die Datei erneut hochladen.'
                )
                return render(request, 'creator/club_csv_import.html', ctx)

            skip_errors = request.POST.get('skip_error_players') == 'on'

            try:
                result = import_club_csv(
                    csv_text, mode=mode, dry_run=False, user=request.user,
                    skip_error_players=skip_errors,
                )
            except (ClubImportError, ValueError) as exc:
                ctx['upload_error'] = str(exc)
                return render(request, 'creator/club_csv_import.html', ctx)

            errors, warnings = validation.count_levels(result['validation_issues'])
            ctx.update({
                'step': 'done',
                'club': result['club'],
                'stats': result['stats'],
                'skipped_players': result['skipped_players'],
                'error_skipped_players': result.get('error_skipped_players', []),
                'validation_issues': result['validation_issues'],
                'error_count': errors,
                'warning_count': warnings,
                'parse_warnings': result['parse_warnings'],
                'reconcile_notes': result['reconcile_notes'],
                'reconcile_warnings': result['reconcile_warnings'],
            })
            return render(request, 'creator/club_csv_import.html', ctx)

    return render(request, 'creator/club_csv_import.html', ctx)


# ── Vereins-/Spielerimport — Creator-Mode Oberfläche ──────────────────────────

_IMPORT_RESULT_SESSION_KEY = 'cfm_import_results'


def _import_access(request):
    """Zugriffsprüfung: nur Staff/Admin. Gibt ``HttpResponseForbidden`` oder ``None``."""
    from django.http import HttpResponseForbidden
    if not request.user.is_staff:
        return HttpResponseForbidden('Nur Staff-Nutzer können importieren.')
    return None


def _format_import_eur(value):
    """Marktwert (Euro-Ganzzahl) als kurze deutsche Anzeige, z. B. „3,00 Mio. €"."""
    if not value:
        return ''
    try:
        value = int(value)
    except (TypeError, ValueError):
        return ''
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}".replace('.', ',') + ' Mio. €'
    if value >= 1_000:
        return f"{value // 1_000} Tsd. €"
    return f"{value} €"


_FOOT_LABELS = {'L': 'links', 'R': 'rechts', 'B': 'beidfüßig'}


def _candidate_display(candidate):
    """Template-freundliche Aufbereitung eines Kandidaten für die Kontrolltabelle."""
    nd = candidate.normalized_data or {}
    detected = candidate.detected_changes or {}
    fmi = candidate.fmi_raw or {}
    sofifa = candidate.sofifa_raw or {}
    tm = candidate.tm_raw or {}

    real_club = nd.get('real_club') or {}
    loaned_from = nd.get('loaned_from') or {}

    return {
        'obj': candidate,
        'id': candidate.id,
        'tm_player_id': candidate.tm_player_id,
        'name': f"{nd.get('first_name', '')} {nd.get('last_name', '')}".strip()
                or tm.get('display_name') or f'TM {candidate.tm_player_id}',
        'status': candidate.status,
        'status_label': candidate.get_status_display(),
        'selected': candidate.selected_for_import,
        'overwrite': candidate.overwrite_existing,
        'main_positions': nd.get('main_positions') or [],
        'secondary_positions': nd.get('secondary_positions') or [],
        'height_cm': nd.get('height_cm'),
        'strong_foot_label': _FOOT_LABELS.get(nd.get('strong_foot'), ''),
        'market_value_label': _format_import_eur(nd.get('market_value')),
        'real_club': real_club.get('name') or '',
        'loaned_from': loaned_from.get('name') or '',
        'tm_url': nd.get('transfermarkt_profile_url') or '',
        'fmi_id': nd.get('fm_inside_id'),
        'fmi_url': fmi.get('url') or '',
        'sofifa_id': nd.get('sofifa_id'),
        'sofifa_url': nd.get('sofifa_profile_url') or '',
        'fmi_missing': not bool(fmi.get('rating')),
        # Prüfbedürftig: keine FM-ID aufgelöst — muss manuell nachgetragen werden
        # (Importer meldet hierfür „prüfbedürftig (FM-ID manuell setzen)").
        'fmi_needs_manual': not nd.get('fm_inside_id'),
        'sofifa_missing': not bool(sofifa.get('rating')),
        'changes': detected.get('items') or [],
        'match_type': detected.get('match_type'),
        'is_weak_match': bool(detected.get('match_type')) and not detected.get('is_strong'),
        'warnings': candidate.source_warnings or [],
        'errors': candidate.validation_errors or [],
        'existing_player': candidate.existing_player,
    }


@login_required
def creator_import_index(request):
    """Übersicht: neuen Importauftrag anlegen + Historie früherer Aufträge."""
    forbidden = _import_access(request)
    if forbidden:
        return forbidden

    from .models import ClubPlayerImportJob
    from .club_import import get_current_tm_season_id, season_label
    from .club_import.validation import count_levels as _count_levels

    season_id = get_current_tm_season_id()
    jobs = (
        ClubPlayerImportJob.objects
        .select_related('ws_club', 'created_by')
        .all()[:100]
    )
    job_rows = []
    for job in jobs:
        cands = job.candidates.all()
        errors, warnings = _count_levels(job.validation_issues or [])
        job_rows.append({
            'job': job,
            'total': len(cands),
            'imported': sum(1 for c in cands if c.status == 'imported'),
            'error_count': errors,
            'warning_count': warnings,
        })

    from .models import League

    return render(request, 'creator/import_index.html', {
        'clubs': Club.objects.order_by('name'),
        'leagues': League.objects.order_by('country', 'name'),
        'season_id': season_id,
        'season_label': season_label(season_id),
        'job_rows': job_rows,
    })


@login_required
@require_POST
def creator_import_create(request):
    """Legt einen neuen Importauftrag mit eingefrorener Saison-ID an."""
    forbidden = _import_access(request)
    if forbidden:
        return forbidden

    from django.db import transaction
    from .models import ClubPlayerImportJob, League
    from .club_import import get_current_tm_season_id, season_label
    from .club_import.import_service import create_or_promote_target_club

    mode = (request.POST.get('import_mode') or 'existing').strip()
    tm_club_id_raw = (request.POST.get('tm_club_id') or '').strip()

    try:
        tm_club_id = int(tm_club_id_raw)
        if tm_club_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, 'Bitte eine gültige Transfermarkt-Vereins-ID eingeben.')
        return redirect('creator_import_index')

    season_id = get_current_tm_season_id()

    def _make_job(club):
        return ClubPlayerImportJob.objects.create(
            created_by=request.user,
            ws_club=club,
            tm_club_id=tm_club_id,
            tm_season_id=season_id,
            season_label=season_label(season_id),
        )

    if mode == 'new':
        club_name = (request.POST.get('club_name') or '').strip()
        league_id = request.POST.get('league')
        league = League.objects.filter(pk=league_id).first()
        if not club_name:
            messages.error(request, 'Bitte einen Vereinsnamen für den neuen Verein eingeben.')
            return redirect('creator_import_index')
        if not league:
            messages.error(request, 'Bitte eine gültige Liga für den neuen Verein auswählen.')
            return redirect('creator_import_index')

        # Vereinsanlage/-hochstufung und Auftrag müssen gemeinsam committen,
        # damit kein verwaister Verein ohne Auftrag zurückbleibt.
        with transaction.atomic():
            club, status = create_or_promote_target_club(
                tm_club_id=tm_club_id, name=club_name, league=league)
            if status == 'exists':
                transaction.set_rollback(True)
                messages.error(
                    request,
                    f'„{club.name}" existiert bereits als WS-Verein — bitte den '
                    'Modus „Bestehenden Verein befüllen" verwenden.',
                )
                return redirect('creator_import_index')
            if status == 'conflict':
                transaction.set_rollback(True)
                messages.error(
                    request,
                    f'Ein Verein namens „{club.name}" existiert bereits mit einer '
                    'anderen Transfermarkt-ID. Bitte Name/ID prüfen oder den Modus '
                    '„Bestehenden Verein befüllen" verwenden.',
                )
                return redirect('creator_import_index')
            if status == 'promoted':
                messages.info(
                    request,
                    f'Vorhandener Platzhalterverein „{club.name}" wurde zum echten '
                    'Verein hochgestuft.',
                )
            job = _make_job(club)
    else:
        club_id = request.POST.get('ws_club')
        club = Club.objects.filter(pk=club_id).first()
        if not club:
            messages.error(request, 'Bitte einen gültigen WS-Verein auswählen.')
            return redirect('creator_import_index')
        job = _make_job(club)

    messages.success(
        request,
        f'Importauftrag #{job.pk} angelegt — wartet auf den lokalen Importer.',
    )
    return redirect('creator_import_detail', job_id=job.pk)


@login_required
def creator_import_detail(request, job_id):
    """Status/Fortschritt, Kontrolltabelle oder Ergebnis — je nach Auftragsstatus."""
    forbidden = _import_access(request)
    if forbidden:
        return forbidden

    from .models import ClubPlayerImportJob
    from .club_import.review import refresh_job_candidates

    job = get_object_or_404(
        ClubPlayerImportJob.objects.select_related('ws_club', 'created_by'),
        pk=job_id,
    )

    ctx = {'job': job}

    if job.status == ClubPlayerImportJob.STATUS_REVIEW:
        # Beim ersten Betreten auswerten (Kandidaten ohne normalisierte Daten).
        needs_build = job.candidates.filter(normalized_data={}).exists()
        if needs_build or request.GET.get('reeval'):
            refresh_job_candidates(job, reset_selection=needs_build)

        candidates = [_candidate_display(c) for c in job.candidates.all()]
        counts = {
            'total': len(candidates),
            'new': sum(1 for c in candidates if c['status'] == 'new'),
            'changed': sum(1 for c in candidates if c['status'] == 'existing_changed'),
            'unchanged': sum(1 for c in candidates if c['status'] == 'existing_unchanged'),
            'invalid': sum(1 for c in candidates if c['status'] == 'invalid'),
            'selected': sum(1 for c in candidates if c['selected']),
            'fmi_missing': sum(1 for c in candidates if c['fmi_missing']),
            'fmi_needs_manual': sum(1 for c in candidates if c['fmi_needs_manual']),
        }
        cand_error_count = sum(len(c['errors']) for c in candidates)
        cand_warning_count = sum(len(c['warnings']) for c in candidates)
        ctx.update({
            'candidates': candidates,
            'counts': counts,
            'cand_error_count': cand_error_count,
            'cand_warning_count': cand_warning_count,
        })

    elif job.status in (
        ClubPlayerImportJob.STATUS_COMPLETED,
        ClubPlayerImportJob.STATUS_IMPORTING,
        ClubPlayerImportJob.STATUS_CANCELLED,
    ):
        from .club_import import validation as _val
        results = request.session.get(_IMPORT_RESULT_SESSION_KEY, {}).get(str(job.pk))
        candidates = [_candidate_display(c) for c in job.candidates.all()]
        vi = job.validation_issues or []
        errors, warnings = _val.count_levels(vi)
        ctx.update({
            'candidates': candidates,
            'result_stats': results,
            'validation_issues': vi,
            'error_count': errors,
            'warning_count': warnings,
        })

    return render(request, 'creator/import_detail.html', ctx)


@login_required
def creator_import_status(request, job_id):
    """Leichter JSON-Status-Endpunkt für das Polling der Fortschrittsansicht."""
    forbidden = _import_access(request)
    if forbidden:
        return forbidden

    from .models import ClubPlayerImportJob

    job = get_object_or_404(ClubPlayerImportJob, pk=job_id)
    return JsonResponse({
        'id': job.id,
        'status': job.status,
        'status_label': job.get_status_display(),
        'current_step': job.current_step,
        'progress_current': job.progress_current,
        'progress_total': job.progress_total,
        'heartbeat_at': job.heartbeat_at.isoformat() if job.heartbeat_at else None,
        'error_message': job.error_message,
        'total_candidates': job.candidates.count(),
    })


@login_required
@require_POST
def creator_import_candidate_update(request, job_id, candidate_id):
    """Manuelle Quellenkorrektur / Auswahl eines einzelnen Kandidaten."""
    forbidden = _import_access(request)
    if forbidden:
        return forbidden

    from .models import ClubPlayerImportJob, PlayerImportCandidate
    from .club_import.review import refresh_candidate

    job = get_object_or_404(ClubPlayerImportJob, pk=job_id)
    candidate = get_object_or_404(
        PlayerImportCandidate, pk=candidate_id, job=job,
    )

    if job.status != ClubPlayerImportJob.STATUS_REVIEW:
        msg = 'Kandidaten können nur in der Kontrollphase bearbeitet werden.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': msg}, status=409)
        messages.error(request, msg)
        return redirect('creator_import_detail', job_id=job.pk)

    action = request.POST.get('action', '')

    if action == 'toggle_select':
        candidate.selected_for_import = not candidate.selected_for_import
        candidate.save(update_fields=['selected_for_import', 'updated_at'])
    elif action == 'toggle_overwrite':
        candidate.overwrite_existing = not candidate.overwrite_existing
        candidate.save(update_fields=['overwrite_existing', 'updated_at'])
    elif action == 'set_source_ids':
        fmi_id = (request.POST.get('fm_inside_id') or '').strip()
        sofifa_id = (request.POST.get('sofifa_id') or '').strip()
        fmi_raw = dict(candidate.fmi_raw or {})
        sofifa_raw = dict(candidate.sofifa_raw or {})
        fmi_raw['id'] = int(fmi_id) if fmi_id.isdigit() else (fmi_id or None)
        sofifa_raw['id'] = sofifa_id or None
        candidate.fmi_raw = fmi_raw
        candidate.sofifa_raw = sofifa_raw
        candidate.save(update_fields=['fmi_raw', 'sofifa_raw', 'updated_at'])
        refresh_candidate(candidate)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'status': candidate.status,
                             'selected': candidate.selected_for_import,
                             'overwrite': candidate.overwrite_existing})
    return redirect('creator_import_detail', job_id=job.pk)


@login_required
@require_POST
def creator_import_bulk(request, job_id):
    """Sammelaktionen auf den Kandidaten eines Auftrags."""
    forbidden = _import_access(request)
    if forbidden:
        return forbidden

    from .models import ClubPlayerImportJob, PlayerImportCandidate as PC
    from .club_import.review import refresh_job_candidates

    job = get_object_or_404(ClubPlayerImportJob, pk=job_id)
    action = request.POST.get('action', '')
    qs = job.candidates.all()

    _active = (
        ClubPlayerImportJob.STATUS_PENDING,
        ClubPlayerImportJob.STATUS_RUNNING,
        ClubPlayerImportJob.STATUS_REVIEW,
        ClubPlayerImportJob.STATUS_IMPORTING,
    )
    if action == 'cancel':
        if job.status not in _active:
            messages.error(request, 'Dieser Auftrag kann nicht abgebrochen werden.')
            return redirect('creator_import_detail', job_id=job.pk)
    elif job.status != ClubPlayerImportJob.STATUS_REVIEW:
        messages.error(
            request, 'Kandidaten können nur in der Kontrollphase bearbeitet werden.')
        return redirect('creator_import_detail', job_id=job.pk)

    if action == 'select_new_changed':
        qs.filter(status__in=[PC.STATUS_NEW, PC.STATUS_EXISTING_CHANGED]).update(
            selected_for_import=True)
    elif action == 'overwrite_existing':
        qs.filter(existing_player__isnull=False).update(
            overwrite_existing=True, selected_for_import=True)
    elif action == 'deselect_unchanged':
        qs.filter(status=PC.STATUS_EXISTING_UNCHANGED).update(
            selected_for_import=False)
    elif action == 'select_ready':
        qs.filter(status__in=[PC.STATUS_NEW, PC.STATUS_EXISTING_CHANGED]).update(
            selected_for_import=True)
        qs.filter(status=PC.STATUS_INVALID).update(selected_for_import=False)
    elif action == 'reset':
        refresh_job_candidates(job, reset_selection=True)
    elif action == 'reeval':
        refresh_job_candidates(job, reset_selection=False)
    elif action == 'cancel':
        job.status = ClubPlayerImportJob.STATUS_CANCELLED
        job.lease_token = ''
        job.lease_expires_at = None
        job.save(update_fields=[
            'status', 'lease_token', 'lease_expires_at', 'updated_at',
        ])
        messages.info(request, f'Importauftrag #{job.pk} abgebrochen.')
        return redirect('creator_import_index')

    return redirect('creator_import_detail', job_id=job.pk)


@login_required
@require_POST
def creator_import_confirm(request, job_id):
    """Löst den verbindlichen serverseitigen Import der gewählten Kandidaten aus."""
    forbidden = _import_access(request)
    if forbidden:
        return forbidden

    from django.utils import timezone
    from .models import ClubPlayerImportJob
    from .club_import.import_service import import_selected_candidates

    job = get_object_or_404(ClubPlayerImportJob, pk=job_id)

    if job.status not in (
        ClubPlayerImportJob.STATUS_REVIEW,
        ClubPlayerImportJob.STATUS_IMPORTING,
    ):
        messages.error(request, 'Dieser Auftrag ist nicht zur Bestätigung bereit.')
        return redirect('creator_import_detail', job_id=job.pk)

    outcome = import_selected_candidates(job, user=request.user)
    stats = outcome['stats']

    job.status = ClubPlayerImportJob.STATUS_COMPLETED
    job.completed_at = timezone.now()
    job.current_step = 'Import abgeschlossen'
    job.progress_total = sum(stats.values())
    job.progress_current = job.progress_total
    job.save(update_fields=[
        'status', 'completed_at', 'current_step',
        'progress_total', 'progress_current', 'updated_at',
    ])

    results = request.session.get(_IMPORT_RESULT_SESSION_KEY, {})
    results[str(job.pk)] = stats
    request.session[_IMPORT_RESULT_SESSION_KEY] = results

    messages.success(
        request,
        'Import abgeschlossen — '
        f"erstellt {stats.get('created', 0)}, "
        f"aktualisiert {stats.get('updated', 0)}, "
        f"übersprungen {stats.get('skipped', 0)}, "
        f"fehlgeschlagen {stats.get('failed', 0)}.",
    )
    return redirect('creator_import_detail', job_id=job.pk)


# ── Wettbewerb anlegen (Liga oder Pokal) ──────────────────────────────────────

@login_required
@require_POST
def creator_competition_create(request):
    """Legt eine neue League (Liga oder Pokal-Wettbewerb) an."""
    name             = request.POST.get('name', '').strip()
    country          = request.POST.get('country', '').strip()
    competition_type = request.POST.get('competition_type', 'cup')
    try:
        max_teams = int(request.POST.get('max_teams', 32))
    except (ValueError, TypeError):
        max_teams = 32

    if not name:
        messages.error(request, 'Name ist erforderlich.')
        return redirect(request.META.get('HTTP_REFERER', '/creator/'))

    league = League.objects.create(
        name=name,
        country=country or 'Deutschland',
        competition_type=competition_type,
        max_teams=max_teams,
        logo_static_path='',
    )
    messages.success(request, f'Wettbewerb „{league.name}" angelegt.')
    return redirect(f'/creator/leagues/{league.pk}/?tab=stammdaten')


# ── Dummy-Clubs generieren ────────────────────────────────────────────────────

@login_required
@require_POST
def creator_cup_generate_dummies(request, league_id):
    """Legt Dummy-Clubs idempotent in einer Ziel-Liga (2. Bundesliga) an.

    Wird explizit vom Creator aufgerufen bevor eine Pokalsaison gestartet wird.
    Idempotent: bestehende Clubs werden nicht dupliziert.
    """
    from .cup_service import generate_dummy_clubs

    get_object_or_404(League, id=league_id)

    target_id = request.POST.get('target_league_id', '')
    try:
        target_league = League.objects.get(pk=int(target_id))
    except (League.DoesNotExist, ValueError, TypeError):
        messages.error(request, 'Ungültige Ziel-Liga.')
        return redirect(f'/creator/leagues/{league_id}/?tab=pokal')

    try:
        count = max(2, min(36, int(request.POST.get('count', 18))))
    except (ValueError, TypeError):
        count = 18

    try:
        clubs = generate_dummy_clubs(
            league=target_league,
            count=count,
            name_prefix=f'{target_league.name} Dummy',
        )
        messages.success(
            request,
            f'{len(clubs)} Dummy-Clubs in „{target_league.name}" bereit '
            f'(neu oder bereits vorhanden — idempotent).'
        )
    except Exception as exc:
        messages.error(request, f'Fehler beim Anlegen der Dummy-Clubs: {exc}')

    return redirect(f'/creator/leagues/{league_id}/?tab=pokal')


# ── Pokalsaison zurücksetzen ──────────────────────────────────────────────────

@login_required
@require_POST
def creator_cup_season_reset(request, league_id, cup_season_id):
    """Löscht eine Pokalsaison vollständig (Runden, Fixtures, Teilnehmer).

    Zwei Modi via POST-Parameter 'mode':
    - 'rounds'  → nur Runden + Fixtures löschen, Saison + Teilnehmer bleiben
    - 'full'    → gesamte CupSeason inkl. Teilnehmer löschen (Default)
    """
    from .models import CupSeason, CupRound, CupFixture

    league     = get_object_or_404(League, id=league_id)
    cup_season = get_object_or_404(CupSeason, pk=cup_season_id, competition=league)
    mode       = request.POST.get('mode', 'full')

    if mode == 'rounds':
        n = CupRound.objects.filter(cup_season=cup_season).count()
        CupRound.objects.filter(cup_season=cup_season).delete()
        cup_season.status = CupSeason.STATUS_PENDING
        cup_season.winner_club = None
        cup_season.save(update_fields=['status', 'winner_club'])
        messages.success(
            request,
            f'Saison {cup_season.season}: {n} Runde(n) gelöscht — '
            f'Teilnehmer und Saison bleiben erhalten.'
        )
    else:
        season_label = cup_season.season
        cup_season.delete()
        messages.success(
            request,
            f'Pokalsaison {season_label} vollständig gelöscht.'
        )

    return redirect(f'/creator/leagues/{league_id}/?tab=pokal')


# ── Pokalsaison anlegen ───────────────────────────────────────────────────────

@login_required
@require_POST
def creator_cup_season_create(request, league_id):
    """Legt eine Pokalsaison an, befüllt Teilnehmer und legt die erste Runde aus."""
    from .models import CupSeason, CupRound
    from .cup_service import (
        build_cup_participants,
        draw_cup_round,
        generate_dummy_clubs,
        ROUND_CODES,
    )

    league = get_object_or_404(League, id=league_id)
    if not league.is_cup:
        messages.error(request, 'Dieser Wettbewerb ist keine Pokal-Liga.')
        return redirect(f'/creator/leagues/{league_id}/?tab=pokal')

    season       = request.POST.get('season', '').strip()
    bl_id        = request.POST.get('bundesliga_id', '')
    zweite_bl_id = request.POST.get('zweitliga_id', '')

    if not season:
        messages.error(request, 'Saison-Bezeichnung ist erforderlich.')
        return redirect(f'/creator/leagues/{league_id}/?tab=pokal')

    if CupSeason.objects.filter(competition=league, season=season).exists():
        messages.warning(request, f'Pokalsaison {season} existiert bereits.')
        return redirect(f'/creator/leagues/{league_id}/?tab=pokal')

    try:
        bundesliga  = League.objects.get(pk=int(bl_id))
        zweitliga   = League.objects.get(pk=int(zweite_bl_id))
    except (League.DoesNotExist, ValueError, TypeError):
        messages.error(request, 'Ungültige Liga-Auswahl.')
        return redirect(f'/creator/leagues/{league_id}/?tab=pokal')

    cup_season = CupSeason.objects.create(
        competition=league,
        season=season,
        status=CupSeason.STATUS_SETUP,
    )

    try:
        participants = build_cup_participants(
            cup_season, bundesliga, zweitliga,
            bl_count=18, zweite_bl_count=14, fallback_by_id=True,
        )
    except Exception as exc:
        cup_season.delete()
        messages.error(request, f'Teilnehmer-Fehler: {exc}')
        return redirect(f'/creator/leagues/{league_id}/?tab=pokal')

    n = len(participants)
    from .cup_service import calculate_opening_round
    info = calculate_opening_round(n)
    round_code = ROUND_CODES.get(n, f'round_of_{n}')
    first_round = CupRound.objects.create(
        cup_season=cup_season,
        round_number=1,
        round_code=round_code,
        status=CupRound.STATUS_PENDING,
    )

    try:
        draw_cup_round(first_round, participants)
    except Exception as exc:
        messages.warning(request, f'Auslosung fehlgeschlagen: {exc}')

    messages.success(
        request,
        f'Pokalsaison {season} angelegt: {n} Teilnehmer, '
        f'{info["matches"]} Spiele + {info["byes"]} Freilose in Runde 1.'
    )
    return redirect(f'/creator/leagues/{league_id}/?tab=pokal')


# ── Erste Runde auslosen ──────────────────────────────────────────────────────

@login_required
@require_POST
def creator_cup_draw_first_round(request, league_id, cup_season_id):
    """Löst die erste Runde einer bestehenden, noch nicht ausgelosten Pokalsaison aus."""
    from .models import CupSeason, CupRound
    from .cup_service import draw_cup_round, calculate_opening_round, ROUND_CODES

    league     = get_object_or_404(League, id=league_id)
    cup_season = get_object_or_404(CupSeason, pk=cup_season_id, competition=league)

    participants = list(cup_season.participants.all())
    if not participants:
        messages.error(request, 'Keine Teilnehmer in dieser Pokalsaison.')
        return redirect(f'/creator/leagues/{league_id}/?tab=pokal')

    first_round, _ = CupRound.objects.get_or_create(
        cup_season=cup_season,
        round_number=1,
        defaults={
            'round_code': ROUND_CODES.get(len(participants), f'round_of_{len(participants)}'),
            'status': CupRound.STATUS_PENDING,
        },
    )

    try:
        draw_cup_round(first_round, participants)
        messages.success(request, 'Erste Runde erfolgreich ausgelost.')
    except Exception as exc:
        messages.error(request, f'Auslosungsfehler: {exc}')

    return redirect(f'/creator/leagues/{league_id}/?tab=pokal')


# ── Runde simulieren ──────────────────────────────────────────────────────────

@login_required
@require_POST
def creator_cup_simulate_round(request, league_id, cup_round_id):
    """Simuliert alle ausstehenden Spiele einer Pokalrunde."""
    from .models import CupRound
    from .cup_service import simulate_cup_round

    league    = get_object_or_404(League, id=league_id)
    cup_round = get_object_or_404(CupRound, pk=cup_round_id, cup_season__competition=league)

    try:
        result = simulate_cup_round(cup_round)
        n_ok  = len(result['simulated'])
        n_err = len(result['errors'])
        if n_err:
            messages.warning(
                request,
                f'{n_ok} Spiel(e) simuliert, {n_err} fehlgeschlagen.'
            )
        else:
            messages.success(request, f'{n_ok} Spiel(e) erfolgreich simuliert.')
    except Exception as exc:
        messages.error(request, f'Simulationsfehler: {exc}')

    return redirect(f'/creator/leagues/{league_id}/?tab=pokal')


# ── Nächste Runde anlegen ─────────────────────────────────────────────────────

@login_required
@require_POST
def creator_cup_advance(request, league_id, cup_round_id):
    """Schließt die aktuelle Pokalrunde ab und legt die nächste an (mit Auslosung)."""
    from .models import CupRound
    from .cup_service import advance_cup_round

    league    = get_object_or_404(League, id=league_id)
    cup_round = get_object_or_404(CupRound, pk=cup_round_id, cup_season__competition=league)

    try:
        next_round = advance_cup_round(cup_round)
        if next_round is None:
            messages.success(request, '🏆 Pokalwettbewerb abgeschlossen! Sieger eingetragen.')
        else:
            messages.success(request, f'Runde {next_round.round_number} ausgelost.')
    except Exception as exc:
        messages.error(request, f'Fehler: {exc}')

    return redirect(f'/creator/leagues/{league_id}/?tab=pokal')


# ── Pokalbaum (öffentliche Ansicht) ──────────────────────────────────────────

def cup_tree_view(request, league_id, season):
    """Zeigt den Pokalbaum (Bracket) für eine Pokalsaison."""
    from .models import CupSeason, CupRound

    league = get_object_or_404(League, id=league_id)
    cup_season = get_object_or_404(
        CupSeason.objects.prefetch_related(
            'rounds__fixtures__home_club',
            'rounds__fixtures__away_club',
            'rounds__fixtures__winner_club',
        ).select_related('winner_club', 'competition'),
        competition=league,
        season=season,
    )

    rounds = list(cup_season.rounds.order_by('round_number'))
    for r in rounds:
        r.display_name = _round_display_name(r.round_code)

    return render(request, 'cup_tree.html', {
        'league': league,
        'cup_season': cup_season,
        'rounds': rounds,
    })


def _round_display_name(code: str) -> str:
    from .cup_service import _round_display_name as _cs_rdn
    return _cs_rdn(code)


# ── Pokal-Terminplanung: Vorschau (AJAX / GET) ────────────────────────────────

@login_required
def creator_cup_schedule_preview(request, league_id, cup_season_id):
    """Berechnet Terminvorschläge für alle Runden und gibt JSON zurück.

    GET-Parameter (mind. eine Quelle muss übergeben werden):
      Variante A — realer Liga-Spielplan:
        reference_league  int   Primär-Liga-ID (Spieltage aus SeasonFixture)
        season            str   Saison-Bezeichnung (z. B. '2025/26')

      Variante B — manuelle Eingabe:
        start_date        str   Erster Ligaspieltag (YYYY-MM-DD)
        matchday_count    int   Anzahl Spieltage
        interval_days     int   Abstand zwischen zwei Spieltagen (Standard: 7)

      Gemeinsam:
        finale_offset     int   Tage nach letztem Spieltag → Finale (Standard: 5)
    """
    from datetime import date as _date, timedelta as _td
    from .models import CupSeason, SeasonFixture
    from .cup_service import auto_schedule_cup_season

    league = get_object_or_404(League, id=league_id)
    cup_season = get_object_or_404(CupSeason, pk=cup_season_id, competition=league)

    finale_offset = int(request.GET.get('finale_offset', 5))

    liga_dates: list[_date] = []

    # --- Variante A: echter Ligaplan ---
    ref_id  = request.GET.get('reference_league', '').strip()
    season_str = request.GET.get('season', '').strip()
    if ref_id:
        try:
            ref_league = League.objects.get(pk=int(ref_id))
            qs = SeasonFixture.objects.filter(
                home_club__league=ref_league,
                scheduled_date__isnull=False,
            )
            # liga_season ist optional — wenn angegeben, auf bestimmte Saison filtern;
            # ansonsten alle Fixtures der Liga (neueste Saison zuerst)
            liga_season = request.GET.get('liga_season', '').strip()
            if liga_season:
                qs = qs.filter(season=liga_season)
            else:
                # Automatisch neueste/aktive Saison wählen
                latest = (
                    SeasonFixture.objects
                    .filter(home_club__league=ref_league, scheduled_date__isnull=False)
                    .order_by('-scheduled_date')
                    .values_list('season', flat=True)
                    .first()
                )
                if latest is not None:
                    qs = qs.filter(season=latest)
            liga_dates = sorted(set(qs.values_list('scheduled_date', flat=True)))
        except (League.DoesNotExist, ValueError):
            pass

    # --- Variante B: manuelle Eingabe (wenn Variante A nichts liefert) ---
    if not liga_dates:
        start_raw = request.GET.get('start_date', '').strip()
        count_raw = request.GET.get('matchday_count', '').strip()
        interval  = int(request.GET.get('interval_days', 7))
        if start_raw and count_raw:
            try:
                start_d = _date.fromisoformat(start_raw)
                count   = max(2, int(count_raw))
                liga_dates = [
                    start_d + _td(days=interval * i) for i in range(count)
                ]
            except (ValueError, TypeError):
                pass

    proposed = auto_schedule_cup_season(
        cup_season, liga_dates, finale_offset_days=finale_offset
    )

    # Serialisierung
    WDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    out = []
    for row in proposed:
        d = row['proposed_date']
        out.append({
            'round_id':     row['round_id'],
            'round_number': row['round_number'],
            'display_name': row['display_name'],
            'proposed_date': d.isoformat(),
            'weekday':       WDAYS[d.weekday()],
            'collisions':    [c.isoformat() for c in row['collisions']],
            'is_future':     row.get('is_future', False),
        })

    liga_info = {
        'count': len(liga_dates),
        'first': liga_dates[0].isoformat() if liga_dates else None,
        'last':  liga_dates[-1].isoformat() if liga_dates else None,
    }
    return JsonResponse({'ok': True, 'rounds': out, 'liga': liga_info})


# ── Pokal-Terminplanung: Übernehmen (POST) ────────────────────────────────────

@login_required
@require_POST
def creator_cup_schedule_apply(request, league_id, cup_season_id):
    """Schreibt die bestätigten Termine in die Datenbank.

    POST-Body (multipart oder JSON):
      round_<id>   YYYY-MM-DD   Datum für Runde mit pk=<id>
    """
    from datetime import date as _date
    from .models import CupSeason
    from .cup_service import apply_cup_schedule

    league = get_object_or_404(League, id=league_id)
    cup_season = get_object_or_404(CupSeason, pk=cup_season_id, competition=league)

    round_dates: dict[int, _date] = {}
    for key, val in request.POST.items():
        if key.startswith('round_') and val:
            try:
                rid = int(key[6:])
                round_dates[rid] = _date.fromisoformat(val)
            except (ValueError, TypeError):
                pass

    if not round_dates:
        messages.error(request, 'Keine gültigen Termine übermittelt.')
        return redirect(f'/creator/leagues/{league_id}/?tab=pokal')

    updated = apply_cup_schedule(cup_season, round_dates)
    messages.success(
        request,
        f'Pokal-Terminplan übernommen: {updated} Runde(n) terminiert.'
    )
    return redirect(f'/creator/leagues/{league_id}/?tab=pokal')


# ── Globale Creator-Schnellsuche (Vereine + Spieler) ─────────────────────────
def creator_search(request):
    from django.templatetags.static import static
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'clubs': [], 'players': []})

    clubs_qs = Club.objects.filter(name__icontains=q).order_by('name')[:8]
    from django.db.models import Q
    players_qs = (
        Player.objects
        .filter(Q(first_name__icontains=q) | Q(last_name__icontains=q))
        .select_related('club')
        .order_by('last_name', 'first_name')[:10]
    )

    clubs_out = []
    for c in clubs_qs:
        crest_url = c.crest_static_path or None
        clubs_out.append({
            'id': c.pk,
            'name': c.name,
            'short': c.short_name or '',
            'crest': crest_url,
        })

    players_out = []
    for p in players_qs:
        players_out.append({
            'id': p.pk,
            'name': (p.first_name + ' ' + p.last_name).strip(),
            'pos': p.position or '',
            'club': p.club.name if p.club else '',
        })

    return JsonResponse({'clubs': clubs_out, 'players': players_out})


# ══════════════════════════════════════════════════════════════════════════════
# Saisonverwaltung — Saison beenden
# ══════════════════════════════════════════════════════════════════════════════

def _perform_season_reset():
    """Setzt Frische, Verletzungen, Sperren und Saisonleistungen für alle Spieler zurück.

    Reihenfolge:
        1. PlayerStrengthProfile.freshness → 100
        2. Player.ws_injury_* → leer / 0
        3. Player.ws_suspension_* → leer / 0
        4. PlayerSeasonStat → alle gelöscht (werden im neuen Spielbetrieb neu aufgebaut)
        5. PlayerFormSnapshot → alle gelöscht
    """
    from decimal import Decimal as D
    PlayerStrengthProfile.objects.all().update(freshness=D('100.00'))
    Player.objects.all().update(
        ws_injury_type='',
        ws_injury_days_remaining=0,
        ws_suspension_reason='',
        ws_suspension_matches_remaining=0,
    )
    deleted_stats, _ = PlayerSeasonStat.objects.all().delete()
    deleted_snaps, _ = PlayerFormSnapshot.objects.filter(
        source__in=['ws_liga', 'ws_cup']
    ).delete()
    return deleted_stats, deleted_snaps


def _compute_season_end_checks(season: str):
    """Prüft ob alle drei Bedingungen zum Saisonabschluss erfüllt sind.

    Returns (leagues_done, nat_cups_done, int_cups_done) als bool-Tupel.
    """
    from .models import SeasonFixture, CupSeason

    # ── Liga: kein ungestpieltes Fixture mehr in echten Ligen (nicht Sonderstatus) ──
    real_fixtures_qs = SeasonFixture.objects.filter(
        season=season,
        league__competition_type='league',
    ).exclude(league__country='System')

    leagues_done = (
        real_fixtures_qs.exists()
        and not real_fixtures_qs.filter(home_goals__isnull=True).exists()
    )

    # ── Cups: getrennt nach national (hat Land) und international (kein Land / "International") ──
    INTL_COUNTRIES = {'', 'International', 'Europa', 'Europe'}
    cup_seasons = CupSeason.objects.filter(season=season, competition__competition_type='cup')

    nat_qs  = cup_seasons.exclude(competition__country__in=INTL_COUNTRIES)
    intl_qs = cup_seasons.filter(competition__country__in=INTL_COUNTRIES)

    # Bedingung erfüllt wenn: keine solchen Cups existieren ODER alle sind completed
    nat_cups_done  = not nat_qs.exclude(status=CupSeason.STATUS_COMPLETED).exists()
    int_cups_done  = not intl_qs.exclude(status=CupSeason.STATUS_COMPLETED).exists()

    return leagues_done, nat_cups_done, int_cups_done


def creator_season_end(request):
    """GET: Saisonverwaltungs-Screen.  POST: Saison als beendet erklären."""
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    season_state = GameSeasonState.objects.first()
    ctx = {
        'season_state': season_state,
        'page': 'season',
    }

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'sofort_reset':
            deleted_stats, deleted_snaps = _perform_season_reset()
            messages.success(
                request,
                f'Sofort-Reset abgeschlossen: Frische 100 %, alle Verletzungen & Sperren aufgehoben, '
                f'{deleted_stats} Saisonleistungen & {deleted_snaps} Snapshots gelöscht.',
            )
            return redirect('creator_season_end')

        if action == 'declare_end':
            # Server-seitig prüfen — POST-Werte werden ignoriert
            from django.db.models import Max
            from .models import SeasonFixture, CupSeason as _CupSeason
            _season = season_state.current_season if season_state else '0'
            leagues_done, nat_cups_done, int_cups_done = _compute_season_end_checks(_season)

            if not (leagues_done and nat_cups_done and int_cups_done):
                messages.error(
                    request,
                    'Nicht alle Bedingungen sind erfüllt. Bitte erst alle Wettbewerbe abschließen.',
                )
                return render(request, 'creator/season_end.html', ctx)

            deleted_stats, deleted_snaps = _perform_season_reset()
            messages.success(
                request,
                f'Saison als beendet erklärt. '
                f'Frische 100 %, alle Verletzungen & Sperren aufgehoben, '
                f'{deleted_stats} Saisonleistungen & {deleted_snaps} Snapshots gelöscht.',
            )
            return redirect('creator_season_end')

    # Statistiken für die Anzeige
    total_players     = Player.objects.count()
    injured_count     = Player.objects.filter(ws_injury_days_remaining__gt=0).count()
    suspended_count   = Player.objects.filter(ws_suspension_matches_remaining__gt=0).count()
    season_stat_count = PlayerSeasonStat.objects.count()

    _season = season_state.current_season if season_state else '0'
    leagues_done, nat_cups_done, int_cups_done = _compute_season_end_checks(_season)
    all_done = leagues_done and nat_cups_done and int_cups_done

    ctx.update({
        'total_players':     total_players,
        'injured_count':     injured_count,
        'suspended_count':   suspended_count,
        'season_stat_count': season_stat_count,
        'leagues_done':      leagues_done,
        'nat_cups_done':     nat_cups_done,
        'int_cups_done':     int_cups_done,
        'all_done':          all_done,
    })
    return render(request, 'creator/season_end.html', ctx)


# ══════════════════════════════════════════════════════════════════════════════
# System — Freie Vereine (Job-Availability)
# ══════════════════════════════════════════════════════════════════════════════

def creator_freie_vereine(request):
    """Creator: Freie Vereine verwalten — Job-Availability-Typ setzen."""
    from .models import Club, LeagueStandings, COUNTRY_FLAG_ASSETS
    from .season_goals import current_season_number

    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    if request.method == 'POST':
        club_id  = request.POST.get('club_id')
        new_type = request.POST.get('job_availability_type', '')
        valid    = [c for c, _ in Club.JOB_AVAILABILITY_CHOICES]
        if club_id and new_type in valid:
            try:
                club = Club.objects.get(pk=club_id)
                old  = club.get_job_availability_type_display()
                club.job_availability_type = new_type
                club.save(update_fields=['job_availability_type'])
                messages.success(
                    request,
                    f'{club.name}: Freigabe → {club.get_job_availability_type_display()} (war: {old})',
                )
            except Club.DoesNotExist:
                messages.error(request, 'Verein nicht gefunden.')
        else:
            messages.error(request, 'Ungültige Eingabe.')
        return redirect('creator_freie_vereine')

    season = str(current_season_number())

    clubs_qs = (
        Club.objects
        .select_related('league')
        .order_by('league__country', 'league__name', 'name')
    )

    standing_map = {}
    for s in LeagueStandings.objects.filter(season=season):
        standing_map[s.club_id] = s.position

    rows = []
    for c in clubs_qs:
        flag_code = None
        try:
            entry = COUNTRY_FLAG_ASSETS.get(c.league.country, {})
            flag_code = entry.get('code')
        except Exception:
            pass
        rows.append({
            'club':        c,
            'position':    standing_map.get(c.pk),
            'has_manager': c.managed_by_id is not None,
            'flag_code':   flag_code,
        })

    ctx = {
        'rows':         rows,
        'type_choices': Club.JOB_AVAILABILITY_CHOICES,
        'total':        len(rows),
        'free_count':   sum(1 for r in rows if not r['has_manager']),
        'page':         'system',
    }
    return render(request, 'creator/freie_vereine.html', ctx)


@staff_member_required
def creator_media_outlets(request):
    from django.conf import settings as _s
    if request.method == 'POST':
        name  = request.POST.get('name', '').strip()
        slug  = request.POST.get('slug', '').strip()
        color = request.POST.get('color', '#22e6ff').strip()
        f     = request.FILES.get('logo')

        if not name or not slug:
            messages.error(request, 'Name und Slug sind Pflichtfelder.')
        else:
            saved_logo = False
            if f:
                dest = _asset_dest('media', f'{slug}_media.png')
                _save_as_png(f, dest)
                saved_logo = True
            updates = {'name': name, 'accent_color': color}
            if saved_logo:
                updates['has_logo'] = True
            obj, created = MediaOutlet.objects.update_or_create(
                slug=slug, defaults=updates,
            )
            messages.success(request, f'{"Angelegt" if created else "Aktualisiert"}: {name}')
        return redirect('creator_media_outlets')

    outlets    = MediaOutlet.objects.all()
    media_base = _s.ASSETS_BASE_URL + 'media/'
    return render(request, 'creator/media_outlets.html', {
        'outlets':    outlets,
        'media_base': media_base,
    })


@staff_member_required
@require_POST
def creator_media_outlet_delete(request, outlet_id):
    outlet = get_object_or_404(MediaOutlet, id=outlet_id)
    name   = outlet.name
    outlet.delete()
    messages.success(request, f'{name} gelöscht.')
    return redirect('creator_media_outlets')


# ═══════════════════════════════════════════════════════════════════════════
#  Finanzanalyse (global, Spec Kap. 12.5)
# ═══════════════════════════════════════════════════════════════════════════

@staff_member_required
def creator_finanzanalyse(request):
    """Globale Finanzanalyse: Geld im Umlauf, Saisonbilanzen, Liga-Vergleich."""
    from django.db.models import Avg, Count, Q, Sum
    from .models import FinanceTransaction
    from .finance import current_sim_season

    def _fmt(val):
        v = float(val or 0)
        sign = '−' if v < 0 else ''
        a = abs(v)
        if a >= 1_000_000_000:
            return f'{sign}{a/1_000_000_000:.2f} Mrd €'.replace('.', ',')
        if a >= 1_000_000:
            return f'{sign}{a/1_000_000:.1f} Mio €'.replace('.', ',')
        if a >= 1_000:
            return f'{sign}{a/1_000:.0f} Tsd €'
        return f'{sign}{a:,.0f} €'.replace(',', '.')

    current_season = current_sim_season() or '0'
    cat_labels = dict(FinanceTransaction.TYP_CHOICES)

    # ── KPIs: Geld im Umlauf ─────────────────────────────────────────
    kpi = Club.objects.aggregate(
        total=Sum('budget'), cnt=Count('id'), avg=Avg('budget'),
    )
    tx_count = FinanceTransaction.objects.count()

    # ── Liga-Vergleich ───────────────────────────────────────────────
    league_rows = list(
        Club.objects.values('league__name')
        .annotate(total=Sum('budget'), cnt=Count('id'), avg=Avg('budget'))
        .order_by('-total')
    )
    max_league_total = max((float(r['total'] or 0) for r in league_rows), default=0)
    for r in league_rows:
        r['name'] = r['league__name'] or 'Ohne Liga'
        r['total_fmt'] = _fmt(r['total'])
        r['avg_fmt'] = _fmt(r['avg'])
        r['pct'] = round(float(r['total'] or 0) / max_league_total * 100, 1) if max_league_total > 0 else 0

    # ── Top-/Flop-Vereine ────────────────────────────────────────────
    def _club_rows(qs):
        return [{
            'name': c.name,
            'league': c.league.name if c.league_id else '—',
            'budget': float(c.budget),
            'budget_fmt': _fmt(c.budget),
        } for c in qs.select_related('league')]

    top_clubs = _club_rows(Club.objects.order_by('-budget')[:10])
    flop_clubs = _club_rows(Club.objects.order_by('budget')[:10])

    # ── Saisonbilanzen ───────────────────────────────────────────────
    season_agg = (
        FinanceTransaction.objects.values('saison')
        .annotate(
            income=Sum('betrag', filter=Q(betrag__gt=0)),
            expense=Sum('betrag', filter=Q(betrag__lt=0)),
            cnt=Count('id'),
        )
    )

    def _season_sort_key(row):
        s = row['saison'] or ''
        return (0, int(s)) if s.isdigit() else (1, 0)

    season_rows = []
    for r in sorted(season_agg, key=_season_sort_key):
        income = r['income'] or 0
        expense = r['expense'] or 0
        net = income + expense
        net_f = float(net)
        net_abs = _fmt(abs(net_f))
        if net_f > 0:
            net_signed = f'+ {net_abs}'
        elif net_f < 0:
            net_signed = f'− {net_abs}'
        else:
            net_signed = net_abs
        season_rows.append({
            'season': r['saison'] or '—',
            'income_fmt': _fmt(income),
            'expense_fmt': _fmt(expense),
            'net': net_f,
            'net_fmt': net_signed,
            'cnt': r['cnt'],
        })

    # ── Kategorien der gewählten Saison ──────────────────────────────
    sel_season = request.GET.get('season') or current_season
    cat_agg = list(
        FinanceTransaction.objects.filter(saison=sel_season)
        .values('typ')
        .annotate(total=Sum('betrag'), cnt=Count('id'))
    )
    income_cats = [r for r in cat_agg if (r['total'] or 0) > 0]
    expense_cats = [r for r in cat_agg if (r['total'] or 0) < 0]
    income_sum = sum(float(r['total']) for r in income_cats)
    expense_sum = sum(abs(float(r['total'])) for r in expense_cats)

    def _cat_rows(rows, total_abs):
        out = []
        for r in sorted(rows, key=lambda x: -abs(float(x['total']))):
            a = abs(float(r['total']))
            out.append({
                'label': cat_labels.get(r['typ'], r['typ']),
                'amount_fmt': _fmt(a),
                'cnt': r['cnt'],
                'pct': round(a / total_abs * 100, 1) if total_abs > 0 else 0,
            })
        return out

    season_options = [row['season'] for row in season_rows if row['season'] != '—']
    if sel_season not in season_options:
        season_options.append(sel_season)

    # ── Monitoring (Spec 12.5): Geldmenge, Senken, Alarmwerte ────────
    from .economy import monitoring
    from .economy.integrity import check_ledger_integrity

    verlauf = monitoring.geldmengen_verlauf()
    verlauf_rows = [{
        'saison': v['saison'],
        'start_fmt': _fmt(v['start']),
        'ende_fmt': _fmt(v['ende']),
        'netto': float(v['netto']),
        'netto_fmt': _fmt(v['netto']),
        'wachstum_fmt': (f"{v['wachstum']*100:+.1f} %".replace('.', ',')
                         if v['wachstum'] is not None else '—'),
        'alarm': v['alarm'],
    } for v in verlauf]

    fluesse = monitoring.saison_geldfluesse(sel_season)
    schoepfung_rows = [{
        'label': r['label'], 'amount_fmt': _fmt(r['total']),
    } for r in fluesse['schoepfung_rows']]
    vernichtung_rows = [{
        'label': r['label'], 'amount_fmt': _fmt(abs(r['total'])),
    } for r in fluesse['vernichtung_rows']]

    ratio = monitoring.abloese_mw_median(sel_season)
    ratio_fmt = (f"{ratio['median']:.2f}".replace('.', ',')
                 if ratio['median'] is not None else '—')

    tk = monitoring.totes_kapital(sel_season)
    # Alarm laut Spec 12.5: totes Kapital über 3 Saisons strikt steigend
    # (Saisonverlauf per Rückwärtsrechnung aus dem Ledger).
    tk_verlauf = monitoring.totes_kapital_verlauf()
    tk_alarm = tk_verlauf['alarm']

    integrity = check_ledger_integrity()

    # ── Vollständigkeitsprüfung (Finanzlücken je Spieltag/Verein) ────────
    from .economy.integrity import check_finance_completeness
    from .models import League

    gap_saison = request.GET.get('gap_saison') or None
    gap_liga_raw = request.GET.get('gap_liga') or None
    gap_spieltag_raw = request.GET.get('gap_spieltag') or None
    gap_liga_id = int(gap_liga_raw) if gap_liga_raw and gap_liga_raw.isdigit() else None
    gap_spieltag = int(gap_spieltag_raw) if gap_spieltag_raw and gap_spieltag_raw.isdigit() else None

    completeness = check_finance_completeness(
        saison=gap_saison,
        liga_id=gap_liga_id,
        spieltag=gap_spieltag,
    )
    gaps = completeness['gaps']
    gaps_checked = completeness['checked_clubs']
    all_leagues = list(League.objects.order_by('name').only('id', 'name'))

    alarm_count = sum([
        1 if any(v['alarm'] for v in verlauf_rows) else 0,
        1 if ratio['alarm'] else 0,
        1 if tk_alarm else 0,
        1 if integrity['mismatches'] else 0,
        1 if gaps else 0,
    ])

    return render(request, 'creator/finanzanalyse.html', {
        'verlauf_rows': verlauf_rows,
        'schoepfung_rows': schoepfung_rows,
        'vernichtung_rows': vernichtung_rows,
        'schoepfung_sum_fmt': _fmt(fluesse['schoepfung']),
        'vernichtung_sum_fmt': _fmt(fluesse['vernichtung']),
        'netto_sum_fmt': _fmt(fluesse['netto']),
        'netto_sum': float(fluesse['netto']),
        'zirkulation_fmt': _fmt(fluesse['zirkulation_volumen']),
        'ratio': ratio,
        'ratio_fmt': ratio_fmt,
        'totes_kapital_fmt': _fmt(tk['summe']),
        'totes_kapital_count': tk['count'],
        'totes_kapital_clubs': [
            {'name': c['name'], 'budget_fmt': _fmt(c['budget']),
             'umsatz_fmt': _fmt(c['umsatz'])}
            for c in tk['clubs']
        ],
        'tk_alarm': tk_alarm,
        'integrity_ok': not integrity['mismatches'],
        'integrity_checked': integrity['checked'],
        'integrity_mismatches': integrity['mismatches'][:10],
        'alarm_count': alarm_count,
        'kpi_total_fmt': _fmt(kpi['total']),
        'kpi_clubs': kpi['cnt'] or 0,
        'kpi_avg_fmt': _fmt(kpi['avg']),
        'kpi_tx_count': tx_count,
        'league_rows': league_rows,
        'top_clubs': top_clubs,
        'flop_clubs': flop_clubs,
        'season_rows': season_rows,
        'sel_season': sel_season,
        'season_options': season_options,
        'income_cat_rows': _cat_rows(income_cats, income_sum),
        'expense_cat_rows': _cat_rows(expense_cats, expense_sum),
        'income_sum_fmt': _fmt(income_sum),
        'expense_sum_fmt': _fmt(expense_sum),
        'current_season': current_season,
        'gaps': gaps,
        'gaps_checked': gaps_checked,
        'gap_saison': gap_saison or '',
        'gap_liga_id': gap_liga_id or '',
        'gap_spieltag': gap_spieltag or '',
        'all_leagues': all_leagues,
    })


@staff_member_required
@require_POST
def creator_finance_gap_retry(request):
    """Nachhol-Lauf für einen fehlenden Spieltag-Finanzlauf (POST, CSRF-geschützt).

    Erwartet POST-Parameter:
      liga_id   — ID der Liga
      saison    — Saison-String (z.B. '1')
      spieltag  — Spieltag-Nummer

    Optional:
      gap_saison / gap_liga / gap_spieltag — Filter-Parameter für den Redirect zurück.
      nachholen_alle=1                      — Alle aktuell sichtbaren Lücken nachholen.
    """
    from .economy.matchday_run import run_matchday_finance
    from .models import League

    # ── Redirect-URL mit Filterparametern rekonstruieren ─────────────────
    base_url = reverse('creator_finanzanalyse')
    params = []
    back_season   = request.POST.get('back_season', '')
    back_gap_saison  = request.POST.get('gap_saison', '')
    back_gap_liga    = request.POST.get('gap_liga', '')
    back_gap_spieltag = request.POST.get('gap_spieltag', '')
    if back_season:
        params.append(f'season={back_season}')
    if back_gap_saison:
        params.append(f'gap_saison={back_gap_saison}')
    if back_gap_liga:
        params.append(f'gap_liga={back_gap_liga}')
    if back_gap_spieltag:
        params.append(f'gap_spieltag={back_gap_spieltag}')
    redirect_url = f'{base_url}?{"&".join(params)}' if params else base_url

    nachholen_alle = request.POST.get('nachholen_alle') == '1'

    if nachholen_alle:
        # Alle Lücken für den aktuellen Filter nachholen
        from .economy.integrity import check_finance_completeness

        gap_saison_f   = request.POST.get('gap_saison') or None
        gap_liga_f_raw = request.POST.get('gap_liga') or None
        gap_spieltag_f_raw = request.POST.get('gap_spieltag') or None
        gap_liga_f_id  = int(gap_liga_f_raw) if gap_liga_f_raw and gap_liga_f_raw.isdigit() else None
        gap_spieltag_f = int(gap_spieltag_f_raw) if gap_spieltag_f_raw and gap_spieltag_f_raw.isdigit() else None

        completeness = check_finance_completeness(
            saison=gap_saison_f,
            liga_id=gap_liga_f_id,
            spieltag=gap_spieltag_f,
        )
        combos = set()
        for g in completeness['gaps']:
            combos.add((g['liga_id'], g['saison'], g['spieltag']))

        ok_count, err_count = 0, 0
        for liga_id_c, saison_c, spieltag_c in sorted(combos):
            try:
                liga = League.objects.get(pk=liga_id_c)
                run_matchday_finance(liga, saison_c, spieltag_c)
                ok_count += 1
            except Exception as exc:
                err_count += 1
                messages.error(
                    request,
                    f'Fehler bei Liga {liga_id_c}, Saison {saison_c}, '
                    f'Spieltag {spieltag_c}: {exc}',
                )

        if ok_count:
            messages.success(
                request,
                f'{ok_count} Spieltag-Finanzlauf/-läufe nachgeholt'
                f'{f", {err_count} Fehler" if err_count else ""}.',
            )
        elif not err_count:
            messages.info(request, 'Keine Lücken gefunden — nichts zu tun.')
        return redirect(redirect_url)

    # ── Einzelner Nachhol-Lauf ────────────────────────────────────────────
    liga_id_raw   = request.POST.get('liga_id', '')
    saison        = request.POST.get('saison', '').strip()
    spieltag_raw  = request.POST.get('spieltag', '')

    if not liga_id_raw or not saison or not spieltag_raw:
        messages.error(request, 'Unvollständige Parameter (liga_id, saison, spieltag benötigt).')
        return redirect(redirect_url)

    try:
        liga_id  = int(liga_id_raw)
        spieltag = int(spieltag_raw)
    except ValueError:
        messages.error(request, 'liga_id und spieltag müssen ganzzahlig sein.')
        return redirect(redirect_url)

    try:
        liga = League.objects.get(pk=liga_id)
    except League.DoesNotExist:
        messages.error(request, f'Liga mit ID {liga_id} nicht gefunden.')
        return redirect(redirect_url)

    try:
        result = run_matchday_finance(liga, saison, spieltag)
    except Exception as exc:
        messages.error(request, f'Fehler beim Nachholen: {exc}')
        return redirect(redirect_url)

    errors = result.get('errors', [])
    gaps   = result.get('gaps', [])
    clubs  = result.get('clubs', [])
    skipped = sum(1 for c in clubs if c.get('skipped'))
    repaired = sum(1 for c in clubs if c.get('repaired'))

    if errors:
        for e in errors[:3]:
            messages.warning(request, e)
    if gaps:
        messages.warning(
            request,
            f'Noch {len(gaps)} Lücke(n) nach dem Lauf (teilweise nachgeholt).',
        )
    else:
        summary_parts = [f'{liga.name} Saison {saison} Spieltag {spieltag}']
        if repaired:
            summary_parts.append(f'{repaired} Reparatur(en)')
        if skipped:
            summary_parts.append(f'{skipped} bereits vollständig')
        messages.success(request, 'Finanzlauf nachgeholt: ' + ' · '.join(summary_parts) + '.')

    return redirect(redirect_url)


@staff_member_required
def creator_kalibrierung(request):
    """Kalibrierung & Regler-Pflege (Finanzsystem Phase 7, Spec Kap. 16).

    Drei Abschnitte: (1) Kennzahlen-Report Live-Ledger vs. Zielkorridore,
    (2) Regler-Übersicht aller EconomyParameter mit [KALIBRIERUNG]-Badge,
    Saison-Historie und Edit-Formular (Versionierung: Speichern schreibt
    IMMER die aktuelle Saison, ältere Saisons bleiben unangetastet),
    (3) Kalibrierungs-Leitfaden (welcher Regler wirkt auf welche Kennzahl).
    Keine Selbstjustierung — jede Änderung ist eine Admin-Entscheidung.
    """
    import json as _json

    from .economy import kalibrierung
    from .economy.params import current_season as _cur_season
    from .models import EconomyParameter

    saison = _cur_season()

    def _typ_kategorie(v):
        if isinstance(v, bool):
            return 'Wahrheitswert'
        if isinstance(v, (int, float)):
            return 'Zahl'
        if isinstance(v, str):
            return 'Text'
        if isinstance(v, dict):
            return 'Objekt'
        if isinstance(v, list):
            return 'Liste'
        return 'Unbekannt'

    if request.method == 'POST':
        key = (request.POST.get('key') or '').strip()
        raw = request.POST.get('value') or ''

        alt_row = (
            EconomyParameter.objects.filter(key=key)
            .order_by('-saison').first()
        )
        if alt_row is None:
            messages.error(
                request,
                f'Unbekannter Parameter-Key „{key}" — neue Keys entstehen '
                'nur über Seed-Migrationen.',
            )
            return redirect('creator_kalibrierung')

        try:
            neu = _json.loads(raw)
        except ValueError as exc:
            messages.error(
                request, f'Ungültiges JSON für {key}: {exc}')
            return redirect('creator_kalibrierung')

        from .economy.params import get_param
        alt = get_param(key, saison)
        if _typ_kategorie(neu) != _typ_kategorie(alt):
            messages.error(
                request,
                f'Typwechsel abgelehnt: {key} ist bisher '
                f'{_typ_kategorie(alt)}, der neue Wert wäre '
                f'{_typ_kategorie(neu)} — das würde Finanzläufe brechen.',
            )
            return redirect('creator_kalibrierung')

        if key == 'KI_KAEUFER' and isinstance(neu, dict):
            # Operativer Schalter der KI-Transferzentrale — hier bewahren,
            # damit ein Regler-Edit die KI nicht versehentlich scharf
            # schaltet oder lahmlegt.
            neu['dry_run'] = bool(alt.get('dry_run', True))

        EconomyParameter.objects.update_or_create(
            saison=saison, key=key, defaults={'value': neu},
        )
        messages.success(
            request,
            f'{key} für Saison {saison} gespeichert '
            f'(ältere Saisons bleiben unverändert).',
        )
        return redirect('creator_kalibrierung')

    # ── Abschnitt 1: Kennzahlen-Report ───────────────────────────────
    sel_season = request.GET.get('saison') or saison
    report = kalibrierung.kalibrierungs_report(sel_season)

    def _pct(v, signed=True):
        if v is None:
            return '—'
        fmt = f'{v * 100:+.1f} %' if signed else f'{v * 100:.1f} %'
        return fmt.replace('.', ',')

    def _num(v, nk=2):
        return (f'{v:.{nk}f}'.replace('.', ',')
                if v is not None else '—')

    kennzahl_rows = []
    for k in report['kennzahlen']:
        ist_zeilen = []
        if k['id'] == 'geldmenge':
            ist_zeilen.append(f"Wachstum {_pct(k['wachstum'])} · "
                              f"MW-Drift {_pct(k['mw_drift'])}")
        elif k['id'] == 'abloese_mw':
            ist_zeilen.append(f"Median {_num(k['median'])} "
                              f"({k['count']} Transfers)")
        elif k['id'] == 'gehaltslasten':
            ist_zeilen.append(
                f"klein {_pct(k['quote_klein'], signed=False)} · "
                f"top {_pct(k['quote_top'], signed=False)} "
                f"({k['clubs_gesamt']} Vereine, Gruppen je "
                f"{k['gruppen_groesse']})")
            if k['laufend']:
                ist_zeilen.append('Werte anteilig — laufende Saison')
        elif k['id'] == 'zuschauer':
            ist_zeilen.append(
                f"Median-Ratio {_num(k['median'])} · Auslastung "
                f"{_pct((k['auslastung_median'] or 0) / 100, signed=False) if k['auslastung_median'] is not None else '—'} "
                f"({k['spiele']} Heimspiele)")
            for a in k['ausreisser']:
                ist_zeilen.append(
                    f"Ausreißer: {a['club']} — Ratio {_num(a['ratio'])}")
        elif k['id'] == 'ki_anteil':
            ist_zeilen.append(
                f"KI-Anteil {_pct(k['anteil'], signed=False)} "
                f"(Limit {_pct(k['limit'], signed=False)})")
        kennzahl_rows.append({
            'titel': k['titel'],
            'korridor': k['korridor'],
            'status': k['status'],
            'status_label': kalibrierung.STATUS_LABELS[k['status']],
            'hinweis': k['hinweis'],
            'fussnote': k.get('fussnote', ''),
            'regler': k['regler'],
            'ist_zeilen': ist_zeilen,
        })

    # ── Abschnitt 2: Regler-Übersicht + Saison-Historie ──────────────
    registry = {r['key']: r for r in kalibrierung.KALIBRIERUNG_REGLER
                if r['key']}
    historie: dict[str, list] = {}
    for row in EconomyParameter.objects.all().order_by('key'):
        historie.setdefault(row.key, []).append((row.saison, row.value))

    def _saison_key(s):
        return (0, int(s)) if (s or '').lstrip('-').isdigit() else (1, 0)

    param_rows = []
    for key in sorted(historie):
        versionen = sorted(historie[key], key=lambda t: _saison_key(t[0]))
        exakt = next((v for s, v in versionen if s == saison), None)
        herkunft, wert = versionen[-1]
        for s, v in reversed(versionen):
            if _saison_key(s) <= _saison_key(saison):
                herkunft, wert = s, v
                break
        reg = registry.get(key)
        param_rows.append({
            'key': key,
            'kalibrierung': key in kalibrierung.KALIBRIERUNG_KEYS,
            'kapitel': reg['kapitel'] if reg else '',
            'beschreibung': reg['beschreibung'] if reg else '',
            'wert_json': _json.dumps(wert, indent=2, ensure_ascii=False,
                                     sort_keys=True),
            'typ': _typ_kategorie(wert),
            'herkunft': herkunft,
            'aktuell': exakt is not None,
            'versionen': [
                {'saison': s,
                 'wert_json': _json.dumps(v, ensure_ascii=False,
                                          sort_keys=True)}
                for s, v in versionen
            ],
        })
    param_rows.sort(key=lambda r: (not r['kalibrierung'], r['key']))

    # ── Abschnitt 3: Leitfaden (Regler → Kennzahl) ───────────────────
    kennzahl_titel = {k['id']: k['titel'] for k in report['kennzahlen']}
    leitfaden_rows = [{
        'name': r['key'] or r.get('titel', ''),
        'hat_key': bool(r['key']),
        'kalibrierung': r.get('kalibrierung', False),
        'kapitel': r['kapitel'],
        'kennzahlen': [kennzahl_titel.get(kid, kid)
                       for kid in r['wirkt_auf']],
        'beschreibung': r['beschreibung'],
    } for r in kalibrierung.KALIBRIERUNG_REGLER]

    from .models import FinanceTransaction
    saison_options = sorted(
        {s for s in FinanceTransaction.objects
         .values_list('saison', flat=True).distinct()
         if (s or '').isdigit()},
        key=int,
    )
    if sel_season not in saison_options:
        saison_options.append(sel_season)

    return render(request, 'creator/kalibrierung.html', {
        'saison': saison,
        'sel_season': sel_season,
        'saison_options': saison_options,
        'kennzahl_rows': kennzahl_rows,
        'alarm_count': report['alarm_count'],
        'warn_count': report['warn_count'],
        'nicht_messbar_count': report['nicht_messbar_count'],
        'ok_count': (len(kennzahl_rows) - report['alarm_count']
                     - report['warn_count']
                     - report['nicht_messbar_count']),
        'param_rows': param_rows,
        'kalibrierung_count': sum(
            1 for r in param_rows if r['kalibrierung']),
        'leitfaden_rows': leitfaden_rows,
    })


@staff_member_required
def creator_ki_angebote(request):
    """Creator-Übersicht aller Scouting-Gebote mit Verhandlungsstatus und Begründung."""
    from .models import ScoutingBid, ScoutingAssignment

    PROFILE_LABELS = {
        'backup': 'Back-up',
        'ergaenzung': 'Ergänzungsspieler',
        'rotation': 'Rotationsspieler',
        'stammkraft': 'Stammkraft',
        'talent': 'Jugendspieler / Talent',
    }

    STATUS_LABELS = {
        'active': 'Aktiv',
        'won': 'Gewonnen',
        'lost': 'Verloren',
        'cancelled': 'Zurückgezogen',
    }

    def _fmt(v):
        if v is None:
            return '—'
        try:
            v = float(v)
        except (TypeError, ValueError):
            return '—'
        if v >= 1_000_000:
            return f'{v / 1_000_000:.1f} Mio. €'
        if v >= 1_000:
            return f'{int(v):,} €'.replace(',', '.')
        return f'{int(v)} €'

    q_status = request.GET.get('status', '')
    q_typ = request.GET.get('typ', '')
    q_club = request.GET.get('q', '').strip()
    q_season = request.GET.get('season', '')

    qs = ScoutingBid.objects.select_related(
        'club', 'club__league', 'player', 'manager', 'find', 'find__assignment',
    ).order_by('-created_at')

    if q_status:
        qs = qs.filter(status=q_status)
    if q_typ == 'ki':
        qs = qs.filter(manager__isnull=True)
    elif q_typ == 'mensch':
        qs = qs.filter(manager__isnull=False)
    if q_club:
        qs = qs.filter(club__name__icontains=q_club)
    if q_season:
        try:
            qs = qs.filter(season_id=int(q_season))
        except ValueError:
            pass

    rows = []
    for bid in qs[:200]:
        profile_label = ''
        position_filter = ''
        if bid.find and bid.find.assignment:
            asgn = bid.find.assignment
            profile_label = PROFILE_LABELS.get(asgn.profile, asgn.profile)
            position_filter = asgn.position or ''

        begruendung = profile_label
        if position_filter:
            begruendung = f'{profile_label} ({position_filter})' if profile_label else position_filter

        rows.append({
            'id': bid.pk,
            'club_name': bid.club.name,
            'club_id': bid.club.pk,
            'league_name': bid.club.league.name if bid.club.league_id else '—',
            'player_name': bid.player.name if bid.player else '—',
            'player_id': bid.player_id,
            'player_pos': bid.player.position if bid.player else '',
            'amount_fmt': _fmt(bid.amount),
            'min_bid_fmt': _fmt(bid.min_bid),
            'status': bid.status,
            'status_label': STATUS_LABELS.get(bid.status, bid.status),
            'window_date': bid.window_date.strftime('%d.%m.%Y') if bid.window_date else '—',
            'created_at': bid.created_at.strftime('%d.%m.%Y %H:%M'),
            'settled_on': bid.settled_on.strftime('%d.%m.%Y') if bid.settled_on else '—',
            'is_ki': bid.manager_id is None,
            'manager_name': str(bid.manager) if bid.manager_id else 'KI',
            'coin_earmarked': bid.coin_earmarked,
            'begruendung': begruendung or '—',
            'season_id': bid.season_id,
        })

    total = ScoutingBid.objects.count()
    active_count = ScoutingBid.objects.filter(status='active').count()
    ki_count = ScoutingBid.objects.filter(manager__isnull=True).count()
    human_count = ScoutingBid.objects.filter(manager__isnull=False).count()

    season_ids = (
        ScoutingBid.objects.values_list('season_id', flat=True)
        .order_by('season_id').distinct()
    )

    return render(request, 'creator/ki_angebote.html', {
        'rows': rows,
        'total': total,
        'active_count': active_count,
        'ki_count': ki_count,
        'human_count': human_count,
        'q_status': q_status,
        'q_typ': q_typ,
        'q_club': q_club,
        'q_season': q_season,
        'season_ids': list(season_ids),
        'result_count': len(rows),
    })


@staff_member_required
def creator_ki_transferzentrale(request):
    """KI-Transferzentrale (Finanzsystem Phase 6, Spec Kap. 9.3).

    Live-Übersicht aller Angebote des aktiven KI-Käufers mit Eingriffen:
    Angebot stornieren, KI-Verein pausieren, globaler Trockenlauf-Schalter,
    Transferfenster öffnen/schließen. Interne Rechnungsgrößen (Bewertung,
    Käufer-Maximum) sind hier bewusst sichtbar — Admin-Review-Werkzeug;
    an Manager-Clients gehen sie weiterhin NIE raus.
    """
    from .economy.ai_buyer import governor_status
    from .economy.params import current_season, get_param
    from .models import AIBuyerRun, AITransferOffer, EconomyParameter

    saison = current_season()
    state, _ = GameSeasonState.objects.get_or_create(pk=1)

    def _fmt(v):
        if v is None:
            return '—'
        try:
            v = float(v)
        except (TypeError, ValueError):
            return '—'
        if v >= 1_000_000:
            return f'{v / 1_000_000:.1f} Mio. €'
        return f'{int(v):,} €'.replace(',', '.')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'storno':
            offer = get_object_or_404(
                AITransferOffer, pk=request.POST.get('offer_id'))
            if offer.status in AITransferOffer.OFFENE_STATUS:
                offer.status = AITransferOffer.STATUS_STORNIERT
                offer.begruendung = (
                    offer.begruendung + '\nStorno durch Admin '
                    f'({timezone.localtime():%d.%m.%Y %H:%M}).'
                ).strip()
                offer.save(update_fields=['status', 'begruendung', 'updated_at'])
                messages.success(
                    request,
                    f'Angebot #{offer.pk} ({offer.player.full_name}) storniert.',
                )
            else:
                messages.error(request, 'Angebot ist nicht mehr offen.')

        elif action == 'pause_club':
            club = get_object_or_404(Club, pk=request.POST.get('club_id'))
            club.ai_buyer_paused = request.POST.get('pause') == '1'
            club.save(update_fields=['ai_buyer_paused'])
            messages.success(
                request,
                f'KI-Käufer für {club.name} '
                f'{"pausiert" if club.ai_buyer_paused else "reaktiviert"}.',
            )

        elif action == 'dry_run':
            scharf = request.POST.get('value') == '0'
            wert = dict(get_param('KI_KAEUFER', saison))
            wert['dry_run'] = not scharf
            EconomyParameter.objects.update_or_create(
                saison=saison, key='KI_KAEUFER', defaults={'value': wert},
            )
            storniert = 0
            if scharf:
                # Trockenlauf-Reste räumen: 'berechnet'-Angebote aus dem
                # Trockenlauf zählen sonst weiter gegen Kadenz-Limits und
                # sperren Kandidaten (haben kein gueltig_bis, laufen nie ab).
                stempel = (
                    '\nStorno: Trockenlauf-Altbestand beim Scharfschalten '
                    f'({timezone.localtime():%d.%m.%Y %H:%M}).'
                )
                for alt in AITransferOffer.objects.filter(
                        dry_run=True,
                        status=AITransferOffer.STATUS_BERECHNET):
                    alt.status = AITransferOffer.STATUS_STORNIERT
                    alt.begruendung = (alt.begruendung + stempel).strip()
                    alt.save(update_fields=[
                        'status', 'begruendung', 'updated_at'])
                    storniert += 1
            messages.success(
                request,
                'KI-Käufer SCHARF geschaltet — Angebote werden versendet.'
                + (f' {storniert} Trockenlauf-Angebote storniert.'
                   if storniert else '')
                if scharf else
                'Trockenlauf aktiviert — Angebote werden nur berechnet.',
            )

        elif action == 'fenster':
            oeffnen = request.POST.get('value') == '1'
            state.transfer_window_open = oeffnen
            if oeffnen and not state.transfer_window_id:
                state.transfer_window_id = f'{saison}-F1'
            state.save(update_fields=['transfer_window_open',
                                      'transfer_window_id'])
            messages.success(
                request,
                f'Transferfenster {"geöffnet" if oeffnen else "geschlossen"} '
                f'(Fenster-ID {state.transfer_window_id or "—"}).',
            )

        else:
            messages.error(request, 'Unbekannte Aktion.')
        return redirect('creator_ki_transferzentrale')

    params = get_param('KI_KAEUFER', saison)
    dry_run = bool(params.get('dry_run', True))
    governor = governor_status(saison, params)

    q_status = request.GET.get('status', '')
    q_typ = request.GET.get('typ', '')
    q_club = request.GET.get('q', '').strip()

    qs = (
        AITransferOffer.objects
        .select_related('buyer_club', 'seller_club', 'player',
                        'seller_club__managed_by')
        .order_by('-updated_at')
    )
    if q_status:
        qs = qs.filter(status=q_status)
    if q_typ:
        qs = qs.filter(kauftyp=q_typ)
    if q_club:
        qs = qs.filter(buyer_club__name__icontains=q_club)

    rows = []
    for o in qs[:200]:
        rows.append({
            'id': o.pk,
            'buyer_name': o.buyer_club.name,
            'buyer_id': o.buyer_club_id,
            'buyer_paused': o.buyer_club.ai_buyer_paused,
            'seller_name': o.seller_club.name,
            'seller_typ': 'Manager' if o.seller_club.managed_by_id else 'KI',
            'player_name': o.player.full_name,
            'player_id': o.player_id,
            'kauftyp': o.kauftyp,
            'kauftyp_label': o.get_kauftyp_display(),
            'bewertung_fmt': _fmt(o.bewertung),
            'max_gebot_fmt': _fmt(o.max_gebot),
            'gebot_fmt': _fmt(o.aktuelles_gebot),
            'stufe': o.stufe,
            'status': o.status,
            'status_label': o.get_status_display(),
            'dry_run': o.dry_run,
            'window_id': o.window_id,
            'offen': o.status in AITransferOffer.OFFENE_STATUS,
            'luecken_score': (f'{o.luecken_score:.1f}'
                              if o.luecken_score is not None else '—'),
            'ki_meta': o.ki_meta or {},
            'begruendung': o.begruendung,
            'updated_at': timezone.localtime(o.updated_at)
                          .strftime('%d.%m.%Y %H:%M'),
        })

    laeufe = (
        AIBuyerRun.objects
        .select_related('club')
        .order_by('-run_at')[:20]
    )
    lauf_rows = []
    for lauf in laeufe:
        report = lauf.report or {}
        lauf_rows.append({
            'club_name': lauf.club.name,
            'spieltag': lauf.spieltag,
            'trigger': lauf.trigger,
            'dry_run': lauf.dry_run,
            'kaeufe': len(report.get('kaeufe', [])),
            'entscheidungen': report.get('entscheidungen', []),
            'created_at': timezone.localtime(lauf.run_at)
                          .strftime('%d.%m.%Y %H:%M'),
        })

    pausierte = list(
        Club.objects.filter(ai_buyer_paused=True).order_by('name')
        .values('id', 'name')
    )

    offen_count = AITransferOffer.objects.filter(
        status=AITransferOffer.STATUS_VERSENDET).count()
    berechnet_count = AITransferOffer.objects.filter(
        status=AITransferOffer.STATUS_BERECHNET).count()
    deal_count = AITransferOffer.objects.filter(
        status=AITransferOffer.STATUS_DEAL).count()

    return render(request, 'creator/ki_transferzentrale.html', {
        'rows': rows,
        'result_count': len(rows),
        'total': AITransferOffer.objects.count(),
        'offen_count': offen_count,
        'berechnet_count': berechnet_count,
        'deal_count': deal_count,
        'dry_run': dry_run,
        'window_open': state.transfer_window_open,
        'window_id': state.transfer_window_id or '—',
        'saison': saison,
        'governor_anteil': f'{governor["anteil"]:.0%}',
        'governor_limit': f'{governor["limit"]:.0%}',
        'governor_ueberschritten': governor['ueberschritten'],
        'governor_ki_fmt': _fmt(governor['ki_volumen']),
        'governor_gesamt_fmt': _fmt(governor['gesamt_volumen']),
        'lauf_rows': lauf_rows,
        'pausierte': pausierte,
        'q_status': q_status,
        'q_typ': q_typ,
        'q_club': q_club,
        'status_choices': AITransferOffer.STATUS_CHOICES,
        'kauftyp_choices': AITransferOffer.KAUFTYP_CHOICES,
    })


@staff_member_required
def creator_sportgericht(request):
    """Creator-Übersicht Zahlungsunfähigkeit (Spec Kap. 12.3).

    Listet offene Vermerke; nach Fristablauf (und weiterhin negativem
    Konto) kann der Admin hier Zwangsversteigerungen ansetzen.
    """
    from django.utils import timezone as tz
    from .economy import forced_auction as fa_service
    from .models import ForcedAuction, InsolvencyCase, Player

    def _fmt(v):
        if v is None:
            return '—'
        try:
            v = float(v)
        except (TypeError, ValueError):
            return '—'
        return f'{int(v):,} €'.replace(',', '.')

    if request.method == 'POST':
        case = get_object_or_404(InsolvencyCase, pk=request.POST.get('case_id'))
        player = get_object_or_404(Player, pk=request.POST.get('player_id'))
        raw = (request.POST.get('min_bid') or '').replace('.', '').replace(',', '.')
        try:
            min_bid = Decimal(raw)
        except (InvalidOperation, ValueError):
            messages.error(request, 'Ungültiges Mindestgebot.')
            return redirect('creator_sportgericht')
        try:
            auction = fa_service.start_auction(case, player, min_bid)
            messages.success(
                request,
                f'Zwangsversteigerung angesetzt: {player.full_name}, '
                f'Mindestgebot {_fmt(auction.min_bid)}, '
                f'Zuschlag am {auction.ends_on:%d.%m.%Y}.',
            )
        except fa_service.ForcedAuctionError as exc:
            messages.error(request, str(exc))
        return redirect('creator_sportgericht')

    now = tz.now()
    case_rows = []
    open_cases = (
        InsolvencyCase.objects
        .filter(status__in=[InsolvencyCase.STATUS_OPEN,
                            InsolvencyCase.STATUS_ENFORCED])
        .select_related('club')
        .order_by('deadline_at')
    )
    for case in open_cases:
        club = case.club
        deadline_passed = now >= case.deadline_at
        enforceable = deadline_passed and (club.budget or 0) < 0
        players = []
        if enforceable:
            players = list(
                Player.objects.filter(club=club)
                .order_by('-market_value', 'last_name')
                .values('id', 'first_name', 'last_name', 'position',
                        'market_value')
            )
            for p in players:
                p['mv_fmt'] = _fmt(p['market_value'])
        case_rows.append({
            'case': case,
            'club': club,
            'budget_fmt': _fmt(club.budget),
            'eroeffnung_fmt': _fmt(case.betrag_bei_eroeffnung),
            'deadline_passed': deadline_passed,
            'enforceable': enforceable,
            'players': players,
            'open_auctions': case.forced_auctions.filter(
                status=ForcedAuction.STATUS_OPEN).count(),
        })

    from django.core.cache import cache
    from game.models import ForcedAuctionBid

    auction_rows = []
    auctions_qs = list(
        ForcedAuction.objects
        .select_related('player', 'seller_club', 'winning_bid',
                        'winning_bid__club')
        .order_by('-created_at')[:100]
    )
    auction_pks = [a.pk for a in auctions_qs]
    bids_by_auction: dict = {pk: [] for pk in auction_pks}
    for bid in (
        ForcedAuctionBid.objects
        .filter(auction_id__in=auction_pks)
        .select_related('club', 'manager')
        .order_by('-amount', 'created_at')
    ):
        bids_by_auction[bid.auction_id].append({
            'club_name': bid.club.name,
            'amount_fmt': _fmt(bid.amount),
            'is_ki': bid.manager_id is None,
            'ki_meta': bid.ki_meta,
            'created_at': bid.created_at,
        })

    for a in auctions_qs:
        bids = bids_by_auction[a.pk]
        auction_rows.append({
            'auction': a,
            'min_bid_fmt': _fmt(a.min_bid),
            'bid_count': len(bids),
            'bids': bids,
            'winner_name': (a.winning_bid.club.name
                            if a.winning_bid_id else '—'),
            'winner_amount_fmt': (_fmt(a.winning_bid.amount)
                                  if a.winning_bid_id else '—'),
        })

    from .economy.forced_auction import load_ki_summary
    ki_summary = load_ki_summary()

    resolved_cases = (
        InsolvencyCase.objects
        .filter(status=InsolvencyCase.STATUS_RESOLVED)
        .select_related('club')
        .order_by('-resolved_at')[:20]
    )

    return render(request, 'creator/sportgericht.html', {
        'case_rows': case_rows,
        'auction_rows': auction_rows,
        'resolved_cases': resolved_cases,
        'ki_summary': ki_summary,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# SCHIEDSRICHTER — Creator Mode
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def creator_referee_list(request):
    q = request.GET.get('q', '').strip()
    qs = Referee.objects.all().order_by('name')
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, 'creator/referee_list.html', {
        'referees': list(qs),
        'q': q,
        'total': Referee.objects.count(),
    })


@login_required
def creator_referee_edit(request, referee_id=None):
    if referee_id:
        ref = get_object_or_404(Referee, pk=referee_id)
        is_new = False
    else:
        ref = Referee()
        is_new = True
    return render(request, 'creator/referee_edit.html', {
        'ref': ref,
        'is_new': is_new,
        'level_choices': [(5, 'Weltklasse'), (4, 'International'), (3, 'Erste Liga'), (2, 'Zweite Liga'), (1, 'Aufsteiger')],
    })


@login_required
@require_POST
def creator_referee_save(request, referee_id=None):
    if referee_id:
        ref = get_object_or_404(Referee, pk=referee_id)
    else:
        ref = Referee()

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Name darf nicht leer sein.')
        return redirect(request.META.get('HTTP_REFERER', 'creator_referee_list'))

    # fm_uid (optional, unique)
    fm_uid_raw = request.POST.get('fm_uid', '').strip()
    fm_uid = int(fm_uid_raw) if fm_uid_raw else None
    if fm_uid is not None:
        dup = Referee.objects.filter(fm_uid=fm_uid).exclude(pk=ref.pk or 0)
        if dup.exists():
            messages.error(request, f'FM-UID {fm_uid} ist bereits einem anderen Schiedsrichter zugewiesen.')
            return redirect(request.META.get('HTTP_REFERER', 'creator_referee_list'))

    ref.name = name
    ref.fm_uid = fm_uid
    ref.nationality = request.POST.get('nationality', '').strip()
    ref.nationality_code = request.POST.get('nationality_code', '').strip()
    ref.schlagwort = request.POST.get('schlagwort', '').strip()

    # birth_date
    bd_raw = request.POST.get('birth_date', '').strip()
    if bd_raw:
        from django.utils.dateparse import parse_date
        ref.birth_date = parse_date(bd_raw)
    else:
        ref.birth_date = None

    # level 1–5
    try:
        ref.level = max(1, min(5, int(request.POST.get('level', 3))))
    except (ValueError, TypeError):
        ref.level = 3

    # quote 1–20
    try:
        ref.quote = max(1, min(20, int(request.POST.get('quote', 10))))
    except (ValueError, TypeError):
        ref.quote = 10

    # tendencies — fine-grained 1–20
    try:
        kt = max(1, min(20, int(request.POST.get('karten_tendenz', 10))))
    except (ValueError, TypeError):
        kt = 10
    try:
        st = max(1, min(20, int(request.POST.get('spielfluss_tendenz', 11))))
    except (ValueError, TypeError):
        st = 11
    ref.karten_tendenz = kt
    ref.spielfluss_tendenz = st

    # vorsaison stats
    def _int(key, default=0):
        try:
            return max(0, int(request.POST.get(key, default)))
        except (ValueError, TypeError):
            return default

    def _dec(key, default='0'):
        import decimal
        try:
            return decimal.Decimal(str(request.POST.get(key, default)).replace(',', '.'))
        except Exception:
            return decimal.Decimal(default)

    ref.vorsaison_spiele = _int('vorsaison_spiele')
    ref.vorsaison_gelb_avg = _dec('vorsaison_gelb_avg')
    ref.vorsaison_rot = _int('vorsaison_rot')
    ref.vorsaison_elfmeter = _int('vorsaison_elfmeter')
    ref.vorsaison_umstritten = _int('vorsaison_umstritten')

    comps_raw = request.POST.get('vorsaison_competitions', '').strip()
    ref.vorsaison_competitions = [c.strip() for c in comps_raw.split(',') if c.strip()] if comps_raw else []

    ref.save()

    # ── Auto-Copy: Spieler-Ordner → Referee-Ordner ───────────────────────────
    if ref.fm_uid:
        import shutil
        from django.conf import settings as _settings
        assets_root = str(_settings.ASSETS_ROOT).rstrip('/')
        ref_dir = os.path.join(assets_root, 'referees')
        os.makedirs(ref_dir, exist_ok=True)

        # Existiert das Bild bereits im Referee-Ordner? → überspringen
        already = next(
            (os.path.join(ref_dir, f'face_{ref.fm_uid}.{ext}')
             for ext in ('png', 'jpg', 'jpeg')
             if os.path.exists(os.path.join(ref_dir, f'face_{ref.fm_uid}.{ext}'))),
            None,
        )
        if already:
            messages.info(request, f'Bild bereits vorhanden — übersprungen ({os.path.basename(already)}).')
        else:
            # Suche im Spieler-Ordner
            player_dir = os.path.join(assets_root, 'players')
            src = next(
                (os.path.join(player_dir, f'face_{ref.fm_uid}.{ext}')
                 for ext in ('png', 'jpg', 'jpeg')
                 if os.path.exists(os.path.join(player_dir, f'face_{ref.fm_uid}.{ext}'))),
                None,
            )
            if src:
                ext = os.path.splitext(src)[1]
                dest = os.path.join(ref_dir, f'face_{ref.fm_uid}{ext}')
                shutil.copy2(src, dest)
                messages.info(request, f'Bild aus Spieler-Ordner kopiert: face_{ref.fm_uid}{ext}')

    # ── Manueller Upload (Override) ───────────────────────────────────────────
    img = request.FILES.get('face_image')
    if img and ref.fm_uid:
        from django.conf import settings as _settings
        ref_dir = os.path.join(str(_settings.ASSETS_ROOT).rstrip('/'), 'referees')
        os.makedirs(ref_dir, exist_ok=True)
        dest = os.path.join(ref_dir, f'face_{ref.fm_uid}.png')
        with open(dest, 'wb') as f:
            for chunk in img.chunks():
                f.write(chunk)
        messages.success(request, f'Bild für {ref.name} manuell gespeichert.')
    elif img and not ref.fm_uid:
        messages.warning(request, 'Bild ignoriert — bitte zuerst eine FM-UID setzen.')

    messages.success(request, f'Schiedsrichter „{ref.name}" gespeichert.')
    return redirect('creator_referee_edit', referee_id=ref.pk)


@login_required
@require_POST
def creator_referee_delete(request, referee_id):
    ref = get_object_or_404(Referee, pk=referee_id)
    name = ref.name
    ref.delete()
    messages.success(request, f'Schiedsrichter „{name}" gelöscht.')
    return redirect('creator_referee_list')


# ── Transferaufsicht (Task #824) ──────────────────────────────────────────

@staff_member_required
def creator_transferaufsicht(request):
    """Creator-Transferaufsicht — Melde-Queue, Admin-Aktionen, Settings."""
    import json as _json

    from .economy.params import current_season as _cur_season, get_param
    from .models import EconomyParameter
    from .transfer_v2.models import (
        ClubPartnership, CreatorActionLog, LoanListing, SquadLimitNote,
        TransferListing, TransferRecord, TransferReport,
    )

    saison = _cur_season()

    # ── Melde-Queue ───────────────────────────────────────────────────────
    open_reports = (
        TransferReport.objects
        .filter(status=TransferReport.STATUS_OPEN)
        .select_related('reporter_club', 'record', 'record__club_a', 'record__club_b')
        .prefetch_related('record__players__player', 'record__youth_levies')
        .order_by('created_at')
    )

    # ── Historie-Zugriff ──────────────────────────────────────────────────
    record_search_id = request.GET.get('record_id', '').strip()
    searched_record = None
    if record_search_id:
        try:
            searched_record = (
                TransferRecord.objects
                .select_related('club_a', 'club_b')
                .prefetch_related('players__player', 'youth_levies')
                .get(pk=int(record_search_id))
            )
        except (TransferRecord.DoesNotExist, ValueError):
            pass

    recent_records = (
        TransferRecord.objects
        .select_related('club_a', 'club_b')
        .prefetch_related('players__player')
        .order_by('-date', '-id')[:20]
    )

    # ── Aktive Auktionen ──────────────────────────────────────────────────
    active_listings = (
        TransferListing.objects
        .filter(status=TransferListing.STATUS_ACTIVE)
        .select_related('player', 'seller')
        .order_by('ends_at', 'id')
    )
    active_loan_listings = (
        LoanListing.objects
        .filter(status=LoanListing.STATUS_ACTIVE)
        .select_related('player', 'owner_club')
        .order_by('-created_at')
    )

    # ── Kadergrenzen-Vermerke ─────────────────────────────────────────────
    squad_notes = (
        SquadLimitNote.objects
        .select_related('club', 'player')
        .order_by('-created_at')[:50]
    )

    # ── ClubPartnerships ──────────────────────────────────────────────────
    partnerships = (
        ClubPartnership.objects
        .filter(active=True)
        .select_related('club_a', 'club_b')
        .order_by('club_a__name')
    )
    all_clubs = Club.objects.order_by('name')

    # ── Aktionsprotokoll ──────────────────────────────────────────────────
    action_logs = (
        CreatorActionLog.objects
        .select_related('actor')
        .order_by('-created_at')[:30]
    )

    # ── Settings-Parameter ────────────────────────────────────────────────
    SETTINGS_KEYS = [
        'RUMOR_P_NEWS', 'RUMOR_P_EXACT', 'LEIHE_LIMIT_REIN',
        'LEIHE_LIMIT_RAUS', 'LEIHE_LIMIT_JE_PAAR', 'LEIHE_DEADLINE_SPIELTAGE',
        'TRANSFER_WECHSELSPERRE_TAGE', 'LEIHE_MIN_GEBUEHR',
        'TRANSFER_MIN_GEBOT', 'TRANSFER_MIN_ERHOEHUNG_ABS',
        'TRANSFER_MIN_ERHOEHUNG_PCT', 'TRANSFER_ERHOEHUNG_RUNDUNG',
        'TRANSFER_TICKER_ENABLED',
    ]
    settings_rows = []
    for key in SETTINGS_KEYS:
        try:
            val = get_param(key, saison)
        except Exception:
            val = None
        settings_rows.append({
            'key': key,
            'value_json': _json.dumps(val, ensure_ascii=False),
        })

    return render(request, 'creator/transferaufsicht.html', {
        'nav_active': 'aufsicht',
        'open_reports': open_reports,
        'searched_record': searched_record,
        'record_search_id': record_search_id,
        'recent_records': recent_records,
        'active_listings': active_listings,
        'active_loan_listings': active_loan_listings,
        'squad_notes': squad_notes,
        'partnerships': partnerships,
        'all_clubs': all_clubs,
        'action_logs': action_logs,
        'settings_rows': settings_rows,
        'saison': saison,
    })


@staff_member_required
@require_POST
def creator_transferaufsicht_report_action(request):
    """Meldung abweisen oder in Überprüfung stellen."""
    from .transfer_v2.admin_actions import log_creator_action
    from .transfer_v2.models import TransferReport
    from .transfer_v2 import push

    report = get_object_or_404(TransferReport, pk=request.POST.get('report_id'))
    action = request.POST.get('action', '')

    if action == 'dismiss':
        report.status = TransferReport.STATUS_DISMISSED
        report.resolved_at = timezone.now()
        report.save(update_fields=['status', 'resolved_at'])
        push.report_resolved(report, 'abgewiesen')
        messages.success(request, f'Meldung #{report.pk} abgewiesen.')
        log_creator_action(
            request.user, 'report_dismiss',
            f'Report #{report.pk}',
            report_id=report.pk,
        )
    elif action == 'review':
        report.status = TransferReport.STATUS_UNDER_REVIEW
        report.resolved_at = timezone.now()
        report.save(update_fields=['status', 'resolved_at'])
        push.report_resolved(report, 'in Überprüfung (Sportgericht)')
        messages.success(request, f'Meldung #{report.pk} in Überprüfung gestellt.')
        log_creator_action(
            request.user, 'report_review',
            f'Report #{report.pk}',
            report_id=report.pk,
        )
    else:
        messages.error(request, 'Unbekannte Aktion.')

    return redirect('creator_transferaufsicht')


@staff_member_required
@require_POST
def creator_transferaufsicht_cancel_record(request):
    """Admin-Storno eines TransferRecords."""
    from .transfer_v2.admin_actions import TransferActionError, admin_cancel_record

    record_id = request.POST.get('record_id', '').strip()
    grund = request.POST.get('grund', '').strip()

    if not grund:
        messages.error(request, 'Bitte einen Grund angeben.')
        return redirect('creator_transferaufsicht')

    try:
        from .transfer_v2.models import TransferRecord as _TR
        record = get_object_or_404(_TR, pk=int(record_id))
        admin_cancel_record(record, grund=grund, actor=request.user)
        messages.success(request, f'Record #{record_id} erfolgreich storniert.')
    except TransferActionError as exc:
        messages.error(request, f'Fehler: {exc}')
    except (ValueError, TypeError):
        messages.error(request, 'Ungültige Record-ID.')
    except Exception as exc:
        messages.error(request, f'Fehler: {exc}')

    return redirect('creator_transferaufsicht')


@staff_member_required
@require_POST
def creator_transferaufsicht_admin_transfer(request):
    """Admin-Transfer (kein Ablöse, keine Abgabe)."""
    from .transfer_v2.admin_actions import TransferActionError, admin_transfer

    try:
        player_id = int(request.POST.get('player_id', ''))
        to_club_id = int(request.POST.get('to_club_id', ''))
        grund = request.POST.get('grund', '').strip()
        player = get_object_or_404(Player, pk=player_id)
        to_club = get_object_or_404(Club, pk=to_club_id)
        admin_transfer(player, to_club, actor=request.user, grund=grund)
        messages.success(request, f'{player.full_name} → {to_club.name} (Admin-Transfer).')
    except TransferActionError as exc:
        messages.error(request, f'Fehler: {exc}')
    except (ValueError, TypeError):
        messages.error(request, 'Ungültige Spieler- oder Verein-ID.')
    except Exception as exc:
        messages.error(request, f'Fehler: {exc}')

    return redirect('creator_transferaufsicht')


@staff_member_required
@require_POST
def creator_transferaufsicht_cancel_listing(request):
    """Admin-Storno einer aktiven Auktion (kein Zuschlag)."""
    from .transfer_v2.admin_actions import TransferActionError, admin_cancel_listing
    from .transfer_v2.models import TransferListing

    try:
        listing_id = int(request.POST.get('listing_id', ''))
        grund = request.POST.get('grund', '').strip()
        listing = get_object_or_404(TransferListing, pk=listing_id)
        admin_cancel_listing(listing, grund=grund, actor=request.user)
        messages.success(request, f'Listing #{listing_id} storniert.')
    except TransferActionError as exc:
        messages.error(request, f'Fehler: {exc}')
    except (ValueError, TypeError):
        messages.error(request, 'Ungültige Listing-ID.')
    except Exception as exc:
        messages.error(request, f'Fehler: {exc}')

    return redirect('creator_transferaufsicht')


@staff_member_required
@require_POST
def creator_transferaufsicht_close_listing(request):
    """Vorzeitiger Zuschlag einer aktiven Auktion."""
    from .transfer_v2.admin_actions import admin_close_listing_now
    from .transfer_v2.models import TransferListing

    try:
        listing_id = int(request.POST.get('listing_id', ''))
        listing = get_object_or_404(TransferListing, pk=listing_id)
        admin_close_listing_now(listing, actor=request.user)
        messages.success(request, f'Listing #{listing_id}: vorzeitiger Zuschlag erteilt.')
    except (ValueError, TypeError):
        messages.error(request, 'Ungültige Listing-ID.')
    except Exception as exc:
        messages.error(request, f'Fehler: {exc}')

    return redirect('creator_transferaufsicht')


@staff_member_required
@require_POST
def creator_transferaufsicht_cancel_loan_listing(request):
    """Admin-Storno eines aktiven Leih-Listings."""
    from .transfer_v2.admin_actions import log_creator_action
    from .transfer_v2.models import LoanListing

    try:
        listing_id = int(request.POST.get('listing_id', ''))
        grund = request.POST.get('grund', '').strip()
        listing = get_object_or_404(LoanListing, pk=listing_id)
        from django.db import transaction as _transaction
        with _transaction.atomic():
            lst = LoanListing.objects.select_for_update().get(pk=listing_id)
            if lst.status != LoanListing.STATUS_ACTIVE:
                messages.error(request, 'Leih-Listing ist nicht aktiv.')
                return redirect('creator_transferaufsicht')
            lst.status = LoanListing.STATUS_WITHDRAWN
            lst.save(update_fields=['status'])
        messages.success(request, f'Leih-Listing #{listing_id} storniert.')
        log_creator_action(
            request.user, 'admin_cancel_loan_listing',
            f'LoanListing #{listing_id} ({listing.player})',
            grund=grund, listing_id=listing_id,
        )
    except (ValueError, TypeError):
        messages.error(request, 'Ungültige Listing-ID.')
    except Exception as exc:
        messages.error(request, f'Fehler: {exc}')

    return redirect('creator_transferaufsicht')


@staff_member_required
@require_POST
def creator_transferaufsicht_squad_note(request):
    """Kadergrenzen-Vermerk im Sportgericht anmerken."""
    from .transfer_v2.admin_actions import log_creator_action
    from .transfer_v2.models import SquadLimitNote

    try:
        note_id = int(request.POST.get('note_id', ''))
        note = get_object_or_404(SquadLimitNote, pk=note_id)
        note.status = SquadLimitNote.STATUS_SPORTGERICHT
        note.save(update_fields=['status'])
        messages.success(request, f'Vermerk #{note_id} im Sportgericht angemerkt.')
        log_creator_action(
            request.user, 'squad_note_sportgericht',
            f'SquadLimitNote #{note_id}',
            note_id=note_id,
        )
    except (ValueError, TypeError):
        messages.error(request, 'Ungültige Vermerks-ID.')
    except Exception as exc:
        messages.error(request, f'Fehler: {exc}')

    return redirect('creator_transferaufsicht')


@staff_member_required
@require_POST
def creator_transferaufsicht_partnership(request):
    """ClubPartnership anlegen oder deaktivieren."""
    from .transfer_v2.admin_actions import log_creator_action
    from .transfer_v2.models import ClubPartnership

    action = request.POST.get('action', '')

    if action == 'create':
        try:
            club_a_id = int(request.POST.get('club_a_id', ''))
            club_b_id = int(request.POST.get('club_b_id', ''))
            club_a = get_object_or_404(Club, pk=club_a_id)
            club_b = get_object_or_404(Club, pk=club_b_id)
            if club_a_id == club_b_id:
                messages.error(request, 'Verein A und B müssen unterschiedlich sein.')
            else:
                ClubPartnership.objects.update_or_create(
                    club_a=club_a if club_a_id < club_b_id else club_b,
                    club_b=club_b if club_a_id < club_b_id else club_a,
                    defaults={'active': True},
                )
                messages.success(request, f'Partnerschaft {club_a.name} ↔ {club_b.name} angelegt.')
                log_creator_action(
                    request.user, 'partnership_create',
                    f'{club_a.name} ↔ {club_b.name}',
                    club_a_id=club_a_id, club_b_id=club_b_id,
                )
        except (ValueError, TypeError):
            messages.error(request, 'Ungültige Verein-ID.')
    elif action == 'deactivate':
        try:
            partnership_id = int(request.POST.get('partnership_id', ''))
            partnership = get_object_or_404(ClubPartnership, pk=partnership_id)
            partnership.active = False
            partnership.save(update_fields=['active'])
            messages.success(request, 'Partnerschaft deaktiviert.')
            log_creator_action(
                request.user, 'partnership_deactivate',
                f'Partnership #{partnership_id}',
                partnership_id=partnership_id,
            )
        except (ValueError, TypeError):
            messages.error(request, 'Ungültige Partnerschaft-ID.')
    else:
        messages.error(request, 'Unbekannte Aktion.')

    return redirect('creator_transferaufsicht')


@staff_member_required
@require_POST
def creator_transferaufsicht_setting(request):
    """Einzel-Einstellung (EconomyParameter) für Transferaufsicht speichern."""
    import json as _json

    from .economy.params import current_season as _cur_season, get_param
    from .models import EconomyParameter
    from .transfer_v2.admin_actions import log_creator_action

    saison = _cur_season()

    def _typ_kategorie(v):
        if isinstance(v, bool):
            return 'Wahrheitswert'
        if isinstance(v, (int, float)):
            return 'Zahl'
        if isinstance(v, str):
            return 'Text'
        if isinstance(v, dict):
            return 'Objekt'
        if isinstance(v, list):
            return 'Liste'
        return 'Unbekannt'

    key = (request.POST.get('key') or '').strip()
    raw = request.POST.get('value') or ''

    ALLOWED_KEYS = {
        'RUMOR_P_NEWS', 'RUMOR_P_EXACT', 'LEIHE_LIMIT_REIN',
        'LEIHE_LIMIT_RAUS', 'LEIHE_LIMIT_JE_PAAR', 'LEIHE_DEADLINE_SPIELTAGE',
        'TRANSFER_WECHSELSPERRE_TAGE', 'LEIHE_MIN_GEBUEHR',
        'TRANSFER_MIN_GEBOT', 'TRANSFER_MIN_ERHOEHUNG_ABS',
        'TRANSFER_MIN_ERHOEHUNG_PCT', 'TRANSFER_ERHOEHUNG_RUNDUNG',
        'TRANSFER_TICKER_ENABLED',
    }

    if key not in ALLOWED_KEYS:
        messages.error(request, f'Unbekannter Parameter-Key „{key}".')
        return redirect('creator_transferaufsicht')

    alt_row = (
        EconomyParameter.objects.filter(key=key)
        .order_by('-saison').first()
    )
    if alt_row is None:
        messages.error(
            request,
            f'Parameter „{key}" existiert nicht — neue Keys entstehen '
            'nur über Seed-Migrationen.',
        )
        return redirect('creator_transferaufsicht')

    try:
        neu = _json.loads(raw)
    except ValueError as exc:
        messages.error(request, f'Ungültiges JSON für {key}: {exc}')
        return redirect('creator_transferaufsicht')

    alt = get_param(key, saison)
    if _typ_kategorie(neu) != _typ_kategorie(alt):
        messages.error(
            request,
            f'Typwechsel abgelehnt: {key} ist bisher '
            f'{_typ_kategorie(alt)}, der neue Wert wäre '
            f'{_typ_kategorie(neu)} — das würde Transferlogik brechen.',
        )
        return redirect('creator_transferaufsicht')

    EconomyParameter.objects.update_or_create(
        saison=saison, key=key, defaults={'value': neu},
    )
    messages.success(request, f'{key} für Saison {saison} gespeichert.')
    log_creator_action(
        request.user, 'setting_save',
        f'EconomyParameter {key}',
        key=key, saison=saison, neuer_wert=neu,
    )
    return redirect('creator_transferaufsicht')
