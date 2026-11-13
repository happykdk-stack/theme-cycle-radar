"""Optional ETF valuation observations. Never infer historical P/E from ETF price."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import yfinance as yf
from update import THEMES, ROOT

OUT=ROOT/"site"/"per_history.json"
PREVIOUS_URL="https://happykdk-stack.github.io/theme-cycle-radar/per_history.json"
FUTURES={"261220.KS","USO"}
MAX_POINTS=370

def valid_pe(value):
    try:
        x=float(value)
        return round(x,2) if math.isfinite(x) and 0<x<1000 else None
    except (ValueError,TypeError,OverflowError):
        return None

def previous_history():
    try:
        req=Request(PREVIOUS_URL+"?source=prior",headers={"User-Agent":"CycleDetector/1.0","Cache-Control":"no-cache"})
        with urlopen(req,timeout=12) as resp:
            payload=json.load(resp)
        if not isinstance(payload,dict) or not isinstance(payload.get("etfs"),dict):
            return {}, "Previous history response invalid"
        return payload["etfs"], None
    except Exception as exc:
        return {}, str(exc)[:160]

def fetch_pe(ticker):
    info=yf.Ticker(ticker).info or {}
    # Not every ETF exposes a valid underlying portfolio P/E.
    return valid_pe(info.get("trailingPE"))

def build(fetch=fetch_pe,prior=None,asof=None):
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
        if value is None and history:
            status="stale" if ticker not in FUTURES else "not_applicable"
        etfs[ticker]={"market":market,"theme":theme,"fund":fund,"ticker":ticker,
                      "pe":value,"status":status,"asof":date if value is not None else None,
                      "history":history,"error":err,
                      "source":"Yahoo Finance ETF quote trailingPE (provider methodology unverified)"}
    return {"version":"1.0","generated_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "history_source_error":history_error,"etfs":etfs,
            "note":"PER values are optional, unverified ETF quote fields, not verified holdings-weighted P/E. Historical observations begin when collected. Missing values are not estimated."}

if __name__=="__main__":
    data=build()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("ETF PER observed",sum(v["pe"] is not None for v in data["etfs"].values()),"of",len(data["etfs"]))
