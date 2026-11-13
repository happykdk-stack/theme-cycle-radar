import json
import numpy as np
import pandas as pd
from update import OUT, BENCHMARK, THEMES, series_download, build
from traffic_lights import traffic_light, empty_signal
from heikin_ashi import ha_traffic_light, empty_ha_signal

SECURITIES_ETF = {"market":"한국", "ticker":"102970.KS", "fund":"KODEX 증권"}

def detect(df,bench):
    d=df.sort_index()
    c=d["Close"].astype(float); v=d["Volume"].astype(float)
    b=bench["Close"].reindex(d.index).ffill().astype(float)
    rel=c/b; r5=rel.pct_change(5); r20=rel.pct_change(20)
    m20=c.rolling(20).mean(); m60=c.rolling(60).mean()
    vr=v/v.shift(1).rolling(20).mean().replace(0,np.nan)
    vr5=v.rolling(5).mean()/v.shift(1).rolling(20).mean().replace(0,np.nan)
    trend=(c>m20)&(m20>m60)
    early=(r5>.008)&(r20>r20.shift(5))&(vr>1.15)&(c>m20*.98)
    expand=(r5>.012)&(r20>.035)&trend&(vr5>1.05)
    heat=(c/m20>1.18)|(c.pct_change(20)>.2)
    falling=(r5<-.015)&((c<m20)|(r20<r20.shift(5)-.02))
    raw=[]
    for i in range(len(d)):
        if i<65:raw.append("데이터 부족")
        elif bool(falling.iloc[i]):raw.append("쇠퇴")
        elif bool(expand.iloc[i]) and bool(heat.iloc[i]):raw.append("과열")
        elif bool(expand.iloc[i]):raw.append("상승 확산")
        elif bool(early.iloc[i]):raw.append("초기 유입")
        elif bool(r20.iloc[i]<-.025) or bool(c.iloc[i]<m60.iloc[i]):raw.append("침체")
        else:raw.append("관찰")
    # Two consecutive sessions are required to confirm stage change.
    stable=[]; last="데이터 부족"
    for i,s in enumerate(raw):
        if i>0 and s==raw[i-1] and s!="데이터 부족":last=s
        stable.append(last)
    changes=[{"date":d.index[i].date().isoformat(),"from":stable[i-1],"to":stable[i]}
             for i in range(1,len(stable)) if stable[i]!=stable[i-1] and stable[i]!="데이터 부족"]
    # Performance of the current uninterrupted, confirmed expansion stage only.
    expansion_since = None
    expansion_return_pct = None
    if stable and stable[-1] == "상승 확산":
        first = len(stable) - 1
        while first > 0 and stable[first - 1] == "상승 확산":
            first -= 1
        start_close = c.iloc[first]
        end_close = c.iloc[-1]
        if pd.notna(start_close) and pd.notna(end_close) and start_close > 0 and end_close > 0:
            expansion_since = d.index[first].date().isoformat()
            expansion_return_pct = round(float((end_close / start_close - 1) * 100), 2)
    rs_score=float(np.clip(50+400*(r20.iloc[-1] if pd.notna(r20.iloc[-1]) else 0),0,100))
    vol_score=float(np.clip(50+35*np.log2(max(float(vr.iloc[-1]),.01)),0,100)) if pd.notna(vr.iloc[-1]) else 50.
    momentum=float(np.clip(50+600*(r5.iloc[-1] if pd.notna(r5.iloc[-1]) else 0),0,100))
    score=.45*rs_score+.30*vol_score+.25*momentum
    if stable[-1]=="과열":score*=.7
    if stable[-1]=="쇠퇴":score*=.6
    # Reconstruct historical daily cycle strength using the same score formula.
    # Only the latest uninterrupted run at or above 60 is eligible.
    rs_history = (50 + 400 * r20.fillna(0)).clip(0, 100)
    vol_history = pd.Series(50.0, index=d.index)
    valid_volume = vr.notna()
    vol_history.loc[valid_volume] = (50 + 35 * np.log2(vr.loc[valid_volume].clip(lower=.01))).clip(0, 100)
    momentum_history = (50 + 600 * r5.fillna(0)).clip(0, 100)
    strength_history = .45 * rs_history + .30 * vol_history + .25 * momentum_history
    stage_penalty = pd.Series([.7 if stage == "과열" else .6 if stage == "쇠퇴" else 1.0 for stage in stable], index=d.index)
    strength_history *= stage_penalty
    strength_since = None
    strength_return_pct = None
    if len(d) >= 66 and pd.notna(strength_history.iloc[-1]) and round(float(strength_history.iloc[-1]), 1) >= 60:
        first = len(d) - 1
        while first > 65 and pd.notna(strength_history.iloc[first - 1]) and round(float(strength_history.iloc[first - 1]), 1) >= 60:
            first -= 1
        base_price, current_price = c.iloc[first], c.iloc[-1]
        if pd.notna(base_price) and pd.notna(current_price) and base_price > 0 and current_price > 0:
            strength_since = d.index[first].date().isoformat()
            strength_return_pct = round(float((current_price / base_price - 1) * 100), 2)
    previous = None
    if len(d)>70:
        p5 = float(r5.iloc[-6]) if pd.notna(r5.iloc[-6]) else 0.
        p20 = float(r20.iloc[-6]) if pd.notna(r20.iloc[-6]) else 0.
        pvr = float(vr.iloc[-6]) if pd.notna(vr.iloc[-6]) else 1.
        previous = .45*float(np.clip(50+400*p20,0,100)) + .30*float(np.clip(50+35*np.log2(max(pvr,.01)),0,100)) + .25*float(np.clip(50+600*p5,0,100))
    delta = round(score-previous,1) if previous is not None else None
    confirmation = sum([bool(r5.iloc[-1]>.005),bool(r20.iloc[-1]>r20.shift(5).iloc[-1]),bool(vr.iloc[-1]>1.2 or vr5.iloc[-1]>1.1),bool(c.iloc[-1]>m20.iloc[-1])])*25
    return {"cycle_stage":stable[-1],"cycle_score":round(score,1),
            "expansion_since":expansion_since,"expansion_return_pct":expansion_return_pct,
            "strength_since":strength_since,"strength_return_pct":strength_return_pct,
            "score_change_5d":delta,"transition_strength":round(float(np.clip(50+2*(delta or 0),0,100)),1) if delta is not None else None,
            "confirmation_score":confirmation,
            "cycle_last_transition":changes[-1]["date"] if changes else None,
            "cycle_previous_stage":changes[-1]["from"] if changes else None,
            "cycle_transitions":changes[-30:],
            "cycle_metrics":{"rs_20d_pct":round(float(r20.iloc[-1])*100,2) if pd.notna(r20.iloc[-1]) else None,
                             "volume_ratio":round(float(vr.iloc[-1]),2) if pd.notna(vr.iloc[-1]) else None}}

def build_v4(fetch=series_download, now=None):
    cache={}
    def cached(t):
        if t not in cache:
            # Three years of history need prior monthly bar for comparison.
            cache[t] = fetch(t, period='5y') if fetch is series_download and t == SECURITIES_ETF['ticker'] else fetch(t)
        return cache[t]
    result=build(cached)
    guide={**SECURITIES_ETF, "etf_trend":empty_ha_signal()}
    try:guide_frame=cached(guide["ticker"])
    except Exception as exc:
        result["errors"].append({"ticker":guide["ticker"],"message":"Securities ETF: "+str(exc)[:160]})
    else:
        try:guide["etf_trend"]=ha_traffic_light(guide_frame,guide["market"],now=now or result["generated_at_utc"],include_intraday=True)
        except Exception as exc:
            result["errors"].append({"ticker":guide["ticker"],"message":"ETF trend calculation: "+str(exc)[:160]})
    result["securities_etf"]=guide
    # Preserve failed ETFs as gray rows; benchmark failures must not hide ETF trends.
    present={t["ticker"] for t in result["themes"]}
    for market,theme,ticker,fund in THEMES:
        if ticker not in present:
            result["themes"].append({"market":market,"theme":theme,"ticker":ticker,"fund":fund,"asof":None})
    for t in result["themes"]:
        t["etf_trend"]=empty_ha_signal()
        try:frame=cached(t["ticker"])
        except Exception as exc:
            result["errors"].append({"ticker":t["ticker"],"message":"ETF trend: "+str(exc)[:160]})
        else:
            try:t["etf_trend"]=ha_traffic_light(frame,t["market"],now=now or result["generated_at_utc"],include_intraday=True)
            except Exception as exc:
                result["errors"].append({"ticker":t["ticker"],"message":"ETF trend calculation: "+str(exc)[:160]})
        try:t.update(detect(cached(t["ticker"]),cached(BENCHMARK[t["market"]])))
        except Exception as exc:result["errors"].append({"ticker":t["ticker"],"message":"V4: "+str(exc)[:160]})
    for market in BENCHMARK:
        group=sorted((t for t in result["themes"] if t["market"]==market and "cycle_score" in t),key=lambda t:t["cycle_score"],reverse=True)
        for rank,t in enumerate(group,1):t["market_rank"]=rank
    result["version"]="4.2"
    result["etf_trend_version"]="1.0"
    result["limitations"].extend(["신호등 상승 점수는 월봉 상승 50점 + 주봉 상승 30점 + 일봉 상승 20점이며, 혼재·보합과 하락은 0점입니다. 데이터 부족 시 미산출하며 실제 상승 확률이 아닙니다.","사이클 단계는 ETF 가격·거래량 대용지표 기반 추정이며 기관 자금 흐름이 아닙니다.",
        "단계 전환은 연속 2거래일 확인 후 기록됩니다. 점수는 예측 확률이 아닙니다.",
        "실제 구성종목 동반 상승 및 기관·외국인 순매수는 미포함입니다.",
        "ETF 신호등은 월·주·일 OHLC를 하이킨 아시로 변환합니다. HA 종가>HA 시가면 상승, 낮으면 하락, 같으면 보합입니다. 실제 시가 대비 등락률은 별도로 표시하며 HA 방향과 다를 수 있습니다.",
        "종합 초록=월·주·일 모두 상승, 빨강=모두 하락, 노랑=혼재·보합, 회색=한 시간대라도 데이터 부족. 완료 거래일까지 계산하며 진행 중인 월·주봉은 미확정입니다. 장중 일봉 HA 신호는 제공하지 않습니다.",
        "최근 신호 변경일과 초록 구간은 각 과거 거래일 당시 진행 중인 월·주봉을 포함해 ETF 종합 색상을 재계산합니다. 최초 산출은 변경으로 세지 않으며 공급자 과거 수정에 따라 달라질 수 있습니다."])
    if result["errors"] and result["status"]=="ok":result["status"]="partial"
    return result

if __name__=="__main__":
    result=build_v4()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("V4 themes",len(result["themes"]),"errors",len(result["errors"]))
    if result["status"]=="error":raise SystemExit(1)
