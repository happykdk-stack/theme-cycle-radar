"""Calendar-week aggregation of observed ETF quote P/E, never a closing P/E."""
from datetime import date, timedelta
import math


def weekly_per_observations(history, asof):
    cutoff = date.fromisoformat(asof)
    unique = {}
    for point in history:
        try:
            day = date.fromisoformat(point['date'])
            value = float(point['pe'])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if day <= cutoff and math.isfinite(value) and value > 0:
            unique[day] = value
    weeks = {}
    for day, value in sorted(unique.items()):
        start = day - timedelta(days=day.weekday())
        row = weeks.setdefault(start, {'week_start': start.isoformat(),
            'week_end': (start + timedelta(days=6)).isoformat(), 'observations': 0})
        row.update(date=day.isoformat(), pe=value)
        row['observations'] += 1
    output = []
    for start, row in sorted(weeks.items()):
        prior = weeks.get(start - timedelta(days=7))
        row.update(previous_week_start=(start-timedelta(days=7)).isoformat(),
            baseline_date=prior['date'] if prior else None,
            baseline_pe=prior['pe'] if prior else None,
            change_pct=round((row['pe']/prior['pe']-1)*100, 6) if prior else None,
            is_partial_week=date.fromisoformat(row['week_end']) > cutoff)
        output.append(row)
    return output
