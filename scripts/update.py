"""Download daily ETF prices and build transparent theme rotation signals."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'site' / 'data.json'
# Listed ETFs are proxies, not exhaustive sector indices. Verify listings periodically.
THEMES = [
    ('한국','반도체','091160.KS','KODEX 반도체'),
    ('한국','2차전지','305720.KS','KODEX 2차전지산업'),
    ('한국','바이오','244580.KS','KODEX 바이오'),
    ('한국','로봇','445290.KS','KODEX K-로봇액티브'),
    ('한국','방산','449450.KS','PLUS K방산'),
    ('한국','원전','433500.KS','ACE 원자력테마딥서치'),
    ('미국','반도체','SOXX','iShares Semiconductor ETF'),
    ('미국','AI·로봇','BOTZ','Global X Robotics & AI ETF'),
    ('미국','바이오','XBI','SPDR S&P Biotech ETF'),
    ('미국','방산','ITA','iShares U.S. Aerospace & Defense ETF'),
    ('미국','원전·우라늄','URA','Global X Uranium ETF'),
    ('미국','사이버보안','CIBR','First Trust Nasdaq Cybersecurity ETF'),
    ('미국','2차전지·리튬','LIT','Global X Lithium & Battery Tech ETF'),
    ('미국','클라우드','SKYY','First Trust Cloud Computing ETF'),
]
BENCHMARK = {'한국':'069500.KS','미국':'SPY'}

def series_download(symbol):
    frame = yf.download(symbol, period='18mo', interval='1d', auto_adjust=True,
                        progress=False, threads=False, timeout=20)
    if frame is None or frame.empty:
        raise ValueError('가격 데이터 없음')
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame[['Close','Volume']].copy().dropna()
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = frame[~frame.index.duplicated(keep='last')].sort_index()
    if len(frame)<45: raise ValueError('분석에 필요한 45거래일 미만')
    if (frame['Close']<=0).any(): raise ValueError('잘못된 가격')
    return frame

def clamp(v): return round(float(np.clip(v,0,100)),1)

def analyze(df, bench, market, theme, symbol, label):
    df=df.copy()
    df['ret']=df.Close.pct_change()
    df['v_ratio']=df.Volume / df.Volume.shift(1).replace(0,np.nan)
    # Exact alert rule requested by user: +3% and 1.5x prior-day volume.
    df['signal']=(df.ret>=.03)&(df.v_ratio>=1.5)
    bench=bench.Close.reindex(df.index,method='ffill')
    relative=(df.Close/df.Close.shift(20))/(bench/bench.shift(20))-1
    current=df.iloc[-1]
    v20=df.Volume.tail(20).mean()
    vscore=clamp(50+30*np.log2(max(float(current.Volume)/max(v20,1),.01)))
    rs=clamp(50+float(relative.iloc[-1])*250) if pd.notna(relative.iloc[-1]) else 50
    # No institutional/foreign flow API: use volume-weighted price pressure as PROXY.
    pressure=(np.sign(df.ret.fillna(0))*df.Volume).tail(10).sum()/max(df.Volume.tail(10).sum(),1)
    flow=clamp(50+50*pressure)
    # Breadth unavailable from single ETF: neutral 50, explicitly disclosed.
    breadth=50.0
    persistence=clamp(100*float((df.ret.tail(10)>0).mean()))
    score=round(.30*vscore+.25*rs+.20*flow+.15*breadth+.10*persistence,1)
    stage='상승 확산 후보' if score>=75 else '초기 유입 후보' if score>=60 else '관찰' if score>=40 else '약세'
    signals=[]
    for pos in np.flatnonzero(df.signal.to_numpy()):
        if pos<20: continue
        row=df.iloc[pos]
        def future(days):
            if pos+days>=len(df): return None
            return round((float(df.Close.iloc[pos+days])/float(row.Close)-1)*100,2)
        signals.append({'date':df.index[pos].date().isoformat(),
                        'rise_pct':round(float(row.ret)*100,2),
                        'volume_multiple':round(float(row.v_ratio),2),
                        'return_5d_pct':future(5),'return_20d_pct':future(20)})
    return {'market':market,'theme':theme,'ticker':symbol,'fund':label,
            'asof':df.index[-1].date().isoformat(), 'close':round(float(current.Close),2),
            'daily_return_pct':round(float(current.ret)*100,2),
            'score':score,'stage':stage,
            'components':{'volume':vscore,'relative_strength':rs,'flow_proxy':flow,
                          'breadth_neutral':breadth,'persistence':persistence},
            'last_signal':signals[-1]['date'] if signals else None,
            'signals':signals[-100:]}

def build(fetch=series_download):
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    result={'generated_at_utc':now,'method':'ETF daily close >=3% and volume >=1.5x previous session',
            'status':'ok','themes':[],'errors':[],
            'limitations':['ETF는 테마 대용지표이며 개별 종목 전체를 대표하지 않습니다.',
                           '수급 점수는 기관/외국인 순매수가 아닌 거래량 가중 가격방향 대리지표입니다.',
                           '테마 내 확산 데이터가 없어 해당 점수는 중립값 50으로 고정합니다.',
                           '과거 신호 수익률은 신호일 종가 대비이며 거래비용·슬리피지 미반영입니다.',
                           '점수 가중치와 단계 경계는 검증된 예측 모델이 아닙니다.']}
    benchmarks={}
    for market,symbol in BENCHMARK.items():
        try: benchmarks[market]=fetch(symbol)
        except Exception as exc: result['errors'].append({'ticker':symbol,'message':str(exc)[:180]})
    for market,theme,symbol,label in THEMES:
        try:
            if market not in benchmarks: raise ValueError('시장 벤치마크 조회 실패')
            result['themes'].append(analyze(fetch(symbol),benchmarks[market],market,theme,symbol,label))
        except Exception as exc: result['errors'].append({'ticker':symbol,'theme':theme,'message':str(exc)[:180]})
    if not result['themes']: result['status']='error'
    elif result['errors']: result['status']='partial'
    return result

if __name__=='__main__':
    data=build()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(f"Saved {len(data['themes'])} themes; {len(data['errors'])} errors; status={data['status']}")
    if data['status']=='error': raise SystemExit(1)
