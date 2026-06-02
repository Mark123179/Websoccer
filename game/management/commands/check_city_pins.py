"""
check_city_pins: One-time geographic sanity check for the CITY_MAP_PCT table.

Checks every hand-verified city pin in game/views.py for:
  1. Range validity  — x ∈ [0,100] and y ∈ [0,100]
  2. TPS back-projection — numerically inverts the TPS transform to recover
     (lng, lat) and compares it against a known reference coordinate.
     Pins where the back-projected position differs >5° from the real city
     are flagged as warnings; those that cannot be inverted at all are errors.
  3. European bounds — back-projected lat/lng must land inside a generous
     Europe bounding box (lat 34–72, lng -15–42); pins outside are errors.
  4. Coverage enforcement — every canonical (unique-coordinate) key must have
     a reference lat/lng entry; missing coverage is reported as an error so
     the test cannot silently degrade when new cities are added.

Exit code 0 = clean; exit code 1 = at least one critical error found.
"""

import math
import sys

from django.core.management.base import BaseCommand

from game.views import (
    CITY_MAP_PCT,
    _MAP_IMG_H,
    _MAP_IMG_W,
    _MAP_TPS_ANCHORS,
    _MAP_TPS_WX,
    _MAP_TPS_WY,
    _tps_eval,
)

# ---------------------------------------------------------------------------
# Known real-world (lat, lng) for every canonical key in CITY_MAP_PCT.
# "Canonical" means the first key seen for a given (x, y) coordinate pair
# (alias keys such as 'munich' that share coords with 'münchen' are skipped).
# If a new city is added to CITY_MAP_PCT without a matching entry here the
# command will fail with a coverage-error, prompting the author to add one.
# ---------------------------------------------------------------------------
_CITY_REF_LATLNG = {
    # Germany
    'augsburg':              (48.37,  10.90),
    'berlin':                (52.52,  13.40),
    'bochum':                (51.48,   7.22),
    'bremen':                (53.08,   8.80),
    'dortmund':              (51.51,   7.47),
    'frankfurt am main':     (50.11,   8.68),
    'freiburg im breisgau':  (47.99,   7.84),
    'hamburg':               (53.55,   9.99),
    'heidenheim an der brenz': (48.68, 10.15),
    'kiel':                  (54.32,  10.13),
    'leipzig':               (51.34,  12.37),
    'leverkusen':            (51.03,   6.98),
    'mainz':                 (49.99,   8.27),
    'mönchengladbach':       (51.20,   6.44),
    'münchen':               (48.14,  11.58),
    'sinsheim':              (49.25,   8.88),
    'stuttgart':             (48.78,   9.18),
    'wolfsburg':             (52.42,  10.79),
    # Spain / Portugal
    'madrid':                (40.42,  -3.70),
    'barcelona':             (41.39,   2.17),
    'valencia':              (39.47,  -0.38),
    'sevilla':               (37.39,  -5.99),
    'bilbao':                (43.26,  -2.93),
    'san sebastián':         (43.32,  -1.98),
    'vigo':                  (42.23,  -8.72),
    'zaragoza':              (41.65,  -0.88),
    'villarreal':            (39.94,  -0.10),
    'málaga':                (36.72,  -4.42),
    'lisboa':                (38.72,  -9.14),
    'porto':                 (41.15,  -8.61),
    # France / Monaco
    'paris':                 (48.85,   2.35),
    'marseille':             (43.30,   5.37),
    'lyon':                  (45.75,   4.84),
    'lille':                 (50.63,   3.07),
    'bordeaux':              (44.84,  -0.58),
    'nice':                  (43.71,   7.26),
    'monaco':                (43.74,   7.43),
    'nantes':                (47.22,  -1.55),
    'toulouse':              (43.60,   1.44),
    'saint-étienne':         (45.44,   4.39),
    'rennes':                (48.11,  -1.68),
    'strasbourg':            (48.58,   7.75),
    'lens':                  (50.43,   2.83),
    'le havre':              (49.49,   0.11),
    'montpellier':           (43.61,   3.88),
    'reims':                 (49.26,   4.03),
    'clermont-ferrand':      (45.78,   3.08),
    # England / Scotland / Ireland
    'london':                (51.51,  -0.13),
    'manchester':            (53.48,  -2.24),
    'liverpool':             (53.41,  -2.98),
    'birmingham':            (52.48,  -1.90),
    'newcastle':             (54.97,  -1.61),
    'leeds':                 (53.80,  -1.55),
    'glasgow':               (55.86,  -4.25),
    'edinburgh':             (55.95,  -3.19),
    'dublin':                (53.33,  -6.25),
    'southampton':           (50.91,  -1.40),
    'sheffield':             (53.38,  -1.47),
    'ipswich':               (52.06,   1.16),
    'blackburn':             (53.75,  -2.48),
    'sunderland':            (54.91,  -1.38),
    'middlesbrough':         (54.57,  -1.23),
    'cardiff':               (51.48,  -3.18),
    'reading':               (51.46,  -0.97),
    'brighton':              (50.83,  -0.14),
    'norwich':               (52.63,   1.30),
    'coventry':              (52.41,  -1.51),
    'hull':                  (53.75,  -0.34),
    'nottingham':            (52.95,  -1.15),
    'leicester':             (52.64,  -1.13),
    'stoke-on-trent':        (53.00,  -2.18),
    'wolverhampton':         (52.59,  -2.13),
    'swansea':               (51.62,  -3.94),
    'plymouth':              (50.37,  -4.14),
    'burnley':               (53.79,  -2.24),
    'oxford':                (51.75,  -1.26),
    # Netherlands / Belgium
    'amsterdam':             (52.37,   4.90),
    'rotterdam':             (51.93,   4.47),
    'eindhoven':             (51.44,   5.48),
    'brussel':               (50.85,   4.35),
    'antwerpen':             (51.22,   4.40),
    'brügge':                (51.21,   3.22),
    'utrecht':               (52.09,   5.12),
    'alkmaar':               (52.63,   4.75),
    'arnhem':                (51.98,   5.91),
    'heerenveen':            (52.96,   5.92),
    'groningen':             (53.22,   6.57),
    'tilburg':               (51.56,   5.09),
    'charleroi':             (50.41,   4.44),
    'gent':                  (51.05,   3.72),
    'liège':                 (50.63,   5.58),
    # Switzerland
    'zürich':                (47.38,   8.55),
    'basel':                 (47.56,   7.59),
    'bern':                  (46.95,   7.45),
    'genf':                  (46.20,   6.14),
    'lausanne':              (46.52,   6.63),
    'lugano':                (46.00,   8.95),
    'luzern':                (47.05,   8.31),
    'st. gallen':            (47.42,   9.37),
    'winterthur':            (47.50,   8.72),
    'sion':                  (46.23,   7.36),
    # Scandinavia
    'kopenhagen':            (55.68,  12.57),
    'oslo':                  (59.91,  10.75),
    'stockholm':             (59.33,  18.07),
    'göteborg':              (57.71,  11.97),
    'malmö':                 (55.61,  13.00),
    'helsingborg':           (56.05,  12.69),
    'norrköping':            (58.59,  16.18),
    'trondheim':             (63.43,  10.39),
    'bergen':                (60.39,   5.33),
    'fredrikstad':           (59.21,  10.93),
    'aalesund':              (62.47,   6.15),
    'molde':                 (62.74,   7.16),
    'odense':                (55.40,  10.39),
    'randers':               (56.46,  10.04),
    'aarhus':                (56.15,  10.22),
    'silkeborg':             (56.17,   9.55),
    'esbjerg':               (55.48,   8.46),
    'horsens':               (55.86,   9.85),
    'vejle':                 (55.71,   9.54),
    'viborg':                (56.45,   9.40),
    'kolding':               (55.49,   9.47),
    # Italy
    'roma':                  (41.90,  12.50),
    'napoli':                (40.84,  14.25),
    'milano':                (45.46,   9.19),
    'torino':                (45.07,   7.69),
    'genova':                (44.41,   8.93),
    'venezia':               (45.44,  12.33),
    'firenze':               (43.77,  11.26),
    'bologna':               (44.50,  11.34),
    'parma':                 (44.80,  10.33),
    'cagliari':              (39.23,   9.11),
    'como':                  (45.81,   9.09),
    'empoli':                (43.72,  10.95),
    'frosinone':             (41.64,  13.35),
    'lecce':                 (40.35,  18.17),
    'udinese':               (46.07,  13.23),
    'bari':                  (41.12,  16.87),
    'palermo':               (38.12,  13.36),
    'catania':               (37.50,  15.09),
    'reggio calabria':       (38.11,  15.65),
    # Italy — additional entries (club names / smaller cities)
    'atalanta':              (45.69,   9.67),   # Bergamo
    'hellas verona':         (45.44,  11.00),
    'monza':                 (45.58,   9.27),
    'salernitana':           (40.68,  14.76),   # Salerno
    'sassuolo':              (44.54,  10.79),
    # Balkans
    'zagreb':                (45.81,  15.98),
    'belgrad':               (44.80,  20.47),
    'hajduk split':          (43.51,  16.44),
    'rijeka':                (45.33,  14.45),
    'osijek':                (45.55,  18.69),
    'varazdin':              (46.31,  16.34),
    'šibenik':               (43.73,  15.89),
    'gorica':                (45.96,  13.62),   # Nova Gorica
    # England — additional entries
    'brentford':             (51.49,  -0.31),
    'burton upon trent':     (52.81,  -1.64),
    'barnsley':              (53.55,  -1.48),
    'luton':                 (51.88,  -0.42),
    'portsmouth':            (50.80,  -1.09),
    'rotherham':             (53.43,  -1.36),
    'watford':               (51.65,  -0.40),
    'wigan':                 (53.54,  -2.63),
    # Netherlands / Belgium — additional entries
    'almere':                (52.37,   5.22),
    'breda':                 (51.59,   4.78),
    'deventer':              (52.25,   6.16),
    'dordrecht':             (51.81,   4.67),
    'emmen':                 (52.79,   6.90),
    'kortrijk':              (50.82,   3.26),
    'mechelen':              (51.03,   4.48),
    'oud-heverlee leuven':   (50.88,   4.70),
    'rwdm':                  (50.86,   4.32),   # Molenbeek, Brussels
    'sint-gillis-waas':      (51.23,   4.11),
    'sittard':               (51.00,   5.87),
    'st-truiden':            (50.81,   5.19),
    'westerlo':              (51.10,   4.91),
    # Switzerland — additional entries
    'aarau':                 (47.39,   8.04),
    'thun':                  (46.76,   7.63),
    # Scandinavia — additional club entries (placed at their home city)
    'aik':                   (59.37,  18.04),   # Stockholm
    'brøndby':               (55.64,  12.43),   # Copenhagen suburb
    'djurgarden':            (59.37,  18.10),   # Stockholm
    'fc midtjylland':        (56.14,   9.16),   # Ikast/Herning area
    'gais':                  (57.68,  11.98),   # Gothenburg
    'hammarby':              (59.30,  18.08),   # Stockholm
    'häcken':                (57.71,  11.97),   # Gothenburg
    'hvidovre':              (55.65,  12.46),   # Copenhagen suburb
    'lyngby':                (55.77,  12.51),   # Copenhagen suburb
    'nordsjaelland':         (55.81,  12.36),   # Farum, N of Copenhagen
    'sarpsborg':             (59.28,  11.11),
}

# ---------------------------------------------------------------------------
# Europe bounding box for gross-error detection (generous margins)
# ---------------------------------------------------------------------------
_EUR_LAT_MIN =  34.0
_EUR_LAT_MAX =  72.0
_EUR_LNG_MIN = -15.0
_EUR_LNG_MAX =  42.0

# Convergence threshold (pixels) and degree-warning threshold
_INVERSION_TOL_PX  = 0.5
_INVERSION_MAX_ITER = 300
_DEGREE_WARN_THRESHOLD = 5.0


def _tps_inverse(x_pct, y_pct):
    """Numerically invert the TPS projection using Newton-Raphson.

    Given (x_pct, y_pct) on the europe-night image, recover the approximate
    (lng, lat) using the same TPS weights.  Returns (lng, lat) or raises
    RuntimeError if the iteration fails to converge.
    """
    target_px = x_pct / 100.0 * _MAP_IMG_W
    target_py = y_pct / 100.0 * _MAP_IMG_H

    # Initial guess: geographic centre of Europe
    lng, lat = 10.0, 50.0

    h = 0.005  # finite-difference step (degrees)

    for _ in range(_INVERSION_MAX_ITER):
        px = _tps_eval(_MAP_TPS_WX, lng, lat)
        py = _tps_eval(_MAP_TPS_WY, lng, lat)

        res_x = px - target_px
        res_y = py - target_py

        if math.hypot(res_x, res_y) < _INVERSION_TOL_PX:
            return lng, lat

        # Jacobian via central finite differences
        j00 = (_tps_eval(_MAP_TPS_WX, lng + h, lat) - _tps_eval(_MAP_TPS_WX, lng - h, lat)) / (2 * h)
        j01 = (_tps_eval(_MAP_TPS_WX, lng, lat + h) - _tps_eval(_MAP_TPS_WX, lng, lat - h)) / (2 * h)
        j10 = (_tps_eval(_MAP_TPS_WY, lng + h, lat) - _tps_eval(_MAP_TPS_WY, lng - h, lat)) / (2 * h)
        j11 = (_tps_eval(_MAP_TPS_WY, lng, lat + h) - _tps_eval(_MAP_TPS_WY, lng, lat - h)) / (2 * h)

        det = j00 * j11 - j01 * j10
        if abs(det) < 1e-8:
            raise RuntimeError("Jacobian singular – TPS inversion failed")

        # Newton step
        dlng = ( j11 * res_x - j01 * res_y) / det
        dlat = (-j10 * res_x + j00 * res_y) / det

        # Clamp step to avoid wild divergence
        step_mag = math.hypot(dlng, dlat)
        if step_mag > 5.0:
            dlng, dlat = dlng / step_mag * 5.0, dlat / step_mag * 5.0

        lng -= dlng
        lat -= dlat

    raise RuntimeError(
        f"TPS inversion did not converge after {_INVERSION_MAX_ITER} iterations "
        f"(residual={math.hypot(res_x, res_y):.2f}px)"
    )


class Command(BaseCommand):
    help = (
        "Sanity-check every city pin in CITY_MAP_PCT for range validity, "
        "TPS back-projection drift, and European bounds. "
        "Exits with code 1 if any critical error is detected."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--warn-threshold",
            type=float,
            default=_DEGREE_WARN_THRESHOLD,
            help=(
                "Back-projection drift (degrees) that triggers a WARNING "
                f"(default: {_DEGREE_WARN_THRESHOLD})"
            ),
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print a summary line for every pin, not just problems.",
        )

    def handle(self, *args, **options):
        warn_threshold = options["warn_threshold"]
        verbose = options["verbose"]

        errors = []
        warnings = []
        ok_count = 0

        # De-duplicate: many keys share the same (x, y) (aliases / club names).
        # We want one check per unique coordinate pair per canonical key.
        seen_coords = {}
        canonical_keys = {}
        for key, coords in CITY_MAP_PCT.items():
            if coords not in seen_coords:
                seen_coords[coords] = key
                canonical_keys[key] = coords

        total = len(canonical_keys)
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\ncheck_city_pins — checking {total} unique coordinate entries "
                f"({len(CITY_MAP_PCT)} total keys in CITY_MAP_PCT)\n"
            )
        )

        # ------------------------------------------------------------------
        # 0. Coverage enforcement — every canonical key must have a reference.
        #    Report missing entries as errors so the test cannot silently
        #    degrade when new cities are added to CITY_MAP_PCT.
        # ------------------------------------------------------------------
        uncovered = sorted(k for k in canonical_keys if k not in _CITY_REF_LATLNG)
        for key in uncovered:
            msg = (
                f"no reference lat/lng in _CITY_REF_LATLNG — "
                f"add a real-world coordinate to enable drift checking"
            )
            self.stdout.write(
                self.style.ERROR(
                    f"  ERROR  {key!r:35s}  {canonical_keys[key]}  — {msg}"
                )
            )
            errors.append(msg)

        for key, (x, y) in sorted(canonical_keys.items()):
            if key in uncovered:
                continue  # already reported above; skip per-pin checks

            city_errors = []
            city_warnings = []

            # ------------------------------------------------------------------
            # 1. Range check
            # ------------------------------------------------------------------
            if not (0.0 <= x <= 100.0):
                city_errors.append(f"x={x} out of [0,100]")
            if not (0.0 <= y <= 100.0):
                city_errors.append(f"y={y} out of [0,100]")

            # ------------------------------------------------------------------
            # 2 & 3. TPS inversion + geographic checks
            # ------------------------------------------------------------------
            try:
                inv_lng, inv_lat = _tps_inverse(x, y)

                # 3a. European bounds check (critical)
                if not (_EUR_LAT_MIN <= inv_lat <= _EUR_LAT_MAX):
                    city_errors.append(
                        f"back-projected lat={inv_lat:.2f} outside Europe "
                        f"[{_EUR_LAT_MIN},{_EUR_LAT_MAX}]"
                    )
                if not (_EUR_LNG_MIN <= inv_lng <= _EUR_LNG_MAX):
                    city_errors.append(
                        f"back-projected lng={inv_lng:.2f} outside Europe "
                        f"[{_EUR_LNG_MIN},{_EUR_LNG_MAX}]"
                    )

                # 3b. Reference-coordinate comparison (warning)
                ref_lat, ref_lng = _CITY_REF_LATLNG[key]
                drift_lat = abs(inv_lat - ref_lat)
                drift_lng = abs(inv_lng - ref_lng)
                drift = math.hypot(drift_lat, drift_lng)
                if drift > warn_threshold:
                    city_warnings.append(
                        f"back-projection drift {drift:.1f}° "
                        f"(inv=({inv_lat:.1f},{inv_lng:.1f}) "
                        f"vs ref=({ref_lat},{ref_lng}))"
                    )

            except RuntimeError as exc:
                city_errors.append(f"TPS inversion failed: {exc}")

            # ------------------------------------------------------------------
            # Report
            # ------------------------------------------------------------------
            if city_errors:
                for msg in city_errors:
                    self.stdout.write(
                        self.style.ERROR(f"  ERROR  {key!r:35s}  ({x}, {y})  — {msg}")
                    )
                errors.extend(city_errors)
            elif city_warnings:
                for msg in city_warnings:
                    self.stdout.write(
                        self.style.WARNING(f"  WARN   {key!r:35s}  ({x}, {y})  — {msg}")
                    )
                warnings.extend(city_warnings)
            else:
                ok_count += 1
                if verbose:
                    self.stdout.write(f"  ok     {key!r:35s}  ({x}, {y})")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        self.stdout.write("")
        summary = (
            f"Results: {ok_count} ok  |  "
            f"{len(warnings)} warning(s)  |  "
            f"{len(errors)} error(s)"
        )
        if errors:
            self.stdout.write(self.style.ERROR(summary))
            self.stdout.write(
                self.style.ERROR(
                    "\nFAILED — fix the entries above in game/views.py CITY_MAP_PCT.\n"
                )
            )
            sys.exit(1)
        elif warnings:
            self.stdout.write(self.style.WARNING(summary))
            self.stdout.write(
                self.style.WARNING(
                    "\nPASSED with warnings — consider re-pinning the flagged cities.\n"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(summary))
            self.stdout.write(self.style.SUCCESS("\nAll city pins look correct.\n"))
