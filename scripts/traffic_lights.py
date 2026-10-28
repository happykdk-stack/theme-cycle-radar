"""ETF trend signals including the latest completed session of open periods."""
from functools import lru_cache
import numpy as np
import pandas as pd
import exchange_calendars as xcals

CALENDARS = {"한국": "XKRX", "미국": "XNYS"}
FREQUENCIES = {"monthly": "M", "weekly": "W-FRI", "daily": "D"}


@lru_cache(maxsize=32)
def exchange_schedule(market, start, end):
    return xcals.get_calendar(CALENDARS[market], start=start, end=end).schedule


def combine(states):
    if "insufficient" in states:
        return "gray"
    if all(s == "up" for s in states):
        return "green"
    if all(s == "down" for s in states):
        return "red"
    return "yellow"


def empty_signal():
    return {"signal": "gray", "last_changed": None, "initial_since": None,
            "asof": None, "transitions": [], "green_performance": None, "timeframes": {
                key: {"state": "insufficient", "asof": None, "close": None,
                      "ma5": None, "previous_ma5": None}
                for key in FREQUENCIES}}


def traffic_light(frame, market, now=None):
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError("now must have a timezone")
    now = now.tz_convert("UTC")
    if frame is None or frame.empty:
        return empty_signal()
    close = pd.to_numeric(frame["Close"], errors="coerce").copy()
    index = pd.DatetimeIndex(close.index)
    if index.tz is not None:
        index = index.tz_convert("Asia/Seoul" if market == "한국" else "America/New_York").tz_localize(None)
    close.index = index.normalize()
    close = close[~close.index.duplicated(keep="last")].sort_index()
    close = close.where(np.isfinite(close) & (close > 0))
    local_today = now.tz_convert("Asia/Seoul" if market == "한국" else "America/New_York").tz_localize(None).normalize()
    close = close.loc[:local_today]
    if close.empty:
        return empty_signal()
    # Include the whole first/last month to reject partial listing months and
    # know the final scheduled session even when Friday/month-end is a holiday.
    start = min(close.index[0].to_period("M").start_time,
                close.index[0].to_period("W-FRI").start_time)
    end = max(local_today.to_period("M").end_time.normalize(),
              local_today.to_period("W-FRI").end_time.normalize())
    schedule = exchange_schedule(market, str(start.date()), str(end.date()))
    sessions = pd.DatetimeIndex(schedule.index).tz_localize(None).normalize()
    close_times = pd.Series(pd.to_datetime(schedule["close"], utc=True).array, index=sessions)
    completed = sessions[close_times <= now]
    if completed.empty:
        return empty_signal()
    aligned = close.reindex(sessions)
    # Missing recent sessions invalidate the live signal rather than silently
    # treating an older quote as the current week/month's latest price.
    if aligned.reindex(completed[-5:]).isna().any():
        return empty_signal()
    histories, snapshots = {}, {}
    for key, frequency in FREQUENCIES.items():
        rows = []
        for _, group in aligned.groupby(sessions.to_period(frequency)):
            final = group.index[-1]
            # For the current week/month use the most recent completed session,
            # even before the calendar period ends. Historical periods retain
            # their final scheduled close to avoid look-ahead bias.
            available = group.index.intersection(completed)
            if not len(available):
                continue
            is_current = final > completed[-1]
            bar_day = available[-1] if is_current else final
            if not is_current and close_times.loc[final] > now:
                continue
            full_period = group.index[0] >= close.index[0]
            rows.append((bar_day, aligned.loc[bar_day] if full_period else np.nan))
        bars = pd.Series(dict(rows), dtype=float).sort_index()
        ma = bars.rolling(5, min_periods=5).mean()
        previous = ma.shift(1)
        valid = bars.notna() & ma.notna() & previous.notna()
        states = pd.Series("insufficient", index=bars.index)
        states.loc[valid] = "mixed"
        states.loc[valid & (bars > ma) & (ma > previous)] = "up"
        states.loc[valid & (bars < ma) & (ma < previous)] = "down"
        histories[key] = states.reindex(completed, method="ffill").fillna("insufficient")
        def number(series):
            return float(series.iloc[-1]) if len(series) and pd.notna(series.iloc[-1]) else None
        snapshots[key] = {"state": states.iloc[-1] if len(states) else "insufficient",
                          "asof": bars.index[-1].date().isoformat() if len(bars) else None,
                          "close": number(bars), "ma5": number(ma), "previous_ma5": number(previous)}
    signals = pd.Series([combine([histories[k].loc[day] for k in FREQUENCIES])
                         for day in completed], index=completed)
    valid_signals = signals[signals != "gray"]
    initial = valid_signals.index[0] if len(valid_signals) else None
    # Initial availability is not presented as a historical signal change.
    transitions = [{"date": signals.index[i].date().isoformat(),
                    "from": signals.iloc[i-1], "to": signals.iloc[i]}
                   for i in range(1, len(signals))
                   if initial is not None and signals.index[i] > initial
                   and signals.iloc[i] != signals.iloc[i-1]]
    # Most recent contiguous all-green run, including a completed run.
    green_performance = None
    green_days = signals.index[signals == "green"]
    if len(green_days):
        last_green = green_days[-1]
        end_pos = signals.index.get_loc(last_green)
        start_pos = end_pos
        while start_pos > 0 and signals.iloc[start_pos - 1] == "green":
            start_pos -= 1
        start_day = signals.index[start_pos]
        base_price = aligned.loc[start_day]
        end_day = completed[-1] if signals.iloc[-1] == "green" else last_green
        period_prices = aligned.loc[start_day:end_day].dropna()
        if pd.notna(base_price) and base_price > 0 and len(period_prices):
            green_performance = {
                "start_date": start_day.date().isoformat(),
                "end_date": end_day.date().isoformat(),
                "start_price": round(float(base_price), 4),
                "end_price": round(float(period_prices.iloc[-1]), 4),
                "return_pct": round(float((period_prices.iloc[-1] / base_price - 1) * 100), 2),
                "peak_return_pct": round(float((period_prices.max() / base_price - 1) * 100), 2),
                "active": bool(signals.iloc[-1] == "green"),
            }
    for key in FREQUENCIES:
        snapshots[key]["provisional"] = key != "daily" and snapshots[key]["asof"] is not None and pd.Timestamp(snapshots[key]["asof"]).to_period(FREQUENCIES[key]) == local_today.to_period(FREQUENCIES[key])
    return {"signal": signals.iloc[-1], "timeframes": snapshots,
            "asof": completed[-1].date().isoformat(),
            "initial_since": initial.date().isoformat() if initial is not None else None,
            "last_changed": transitions[-1]["date"] if transitions else None,
            "transitions": transitions[-60:], "green_performance": green_performance}
