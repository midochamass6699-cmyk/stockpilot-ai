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
SCREENER_IDS = ("penny_stocks", "most_actives", "day_gainers", "small_cap_gainers")
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
        return ""
    # Yahoo's Canadian quote pages conventionally use .TO for TSX and .V for TSXV.
    if market == "Canada" and "." not in symbol:
        ex = str(exchange or "").upper()
        if "VENTURE" in ex or "TSXV" in ex:
            symbol += ".V"
        elif "CSE" in ex:
            symbol += ".CN"
        else:
            symbol += ".TO"
    return symbol


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
                    symbol = normalize_symbol(raw, market, q.get("fullExchangeName") or q.get("exchange"))
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
                        "market": market,
                        "exchange": q.get("fullExchangeName") or q.get("exchange") or ("US exchange" if market == "US" else "Canadian exchange"),
                        "sector": q.get("sector") or q.get("industry") or "Unclassified",
                        "currency": q.get("currency") or ("USD" if market == "US" else "CAD"),
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
        records[market] = candidates[:MAX_CANDIDATES_PER_MARKET]
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
    # Activity-first score: prioritize unusual participation and meaningful
    # current price movement, not long-term trend or company fundamentals.
    score_relative_volume = clamp(50 + 25 * math.log2(max(volume_ratio, 0.01)))
    score_daily_move = clamp(abs(daily_change) * 8.0)
    score_5d_activity = clamp(abs(ret5) * 4.0)
    score_20d_activity = clamp(abs(ret20) * 1.5)
    score_liquidity = clamp(50 + 10 * math.log10(max(avg_dollar_volume20, 1.0) / 1_000_000))
    volatility_penalty = min(8.0, max(0.0, volatility20 - 5.0) * 0.6)
    raw = (
        score_relative_volume * .35
        + score_daily_move * .30
        + score_5d_activity * .20
        + score_20d_activity * .10
        + score_liquidity * .05
    )
    return {
        "score": round(clamp(raw - volatility_penalty), 1),
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


def analyze(meta, frame):
    m = score_momentum(frame)
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
    risks = []
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
    print("StockPilot Market Activity v4 — public US + Canada candidate screeners")
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
    for symbol, frame in histories.items():
        try:
            results.append(analyze(meta_by_symbol[symbol], frame))
        except Exception as exc:
            history_errors.append(f"{symbol}: analysis failed: {exc}")

    main_ranked = sorted([x for x in results if eligible(x, False)], key=lambda x: x["score"], reverse=True)
    penny_ranked = sorted([x for x in results if eligible(x, True)], key=lambda x: x["score"], reverse=True)
    main_picks = choose_diversified(main_ranked, 3)
    selected = {x["ticker"] for x in main_picks}
    penny_ranked = [x for x in penny_ranked if x["ticker"] not in selected]
    penny_picks = choose_diversified(penny_ranked, 3)

    if len(main_picks) < 3:
        sys.exit("ERROR: Fewer than 3 main stocks passed the filters; existing picks.json left unchanged.")
    for stock in penny_picks:
        stock["risk"] = "HIGH RISK — penny-stock volatility. " + stock["risk"]

    now = datetime.now(timezone.utc)
    output = {
        "status": "ok",
        "updated_at": now.isoformat(),
        "snapshot_time": now.date().isoformat(),
        "data_source": "Yahoo Finance public screeners + Yahoo Finance daily historical prices (via yfinance)",
        "data_note": (
            "Free, broad candidate scan from public US and Canadian activity/gainer screeners; "
            "not an exhaustive scan of every listed security. End-of-day history may be delayed. "
            "Yahoo endpoints are unofficial and can be throttled or changed. Prices are in local "
            "trading currencies (USD for US, CAD for Canada)."
        ),
        "strategy": (
            "Market activity score 0–100: 35% relative volume, 30% absolute daily price movement, "
            "20% absolute 5-day movement, 10% absolute 20-day movement, and 5% average dollar liquidity; "
            "a modest penalty applies to unusually high 20-day volatility. Both gainers and decliners "
            "can qualify. Main stocks must have 20-day average dollar volume of at least $1 million; "
            "penny stocks must be priced $0.05–$10 and have at least $100,000 average daily dollar volume."
        ),
        "universe": {
            "markets": ["US", "Canada"],
            "candidate_sources": list(SCREENER_IDS),
            "us_candidates_queued": len(universe.get("US", [])),
            "canada_candidates_queued": len(universe.get("Canada", [])),
            "unique_candidates_queued": len(all_meta),
            "history_symbols_returned": len(histories),
            "penny_price_cap_local_currency": PENNY_MAX_PRICE,
            "exhaustive_market_scan": False,
        },
        "main": main_picks,
        "penny": penny_picks,
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
