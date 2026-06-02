import json
import os
from datetime import date, timedelta
from django.db import models as _db_models
from itertools import product

from django.contrib import messages
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
    DataSource,
    League,
    MatchResult,
    Player,
    PlayerAwardTitle,
    PlayerInjuryRecord,
    PlayerSeasonStat,
    PlayerSourceRating,
    PlayerSuspensionRecord,
    PlayerTransferHistory,
    TacticSetup,
    TacticTemplate,
)
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


# Thin-plate-spline calibration of europe-night.png (1536x1024). The background
# is a perspective ("tilted globe") satellite render, NOT a flat map projection,
# so a single linear/affine or even Mercator formula drifts badly (south-German
# cities ended up too far north, Barcelona over the Pyrenees in France). The TPS
# below was fitted against hand-verified light-cluster pixels of 10 well-spread,
# unambiguous cities (clear starbursts + coastal clusters). It interpolates those
# anchors exactly and warps smoothly between them. To re-calibrate, re-pin the
# anchor pixels and re-solve the TPS (see .agents/memory/europe-night-calibration.md).
_MAP_TPS_ANCHORS = (
    (-3.70, 40.42), (2.17, 41.39), (-9.14, 38.72), (-8.61, 41.15), (2.35, 48.85),
    (-0.13, 51.51), (4.90, 52.37), (4.84, 45.76), (9.19, 45.46), (12.50, 41.90),
)
# weights[0..n-1] = radial-basis weights; weights[n..n+2] = affine [c, x, y]
_MAP_TPS_WX = (
    -0.544691, 0.774326, 0.989405, -1.000482, -0.953162, 0.627053, -0.054187,
    -0.055979, 0.945682, -0.727964, 263.200195, 16.330017, 5.171957,
)
_MAP_TPS_WY = (
    0.561837, -0.446532, 0.362923, -0.633604, 0.361124, -0.043918, -0.065806,
    -0.361087, 0.358906, -0.093843, 1949.379942, 2.580988, -28.943117,
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
    'augsburg': (45.44, 59.47),
    'berlin': (49.09, 49.02),
    'bochum': (41.80, 49.71),
    'bremen': (44.21, 45.99),
    'dortmund': (42.06, 49.80),
    'frankfurt am main': (43.36, 54.00), 'frankfurt': (43.36, 54.00),
    'freiburg im breisgau': (42.12, 59.18), 'freiburg': (42.12, 59.18),
    'hamburg': (45.64, 45.02),
    'heidenheim an der brenz': (44.86, 58.20), 'heidenheim': (44.86, 58.20),
    'kiel': (46.09, 42.97),
    'leipzig': (47.59, 51.76),
    'leverkusen': (41.34, 50.88),
    'mainz': (42.84, 54.10),
    'mönchengladbach': (40.56, 50.29), 'monchengladbach': (40.56, 50.29),
    'gladbach': (40.56, 50.29),
    'münchen': (45.96, 59.86), 'munchen': (45.96, 59.86), 'munich': (45.96, 59.86),
    'sinsheim': (43.55, 56.35),
    'stuttgart': (43.88, 57.62),
    'wolfsburg': (46.29, 48.34),
    # --- Spain / Portugal (verified against europe-night.png light clusters) ---
    'madrid': (22.14, 78.32),
    'barcelona': (32.88, 74.22),
    'valencia': (28.13, 80.33),
    'sevilla': (19.54, 86.83), 'seville': (19.54, 86.83),
    'bilbao': (24.01, 69.52),
    'san sebastián': (25.73, 69.34), 'san sebastian': (25.73, 69.34),
    'vigo': (15.13, 70.32),
    'zaragoza': (27.54, 74.04),
    'villarreal': (28.75, 78.83),
    'málaga': (21.59, 89.02), 'malaga': (21.59, 89.02),
    'lisboa': (15.89, 81.74), 'lissabon': (15.89, 81.74), 'lisbon': (15.89, 81.74),
    'porto': (15.30, 73.73),
    # --- France / Monaco ---
    'paris': (33.53, 55.37),
    'marseille': (37.88, 69.57),
    'lyon': (37.37, 63.18),
    'lille': (35.43, 50.83),
    'bordeaux': (28.52, 65.00),
    'nice': (40.30, 69.55), 'nizza': (40.30, 69.55),
    'monaco': (40.48, 69.54),
    'nantes': (27.54, 58.50),
    'toulouse': (32.03, 68.11),
    'saint-étienne': (36.66, 63.82), 'saint-etienne': (36.66, 63.82),
    # --- England / Scotland / Ireland ---
    'london': (31.97, 47.36),
    'manchester': (29.99, 41.11),
    'liverpool': (28.86, 41.01),
    'birmingham': (30.01, 43.99),
    'newcastle': (31.55, 37.18),
    'leeds': (31.13, 40.48),
    'glasgow': (28.21, 33.72),
    'edinburgh': (29.76, 33.88),
    'dublin': (24.02, 39.90),
    # --- Netherlands / Belgium ---
    'amsterdam': (38.80, 46.58),
    'rotterdam': (38.04, 47.69),
    'eindhoven': (39.27, 49.28),
    'brussel': (37.40, 50.56), 'brüssel': (37.40, 50.56), 'brussels': (37.40, 50.56),
    'antwerpen': (37.62, 49.57), 'antwerp': (37.62, 49.57),
    'brügge': (35.96, 49.30), 'bruges': (35.96, 49.30),
    # --- Italy (hand-pinned: the TPS formula drifts ~4-5% E of the Rome
    # anchor, putting Rome on Corsica and Naples on Sardinia) ---
    'roma': (47.10, 78.10), 'rom': (47.10, 78.10), 'rome': (47.10, 78.10),
    'napoli': (49.00, 80.40), 'neapel': (49.00, 80.40), 'naples': (49.00, 80.40),
    'milano': (43.40, 66.00), 'mailand': (43.40, 66.00), 'milan': (43.40, 66.00),
    'torino': (41.00, 65.90), 'turin': (41.00, 65.90),
    'genova': (42.00, 69.20), 'genua': (42.00, 69.20), 'genoa': (42.00, 69.20),
    'venezia': (46.00, 67.50), 'venedig': (46.00, 67.50), 'venice': (46.00, 67.50),
    'firenze': (44.00, 71.20), 'florenz': (44.00, 71.20), 'florence': (44.00, 71.20),
    'bologna': (44.60, 69.00),
    # --- Switzerland ---
    'zürich': (42.93, 61.08), 'zurich': (42.93, 61.08),
    'basel': (41.70, 60.13),
    'bern': (41.45, 61.60),
    'genf': (39.43, 62.74), 'genève': (39.43, 62.74), 'geneva': (39.43, 62.74),
    # --- Scandinavia (verified via Øresund / fjord / archipelago coastlines) ---
    'kopenhagen': (49.00, 39.60), 'copenhagen': (49.00, 39.60), 'københavn': (49.00, 39.60),
    'oslo': (48.30, 25.50),
    'stockholm': (54.30, 26.50),
    'göteborg': (49.00, 34.00), 'goteborg': (49.00, 34.00), 'gothenburg': (49.00, 34.00),
    # --- Balkans (hand-pinned; the TPS formula drifts these into the
    # Adriatic, e.g. Belgrade landed offshore) ---
    'zagreb': (49.00, 65.50),
    'belgrad': (52.50, 69.00), 'belgrade': (52.50, 69.00), 'beograd': (52.50, 69.00),
}


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
    'palermo': (284, 274),
    'genova': (257, 230), 'genoa': (257, 230),
    'bari': (308, 258),
    'catania': (290, 278),
    'verona': (272, 222),
    'bergamo': (264, 220),
    'brescia': (268, 222),
    'lecce': (316, 264),
    'parma': (268, 228),
    'reggio calabria': (294, 272),
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


def current_manager_club():
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


def build_game_header(
    title,
    subtitle,
    back_url='/',
    current_club=None,
    opponent_club=None,
    calendar_offset=0,
):
    base_game_date = date(2026, 5, 15)
    game_date = base_game_date + timedelta(days=calendar_offset)
    weekday_labels = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    opponent_name = opponent_club.short_name if opponent_club else 'Gegner'
    opponent_crest = opponent_club.crest_static_path if opponent_club else ''
    opponent_url = reverse_club_detail(opponent_club) if opponent_club else ''
    league_name = (
        current_club.league.name
        if current_club and current_club.league
        else '1. Bundesliga'
    )

    def fixture_entry(lineup_saved, result, venue, meta, match_time=''):
        home_club = current_club if venue == 'H' else opponent_club
        return {
            'opponent_name': opponent_name,
            'opponent_crest': opponent_crest,
            'opponent_url': opponent_url,
            'stadium': stadium_static_path(home_club),
            'competition_logo': competition_logo_static_path(league_name),
            'lineup_saved': lineup_saved,
            'result': result,
            'venue': venue,
            'meta': meta,
            'match_time': match_time,
        }

    fixtures_by_date = {
        base_game_date - timedelta(days=3): fixture_entry(False, '1:1', 'A', '33. Spieltag (A)'),
        base_game_date - timedelta(days=1): fixture_entry(True, '5:0', 'H', 'Testspiel (H)'),
        base_game_date + timedelta(days=2): fixture_entry(False, '', 'H', '27. Spieltag (H)', match_time='18:00'),
    }

    calendar_days = []
    for offset in range(-3, 4):
        day = game_date + timedelta(days=offset)
        fixture = fixtures_by_date.get(day)
        calendar_days.append({
            'date': day,
            'weekday': weekday_labels[day.weekday()],
            'day_number': day.day,
            'is_today': day == base_game_date,
            'fixture': fixture,
        })

    return {
        'title': title,
        'subtitle': subtitle,
        'back_url': back_url,
        'game_date': game_date,
        'previous_calendar_offset': calendar_offset - 1,
        'next_calendar_offset': calendar_offset + 1,
        'calendar_days': calendar_days,
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


def home(request):
    clubs = Club.objects.select_related('league').annotate(
        player_count=Count('player'),
        average_strength=Avg('player__strength_profile__final_strength'),
    )
    richest_clubs = clubs.order_by('-budget')[:6]
    primary_club = current_manager_club() or clubs.order_by('-budget').first()
    secondary_club = (
        clubs.exclude(id=primary_club.id).order_by('-budget').first()
        if primary_club
        else None
    )

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
    primary_top_scorer = primary_players.order_by(
        '-strength_profile__final_strength',
        '-market_value',
        'last_name',
        'first_name',
    ).first()
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
            f'{primary_top_scorer.last_name} (18)'
        )
        top_scorer_portrait = primary_top_scorer.portrait_static_path
    else:
        top_scorer_label = 'L. Martinez (18)'
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
        'fan_percent': 86,
        'form': [
            {'label': 'S', 'tone': 'win'},
            {'label': 'S', 'tone': 'win'},
            {'label': 'U', 'tone': 'draw'},
            {'label': 'S', 'tone': 'win'},
            {'label': 'N', 'tone': 'loss'},
        ],
    }

    table_clubs = []
    seen_ids = set()
    for club in [primary_club, secondary_club]:
        if club and club.id not in seen_ids:
            table_clubs.append(club)
            seen_ids.add(club.id)
    for club in clubs.order_by('-budget'):
        if len(table_clubs) >= 5:
            break
        if club.id in seen_ids:
            continue
        table_clubs.append(club)
        seen_ids.add(club.id)

    fallback_table = [
        ('FC Novum', 'FC Novum', 78, '68:29', '+39'),
        ('FC Aurora', 'FC Aurora', 72, '61:28', '+33'),
        ('FC Helios', 'FC Helios', 64, '57:32', '+25'),
        ('SV Fortuna', 'SV Fortuna', 55, '49:37', '+12'),
        ('SC Meridian', 'SC Meridian', 53, '46:40', '+6'),
    ]
    table_points = [78, 72, 64, 55, 53]
    table_goals = ['68:29', '61:28', '57:32', '49:37', '46:40']
    table_diff = ['+39', '+33', '+25', '+12', '+6']
    overview_league_table = []
    for index in range(5):
        club = table_clubs[index] if index < len(table_clubs) else None
        fallback = fallback_table[index]
        overview_league_table.append({
            'position': index + 1,
            'club_name': club.name if club else fallback[0],
            'short_name': club.short_name if club else fallback[1],
            'crest_static_path': club.crest_static_path if club else '',
            'club_url': f'/clubs/{club.id}/' if club else '',
            'played': 33,
            'goals': table_goals[index],
            'goal_difference': table_diff[index],
            'points': table_points[index],
            'is_current_club': bool(primary_club and club and club.id == primary_club.id),
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

    club_news_player = top_strength_player.last_name if top_strength_player else 'Martinez'
    club_news = [
        {'title': f'{club_news_player} zum Spieler des Monats gekuert', 'when': 'Heute'},
        {'title': 'Vertragsverhandlungen mit Kaya gestartet', 'when': 'Gestern'},
        {'title': 'FC Novum erreicht Gewinn im letzten Quartal', 'when': '22. Mai'},
    ]
    sim_news = [
        {'title': 'Martinez zum Spieler des Monats gekuert', 'when': 'Heute'},
        {'title': 'Vertragsverhandlungen mit Kaya gestartet', 'when': 'Gestern'},
        {'title': 'FC Novum erreicht Gewinn im letzten Quartal', 'when': '22. Mai'},
    ]
    home_stadium_static_path = stadium_static_path(primary_club)
    last_match_home_stadium_static_path = stadium_static_path(primary_club)
    competition_logo_static_path_value = competition_logo_static_path(
        primary_club.league.name
        if primary_club and primary_club.league
        else '1. Bundesliga'
    )

    return render(
        request,
        'game/home.html',
        {
            'richest_clubs': richest_clubs,
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
            'active_managers': [
                {
                    'name': 'bojankrkic',
                    'crest': primary_club.crest_static_path if primary_club else '',
                    'club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                },
                {
                    'name': 'husteguz92',
                    'crest': secondary_club.crest_static_path if secondary_club else '',
                    'club_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                },
                {
                    'name': 'Doppel_Loewen Power',
                    'crest': primary_club.crest_static_path if primary_club else '',
                    'club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                },
                {
                    'name': 'FootballMaster2017',
                    'crest': secondary_club.crest_static_path if secondary_club else '',
                    'club_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                },
                {
                    'name': 'Fohlenmeister',
                    'crest': primary_club.crest_static_path if primary_club else '',
                    'club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                },
                {
                    'name': 'Ilundehund',
                    'crest': secondary_club.crest_static_path if secondary_club else '',
                    'club_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                },
                {
                    'name': 'Schae',
                    'crest': primary_club.crest_static_path if primary_club else '',
                    'club_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                },
                {
                    'name': 'Beppi',
                    'crest': secondary_club.crest_static_path if secondary_club else '',
                    'club_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                },
            ],
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
            'last_match_scorers': [
                {'name': 'Martinez', 'minute': 23},
                {'name': 'Petrov', 'minute': 58},
                {'name': 'Kaya', 'minute': 67},
            ],
            'live_matches': [
                {
                    'time': '20:40',
                    'home': primary_club.short_name if primary_club else 'ASK',
                    'away': secondary_club.short_name if secondary_club else 'FOR',
                    'home_crest': primary_club.crest_static_path if primary_club else '',
                    'away_crest': secondary_club.crest_static_path if secondary_club else '',
                    'home_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'away_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '21:20',
                    'home': secondary_club.short_name if secondary_club else 'SER',
                    'away': 'KAS',
                    'home_crest': secondary_club.crest_static_path if secondary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '22:20',
                    'home': primary_club.short_name if primary_club else 'LIV',
                    'away': 'RMA',
                    'home_crest': primary_club.crest_static_path if primary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '22:45',
                    'home': secondary_club.short_name if secondary_club else 'SER',
                    'away': primary_club.short_name if primary_club else 'ASK',
                    'home_crest': secondary_club.crest_static_path if secondary_club else '',
                    'away_crest': primary_club.crest_static_path if primary_club else '',
                    'home_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'away_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '23:05',
                    'home': primary_club.short_name if primary_club else 'LIV',
                    'away': 'ROM',
                    'home_crest': primary_club.crest_static_path if primary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '23:30',
                    'home': secondary_club.short_name if secondary_club else 'BVB',
                    'away': 'S04',
                    'home_crest': secondary_club.crest_static_path if secondary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '00:10',
                    'home': primary_club.short_name if primary_club else 'FCB',
                    'away': 'SGE',
                    'home_crest': primary_club.crest_static_path if primary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{primary_club.id}/' if primary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
                {
                    'time': '00:35',
                    'home': secondary_club.short_name if secondary_club else 'BVB',
                    'away': 'SVW',
                    'home_crest': secondary_club.crest_static_path if secondary_club else '',
                    'away_crest': '',
                    'home_url': f'/clubs/{secondary_club.id}/' if secondary_club else '',
                    'away_url': '',
                    'competition_logo': competition_logo_static_path_value,
                },
            ],
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
                primary_club,
                secondary_club,
                calendar_offset_from_request(request),
            ),
        }
    )


def club_list(request):
    clubs = Club.objects.select_related('league').annotate(
        player_count=Count('player'),
        average_strength=Avg('player__strength_profile__final_strength'),
    )
    manager_club = current_manager_club()
    header_club = manager_club or clubs.first()
    header_opponent = (
        clubs.exclude(id=header_club.id).order_by('-budget').first()
        if header_club
        else None
    )

    return render(
        request,
        'game/club_list.html',
        {
            'clubs': clubs,
            'game_header': build_game_header(
                'Vereinsübersicht',
                'Scoutingzentrale · Datenbank',
                '/',
                header_club,
                header_opponent,
                calendar_offset_from_request(request),
            ),
        }
    )


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


def form_rows_with_opponents(rows, team_club):
    candidates = list(
        Club.objects.filter(fm_inside_id__isnull=False)
        .exclude(id=getattr(team_club, 'id', None))
        .order_by('name', 'id')[:5]
    )
    if not candidates and team_club and team_club.fm_inside_id:
        candidates = [team_club]

    result = []
    for index, row in enumerate(rows):
        opponent = candidates[index % len(candidates)] if candidates else None
        result.append({
            **row,
            'opponent_name': opponent.name if opponent else 'Gegner',
            'opponent_crest': opponent.crest_static_path if opponent else '',
            'opponent_url': reverse_club_detail(opponent) if opponent else '#',
        })
    return result


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
    duel_home_club = current_manager_club() or club
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
        'home_form': form_rows_with_opponents(RESULT_FORM, club),
        'away_form': form_rows_with_opponents(OPPONENT_RESULT_FORM, opponent_club or club),
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
            club,
            opponent_club,
            calendar_offset_from_request(request),
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
        club,
        opponent_club,
        calendar_offset_from_request(request),
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
        messages.success(request, 'Taktik bestätigt und gespeichert.')
        return redirect(tactic_redirect_url(club, squad_scope, confirmed=1))

    context = build_tactics_context(request, club, setup, squad_scope)
    return render(request, 'game/tactics.html', context)


_SQUAD_POSITION_GROUP = {
    'TW': 0,
    'IV': 1, 'LV': 1, 'RV': 1, 'LI': 1, 'LOV': 1, 'ROV': 1,
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


def _build_squad_context(request, club, squad_title):
    is_youth = squad_title == 'Jugendkader'
    qs = Player.objects.filter(club=club).select_related('strength_profile')
    if is_youth:
        qs = qs.filter(age__lte=21)
    players = _sorted_squad(qs)
    total_squad_value = sum(p.market_value for p in players if p.market_value)
    opponent_club = Club.objects.exclude(id=club.id).order_by('name').first()
    return {
        'club': club,
        'players': players,
        'player_count': len(players),
        'total_squad_value': total_squad_value,
        'squad_title': squad_title,
        'game_header': build_game_header(
            squad_title,
            club.name,
            reverse_club_detail(club),
            club,
            opponent_club,
            calendar_offset_from_request(request),
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


def club_table(request, club_id):
    return render_public_club_stub(
        request,
        club_id,
        'Ligatabelle',
        'Die komplette öffentliche Tabelle wird als eigener Bereich vorbereitet.',
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
                club,
                opponent_club,
                calendar_offset_from_request(request),
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
                player.club,
                (
                    Club.objects.exclude(id=player.club.id).order_by('name').first()
                    if player.club
                    else None
                ),
                calendar_offset_from_request(request),
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


def manager_profile(request):
    tab = request.GET.get('tab', 'profil')

    club = (
        Club.objects.filter(fm_inside_id=915).first()
        or Club.objects.filter(name__icontains='Bayern').first()
    )

    club_profile = None
    if club:
        try:
            club_profile = club.public_profile
        except ClubPublicProfile.DoesNotExist:
            club_profile = None

    club_name = club.name if club else 'FC Bayern München'
    club_crest = club.crest_static_path if club else 'game/images/crests/915.png'
    club_url = f'/clubs/{club.id}/' if club else '/clubs/2/'

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
    else:
        # Fallback: single station from ClubPublicProfile
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
        profile_image_url = _static(_raw_image or 'game/images/managers/kirschgutzje-test.png')

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
    else:
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
            club,
            None,
            calendar_offset_from_request(request),
        ),
        'trainer_types_selectable': trainer_types_selectable,
        'trainer_types_unlockable': trainer_types_unlockable,
        'map_stations': map_stations,
        'photo_map_markers': photo_map_markers,
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
            'club_since': '15. Aug. 2023',
            'club_season': '3. Saison',
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
            'period': '15. Aug. 2023 – heute',
            'url': club_url,
            'time_label': '2 Jahre, 9 Monate',
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
        'can_edit_profile': request.user.is_authenticated,
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

    from django.conf import settings as _settings
    rel_path = f'managers/{request.user.id}/avatar{ext}'
    save_path = os.path.join(_settings.MEDIA_ROOT, rel_path)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    with open(save_path, 'wb+') as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    from .models import ManagerProfile
    profile, _ = ManagerProfile.objects.get_or_create(
        user=request.user,
        defaults={'name': request.user.username},
    )
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
        full_path = os.path.join(_settings.MEDIA_ROOT, old_path)
        if os.path.isfile(full_path):
            try:
                os.remove(full_path)
            except OSError:
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
