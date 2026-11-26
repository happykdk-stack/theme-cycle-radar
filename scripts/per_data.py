"""Optional ETF valuation observations. Never infer historical P/E from ETF price."""
import json
import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import yfinance as yf
from update import THEMES, ROOT, series_download
from per_slopes import daily_per_slopes, LOOKBACK_SESSIONS

OUT=ROOT/"site"/"per_history.json"
PREVIOUS_URL="https://happykdk-stack.github.io/theme-cycle-radar/per_history.json"
FUTURES={"261220.KS","USO"}
MAX_POINTS=370
KRX_CSV=ROOT/"data"/"krx_index_per.csv"
HISTORY_CACHE=ROOT/"data"/"etf_per_history.json"
INDICES=[
 ("한국","코스피","^KS11"),("한국","코스닥","^KQ11"),("한국","코스피200","^KS200"),
 ("미국","S&P 500","^GSPC"),("미국","나스닥 종합","^IXIC"),
 ("미국","다우존스 산업평균","^DJI"),("미국","러셀 2000","^RUT")
]

def valid_pe(value):
    try:
        x=float(value)
        return round(x,2) if math.isfinite(x) and 0<x<1000 else None
    except (ValueError,TypeError,OverflowError):
        return None

def load_history_cache():
    try:
        payload=json.loads(HISTORY_CACHE.read_text(encoding='utf-8'))
        return payload['etfs'] if isinstance(payload.get('etfs'),dict) else {}
    except (OSError,ValueError,KeyError,TypeError):
        return {}


def write_history_cache(payload):
    snapshots={ticker:{'history':item.get('history',[]),
                       'pbr_history':item.get('pbr_history',[])}
               for ticker,item in payload['etfs'].items()}
    HISTORY_CACHE.parent.mkdir(parents=True,exist_ok=True)
    HISTORY_CACHE.write_text(json.dumps({'version':1,'source':'Yahoo Finance ETF quote observations',
        'etfs':snapshots},ensure_ascii=False,indent=2),encoding='utf-8')


def previous_history():
    cached=load_history_cache()
    try:
        req=Request(PREVIOUS_URL+"?source=prior",headers={"User-Agent":"CycleDetector/1.0","Cache-Control":"no-cache"})
        with urlopen(req,timeout=12) as resp:
            payload=json.load(resp)
        if not isinstance(payload,dict) or not isinstance(payload.get("etfs"),dict):
            return cached, "Previous history response invalid; using saved observations"
        combined=dict(cached)
        for ticker,item in payload['etfs'].items():
            if not isinstance(item,dict):continue
            old=cached.get(ticker,{})
            merged={**old,**item}
            for field,key in [('history','pe'),('pbr_history','pbr')]:
                unique={}
                for point in [*old.get(field,[]),*item.get(field,[])]:
                    if isinstance(point,dict) and isinstance(point.get('date'),str) and valid_pe(point.get(key)) is not None:
                        unique[point['date']]=point
                merged[field]=sorted(unique.values(),key=lambda p:p['date'])[-MAX_POINTS:]
            combined[ticker]=merged
        return combined, None
    except Exception as exc:
        return cached, str(exc)[:160]

def fetch_valuation(ticker):
    info=yf.Ticker(ticker).info or {}
    return {"pe":valid_pe(info.get("trailingPE")),
            "pbr":valid_pe(info.get("priceToBook"))}

def fetch_pe(ticker):
    return fetch_valuation(ticker)["pe"]

def price_context(ticker, fetch_prices):
    try:
        frame=fetch_prices(ticker)
        c=frame["Close"].astype(float).dropna()
        if len(c)<25: return {"prices":[],"rebounds":[],"error":"가격 이력 부족"}
        prices=[{"date":idx.date().isoformat(),"close":round(float(v),2)} for idx,v in c.tail(370).items()]
        # Retrospective 20-session low followed by 5% gain within 20 sessions.
        # Confirmation date is the first future close reaching the threshold.
        lows=c<=c.shift(1).rolling(20).min()
        events=[]
        last=-100
        for i in range(20,len(c)-1):
            if not bool(lows.iloc[i]) or i-last<20:continue
            base=float(c.iloc[i])
            for j in range(i+1,min(i+21,len(c))):
                if float(c.iloc[j])>=base*1.05:
                    events.append({"low_date":c.index[i].date().isoformat(),
                                   "confirmation_date":c.index[j].date().isoformat(),
                                   "low_close":round(base,2),
                                   "confirmation_close":round(float(c.iloc[j]),2),
                                   "rise_pct":round((float(c.iloc[j])/base-1)*100,2),
                                   "sessions":j-i})
                    last=i
                    break
        return {"prices":prices,"rebounds":events[-25:],"error":None}
    except Exception as exc:
        return {"prices":[],"rebounds":[],"error":str(exc)[:160]}


# Historical index valuations are separate from ETF quote PER and must retain provenance.
from html.parser import HTMLParser
from datetime import datetime as _dt

MULTPL_URL="https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
class _PERTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_row=False;self.in_cell=False;self.cells=[];self.rows=[];self.text=""
    def handle_starttag(self,tag,attrs):
        if tag=="tr":self.in_row=True;self.cells=[]
        if self.in_row and tag in ("td","th"):self.in_cell=True;self.text=""
    def handle_data(self,data):
        if self.in_cell:self.text+=data
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.in_cell:
            self.cells.append(self.text.strip());self.in_cell=False
        if tag=="tr" and self.in_row:
            if len(self.cells)>=2:self.rows.append(self.cells[:2])
            self.in_row=False

def parse_multpl(html):
    parser=_PERTable();parser.feed(html)
    found={}
    for date_text,pe_text in parser.rows:
        try:date=_dt.strptime(date_text.strip(),"%b %d, %Y").date().isoformat()
        except ValueError:continue
        # Do not mix estimated values with observed historical P/E.
        if "estimate" in pe_text.lower() or "†" in pe_text:continue
        import re
        match=re.search(r"(\d+(?:\.\d+)?)",pe_text)
        value=valid_pe(match.group(1)) if match else None
        if value is not None:found[date]={"date":date,"pe":value}
    return sorted(found.values(),key=lambda x:x["date"])

def krx_csv_pe(path=KRX_CSV):
    """Read licensed KRX index P/E observations; no network scraping or fabricated values.

    Explicit schema: date YYYY-MM-DD, ticker (^KS11/^KQ11/^KS200), pe, source.
    The source column must identify the supplied licensed KRX dataset.
    """
    result={}
    if not path.exists():return result
    with path.open("r",encoding="utf-8-sig",newline="") as handle:
        reader=csv.DictReader(handle)
        if not {"date","ticker","pe","source"}.issubset(reader.fieldnames or []):
            raise ValueError("KRX CSV requires date,ticker,pe,source")
        for row in reader:
            date=row["date"].strip()
            try:_dt.strptime(date,"%Y-%m-%d")
            except ValueError:raise ValueError("Invalid KRX PER date: "+date)
            ticker=row["ticker"].strip()
            if ticker not in {"^KS11","^KQ11","^KS200"}:continue
            source=row["source"].strip()
            if not source or "KRX" not in source.upper():raise ValueError("KRX provenance required")
            value=valid_pe(row["pe"])
            if value is None:continue
            entry=result.setdefault(ticker,{"history":[],"source":source,"frequency":"as supplied"})
            entry["history"].append({"date":date,"pe":value})
    for ticker,item in result.items():
        dedup={x["date"]:x for x in item["history"]}
        item["history"]=sorted(dedup.values(),key=lambda x:x["date"])
    return result


def ecos_index_pe(api_key, stat_code, item_code, start="200401", end=None):
    """Official ECOS StatisticSearch monthly series, configured with verified codes.

    Requires ECOS_API_KEY, ECOS_KOSPI_PER_STAT_CODE, ECOS_KOSPI_PER_ITEM_CODE.
    Missing credentials/codes never result in fabricated data.
    """
    from urllib.parse import quote
    if not all((api_key,stat_code,item_code)):return []
    end=end or datetime.now(timezone.utc).strftime("%Y%m")
    url="https://ecos.bok.or.kr/api/StatisticSearch/{}/json/kr/1/10000/{}/M/{}/{}/{}".format(
        quote(api_key,safe=""),quote(stat_code,safe=""),start,end,quote(item_code,safe=""))
    req=Request(url,headers={"User-Agent":"CycleDetector/1.0"})
    with urlopen(req,timeout=25) as response:payload=json.load(response)
    section=payload.get("StatisticSearch",{})
    rows=section.get("row",[])
    if not isinstance(rows,list):raise ValueError("ECOS StatisticSearch returned no rows")
    found={}
    for row in rows:
        month=str(row.get("TIME",""))
        if len(month)!=6 or not month.isdigit():continue
        value=valid_pe(row.get("DATA_VALUE"))
        if value is not None:found[month+"01"]={"date":month[:4]+"-"+month[4:]+"-01","pe":value}
    return sorted(found.values(),key=lambda x:x["date"])

def ecos_json(service,key,*parts):
    from urllib.parse import quote
    url="https://ecos.bok.or.kr/api/"+"/".join([service,quote(key,safe=""),"json","kr",*[quote(str(x),safe="") for x in parts]])
    with urlopen(Request(url,headers={"User-Agent":"CycleDetector/1.0"}),timeout=20) as response:
        return json.load(response)

def discover_ecos_kospi_per(key):
    """Discover a KOSPI P/E series only when table AND item labels confirm it."""
    payload=ecos_json("StatisticTableList",key,1,1500)
    rows=payload.get("StatisticTableList",{}).get("row",[])
    matches=[]
    for table in rows:
        name=str(table.get("STAT_NAME","")).replace(" ","")
        if table.get("SRCH_YN")!="Y" or not ("주가이익비율" in name or "주가수익비율" in name or "PER" in name.upper()):
            continue
        code=table.get("STAT_CODE")
        items=ecos_json("StatisticItemList",key,1,1000,code).get("StatisticItemList",{}).get("row",[])
        for item in items:
            label=" ".join(str(item.get(k,"")) for k in ("ITEM_NAME","ITEM_NAME1","ITEM_NAME2","ITEM_NAME3","ITEM_NAME4"))
            if "코스피" not in label.replace(" ","") and "KOSPI" not in label.upper() and "코스피" not in name:
                continue
            if "PER" not in (name+" "+label).upper() and "주가이익비율" not in name and "주가수익비율" not in name:
                continue
            item_code=item.get("ITEM_CODE") or item.get("ITEM_CODE1")
            if item_code and str(item.get("CYCLE","M")).upper() in ("M",""):
                matches.append((code,str(item_code),str(table.get("STAT_NAME",""))+" / "+label))
    if len(matches)!=1:
        raise ValueError("ECOS KOSPI PER code discovery ambiguous or unavailable: "+str(len(matches))+" matches")
    return matches[0]

def configured_ecos_pe():
    import os
    key=os.environ.get("ECOS_API_KEY","")
    code=os.environ.get("ECOS_KOSPI_PER_STAT_CODE","")
    item=os.environ.get("ECOS_KOSPI_PER_ITEM_CODE","")
    if not key:return {},{"ECOS":"ECOS_API_KEY missing; official KOSPI PER cannot be downloaded"}
    try:
        if not code or not item:
            code,item,discovered_name=discover_ecos_kospi_per(key)
        else:
            discovered_name="configured verified KOSPI PER"
        points=ecos_index_pe(key,code,item)
        if len(points)<12:raise ValueError("ECOS PER series has fewer than 12 observations")
        return {"^KS11":{"history":points,"source":"Bank of Korea ECOS StatisticSearch; "+discovered_name,"frequency":"monthly"}},{}
    except Exception as exc:
        return {},{"ECOS":str(exc)[:160]}

def historical_index_pe():
    result={}
    errors={}
    try:
        req=Request(MULTPL_URL,headers={"User-Agent":"Mozilla/5.0"})
        with urlopen(req,timeout=18) as response:raw=response.read().decode("utf-8","replace")
        observations=parse_multpl(raw)
        if len(observations)<12:raise ValueError("Historical S&P 500 PER table incomplete")
        if observations[-1]["date"]<"2025-01-01":raise ValueError("Historical S&P 500 PER table stale")
        result["^GSPC"]={"history":observations[-120:],"source":"Multpl.com / Robert Shiller, trailing 12-month reported earnings; monthly observations","frequency":"monthly"}
    except Exception as exc:errors["^GSPC"]=str(exc)[:160]
    return result,errors

def build(fetch=fetch_pe,prior=None,asof=None,fetch_prices=series_download,fetch_index_pe=historical_index_pe,fetch_pbr=None):
    date=asof or datetime.now(timezone.utc).date().isoformat()
    if prior is None:
        prior,history_error=previous_history()
    else:
        history_error=None
    etfs={}
    for market,theme,ticker,fund in THEMES:
        old=prior.get(ticker,{}) if isinstance(prior,dict) else {}
        points=[p for p in old.get("history",[]) if isinstance(p,dict) and isinstance(p.get("date"),str) and valid_pe(p.get("pe")) is not None and p["date"]<=date]
        unique={p["date"]:{"date":p["date"],"pe":valid_pe(p["pe"])} for p in points}
        status="unavailable";value=None;err=None
        if ticker in FUTURES:
            status="not_applicable"
        elif date in unique:
            value=unique[date]["pe"];status="observed"
        else:
            try:
                value=fetch(ticker)
                if value is not None:
                    unique[date]={"date":date,"pe":value};status="observed"
            except Exception as exc:
                err=str(exc)[:160]
        history=sorted(unique.values(),key=lambda p:p["date"])[-MAX_POINTS:]
        pbr_previous={v["date"]:{"date":v["date"],"pbr":valid_pe(v["pbr"])} for v in old.get("pbr_history",[]) if isinstance(v,dict) and "date" in v and valid_pe(v.get("pbr")) is not None}
        pbr_value=None
        if ticker not in FUTURES:
            try:
                pbr_value=(fetch_pbr(ticker) if fetch_pbr is not None else valid_pe((yf.Ticker(ticker).info or {}).get("priceToBook")))
                pbr_value=valid_pe(pbr_value)
                if pbr_value is not None:pbr_previous[date]={"date":date,"pbr":pbr_value}
            except Exception:pass
        pbr_history=sorted(pbr_previous.values(),key=lambda v:v["date"])[-MAX_POINTS:]
        if value is None and history:
            status="stale" if ticker not in FUTURES else "not_applicable"
        context=price_context(ticker,fetch_prices)
        etfs[ticker]={"market":market,"theme":theme,"fund":fund,"ticker":ticker,
                      "pe":value,"status":status,"asof":date if value is not None else None,
                      "history":history,"pbr":pbr_value,"pbr_history":pbr_history,"pbr_source":"Yahoo Finance priceToBook ETF quote (not verified portfolio PBR)","error":err,"price_context":context,
                      "source":"Yahoo Finance ETF quote trailingPE (provider methodology unverified)"}
        etfs[ticker]['per_slope_history'] = daily_per_slopes(history, market, date)
    index_pe,pe_errors=fetch_index_pe()
    indices={}
    for market,name,ticker in INDICES:
        ctx=price_context(ticker,fetch_prices)
        historical=index_pe.get(ticker,{})
        pe_points=[p for p in historical.get("history",[]) if p["date"]<=date]
        recent=pe_points[-1] if pe_points else None
        indices[ticker]={"market":market,"theme":name,"fund":name,"ticker":ticker,
                         "kind":"index","pe":recent["pe"] if recent else None,
                         "status":"historical_monthly" if recent else "unavailable",
                         "asof":recent["date"] if recent else None,"history":pe_points,"pbr":None,"pbr_history":[],"pbr_source":"No verified index PBR feed connected",
                         "price_context":ctx,"pe_error":pe_errors.get(ticker),
                         "source":historical.get("source","No verified historical index P/E feed connected"),
                         "pe_frequency":historical.get("frequency")}
    return {"version":"1.8","per_slope_lookback_sessions":LOOKBACK_SESSIONS,
            "per_slope_basis":"ETF quote observation dates; not verified closing valuation dates",
            "generated_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "history_source_error":history_error,"index_pe_errors":pe_errors,"etfs":etfs,"indices":indices,
            "note":"ETF PER observations start at collection. Index prices are genuine index levels. S&P 500 monthly historical trailing P/E is loaded from Multpl when available. Estimates are excluded. Korean index P/E is N/A until a licensed and validated source is connected. Other index P/E remains N/A. Rebound events are retrospective, not predictions."}

if __name__=="__main__":
    data=build()
    write_history_cache(data)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Index PER available:",[(k,v["pe"],v["asof"]) for k,v in data["indices"].items() if v["pe"] is not None])
    print("Index PER source errors:",data["index_pe_errors"])
    print("ETF PER observed",sum(v["pe"] is not None for v in data["etfs"].values()),"of",len(data["etfs"]))
