#!/usr/bin/env python3
"""StockPilot free-data momentum screener.

Builds a broad DAILY CANDIDATE pool from Yahoo Finance public predefined
screeners for US and Canadian markets, then scores daily price/volume history.

Important: this is NOT an exhaustive scan of every listed security. Yahoo's
public screener endpoints and Yahoo Finance history access are unofficial,
undocumented interfaces with changeable limits. Missing data is skipped; picks
are never fabricated. This is an educational screening tool, not advice.

Output contract retained for the existing GitHub Pages site:
  docs/data/picks.json: status, updated_at, data_source, main, penny, picks,
  watchlist, errors, plus transparent scan statistics.
"""

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import pstdev
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

OUTPUT = Path(os.environ.get("PICKS_OUTPUT", "docs/data/picks.json"))
SCREENER_COUNT = int(os.environ.get("SCREENER_COUNT", "75"))
SCREEN_QUOTA = int(os.environ.get("SCREEN_QUOTA", "25"))
MAX_CANDIDATES_PER_MARKET = int(os.environ.get("MAX_CANDIDATES_PER_MARKET", "100"))
DOWNLOAD_BATCH_SIZE = int(os.environ.get("DOWNLOAD_BATCH_SIZE", "25"))
PENNY_MAX_PRICE = float(os.environ.get("PENNY_MAX_PRICE", "10.00"))
PENNY_MIN_PRICE = 0.05
MAIN_MIN_AVG_DOLLAR_VOLUME = 1_000_000
PENNY_MIN_AVG_DOLLAR_VOLUME = 100_000
MIN_HISTORY = 55
# Yahoo's old "penny_stocks" predefined screen returns HTTP 404. Use supported
# activity screens, and supplement Canada with a maintained seed universe so a
# temporary/empty Canada-region screener cannot erase Canadian coverage.
SCREENER_IDS = ("most_actives", "day_gainers", "small_cap_gainers")
CANADIAN_SEED_TICKERS = {
    # Established TSX listings spanning finance, energy, infrastructure,
    # materials, technology, healthcare and consumer sectors.
    "RY.TO": ("Royal Bank of Canada", "Financial Services"),
    "TD.TO": ("Toronto-Dominion Bank", "Financial Services"),
    "BNS.TO": ("Bank of Nova Scotia", "Financial Services"),
    "BMO.TO": ("Bank of Montreal", "Financial Services"),
    "CM.TO": ("Canadian Imperial Bank of Commerce", "Financial Services"),
    "NA.TO": ("National Bank of Canada", "Financial Services"),
    "ENB.TO": ("Enbridge", "Energy"),
    "CNQ.TO": ("Canadian Natural Resources", "Energy"),
    "SU.TO": ("Suncor Energy", "Energy"),
    "IMO.TO": ("Imperial Oil", "Energy"),
    "CP.TO": ("Canadian Pacific Kansas City", "Industrials"),
    "CNR.TO": ("Canadian National Railway", "Industrials"),
    "BCE.TO": ("BCE", "Telecommunications"),
    "T.TO": ("TELUS", "Telecommunications"),
    "FTS.TO": ("Fortis", "Utilities"),
    "TRP.TO": ("TC Energy", "Energy"),
    "MFC.TO": ("Manulife Financial", "Financial Services"),
    "SLF.TO": ("Sun Life Financial", "Financial Services"),
    "SHOP.TO": ("Shopify", "Technology"),
    "CSU.TO": ("Constellation Software", "Technology"),
    "WCN.TO": ("Waste Connections", "Industrials"),
    "ATD.TO": ("Alimentation Couche-Tard", "Consumer Defensive"),
    "QSR.TO": ("Restaurant Brands International", "Consumer Cyclical"),
    "DOL.TO": ("Dollarama", "Consumer Defensive"),
    "GWO.TO": ("Great-West Lifeco", "Financial Services"),
    "IFC.TO": ("Intact Financial", "Financial Services"),
    "POW.TO": ("Power Corporation of Canada", "Financial Services"),
    "AEM.TO": ("Agnico Eagle Mines", "Basic Materials"),
    "ABX.TO": ("Barrick Mining", "Basic Materials"),
    "K.TO": ("Kinross Gold", "Basic Materials"),
    "NTR.TO": ("Nutrien", "Basic Materials"),
    "WPM.TO": ("Wheaton Precious Metals", "Basic Materials"),
    "CCO.TO": ("Cameco", "Energy"),
    "LUN.TO": ("Lundin Mining", "Basic Materials"),
    "TECK-B.TO": ("Teck Resources", "Basic Materials"),
    "AC.TO": ("Air Canada", "Industrials"),
    "WELL.TO": ("WELL Health Technologies", "Healthcare"),
    "HUT.TO": ("Hut 8", "Technology"),
    "BITF.TO": ("Bitfarms", "Technology"),
    "GLXY.TO": ("Galaxy Digital", "Financial Services"),
    "LSPD.TO": ("Lightspeed Commerce", "Technology"),
    "CTS.TO": ("Converge Technology Solutions", "Technology"),
    "DND.TO": ("Dye & Durham", "Technology"),
    "GIB-A.TO": ("CGI", "Technology"),
    "OTEX.TO": ("OpenText", "Technology"),
    "FNV.TO": ("Franco-Nevada", "Basic Materials"),
    "CTC-A.TO": ("Canadian Tire", "Consumer Cyclical"),
    "MG.TO": ("Magna International", "Consumer Cyclical"),
    "TFII.TO": ("TFI International", "Industrials"),
    "EQB.TO": ("EQB", "Financial Services"),
    "BIR.TO": ("Birchcliff Energy", "Energy"),
    "MEG.TO": ("MEG Energy", "Energy"),
    "PPL.TO": ("Pembina Pipeline", "Energy"),
    "IAG.TO": ("iA Financial", "Financial Services"),
    "MDA.TO": ("MDA Space", "Industrials"),
    "KXS.TO": ("Kinaxis", "Technology"),
    "DSG.TO": ("Descartes Systems Group", "Technology"),
    # Venture-listed names broaden the small-company/penny-stock candidate pool.
    "HIVE.V": ("HIVE Digital Technologies", "Technology"),
    "VNP.V": ("5N Plus", "Basic Materials"),
    "PNG.V": ("Kraken Robotics", "Technology"),
    "REAL.V": ("The Real Brokerage", "Technology"),
    "AYA.V": ("Aya Gold & Silver", "Basic Materials"),
    "NFG.V": ("New Found Gold", "Basic Materials"),
    "CSTR.V": ("Crestview Exploration", "Basic Materials"),
    "FOBI.V": ("Fobi AI", "Technology"),
}
USER_AGENT = "Mozilla/5.0 (compatible; StockPilot/3.0; +https://technofront.org)"


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def pct_change(new, old):
    return ((new / old) - 1.0) * 100.0 if old else 0.0


def yahoo_screener(region, screener_id):
    params = urlencode({
        "formatted": "false",
        "lang": "en-US",
        "region": region,
        "scrIds": screener_id,
        "count": SCREENER_COUNT,
        "start": 0,
    })
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?" + params
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload.get("finance", {}).get("result") or []
    if not result:
        err = payload.get("finance", {}).get("error")
        raise RuntimeError(f"Yahoo screener {region}/{screener_id}: {err or 'empty response'}")
    return result[0].get("quotes") or []


def normalize_symbol(raw_symbol, market, exchange):
    symbol = str(raw_symbol or "").strip().upper()
    if not symbol:
        return "", market
    ex = str(exchange or "").upper()
    # Trust the listing venue over the screener's regional label. The old
    # region-only suffixing could turn a US ticker such as T into T.TO.
    us_listing = any(x in ex for x in ("NASDAQ", "NYSE", "NEW YORK", "NYSEARCA", "NYSE ARCA"))
    ca_listing = any(x in ex for x in ("TORONTO", "TSX", "VENTURE", "TSXV", "CSE", "CANADIAN SECURITIES"))
    if us_listing:
        market = "US"
    elif ca_listing:
        market = "Canada"
    if market == "Canada" and "." not in symbol:
        if "VENTURE" in ex or "TSXV" in ex:
            symbol += ".V"
        elif "CSE" in ex or "CANADIAN SECURITIES" in ex:
            symbol += ".CN"
        else:
            symbol += ".TO"
    return symbol, market


def build_universe():
    records = {}
    errors = []
    scanned_screeners = 0
    for region, market in (("US", "US"), ("CA", "Canada")):
        market_records = {}
        for screen_id in SCREENER_IDS:
            try:
                quotes = yahoo_screener(region, screen_id)
                scanned_screeners += 1
                for q in quotes[:SCREEN_QUOTA]:
                    quote_type = str(q.get("quoteType") or "").upper()
                    if quote_type and quote_type not in ("EQUITY", "ETF"):
                        continue
                    raw = q.get("symbol")
                    exchange_name = q.get("fullExchangeName") or q.get("exchange") or ""
                    symbol, actual_market = normalize_symbol(raw, market, exchange_name)
                    if not symbol:
                        continue
                    # Prefer ordinary shares; ETFs are not stock picks.
                    if quote_type == "ETF":
                        continue
                    price = q.get("regularMarketPrice")
                    if price is None:
                        price = q.get("regularMarketPreviousClose")
                    try:
                        price = float(price)
                    except (TypeError, ValueError):
                        price = 0.0
                    meta = {
                        "ticker": symbol,
                        "company": q.get("longName") or q.get("shortName") or symbol,
                        "market": actual_market,
                        "exchange": exchange_name or ("US exchange" if actual_market == "US" else "Canadian exchange"),
                        "sector": q.get("sector") or q.get("industry") or "Unclassified",
                        "currency": q.get("currency") or ("USD" if actual_market == "US" else "CAD"),
                        "screener_price": price,
                    }
                    # Keep the richer metadata if a symbol appears in several screens.
                    old = market_records.get(symbol, {})
                    if len(str(meta.get("company", ""))) > len(str(old.get("company", ""))):
                        market_records[symbol] = meta
                    else:
                        old.update({k: v for k, v in meta.items() if v not in (None, "", "Unclassified")})
            except Exception as exc:
                errors.append(f"{market}/{screen_id}: {exc}")
            time.sleep(0.6)
        # Preserve screen priority: penny candidates are deliberately included first,
        # followed by active names and gainers. This avoids a price sort crowding them out.
        candidates = list(market_records.values())
        # A screener can return cross-listed securities. Route by the actual
        # exchange instead of assuming every CA-region result is Canadian.
        for item in candidates:
            records.setdefault(item["market"], [])
            if len(records[item["market"]]) < MAX_CANDIDATES_PER_MARKET:
                records[item["market"]].append(item)

    # Independent Canadian fallback universe. Yahoo's CA predefined screeners
    # can return no Canadian listings even when the request succeeds; seed
    # symbols are still checked against real daily Yahoo history and the same
    # liquidity/price filters before they can qualify.
    canada_records = {x["ticker"]: x for x in records.get("Canada", [])}
    for symbol, (company, sector) in CANADIAN_SEED_TICKERS.items():
        canada_records.setdefault(symbol, {
            "ticker": symbol,
            "company": company,
            "market": "Canada",
            "exchange": "TSX Venture" if symbol.endswith(".V") else "TSX",
            "sector": sector,
            "currency": "CAD",
            "screener_price": 0.0,
            "candidate_source": "Canadian listing seed universe",
        })
    records["Canada"] = list(canada_records.values())[:MAX_CANDIDATES_PER_MARKET]
    return records, errors, scanned_screeners


def _extract_ticker_frame(data, ticker):
    if data is None or data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        # yfinance has used both (field, ticker) and (ticker, field) layouts.
        for level in (0, 1):
            if ticker in data.columns.get_level_values(level):
                try:
                    frame = data.xs(ticker, axis=1, level=level, drop_level=True)
                    if not frame.empty:
                        return frame
                except Exception:
                    pass
        return pd.DataFrame()
    return data if len(data.columns) and len([ticker]) == 1 else pd.DataFrame()


def fetch_histories(symbols):
    histories = {}
    errors = []
    for start in range(0, len(symbols), DOWNLOAD_BATCH_SIZE):
        batch = symbols[start:start + DOWNLOAD_BATCH_SIZE]
        try:
            data = yf.download(
                tickers=batch,
                period="6mo",
                interval="1d",
                auto_adjust=True,
                actions=False,
                group_by="ticker",
                threads=2,
                progress=False,
                timeout=25,
                multi_level_index=True,
            )
        except Exception as exc:
            errors.append(f"History batch {batch[0]}…{batch[-1]}: {exc}")
            time.sleep(3)
            continue

        for symbol in batch:
            frame = _extract_ticker_frame(data, symbol)
            if frame.empty or "Close" not in frame.columns or "Volume" not in frame.columns:
                errors.append(f"{symbol}: no daily history returned")
                continue
            frame = frame.dropna(subset=["Close", "Volume"])
            if len(frame) < MIN_HISTORY:
                errors.append(f"{symbol}: only {len(frame)} daily rows; need {MIN_HISTORY}")
                continue
            histories[symbol] = frame
        time.sleep(2.0)
    return histories, errors


SEC_WORKER_BASE = os.environ.get("STOCKPILOT_SEC_API", "https://api.technofront.org")


def _metric_values(company, key):
    for metric in company.get("metrics", []):
        if metric.get("key") == key:
            return metric.get("values") or []
    return []


def fetch_sec_fundamentals(meta):
    """Fetch filed annual fundamentals through StockPilot's existing SEC Worker.
    Returns None when the ticker has no exact SEC match or the source is unavailable.
    """
    ticker = str(meta.get("ticker", "")).upper()
    # SEC company-ticker mapping is for US registrants and cross-filers. Avoid
    # fuzzy matches: a wrong CIK is worse than honestly reporting missing data.
    try:
        search_url = SEC_WORKER_BASE + "/api/search?" + urlencode({"q": ticker})
        req = Request(search_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urlopen(req, timeout=20) as response:
            matches = json.loads(response.read().decode("utf-8")).get("results", [])
        exact = [x for x in matches if str(x.get("ticker", "")).upper() == ticker]
        if not exact:
            return None
        cik = exact[0].get("cik")
        if not cik:
            return None
        company_url = SEC_WORKER_BASE + "/api/company?" + urlencode({"cik": cik})
        req = Request(company_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urlopen(req, timeout=30) as response:
            company = json.loads(response.read().decode("utf-8"))
        metrics = {key: _metric_values(company, key) for key in (
            "revenue", "grossProfit", "operatingIncome", "netIncome",
            "assets", "liabilities", "equity", "cash", "operatingCashFlow",
            "currentDebt", "longTermDebt"
        )}
        if not any(metrics.values()):
            return None
        latest = {key: (vals[0].get("value") if vals else None) for key, vals in metrics.items()}
        revenue_values = metrics["revenue"]
        revenue_growth = None
        if len(revenue_values) >= 2:
            prior = revenue_values[1].get("value")
            current = revenue_values[0].get("value")
            if prior not in (None, 0) and current is not None:
                revenue_growth = (float(current) / float(prior) - 1) * 100
        return {
            "source": "SEC EDGAR Company Facts",
            "company": company.get("company"),
            "cik": cik,
            "retrieved_at": company.get("retrievedAt"),
            "fiscal_year": revenue_values[0].get("fiscalYear") if revenue_values else None,
            "revenue_growth_percent": round(revenue_growth, 2) if revenue_growth is not None else None,
            "metrics": latest,
            "periods": {key: vals[:2] for key, vals in metrics.items()},
        }
    except Exception as exc:
        return {"_error": str(exc)}


def score_fundamentals(fundamentals):
    if not fundamentals or fundamentals.get("_error"):
        return None, [], []
    m = fundamentals.get("metrics", {})
    components = []
    details = []
    risks = []

    def add(name, value, weight):
        if value is not None and math.isfinite(float(value)):
            components.append((clamp(value), weight))
            details.append(name)

    growth = fundamentals.get("revenue_growth_percent")
    if growth is not None:
        add("revenue_growth", 50 + float(growth) * 1.25, 20)

    assets, liabilities = m.get("assets"), m.get("liabilities")
    equity, cash = m.get("equity"), m.get("cash")
    op_income, net_income = m.get("operatingIncome"), m.get("netIncome")
    revenue, op_cash = m.get("revenue"), m.get("operatingCashFlow")
    debt_current, debt_long = m.get("currentDebt"), m.get("longTermDebt")

    if revenue not in (None, 0) and m.get("grossProfit") is not None:
        add("gross_margin", float(m["grossProfit"]) / float(revenue) * 100 * 1.5 + 35, 15)
    if revenue not in (None, 0) and op_income is not None:
        margin = float(op_income) / float(revenue) * 100
        add("operating_margin", 50 + margin * 2.0, 20)
        if margin < 0:
            risks.append("negative operating margin in latest annual filing")
    if revenue not in (None, 0) and net_income is not None:
        margin = float(net_income) / float(revenue) * 100
        add("net_margin", 50 + margin * 1.5, 15)
        if margin < 0:
            risks.append("net loss in latest annual filing")
    if assets not in (None, 0) and liabilities is not None:
        liability_ratio = float(liabilities) / float(assets)
        add("liabilities_to_assets", 100 - liability_ratio * 100, 15)
        if liability_ratio > 0.8:
            risks.append("liabilities exceed 80% of reported assets")
    if assets not in (None, 0) and equity is not None:
        add("equity_ratio", float(equity) / float(assets) * 100, 5)
        if float(equity) < 0:
            risks.append("negative shareholders' equity")
    if op_cash is not None:
        add("operating_cash_flow", 75 if float(op_cash) > 0 else 20, 10)
        if float(op_cash) < 0:
            risks.append("negative operating cash flow")
    if cash is not None and (debt_current is not None or debt_long is not None):
        debt = float(debt_current or 0) + float(debt_long or 0)
        if debt > 0:
            add("cash_vs_debt", clamp(float(cash) / debt * 50), 5)
            if float(cash) < debt * 0.2:
                risks.append("cash is less than 20% of reported debt")
    # Avoid giving a company a filing-based score from only one or two
    # isolated facts; sparse disclosures remain market-data-only.
    if len(components) < 3:
        return None, details, ["insufficient SEC metric coverage for a balanced fundamental score"]
    total_weight = sum(weight for _, weight in components)
    score = sum(value * weight for value, weight in components) / total_weight
    return round(clamp(score), 1), details, risks


def calculate_rsi(closes, period=14):
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = changes[-period:]
    gains = sum(x for x in recent if x > 0) / period
    losses = -sum(x for x in recent if x < 0) / period
    if losses == 0:
        return 100.0 if gains else 50.0
    rs = gains / losses
    return 100.0 - (100.0 / (1.0 + rs))


def score_momentum(frame):
    closes = [float(x) for x in frame["Close"].tolist()]
    volumes = [float(x) for x in frame["Volume"].tolist()]
    dates = [x.strftime("%Y-%m-%d") for x in frame.index]
    last = closes[-1]
    ret5 = pct_change(last, closes[-6])
    ret20 = pct_change(last, closes[-21])
    ret50 = pct_change(last, closes[-51])
    daily_change = pct_change(last, closes[-2])
    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50
    rsi14 = calculate_rsi(closes)
    avg_volume20 = sum(volumes[-20:]) / 20
    volume_ratio = volumes[-1] / avg_volume20 if avg_volume20 else 0.0
    avg_dollar_volume20 = sum(closes[i] * volumes[i] for i in range(len(closes) - 20, len(closes))) / 20
    daily_returns = [pct_change(closes[i], closes[i - 1]) for i in range(len(closes) - 20, len(closes))]
    volatility20 = pstdev(daily_returns) if daily_returns else 0.0
    # Trend-quality and trading-conditions score. Absolute price spikes no
    # longer dominate: trend alignment and sustained returns matter more.
    trend_alignment = (50 if last > ma20 else 0) + (50 if ma20 > ma50 else 0)
    score_trend = clamp(trend_alignment)
    score_50d = clamp(50 + ret50 * 1.2)
    score_20d = clamp(50 + ret20 * 1.6)
    score_5d = clamp(50 + ret5 * 1.5)
    score_relative_volume = clamp(50 + 20 * math.log2(max(volume_ratio, 0.01)))
    score_liquidity = clamp(50 + 10 * math.log10(max(avg_dollar_volume20, 1.0) / 1_000_000))
    volatility_penalty = min(12.0, max(0.0, volatility20 - 4.0) * 0.8)
    technical = clamp(
        score_trend * .25 + score_50d * .20 + score_20d * .20
        + score_5d * .10 + score_relative_volume * .10
        + score_liquidity * .15 - volatility_penalty
    )
    return {
        "score_technical": round(technical, 1),
        "score": round(technical, 1),
        "return_5d": round(ret5, 2),
        "return_20d": round(ret20, 2),
        "return_50d": round(ret50, 2),
        "change_percent": round(daily_change, 2),
        "rsi": round(rsi14, 1),
        "volume_ratio": round(volume_ratio, 2),
        "average_volume_20d": round(avg_volume20),
        "average_dollar_volume_20d": round(avg_dollar_volume20, 2),
        "volatility_20d": round(volatility20, 2),
        "above_20day_average": last > ma20,
        "above_50day_average": last > ma50,
        "ma20": round(ma20, 4),
        "ma50": round(ma50, 4),
        "price_date": dates[-1],
        "price": round(last, 4 if last < 1 else 2),
        "volume": int(volumes[-1]),
    }


def analyze(meta, frame, fundamentals=None, penny=False):
    m = score_momentum(frame)
    fundamental_score, fundamental_coverage, fundamental_risks = score_fundamentals(fundamentals)
    # Use filings when an exact SEC registrant match exists. Canadian issuers
    # without SEC filings remain technical-only; never infer or fabricate facts.
    if fundamental_score is not None:
        fundamental_weight = 0.30 if penny else 0.60
        m["score"] = round(m["score_technical"] * (1 - fundamental_weight) + fundamental_score * fundamental_weight, 1)
        m["score_basis"] = "SEC fundamentals + market data"
        m["score_fundamental"] = fundamental_score
        m["fundamental_coverage"] = fundamental_coverage
        m["fundamental_confidence"] = "higher" if len(fundamental_coverage) >= 6 else "moderate"
    else:
        m["score"] = m["score_technical"]
        m["score_basis"] = "market data only — SEC fundamentals unavailable or insufficient"
        m["score_fundamental"] = None
        m["fundamental_coverage"] = fundamental_coverage
        m["fundamental_confidence"] = "not rated"
    # Keep the latest 63 daily adjusted closes (approximately three trading months)
    # for compact, data-backed sparklines on the homepage stock cards.
    chart_frame = frame.dropna(subset=["Close"]).tail(63)
    chart_history = [
        {"date": date.strftime("%Y-%m-%d"), "close": round(float(close), 6)}
        for date, close in zip(chart_frame.index, chart_frame["Close"].tolist())
    ]
    reasons = []
    reasons.append(f"daily price move {m['change_percent']:+.2f}%")
    reasons.append(f"relative volume {m['volume_ratio']:.1f}x its 20-day average")
    reasons.append(f"5-day move {m['return_5d']:+.1f}%")
    if m["average_dollar_volume_20d"] > 0:
        reasons.append(f"20-day average dollar volume ${m['average_dollar_volume_20d']:,.0f}")
    risks = list(fundamental_risks)
    if m["rsi"] >= 70:
        risks.append("RSI elevated; short-term pullback risk")
    if m["volatility_20d"] >= 5:
        risks.append("high recent volatility")
    if not m["above_50day_average"]:
        risks.append("price below 50-day average")
    if m["return_20d"] < 0:
        risks.append("negative 20-day momentum")
    if not risks:
        risks.append("normal market and company-specific risks remain")
    return {
        "ticker": meta["ticker"],
        "company": meta["company"],
        "exchange": meta["exchange"],
        "market": meta["market"],
        "sector": meta["sector"],
        "currency": meta["currency"],
        "quote_time": m["price_date"] + " (daily close)",
        "reason": "; ".join(reasons or ["highest momentum score in the screened candidate pool"]) + ".",
        "risk": "; ".join(risks) + ".",
        "price_history_3mo": chart_history,
        "fundamentals": fundamentals if fundamentals and not fundamentals.get("_error") else None,
        **m,
    }


def eligible(stock, penny=False):
    # Keep the list liquid enough to be useful, but do not require positive
    # momentum: active gainers AND decliners can qualify for a market-activity screen.
    if penny:
        return (PENNY_MIN_PRICE <= stock["price"] <= PENNY_MAX_PRICE
                and stock["average_dollar_volume_20d"] >= PENNY_MIN_AVG_DOLLAR_VOLUME
                and stock["average_volume_20d"] >= 50_000)
    return stock["price"] > PENNY_MAX_PRICE and stock["average_dollar_volume_20d"] >= MAIN_MIN_AVG_DOLLAR_VOLUME


def choose_diversified(ranked, count=3):
    chosen, markets, sectors = [], {}, {}
    for stock in ranked:
        if markets.get(stock["market"], 0) >= 2 or sectors.get(stock["sector"], 0) >= 1:
            continue
        chosen.append(stock)
        markets[stock["market"]] = markets.get(stock["market"], 0) + 1
        sectors[stock["sector"]] = sectors.get(stock["sector"], 0) + 1
        if len(chosen) == count:
            return chosen
    for stock in ranked:
        if stock not in chosen:
            chosen.append(stock)
        if len(chosen) == count:
            break
    return chosen


def main():
    print("StockPilot Multi-Factor Research v5 — US + Canada candidate screeners")
    universe, universe_errors, screeners_ok = build_universe()
    all_meta = universe.get("US", []) + universe.get("Canada", [])
    # Remove duplicate symbols while preserving first occurrence.
    unique = {x["ticker"]: x for x in all_meta}
    all_meta = list(unique.values())
    print(f"Screeners responding: {screeners_ok}/{len(SCREENER_IDS) * 2}")
    print(f"Candidates queued: {len(all_meta)} (US {len(universe.get('US', []))}; Canada {len(universe.get('Canada', []))})")
    if len(all_meta) < 20:
        sys.exit("ERROR: Too few candidates returned by public screeners; existing picks.json left unchanged.")

    histories, history_errors = fetch_histories([x["ticker"] for x in all_meta])
    results = []
    meta_by_symbol = {x["ticker"]: x for x in all_meta}

    # SEC fundamentals are retrieved only through the existing StockPilot SEC
    # Worker. Limit concurrency to respect upstream SEC fair-access limits.
    fundamentals_by_symbol = {}
    sec_candidates = [x for x in all_meta if x["market"] == "US"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch_sec_fundamentals, meta): meta["ticker"] for meta in sec_candidates}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                if result and not result.get("_error"):
                    fundamentals_by_symbol[ticker] = result
                elif result and result.get("_error"):
                    history_errors.append(f"{ticker}: SEC fundamentals unavailable: {result['_error']}")
            except Exception as exc:
                history_errors.append(f"{ticker}: SEC fundamentals unavailable: {exc}")

    for symbol, frame in histories.items():
        try:
            meta = meta_by_symbol[symbol]
            results.append(analyze(meta, frame, fundamentals_by_symbol.get(symbol), penny=eligible({"price": float(frame["Close"].iloc[-1]), "average_dollar_volume_20d": float((frame["Close"].tail(20) * frame["Volume"].tail(20)).mean()), "average_volume_20d": float(frame["Volume"].tail(20).mean())}, True)))
        except Exception as exc:
            history_errors.append(f"{symbol}: analysis failed: {exc}")

    main_ranked = sorted([x for x in results if eligible(x, False)], key=lambda x: x["score"], reverse=True)
    penny_ranked = sorted([x for x in results if eligible(x, True)], key=lambda x: x["score"], reverse=True)
    main_picks = choose_diversified(main_ranked, 3)
    selected = {x["ticker"] for x in main_picks}
    penny_ranked = [x for x in penny_ranked if x["ticker"] not in selected]
    penny_picks = choose_diversified(penny_ranked, 3)

    # One independent Stock of the Day per market. Prefer a main-list eligible
    # company; if that market has none, use its highest-ranked qualifying penny
    # stock and label the fallback so the page never silently shows the other
    # market's pick.
    stock_of_day = {}
    for market in ("US", "Canada"):
        market_main = [x for x in main_ranked if x["market"] == market]
        market_penny = [x for x in penny_ranked if x["market"] == market]
        chosen_day = (market_main or market_penny)
        if chosen_day:
            featured = dict(chosen_day[0])
            featured["selection_type"] = "main stock" if market_main else "penny stock fallback"
            stock_of_day[market] = featured

    if len(main_picks) < 3:
        sys.exit("ERROR: Fewer than 3 main stocks passed the filters; existing picks.json left unchanged.")
    for stock in penny_picks:
        stock["risk"] = "HIGH RISK — penny-stock volatility. " + stock["risk"]

    now = datetime.now(timezone.utc)
    output = {
        "status": "ok",
        "updated_at": now.isoformat(),
        "snapshot_time": now.date().isoformat(),
        "data_source": "Yahoo Finance public screeners and daily prices (via yfinance); SEC EDGAR Company Facts through StockPilot SEC Worker where an exact US filing match exists",
        "data_note": (
            "Candidate scan uses Yahoo Finance activity/gainer screeners plus a maintained "
            "Canadian TSX/TSXV symbol seed list. This is not an exhaustive scan of every listing. "
            "Every seed candidate must still return real daily price history and pass the same "
            "liquidity and price filters. Yahoo endpoints are unofficial and data may be delayed. "
            "SEC annual fundamentals are included only when an exact SEC ticker match is available; "
            "other issuers are explicitly marked market-data-only. Prices use local trading currencies."
        ),
        "strategy": (
            "Multi-factor score 0–100. Technical score: 25% trend alignment, 20% 50-day return, "
            "20% 20-day return, 10% 5-day return, 10% relative volume, and 15% liquidity, less a "
            "volatility penalty. Where exact SEC annual fundamentals are available, the main-stock "
            "score blends 60% filing-based financial health/growth/profitability with 40% technical "
            "conditions; penny stocks blend 30% fundamentals with 70% technical conditions. "
            "Without SEC fundamentals, the score is technical-only and is explicitly labelled. "
            "Main stocks require 20-day average dollar volume of at least $1 million; penny stocks "
            "must be $0.05–$10 with at least $100,000 average daily dollar volume. Stock of the Day "
            "is selected independently for each market from that market's highest-ranked eligible "
            "main stock, with a clearly labelled penny-stock fallback only if necessary."
        ),
        "universe": {
            "markets": ["US", "Canada"],
            "candidate_sources": list(SCREENER_IDS) + ["Canadian TSX/TSXV seed universe"],
            "us_candidates_queued": len(universe.get("US", [])),
            "canada_candidates_queued": len(universe.get("Canada", [])),
            "canadian_seed_symbols": len(CANADIAN_SEED_TICKERS),
            "unique_candidates_queued": len(all_meta),
            "history_symbols_returned": len(histories),
            "sec_fundamentals_returned": len(fundamentals_by_symbol),
            "sec_fundamentals_coverage": round(len(fundamentals_by_symbol) / max(1, len([x for x in results if x["market"] == "US"])) * 100, 1),
            "penny_price_cap_local_currency": PENNY_MAX_PRICE,
            "exhaustive_market_scan": False,
        },
        "main": main_picks,
        "penny": penny_picks,
        "stock_of_day": stock_of_day,
        "picks": main_picks,
        "watchlist": main_ranked,
        "penny_watchlist": penny_ranked,
        "main_candidates_scanned": len(results),
        "main_candidates_eligible": len(main_ranked),
        "penny_candidates_scanned": len(results),
        "penny_candidates_eligible": len(penny_ranked),
        "errors": universe_errors + history_errors,
        "penny_errors": [],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    temp.write_text(json.dumps(output, indent=2), encoding="utf-8")
    temp.replace(OUTPUT)
    print(f"SUCCESS: {len(main_picks)}/3 main picks; {len(penny_picks)}/3 penny picks")
    print(f"History downloaded for {len(histories)}/{len(all_meta)} candidates")
    print(f"Output: {OUTPUT}")
    if len(penny_picks) < 3:
        print("WARNING: fewer than 3 penny stocks qualified; no picks were fabricated.")


if __name__ == "__main__":
    main()
