"""Cycle Radar V2: predeclared trend/relative-strength signal vs legacy spike signal."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from update import ROOT, OUT, THEMES, BENCHMARK, build, series_download

def calculate_v2(df, bench):
    d = df.copy().sort_index()
    b = bench["Close"].reindex(d.index).ffill()
    close = d["Close"].astype(float)
    volume = d["Volume"].astype(float)
    rel = close / b
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    rs5 = rel.pct_change(5)
    rs20 = rel.pct_change(20)
    vol20 = volume.shift(1).rolling(20).mean()
    volume_ratio = volume / vol20.replace(0, np.nan)
    run20 = close.pct_change(20)
    ret5 = close.pct_change(5)
    trend = (close > ma20) & (ma5 > ma20) & (ma20 > ma20.shift(5))
    strength = (rs5 > 0.01) & (rs20 > 0.02)
    interest = volume_ratio > 1.15
    overheated = (ret5 > 0.15) | (run20 > 0.30) | (close / ma20 > 1.18)
    eligible = (trend & strength & interest & ~overheated).fillna(False)
    # First qualifying day, then a 10-session cooldown. All calculations use current/past data only.
    signals = np.zeros(len(d), dtype=bool)
    last = -100
    for i, flag in enumerate(eligible.to_numpy()):
        if i >= 65 and flag and i-last > 10:
            signals[i] = True
            last = i
    # Composite score: RS 30%, prior-20-day volume interest 25%,
    # moving-average trend 20%, momentum persistence 10%, heat-adjusted 15%.
    rs_score = (50 + 550 * rs20.fillna(0)).clip(0,100)
    volume_score = (50 + 40 * np.log2(volume_ratio.clip(lower=0.01))).clip(0,100).fillna(50)
    trend_score = (25 * (close > ma20).astype(int) + 25 * (ma5 > ma20).astype(int)
                   + 25 * (ma20 > ma60).astype(int) + 25 * (ma20 > ma20.shift(5)).astype(int))
    persist = (close.pct_change() > 0).rolling(10).mean().fillna(0.5)*100
    heat_score = (100 - 100 * overheated.astype(int))
    score = (0.30*rs_score + 0.25*volume_score + 0.20*trend_score
             + 0.10*persist + 0.15*heat_score).clip(0,100)
    def future(i, n):
        if i+n >= len(d): return None
        # End-of-day signal is evaluated using next session OPEN as entry when available.
        entry = float(d["Open"].iloc[i+1]) if "Open" in d.columns and pd.notna(d["Open"].iloc[i+1]) else None
        if entry is None or entry <= 0: return None
        return round((float(close.iloc[i+n])/entry - 1)*100,2)
    events=[]
    for i in np.flatnonzero(signals):
        events.append({"date":d.index[i].date().isoformat(),
                       "return_5d_pct":future(i,5),"return_20d_pct":future(i,20),
                       "entry_basis":"next_open"})
    def stats(events, n):
        values=[x[f"return_{n}d_pct"] for x in events if x[f"return_{n}d_pct"] is not None]
        return {"count":len(values),"win_rate_pct":round(100*sum(x>0 for x in values)/len(values),1) if values else None,
                "avg_return_pct":round(sum(values)/len(values),2) if values else None}
    return {"score_v2":round(float(score.iloc[-1]),1),
            "stage_v2":("과열 경고" if bool(overheated.iloc[-1]) else
                        "초기 유입" if bool(signals[-1]) else
                        "상승 추세" if bool(eligible.iloc[-1]) else
                        "관찰" if float(score.iloc[-1])>=45 else "약세"),
            "last_signal_v2":events[-1]["date"] if events else None,
            "signals_v2":events[-100:],
            "stats_v2":{"5d":stats(events,5),"20d":stats(events,20)},
            "current":{"relative_20d_pct":round(float(rs20.iloc[-1])*100,2) if pd.notna(rs20.iloc[-1]) else None,
                       "volume_to_prior_20d":round(float(volume_ratio.iloc[-1]),2) if pd.notna(volume_ratio.iloc[-1]) else None,
                       "overheated":bool(overheated.iloc[-1])}}

def build_v2(fetch=series_download):
    cache={}
    def cached(symbol):
        if symbol not in cache: cache[symbol]=fetch(symbol)
        return cache[symbol]
    result=build(cached)
    for t in result["themes"]:
        try:
            df=cached(t["ticker"])
            bench=cached(BENCHMARK[t["market"]])
            t.update(calculate_v2(df,bench))
        except Exception as exc:
            result["errors"].append({"ticker":t["ticker"],"message":"V2: "+str(exc)[:150]})
    result["version"]="2.0"
    result["limitations"].extend([
        "V2는 이동평균·상대강도·거래량 기반 실험 규칙입니다. 미래 예측 정확도는 검증되지 않았습니다.",
        "V2는 다음 거래일 시가가 없는 데이터에서는 수익률을 산출하지 않습니다.",
        "V2 성과는 ETF별 과거 신호를 중복 포함하며 거래비용·슬리피지 미반영입니다.",
        "테마 구성종목 확산과 기관 순매수는 아직 연결되지 않아 V2 점수에 포함하지 않습니다.",
        "동일한 과거 구간으로 규칙을 고르고 평가하면 과최적화 위험이 있습니다."
    ])
    if result["errors"] and result["status"]=="ok":result["status"]="partial"
    return result

if __name__=="__main__":
    result=build_v2()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("V2 generated:",len(result["themes"]),"themes;",len(result["errors"]),"errors")
    if result["status"]=="error":raise SystemExit(1)
