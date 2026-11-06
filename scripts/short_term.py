"""Research-only KOSPI crash rebound scanner; no orders or live trading."""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site" / "short_term.json"
WATCH = [("KODEX 200", "069500.KS"), ("KODEX 반도체", "091160.KS"),
         ("KODEX 2차전지산업", "305720.KS"), ("KODEX 바이오", "244580.KS"),
         ("KODEX K-로봇액티브", "445290.KS"), ("PLUS K방산", "449450.KS")]
CRASH_THRESHOLD = -9.0

def normalize(frame):
    if frame is None or frame.empty:
        raise ValueError("시세 데이터 없음")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame[["Open", "High", "Low", "Close", "Volume"]].copy()
    frame.index = pd.to_datetime(frame.index)
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("Asia/Seoul")
    else:
        frame.index = frame.index.tz_convert("Asia/Seoul")
    return frame.sort_index().dropna(subset=["Close", "Low", "High"])

def download(symbol, interval, period):
    data = yf.download(symbol, interval=interval, period=period, auto_adjust=True,
                       progress=False, threads=False, timeout=20)
    if data is None or data.empty:
        data = yf.Ticker(symbol).history(interval=interval, period=period, auto_adjust=True)
    return normalize(data)

def evaluate(bars):
    """Only completed five-minute candles; no future-bar lookahead."""
    if len(bars) < 12:
        return {"status": "N/A", "reason": "완료된 5분봉 12개 미만"}
    c = bars["Close"].astype(float)
    low = bars["Low"].astype(float)
    vol = bars["Volume"].astype(float)
    ma5 = c.rolling(5).mean()
    ma10 = c.rolling(10).mean()
    prior_volume = vol.iloc[-11:-1].mean()
    bounce = c.iloc[-1] >= low.iloc[-12:].min() * 1.01
    trend = c.iloc[-1] > ma5.iloc[-1] > ma10.iloc[-1]
    recovery = c.iloc[-1] > c.iloc[-2]
    volume = prior_volume > 0 and vol.iloc[-1] >= 1.5 * prior_volume
    confirmed = bool(bounce and trend and recovery and volume)
    return {"status": "반등 확인" if confirmed else "관찰",
            "bounce_pct": round(float((c.iloc[-1] / low.iloc[-12:].min() - 1) * 100), 2),
            "above_ma": bool(trend), "rising": bool(recovery), "volume_confirmed": bool(volume),
            "volume_multiple": round(float(vol.iloc[-1] / prior_volume), 2) if prior_volume > 0 else None,
            "close": round(float(c.iloc[-1]), 2),
            "asof": bars.index[-1].isoformat()}

def build(now=None, fetch=download):
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    local = now.tz_convert("Asia/Seoul")
    result = {"generated_at_utc": now.isoformat(), "threshold_pct": CRASH_THRESHOLD,
              "market": "KOSPI", "status": "N/A", "drop_pct": None,
              "trigger_date": None, "candidates": [], "errors": [],
              "note": "5분봉은 지연될 수 있으며 주문 실행 신호가 아닙니다."}
    try:
        daily = fetch("^KS11", "1d", "10d")
        # Use only completed daily sessions to calculate the preceding close.
        completed = daily[daily.index.normalize() < local.normalize()]
        today = daily[daily.index.normalize() == local.normalize()]
        if not today.empty and local.hour >= 15 and (local.hour > 15 or local.minute >= 30):
            current = today.iloc[-1]
            previous = completed.iloc[-1] if len(completed) else None
        elif not today.empty and local.hour >= 9:
            current = today.iloc[-1]
            previous = completed.iloc[-1] if len(completed) else None
        elif len(completed) >= 2:
            current, previous = completed.iloc[-1], completed.iloc[-2]
        else:
            raise ValueError("코스피 비교 종가 부족")
        if previous is None or previous["Close"] <= 0:
            raise ValueError("전일 종가 없음")
        change = (float(current["Close"]) / float(previous["Close"]) - 1) * 100
        result["drop_pct"] = round(change, 2)
        result["trigger_date"] = current.name.date().isoformat()
        if change > CRASH_THRESHOLD:
            result["status"] = "조건 미충족"
            return result
        # The 5-minute scanner only evaluates the same local trading session.
        if current.name.date() != local.date() or not (9 <= local.hour <= 16):
            result["status"] = "과거 급락일 · 5분봉 미평가"
            return result
        result["status"] = "급락 조건 충족"
        for name, ticker in WATCH:
            try:
                bars = fetch(ticker, "5m", "5d")
                bars = bars[bars.index.date == local.date()]
                # Exclude the candle currently forming.
                bar_end = bars.index + pd.Timedelta(minutes=5)
                bars = bars[bar_end <= local]
                result["candidates"].append({"name": name, "ticker": ticker, **evaluate(bars)})
            except Exception as exc:
                result["errors"].append({"ticker": ticker, "message": str(exc)[:150]})
    except Exception as exc:
        result["errors"].append({"ticker": "^KS11", "message": str(exc)[:150]})
    return result

if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
