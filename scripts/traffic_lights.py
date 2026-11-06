"""MA1 price-direction signals, with separate provisional intraday snapshots."""
from functools import lru_cache
import numpy as np
import pandas as pd
import exchange_calendars as xcals

CALENDARS = {"한국": "XKRX", "미국": "XNYS"}
BULLISH_WEIGHTS = {"monthly": 50, "weekly": 30, "daily": 20}
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


def bullish_score(signal, timeframes):
    """Weighted trend agreement (0-100 points), not a win probability."""
    if signal == "gray" or any(timeframes.get(k, {}).get("state") not in ("up", "down", "mixed") for k in BULLISH_WEIGHTS):
        return None
    return sum(weight for key, weight in BULLISH_WEIGHTS.items() if timeframes[key]["state"] == "up")


def empty_signal():
    return {"signal": "gray", "last_changed": None, "initial_since": None,
            "green_history": None, "bullish_score": None, "intraday": None, "method": "MA1",
            "asof": None, "transitions": [], "green_performance": None, "green_since": None, "timeframes": {
                key: {"state": "insufficient", "asof": None, "close": None,
                      "ma1": None, "previous_ma1": None}
                for key in FREQUENCIES}}


def green_history(signals):
    """Three-calendar-year window, with runs contiguous in exchange sessions, not days.

    Keep the true observed start of an overlapping run, even before the window.
    Gray observations break runs and prevent an unqualified 'none' assertion.
    """
    asof = signals.index[-1]
    start = asof - pd.DateOffset(years=3)
    window = signals.loc[start:]
    runs = []
    first = None
    for i, (day, color) in enumerate(signals.items()):
        if color == "green" and first is None:
            first = day
        if first is not None and (color != "green" or i == len(signals) - 1):
            last = day if color == "green" else signals.index[i - 1]
            if last >= start:
                runs.append({"start_date": first.date().isoformat(),
                             "end_date": last.date().isoformat(),
                             "active": bool(color == "green" and day == asof)})
            first = None
    latest = runs[-1] if runs else None
    return {"window_start": start.date().isoformat(), "asof": asof.date().isoformat(),
            "complete": bool(len(window) and signals.index[0] <= start and (window != "gray").all()),
            "latest_date": latest["end_date"] if latest else None,
            "latest_run": latest, "runs": runs}


def traffic_light(frame, market, now=None, include_intraday=False):
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
    recent_valid = aligned.reindex(completed).notna().rolling(2, min_periods=1).sum()
    recent_valid = recent_valid == np.minimum(np.arange(len(completed)) + 1, 2)
    histories, snapshots, live_snapshots = {}, {}, {}
    open_times = pd.Series(pd.to_datetime(schedule["open"], utc=True).array, index=sessions)
    live_day = local_today if (include_intraday and local_today in sessions
                and open_times.loc[local_today] <= now < close_times.loc[local_today]
                and pd.notna(aligned.loc[local_today])) else None
    for key, frequency in FREQUENCIES.items():
        periods = completed.to_period(frequency)
        # Final closes are used ONLY through shifted prior-period aggregates.
        # Every session supplies its own current partial month/week close, so
        # later prices in that period cannot change an earlier day's signal.
        groups = aligned.groupby(sessions.to_period(frequency))
        finals = groups.agg(lambda group: group.iloc[-1])  # Never skip a missing final.
        full = pd.Series([group.index[0] >= close.index[0] for _, group in groups], index=finals.index)
        finals = finals.where(full)
        bars = aligned.reindex(completed).where(full.reindex(periods).to_numpy())
        # MA1 is the price itself: compare with the prior period's final price.
        prior = finals.shift(1)
        previous = pd.Series(prior.reindex(periods).to_numpy(), index=completed)
        valid = bars.notna() & previous.notna()
        states = pd.Series("insufficient", index=bars.index)
        states.loc[valid] = "mixed"
        states.loc[valid & (bars > previous)] = "up"
        states.loc[valid & (bars < previous)] = "down"
        histories[key] = states
        def number(series):
            return float(series.iloc[-1]) if len(series) and pd.notna(series.iloc[-1]) else None
        snapshots[key] = {"state": states.iloc[-1] if len(states) else "insufficient",
                          "asof": bars.index[-1].date().isoformat() if len(bars) else None,
                          "close": number(bars), "ma1": number(bars), "previous_ma1": number(previous)}
        if live_day is not None:
            period = live_day.to_period(frequency)
            price, base = aligned.loc[live_day], prior.loc[period]
            state = "insufficient" if pd.isna(base) or not full.loc[period] else "up" if price > base else "down" if price < base else "mixed"
            live_snapshots[key] = {"state": state, "asof": live_day.date().isoformat(),
                                   "close": float(price), "ma1": float(price),
                                   "previous_ma1": float(base) if pd.notna(base) else None,
                                   "provisional": True}
    signals = pd.Series([combine([histories[k].loc[day] for k in FREQUENCIES])
                         for day in completed], index=completed)
    signals.loc[~recent_valid] = "gray"
    valid_signals = signals[signals != "gray"]
    initial = valid_signals.index[0] if len(valid_signals) else None
    # Initial availability is not presented as a historical signal change.
    transitions = [{"date": signals.index[i].date().isoformat(),
                    "from": signals.iloc[i-1], "to": signals.iloc[i]}
                   for i in range(1, len(signals))
                   if initial is not None and signals.index[i] > initial
                   and signals.iloc[i] != signals.iloc[i-1]]
    # Track only the current uninterrupted triple-green run.
    green_performance = None
    green_since = None
    if signals.iloc[-1] == "green":
        pos = len(signals) - 1
        while pos > 0 and signals.iloc[pos - 1] == "green":
            pos -= 1
        first = signals.index[pos]
        latest = completed[-1]
        base = aligned.loc[first]
        prices = aligned.loc[first:latest].dropna()
        if pd.notna(base) and base > 0 and len(prices) and prices.index[-1] == latest:
            green_since = first.date().isoformat()
            green_performance = {
                "start_date": green_since,
                "end_date": latest.date().isoformat(),
                "start_price": round(float(base), 4),
                "end_price": round(float(prices.iloc[-1]), 4),
                "return_pct": round(float((prices.iloc[-1] / base - 1) * 100), 2),
                "peak_return_pct": round(float((prices.max() / base - 1) * 100), 2),
                "active": True,
            }
    for key in FREQUENCIES:
        snapshots[key]["provisional"] = key != "daily" and snapshots[key]["asof"] is not None and pd.Timestamp(snapshots[key]["asof"]).to_period(FREQUENCIES[key]) == local_today.to_period(FREQUENCIES[key])
    intraday = None
    if live_day is not None:
        live_signal = combine([live_snapshots[k]["state"] for k in FREQUENCIES])
        if aligned.reindex(completed[-1:]).isna().any():
            live_signal = "gray"
        intraday = {"signal": live_signal, "bullish_score": bullish_score(live_signal, live_snapshots),
                    "timeframes": live_snapshots, "asof": live_day.date().isoformat(),
                    "provisional": True, "observed_at_utc": now.isoformat()}
    return {"signal": signals.iloc[-1], "timeframes": snapshots, "method": "MA1", "intraday": intraday,
            "bullish_score": bullish_score(signals.iloc[-1], snapshots),
            "asof": completed[-1].date().isoformat(),
            "initial_since": initial.date().isoformat() if initial is not None else None,
            "last_changed": transitions[-1]["date"] if transitions else None,
            "transitions": transitions[-60:], "green_performance": green_performance, "green_since": green_since,
            "green_history": green_history(signals)}
