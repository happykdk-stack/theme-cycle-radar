"""Cycle Radar 3.0: selective pullback/recovery signals, retaining V1 and V2 history."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from update import OUT, BENCHMARK, series_download
from update_v2 import build_v2

HORIZONS=(3,5,7,10,15,20,30)
MIN_TRAIN=8
MIN_TEST=3

def horizon_report(events):
    """Chronological 70/30 split; evaluate all horizons on identical matured events."""
    complete=[e for e in events if all(e.get(f'return_{h}d_pct') is not None for h in HORIZONS)]
    cutoff=int(len(complete)*0.7)
    train,test=complete[:cutoff],complete[cutoff:]
    def summarize(rows,h):
        a=[float(e[f'return_{h}d_pct']) for e in rows]
        return {'count':len(a),'win_rate_pct':round(100*sum(x>0 for x in a)/len(a),1) if a else None,
                'avg_return_pct':round(sum(a)/len(a),2) if a else None}
    table=[{'days':h,'train':summarize(train,h),'test':summarize(test,h)} for h in HORIZONS]
    if len(train)<MIN_TRAIN or len(test)<MIN_TEST:
        return {'status':'insufficient','message':f'동일 기간 평가 가능한 신호 {len(complete)}건 (학습 {len(train)}, 검증 {len(test)}). 최소 {MIN_TRAIN}+{MIN_TEST}건 필요', 'best_days':None,'table':table}
    # Only positive average-return candidates; win rate is primary, mean return tie-break.
    eligible=[x for x in table if x['train']['avg_return_pct']>0]
    if not eligible:
        return {'status':'no_edge','message':'학습 구간 평균 수익률이 양수인 보유 기간이 없습니다.', 'best_days':None,'table':table}
    best=max(eligible,key=lambda x:(x['train']['win_rate_pct'],x['train']['avg_return_pct']))
    return {'status':'evaluated','message':'학습 구간에서 선정, 검증 구간은 독립 평가. 과거 성과는 미래를 보장하지 않습니다.', 'best_days':best['days'],'table':table}


def calculate_v3(df, benchmark):
    d=df.sort_index().copy()
    c=d["Close"].astype(float)
    o=d["Open"].astype(float)
    v=d["Volume"].astype(float)
    b=benchmark["Close"].reindex(d.index).ffill().astype(float)
    m5=c.rolling(5).mean()
    m20=c.rolling(20).mean()
    m60=c.rolling(60).mean()
    rs=c/b
    rs5=rs.pct_change(5)
    rs20=rs.pct_change(20)
    rs60=rs.pct_change(60)
    volratio=v/v.shift(1).rolling(20).mean().replace(0,np.nan)
    ret=c.pct_change()
    market_ok=(b>b.rolling(60).mean())&(b.rolling(20).mean()>b.rolling(20).mean().shift(5))
    trend=(c>m20)&(m20>m60)&(m20>m20.shift(5))
    strong=(rs20>0.025)&(rs60>0.035)&(rs5>0)
    # A recovery after a modest 5-day pullback in an established uptrend.
    recent_pullback=(c.shift(1)<m5.shift(1)) | (ret.shift(1)<-0.012)
    recovery=(c>m5)&(c>c.shift(1))&(ret>0)
    interest=(volratio>1.05)&(volratio<3.5)
    overheat=(c/m20>1.15)|(c.pct_change(5)>0.12)
    setup=(trend&strong&recent_pullback&recovery&interest&market_ok&~overheat).fillna(False)
    signals=np.zeros(len(d),dtype=bool)
    last=-100
    for i,flag in enumerate(setup.to_numpy()):
        if i>=85 and flag and i-last>8:
            signals[i]=True
            last=i
    # 5/20/60-day scores; scores describe conditions, not calibrated probabilities.
    relative_score=(50+400*rs20.fillna(0)+180*rs60.fillna(0)).clip(0,100)
    volume_score=(50+35*np.log2(volratio.clip(lower=.01))).clip(0,100).fillna(50)
    trend_score=(25*(c>m20).astype(int)+25*(m20>m60).astype(int)+
                 25*(m20>m20.shift(5)).astype(int)+25*(c>m5).astype(int))
    regime_score=market_ok.astype(float)*100
    heat_score=(~overheat).astype(float)*100
    score=(.30*relative_score+.20*volume_score+.25*trend_score+
           .15*regime_score+.10*heat_score).clip(0,100)
    # 5/20 sessions after signal, enter next open. No forward data in signals.
    events=[]
    for i in np.flatnonzero(signals):
        entry=float(o.iloc[i+1]) if i+1<len(d) and pd.notna(o.iloc[i+1]) and o.iloc[i+1]>0 else None
        def outcome(n):
            if entry is None or i+n>=len(d):return None
            return round((float(c.iloc[i+n])/entry-1)*100,2)
        events.append({"date":d.index[i].date().isoformat(),
                       **{f"return_{n}d_pct":outcome(n) for n in HORIZONS},
                       "entry_basis":"next_open"})
    def summary(n):
        a=[x[f"return_{n}d_pct"] for x in events if x[f"return_{n}d_pct"] is not None]
        return {"count":len(a),"win_rate_pct":round(100*sum(x>0 for x in a)/len(a),1) if a else None,
                "avg_return_pct":round(sum(a)/len(a),2) if a else None}
    last_idx=-1
    return {
        "score_v3":round(float(score.iloc[-1]),1),
        "stage_v3":("과열 경고" if bool(overheat.iloc[-1]) else
                    "진입 후보" if bool(signals[-1]) else
                    "상승 관찰" if bool(trend.iloc[-1]) and bool(strong.iloc[-1]) else
                    "시장 방어" if not bool(market_ok.iloc[-1]) else "관찰"),
        "last_signal_v3":events[-1]["date"] if events else None,
        "signals_v3":events[-100:],
        "stats_v3":{f"{n}d":summary(n) for n in HORIZONS},
        "holding_period_v3":horizon_report(events),
        "v3_conditions":{"market_uptrend":bool(market_ok.iloc[-1]),
                         "relative_strength_20d_pct":round(float(rs20.iloc[-1])*100,2) if pd.notna(rs20.iloc[-1]) else None,
                         "volume_ratio":round(float(volratio.iloc[-1]),2) if pd.notna(volratio.iloc[-1]) else None,
                         "pullback_recovery":bool(recent_pullback.iloc[-1] and recovery.iloc[-1])}
    }

def build_v3(fetch=series_download):
    cache={}
    def cached(ticker):
        if ticker not in cache:cache[ticker]=fetch(ticker)
        return cache[ticker]
    result=build_v2(cached)
    for t in result["themes"]:
        try:
            t.update(calculate_v3(cached(t["ticker"]),cached(BENCHMARK[t["market"]])))
        except Exception as exc:
            result["errors"].append({"ticker":t["ticker"],"message":"V3: "+str(exc)[:160]})
    result["version"]="3.1"
    result["limitations"].extend([
        "V3는 시장 추세, 5·20·60일 상대강도, 눌림목 회복을 사용하는 실험적 보수형 신호입니다.",
        "V3.1은 3·5·7·10·15·20·30거래일을 비교합니다. 학습 70%에서 적중률 우선·평균수익률 양수 조건으로 기간을 선정하고, 뒤의 30%에서 검증합니다.",
        "모든 기간을 공정하게 비교하기 위해 30거래일 이상 경과한 동일 신호만 기간 선정에 사용합니다. 최소 학습 8건·검증 3건 미달 시 추천하지 않습니다.",
        "V3 수익률은 신호 다음 거래일 시가 진입, 5·20거래일 종가 청산 가정이며 수수료·슬리피지·세금은 미반영입니다.",
        "V1은 신호일 종가 기준으로 계산되므로 V3와 직접적인 수익률 비교가 불공정합니다.",
        "ETF 단위 신호이므로 구성종목 확산, 외국인·기관 실매수 및 실제 테마 전체의 자금 흐름은 측정하지 않습니다."
    ])
    if result["errors"] and result["status"]=="ok":result["status"]="partial"
    return result

if __name__=="__main__":
    result=build_v3()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(f"V3 generated {len(result['themes'])} themes; {len(result['errors'])} errors")
    if result["status"]=="error":raise SystemExit(1)
