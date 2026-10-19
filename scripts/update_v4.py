import json
import numpy as np
import pandas as pd
from update import OUT, BENCHMARK, series_download, build

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
    watch=((r5>.005)&(r5>r5.shift(3))&(r20>r20.shift(5))&
           ((vr>1.2)|(vr5>1.1))&(c>m20*.96)&~falling&~heat).fillna(False)
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
    watch_start=None
    for i in range(65,len(d)):
        if bool(watch.iloc[i]) and not bool(watch.iloc[i-1]):
            watch_start=d.index[i].date().isoformat()
    reasons=[]
    if pd.notna(r5.iloc[-1]) and r5.iloc[-1]>.005:reasons.append("5일 상대강도 개선")
    if pd.notna(vr.iloc[-1]) and vr.iloc[-1]>1.2:reasons.append("당일 거래량 증가")
    if pd.notna(vr5.iloc[-1]) and vr5.iloc[-1]>1.1:reasons.append("5일 평균 거래량 증가")
    if pd.notna(r20.iloc[-1]) and pd.notna(r20.shift(5).iloc[-1]) and r20.iloc[-1]>r20.shift(5).iloc[-1]:reasons.append("20일 상대강도 가속")
    rs_score=float(np.clip(50+400*(r20.iloc[-1] if pd.notna(r20.iloc[-1]) else 0),0,100))
    vol_score=float(np.clip(50+35*np.log2(max(float(vr.iloc[-1]),.01)),0,100)) if pd.notna(vr.iloc[-1]) else 50.
    momentum=float(np.clip(50+600*(r5.iloc[-1] if pd.notna(r5.iloc[-1]) else 0),0,100))
    score=.45*rs_score+.30*vol_score+.25*momentum
    if stable[-1]=="과열":score*=.7
    if stable[-1]=="쇠퇴":score*=.6
    return {"cycle_stage":stable[-1],"cycle_score":round(score,1),
            "watch_active":bool(watch.iloc[-1]),"watch_first_seen":watch_start,"watch_reasons":reasons,
            "cycle_last_transition":changes[-1]["date"] if changes else None,
            "cycle_previous_stage":changes[-1]["from"] if changes else None,
            "cycle_transitions":changes[-30:],
            "cycle_metrics":{"rs_20d_pct":round(float(r20.iloc[-1])*100,2) if pd.notna(r20.iloc[-1]) else None,
                             "volume_ratio":round(float(vr.iloc[-1]),2) if pd.notna(vr.iloc[-1]) else None}}

def build_v4(fetch=series_download):
    cache={}
    def cached(t):
        if t not in cache:cache[t]=fetch(t)
        return cache[t]
    result=build(cached)
    for t in result["themes"]:
        try:t.update(detect(cached(t["ticker"]),cached(BENCHMARK[t["market"]])))
        except Exception as exc:result["errors"].append({"ticker":t["ticker"],"message":"V4: "+str(exc)[:160]})
    for market in BENCHMARK:
        group=sorted((t for t in result["themes"] if t["market"]==market and "cycle_score" in t),key=lambda t:t["cycle_score"],reverse=True)
        for rank,t in enumerate(group,1):t["market_rank"]=rank
    result["version"]="4.1"
    result["limitations"].extend(["조기 징후는 당일 미확정 신호이고, 단계 전환은 연속 2거래일 확인입니다.","사이클 단계는 ETF 가격·거래량 대용지표 기반 추정이며 기관 자금 흐름이 아닙니다.",
        "단계 전환은 연속 2거래일 확인 후 기록됩니다. 점수는 예측 확률이 아닙니다.",
        "실제 구성종목 동반 상승 및 기관·외국인 순매수는 미포함입니다."])
    if result["errors"] and result["status"]=="ok":result["status"]="partial"
    return result

if __name__=="__main__":
    result=build_v4()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("V4 themes",len(result["themes"]),"errors",len(result["errors"]))
    if result["status"]=="error":raise SystemExit(1)
