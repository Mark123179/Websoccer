"""Feste Zuschlagstermine (Transferfenster) und 7-Tage-Vorlauf-Regel."""

from datetime import date

from .constants import WINDOW_DATES, BID_LEAD_DAYS


def all_window_dates_in_range(start, end):
    """Alle festen Zuschlagstermine im Zeitraum [start, end] (inklusiv), sortiert."""
    out = []
    for year in range(start.year, end.year + 1):
        for month, day in WINDOW_DATES:
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            if start <= d <= end:
                out.append(d)
    return sorted(out)


def next_window_after(reference_date):
    """Der nächste feste Zuschlagstermin strikt nach ``reference_date``."""
    year = reference_date.year
    candidates = []
    for y in (year, year + 1):
        for month, day in WINDOW_DATES:
            try:
                d = date(y, month, day)
            except ValueError:
                continue
            if d > reference_date:
                candidates.append(d)
    return min(candidates)


def window_for_bid(placed_on, lead_days=BID_LEAD_DAYS):
    """Zuschlagstermin, zu dem ein an ``placed_on`` abgegebenes Gebot zählt.

    Ein Gebot zählt nur für einen Termin, wenn es mindestens ``lead_days`` Tage
    davor abgegeben wurde; sonst zählt es erst für den nächsten Termin.
    """
    earliest_valid = placed_on
    target = next_window_after(placed_on)
    while (target - earliest_valid).days < lead_days:
        target = next_window_after(target)
    return target
