"""Changes between observed ETF quote P/Es exactly 15 exchange sessions apart.

Quote observation dates are not verified historical valuation/closing dates.
Never infer a P/E from prices, interpolate gaps, or substitute a nearby date.
"""
from datetime import date, timedelta
import math

from traffic_lights import exchange_schedule

LOOKBACK_SESSIONS = 15


def daily_per_slopes(history, market, asof):
    cutoff = date.fromisoformat(asof)
    points = {}
    for point in history:
        try:
            day = date.fromisoformat(point['date'])
            value = float(point['pe'])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if day <= cutoff and math.isfinite(value) and value > 0:
            points[day.isoformat()] = value
    if not points:
        return []
    try:
        first = date.fromisoformat(min(points)) - timedelta(days=90)
        schedule = exchange_schedule(market, first.isoformat(), asof)
        sessions = [stamp.date().isoformat() for stamp in schedule.index]
        positions = {day: i for i, day in enumerate(sessions)}
    except Exception:
        sessions, positions = [], None
    rows = []
    for day, value in sorted(points.items()):
        row = {'date': day, 'pe': value, 'baseline_date': None,
               'baseline_pe': None, 'change_pct': None,
               'slope_per_session': None, 'status': 'missing_baseline'}
        if positions is None:
            row['status'] = 'calendar_error'
        elif day not in positions:
            row['status'] = 'non_session'
        elif positions[day] >= LOOKBACK_SESSIONS:
            baseline = sessions[positions[day] - LOOKBACK_SESSIONS]
            row['baseline_date'] = baseline
            prior = points.get(baseline)
            if prior is not None:
                row.update(baseline_pe=prior,
                           change_pct=round((value / prior - 1) * 100, 6),
                           slope_per_session=round((value - prior) / LOOKBACK_SESSIONS, 6),
                           status='ok')
        rows.append(row)
    return rows
