"""Heikin-Ashi trend signals derived from exchange-session OHLC bars."""
import numpy as np
import pandas as pd
from traffic_lights import (traffic_light, combine, bullish_score, green_history,
                            FREQUENCIES, CALENDARS, exchange_schedule)

def ha_candles(ohlc):
    """Canonical HA candles, recursively seeded with the first real candle."""
    if ohlc.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close"])
    out = []
    prior_open = prior_close = None
    for row in ohlc.itertuples(index=False):
        o, h, l, c = (float(getattr(row, key)) for key in ("Open", "High", "Low", "Close"))
        hc = (o + h + l + c) / 4
        ho = (o + c) / 2 if prior_open is None else (prior_open + prior_close) / 2
        out.append((ho, max(h, ho, hc), min(l, ho, hc), hc))
        prior_open, prior_close = ho, hc
    return pd.DataFrame(out, index=ohlc.index, columns=["Open", "High", "Low", "Close"])

def ha_traffic_light(frame, market, now=None, include_intraday=False):
    """Recompute HA at each session without using future month/week candles."""
    baseline = traffic_light(frame, market, now=now, include_intraday=include_intraday)
    if frame is None or frame.empty or baseline["asof"] is None:
        return baseline
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError("now must have a timezone")
    now = now.tz_convert("UTC")
    zone = "Asia/Seoul" if market == "한국" else "America/New_York"
    local_today = now.tz_convert(zone).tz_localize(None).normalize()
    f = frame.copy()
    if isinstance(f.columns, pd.MultiIndex):
        f.columns = f.columns.get_level_values(0)
    # Historical unit fixtures sometimes provide close-only bars.
    if "Open" not in f:
        f["Open"] = f["Close"]
    if "High" not in f:
        f["High"] = f[["Open", "Close"]].max(axis=1)
    if "Low" not in f:
        f["Low"] = f[["Open", "Close"]].min(axis=1)
    idx = pd.DatetimeIndex(f.index)
    if idx.tz is not None:
        idx = idx.tz_convert(zone).tz_localize(None)
    f.index = idx.normalize()
    f = f[~f.index.duplicated(keep="last")].sort_index().loc[:local_today]
    f = f[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce")
    if f.empty:
        return baseline
    start = min(f.index[0].to_period("M").start_time, f.index[0].to_period("W-FRI").start_time)
    end = max(local_today.to_period("M").end_time.normalize(),
              local_today.to_period("W-FRI").end_time.normalize())
    schedule = exchange_schedule(market, str(start.date()), str(end.date()))
    sessions = pd.DatetimeIndex(schedule.index).tz_localize(None).normalize()
    close_times = pd.Series(pd.to_datetime(schedule["close"], utc=True).array, index=sessions)
    completed = sessions[close_times <= now]
    if len(completed) == 0:
        return baseline
    aligned = f.reindex(sessions)
    histories, snapshots = {}, {}
    for key, frequency in FREQUENCIES.items():
        history = {}
        previous_open = previous_close = None
        period_key = None
        period_rows = []
        for day in completed:
            p = day.to_period(frequency)
            if p != period_key:
                if period_rows:
                    # Finalize the previous period using only its known session data.
                    agg = _aggregate(period_rows)
                    if agg is not None:
                        hc = sum(agg.values()) / 4
                        ho = (agg["Open"] + agg["Close"]) / 2 if previous_open is None else (previous_open + previous_close) / 2
                        previous_open, previous_close = ho, hc
                period_rows = []
                period_key = p
            row = aligned.loc[day]
            if row.notna().all() and (row > 0).all():
                period_rows.append(row)
            agg = _aggregate(period_rows)
            if agg is None:
                history[day] = ("insufficient", None, None)
                continue
            hc = sum(agg.values()) / 4
            ho = (agg["Open"] + agg["Close"]) / 2 if previous_open is None else (previous_open + previous_close) / 2
            state = "up" if hc > ho else "down" if hc < ho else "mixed"
            history[day] = (state, ho, hc)
        histories[key] = pd.Series({day: val[0] for day, val in history.items()})
        state, ho, hc = history[completed[-1]]
        actual = _aggregate(period_rows)
        actual_open = actual["Open"] if actual is not None else None
        actual_close = actual["Close"] if actual is not None else None
        actual_change = round((actual_close / actual_open - 1) * 100, 2) if actual_open and actual_close else None
        snapshots[key] = {"state": state, "asof": completed[-1].date().isoformat(),
                          "ha_open": ho, "ha_close": hc,
                          "actual_open": actual_open, "actual_close": actual_close,
                          "actual_change_pct": actual_change,
                          "close": float(aligned.loc[completed[-1], "Close"]) if pd.notna(aligned.loc[completed[-1], "Close"]) else None,
                          "provisional": key != "daily" and completed[-1].to_period(frequency) == local_today.to_period(frequency)}
    signals = pd.Series([combine([histories[k].loc[day] for k in FREQUENCIES]) for day in completed], index=completed)
    # Preserve stale-session safety from the original exchange-aware implementation.
    if baseline["signal"] == "gray":
        signals.iloc[-1] = "gray"
        for key in FREQUENCIES:
            snapshots[key]["state"] = "insufficient"
    transitions = [{"date": completed[i].date().isoformat(), "from": signals.iloc[i-1], "to": signals.iloc[i]}
                   for i in range(1, len(signals)) if signals.iloc[i] != signals.iloc[i-1]]
    current = signals.iloc[-1]
    baseline.update({"method": "Heikin-Ashi", "signal": current, "timeframes": snapshots,
                     "bullish_score": bullish_score(current, snapshots),
                     "advanced_bullish_score": _ha_strength(current, snapshots),
                     "green_history": green_history(signals),
                     "last_changed": transitions[-1]["date"] if transitions else None,
                     "transitions": transitions[-60:]})
    # Current open monthly/weekly candles are provisional, even after a daily close.
    baseline["intraday"] = None
    if include_intraday and baseline["asof"] != local_today.date().isoformat():
        # Do not synthesize an intraday HA signal from incomplete OHLC.
        pass
    return baseline

def _aggregate(rows):
    if not rows:
        return None
    return {"Open": float(rows[0]["Open"]), "High": max(float(r["High"]) for r in rows),
            "Low": min(float(r["Low"]) for r in rows), "Close": float(rows[-1]["Close"])}

def _ha_strength(signal, frames):
    if signal == "gray":
        return None
    weights = {"monthly": 50, "weekly": 30, "daily": 20}
    total = 0.
    for key, weight in weights.items():
        f = frames[key]
        o, c = f["ha_open"], f["ha_close"]
        if o is None or c is None or o <= 0:
            return None
        total += weight * float(np.clip((c - o) / o / {"monthly": .05, "weekly": .03, "daily": .015}[key], 0, 1))
    return round(total, 1)
