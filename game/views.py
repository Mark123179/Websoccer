import json
import os
from collections import OrderedDict
from datetime import date, timedelta
from django.db import models as _db_models
from itertools import product

from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import redirect, render, get_object_or_404
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from .club_profile import build_club_profile_context
from .club_profile_highlights import nt_confederation_badge
from .competition_assets import (
    _NT_COMPETITION_KEYS,
    _NATIONALITY_CONFEDERATION,
    _CONFEDERATION_BADGE,
    nt_competition_logo,
    competition_logo_static_path,
)
from .context_processors import CURRENT_MANAGER_PROFILE_IMAGE
from .models import (
    Club,
    ClubNewsItem,
    ClubProfileMatch,
    ClubPublicProfile,
    ClubTrophy,
    COUNTRY_FLAG_ASSETS,
    DataSource,
    GameSeasonState,
    League,
    LeagueNews,
    LeagueStandings,
    ManagerProfile,
    MatchResult,
    Player,
    PlayerAwardTitle,
    PlayerFormSnapshot,
    PlayerInjuryRecord,
    PlayerSeasonStat,
    PlayerSourceRating,
    PlayerSuspensionRecord,
    PlayerTransferHistory,
    SeasonFixture,
    TacticSetup,
    TacticTemplate,
)
from .fixture_display import get_form_rows_with_opponents
from .tactics import (
    HALF_TACTIC_FIELDS,
    OPPONENT_RESULT_FORM,
    RESULT_FORM,
    STANDARD_FIELDS,
    TACTIC_OPTION_GROUPS,
    FORMATION_ORDER,
    FORMATION_PARTS,
    copy_payload_to_setup,
    default_half_tactic,
    default_standards,
    field_player_count,
    formation_choice_groups,
    formation_code,
    formation_part_summaries,
    formation_slots,
    normalize_formation,
    normalize_squad_scope,
    orientation_label,
    player_match_state,
    player_options_for_squad,
    sanitize_assignments,
    sanitize_payload,
    tactic_payload_from_setup,
    unavailable_players_for_squad,
    validate_formation,
    validate_substitutions,
)


import math as _math


# Thin-plate-spline calibration of europe-night.png (1536×1024). The background
# is a perspective ("tilted globe") satellite render, NOT a flat map projection,
# so a single linear/affine or even Mercator formula drifts badly. The TPS below
# was fitted against 14 geographic anchor points identified without brightness:
#   6 verified city starbursts (Frankfurt, Madrid, Barcelona, München, + the
#     two brightness-allowed anchors London, Paris),
#   5 coastal/geographic features (Cap de la Hague, Brittany/Corsen, Calabria
#     tip, Skagen tip, Mull of Kintyre),
#   2 urban-pattern coast anchors (Lisboa Tejo estuary, Porto coast),
#   1 archipelago anchor (Stockholm Baltic coast).
# All 14 anchors interpolate to 0.0 px residual. The transform is reproduced by
# game/calibration/calibrate_city_map.py — re-run that script to regenerate
# these weights after any anchor change.
# Coordinate convention: anchors stored as (lng, lat); _tps_eval signature is
#   _tps_eval(weights, lng, lat).
_MAP_TPS_ANCHORS = (
    ( 8.68, 50.11),   # Frankfurt        (city starburst)
    (-3.70, 40.42),   # Madrid           (city starburst)
    ( 2.17, 41.39),   # Barcelona        (city starburst)
    (11.58, 48.14),   # München          (city starburst)
    (-0.13, 51.51),   # London           (brightness allowed)
    ( 2.35, 48.85),   # Paris            (brightness allowed)
    (-1.93, 49.73),   # Cap de la Hague  (coastal peninsula)
    (-4.72, 48.41),   # Brittany/Corsen  (coastal point)
    (15.64, 37.65),   # Calabria tip     (boot-toe coast)
    (10.58, 57.73),   # Skagen           (Jutland tip)
    (-5.71, 55.30),   # Mull of Kintyre  (Scottish peninsula)
    (-9.14, 38.72),   # Lisboa           (Tejo estuary coast)
    (-8.61, 41.15),   # Porto            (coast, urban pattern)
    (18.07, 59.33),   # Stockholm        (Baltic archipelago)
)
# weights[0..n-1] = radial-basis weights; weights[n..n+2] = affine [constant, lng, lat]
_MAP_TPS_WX = (
    -0.111711,
    -0.452367,
     0.357419,
     0.292549,
    -1.636255,
    -0.307397,
     3.138902,
    -1.641837,
    -0.099319,
     0.113055,
     0.352754,
     0.883114,
    -0.766735,
    -0.122170,
    339.015967,
     17.232131,
      3.160251,
)
_MAP_TPS_WY = (
    -0.279317,
     0.516328,
    -0.536180,
     0.231476,
    -0.875358,
     0.606112,
     0.631787,
    -0.121384,
    -0.012970,
     0.242833,
     0.064864,
     0.455602,
    -0.779136,
    -0.144656,
    2032.907847,
       0.263777,
     -28.862434,
)
_MAP_IMG_W = 1536.0
_MAP_IMG_H = 1024.0


def _tps_eval(weights, lng, lat):
    n = len(_MAP_TPS_ANCHORS)
    val = weights[n] + weights[n + 1] * lng + weights[n + 2] * lat
    for i, (ax, ay) in enumerate(_MAP_TPS_ANCHORS):
        r = _math.hypot(lng - ax, lat - ay)
        if r > 0:
            val += weights[i] * r * r * _math.log(r)
    return val


def lat_lng_to_map_pct(lat, lng):
    """Map real lat/lng to x/y percent on the europe-night.png satellite image."""
    px = _tps_eval(_MAP_TPS_WX, lng, lat)
    py = _tps_eval(_MAP_TPS_WY, lng, lat)
    x_pct = px / _MAP_IMG_W * 100.0
    y_pct = py / _MAP_IMG_H * 100.0
    return round(max(0.0, min(100.0, x_pct)), 2), round(max(0.0, min(100.0, y_pct)), 2)


# Hand-verified marker positions on europe-night.png as (x%, y%). Each value was
# pixel-pinned against the satellite render via a calibration grid (1536x1024),
# so markers sit exactly on their city instead of drifting off the perspective
# formula. Table-first: any city listed here uses these fixed coordinates; the
# lat/lng TPS formula is only a fallback for cities not in the table. Keys are
# lowercase; lookup is accent/prefix tolerant via city_map_pct().
CITY_MAP_PCT = {
    # --- Germany — TPS-calibrated (14-anchor geographic homography) ---
    # Anchors: Frankfurt, Madrid, Barcelona, München, London, Paris,
    #   Cap de la Hague, Brittany/Corsen, Calabria tip, Skagen,
    #   Mull of Kintyre, Lisboa coast, Porto coast, Stockholm
    'augsburg': (46.22, 58.09),
    'berlin': (49.48, 46.91),
    'bochum': (41.42, 49.28),
    'bremen': (43.83, 45.24),
    'dortmund': (41.77, 49.22),
    'frankfurt am main': (43.29, 53.03), 'frankfurt': (43.29, 53.03),
    'freiburg im breisgau': (41.95, 58.67), 'freiburg': (41.95, 58.67),
    'hamburg': (45.47, 44.15),
    'heidenheim an der brenz': (45.24, 57.13), 'heidenheim': (45.24, 57.13),
    'kiel': (45.77, 42.14),
    'leipzig': (48.23, 50.16),
    'leverkusen': (41.02, 50.48),
    'mainz': (42.71, 53.29),
    'mönchengladbach': (40.28, 50.04), 'monchengladbach': (40.28, 50.04),
    'gladbach': (40.28, 50.04),
    'münchen': (47.07, 58.79), 'munchen': (47.07, 58.79), 'munich': (47.07, 58.79),
    'sinsheim': (43.51, 55.38),
    'stuttgart': (43.90, 56.70),
    'wolfsburg': (46.36, 47.19),
    # --- Spain / Portugal — TPS-calibrated ---
    'madrid': (22.14, 78.32),
    'barcelona': (32.88, 74.22),
    'valencia': (27.95, 80.26),
    'sevilla': (19.63, 86.56), 'seville': (19.63, 86.56),
    'bilbao': (24.12, 70.15),
    'san sebastián': (25.92, 70.07), 'san sebastian': (25.92, 70.07),
    'vigo': (15.02, 70.45),
    'zaragoza': (27.45, 74.43),
    'villarreal': (28.53, 78.84),
    'málaga': (21.71, 88.63), 'malaga': (21.71, 88.63),
    'lisboa': (15.89, 81.74), 'lissabon': (15.89, 81.74), 'lisbon': (15.89, 81.74),
    'porto': (15.30, 73.73),
    # --- France / Monaco — TPS-calibrated ---
    'paris': (34.51, 56.45),
    'marseille': (37.93, 69.93),
    'lyon': (37.55, 64.16),
    'lille': (35.57, 51.24),
    'bordeaux': (29.18, 66.18),
    'nice': (40.56, 69.27), 'nizza': (40.56, 69.27),
    'monaco': (40.76, 69.20),
    'nantes': (28.99, 59.92),
    'toulouse': (32.17, 69.06),
    'saint-étienne': (36.89, 64.89), 'saint-etienne': (36.89, 64.89),
    'rennes': (29.52, 57.49),
    'strasbourg': (41.87, 57.10),
    'lens': (35.26, 51.79),
    'le havre': (32.30, 53.90),
    'montpellier': (35.91, 69.03),
    'reims': (36.71, 55.34),
    'clermont-ferrand': (35.10, 64.08),
    # --- England / Scotland / Ireland — TPS-calibrated ---
    'london': (31.97, 47.36),
    'manchester': (30.41, 41.43),
    'liverpool': (29.54, 41.55),
    'birmingham': (30.54, 44.31),
    'newcastle': (31.60, 37.35),
    'leeds': (31.22, 40.61),
    'glasgow': (29.09, 34.55),
    'edinburgh': (30.32, 34.46),
    'dublin': (24.97, 41.09),
    'southampton': (31.02, 49.21),
    'sheffield': (31.16, 41.79),
    'ipswich': (33.43, 46.19),
    'blackburn': (30.23, 40.64),
    'sunderland': (31.80, 37.58),
    'middlesbrough': (31.81, 38.50),
    'cardiff': (28.70, 47.17),
    'reading': (31.31, 47.45),
    'brighton': (32.04, 49.55),
    'norwich': (33.75, 44.58),
    'coventry': (30.90, 44.57),
    'hull': (32.38, 40.96),
    'brentford': (31.83, 47.40),
    'luton': (31.77, 46.20),
    'portsmouth': (31.30, 49.54),
    'nottingham': (31.35, 43.04),
    'leicester': (31.29, 43.92),
    'stoke-on-trent': (30.34, 42.81),
    'wolverhampton': (30.30, 44.00),
    'watford': (31.75, 46.86),
    'swansea': (27.49, 46.58),
    'plymouth': (26.35, 50.15),
    'burnley': (30.51, 40.56),
    'burton upon trent': (30.85, 43.42),
    'rotherham': (31.29, 41.66),
    'wigan': (30.01, 41.19),
    'barnsley': (31.20, 41.31),
    'oxford': (31.07, 46.55),
    # --- Netherlands / Belgium — TPS-calibrated ---
    'amsterdam': (38.36, 46.54),
    'rotterdam': (37.69, 47.73),
    'eindhoven': (38.98, 49.24),
    'brussel': (37.33, 50.80), 'brüssel': (37.33, 50.80), 'brussels': (37.33, 50.80),
    'antwerpen': (37.45, 49.73), 'antwerp': (37.45, 49.73),
    'brügge': (35.86, 49.52), 'bruges': (35.86, 49.52),
    'utrecht': (38.60, 47.37),
    'alkmaar': (38.21, 45.77),
    'arnhem': (39.67, 47.80),
    'heerenveen': (39.90, 45.10),
    'groningen': (40.83, 44.52),
    'tilburg': (38.46, 48.86),
    'sittard': (39.46, 50.50),
    'breda': (38.04, 48.73),
    'almere': (38.80, 46.60),
    'deventer': (40.07, 47.06),
    'emmen': (41.20, 45.73),
    'dordrecht': (37.93, 48.08),
    'sparta rotterdam': (37.69, 47.73),
    'excelsior': (37.69, 47.73),
    'charleroi': (37.39, 52.08),
    'gent': (36.50, 50.11),
    'liège': (38.99, 51.52), 'liege': (38.99, 51.52),
    'st-truiden': (38.48, 50.96),
    'kortrijk': (35.87, 50.68),
    'mechelen': (37.53, 50.29),
    'beerschot': (37.45, 49.73),
    'cercle brugge': (35.86, 49.52),
    'oud-heverlee leuven': (37.78, 50.75),
    'sint-gillis-waas': (37.07, 49.66),
    'westerlo': (38.15, 50.14),
    'rwdm': (37.33, 50.71),
    # --- Switzerland — TPS-calibrated ---
    'zürich': (42.87, 60.35), 'zurich': (42.87, 60.35),
    'basel': (41.56, 59.77),
    'bern': (41.30, 61.33),
    'genf': (39.40, 63.14), 'genève': (39.40, 63.14), 'geneva': (39.40, 63.14),
    'lausanne': (40.11, 62.37),
    'lugano': (43.23, 63.89),
    'luzern': (42.50, 61.15),
    'st. gallen': (44.03, 60.33),
    'winterthur': (43.14, 60.03),
    'sion': (41.09, 63.14),
    'aarau': (42.17, 60.25),
    'thun': (41.53, 61.83),
    # --- Scandinavia — TPS-calibrated ---
    'kopenhagen': (48.81, 38.40), 'copenhagen': (48.81, 38.40), 'københavn': (48.81, 38.40),
    'oslo': (47.38, 26.66),
    'stockholm': (54.69, 26.37),
    'göteborg': (48.41, 32.89), 'goteborg': (48.41, 32.89), 'gothenburg': (48.41, 32.89),
    'malmö': (49.27, 38.52), 'malmo': (49.27, 38.52),
    'helsingborg': (48.98, 37.37),
    'norrköping': (52.76, 29.11),
    'djurgarden': (54.72, 26.33),
    'hammarby': (54.68, 26.45),
    'aik': (54.57, 26.26),
    'gais': (54.61, 26.53),
    'häcken': (48.41, 32.84),
    'trondheim': (47.56, 16.24),
    'bergen': (41.28, 24.50),
    'brann': (41.28, 24.50),
    'fredrikstad': (47.48, 28.68),
    'rosenborg': (47.56, 16.24),
    'aalesund': (42.75, 18.73),
    'molde': (43.93, 18.11),
    'sarpsborg': (47.68, 28.49),
    'odense': (46.25, 39.30),
    'randers': (46.02, 36.43),
    'aarhus': (46.15, 37.27),
    'silkeborg': (45.36, 37.19),
    'fc midtjylland': (44.67, 37.22),
    'esbjerg': (43.85, 38.89),
    'horsens': (45.67, 38.05),
    'brøndby': (48.66, 38.40),
    'nordsjaelland': (48.68, 37.74),
    'lyngby': (48.74, 38.17),
    'vejle': (45.26, 38.42),
    'viborg': (45.25, 36.42),
    'kolding': (45.13, 38.99),
    'hvidovre': (48.68, 38.53),
    # --- Italy — HAND-PINNED (TPS formula drifts ~4-5% for cities far east
    # of the anchor hull; Calabria-tip anchor at 15.64°E keeps the peninsula
    # well-interpolated. All values verified 2026-06 via direct RGB brightness
    # analysis of the satellite image: each pin is placed on the warm urban
    # light cluster (rgb > 180 warmth > 20) visible in the night satellite.
    # Roma: px(720,760) rgb(214,198,176) warmth=35 — Roman metro light cluster.
    # Napoli: px(726,795) rgb(185,169,147) warmth=30 — Naples metro light cluster.
    'roma': (46.88, 74.22), 'rom': (46.88, 74.22), 'rome': (46.88, 74.22),
    'napoli': (47.27, 77.64), 'neapel': (47.27, 77.64), 'naples': (47.27, 77.64),
    'milano': (43.5, 65.3), 'mailand': (43.5, 65.3), 'milan': (43.5, 65.3),
    'torino': (41.4, 66.0), 'turin': (41.4, 66.0),
    'genova': (42.9, 67.8), 'genua': (42.9, 67.8), 'genoa': (42.9, 67.8),
    'venezia': (47.3, 65.7), 'venedig': (47.3, 65.7), 'venice': (47.3, 65.7),
    'firenze': (45.6, 69.7), 'florenz': (45.6, 69.7), 'florence': (45.6, 69.7),
    'bologna': (45.9, 68.0),
    'parma': (44.8, 67.1),
    'lazio': (46.88, 74.22),
    'fiorentina': (45.6, 69.7),
    'atalanta': (44.1, 64.7),
    'cagliari': (41.6, 80.8),
    'como': (43.4, 64.4),
    'empoli': (45.2, 69.8),
    'frosinone': (47.2, 75.2),
    'hellas verona': (45.8, 65.6),
    'inter': (43.5, 65.3),
    'juventus': (41.4, 66.0),
    'lecce': (50.5, 79.8),
    'monza': (43.6, 65.0),
    'salernitana': (48.4, 77.7),
    'sassuolo': (45.3, 67.7),
    'udinese': (48.5, 64.1),
    # Southern Italy / Sicily — TPS places these in the sea; hand-pinned 2026-06:
    # Bari: Adriatic coast, same latitude as Napoli (EUROPEAN cross-ref).
    # Palermo/Catania: TPS y≈84-86 lands ~4-5% north of Sicily; scan shows Sicily
    # starting at y≈88.5. Reggio Calabria: near Calabria-tip TPS anchor (correct
    # x/y for land), dark on image but confirmed on mainland.
    'bari': (49.5, 77.3),
    'palermo': (46.5, 90.0),
    'catania': (47.6, 89.5),
    'reggio calabria': (48.4, 84.4),
    # --- Balkans — HAND-PINNED (TPS formula drifts into the Adriatic) ---
    'zagreb': (49.00, 65.50),
    'belgrad': (52.50, 69.00), 'belgrade': (52.50, 69.00), 'beograd': (52.50, 69.00),
    'dinamo zagreb': (49.00, 65.50),
    'hajduk split': (49.80, 68.20),
    'rijeka': (48.30, 66.80),
    'osijek': (51.20, 63.80),
    'varazdin': (49.20, 63.50),
    'šibenik': (49.60, 68.80),
    'gorica': (48.10, 66.60),
}


# Country-level bounding boxes for single-station minimum zoom.
# Format: [min_x%, max_x%, min_y%, max_y%] on europe-night.png (1536×1024).
# Used when a manager has only one training station — zooms out to show the
# whole country instead of just the city area (which gives zero geographic
# context). Values are tuned against CITY_MAP_PCT anchor positions.
COUNTRY_MAP_BBOX = {
    # --- Germany ---
    'deutschland': [37.0, 52.5, 40.0, 61.5],
    'germany':     [37.0, 52.5, 40.0, 61.5],
    # --- Spain / Portugal ---
    'spanien':     [12.0, 34.5, 67.5, 91.5],
    'spain':       [12.0, 34.5, 67.5, 91.5],
    'portugal':    [13.5, 22.5, 69.0, 87.0],
    # --- France / Monaco ---
    'frankreich':  [24.5, 43.5, 48.5, 72.5],
    'france':      [24.5, 43.5, 48.5, 72.5],
    # --- England / UK ---
    'england':     [22.5, 35.5, 30.5, 52.0],
    'uk':          [20.5, 36.5, 29.0, 52.5],
    'schottland':  [25.0, 34.0, 29.0, 39.0],
    'scotland':    [25.0, 34.0, 29.0, 39.0],
    'wales':       [25.0, 32.5, 39.0, 48.0],
    'irland':      [20.5, 29.5, 36.5, 46.0],
    'ireland':     [20.5, 29.5, 36.5, 46.0],
    # --- Italy ---
    'italien':     [38.0, 54.0, 60.5, 94.0],
    'italy':       [38.0, 54.0, 60.5, 94.0],
    # --- Netherlands / Belgium ---
    'niederlande': [36.0, 42.5, 42.5, 51.5],
    'netherlands': [36.0, 42.5, 42.5, 51.5],
    'belgien':     [33.5, 40.5, 48.5, 53.5],
    'belgium':     [33.5, 40.5, 48.5, 53.5],
    # --- Switzerland / Austria ---
    'schweiz':     [38.0, 45.0, 58.0, 65.5],
    'switzerland': [38.0, 45.0, 58.0, 65.5],
    'österreich':  [43.5, 57.5, 54.0, 64.5],
    'austria':     [43.5, 57.5, 54.0, 64.5],
    # --- Scandinavia ---
    'dänemark':    [42.0, 52.0, 36.0, 41.5],
    'denmark':     [42.0, 52.0, 36.0, 41.5],
    'schweden':    [46.5, 58.0, 22.5, 39.0],
    'sweden':      [46.5, 58.0, 22.5, 39.0],
    'norwegen':    [37.5, 52.0, 13.0, 31.0],
    'norway':      [37.5, 52.0, 13.0, 31.0],
    'finnland':    [50.0, 65.0, 17.0, 33.0],
    'finland':     [50.0, 65.0, 17.0, 33.0],
    # --- Eastern Europe / Balkans ---
    'kroatien':    [45.5, 53.5, 61.5, 71.5],
    'croatia':     [45.5, 53.5, 61.5, 71.5],
    'serbien':     [48.5, 56.5, 64.5, 74.5],
    'serbia':      [48.5, 56.5, 64.5, 74.5],
    'griechenland':[47.5, 58.5, 76.5, 95.0],
    'greece':      [47.5, 58.5, 76.5, 95.0],
    'türkei':      [55.0, 75.0, 72.0, 88.5],
    'turkey':      [55.0, 75.0, 72.0, 88.5],
}


def country_map_bbox(country_name):
    """Return [min_x%, max_x%, min_y%, max_y%] for the country, or None.

    Tolerant lookup: exact lowercase match first, then substring match so
    'Great Britain' → 'uk' and regional labels like 'Deutschland/Bayern' still hit.
    """
    key = (country_name or '').strip().lower()
    if not key:
        return None
    hit = COUNTRY_MAP_BBOX.get(key)
    if hit:
        return hit
    for ck, cv in COUNTRY_MAP_BBOX.items():
        if ck in key or key in ck:
            return cv
    return None


def city_map_pct(*names):
    """Return the hand-verified (x%, y%) for a city name, or None.

    Tolerant lookup: exact match first, then a two-way prefix match so
    'Frankfurt' resolves to 'frankfurt am main' and minor typos still hit.
    The first name that resolves wins.
    """
    for raw in names:
        key = (raw or '').strip().lower()
        if not key:
            continue
        hit = CITY_MAP_PCT.get(key)
        if hit:
            return hit
        if len(key) >= 4:
            for ck, cv in CITY_MAP_PCT.items():
                # ck.startswith(key): tolerate truncations/typos ("frankfur").
                # key.startswith(ck + ' '): only match a table key that is a
                # leading *word* of the input ("frankfurt am main" -> "frankfurt")
                # so a short key never grabs an unrelated longer name
                # ("kielce" must not resolve to "kiel").
                if ck.startswith(key) or key.startswith(ck + ' '):
                    return cv
    return None


EUROPEAN_CITY_COORDS = {
    # Germany
    'münchen': (271, 214), 'munich': (271, 214),
    'berlin': (285, 155),
    'hamburg': (254, 133),
    'frankfurt': (252, 182),
    'köln': (238, 168), 'cologne': (238, 168),
    'dortmund': (240, 160),
    'düsseldorf': (235, 163),
    'stuttgart': (258, 200),
    'leipzig': (280, 162),
    'hannover': (254, 150),
    'bremen': (247, 140),
    'dresden': (292, 168),
    'nürnberg': (268, 195), 'nuremberg': (268, 195),
    'bochum': (239, 162),
    'wuppertal': (237, 165),
    'bielefeld': (247, 155),
    'bonn': (234, 172),
    'mannheim': (252, 195),
    'karlsruhe': (250, 200),
    'augsburg': (264, 210),
    'mönchengladbach': (232, 165),
    'gelsenkirchen': (238, 160),
    'freiburg': (248, 210),
    'kiel': (257, 120),
    'magdeburg': (278, 148),
    'erfurt': (272, 168),
    'mainz': (248, 185),
    'kaiserslautern': (244, 192),
    'saarbrücken': (240, 196),
    # Austria
    'wien': (308, 200), 'vienna': (308, 200),
    'salzburg': (284, 209),
    'graz': (305, 214),
    'innsbruck': (272, 217),
    'linz': (294, 203),
    'klagenfurt': (296, 220),
    # Switzerland
    'zürich': (255, 210), 'zurich': (255, 210),
    'basel': (247, 207),
    'bern': (250, 215),
    'genf': (240, 222), 'geneva': (240, 222),
    'lausanne': (244, 220),
    'luzern': (252, 213),
    # France
    'paris': (218, 190),
    'lyon': (232, 220),
    'marseille': (236, 240),
    'bordeaux': (206, 228),
    'lille': (220, 170),
    'nantes': (198, 212),
    'strasbourg': (248, 196),
    'nice': (247, 240),
    'toulouse': (215, 238),
    'rennes': (200, 198),
    'montpellier': (232, 242),
    'saint-étienne': (232, 224),
    'lens': (218, 168),
    'metz': (237, 185),
    'nancy': (237, 187),
    'grenoble': (240, 228),
    # Spain
    'madrid': (165, 258),
    'barcelona': (205, 248),
    'sevilla': (143, 272), 'seville': (143, 272),
    'valencia': (190, 258),
    'bilbao': (174, 238),
    'zaragoza': (184, 250),
    'málaga': (158, 280), 'malaga': (158, 280),
    'alicante': (190, 265),
    'córdoba': (158, 268), 'cordoba': (158, 268),
    'granada': (162, 272),
    'murcia': (186, 268),
    'valladolid': (158, 245),
    'athletic bilbao': (174, 238),
    'san sebastián': (176, 234), 'san sebastian': (176, 234),
    'pamplona': (180, 242),
    'vigo': (140, 244),
    'las palmas': (100, 298),
    # Portugal
    'lisboa': (132, 268), 'lisbon': (132, 268),
    'porto': (140, 252),
    'braga': (140, 248),
    'guimarães': (141, 250),
    'setúbal': (130, 272),
    # Italy
    'roma': (285, 248), 'rome': (285, 248),
    'milano': (263, 220), 'milan': (263, 220),
    'napoli': (296, 258), 'naples': (296, 258),
    'torino': (252, 224), 'turin': (252, 224),
    'venezia': (280, 223), 'venice': (280, 223),
    'firenze': (275, 238), 'florence': (275, 238),
    'bologna': (272, 230),
    'palermo': (286, 303),
    'genova': (257, 230), 'genoa': (257, 230),
    'bari': (308, 258),
    'catania': (294, 302),
    'verona': (272, 222),
    'bergamo': (264, 220),
    'brescia': (268, 222),
    'lecce': (316, 264),
    'parma': (268, 228),
    'reggio calabria': (300, 283),
    # England
    'london': (195, 164),
    'manchester': (185, 145),
    'liverpool': (181, 148),
    'birmingham': (190, 155),
    'leeds': (190, 141),
    'newcastle': (186, 130),
    'bristol': (184, 163),
    'sheffield': (190, 145),
    'leicester': (193, 153),
    'southampton': (192, 167),
    'portsmouth': (192, 168),
    'nottingham': (193, 150),
    'wolverhampton': (187, 155),
    'sunderland': (188, 133),
    'brighton': (196, 168),
    'coventry': (191, 155),
    'middlesbrough': (190, 135),
    'stoke': (188, 151),
    'derby': (192, 150),
    # Scotland
    'glasgow': (172, 118),
    'edinburgh': (180, 122),
    'aberdeen': (178, 108),
    'dundee': (178, 114),
    # Wales
    'cardiff': (181, 160),
    # Ireland
    'dublin': (163, 148),
    'cork': (156, 160),
    # Netherlands
    'amsterdam': (228, 150),
    'rotterdam': (224, 158),
    'eindhoven': (229, 162),
    'utrecht': (226, 154),
    'den haag': (222, 156), 'the hague': (222, 156),
    'tilburg': (226, 162),
    'groningen': (236, 138),
    'alkmaar': (225, 146),
    'breda': (224, 163),
    'nijmegen': (230, 160),
    'heerenveen': (232, 138),
    'arnhem': (230, 158),
    'enschede': (236, 158),
    'sittard': (228, 168),
    'venlo': (230, 164),
    # Belgium
    'brüssel': (220, 163), 'brussels': (220, 163),
    'antwerpen': (218, 158), 'antwerp': (218, 158),
    'brügge': (215, 162), 'bruges': (215, 162),
    'gent': (218, 162), 'ghent': (218, 162),
    'liège': (223, 165), 'liege': (223, 165),
    'anderlecht': (220, 163),
    'mechelen': (218, 160),
    'sint-truiden': (222, 166),
    'charleroi': (220, 168),
    # Czech Republic
    'prag': (292, 172), 'prague': (292, 172),
    'brno': (304, 185),
    'ostrava': (310, 172),
    'plzen': (285, 177), 'pilsen': (285, 177),
    # Poland
    'warszawa': (326, 152), 'warsaw': (326, 152),
    'krakau': (318, 172), 'krakow': (318, 172), 'kraków': (318, 172),
    'gdansk': (305, 132), 'danzig': (305, 132),
    'wroclaw': (305, 162), 'breslau': (305, 162), 'wrocław': (305, 162),
    'lodz': (316, 155), 'łódź': (316, 155),
    'poznan': (300, 148), 'poznań': (300, 148),
    'szczecin': (292, 136),
    'bydgoszcz': (305, 144),
    'lublin': (332, 158),
    'katowice': (312, 170),
    'rzeszów': (325, 172),
    'białystok': (336, 144),
    # Hungary
    'budapest': (316, 202),
    'debrecen': (335, 198),
    'miskolc': (325, 190),
    'győr': (308, 196),
    # Romania
    'bukarest': (355, 212), 'bucharest': (355, 212), 'bucurești': (355, 212),
    'cluj': (338, 192), 'cluj-napoca': (338, 192),
    'timisoara': (330, 206), 'timișoara': (330, 206),
    'iași': (360, 190), 'iasi': (360, 190),
    'constanta': (372, 220), 'constanța': (372, 220),
    'brasov': (348, 202), 'brașov': (348, 202),
    # Serbia
    'belgrad': (325, 222), 'belgrade': (325, 222), 'beograd': (325, 222),
    'novi sad': (318, 215),
    # Croatia
    'zagreb': (306, 222),
    'split': (302, 240),
    'rijeka': (296, 228),
    'osijek': (318, 218),
    # Greece
    'athen': (342, 272), 'athens': (342, 272), 'athina': (342, 272),
    'thessaloniki': (334, 252),
    'patras': (328, 272),
    'heraklion': (344, 295),
    # Turkey
    'istanbul': (375, 242),
    'ankara': (400, 252),
    'izmir': (375, 262),
    'bursa': (380, 248),
    'adana': (405, 265),
    'trabzon': (420, 250),
    # Denmark
    'kopenhagen': (272, 120), 'copenhagen': (272, 120), 'københavn': (272, 120),
    'aarhus': (262, 108),
    'odense': (258, 118),
    'aalborg': (257, 106),
    # Sweden
    'stockholm': (308, 100),
    'göteborg': (268, 110), 'gothenburg': (268, 110),
    'malmö': (272, 122),
    'uppsala': (308, 96),
    'norrköping': (295, 104),
    'örebro': (286, 102),
    'helsingborg': (268, 118),
    # Norway
    'oslo': (266, 90),
    'bergen': (246, 92),
    'trondheim': (260, 75),
    'stavanger': (240, 98),
    # Finland
    'helsinki': (330, 90),
    'tampere': (326, 80),
    'turku': (318, 90),
    'oulu': (326, 70),
    # Iceland
    'reykjavik': (110, 76),
    # Russia
    'moskau': (410, 125), 'moscow': (410, 125), 'moskva': (410, 125),
    'st. petersburg': (380, 100), 'saint petersburg': (380, 100),
    'kasan': (460, 120), 'kazan': (460, 120),
    # Ukraine
    'kiew': (368, 170), 'kyiv': (368, 170), 'kiev': (368, 170),
    'charkiw': (388, 162), 'kharkiv': (388, 162),
    'dnipro': (385, 182),
    'odessa': (375, 196),
    'lemberg': (345, 175), 'lviv': (345, 175),
    'donezk': (398, 178), 'donetsk': (398, 178),
    'saporischschja': (390, 186), 'zaporizhzhia': (390, 186),
    # Slovakia
    'bratislava': (306, 192),
    'košice': (325, 183), 'kosice': (325, 183),
    # Slovenia
    'ljubljana': (298, 224),
    # Bosnia
    'sarajevo': (314, 234),
    # Montenegro
    'podgorica': (318, 242),
    # Albania
    'tirana': (321, 248),
    # North Macedonia
    'skopje': (330, 242),
    # Bulgaria
    'sofia': (335, 232),
    'plovdiv': (346, 238),
    'varna': (366, 228),
    # Latvia
    'riga': (338, 118),
    # Lithuania
    'vilnius': (342, 132),
    'kaunas': (334, 130),
    # Estonia
    'tallinn': (334, 108),
    # Belarus
    'minsk': (352, 142),
    # Moldova
    'chisinau': (360, 195), 'chișinău': (360, 195),
    # Luxembourg
    'luxemburg': (230, 175), 'luxembourg': (230, 175),
    # Cyprus
    'nikosia': (406, 282), 'nicosia': (406, 282),
}


def map_xy_to_lat_lng(mx, my):
    """Convert the legacy small-map pixel coords (map_x/map_y) to real lat/lng.

    Calibrated (affine, least-squares) against EUROPEAN_CITY_COORDS using cities
    whose real lat/lng are known. Lets custom stations (no linked club) be placed
    on the lat/lng-calibrated satellite map.
    """
    lng = 0.137677 * mx - 0.006277 * my - 24.96416
    merc = 0.000254 * mx - 0.002833 * my + 1.45515
    lat = _math.degrees(2 * _math.atan(_math.exp(merc)) - _math.pi / 2)
    return lat, lng


# Real geographic coordinates (lat, lng) for major European cities. Used to place
# custom career stations (no linked club) on the satellite map. Real coords are
# fed straight into the TPS calibration, avoiding the lossy legacy map_x/map_y
# conversion. Keys are lowercase; add German/English aliases as needed.
REAL_CITY_LATLNG = {
    'münchen': (48.14, 11.58), 'munchen': (48.14, 11.58), 'munich': (48.14, 11.58),
    'augsburg': (48.37, 10.90), 'frankfurt': (50.11, 8.68), 'berlin': (52.52, 13.40),
    'hamburg': (53.55, 9.99), 'köln': (50.94, 6.96), 'koln': (50.94, 6.96),
    'cologne': (50.94, 6.96), 'düsseldorf': (51.23, 6.78), 'dusseldorf': (51.23, 6.78),
    'dortmund': (51.51, 7.47), 'stuttgart': (48.78, 9.18), 'leipzig': (51.34, 12.37),
    'bremen': (53.08, 8.80), 'hannover': (52.37, 9.74), 'hanover': (52.37, 9.74),
    'nürnberg': (49.45, 11.08), 'nurnberg': (49.45, 11.08), 'nuremberg': (49.45, 11.08),
    'mönchengladbach': (51.18, 6.44), 'monchengladbach': (51.18, 6.44),
    'wolfsburg': (52.42, 10.79), 'freiburg': (47.99, 7.84), 'mainz': (50.00, 8.27),
    'gelsenkirchen': (51.52, 7.10), 'bochum': (51.48, 7.22), 'kiel': (54.32, 10.14),
    'london': (51.51, -0.13), 'manchester': (53.48, -2.24), 'liverpool': (53.41, -2.99),
    'birmingham': (52.49, -1.89), 'leeds': (53.80, -1.55), 'newcastle': (54.98, -1.61),
    'glasgow': (55.86, -4.25), 'edinburgh': (55.95, -3.19), 'dublin': (53.35, -6.26),
    'paris': (48.85, 2.35), 'marseille': (43.30, 5.37), 'lyon': (45.76, 4.84),
    'lille': (50.63, 3.06), 'bordeaux': (44.84, -0.58), 'nantes': (47.22, -1.55),
    'nice': (43.70, 7.27), 'monaco': (43.74, 7.42), 'toulouse': (43.60, 1.44),
    'saint-étienne': (45.44, 4.39), 'saint-etienne': (45.44, 4.39),
    'madrid': (40.42, -3.70), 'barcelona': (41.39, 2.17), 'valencia': (39.47, -0.38),
    'sevilla': (37.39, -5.99), 'seville': (37.39, -5.99), 'bilbao': (43.26, -2.92),
    'málaga': (36.72, -4.42), 'malaga': (36.72, -4.42), 'zaragoza': (41.65, -0.89),
    'villarreal': (39.94, -0.10), 'san sebastián': (43.32, -1.98),
    'san sebastian': (43.32, -1.98), 'vigo': (42.24, -8.72),
    'lisboa': (38.72, -9.14), 'lissabon': (38.72, -9.14), 'lisbon': (38.72, -9.14),
    'porto': (41.15, -8.61),
    'roma': (41.90, 12.50), 'rom': (41.90, 12.50), 'rome': (41.90, 12.50),
    'milano': (45.46, 9.19), 'mailand': (45.46, 9.19), 'milan': (45.46, 9.19),
    'torino': (45.07, 7.69), 'turin': (45.07, 7.69), 'napoli': (40.85, 14.27),
    'neapel': (40.85, 14.27), 'naples': (40.85, 14.27), 'firenze': (43.77, 11.26),
    'florenz': (43.77, 11.26), 'florence': (43.77, 11.26), 'genova': (44.41, 8.93),
    'genua': (44.41, 8.93), 'genoa': (44.41, 8.93), 'bologna': (44.49, 11.34),
    'venezia': (45.44, 12.33), 'venedig': (45.44, 12.33), 'venice': (45.44, 12.33),
    'amsterdam': (52.37, 4.90), 'rotterdam': (51.92, 4.48), 'eindhoven': (51.44, 5.48),
    'brussel': (50.85, 4.35), 'brüssel': (50.85, 4.35), 'brussels': (50.85, 4.35),
    'antwerpen': (51.22, 4.40), 'antwerp': (51.22, 4.40), 'brügge': (51.21, 3.22),
    'bruges': (51.21, 3.22),
    'wien': (48.21, 16.37), 'vienna': (48.21, 16.37), 'salzburg': (47.81, 13.06),
    'zürich': (47.37, 8.54), 'zurich': (47.37, 8.54), 'basel': (47.56, 7.59),
    'bern': (46.95, 7.45), 'genf': (46.20, 6.14), 'geneva': (46.20, 6.14),
    'warschau': (52.23, 21.01), 'warsaw': (52.23, 21.01), 'warszawa': (52.23, 21.01),
    'krakau': (50.06, 19.94), 'krakow': (50.06, 19.94), 'prag': (50.08, 14.44),
    'prague': (50.08, 14.44), 'praha': (50.08, 14.44), 'budapest': (47.50, 19.04),
    'kopenhagen': (55.68, 12.57), 'copenhagen': (55.68, 12.57), 'oslo': (59.91, 10.75),
    'stockholm': (59.33, 18.07), 'göteborg': (57.71, 11.97), 'goteborg': (57.71, 11.97),
    'helsinki': (60.17, 24.94), 'athen': (37.98, 23.73), 'athens': (37.98, 23.73),
    'athina': (37.98, 23.73), 'istanbul': (41.01, 28.98), 'zagreb': (45.81, 15.98),
    'belgrad': (44.79, 20.45), 'belgrade': (44.79, 20.45), 'bukarest': (44.43, 26.10),
    'bucharest': (44.43, 26.10), 'kyiv': (50.45, 30.52), 'kiew': (50.45, 30.52),
    'kiev': (50.45, 30.52), 'moskau': (55.76, 37.62), 'moscow': (55.76, 37.62),
}


def resolve_city_latlng(*names):
    """Resolve a city name to real lat/lng for placement on the satellite map.

    Prefers the accurate REAL_CITY_LATLNG table (exact then prefix match, so typos
    like "Barcelon" still resolve to "barcelona"). Falls back to converting the
    legacy EUROPEAN_CITY_COORDS pixel coords when a name is only known there.
    Returns None if nothing fits.
    """
    for raw in names:
        key = (raw or '').strip().lower()
        if not key:
            continue
        real = REAL_CITY_LATLNG.get(key)
        if not real and len(key) >= 3:
            for ck, cv in REAL_CITY_LATLNG.items():
                if ck.startswith(key) or key.startswith(ck):
                    real = cv
                    break
        if real:
            return real
        coords = EUROPEAN_CITY_COORDS.get(key)
        if not coords and len(key) >= 3:
            for ck, cv in EUROPEAN_CITY_COORDS.items():
                if ck.startswith(key) or key.startswith(ck):
                    coords = cv
                    break
        if coords:
            return map_xy_to_lat_lng(coords[0], coords[1])
    return None


def decimal_number(value):
    if value is None:
        return None

    return float(value)


def date_label(value):
    return value.isoformat() if value else ''


def latest_in_chronological_order(queryset):
    return list(queryset.order_by('-recorded_at', '-id')[:10])[::-1]


def latest_form_snapshots_in_chronological_order(queryset):
    return list(queryset.order_by('-fixture_date', '-id')[:10])[::-1]


def award_trophy_shape(award):
    title = award.title.lower()
    image_path = award.trophy_static_path.lower()

    if any(token in title or token in image_path for token in ['meisterschaft', 'schale']):
        return 'wide'

    if any(token in title or token in image_path for token in ['torjäger', 'torjager', 'kanone']):
        return 'small'

    if any(token in title or token in image_path for token in ['spieler der saison', 'player-of-the-season']):
        return 'season-award'

    if any(token in title or token in image_path for token in ['champions league']):
        return 'tall'

    return 'default'


def award_display_title(award):
    title = award.title.strip()
    normalized = title.lower()

    if normalized == 'meisterschaft':
        return '1. Bundesliga Meisterschaft'

    if normalized == 'ligapokal':
        return 'DFL-Ligapokal'

    return title


def static_asset_version(path):
    found_path = finders.find(path)
    if not found_path:
        return ''

    return str(int(os.path.getmtime(found_path)))


def award_podium_slots(awards):
    slots = []
    for index in range(4):
        if index < len(awards):
            award = awards[index]
            slots.append(
                {
                    'award': award,
                    'image_path': award.trophy_static_path,
                    'title': award_display_title(award),
                    'count': award.count,
                    'shape': award_trophy_shape(award),
                    'asset_version': static_asset_version(award.trophy_static_path),
                    'is_placeholder': False,
                }
            )
            continue

        slots.append(
            {
                'award': None,
                'image_path': None,
                'title': 'Freier Titelplatz',
                'count': None,
                'shape': 'empty',
                'is_placeholder': True,
            }
        )

    return slots


def compact_money(value):
    if value is None:
        return '-'

    value = float(value)
    if value >= 1000000:
        millions = value / 1000000
        if millions.is_integer():
            return f'{millions:.0f} Mio. €'
        return f'{millions:.1f}'.replace('.', ',') + ' Mio. €'

    if value >= 1000:
        return f'{value / 1000:.0f} Tsd. €'

    return f'{value:.0f} €'


def compact_money_axis(value):
    if value is None:
        return '-'

    value = float(value)
    if value >= 1000000:
        return f'{value / 1000000:.0f}M'

    if value >= 1000:
        return f'{value / 1000:.0f}K'

    return f'{value:.0f}'


def market_chart_points(rows, current_value):
    entries = [
        {
            'value': float(row.value_eur),
            'date': row.recorded_at,
        }
        for row in rows
        if row.value_eur is not None
    ]
    if not entries and current_value:
        entries = [{
            'value': float(current_value),
            'date': None,
        }]

    if not entries:
        return []

    values = [entry['value'] for entry in entries]
    min_value = min(values)
    max_value = max(values)
    span = max(max_value - min_value, 1)
    points = []

    for index, entry in enumerate(entries):
        value = entry['value']
        x = 6 + (index / max(len(entries) - 1, 1)) * 88
        y = 82 - ((value - min_value) / span) * 66
        date = entry['date']
        points.append({
            'x': f'{x:.2f}',
            'y': f'{y:.2f}',
            'numeric_value': value,
            'value': compact_money(value),
            'axis_value': compact_money_axis(value),
            'date_label': date.strftime('%m/%y') if date else 'aktuell',
            'full_date_label': date.strftime('%d.%m.%Y') if date else 'aktuell',
        })

    return points


def compute_market_value_trend(rows):
    valid = [row for row in rows if row.value_eur is not None]
    if len(valid) < 2:
        return None
    prev_value = float(valid[-2].value_eur)
    curr_value = float(valid[-1].value_eur)
    delta = curr_value - prev_value
    if delta > 0:
        direction = 'up'
        sign = '+'
    elif delta < 0:
        direction = 'down'
        sign = ''
    else:
        direction = 'flat'
        sign = ''
    return {
        'direction': direction,
        'delta': sign + compact_money(abs(delta)),
    }


def market_chart_axis(points):
    raw_values = [point['numeric_value'] for point in points]

    if not raw_values:
        return {
            'max': '-',
            'mid': '-',
            'min': '-',
        }

    min_value = min(raw_values)
    max_value = max(raw_values)
    return {
        'max': compact_money_axis(max_value),
        'mid': compact_money_axis((max_value + min_value) / 2),
        'min': compact_money_axis(min_value),
    }


def market_polyline(points):
    return ' '.join(f"{point['x']},{point['y']}" for point in points)


def market_area_points(points):
    if not points:
        return ''

    return f"8,92 {market_polyline(points)} 92,92"


def stadium_static_path(club):
    if not club or not club.fm_inside_id:
        return ''

    stadium_assets = {
        901:      'game/images/stadiums/germany/b-leverkusen.jpg',
        905:      'game/images/stadiums/germany/bochum.jpg',
        907:      'game/images/stadiums/germany/b-dortmund.jpg',
        908:      'game/images/stadiums/germany/b-gladbach.jpg',
        912:      'game/images/stadiums/germany/e-frankfurt.jpg',
        915:      'game/images/stadiums/germany/fc-bayern.jpg',
        918:      'game/images/stadiums/germany/mainz.jpg',
        944:      'game/images/stadiums/germany/freiburg.jpg',
        948:      'game/images/stadiums/germany/werder.jpg',
        960:      'game/images/stadiums/germany/stuttgart.jpg',
        961:      'game/images/stadiums/germany/wolfsburg.jpg',
        2238:     'game/images/stadiums/germany/augsburg.jpg',
        2245:     'game/images/stadiums/germany/holstein kiel.jpg',
        121182:   'game/images/stadiums/germany/union berlin.jpg',
        879226:   'game/images/stadiums/germany/hoffenheim.jpg',
        880295:   'game/images/stadiums/germany/heidenheim.jpg',
        3604375:  'game/images/stadiums/germany/st pauli.jpg',
        91013388: 'game/images/stadiums/germany/redbull-leipzig.jpg',
    }
    return stadium_assets.get(club.fm_inside_id, '')


def current_manager_club(user=None):
    """Return the Club currently managed by *user*.

    Pass request.user to get the real assignment; returns None when the
    authenticated user has no club assigned.
    Omit user (or pass None / anonymous) only for legacy views that still
    need the Bayern fallback — those should be migrated over time.
    """
    if user is not None and getattr(user, 'is_authenticated', False):
        try:
            profile = user.manager_profile
            club = Club.objects.select_related('league').get(managed_by=profile)
            return club
        except (Club.DoesNotExist, AttributeError):
            return None
    return (
        Club.objects.select_related('league')
        .filter(fm_inside_id=915)
        .first()
        or Club.objects.select_related('league').filter(name__icontains='Bayern').first()
    )


def city_static_path(club):
    if not club or not club.fm_inside_id:
        return ''

    path = f'game/images/city/{club.fm_inside_id}.jpg'
    if finders.find(path):
        return path

    return ''


def build_game_header(title, subtitle, back_url='/'):
    return {
        'title': title,
        'subtitle': subtitle,
        'back_url': back_url,
    }


def calendar_offset_from_request(request):
    try:
        return int(request.GET.get('calendar_offset', 0))
    except (TypeError, ValueError):
        return 0


def grade_badge_class(grade):
    if grade is None:
        return 'grade-empty'

    grade = float(grade)
    if grade <= 1.5:
        return 'grade-elite'
    if grade <= 2.5:
        return 'grade-good'
    if grade <= 3.5:
        return 'grade-ok'
    if grade <= 4.5:
        return 'grade-warn'
    if grade <= 5.3:
        return 'grade-bad'
    return 'grade-disaster'


def season_table_rows(rows, nt_nationality=None):
    return [
        {
            'season_label': f"#{row.season_number}",
            'competition': row.competition,
            'competition_logo': competition_logo_static_path(row.competition, nt_nationality),
            'matches': row.matches,
            'goals': row.goals,
            'assists': row.assists,
            'substitutions_in': row.substitutions_in,
            'substitutions_out': row.substitutions_out,
            'yellow_cards': row.yellow_cards,
            'red_cards': row.red_cards,
            'player_of_match_awards': row.player_of_match_awards,
            'minutes_played': row.minutes_played,
            'average_grade': row.average_grade,
            'grade_class': grade_badge_class(row.average_grade),
        }
        for row in rows
    ]


def stat_bar_percent(value, maximum, minimum=4):
    if not value or not maximum:
        return 0

    return max(minimum, round((value / maximum) * 100))


def performance_visual_rows(rows):
    if not rows:
        return []

    maxima = {
        'matches': max(row['matches'] for row in rows),
        'goals': max(row['goals'] for row in rows),
        'assists': max(row['assists'] for row in rows),
        'minutes_played': max(row['minutes_played'] for row in rows),
        'cards': max(row['yellow_cards'] + row['red_cards'] for row in rows),
        'subs': max(row['substitutions_in'] + row['substitutions_out'] for row in rows),
        'player_of_match_awards': max(row['player_of_match_awards'] for row in rows),
    }

    visual_rows = []
    for row in rows:
        cards = row['yellow_cards'] + row['red_cards']
        subs = row['substitutions_in'] + row['substitutions_out']
        visual_rows.append({
            **row,
            'cards': cards,
            'substitutions_total': subs,
            'matches_bar': stat_bar_percent(row['matches'], maxima['matches']),
            'goals_bar': stat_bar_percent(row['goals'], maxima['goals']),
            'assists_bar': stat_bar_percent(row['assists'], maxima['assists']),
            'minutes_bar': stat_bar_percent(row['minutes_played'], maxima['minutes_played']),
            'cards_bar': stat_bar_percent(cards, maxima['cards']),
            'subs_bar': stat_bar_percent(subs, maxima['subs']),
            'player_of_match_bar': stat_bar_percent(
                row['player_of_match_awards'],
                maxima['player_of_match_awards'],
            ),
        })

    return visual_rows


def preview_performance_rows(rows, minimum_count=6, nt_nationality=None):
    if not rows or len(rows) >= minimum_count:
        return rows

    result = list(rows)
    existing_competitions = {row['competition'] for row in result}
    samples = [
        ('Europa League', 6, 4, 3, 0, 1, 2, 0, 1, 540, 1.82),
        ('Nationalmannschaft', 5, 3, 2, 1, 0, 1, 0, 2, 410, 1.94),
        ('Club-WM', 4, 2, 2, 1, 1, 1, 0, 1, 360, 2.08),
        ('UEFA Super Cup', 1, 1, 0, 0, 1, 0, 0, 0, 90, 2.10),
        ('Freundschaftspokal', 3, 2, 1, 1, 2, 0, 0, 1, 225, 1.76),
        ('Ligapokal', 2, 1, 1, 0, 0, 0, 0, 0, 180, 2.22),
    ]

    for sample in samples:
        if len(result) >= minimum_count:
            break
        competition = sample[0]
        if competition in existing_competitions:
            continue
        average_grade = sample[10]
        result.append({
            'season_label': rows[0].get('season_label', '#1'),
            'competition': competition,
            'competition_logo': competition_logo_static_path(competition, nt_nationality),
            'matches': sample[1],
            'goals': sample[2],
            'assists': sample[3],
            'substitutions_in': sample[4],
            'substitutions_out': sample[5],
            'yellow_cards': sample[6],
            'red_cards': sample[7],
            'player_of_match_awards': sample[8],
            'minutes_played': sample[9],
            'average_grade': average_grade,
            'grade_class': grade_badge_class(average_grade),
            'is_preview': True,
        })
        existing_competitions.add(competition)

    return result


def career_rows_from_ws_stats(rows, nt_nationality=None):
    grouped = {}

    for row in rows:
        bucket = grouped.setdefault(row.competition, {
            'competition': row.competition,
            'competition_logo': competition_logo_static_path(row.competition, nt_nationality),
            'matches': 0,
            'goals': 0,
            'assists': 0,
            'substitutions_in': 0,
            'substitutions_out': 0,
            'yellow_cards': 0,
            'red_cards': 0,
            'player_of_match_awards': 0,
            'minutes_played': 0,
            'grade_minutes': 0,
            'grade_weighted_sum': 0,
        })
        bucket['matches'] += row.matches
        bucket['goals'] += row.goals
        bucket['assists'] += row.assists
        bucket['substitutions_in'] += row.substitutions_in
        bucket['substitutions_out'] += row.substitutions_out
        bucket['yellow_cards'] += row.yellow_cards
        bucket['red_cards'] += row.red_cards
        bucket['player_of_match_awards'] += row.player_of_match_awards
        bucket['minutes_played'] += row.minutes_played
        if row.average_grade is not None and row.matches:
            bucket['grade_minutes'] += row.matches
            bucket['grade_weighted_sum'] += float(row.average_grade) * row.matches

    career_rows = []
    for bucket in grouped.values():
        average_grade = None
        if bucket['grade_minutes']:
            average_grade = round(
                bucket['grade_weighted_sum'] / bucket['grade_minutes'],
                2,
            )
        career_rows.append({
            **bucket,
            'average_grade': average_grade,
            'grade_class': grade_badge_class(average_grade),
        })

    return sorted(career_rows, key=lambda row: row['competition'])


def money_label(value):
    if value is None or value <= 0:
        return ''

    return f'{value:,.0f} EUR'.replace(',', '.')


def money_full_eur(value):
    if value is None:
        return '0 €'

    return f'{value:,.0f} €'.replace(',', '.')


def transfer_detail_players(candidates, offset, fallback_prefix):
    names = [
        player.full_name
        for player in candidates[offset:offset + 3]
    ]
    while len(names) < 3:
        names.append(f'{fallback_prefix} {len(names) + 1}')
    return names


def transfer_display_rows(rows):
    rows = list(rows)[:6]
    if not rows:
        return []

    candidate_players = list(
        Player.objects.select_related('club')
        .exclude(id__in=[row.player_id for row in rows])
        .order_by('-market_value', 'last_name', 'first_name')[:36]
    )
    clubs = list(
        Club.objects.exclude(fm_inside_id__isnull=True)
        .order_by('-budget', 'name')[:6]
    )

    sample_fees = [
        '78.000.000 EUR',
        'WS-Draft/Initialkader',
        '42.500.000 EUR',
        '18.000.000 EUR',
        'Leihe + Kaufoption',
        '12.000.000 EUR',
    ]

    def build_display_row(
        transfer_date,
        from_club,
        to_club,
        fee_label,
        index,
        is_preview=False,
    ):
        fallback_from = clubs[index % len(clubs)] if clubs else None
        fallback_to = clubs[(index + 1) % len(clubs)] if len(clubs) > 1 else fallback_from
        visible_from_club = from_club if from_club and from_club.crest_static_path else fallback_from
        visible_to_club = to_club if to_club and to_club.crest_static_path else fallback_to

        return {
            'date': transfer_date,
            'from_crest': visible_from_club.crest_static_path if visible_from_club else '',
            'to_crest': visible_to_club.crest_static_path if visible_to_club else '',
            'from_club_url': reverse_club_detail(visible_from_club) if visible_from_club else '',
            'to_club_url': reverse_club_detail(visible_to_club) if visible_to_club else '',
            'fee_label': fee_label or sample_fees[index % len(sample_fees)],
            'outgoing_players': transfer_detail_players(
                candidate_players,
                index * 3,
                'Abgabe',
            ),
            'incoming_players': transfer_detail_players(
                candidate_players,
                index * 3 + 9,
                'Zugang',
            ),
            'is_preview': is_preview,
        }

    display_rows = []

    for index, row in enumerate(rows):
        display_rows.append(
            build_display_row(
                row.transfer_date,
                row.from_club,
                row.to_club,
                money_label(row.fee_eur) or row.notes,
                index,
            )
        )

    base_date = rows[-1].transfer_date if rows else timezone.localdate()
    while len(display_rows) < 6:
        index = len(display_rows)
        from_club = clubs[index % len(clubs)] if clubs else None
        to_club = clubs[(index + 1) % len(clubs)] if len(clubs) > 1 else from_club
        display_rows.append(
            build_display_row(
                base_date - timedelta(days=120 * index),
                from_club,
                to_club,
                sample_fees[index % len(sample_fees)],
                index,
                is_preview=True,
            )
        )

    return display_rows


def pitch_position_slots(player):
    coordinate_slots = [
        ('TW', 49, 89),
        ('LV', 18, 74),
        ('IV', 33, 74),
        ('IV', 49, 74),
        ('IV', 65, 74),
        ('RV', 80, 74),
        ('LOV', 14, 62),
        ('DM', 30, 62),
        ('DM', 49, 62),
        ('DM', 65, 62),
        ('ROV', 83, 62),
        ('LM', 14, 46),
        ('ZM', 31, 46),
        ('ZM', 49, 46),
        ('ZM', 65, 46),
        ('RM', 82, 46),
        ('LOM', 22, 33),
        ('OM', 39, 33),
        ('OM', 59, 33),
        ('ROM', 77, 33),
        ('LF', 28, 25),
        ('ST', 43, 14),
        ('ST', 57, 14),
        ('RF', 70, 25),
    ]
    main_positions = set(player.main_positions)
    secondary_positions = set(player.secondary_positions)
    slots = []

    for index, (code, x, y) in enumerate(coordinate_slots):
        kind = ''
        state = 'neutral'
        if code in main_positions:
            kind = 'HP'
            state = 'main'
        elif code in secondary_positions:
            kind = 'NP'
            state = 'secondary'

        slots.append({
            'code': code,
            'kind': kind,
            'state': state,
            'key': f'{code}-{index}',
            'x': x,
            'y': y,
        })

    return slots


def career_summary_from_ws_stats(rows):
    return {
        'seasons': len({row.season for row in rows}),
        'matches': sum(row.matches for row in rows),
        'goals': sum(row.goals for row in rows),
        'assists': sum(row.assists for row in rows),
        'substitutions_in': sum(row.substitutions_in for row in rows),
        'substitutions_out': sum(row.substitutions_out for row in rows),
        'yellow_cards': sum(row.yellow_cards for row in rows),
        'red_cards': sum(row.red_cards for row in rows),
        'player_of_match_awards': sum(row.player_of_match_awards for row in rows),
        'minutes_played': sum(row.minutes_played for row in rows),
    }


@login_required
def home(request):
    clubs = Club.objects.select_related('league').annotate(
        player_count=Count('player'),
        average_strength=Avg('player__strength_profile__final_strength'),
    )
    richest_clubs = clubs.order_by('-budget')[:6]
    user_assigned_club = current_manager_club(user=request.user)
    user_has_no_club = user_assigned_club is None
    primary_club = user_assigned_club
    secondary_club = (
        clubs.exclude(id=primary_club.id).order_by('-budget').first()
        if primary_club
        else None
    )

    # --- Nächstes / Letztes Spiel aus echten SeasonFixture-Daten ---
    from .fixture_display import FixtureDisplay as FD, get_next_fixture, get_last_fixture
    next_fixture = get_next_fixture(primary_club) if primary_club else None
    last_fixture = get_last_fixture(primary_club) if primary_club else None

    if next_fixture:
        next_match_obj = FD(next_fixture, primary_club)
        next_match_opponent = (
            next_fixture.away_club if next_fixture.home_club_id == primary_club.pk
            else next_fixture.home_club
        )
    else:
        next_match_obj = None
        next_match_opponent = secondary_club

    if last_fixture:
        last_match_obj = FD(last_fixture, primary_club)
        is_home = last_fixture.home_club_id == primary_club.pk
        last_match_opponent = last_fixture.away_club if is_home else last_fixture.home_club
        my_g = last_fixture.home_goals if is_home else last_fixture.away_goals
        opp_g = last_fixture.away_goals if is_home else last_fixture.home_goals
        last_match_score = f'{my_g}:{opp_g}' if my_g is not None and opp_g is not None else None
    else:
        last_match_obj = None
        last_match_opponent = None
        last_match_score = None

    transfer_queryset = Player.objects.select_related(
        'club',
        'club__league',
        'strength_profile',
    )
    if primary_club:
        transfer_queryset = transfer_queryset.exclude(club=primary_club)
    transfer_targets = transfer_queryset.order_by(
        '-market_value',
        '-potential',
        'last_name',
        'first_name',
    )[:3]
    transfer_partner_names = [
        ('Michael Olise', 'Alphonso Davies'),
        ('Jamal Musiala', 'Maximilian Beier'),
        ('Aleksandar Pavlovic', 'Tom Bischof'),
    ]
    transfer_rows = []
    for index, player in enumerate(transfer_targets):
        outgoing_players = [player.full_name]
        incoming_players = []
        for outgoing_name, _incoming_name in transfer_partner_names[:2]:
            outgoing_players.append(outgoing_name)
        for _outgoing_name, incoming_name in transfer_partner_names:
            incoming_players.append(incoming_name)

        transfer_rows.append({
            'player': player,
            'date': date(2026, 7, index + 1),
            'from_crest': player.club.crest_static_path if player.club else '',
            'to_crest': primary_club.crest_static_path if primary_club else '',
            'from_club_url': f'/clubs/{player.club.id}/' if player.club else '',
            'to_club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
            'fee_label': money_label(player.market_value) or money_full_eur(player.market_value),
            'from_label': player.club.short_name if player.club else 'Abgebend',
            'to_label': primary_club.short_name if primary_club else 'Zielverein',
            'outgoing_players': outgoing_players[:3],
            'incoming_players': incoming_players[:3],
        })

    top_strength_players = list(Player.objects.select_related(
        'club',
        'strength_profile',
    ).filter(
        strength_profile__isnull=False,
    ).order_by(
        '-strength_profile__final_strength',
        '-market_value',
        'last_name',
        'first_name',
    )[:4])
    top_strength_player = top_strength_players[0] if top_strength_players else None

    primary_players = (
        Player.objects.filter(club=primary_club)
        if primary_club
        else Player.objects.none()
    )
    primary_market_value = (
        primary_players.aggregate(total=Sum('market_value'))['total'] or 0
    )
    primary_top_scorer = (
        primary_players.filter(ws_season_stats__goals__gt=0)
        .annotate(total_goals=Sum('ws_season_stats__goals'))
        .order_by('-total_goals', '-market_value', 'last_name', 'first_name')
        .first()
    ) or primary_players.order_by('-market_value', 'last_name', 'first_name').first()
    primary_market_player = primary_players.order_by(
        '-market_value',
        '-strength_profile__final_strength',
        'last_name',
        'first_name',
    ).first()
    primary_grade_player = (
        primary_players.filter(ws_season_stats__average_grade__isnull=False)
        .annotate(best_grade=Avg('ws_season_stats__average_grade'))
        .order_by('best_grade', '-market_value', 'last_name', 'first_name')
        .first()
    )
    if primary_grade_player is None:
        primary_grade_player = primary_top_scorer

    if primary_top_scorer:
        top_scorer_label = (
            f'{primary_top_scorer.first_name[:1]}. '
            f'{primary_top_scorer.last_name}'
        )
        top_scorer_portrait = primary_top_scorer.portrait_static_path
    else:
        top_scorer_label = '–'
        top_scorer_portrait = ''

    if primary_market_player:
        market_player_label = (
            f'{primary_market_player.first_name[:1]}. '
            f'{primary_market_player.last_name}'
        )
        market_player_value = money_full_eur(primary_market_player.market_value)
        market_player_portrait = primary_market_player.portrait_static_path
    else:
        market_player_label = 'J. Brandt'
        market_player_value = '78.000.000 €'
        market_player_portrait = ''

    grade_value = getattr(primary_grade_player, 'best_grade', None)
    if primary_grade_player:
        grade_player_label = (
            f'{primary_grade_player.first_name[:1]}. '
            f'{primary_grade_player.last_name}'
        )
        grade_player_value = (
            f'Note {float(grade_value):.2f}'.replace('.', ',')
            if grade_value is not None
            else 'Note 1,80'
        )
        grade_player_portrait = primary_grade_player.portrait_static_path
    else:
        grade_player_label = 'L. Martinez'
        grade_player_value = 'Note 1,80'
        grade_player_portrait = ''

    overview_profile = {
        'budget_label': money_full_eur(primary_club.budget if primary_club else 42800000),
        'club_value_label': money_full_eur(primary_market_value or 214000000),
        'attendance_label': '23.856',
        'top_scorer_label': top_scorer_label,
        'top_scorer_portrait': top_scorer_portrait,
        'spotlights': [
            {
                'title': 'Top-Torjaeger',
                'name': top_scorer_label,
                'meta': '18 Tore',
                'portrait': top_scorer_portrait,
                'player_id': primary_top_scorer.id if primary_top_scorer else None,
            },
            {
                'title': 'Wertvollster Spieler',
                'name': market_player_label,
                'meta': market_player_value,
                'portrait': market_player_portrait,
                'player_id': primary_market_player.id if primary_market_player else None,
            },
            {
                'title': 'Notenbester Spieler',
                'name': grade_player_label,
                'meta': grade_player_value,
                'portrait': grade_player_portrait,
                'player_id': primary_grade_player.id if primary_grade_player else None,
            },
        ],
        'city_static_path': city_static_path(primary_club),
        'fan_percent': primary_club.fan_popularity if primary_club else 0,
        'form': [
            {'label': 'S', 'tone': 'win'},
            {'label': 'S', 'tone': 'win'},
            {'label': 'U', 'tone': 'draw'},
            {'label': 'S', 'tone': 'win'},
            {'label': 'N', 'tone': 'loss'},
        ],
    }

    # Echte Ligatabelle aus LeagueStandings laden
    overview_league_table = []
    _league_for_table = primary_club.league if primary_club else None
    if _league_for_table:
        try:
            _state = GameSeasonState.objects.only('current_season').first()
            _season_key = str(_state.current_season) if _state else '0'
        except Exception:
            _season_key = '0'
        _all_rows = list(
            LeagueStandings.objects
            .filter(league=_league_for_table, season=_season_key)
            .select_related('club')
            .order_by('position', '-points', 'club__name')
        )
        # Top 5 anzeigen, eigenen Verein hervorheben
        for _s in _all_rows[:5]:
            _diff = _s.goals_for - _s.goals_against
            overview_league_table.append({
                'position': _s.position,
                'club_name': _s.club.name,
                'short_name': _s.club.short_name or _s.club.name,
                'crest_static_path': _s.club.crest_static_path,
                'club_url': f'/clubs/{_s.club_id}/',
                'played': _s.played,
                'goals': f'{_s.goals_for}:{_s.goals_against}',
                'goal_difference': f'+{_diff}' if _diff > 0 else str(_diff),
                'points': _s.points,
                'is_current_club': bool(primary_club and _s.club_id == primary_club.id),
            })

    totals = {
        'league_count': League.objects.count(),
        'club_count': Club.objects.count(),
        'player_count': Player.objects.count(),
        'manager_count': get_user_model().objects.filter(is_active=True).count(),
        'total_budget': Club.objects.aggregate(total=Sum('budget'))['total'] or 0,
        'total_market_value': (
            Player.objects.aggregate(total=Sum('market_value'))['total'] or 0
        ),
        'total_salary_per_match': (
            Player.objects.aggregate(total=Sum('salary_per_match'))['total'] or 0
        ),
        'average_strength': (
            Player.objects.aggregate(
                average=Avg('strength_profile__final_strength')
            )['average'] or 0
        ),
        'average_age': (
            Player.objects.aggregate(average=Avg('age'))['average'] or 0
        ),
    }

    club_news = ClubNewsItem.objects.all()[:5]
    sim_news = ClubNewsItem.objects.all()[:5]
    home_stadium_static_path = stadium_static_path(primary_club)
    last_match_home_stadium_static_path = stadium_static_path(primary_club)
    competition_logo_static_path_value = competition_logo_static_path(
        primary_club.league.name
        if primary_club and primary_club.league
        else '1. Bundesliga'
    )

    _other_profiles = ManagerProfile.objects.filter(
        user__is_active=True,
        user__is_staff=False,
        user__is_superuser=False,
    ).exclude(
        user=request.user,
    ).select_related('user').order_by('name')
    _manager_clubs = {
        club.managed_by_id: club
        for club in Club.objects.filter(managed_by__in=_other_profiles)
    }
    active_managers = [
        {
            'name': mp.name,
            'crest': _manager_clubs[mp.id].crest_static_path if mp.id in _manager_clubs else '',
            'club_url': f'/clubs/{_manager_clubs[mp.id].id}/' if mp.id in _manager_clubs else '',
        }
        for mp in _other_profiles
    ]

    return render(
        request,
        'game/home.html',
        {
            'richest_clubs': richest_clubs,
            'user_has_no_club': user_has_no_club,
            'primary_club': primary_club,
            'secondary_club': secondary_club,
            'transfer_targets': transfer_targets,
            'transfer_rows': transfer_rows,
            'top_strength_players': top_strength_players,
            'overview_profile': overview_profile,
            'overview_league_table': overview_league_table,
            'home_stadium_static_path': home_stadium_static_path,
            'last_match_home_stadium_static_path': last_match_home_stadium_static_path,
            'competition_logo_static_path': competition_logo_static_path_value,
            'active_managers': active_managers,
            'chat_messages': [
                {
                    'time': '13.05.2026, 19:34',
                    'author': 'Admin',
                    'text': 'Ihr muesst leider heute nochmal mit einer falschen Darstellung in der Aufstellung leben. Es ist nur die Darstellung, alles wurde sauber gespeichert.',
                },
                {
                    'time': '13.05.2026, 19:35',
                    'author': 'roy10',
                    'text': 'Hab dir FS geschickt.',
                },
                {
                    'time': '13.05.2026, 19:49',
                    'author': 'Gdansk Chris',
                    'text': 'aufgestellt',
                },
            ],
            'club_news': club_news,
            'sim_news': sim_news,
            'social_posts': [
                {
                    'source': 'Transfer Radar',
                    'handle': '@transferradar',
                    'text': 'Geruecht: Um Giuliano Whitchurch entbrennt Spekulation - auch RCD Mallorca wird genannt.',
                    'reactions': '0 Kommentare',
                },
                {
                    'source': 'TR',
                    'handle': '@ligafokus',
                    'text': 'Der Titelkampf bleibt bis zum letzten Spieltag offen.',
                    'reactions': '3 Reaktionen',
                },
            ],
            'next_match': next_match_obj,
            'next_match_opponent': next_match_opponent,
            'last_match': last_match_obj,
            'last_match_opponent': last_match_opponent,
            'last_match_score': last_match_score,
            'last_match_scorers': last_match_obj.scorers if last_match_obj else [],
            'live_matches': [],
            'overview_stats': [
                {'value': str(totals['manager_count']), 'label': 'registrierte Manager'},
                {
                    'value': str(totals['club_count']),
                    'label': 'Profiteam{} in {} Liga{}'.format(
                        's' if totals['club_count'] != 1 else '',
                        totals['league_count'],
                        'en' if totals['league_count'] != 1 else '',
                    ),
                },
                {'value': '0', 'label': 'Jugendteams'},
                {'value': '0', 'label': 'Nationalteams'},
                {'value': str(totals['player_count']), 'label': 'Spieler'},
            ],
            'totals': totals,
            'game_header': build_game_header(
                'MatchEngine',
                'Saisonvorbereitung · Creator Mode',
                '/',
            ),
        }
    )


@login_required
def club_list(request):
    user_has_no_club = current_manager_club(user=request.user) is None

    clubs_qs = Club.objects.select_related('league', 'managed_by').order_by('league__name', 'name')

    if user_has_no_club:
        # Group by league for the "Verein wählen" screen — no strength shown
        from collections import defaultdict
        league_map = defaultdict(list)
        for c in clubs_qs:
            is_free = c.managed_by_id is None
            league_map[c.league].append({
                'id': c.id,
                'name': c.name,
                'short_name': c.short_name,
                'crest_static_path': c.crest_static_path,
                'is_free': is_free,
            })

        leagues = []
        for league, club_list_data in league_map.items():
            free_count = sum(1 for cl in club_list_data if cl['is_free'])
            leagues.append({
                'name': league.name,
                'country': league.country,
                'logo': competition_logo_static_path(league.name),
                'clubs': club_list_data,
                'free_count': free_count,
                'total_count': len(club_list_data),
            })
        leagues.sort(key=lambda l: l['name'])

        return render(request, 'game/club_list.html', {
            'user_has_no_club': True,
            'leagues': leagues,
            'game_header': build_game_header('Verein wählen', 'Starte deine Karriere', '/'),
        })

    # Manager WITH a club: normal overview (no strength shown either)
    clubs = clubs_qs.annotate(player_count=Count('player'))
    return render(
        request,
        'game/club_list.html',
        {
            'user_has_no_club': False,
            'clubs': clubs,
            'game_header': build_game_header(
                'Vereinsübersicht',
                'Scoutingzentrale · Datenbank',
                '/',
            ),
        }
    )


@require_POST
@login_required
def claim_club(request, club_id):
    """Vereinsloser Manager nimmt einen freien Verein.

    Race-Condition-Schutz:
    - select_for_update() sperrt die Club-Zeile für die Dauer der Transaktion.
    - Falls doch zwei Requests gleichzeitig durchkommen, fängt der DB-UNIQUE-
      Constraint (OneToOneField → UNIQUE auf managed_by_id) den zweiten ab und
      Django wirft einen IntegrityError, den wir sauber behandeln.
    """
    import datetime
    from django.db import transaction, IntegrityError
    from .models import PresidentSatisfaction, ManagerProfile as MP, ManagerCareerEntry

    try:
        with transaction.atomic():
            # 1. Manager-Zeile locken — verhindert, dass derselbe User in zwei
            #    Tabs gleichzeitig zwei verschiedene Vereine übernimmt.
            try:
                manager_profile = MP.objects.select_for_update().get(user=request.user)
            except MP.DoesNotExist:
                messages.error(request, 'Kein Manager-Profil gefunden.')
                return redirect('club_list')

            # 2. Prüfen: Hat Manager bereits einen Verein?
            if Club.objects.filter(managed_by=manager_profile).exists():
                messages.error(request, 'Du verwaltest bereits einen Verein.')
                return redirect('club_list')

            # 3. Club-Zeile locken — verhindert, dass zwei verschiedene Manager
            #    denselben Verein gleichzeitig übernehmen.
            try:
                club = Club.objects.select_for_update().get(id=club_id)
            except Club.DoesNotExist:
                messages.error(request, 'Verein nicht gefunden.')
                return redirect('club_list')

            # 4. Prüfen: Ist Verein noch frei?
            if club.managed_by_id is not None:
                messages.error(request, f'„{club.name}" hat bereits einen Manager.')
                return redirect('club_list')

            # 5. Übernahme — DB-UNIQUE-Constraint ist letzte Sicherung.
            club.managed_by = manager_profile
            club.save(update_fields=['managed_by'])

            # 6. Karriereeintrag erstellen (Historienschicht).
            ManagerCareerEntry.objects.create(
                manager=manager_profile,
                club=club,
                started_at=datetime.date.today(),
                active=True,
            )

            # 7. Präsident-Zufriedenheit: Neustart bei 100.
            PresidentSatisfaction.objects.get_or_create(
                manager=manager_profile, club=club, defaults={'value': 100}
            )

    except IntegrityError:
        messages.error(request, 'Die Vereinsübernahme ist fehlgeschlagen. Bitte wähle einen anderen Verein.')
        return redirect('club_list')

    messages.success(request, f'Willkommen bei {club.name}! Deine Karriere beginnt jetzt.')
    return redirect('/')


def tactic_redirect_url(club, squad_scope, **params):
    query = {'squad': squad_scope, **params}
    query_string = '&'.join(f'{key}={value}' for key, value in query.items())
    return f'/clubs/{club.id}/tactics/?{query_string}'


def squad_scope_label(squad_scope):
    return 'Jugend' if squad_scope == 'youth' else 'Profis'


def safe_int(value, default=0, minimum=None, maximum=None):
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def parse_half_tactic(post_data, prefix):
    defaults = default_half_tactic()
    result = {
        'orientation': safe_int(
            post_data.get(f'{prefix}_orientation'),
            defaults['orientation'],
            0,
            100,
        ),
    }
    for field_name, _label in HALF_TACTIC_FIELDS:
        options = {value for value, _option_label in TACTIC_OPTION_GROUPS[field_name]}
        value = post_data.get(f'{prefix}_{field_name}', defaults[field_name])
        result[field_name] = value if value in options else defaults[field_name]
    return result


def parse_tactic_payload_from_post(post_data, club, squad_scope):
    errors = []
    raw_formation = {
        part: post_data.get(f'formation_{part}')
        for part in FORMATION_ORDER
    }
    formation = normalize_formation(raw_formation)
    try:
        validate_formation(formation)
    except Exception as exc:
        errors.append(str(exc))

    available_ids = {
        option['id']
        for option in player_options_for_squad(club, squad_scope)
    }
    slots = formation_slots(formation)
    raw_lineup = {
        slot['key']: post_data.get(f"lineup_{slot['key']}", '')
        for slot in slots
    }
    raw_bench = [
        post_data.get(f'bench_{index}', '')
        for index in range(1, 8)
    ]
    lineup, bench = sanitize_assignments(raw_lineup, raw_bench, available_ids)
    lineup_ids = {player_id for player_id in lineup.values() if player_id}

    standards = {}
    for key, _label in STANDARD_FIELDS:
        raw_value = post_data.get(f'standard_{key}', '')
        try:
            player_id = int(raw_value) if raw_value else ''
        except (TypeError, ValueError):
            player_id = ''
        standards[key] = player_id if player_id in lineup_ids else ''

    raw_substitutions = []
    for index in range(1, 6):
        raw_in = post_data.get(f'substitution_{index}_in', '')
        raw_out = post_data.get(f'substitution_{index}_out', '')
        try:
            player_in = int(raw_in) if raw_in else ''
        except (TypeError, ValueError):
            player_in = ''
        try:
            player_out = int(raw_out) if raw_out else ''
        except (TypeError, ValueError):
            player_out = ''
        raw_substitutions.append({
            'minute': post_data.get(f'substitution_{index}_minute', ''),
            'in': player_in if player_in in available_ids else '',
            'out': player_out if player_out in available_ids else '',
        })
    substitution_validation = validate_substitutions(
        raw_substitutions,
        lineup,
        bench,
    )
    errors.extend(substitution_validation.errors)

    return {
        'payload': {
            'formation': formation,
            'lineup': lineup,
            'bench': bench,
            'standards': {**default_standards(), **standards},
            'substitutions': substitution_validation.substitutions,
            'first_half': parse_half_tactic(post_data, 'first_half'),
            'second_half': parse_half_tactic(post_data, 'second_half'),
        },
        'errors': errors,
    }


def confirm_errors_for_payload(payload):
    errors = []
    slots = formation_slots(payload['formation'])
    missing_slots = [
        slot['code']
        for slot in slots
        if not payload['lineup'].get(slot['key'])
    ]
    if missing_slots:
        errors.append(
            'Zum Bestätigen müssen Torwart und alle 10 Feldspieler besetzt sein.'
        )
    if field_player_count(payload['formation']) != 10:
        errors.append('Die Formation muss genau 10 Feldspieler enthalten.')
    return errors


def all_valid_formation_slot_data():
    data = {}
    part_values = [
        list(FORMATION_PARTS[part].keys())
        for part in FORMATION_ORDER
    ]
    for values in product(*part_values):
        formation = dict(zip(FORMATION_ORDER, values))
        if field_player_count(formation) != 10:
            continue
        data[formation_code(formation)] = {
            'formation': formation,
            'slots': formation_slots(formation),
            'summaries': formation_part_summaries(formation),
        }
    return data


def top_player_rows(club, squad_scope, metric):
    players = Player.objects.filter(club=club)
    if squad_scope == 'youth':
        players = players.filter(age__lte=21)
    else:
        players = players.filter(age__gt=21)

    if metric == 'goals':
        rows = players.annotate(value=Sum('ws_season_stats__goals')).filter(
            value__gt=0,
        ).order_by('-value', 'last_name', 'first_name')[:3]
        return [
            {'name': player.full_name, 'value': player.value, 'portrait': player.portrait_static_path}
            for player in rows
        ]
    if metric == 'assists':
        rows = players.annotate(value=Sum('ws_season_stats__assists')).filter(
            value__gt=0,
        ).order_by('-value', 'last_name', 'first_name')[:3]
        return [
            {'name': player.full_name, 'value': player.value, 'portrait': player.portrait_static_path}
            for player in rows
        ]

    rows = players.annotate(value=Avg('ws_season_stats__average_grade')).filter(
        value__isnull=False,
    ).order_by('value', 'last_name', 'first_name')[:3]
    return [
        {'name': player.full_name, 'value': f'{player.value:.2f}', 'portrait': player.portrait_static_path}
        for player in rows
    ]


def fallback_top_rows(player_options, value):
    return [
        {
            'name': option['name'],
            'value': value,
            'portrait': option['portrait'],
        }
        for option in player_options[:3]
    ]


def ensure_three_top_rows(rows, player_options, fallback_value):
    result = list(rows[:3])
    used_names = {row['name'] for row in result}
    for option in player_options:
        if len(result) >= 3:
            break
        if option['name'] in used_names:
            continue
        result.append({
            'name': option['name'],
            'value': fallback_value,
            'portrait': option['portrait'],
        })
        used_names.add(option['name'])
    return result


def tactic_template_payload(template):
    return tactic_payload_from_setup(template)


def template_options_for_context(templates):
    return [
        {
            'id': template.id,
            'name': template.name,
            'formation_code': formation_code(template.formation),
        }
        for template in templates
    ]


def player_lookup_from_options(player_options):
    return {
        option['id']: option
        for option in player_options
    }


def formation_layer_counts(slots):
    return {
        'attack': sum(1 for slot in slots if slot['group'] == 'attack'),
        'midfield': sum(
            1
            for slot in slots
            if slot['group'] in {'defensive_midfield', 'midfield', 'offensive_midfield'}
        ),
        'defense': sum(1 for slot in slots if slot['group'] == 'defense'),
        'goalkeeper': sum(1 for slot in slots if slot['group'] == 'goalkeeper'),
    }


def tactic_display_absences(rows):
    if rows:
        return rows
    return [
        {'name': 'Spieler X', 'reason': 'fällt aus', 'tone': 'injury'},
        {'name': 'Spieler Y', 'reason': 'fällt aus', 'tone': 'injury'},
        {'name': 'Spieler X', 'reason': 'gesperrt', 'tone': 'suspension'},
        {'name': 'Spieler Y', 'reason': 'gesperrt', 'tone': 'suspension'},
    ]


def split_absence_labels(rows):
    injuries = [row['name'] for row in rows if row['tone'] == 'injury']
    suspensions = [row['name'] for row in rows if row['tone'] == 'suspension']
    return {
        'injuries': ', '.join(injuries) if injuries else 'keine',
        'suspensions': ', '.join(suspensions) if suspensions else 'keine',
    }




def opponent_absence_rows(opponent_club):
    players = []
    if opponent_club:
        players = list(opponent_club.player_set.order_by('last_name', 'first_name', 'id')[:4])

    fallback_names = ['Spieler X', 'Spieler Y', 'Spieler Z', 'Spieler A']
    details = [
        ('injury', 'Muskelverletzung', '12 Tage'),
        ('injury', 'Knieprobleme', '21 Tage'),
        ('suspension', 'Gelbsperre', '1 Spiel'),
        ('suspension', 'Rotsperre', '2 Spiele'),
    ]
    rows = []
    for index, (tone, reason, duration) in enumerate(details):
        player = players[index] if index < len(players) else None
        rows.append({
            'tone': tone,
            'name': player.full_name if player else fallback_names[index],
            'portrait': player.portrait_static_path if player else 'game/images/default_player.svg',
            'reason': reason,
            'duration': duration,
        })
    return rows


def tactic_match_date_display(value):
    if not value:
        return {'weekday': 'Termin offen', 'date': ''}

    month_numbers = {
        'Januar': '01',
        'Februar': '02',
        'März': '03',
        'Maerz': '03',
        'April': '04',
        'Mai': '05',
        'Juni': '06',
        'Juli': '07',
        'August': '08',
        'September': '09',
        'Oktober': '10',
        'November': '11',
        'Dezember': '12',
    }
    if ',' not in value:
        return {'weekday': value, 'date': ''}

    weekday, raw_date = [part.strip() for part in value.split(',', 1)]
    tokens = raw_date.replace('.', '').split()
    if len(tokens) == 3 and tokens[1] in month_numbers:
        return {
            'weekday': f'{weekday},',
            'date': f'{int(tokens[0]):02d}.{month_numbers[tokens[1]]}.{tokens[2]}',
        }
    return {'weekday': f'{weekday},', 'date': raw_date}


def half_tactic_rows(half_tactic):
    return [
        {
            'name': field_name,
            'label': label,
            'selected': half_tactic.get(field_name, default_half_tactic()[field_name]),
            'options': [
                {'value': value, 'label': option_label}
                for value, option_label in TACTIC_OPTION_GROUPS[field_name]
            ],
        }
        for field_name, label in HALF_TACTIC_FIELDS
    ]


def player_name(player_lookup, player_id):
    option = player_lookup.get(player_id)
    return option['name'] if option else ''


def build_tactics_context(request, club, setup, squad_scope, payload=None, form_errors=None):
    payload = payload or tactic_payload_from_setup(setup)
    player_options = player_options_for_squad(club, squad_scope)
    available_ids = {option['id'] for option in player_options}
    payload = sanitize_payload(payload, available_ids)
    player_lookup = player_lookup_from_options(player_options)
    formation = payload['formation']
    slots = []

    for slot in formation_slots(formation):
        selected_id = payload['lineup'].get(slot['key'])
        selected_player = player_lookup.get(selected_id)
        slots.append({
            **slot,
            'selected_id': selected_id or '',
            'player': selected_player,
            'is_captain': bool(
                selected_id and selected_id == payload['standards'].get('captain')
            ),
            'match_state': (
                player_match_state_from_option(selected_player, slot['code'])
                if selected_player
                else 'empty'
            ),
        })

    selected_field_count = sum(
        1
        for slot in slots
        if slot['group'] != 'goalkeeper' and slot['selected_id']
    )
    selected_freshness_values = [
        slot['player']['freshness']
        for slot in slots
        if slot['selected_id'] and slot['player'] and slot['player']['freshness'] is not None
    ]
    average_freshness = (
        round(sum(selected_freshness_values) / len(selected_freshness_values))
        if selected_freshness_values
        else '-'
    )

    bench_rows = []
    for index in range(1, 8):
        selected_id = payload['bench'][index - 1] if index <= len(payload['bench']) else ''
        bench_rows.append({
            'index': index,
            'selected_id': selected_id or '',
            'player': player_lookup.get(selected_id),
        })

    lineup_player_ids = {
        player_id
        for player_id in payload['lineup'].values()
        if player_id
    }
    lineup_player_options = [
        player_lookup[player_id]
        for player_id in lineup_player_ids
        if player_id in player_lookup
    ]
    lineup_player_options.sort(key=lambda option: option['name'])
    standard_rows = []
    for key, label in STANDARD_FIELDS:
        selected_id = payload['standards'].get(key, '')
        standard_rows.append({
            'key': key,
            'label': label,
            'selected_id': selected_id or '',
            'warning': bool(selected_id and selected_id not in lineup_player_ids),
        })

    substitution_rows = []
    for index in range(1, 6):
        existing = payload['substitutions'][index - 1] if index <= len(payload['substitutions']) else {}
        substitution_rows.append({
            'index': index,
            'minute': existing.get('minute', ''),
            'out': existing.get('out', ''),
            'in': existing.get('in', ''),
        })

    profile_context = build_club_profile_context(club)
    profile = profile_context['profile']
    opponent_club = profile_context['opponent_club'] or (
        Club.objects.exclude(id=club.id).order_by('name').first()
    )
    next_match = profile['nextMatch']
    templates = list(
        club.tactic_templates.filter(squad_scope=squad_scope).order_by('name')
    )
    top_goals = ensure_three_top_rows(top_player_rows(club, squad_scope, 'goals'), player_options, 0)
    top_assists = ensure_three_top_rows(top_player_rows(club, squad_scope, 'assists'), player_options, 0)
    top_grades = ensure_three_top_rows(top_player_rows(club, squad_scope, 'grades'), player_options, '-')
    status_label = 'Taktik bestätigt' if setup.is_confirmed else 'Taktik nicht bestätigt'
    formation_choice_rows = []
    for group in formation_choice_groups():
        formation_choice_rows.append({
            **group,
            'selected': formation[group['name']],
        })
    display_absences = tactic_display_absences(
        unavailable_players_for_squad(club, squad_scope)
    )
    duel_home_club = current_manager_club(user=request.user) or club
    duel_away_club = opponent_club
    if duel_home_club and duel_away_club and duel_away_club.id == duel_home_club.id:
        duel_away_club = club
    if duel_home_club and duel_away_club and duel_away_club.id == duel_home_club.id:
        duel_away_club = None

    def duel_avatar_path(manager_club):
        if manager_club and manager_club.crest_static_path:
            return manager_club.crest_static_path
        return 'game/images/default_player.svg'

    return {
        'club': club,
        'squad_scope': squad_scope,
        'squad_scope_label': squad_scope_label(squad_scope),
        'squad_switch': [
            {'value': 'pro', 'label': 'Profis', 'url': tactic_redirect_url(club, 'pro')},
            {'value': 'youth', 'label': 'Jugend', 'url': tactic_redirect_url(club, 'youth')},
        ],
        'setup': setup,
        'payload': payload,
        'status_label': status_label,
        'status_tone': 'confirmed' if setup.is_confirmed else 'open',
        'formation': formation,
        'formation_code': formation_code(formation),
        'formation_count': field_player_count(formation),
        'formation_slots': slots,
        'selected_field_count': selected_field_count,
        'average_freshness': average_freshness,
        'layer_counts': formation_layer_counts(slots),
        'formation_choices': formation_choice_rows,
        'formation_summary': formation_part_summaries(formation),
        'formation_slot_data': all_valid_formation_slot_data(),
        'player_options': player_options,
        'lineup_player_options': lineup_player_options,
        'player_options_by_id': player_lookup,
        'bench_rows': bench_rows,
        'standard_rows': standard_rows,
        'substitution_rows': substitution_rows,
        'unavailable_players': display_absences,
        'hero_absences': split_absence_labels(display_absences),
        'templates': template_options_for_context(templates),
        'template_count': len(templates),
        'template_limit': 10,
        'first_half': {
            **payload['first_half'],
            'orientation_label': orientation_label(payload['first_half']['orientation']),
            'rows': half_tactic_rows(payload['first_half']),
        },
        'second_half': {
            **payload['second_half'],
            'orientation_label': orientation_label(payload['second_half']['orientation']),
            'rows': half_tactic_rows(payload['second_half']),
        },
        'half_tactic_fields': HALF_TACTIC_FIELDS,
        'tactic_option_groups': TACTIC_OPTION_GROUPS,
        'next_match': next_match,
        'match_date_display': tactic_match_date_display(next_match.get('dateLabel')),
        'competition_logo': competition_logo_static_path(next_match.get('competitionName'), next_match.get('ntNationality')),
        'home_club_url': reverse_club_detail(club),
        'away_club_url': reverse_club_detail(opponent_club) if opponent_club else '#',
        'opponent_club': opponent_club,
        'home_form': get_form_rows_with_opponents(club, n=5),
        'away_form': get_form_rows_with_opponents(opponent_club or club, n=5),
        'opponent_absences': opponent_absence_rows(opponent_club),
        'top_goals': top_goals,
        'top_assists': top_assists,
        'top_grades': top_grades,
        'manager_duel': {
            'home': 'Kirschgutzje',
            'away': 'AjaxTactician' if opponent_club else 'Gastmanager',
            'home_rank': 'Profi',
            'away_rank': 'Legende',
            'home_avatar': CURRENT_MANAGER_PROFILE_IMAGE,
            'away_avatar': duel_avatar_path(duel_away_club),
            'rows': [
                {'label': 'Trophäen', 'left': '5', 'right': '12', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Highscore', 'left': '2.150', 'right': '2.430', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Registriert seit', 'left': '12.03.2018', 'right': '01.07.2017', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Spiele', 'left': '1.254', 'right': '1.482', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Siege', 'left': '782', 'right': '912', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Unentschieden', 'left': '241', 'right': '270', 'left_tone': 'trail', 'right_tone': 'lead'},
                {'label': 'Niederlagen', 'left': '231', 'right': '300', 'left_tone': 'lead', 'right_tone': 'trail'},
                {'label': 'Punkte pro Spiel', 'left': '2,02', 'right': '2,04', 'left_tone': 'trail', 'right_tone': 'lead'},
            ],
        },
        'warnings': standard_rows,
        'form_errors': form_errors or [],
        'game_header': build_game_header(
            'Taktik',
            f'{club.name} · {squad_scope_label(squad_scope)}',
            reverse_club_detail(club),
        ),
    }


def player_match_state_from_option(option, slot_code):
    if not option:
        return 'empty'
    if slot_code in option['main_positions']:
        return 'main'
    if slot_code in option['secondary_positions']:
        return 'secondary'
    return 'foreign'


@login_required
def club_detail(request, club_id):
    club = get_object_or_404(
        Club.objects.select_related('league'),
        id=club_id
    )
    context = build_club_profile_context(club)
    opponent_club = context['opponent_club']
    context['game_header'] = build_game_header(
        club.name,
        f'Saison 2026/27 · {club.league.name}',
        '/clubs/',
    )

    return render(
        request,
        'game/club_detail.html',
        context,
    )


def club_tactics(request, club_id):
    club = get_object_or_404(
        Club.objects.select_related('league'),
        id=club_id,
    )
    squad_scope = normalize_squad_scope(
        request.POST.get('squad_scope') or request.GET.get('squad')
    )
    setup, _created = TacticSetup.objects.get_or_create(
        club=club,
        squad_scope=squad_scope,
    )

    if request.method == 'POST':
        action = request.POST.get('action', 'confirm')

        if action == 'load_template':
            template_id = request.POST.get('template_id')
            if not template_id:
                context = build_tactics_context(
                    request,
                    club,
                    setup,
                    squad_scope,
                    form_errors=['Bitte eine Vorlage auswählen.'],
                )
                return render(request, 'game/tactics.html', context)

            template = get_object_or_404(
                TacticTemplate,
                id=template_id,
                club=club,
                squad_scope=squad_scope,
            )
            available_ids = {
                option['id']
                for option in player_options_for_squad(club, squad_scope)
            }
            payload = sanitize_payload(tactic_template_payload(template), available_ids)
            copy_payload_to_setup(setup, payload, confirmed=False)
            setup.full_clean()
            setup.save()
            messages.success(request, f'Vorlage "{template.name}" geladen.')
            return redirect(tactic_redirect_url(club, squad_scope, loaded=1))

        parsed = parse_tactic_payload_from_post(request.POST, club, squad_scope)
        payload = parsed['payload']
        errors = list(parsed['errors'])

        if action == 'save_template':
            template_name = (request.POST.get('template_name') or '').strip()
            if not template_name:
                errors.append('Bitte einen Namen für die Vorlage eingeben.')
            existing_template = TacticTemplate.objects.filter(
                club=club,
                squad_scope=squad_scope,
                name=template_name,
            ).first() if template_name else None
            if (
                template_name
                and existing_template is None
                and club.tactic_templates.filter(squad_scope=squad_scope).count() >= 10
            ):
                errors.append('Es sind maximal 10 Taktikvorlagen pro Bereich erlaubt.')
            if errors:
                context = build_tactics_context(
                    request,
                    club,
                    setup,
                    squad_scope,
                    payload=payload,
                    form_errors=errors,
                )
                return render(request, 'game/tactics.html', context)

            template = existing_template or TacticTemplate(
                club=club,
                squad_scope=squad_scope,
                name=template_name,
            )
            template.formation = payload['formation']
            template.lineup = payload['lineup']
            template.bench = payload['bench']
            template.standards = payload['standards']
            template.substitutions = payload['substitutions']
            template.first_half = payload['first_half']
            template.second_half = payload['second_half']
            template.full_clean()
            template.save()
            messages.success(request, f'Vorlage "{template.name}" gespeichert.')
            return redirect(tactic_redirect_url(club, squad_scope, template_saved=1))

        errors.extend(confirm_errors_for_payload(payload))
        if errors:
            context = build_tactics_context(
                request,
                club,
                setup,
                squad_scope,
                payload=payload,
                form_errors=errors,
            )
            return render(request, 'game/tactics.html', context)

        copy_payload_to_setup(
            setup,
            payload,
            confirmed=True,
            confirmed_at=timezone.now(),
        )
        setup.full_clean()
        setup.save()

        # Mark lineup as set on the next upcoming (unplayed) fixture for this club
        if squad_scope == 'pro':
            from django.db.models import Q
            today = timezone.now().date()
            next_fixture = (
                SeasonFixture.objects
                .filter(Q(home_club=club) | Q(away_club=club), is_played=False, scheduled_date__gte=today)
                .order_by('scheduled_date', 'id')
                .first()
            )
            if next_fixture:
                is_home = next_fixture.home_club_id == club.pk
                field = 'home_lineup_set' if is_home else 'away_lineup_set'
                setattr(next_fixture, field, True)
                next_fixture.save(update_fields=[field])

        messages.success(request, 'Taktik bestätigt und gespeichert.')
        return redirect(tactic_redirect_url(club, squad_scope, confirmed=1))

    context = build_tactics_context(request, club, setup, squad_scope)
    return render(request, 'game/tactics.html', context)


_SQUAD_POSITION_GROUP = {
    'TW': 0,
    'IV': 1, 'LV': 1, 'RV': 1, 'LOV': 1, 'ROV': 1,
    'DM': 2, 'ZM': 2, 'LM': 2, 'RM': 2, 'LOM': 2, 'ROM': 2, 'OM': 2,
    'LF': 3, 'RF': 3, 'ST': 3,
}


def _sorted_squad(players):
    def _key(p):
        pos = p.position or p.primary_position or ''
        group = _SQUAD_POSITION_GROUP.get(pos, 9)
        shirt = p.shirt_number if p.shirt_number is not None else 999
        return (group, shirt, p.last_name, p.first_name)
    return sorted(players, key=_key)


CURRENT_SQUAD_SEASON = '2026/27'
YOUTH_AGE_LIMIT = 21

# Logische Position jedes Postencodes auf dem Spielfeld (vertikal, TW unten,
# ST oben). Prozentwerte (x, y) relativ zum Platz-Rechteck.
SQUAD_PITCH_COORDS = {
    'TW':  (50, 93),
    'LV':  (17, 76),
    'IV':  (50, 78),
    'RV':  (83, 76),
    'LOV': (11, 62),
    'ROV': (89, 62),
    'DM':  (50, 63),
    'LM':  (17, 49),
    'ZM':  (50, 49),
    'RM':  (83, 49),
    'LOM': (29, 34),
    'OM':  (50, 33),
    'ROM': (71, 34),
    'LF':  (22, 17),
    'RF':  (78, 17),
    'ST':  (50, 12),
}


def _aggregate_squad_season_stats(player_ids, season=CURRENT_SQUAD_SEASON):
    """Summiert Saisonstatistiken pro Spieler (alle Wettbewerbe)."""
    stats = {}
    grade_weight = {}
    rows = PlayerSeasonStat.objects.filter(
        player_id__in=player_ids,
        season=season,
    )
    for row in rows:
        bucket = stats.setdefault(row.player_id, {
            'matches': 0, 'goals': 0, 'assists': 0, 'minutes': 0, 'grade': None,
        })
        bucket['matches'] += row.matches
        bucket['goals'] += row.goals
        bucket['assists'] += row.assists
        bucket['minutes'] += row.minutes_played
        if row.average_grade is not None:
            weight = max(row.matches, 1)
            acc = grade_weight.setdefault(row.player_id, [0.0, 0])
            acc[0] += float(row.average_grade) * weight
            acc[1] += weight
    for pid, (total, weight) in grade_weight.items():
        if weight:
            stats[pid]['grade'] = round(total / weight, 2)
    return stats


# ISO-3166-1 alpha-2 / flagcdn-Sondercode → 3-Buchstaben-Anzeigecode (FIFA/IOC-Stil)
_ISO2_TO_CODE3 = {
    'AF': 'AFG', 'AL': 'ALB', 'DZ': 'ALG', 'AD': 'AND', 'AO': 'ANG',
    'AR': 'ARG', 'AM': 'ARM', 'AU': 'AUS', 'AT': 'AUT', 'AZ': 'AZE',
    'BS': 'BAH', 'BH': 'BHR', 'BD': 'BAN', 'BB': 'BRB', 'BY': 'BLR',
    'BE': 'BEL', 'BJ': 'BEN', 'BT': 'BHU', 'BO': 'BOL', 'BA': 'BIH',
    'BW': 'BOT', 'BR': 'BRA', 'BN': 'BRU', 'BG': 'BUL', 'BF': 'BFA',
    'BI': 'BDI', 'CL': 'CHI', 'CN': 'CHN', 'CO': 'COL', 'CR': 'CRC',
    'HR': 'CRO', 'CU': 'CUB', 'CW': 'CUW', 'CZ': 'CZE', 'DK': 'DEN',
    'DJ': 'DJI', 'DO': 'DOM', 'EC': 'ECU', 'EG': 'EGY', 'SV': 'SLV',
    'GQ': 'EQG', 'ER': 'ERI', 'EE': 'EST', 'ET': 'ETH', 'FJ': 'FIJ',
    'FI': 'FIN', 'FR': 'FRA', 'GA': 'GAB', 'GM': 'GAM', 'GE': 'GEO',
    'DE': 'GER', 'GH': 'GHA', 'GR': 'GRE', 'GD': 'GRN', 'GT': 'GUA',
    'GN': 'GUI', 'GW': 'GNB', 'GY': 'GUY', 'HT': 'HAI', 'HN': 'HON',
    'HU': 'HUN', 'IS': 'ISL', 'IN': 'IND', 'ID': 'IDN', 'IR': 'IRN',
    'IQ': 'IRQ', 'IE': 'IRL', 'IL': 'ISR', 'IT': 'ITA', 'JM': 'JAM',
    'JP': 'JPN', 'JO': 'JOR', 'KH': 'CAM', 'CM': 'CMR', 'CA': 'CAN',
    'CV': 'CPV', 'KZ': 'KAZ', 'QA': 'QAT', 'KE': 'KEN', 'KG': 'KGZ',
    'KI': 'KIR', 'KW': 'KUW', 'LA': 'LAO', 'LS': 'LES', 'LV': 'LAT',
    'LB': 'LIB', 'LR': 'LBR', 'LY': 'LBA', 'LT': 'LTU', 'LU': 'LUX',
    'MG': 'MAD', 'MW': 'MAW', 'MY': 'MAS', 'ML': 'MLI', 'MT': 'MLT',
    'MR': 'MTN', 'MX': 'MEX', 'MD': 'MDA', 'MC': 'MON', 'MN': 'MGL',
    'ME': 'MNE', 'MA': 'MAR', 'MZ': 'MOZ', 'MM': 'MYA', 'NA': 'NAM',
    'NP': 'NEP', 'NL': 'NED', 'NZ': 'NZL', 'NI': 'NCA', 'NE': 'NIG',
    'NG': 'NGA', 'NO': 'NOR', 'OM': 'OMA', 'PK': 'PAK', 'PA': 'PAN',
    'PG': 'PNG', 'PY': 'PAR', 'PE': 'PER', 'PH': 'PHI', 'PL': 'POL',
    'PT': 'POR', 'RO': 'ROU', 'RU': 'RUS', 'RW': 'RWA', 'SA': 'KSA',
    'SN': 'SEN', 'RS': 'SRB', 'SL': 'SLE', 'SK': 'SVK', 'SI': 'SVN',
    'SO': 'SOM', 'ZA': 'RSA', 'KR': 'KOR', 'ES': 'ESP', 'LK': 'SRI',
    'SD': 'SDN', 'SR': 'SUR', 'SE': 'SWE', 'CH': 'SUI', 'SY': 'SYR',
    'TJ': 'TJK', 'TZ': 'TAN', 'TH': 'THA', 'TL': 'TLS', 'TG': 'TOG',
    'TT': 'TRI', 'TN': 'TUN', 'TR': 'TUR', 'TM': 'TKM', 'UG': 'UGA',
    'UA': 'UKR', 'AE': 'UAE', 'US': 'USA', 'UY': 'URU', 'UZ': 'UZB',
    'VE': 'VEN', 'VN': 'VIE', 'YE': 'YEM', 'ZM': 'ZAM', 'ZW': 'ZIM',
    'MK': 'MKD', 'XK': 'KOS', 'KP': 'PRK', 'CI': 'CIV', 'CG': 'CGO',
    'CD': 'COD', 'GP': 'GLP',
    # flagcdn-Sondercodes für britische Nationen
    'GB-ENG': 'ENG', 'GB-SCO': 'SCO', 'GB-WAL': 'WAL', 'GB-NIR': 'NIR',
    'GB': 'GBR',
}


def _form_series_map(player_ids, limit=7):
    """Letzte N echten Bewertungen pro Spieler (chronologisch)."""
    series = {}
    snapshots = (
        PlayerFormSnapshot.objects
        .filter(player_id__in=player_ids, rating__isnull=False)
        .order_by('player_id', '-fixture_date', '-fixture_id')
        .values_list('player_id', 'rating')
    )
    for pid, rating in snapshots:
        bucket = series.setdefault(pid, [])
        if len(bucket) < limit:
            bucket.append(float(rating))
    return {pid: list(reversed(values)) for pid, values in series.items()}


def _spark_points(values, width=66, height=22, pad=3):
    """Erzeugt SVG-Polyline-Punkte aus einer Werteliste (5–10 Skala)."""
    if not values:
        return ''
    lo, hi = 4.0, 9.0
    span = hi - lo
    if len(values) == 1:
        values = values * 2
    step = (width - 2 * pad) / (len(values) - 1)
    points = []
    for i, value in enumerate(values):
        clamped = min(max(value, lo), hi)
        ratio = (clamped - lo) / span if span else 0.5
        x = pad + i * step
        y = height - pad - ratio * (height - 2 * pad)
        points.append(f'{x:.1f},{y:.1f}')
    return ' '.join(points)


def _effective_positions(player):
    """Hauptposition(en) und Nebenposition(en) eines Spielers.

    Viele Spieler tragen ihre Position noch im Alt-Feld ``position`` statt in
    den HP-Feldern. Fällt ``main_positions`` leer aus, gilt ``position`` als
    Hauptposition, damit Tabelle und Kaderanalyse die echten Daten zeigen.
    """
    hp = list(player.main_positions)
    if not hp and player.position:
        hp = [player.position]
    np = [code for code in player.secondary_positions if code not in hp]
    return hp, np


def _build_player_row(player, stats, form_map):
    season = stats.get(player.id, {})

    # Fitness
    fitness = None
    profile = getattr(player, 'strength_profile', None)
    if profile and profile.freshness is not None:
        fitness = int(round(float(profile.freshness)))

    # Nation: flagcdn-URL + 3-Buchstaben-Code
    nat_code = ''
    flag_url = ''
    nation_name = ''
    if player.nationalities:
        country = player.nationalities.split(',')[0].strip()
        nation_name = country
        asset = COUNTRY_FLAG_ASSETS.get(country, {})
        iso2 = asset.get('code', '')
        if iso2:
            flag_url = f"https://flagcdn.com/{iso2.lower()}.svg"
            nat_code = _ISO2_TO_CODE3.get(iso2, iso2)

    # Status
    if player.is_ws_injured:
        status = {'code': 'injured', 'label': 'Verletzt'}
    elif player.is_ws_suspended:
        status = {'code': 'suspended', 'label': 'Gesperrt'}
    elif player.is_loaned_in:
        status = {'code': 'loaned_in', 'label': 'Geliehen'}
    else:
        status = {'code': 'fit', 'label': ''}

    # Positionen: max. 3 HP + 3 NP
    hp_all, np_all = _effective_positions(player)
    hp = hp_all[:3]
    np = np_all[:3]

    # Form-Balkendiagramm (letzte 5 Spiele, Skala 1.00–6.00)
    form_values = form_map.get(player.id, [])
    recent = form_values[-5:]
    form_bars = []
    for v in recent:
        grade = 'good' if v < 3.0 else ('ok' if v < 5.0 else 'weak')
        form_bars.append({
            'val': round(v, 2),
            'height_pct': round((6.0 - v) / 5.0 * 100),
            'grade': grade,
        })
    form_empty_bars = [None] * (5 - len(form_bars))
    form_avg = round(sum(recent) / len(recent), 2) if recent else None

    return {
        'id': player.id,
        'shirt': player.shirt_number,
        'name': player.full_name,
        'portrait': player.portrait_static_path,
        'age': player.age,
        'nation_name': nation_name,
        'flag_url': flag_url,
        'nat_code': nat_code,
        'hp': hp,
        'np': np,
        'fitness': fitness,
        'form_bars': form_bars,
        'form_empty_bars': form_empty_bars,
        'form_avg': form_avg,
        'matches': season.get('matches', 0),
        'goals': season.get('goals', 0),
        'assists': season.get('assists', 0),
        'minutes': season.get('minutes', 0),
        'grade': season.get('grade'),
        'market_value': float(player.market_value or 0),
        'market_value_fmt': (f"{int(float(player.market_value)):,}".replace(',', '.') + ' €') if player.market_value else '–',
        'status': status,
        'is_loaned_in': player.is_loaned_in,
        'on_transfer_list': player.is_on_transfer_list,
        'on_loan_list': player.is_on_loan_list,
        'youth_eligible': player.age is not None and player.age < YOUTH_AGE_LIMIT,
        'detail_url': reverse('player_detail', args=[player.id]),
        'tm_url': player.transfermarkt_profile_url or '',
        'edit_pending': False,
    }


def _build_loan_card(player, stats):
    season = stats.get(player.id, {})
    partner = player.loan_partner_club
    hp, _np = _effective_positions(player)
    return {
        'id': player.id,
        'name': player.full_name,
        'portrait': player.portrait_static_path,
        'hp': hp[0] if hp else '—',
        'matches': season.get('matches', 0),
        'grade': season.get('grade'),
        'partner': partner.name if partner else '',
        'loan_until': player.loan_until,
        'detail_url': reverse('player_detail', args=[player.id]),
    }


def _build_squad_context(request, club, squad_title):
    is_youth = squad_title == 'Jugendkader'
    qs = Player.objects.filter(club=club).select_related(
        'strength_profile', 'loan_partner_club')
    if is_youth:
        qs = qs.filter(age__lte=YOUTH_AGE_LIMIT)
    all_club_players = list(qs)

    loaned_out = [p for p in all_club_players if p.is_loaned_out]
    loaned_in = [p for p in all_club_players if p.is_loaned_in]
    # Aktiver Kader: alle Vereinsspieler außer den aktuell Verliehenen.
    active_players = _sorted_squad(
        [p for p in all_club_players if not p.is_loaned_out])

    all_ids = [p.id for p in all_club_players]
    stats = _aggregate_squad_season_stats(all_ids)
    form_map = _form_series_map([p.id for p in active_players])

    player_rows = [
        _build_player_row(p, stats, form_map) for p in active_players]

    # Positionsübersicht (Kaderanalyse) — HP grün, NP gelb.
    position_counts = OrderedDict()
    for code, _label in Player.POSITION_CHOICES:
        coords = SQUAD_PITCH_COORDS.get(code, (50, 50))
        position_counts[code] = {
            'code': code,
            'hp': 0,
            'np': 0,
            'x': coords[0],
            'y': coords[1],
        }
    for p in active_players:
        hp_codes, np_codes = _effective_positions(p)
        for code in hp_codes:
            if code in position_counts:
                position_counts[code]['hp'] += 1
        for code in np_codes:
            if code in position_counts:
                position_counts[code]['np'] += 1
    pitch_positions = list(position_counts.values())

    injured = [r for r in player_rows if r['status']['code'] == 'injured']
    suspended = [r for r in player_rows if r['status']['code'] == 'suspended']

    grades = [r['grade'] for r in player_rows if r['grade'] is not None]
    ages = [r['age'] for r in player_rows if r['age'] is not None]
    total_value = sum(r['market_value'] for r in player_rows)
    total_salary = sum(
        float(p.salary_per_match or 0) for p in active_players)
    available = len(
        [r for r in player_rows
         if r['status']['code'] in ('fit', 'loaned_in')])

    header_stats = [
        {'label': 'Spieler', 'value': str(len(player_rows)), 'sub': 'im Kader',
         'tone': 'cyan'},
        {'label': 'Einsatzbereit', 'value': str(available),
         'sub': f'{len(injured)} verl. · {len(suspended)} gesp.',
         'tone': 'green'},
        {'label': 'Ø Note',
         'value': (f'{sum(grades) / len(grades):.2f}'.replace('.', ',')
                   if grades else '—'),
         'sub': 'Saison', 'tone': 'yellow'},
        {'label': 'Ø Alter',
         'value': (f'{sum(ages) / len(ages):.1f}'.replace('.', ',')
                   if ages else '—'),
         'sub': 'Jahre', 'tone': 'teal'},
        {'label': 'Kaderwert', 'value': compact_money(total_value),
         'sub': 'Marktwert gesamt', 'tone': 'cyan'},
        {'label': 'Gehalt', 'value': compact_money(total_salary),
         'sub': 'pro Spieltag', 'tone': 'red'},
    ]

    # Max. 6 Karten je Box (UI zeigt ~3, Rest per Scroll).
    loaned_in_cards = [_build_loan_card(p, stats) for p in loaned_in[:6]]
    loaned_out_cards = [_build_loan_card(p, stats) for p in loaned_out[:6]]

    is_owner = (
        request.user.is_authenticated
        and current_manager_club(user=request.user) == club
    )

    return {
        'club': club,
        'squad_title': squad_title,
        'is_youth': is_youth,
        'is_owner': is_owner,
        'player_rows': player_rows,
        'player_count': len(player_rows),
        'header_stats': header_stats,
        'position_filters': [code for code, _ in Player.POSITION_CHOICES],
        'pitch_positions': pitch_positions,
        'injured': injured,
        'suspended': suspended,
        'unavailable_count': len(injured) + len(suspended),
        'loaned_in_cards': loaned_in_cards,
        'loaned_out_cards': loaned_out_cards,
        'youth_age_limit': YOUTH_AGE_LIMIT,
        'shirt_action_url': reverse('squad_assign_shirt', args=[club.id]),
        'youth_action_url': reverse('squad_move_to_youth', args=[club.id]),
        'game_header': build_game_header(
            squad_title,
            club.name,
            reverse_club_detail(club),
        ),
    }


def club_professional_squad(request, club_id):
    club = get_object_or_404(Club.objects.select_related('league'), id=club_id)
    return render(request, 'game/club_profile/squad_page.html',
                  _build_squad_context(request, club, 'Profikader'))


def club_youth_squad(request, club_id):
    club = get_object_or_404(Club.objects.select_related('league'), id=club_id)
    return render(request, 'game/club_profile/squad_page.html',
                  _build_squad_context(request, club, 'Jugendkader'))


@login_required
@require_POST
def squad_assign_shirt(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    if current_manager_club(user=request.user) != club:
        return JsonResponse(
            {'ok': False, 'error': 'Keine Berechtigung für diesen Verein.'},
            status=403)
    try:
        player_id = int(request.POST.get('player_id', ''))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Ungültiger Spieler.'},
                            status=400)
    raw_number = (request.POST.get('shirt_number') or '').strip()
    player = get_object_or_404(Player, id=player_id, club=club)

    if raw_number == '':
        player.shirt_number = None
        player.save(update_fields=['shirt_number'])
        return JsonResponse({'ok': True, 'shirt_number': None})

    try:
        number = int(raw_number)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Nummer muss eine Zahl sein.'},
                            status=400)
    if number < 1 or number > 99:
        return JsonResponse(
            {'ok': False, 'error': 'Nummer muss zwischen 1 und 99 liegen.'},
            status=400)

    clash = (Player.objects
             .filter(club=club, shirt_number=number)
             .exclude(id=player.id)
             .first())
    if clash:
        return JsonResponse(
            {'ok': False,
             'error': f'Nummer {number} ist bereits an {clash.full_name} '
                      f'vergeben.'},
            status=409)

    player.shirt_number = number
    player.save(update_fields=['shirt_number'])
    return JsonResponse({'ok': True, 'shirt_number': number})


@login_required
@require_POST
def squad_move_to_youth(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    if current_manager_club(user=request.user) != club:
        return JsonResponse(
            {'ok': False, 'error': 'Keine Berechtigung für diesen Verein.'},
            status=403)
    try:
        player_id = int(request.POST.get('player_id', ''))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Ungültiger Spieler.'},
                            status=400)
    player = get_object_or_404(Player, id=player_id, club=club)
    if player.age is None or player.age >= YOUTH_AGE_LIMIT:
        return JsonResponse(
            {'ok': False,
             'error': 'Nur Spieler unter '
                      f'{YOUTH_AGE_LIMIT} Jahren können in die Jugend.'},
            status=400)
    # Jugendkader = Vereinsspieler unter Altersgrenze; die Zuordnung erfolgt
    # bereits über das Alter. Aktion bestätigt den Spieler als Jugendspieler.
    return JsonResponse(
        {'ok': True,
         'message': f'{player.full_name} ist als Jugendspieler geführt.'})


def club_table(request, club_id):
    club = get_object_or_404(Club.objects.select_related('league'), id=club_id)
    if club.league_id:
        return redirect('league_detail', league_id=club.league_id)
    return render_public_club_stub(
        request,
        club_id,
        'Ligatabelle',
        'Dieser Verein ist keiner Liga zugeordnet.',
    )


def club_match_preview(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Spielvorschau',
        'Die öffentliche Spielvorschau wird als eigener Matchbereich vorbereitet.',
    )


def club_match_report(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Spielbericht',
        'Der öffentliche Spielbericht wird als eigener Matchbereich vorbereitet.',
    )


def club_news(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Vereinsnews',
        'Alle öffentlichen Vereinsmeldungen werden hier gebündelt.',
    )


def club_news_detail(request, club_id, news_id):
    club = get_object_or_404(Club.objects.select_related('league'), id=club_id)
    news_item = get_object_or_404(ClubNewsItem, club=club, id=news_id)
    return render_public_club_stub(
        request,
        club_id,
        news_item.title,
        f'Meldung vom {news_item.published_at:%d.%m.%Y}.',
    )


def render_public_club_stub(request, club_id, title, copy):
    club = get_object_or_404(Club.objects.select_related('league'), id=club_id)
    opponent_club = Club.objects.exclude(id=club.id).order_by('name').first()
    return render(
        request,
        'game/club_profile/stub_page.html',
        {
            'club': club,
            'stub_title': title,
            'stub_copy': copy,
            'game_header': build_game_header(
                title,
                club.name,
                reverse_club_detail(club),
            ),
        },
    )


def reverse_club_detail(club):
    return f'/clubs/{club.id}/'


def _player_nation_nt_logo(player):
    from django.contrib.staticfiles import finders
    from game.models import COUNTRY_FLAG_ASSETS

    registered = (player.nt_nationality or '').strip()
    if registered and registered in COUNTRY_FLAG_ASSETS:
        asset_id = COUNTRY_FLAG_ASSETS[registered].get('asset_id', '')
    else:
        badges = player.nationality_badges
        if not badges:
            return ''
        first_country = badges[0].get('name', '')
        asset_id = COUNTRY_FLAG_ASSETS.get(first_country, {}).get('asset_id', '')

    if asset_id:
        for ext in ('png', 'svg'):
            nt_path = f'game/images/crests/nt_{asset_id}.{ext}'
            if finders.find(nt_path):
                return nt_path

    return ''


def _player_nation_nt_name(player):
    registered = (player.nt_nationality or '').strip()
    if registered:
        return registered
    badges = player.nationality_badges
    if badges:
        return badges[0].get('name', '')
    return ''


def player_detail(request, player_id):
    player = get_object_or_404(
        Player.objects.select_related(
            'club',
            'club__league',
            'real_life_club',
            'real_life_club__league',
            'strength_profile',
        ),
        id=player_id,
    )
    all_season_rows = list(
        PlayerSeasonStat.objects.filter(player=player).order_by(
            '-season_number',
            'competition',
        )
    )
    selected_season_number = max(
        (row.season_number for row in all_season_rows),
        default=1,
    )
    season_rows = [
        row
        for row in all_season_rows
        if row.season_number == selected_season_number
    ]
    market_rows = latest_in_chronological_order(
        player.market_value_snapshots.select_related('source')
    )
    transfer_rows = PlayerTransferHistory.objects.select_related(
        'from_club',
        'to_club',
    ).filter(player=player)[:6]
    injury_rows = PlayerInjuryRecord.objects.filter(player=player)[:5]
    suspension_rows = PlayerSuspensionRecord.objects.filter(player=player)[:5]
    all_award_rows = list(PlayerAwardTitle.objects.filter(player=player))
    award_paginator = Paginator(all_award_rows, 4)
    award_page = award_paginator.get_page(request.GET.get('awards_page'))
    market_points = market_chart_points(
        market_rows,
        player.market_value,
    )
    market_trend = compute_market_value_trend(market_rows)
    award_total_count = sum(row.count for row in all_award_rows)
    freshness = None
    if hasattr(player, 'strength_profile'):
        freshness = player.strength_profile.freshness

    nt_nationality = (
        player.nt_nationality
        or (player.nationalities.split(',')[0].strip() if player.nationalities else None)
    )

    return render(
        request,
        'game/player_detail.html',
        {
            'player': player,
            'season_rows': performance_visual_rows(
                preview_performance_rows(
                    season_table_rows(season_rows, nt_nationality=nt_nationality),
                    6,
                    nt_nationality=nt_nationality,
                )
            ),
            'season_summary': career_summary_from_ws_stats(season_rows),
            'career_summary': career_summary_from_ws_stats(all_season_rows),
            'career_rows': performance_visual_rows(
                preview_performance_rows(
                    career_rows_from_ws_stats(all_season_rows, nt_nationality=nt_nationality),
                    8,
                    nt_nationality=nt_nationality,
                )
            ),
            'market_rows': market_rows,
            'market_trend': market_trend,
            'market_points': market_points,
            'market_axis': market_chart_axis(market_points),
            'market_polyline': market_polyline(market_points),
            'market_area_points': market_area_points(market_points),
            'transfer_rows': transfer_display_rows(transfer_rows),
            'injury_rows': injury_rows,
            'suspension_rows': suspension_rows,
            'award_rows': award_page.object_list,
            'award_slots': award_podium_slots(award_page.object_list),
            'award_page': award_page,
            'award_page_range': award_paginator.page_range,
            'award_count': len(all_award_rows),
            'award_total_count': award_total_count,
            'pitch_slots': pitch_position_slots(player),
            'league_logo': (
                competition_logo_static_path(player.club.league.name)
                if player.club and player.club.league
                else ''
            ),
            'freshness': freshness,
            'shirt_number': player.shirt_number,
            'rl_club_crest': (
                player.real_life_club.crest_static_path
                if player.real_life_club
                else (player.club.crest_static_path if player.club else '')
            ),
            'nation_nt_logo': _player_nation_nt_logo(player),
            'nation_nt_name': _player_nation_nt_name(player),
            'nt_confederation_badge_url': nt_confederation_badge(player),
            'game_header': build_game_header(
                'Spielerprofil',
                f"{player.full_name} · {player.club.name if player.club else 'ohne Verein'}",
                f"/clubs/{player.club.id}/" if player.club else '/',
            ),
        }
    )


def player_graph_data(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    market_rows = latest_in_chronological_order(
        player.market_value_snapshots.select_related('source')
    )
    rating_rows = latest_in_chronological_order(
        player.source_rating_snapshots.select_related('source')
    )
    strength_rows = latest_in_chronological_order(
        player.strength_snapshots.all()
    )
    weighted_rating_rows = latest_in_chronological_order(
        player.weighted_rating_snapshots.all()
    )
    match_rating_rows = latest_form_snapshots_in_chronological_order(
        player.form_snapshots.all()
    )
    rating_series = {
        'fm_rating': [],
        'fm_potential': [],
        'sofifa_rating': [],
        'sofifa_potential': [],
    }
    source_to_series = {
        DataSource.CODE_FMINSIDE: ('fm_rating', 'fm_potential'),
        DataSource.CODE_SOFIFA: ('sofifa_rating', 'sofifa_potential'),
        PlayerSourceRating.SOURCE_EA: ('sofifa_rating', 'sofifa_potential'),
    }

    for row in rating_rows:
        series_keys = source_to_series.get(row.source.code)
        if not series_keys:
            continue

        rating_key, potential_key = series_keys
        rating_series[rating_key].append({
            'x': date_label(row.recorded_at),
            'y': row.rating,
            'source': row.source.name,
        })
        if row.potential is not None:
            rating_series[potential_key].append({
                'x': date_label(row.recorded_at),
                'y': row.potential,
                'source': row.source.name,
            })

    return JsonResponse({
        'player': {
            'id': player.id,
            'wsc_player_id': player.wsc_player_id,
            'name': player.full_name,
        },
        'market_value': [
            {
                'x': date_label(row.recorded_at),
                'y': decimal_number(row.value_eur),
                'source': row.source.name,
                'profile_url': row.profile_url,
            }
            for row in market_rows
        ],
        'source_ratings': rating_series,
        'match_ratings': [
            {
                'x': date_label(row.fixture_date),
                'y': decimal_number(row.rating),
                'source': row.get_source_display(),
                'fixture_id': row.fixture_id,
                'opponent': row.opponent_name,
                'minutes_played': row.minutes_played,
                'goals': row.goals,
                'assists': row.assists,
            }
            for row in match_rating_rows
            if row.rating is not None
        ],
        'weighted_ratings': [
            {
                'x': date_label(row.recorded_at),
                'y': decimal_number(row.weighted_rating),
                'source': row.get_source_display(),
                'fixture_reference': row.fixture_reference,
                'rating_minutes': row.rating_minutes,
                'match_count': row.match_count,
                'window_label': row.window_label,
            }
            for row in weighted_rating_rows
        ],
        'strength': {
            'base_strength': [
                {
                    'x': date_label(row.recorded_at),
                    'y': decimal_number(row.base_strength),
                    'match_reference': row.match_reference,
                }
                for row in strength_rows
            ],
            'final_strength': [
                {
                    'x': date_label(row.recorded_at),
                    'y': decimal_number(row.final_strength),
                    'match_reference': row.match_reference,
                }
                for row in strength_rows
            ],
            'max_strength': [
                {
                    'x': date_label(row.recorded_at),
                    'y': decimal_number(row.max_strength),
                    'match_reference': row.match_reference,
                }
                for row in strength_rows
            ],
            'last_10_average_strength': [
                {
                    'x': date_label(row.recorded_at),
                    'y': decimal_number(row.last_10_average_strength),
                    'match_reference': row.match_reference,
                }
                for row in strength_rows
                if row.last_10_average_strength is not None
            ],
        },
    })


@login_required
def manager_profile(request):
    tab = request.GET.get('tab', 'profil')

    club = current_manager_club(user=request.user)

    club_profile = None
    if club:
        try:
            club_profile = club.public_profile
        except ClubPublicProfile.DoesNotExist:
            club_profile = None

    club_name = club.name if club else 'Kein Verein'
    club_crest = club.crest_static_path if club else ''
    club_url = f'/clubs/{club.id}/' if club else '/clubs/'

    # --- Trophies from ClubTrophy ---
    db_trophies = list(club.public_trophies.all()) if club else []
    _default_icons = [
        'game/images/icons/Default Trophy 1.png',
        'game/images/icons/Default Trophy 2.png',
        'game/images/icons/Default Trophy 3.png',
        'game/images/icons/Default Trophy 4.png',
    ]
    trophies_list = [
        {
            'name': t.competition_name,
            'count': t.count,
            'icon': t.trophy_static_path or _default_icons[i % len(_default_icons)],
        }
        for i, t in enumerate(db_trophies)
    ]
    trophies_count = sum(t.count for t in db_trophies)

    # --- Match stats from MatchResult (full career history) ---
    if club:
        all_results = list(
            MatchResult.objects.filter(club=club)
            .select_related('home_club', 'away_club')
            .order_by('sort_order', 'id')
        )
    else:
        all_results = []

    wins = 0
    draws = 0
    losses = 0
    goals_scored = 0
    goals_against = 0
    for m in all_results:
        hg = m.home_goals or 0
        ag = m.away_goals or 0
        if m.home_club_id == club.id:
            club_g, opp_g = hg, ag
        else:
            club_g, opp_g = ag, hg
        if m.result_label == MatchResult.RESULT_WIN:
            wins += 1
        elif m.result_label == MatchResult.RESULT_DRAW:
            draws += 1
        elif m.result_label == MatchResult.RESULT_LOSS:
            losses += 1
        goals_scored += club_g
        goals_against += opp_g

    games = wins + draws + losses
    points = wins * 3 + draws
    win_pct = round(wins / games * 100) if games else 0
    draw_pct = round(draws / games * 100) if games else 0
    loss_pct = round(losses / games * 100) if games else 0
    ppg = f'{points / games:.2f}'.replace('.', ',') if games else '0,00'
    gpg = f'{goals_scored / games:.2f}'.replace('.', ',') if games else '0,00'
    gagpg = f'{goals_against / games:.2f}'.replace('.', ',') if games else '0,00'
    win_rate = f'{win_pct}%'
    win_rate_detail = f'({wins} S / {draws} U / {losses} N)'

    # --- Streak computation (longest run of consecutive wins / losses) ---
    max_win_streak = 0
    max_loss_streak = 0
    cur_win = 0
    cur_loss = 0
    for m in all_results:
        if m.result_label == MatchResult.RESULT_WIN:
            cur_win += 1
            cur_loss = 0
        elif m.result_label == MatchResult.RESULT_LOSS:
            cur_loss += 1
            cur_win = 0
        else:
            cur_win = 0
            cur_loss = 0
        max_win_streak = max(max_win_streak, cur_win)
        max_loss_streak = max(max_loss_streak, cur_loss)

    club_stats = {
        'games': games,
        'wins': wins,
        'win_pct': win_pct,
        'draws': draws,
        'draw_pct': draw_pct,
        'losses': losses,
        'loss_pct': loss_pct,
        'goals': goals_scored,
        'goals_against': goals_against,
        'points': points,
        'points_per_game': ppg,
        'goals_per_game': gpg,
        'goals_against_per_game': gagpg,
        'win_streak': max_win_streak,
        'loss_streak': max_loss_streak,
    }

    # --- Records: true maxima from all stored match results ---
    best_win_margin = -1
    best_win_str = '–'
    best_loss_margin = -1
    best_loss_str = '–'
    best_goals_total = -1
    best_goals_str = '–'
    for m in all_results:
        hg = m.home_goals or 0
        ag = m.away_goals or 0
        if m.home_club_id == club.id:
            club_g, opp_g = hg, ag
            opp_name = m.away_club.name if m.away_club else '?'
        else:
            club_g, opp_g = ag, hg
            opp_name = m.home_club.name if m.home_club else '?'
        total_goals = hg + ag
        is_win = m.result_label == MatchResult.RESULT_WIN
        is_loss = m.result_label == MatchResult.RESULT_LOSS
        margin = club_g - opp_g
        if is_win and margin > best_win_margin:
            best_win_margin = margin
            best_win_str = f'{club_g}:{opp_g} vs. {opp_name}'
        if is_loss and (opp_g - club_g) > best_loss_margin:
            best_loss_margin = opp_g - club_g
            best_loss_str = f'{opp_g}:{club_g} vs. {opp_name}'
        if total_goals > best_goals_total:
            best_goals_total = total_goals
            best_goals_str = f'{total_goals} vs. {opp_name}'
    records_highest_win = best_win_str
    records_highest_loss = best_loss_str
    records_most_goals = best_goals_str

    # --- Last match from ClubProfileMatch (for display / timeline only) ---
    if club:
        finished_matches = list(
            ClubProfileMatch.objects.filter(club=club)
            .exclude(result_label='')
            .select_related('home_club', 'away_club')
        )
    else:
        finished_matches = []

    # Transfer records from PlayerTransferHistory
    transfer_in_str = '–'
    transfer_out_str = '–'
    if club:
        best_in = (
            PlayerTransferHistory.objects.filter(to_club=club)
            .exclude(fee_eur=None).exclude(fee_eur=0)
            .select_related('player')
            .order_by('-fee_eur')
            .first()
        )
        best_out = (
            PlayerTransferHistory.objects.filter(from_club=club)
            .exclude(fee_eur=None).exclude(fee_eur=0)
            .select_related('player')
            .order_by('-fee_eur')
            .first()
        )
        if best_in:
            fee_fmt = f'€{int(best_in.fee_eur):,}'.replace(',', '.')
            date_fmt = best_in.transfer_date.strftime('%d.%m.%Y') if best_in.transfer_date else '–'
            transfer_in_str = f'{fee_fmt} – {best_in.player.full_name} ({date_fmt})'
        if best_out:
            fee_fmt = f'€{int(best_out.fee_eur):,}'.replace(',', '.')
            date_fmt = best_out.transfer_date.strftime('%d.%m.%Y') if best_out.transfer_date else '–'
            transfer_out_str = f'{fee_fmt} – {best_out.player.full_name} ({date_fmt})'

    # --- Timeline events built from real DB data ---
    timeline_events = []

    # Club join event
    timeline_events.append({
        'date': '15. Aug. 2023',
        'type': 'verein',
        'tone': 'neutral',
        'title': 'Willkommen an Bord',
        'body': f'Übernahme von {club_name} (1. Saison)',
        'icon': 'join',
        'crest': club_crest,
    })

    # Trophy events from ClubTrophy
    for trophy in db_trophies:
        timeline_events.append({
            'date': '–',
            'type': 'titel',
            'tone': 'gold',
            'title': trophy.competition_name,
            'body': f'{trophy.count}x gewonnen mit {club_name}',
            'icon': 'trophy',
            'crest': club_crest,
        })

    # Last match result as timeline event
    for m in finished_matches:
        tone_map = {
            ClubProfileMatch.RESULT_WIN: 'gold',
            ClubProfileMatch.RESULT_DRAW: 'silver',
            ClubProfileMatch.RESULT_LOSS: 'red',
        }
        result_de = {
            ClubProfileMatch.RESULT_WIN: 'Sieg',
            ClubProfileMatch.RESULT_DRAW: 'Unentschieden',
            ClubProfileMatch.RESULT_LOSS: 'Niederlage',
        }.get(m.result_label, '')
        if m.home_club_id == club.id:
            opponent = m.away_club
            score = f'{m.home_goals}:{m.away_goals}'
        else:
            opponent = m.home_club
            score = f'{m.away_goals}:{m.home_goals}'
        opp_name = opponent.name if opponent else 'Unbekannt'
        opp_crest = opponent.crest_static_path if opponent else ''
        timeline_events.append({
            'date': m.date_label or '–',
            'type': 'liga',
            'tone': tone_map.get(m.result_label, 'neutral'),
            'title': f'{result_de} gegen {opp_name}',
            'body': f'{m.competition_name}: {score}',
            'icon': 'table',
            'crest': opp_crest,
        })

    # Transfer events from PlayerTransferHistory
    if club:
        top_transfers = (
            PlayerTransferHistory.objects.filter(to_club=club)
            .exclude(fee_eur=None).exclude(fee_eur=0)
            .select_related('player')
            .order_by('-fee_eur')[:2]
        )
        for t in top_transfers:
            fee_fmt = f'€{int(t.fee_eur):,}'.replace(',', '.')
            date_fmt = t.transfer_date.strftime('%-d. %b %Y') if t.transfer_date else '–'
            timeline_events.append({
                'date': date_fmt,
                'type': 'transfers',
                'tone': 'cyan',
                'title': 'Einkauf',
                'body': f'{fee_fmt} für {t.player.full_name}',
                'icon': 'transfer',
            })

    # --- Manager profile (needed for career stations and trainer types) ---
    from .models import ManagerProfile, ManagerCareerStation, COUNTRY_FLAG_ASSETS
    from django.db.models import Sum as _Sum
    if request.user.is_authenticated:
        manager_profile_obj, _ = ManagerProfile.objects.get_or_create(
            user=request.user,
            defaults={'name': request.user.username},
        )
    else:
        manager_profile_obj = ManagerProfile.objects.first()

    # --- Map stations from ManagerCareerStation (real career history) ---
    db_stations = list(
        ManagerCareerStation.objects.filter(manager=manager_profile_obj)
        .select_related('club', 'club__public_profile')
        .order_by('order')
    )

    map_stations = []
    if db_stations:
        for st in db_stations:
            is_active = st.ended_at is None
            if st.club:
                station_crest = st.club.crest_static_path
                station_club_name = st.club.name
                trophy_total = (
                    ClubTrophy.objects.filter(club_id=st.club_id)
                    .aggregate(total=_Sum('count'))['total'] or 0
                )
            else:
                station_crest = club_crest
                station_club_name = st.city_name
                trophy_total = 0

            station_games = games if is_active else st.games_played

            city_display = st.city_name
            if not city_display and st.club:
                try:
                    city_display = st.club.public_profile.city_name or st.club.name
                except Exception:
                    city_display = st.club.name

            station_club_url = f'/clubs/{st.club.id}/' if st.club else ''
            season_rows = _station_season_breakdown(
                st.started_at, st.ended_at, station_games, trophy_total
            )
            map_stations.append({
                'id': st.id,
                'city': city_display,
                'country': st.city_country,
                'club': st.custom_club_name or station_club_name,
                'crest': station_crest,
                'x': st.map_x,
                'y': st.map_y,
                'active': is_active,
                'period': st.period_label,
                'order': st.order,
                'games': station_games,
                'titles': trophy_total,
                'club_url': station_club_url,
                'season_breakdown_json': json.dumps(season_rows),
                'started_year': st.started_at.year if st.started_at else '',
                'ended_year': st.ended_at.year if st.ended_at else '',
                'has_club_fk': bool(st.club_id),
            })
    elif club is not None:
        # Fallback: single station from ClubPublicProfile (only if manager has a club)
        city = (club_profile.city_name if club_profile and club_profile.city_name else 'München')
        country = (club_profile.city_country if club_profile and club_profile.city_country else 'Deutschland')
        fallback_season_rows = _station_season_breakdown(
            date(2023, 8, 15), None, games, trophies_count
        )
        map_stations.append({
            'city': city,
            'country': country,
            'club': club_name,
            'crest': club_crest,
            'x': 271,
            'y': 214,
            'active': True,
            'period': '15. Aug. 2023 – heute',
            'order': 1,
            'games': games,
            'titles': trophies_count,
            'club_url': club_url,
            'season_breakdown_json': json.dumps(fallback_season_rows),
        })

    # --- Trainer types (db-persisted) ---
    manager_name = manager_profile_obj.name
    active_type_key = manager_profile_obj.trainer_type
    trainer_types_selectable = [
        {'key': 'laptoptrainer', 'label': 'Laptoptrainer', 'active': active_type_key == 'laptoptrainer'},
        {'key': 'taktikfuchs', 'label': 'Taktikfuchs', 'active': active_type_key == 'taktikfuchs'},
        {'key': 'motivator', 'label': 'Motivator', 'active': active_type_key == 'motivator'},
        {'key': 'talentschmied', 'label': 'Talentschmied', 'active': active_type_key == 'talentschmied'},
        {'key': 'transferstratege', 'label': 'Transferstratege', 'active': active_type_key == 'transferstratege'},
        {'key': 'pokaljager', 'label': 'Pokaljäger', 'active': active_type_key == 'pokaljager'},
        {'key': 'offensivarchitekt', 'label': 'Offensivarchitekt', 'active': active_type_key == 'offensivarchitekt'},
        {'key': 'underdog', 'label': 'Underdog-Flüsterer', 'active': active_type_key == 'underdog'},
    ]

    trainer_types_unlockable = _build_trainer_types_unlockable(club, trophies_count)

    login_history = [
        {'date': 'Heute, 09:42', 'location': 'München, Deutschland', 'device': 'Windows PC', 'success': True},
        {'date': 'Gestern, 18:23', 'location': 'München, Deutschland', 'device': 'MacBook Pro', 'success': True},
        {'date': '29.05.2025, 21:15', 'location': 'München, Deutschland', 'device': 'iPhone 15 Pro', 'success': True},
        {'date': '10.05.2025, 14:08', 'location': 'Düsseldorf, Deutschland', 'device': 'Android Tablet', 'success': True},
        {'date': '09.05.2025, 18:52', 'location': 'München, Deutschland', 'device': 'Windows PC', 'success': True},
    ]

    member_since_display = (
        manager_profile_obj.member_since.strftime('%d.%m.%Y')
        if manager_profile_obj.member_since
        else (
            request.user.date_joined.strftime('%d.%m.%Y')
            if request.user.is_authenticated and request.user.date_joined
            else '–'
        )
    )
    last_login_display = (
        request.user.last_login.strftime('%d.%m.%Y, %H:%M')
        if request.user.is_authenticated and request.user.last_login
        else '–'
    )
    _raw_image = manager_profile_obj.profile_image or ''
    if _raw_image and not _raw_image.startswith('game/'):
        from django.conf import settings as _settings
        profile_image_url = request.build_absolute_uri(_settings.MEDIA_URL + _raw_image)
    else:
        from django.templatetags.static import static as _static
        profile_image_url = _static(_raw_image or 'game/images/managers/default-manager.png')

    # --- Derive active career station for header display ---
    _active_st = next((st for st in db_stations if st.ended_at is None), None)

    def _fmt_de_date(d):
        if d is None:
            return '–'
        _months_de = [
            '', 'Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni',
            'Juli', 'Aug.', 'Sep.', 'Okt.', 'Nov.', 'Dez.',
        ]
        return f'{d.day}. {_months_de[d.month]} {d.year}'

    def _time_elapsed_de(d):
        if d is None:
            return ''
        from datetime import date as _date_cls
        today = _date_cls.today()
        months = (today.year - d.year) * 12 + (today.month - d.month)
        years, rem_months = divmod(months, 12)
        if years and rem_months:
            return f'{years} Jahr{"e" if years != 1 else ""}, {rem_months} Monat{"e" if rem_months != 1 else ""}'
        if years:
            return f'{years} Jahr{"e" if years != 1 else ""}'
        return f'{rem_months} Monat{"e" if rem_months != 1 else ""}'

    if _active_st and _active_st.started_at:
        _club_since_dt = _active_st.started_at
        _club_since_str = _fmt_de_date(_club_since_dt)
        _current_period_str = f'{_club_since_str} – heute'
        _time_label_str = _time_elapsed_de(_club_since_dt)
        # Season count: rough estimate (season starts Aug 1)
        from datetime import date as _date_cls
        _today = _date_cls.today()
        _start_year = _club_since_dt.year if _club_since_dt.month >= 8 else _club_since_dt.year - 1
        _curr_year = _today.year if _today.month >= 8 else _today.year - 1
        _season_num = max(1, _curr_year - _start_year + 1)
        _club_season_str = f'{_season_num}. Saison'
    else:
        _club_since_str = '–'
        _current_period_str = '–'
        _time_label_str = '–'
        _club_season_str = '1. Saison'

    # --- Photo map markers (satellite image, lat/lng-calibrated) ---
    photo_map_markers = []

    if db_stations:
        for _st in db_stations:
            _prof_city = None
            if _st.club:
                try:
                    _prof_city = _st.club.public_profile.city_name
                except Exception:
                    _prof_city = None
            _city_label = _st.city_name or _prof_city or (
                _st.club.name if _st.club else 'München'
            )
            # Table-first: use hand-verified pixel positions when the city is
            # known; only fall back to the lat/lng TPS formula otherwise.
            _pct = city_map_pct(
                _st.city_name, _st.custom_club_name, _prof_city,
                _st.club.name if _st.club else None,
            )
            if _pct is not None:
                _xp, _yp = _pct
            else:
                _lat = _lng = None
                if _st.club:
                    try:
                        _prof = _st.club.public_profile
                        _lat, _lng = _prof.map_lat, _prof.map_lng
                    except Exception:
                        pass
                if _lat is None or _lng is None:
                    _resolved = resolve_city_latlng(_st.city_name, _st.custom_club_name)
                    if _resolved is None and (_st.map_x, _st.map_y) != (271, 214):
                        _resolved = map_xy_to_lat_lng(_st.map_x, _st.map_y)
                    _lat, _lng = _resolved if _resolved is not None else (48.22, 11.55)
                _xp, _yp = lat_lng_to_map_pct(_lat, _lng)
            _is_active = _st.ended_at is None
            _crest = _st.club.crest_static_path if _st.club else club_crest
            from django.templatetags.static import static as _s
            _crest_url = _s(_crest) if _crest else ''
            photo_map_markers.append({
                'x_pct': _xp, 'y_pct': _yp,
                'club': _st.custom_club_name or (_st.club.name if _st.club else ''),
                'city': _city_label,
                'crest_url': _crest_url,
                'is_active': _is_active,
            })
    elif club is not None:
        # Fallback: single marker from ClubPublicProfile (only if manager has a club)
        _city = club_profile.city_name if club_profile and club_profile.city_name else None
        _pct = city_map_pct(_city, club_name)
        if _pct is not None:
            _xp, _yp = _pct
        else:
            _lat = club_profile.map_lat if club_profile and club_profile.map_lat else 48.22
            _lng = club_profile.map_lng if club_profile and club_profile.map_lng else 11.55
            _xp, _yp = lat_lng_to_map_pct(_lat, _lng)
        from django.templatetags.static import static as _s
        photo_map_markers.append({
            'x_pct': _xp, 'y_pct': _yp,
            'club': club_name,
            'city': club_profile.city_name if club_profile and club_profile.city_name else 'München',
            'crest_url': _s(club_crest),
            'is_active': True,
        })

    city_coords_json = json.dumps({k: list(v) for k, v in EUROPEAN_CITY_COORDS.items()})

    # Single-station minimum-zoom: when there is exactly one marker, supply the
    # country's bounding box so the JS can zoom to show the whole country instead
    # of just the city area (which gives zero geographic context).
    _country_zoom_box = None
    if len(photo_map_markers) == 1:
        _station_country = ''
        if db_stations:
            _station_country = (db_stations[0].city_country or '').strip()
        else:
            _station_country = (
                (club_profile.city_country if club_profile and club_profile.city_country else '')
                or 'Deutschland'
            ).strip()
        _country_zoom_box = country_map_bbox(_station_country)
    country_zoom_box_json = json.dumps(_country_zoom_box)  # 'null' when multi-station

    from django.templatetags.static import static as _static_fn
    _clubs_with_crests = [
        {
            'id': c.id,
            'name': c.name,
            'crest_url': _static_fn(c.crest_static_path) if c.crest_static_path else '',
        }
        for c in Club.objects.order_by('name')
    ]

    return render(request, 'game/manager_profile.html', {
        'tab': tab,
        'timeline_events': timeline_events,
        'game_header': build_game_header(
            f'Manager · {manager_name}',
            'Trainerprofil',
            '/',
        ),
        'trainer_types_selectable': trainer_types_selectable,
        'trainer_types_unlockable': trainer_types_unlockable,
        'map_stations': map_stations,
        'photo_map_markers': photo_map_markers,
        'country_zoom_box_json': country_zoom_box_json,
        'login_history': login_history,
        'trophies_list': trophies_list,
        'manager': {
            'name': manager_name,
            'trainer_type': manager_profile_obj.trainer_type_label,
            'active_type': manager_profile_obj.trainer_type_label,
            'flag': manager_profile_obj.nationality_flag,
            'flag_url': manager_profile_obj.nationality_flag,
            'flag_name': manager_profile_obj.nationality_name,
            'club_name': club_name,
            'club_crest': club_crest,
            'club_url': club_url,
            'club_since': _club_since_str,
            'club_season': _club_season_str,
            'member_since': member_since_display,
            'profile_image_url': profile_image_url,
            'level': manager_profile_obj.level,
            'xp': manager_profile_obj.xp,
            'xp_max': manager_profile_obj.xp_max,
            'xp_pct': manager_profile_obj.xp_pct,
            'xp_label': manager_profile_obj.xp_label,
            'highscore': manager_profile_obj.highscore,
            'highscore_rank': '–',
            'trophies': trophies_count,
            'games_total': games,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'win_rate': win_rate,
            'win_rate_detail': win_rate_detail,
            'not_fielded': '1/3',
            'transfer_ban': 'Keine',
            'last_login': last_login_display,
            'registered': member_since_display,
        },
        'club_stats': club_stats,
        'current_club_summary': {
            'name': club_name,
            'crest': club_crest,
            'period': _current_period_str,
            'url': club_url,
            'time_label': _time_label_str,
            'games': games,
            'titles': trophies_count,
            'finals_lost': 0,
            'best_position': '–',
            'points_per_game': ppg,
        },
        'records': {
            'highest_win': records_highest_win,
            'wins_in_row': '–',
            'highest_loss': records_highest_loss,
            'most_goals': records_most_goals,
            'transfer_out': transfer_out_str,
            'transfer_in': transfer_in_str,
        },
        'login_streak': 7,
        'login_points_today': 150,
        'next_reward_days': 2,
        'country_choices': sorted(COUNTRY_FLAG_ASSETS.keys()),
        'country_choices_with_flags': [
            {'name': k, 'code': v['code'].lower()}
            for k, v in sorted(COUNTRY_FLAG_ASSETS.items())
        ],
        'current_nationality': manager_profile_obj.nationality_name,
        'all_clubs': _clubs_with_crests,
        'manager_trainer_type_key': manager_profile_obj.trainer_type,
        'manager_favourite_club_id': manager_profile_obj.favourite_club_id or '',
        'can_edit_profile': request.user.is_superuser,
        'has_custom_image': bool(_raw_image) and not _raw_image.startswith('game/'),
        'name_confirmed': request.user.is_authenticated and manager_profile_obj.name_confirmed,
        'city_coords_json': city_coords_json,
    })


def _station_season_breakdown(started_at, ended_at, total_games, total_titles):
    """Generate plausible season-by-season breakdown for a career station."""
    if not started_at:
        return []
    today = date.today()
    end = ended_at or today

    def _season_start_year(d):
        return d.year if d.month >= 7 else d.year - 1

    start_yr = _season_start_year(started_at)
    end_yr = _season_start_year(end)
    num = max(1, end_yr - start_yr + 1)

    base = total_games // num
    leftover_g = total_games
    leftover_t = total_titles
    rows = []
    for i in range(num):
        yr = start_yr + i
        label = f'{yr}/{str(yr + 1)[-2:]}'
        if i == num - 1:
            g = leftover_g
            t = leftover_t
        else:
            g = max(0, base + (1 if i % 2 == 0 else -1))
            leftover_g -= g
            t = 1 if (leftover_t > 0 and i == num - 2) else 0
            leftover_t -= t
        w = round(g * 0.50)
        d = round(g * 0.24)
        l = g - w - d
        rows.append({'season': label, 'games': g, 'wins': w, 'draws': d, 'losses': l, 'titles': t})
    return rows


def _build_trainer_types_unlockable(club, trophies_count=None):
    if trophies_count is None:
        trophies_count = sum(t.count for t in club.public_trophies.all()) if club else 0
    return [
        {'key': 'aufstiegsheld', 'label': 'Aufstiegsheld', 'condition': '3 Aufstiege geschafft', 'progress': 0, 'max': 3, 'unlocked': False},
        {'key': 'defensivmeister', 'label': 'Defensivmeister', 'condition': 'Wenigste Gegentore der gesamten Simulation', 'progress': 0, 'max': 1, 'unlocked': False},
        {'key': 'weltenbummler', 'label': 'Weltenbummler', 'condition': '5 Vereine in 5 verschiedenen Ländern trainiert', 'progress': 1, 'max': 5, 'unlocked': False},
        {'key': 'serienmeister', 'label': 'Serienmeister', 'condition': 'Mehrere Meisterschaften in Folge', 'progress': trophies_count, 'max': 3, 'unlocked': trophies_count >= 3},
        {'key': 'feuerwehrmann', 'label': 'Feuerwehrmann', 'condition': 'Klassenerhalt auf Abstiegsplatz, max. 10 Spieltage Rest', 'progress': 0, 'max': 1, 'unlocked': False},
        {'key': 'vereinslegende', 'label': 'Vereinslegende', 'condition': '5 Saisons bei einem Verein', 'progress': 2, 'max': 5, 'unlocked': False},
    ]


SELECTABLE_TRAINER_TYPES = {
    'laptoptrainer': 'Laptoptrainer',
    'taktikfuchs': 'Taktikfuchs',
    'motivator': 'Motivator',
    'talentschmied': 'Talentschmied',
    'transferstratege': 'Transferstratege',
    'pokaljager': 'Pokaljäger',
    'offensivarchitekt': 'Offensivarchitekt',
    'underdog': 'Underdog-Flüsterer',
    'aufstiegsheld': 'Aufstiegsheld',
    'defensivmeister': 'Defensivmeister',
    'weltenbummler': 'Weltenbummler',
    'serienmeister': 'Serienmeister',
    'feuerwehrmann': 'Feuerwehrmann',
    'vereinslegende': 'Vereinslegende',
}

_ALWAYS_SELECTABLE_KEYS = {
    'laptoptrainer', 'taktikfuchs', 'motivator', 'talentschmied',
    'transferstratege', 'pokaljager', 'offensivarchitekt', 'underdog',
}


def _get_unlocked_achievement_keys():
    club = (
        Club.objects.filter(fm_inside_id=915).first()
        or Club.objects.filter(name__icontains='Bayern').first()
    )
    return {t['key'] for t in _build_trainer_types_unlockable(club) if t['unlocked']}


@login_required
def set_trainer_type(request):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    key = request.POST.get('trainer_type_key', '').strip()
    if key not in SELECTABLE_TRAINER_TYPES:
        from django.shortcuts import redirect
        return redirect('manager_profile')

    allowed = _ALWAYS_SELECTABLE_KEYS | _get_unlocked_achievement_keys()
    if key in allowed:
        from .models import ManagerProfile
        profile, _ = ManagerProfile.objects.get_or_create(
            user=request.user,
            defaults={'name': request.user.username},
        )
        profile.trainer_type = key
        profile.save(update_fields=['trainer_type', 'updated_at'])

    from django.shortcuts import redirect
    return redirect('manager_profile')


def save_career_station(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Nicht angemeldet'}, status=401)
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Keine Berechtigung'}, status=403)

    from .models import ManagerProfile, ManagerCareerStation

    profile, _ = ManagerProfile.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.username},
    )

    station_id = request.POST.get('station_id', '').strip()
    club_name = request.POST.get('club_name', '').strip()
    city_name = request.POST.get('city_name', '').strip()
    city_country = request.POST.get('city_country', '').strip()
    started_year = request.POST.get('started_year', '').strip()
    ended_year = request.POST.get('ended_year', '').strip()
    games_played = request.POST.get('games_played', '0').strip()
    map_x = request.POST.get('map_x', '271').strip()
    map_y = request.POST.get('map_y', '214').strip()

    if not club_name or not city_name:
        return JsonResponse({'ok': False, 'error': 'Verein und Stadt sind Pflichtfelder'}, status=400)

    try:
        started_at = date(int(started_year), 1, 1) if started_year else None
    except (ValueError, TypeError):
        started_at = None

    try:
        ended_at = date(int(ended_year), 12, 31) if ended_year else None
    except (ValueError, TypeError):
        ended_at = None

    try:
        games_played_int = max(0, int(games_played))
    except (ValueError, TypeError):
        games_played_int = 0

    try:
        map_x_int = max(0, min(500, int(map_x)))
        map_y_int = max(0, min(380, int(map_y)))
    except (ValueError, TypeError):
        map_x_int, map_y_int = 271, 214

    if station_id:
        try:
            station = ManagerCareerStation.objects.get(id=station_id, manager=profile)
        except ManagerCareerStation.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Station nicht gefunden'}, status=404)
        station.custom_club_name = club_name
        station.city_name = city_name
        station.city_country = city_country
        station.started_at = started_at
        station.ended_at = ended_at
        station.games_played = games_played_int
        station.map_x = map_x_int
        station.map_y = map_y_int
        station.save(update_fields=[
            'custom_club_name', 'city_name', 'city_country',
            'started_at', 'ended_at', 'games_played', 'map_x', 'map_y',
        ])
    else:
        max_order = (
            ManagerCareerStation.objects.filter(manager=profile)
            .aggregate(m=_db_models.Max('order'))['m'] or 0
        )
        station = ManagerCareerStation.objects.create(
            manager=profile,
            custom_club_name=club_name,
            city_name=city_name,
            city_country=city_country,
            started_at=started_at,
            ended_at=ended_at,
            games_played=games_played_int,
            map_x=map_x_int,
            map_y=map_y_int,
            order=max_order + 1,
        )

    return JsonResponse({'ok': True, 'id': station.id})


def delete_career_station(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Nicht angemeldet'}, status=401)
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Keine Berechtigung'}, status=403)

    from .models import ManagerProfile, ManagerCareerStation

    profile, _ = ManagerProfile.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.username},
    )

    station_id = request.POST.get('station_id', '').strip()
    if not station_id:
        return JsonResponse({'ok': False, 'error': 'ID fehlt'}, status=400)

    try:
        station = ManagerCareerStation.objects.get(id=station_id, manager=profile)
        station.delete()
    except ManagerCareerStation.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Station nicht gefunden'}, status=404)

    return JsonResponse({'ok': True})


@login_required
def upload_profile_image(request):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    file = request.FILES.get('image')
    if not file:
        return JsonResponse({'error': 'Keine Datei hochgeladen'}, status=400)

    allowed_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    if file.content_type not in allowed_types:
        return JsonResponse({'error': 'Ungültiges Format. Erlaubt: JPG, PNG, GIF, WebP'}, status=400)

    max_size = 5 * 1024 * 1024
    if file.size > max_size:
        return JsonResponse({'error': 'Datei zu groß. Maximum: 5 MB'}, status=400)

    ext_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif', 'image/webp': '.webp'}
    ext = ext_map.get(file.content_type, '.jpg')

    import uuid as _uuid
    from django.conf import settings as _settings
    from replit.object_storage import Client as _ObjClient

    version = _uuid.uuid4().hex[:12]
    rel_path = f'managers/{request.user.id}/avatar_{version}{ext}'

    data = b''.join(file.chunks())
    obj_client = _ObjClient()
    obj_client.upload_from_bytes(rel_path, data)

    from .models import ManagerProfile
    profile, _ = ManagerProfile.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.username},
    )

    old_path = profile.profile_image or ''
    if old_path and not old_path.startswith('game/'):
        try:
            obj_client.delete(old_path, ignore_not_found=True)
        except Exception:
            pass

    profile.profile_image = rel_path
    profile.save(update_fields=['profile_image'])

    image_url = request.build_absolute_uri(_settings.MEDIA_URL + rel_path)
    return JsonResponse({'url': image_url})


@login_required
def reset_profile_image(request):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    from .models import ManagerProfile
    from django.conf import settings as _settings
    from django.templatetags.static import static as _static

    try:
        profile = ManagerProfile.objects.get(user=request.user)
    except ManagerProfile.DoesNotExist:
        return JsonResponse({'ok': True})

    old_path = profile.profile_image or ''
    if old_path and not old_path.startswith('game/'):
        try:
            from replit.object_storage import Client as _ObjClient
            _ObjClient().delete(old_path, ignore_not_found=True)
        except Exception:
            pass

    profile.profile_image = ''
    profile.save(update_fields=['profile_image'])

    default_url = request.build_absolute_uri(
        _static('game/images/managers/kirschgutzje-test.png')
    )
    return JsonResponse({'ok': True, 'url': default_url})


def update_manager_profile(request):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    from django.shortcuts import redirect
    from django.http import JsonResponse
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not request.user.is_authenticated:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'not_authenticated'}, status=403)
        return redirect('manager_profile')

    from .models import ManagerProfile, COUNTRY_FLAG_ASSETS
    profile, _ = ManagerProfile.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.username},
    )

    new_name = request.POST.get('display_name', '').strip()
    nationality_name = request.POST.get('nationality_name', '').strip()

    update_fields = ['updated_at']

    if new_name and new_name != profile.name:
        import re
        from urllib.parse import urlencode
        from django.urls import reverse
        MIN_NAME_LENGTH = 2
        MAX_NAME_LENGTH = 100
        ALLOWED_NAME_RE = re.compile(r'^[\w\s\-\.\']+$', re.UNICODE)
        if len(new_name) < MIN_NAME_LENGTH or len(new_name) > MAX_NAME_LENGTH or not ALLOWED_NAME_RE.match(new_name):
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'name_invalid', 'attempted_name': new_name})
            params = urlencode({'name_invalid': '1', 'attempted_name': new_name})
            return redirect(f"{reverse('manager_profile')}?{params}")
        taken = ManagerProfile.objects.filter(name=new_name).exclude(pk=profile.pk).exists()
        if taken:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'name_taken', 'attempted_name': new_name})
            params = urlencode({'name_taken': '1', 'attempted_name': new_name})
            return redirect(f"{reverse('manager_profile')}?{params}")
        profile.name = new_name
        update_fields.append('name')

    if not profile.name_confirmed and profile.name != request.user.username:
        profile.name_confirmed = True
        update_fields.append('name_confirmed')

    if nationality_name and nationality_name in COUNTRY_FLAG_ASSETS:
        info = COUNTRY_FLAG_ASSETS[nationality_name]
        profile.nationality_name = nationality_name
        profile.nationality_flag = f'https://flagcdn.com/{info["code"].lower()}.svg'
        update_fields += ['nationality_name', 'nationality_flag']

    trainer_type_val = request.POST.get('trainer_type', '').strip()
    valid_types = dict(ManagerProfile.TRAINER_TYPE_CHOICES)
    if trainer_type_val and trainer_type_val in valid_types:
        profile.trainer_type = trainer_type_val
        update_fields.append('trainer_type')

    favourite_club_id = request.POST.get('favourite_club_id', '').strip()
    if favourite_club_id == '':
        profile.favourite_club_id = None
        update_fields.append('favourite_club')
    elif favourite_club_id:
        try:
            from .models import Club
            if Club.objects.filter(pk=int(favourite_club_id)).exists():
                profile.favourite_club_id = int(favourite_club_id)
                update_fields.append('favourite_club')
        except (ValueError, TypeError):
            pass

    profile.save(update_fields=list(set(update_fields)))

    if is_ajax:
        return JsonResponse({
            'ok': True,
            'name_confirmed': profile.name_confirmed,
            'display_name': profile.name,
            'trainer_type_label': profile.trainer_type_label,
            'flag_url': profile.nationality_flag,
            'flag_name': profile.nationality_name,
        })
    return redirect('manager_profile')


# ---------------------------------------------------------------------------
# Liga-Seite
# ---------------------------------------------------------------------------

def league_detail(request, league_id):
    """Vollständige Liga-Seite: Tabelle, Spieltag, News, Statistiken, Historie."""
    from .models import GameSeasonState

    league = get_object_or_404(
        League.objects.select_related('season_winner', 'cup_winner'),
        id=league_id,
    )

    try:
        season_state = GameSeasonState.objects.first()
        current_season_int = season_state.current_season if season_state else 0
    except Exception:
        current_season_int = 0

    current_season = str(current_season_int)
    if current_season_int == 0:
        season_display = 'Vorbereitung'
    else:
        season_display = f'Saison {current_season_int}'

    # ---- Tabelle ----------------------------------------------------------
    standings_qs = (
        LeagueStandings.objects
        .filter(league=league, season=current_season)
        .select_related('club')
        .order_by('position', '-points', 'club__name')
    )

    total_clubs = standings_qs.count()
    cl_limit = league.cl_spots
    el_limit = cl_limit + league.el_spots
    conf_limit = el_limit + league.conference_spots
    relegate_start = max(1, total_clubs - league.relegation_spots + 1)

    my_club = current_manager_club(request.user)

    table_rows = []
    for s in standings_qs:
        pos = s.position
        if pos <= cl_limit:
            zone = 'cl'
        elif pos <= el_limit:
            zone = 'el'
        elif pos <= conf_limit:
            zone = 'conf'
        elif total_clubs > 0 and pos >= relegate_start:
            zone = 'relegation'
        else:
            zone = ''

        form_items = list(s.form) if s.form else []

        is_winner = league.season_winner_id == s.club_id
        is_cup = league.cup_winner_id == s.club_id

        table_rows.append({
            'standing': s,
            'zone': zone,
            'form_items': form_items,
            'is_current_club': bool(my_club and my_club.id == s.club_id),
            'is_winner': is_winner,
            'is_cup': is_cup,
        })

    # ---- Spieltag ---------------------------------------------------------
    last_matchday_num = (
        SeasonFixture.objects
        .filter(league=league, season=current_season, is_played=True)
        .order_by('-matchday')
        .values_list('matchday', flat=True)
        .first()
    )
    next_matchday_num = (
        SeasonFixture.objects
        .filter(league=league, season=current_season, is_played=False)
        .order_by('matchday')
        .values_list('matchday', flat=True)
        .first()
    )

    last_fixtures = list(
        SeasonFixture.objects
        .filter(league=league, season=current_season, matchday=last_matchday_num)
        .select_related('home_club', 'away_club')
        .order_by('scheduled_date', 'scheduled_time')
    ) if last_matchday_num is not None else []

    next_fixtures = list(
        SeasonFixture.objects
        .filter(league=league, season=current_season, matchday=next_matchday_num)
        .select_related('home_club', 'away_club')
        .order_by('scheduled_date', 'scheduled_time')
    ) if next_matchday_num is not None else []

    # ---- News -------------------------------------------------------------
    liga_news = list(LeagueNews.objects.filter(league=league).order_by('-published_at', '-id')[:6])

    # ---- Aktiver Tab ------------------------------------------------------
    active_tab = request.GET.get('tab', 'tabelle')

    # ---- Spielplan (alle Spieltage) ---------------------------------------
    spielplan_matchdays = []
    if active_tab == 'spielplan':
        all_fixtures = list(
            SeasonFixture.objects
            .filter(league=league, season=current_season)
            .select_related('home_club', 'away_club')
            .order_by('matchday', 'scheduled_date', 'scheduled_time')
        )
        my_club_id = my_club.id if my_club else None
        matchday_map = {}
        for f in all_fixtures:
            md = f.matchday
            if md not in matchday_map:
                matchday_map[md] = []
            matchday_map[md].append(f)
        _de_months = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']

        def _fmt_date_range(fixtures):
            dates = [fx.scheduled_date for fx in fixtures if fx.scheduled_date]
            if not dates:
                return ''
            lo, hi = min(dates), max(dates)
            lo_mon = _de_months[lo.month - 1]
            hi_mon = _de_months[hi.month - 1]
            if lo == hi:
                return f'{lo.day}. {lo_mon}'
            if lo.month == hi.month:
                return f'{lo.day}.–{hi.day}. {hi_mon}'
            return f'{lo.day}. {lo_mon} – {hi.day}. {hi_mon}'

        for md_num in sorted(matchday_map.keys()):
            fixtures_list = matchday_map[md_num]
            is_upcoming = any(not fx.is_played for fx in fixtures_list)
            is_current = (
                next_matchday_num is not None and md_num == next_matchday_num
            )
            spielplan_matchdays.append({
                'matchday_num': md_num,
                'fixtures': fixtures_list,
                'is_upcoming': is_upcoming,
                'is_current': is_current,
                'date_range': _fmt_date_range(fixtures_list),
            })

    # ---- Bundesliga-Logo --------------------------------------------------
    logo_path = league.logo_static_path
    if not logo_path:
        slug = league.name.lower().replace(' ', '-').replace('.', '')
        logo_path = f'game/images/competitions/{slug}.svg'

    return render(request, 'game/liga/league_detail.html', {
        'league': league,
        'table_rows': table_rows,
        'cl_limit': cl_limit,
        'el_limit': el_limit,
        'conf_limit': conf_limit,
        'relegate_start': relegate_start,
        'total_clubs': total_clubs,
        'last_matchday_num': last_matchday_num,
        'next_matchday_num': next_matchday_num,
        'last_fixtures': last_fixtures,
        'next_fixtures': next_fixtures,
        'liga_news': liga_news,
        'active_tab': active_tab,
        'current_season': current_season,
        'season_display': season_display,
        'league_logo_path': logo_path,
        'spielplan_matchdays': spielplan_matchdays,
        'my_club_id': my_club.id if my_club else None,
        'game_header': build_game_header(
            league.name,
            season_display,
            '/',
        ),
    })
