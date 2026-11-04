#!/usr/bin/env python3
"""Build a daily three-stock research shortlist using Alpha Vantage daily OHLCV data.

Free-tier design: 18 symbols per run, below Alpha Vantage's published 25 requests/day.
The ranking is a rules-based research screen, not a prediction or investment advice.
"""
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
OUTPUT = Path(os.environ.get("PICKS_OUTPUT", "docs/data/picks.json"))

# Curated starter universe. Alpha Vantage uses .TRT for Toronto Stock Exchange listings.
# Confirm ticker availability and exchange suffixes before expanding this universe.
UNIVERSE = [
    ("MSFT", "Microsoft", "US", "Technology"),
    ("NVDA", "NVIDIA", "US", "Semiconductors"),
    ("AMZN", "Amazon", "US", "Consumer / Cloud"),
    ("GOOGL", "Alphabet", "US", "Communication Services"),
    ("META", "Meta Platforms", "US", "Communication Services"),
    ("AVGO", "Broadcom", "US", "Semiconductors"),
    ("JPM", "JPMorgan Chase", "US", "Financials"),
    ("COST", "Costco", "US", "Consumer Staples"),
    ("LLY", "Eli Lilly", "US", "Healthcare"),
    ("KO", "Coca-Cola", "US", "Consumer Staples"),
    ("SHOP.TRT", "Shopify", "Canada", "Technology"),
    ("RY.TRT", "Royal Bank of Canada", "Canada", "Financials"),
    ("TD.TRT", "Toronto-Dominion Bank", "Canada", "Financials"),
    ("CNR.TRT", "Canadian National Railway", "Canada", "Industrials"),
    ("ENB.TRT", "Enbridge", "Canada", "Energy / Utilities"),
    ("CNQ.TRT", "Canadian Natural Resources", "Canada", "Energy"),
    ("CSU.TRT", "Constellation Software", "Canada", "Technology"),
    ("BNS.TRT", "Bank of Nova Scotia", "Canada", "Financials"),
]

def fetch_daily(symbol):
    params = urlencode({
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": API_KEY,
    })
    url = "https://www.alphavantage.co/query?" + params
    req = Request(url, headers={"User-Agent": "3DailyStockPicks/1.0"})
    with urlopen(req, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    key = "Time Series (Daily)"
    if key not in payload:
        message = payload.get("Note") or payload.get("Information") or payload.get("Error Message") or "No daily series returned"
        raise RuntimeError(f"{symbol}: {message}")
    rows = []
    for date, values in payload[key].items():
        rows.append({
            "date": date,
            "close": float(values["4. close"]),
            "volume": float(values["5. volume"]),
            "high": float(values["2. high"]),
            "low": float(values["3. low"]),
        })
    rows.sort(key=lambda x: x["date"])
    if len(rows) < 55:
        raise RuntimeError(f"{symbol}: not enough history ({len(rows)} sessions)")
    return rows

def pct_change(new, old):
    return (new / old - 1.0) * 100.0 if old else 0.0

def rsi(closes, period=14):
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    recent = changes[-period:]
    gains = sum(x for x in recent if x > 0) / period
    losses = -sum(x for x in recent if x < 0) / period
    if losses == 0:
        return 100.0 if gains else 50.0
    rs = gains / losses
    return 100.0 - (100.0 / (1.0 + rs))

def analyze(meta):
    symbol, company, market, sector = meta
    rows = fetch_daily(symbol)
    closes = [r["close"] for r in rows]
    volumes = [r["volume"] for r in rows]
    last = closes[-1]
    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50
    ret20 = pct_change(last, closes[-21])
    ret50 = pct_change(last, closes[-51])
    rsi14 = rsi(closes)
    avg_vol20 = sum(volumes[-20:]) / 20
    vol_ratio = volumes[-1] / avg_vol20 if avg_vol20 else 1.0
    high100 = max(r["high"] for r in rows[-100:])
    drawdown = pct_change(last, high100)  # <= 0; recent pullback proxy, NOT intrinsic value.

    # Blend: trend/momentum (50%), pullback/entry context (25%), participation (15%),
    # RSI balance (10%). All components are bounded to avoid extreme outliers.
    trend = max(0, min(100, 50 + ret20 * 2.0 + ret50 * 0.8 + (8 if last > ma50 else -12)))
    pullback = max(0, min(100, 75 + drawdown * 2.0))  # moderate pullback scores better than chasing highs
    participation = max(0, min(100, 50 + (vol_ratio - 1.0) * 20))
    rsi_score = max(0, 100 - abs(rsi14 - 58) * 2.2)
    score = round(trend * .50 + pullback * .25 + participation * .15 + rsi_score * .10, 1)

    why = []
    if last > ma50:
        why.append("price is above its 50-session average")
    if ret20 > 0:
        why.append(f"20-session momentum is positive ({ret20:.1f}%)")
    if 40 <= rsi14 <= 68:
        why.append(f"RSI is in a moderate range ({rsi14:.0f})")
    if vol_ratio >= 1.15:
        why.append("latest volume is above its 20-session average")
    if not why:
        why.append("screen score is comparatively strong within the monitored universe")

    risks = []
    if last < ma50:
        risks.append("price is below its 50-session average")
    if rsi14 >= 70:
        risks.append("momentum may be overextended (high RSI)")
    elif rsi14 < 35:
        risks.append("weak momentum (low RSI)")
    if ret20 < -5:
        risks.append("negative 20-session price momentum")
    if vol_ratio < .7:
        risks.append("latest volume is below its recent average")
    if not risks:
        risks.append("market, company-specific and valuation risks remain; this screen does not assess fundamentals")

    return {
        "symbol": symbol, "company": company, "market": market, "sector": sector,
        "price": round(last, 2), "price_date": rows[-1]["date"],
        "currency": "USD" if market == "US" else "CAD",
        "score": score, "return_20d_pct": round(ret20, 2),
        "return_50d_pct": round(ret50, 2), "rsi_14": round(rsi14, 1),
        "volume_vs_20d_avg": round(vol_ratio, 2),
        "distance_from_100d_high_pct": round(drawdown, 2),
        "reason": "; ".join(why) + ".",
        "risk": "; ".join(risks) + ".",
    }

def main():
    if not API_KEY:
        print("Missing ALPHAVANTAGE_API_KEY environment variable.", file=sys.stderr)
        sys.exit(2)

    results, errors = [], []
    for index, meta in enumerate(UNIVERSE):
        try:
            results.append(analyze(meta))
            print(f"OK {meta[0]}")
        except Exception as exc:
            errors.append(str(exc))
            print(f"SKIP {meta[0]}: {exc}", file=sys.stderr)
        # Stay below provider rate/frequency limits.
        if index < len(UNIVERSE) - 1:
            time.sleep(12.5)

    if len(results) < 3:
        raise SystemExit("Fewer than 3 symbols returned valid data; refusing to publish stale or fabricated picks.")

    # Encourage a diversified shortlist: maximum two picks per market and sector.
    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    chosen, market_count, sector_count = [], {}, {}
    for item in ranked:
        if market_count.get(item["market"], 0) >= 2:
            continue
        if sector_count.get(item["sector"], 0) >= 1:
            continue
        chosen.append(item)
        market_count[item["market"]] = market_count.get(item["market"], 0) + 1
        sector_count[item["sector"]] = sector_count.get(item["sector"], 0) + 1
        if len(chosen) == 3:
            break
    # If diversification constraints prevent three picks, fill by score.
    for item in ranked:
        if len(chosen) == 3:
            break
        if item not in chosen:
            chosen.append(item)

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_source": "Alpha Vantage TIME_SERIES_DAILY",
        "data_note": "Daily end-of-day OHLCV; not real-time. Prices and technical signals are not a guarantee of future performance.",
        "strategy": "50% trend/momentum, 25% recent pullback context, 15% volume participation, 10% RSI balance.",
        "value_note": "This free version does not access verified P/E, P/B, cash-flow or intrinsic-value data. Pullback context is not a valuation measure.",
        "universe_size": len(UNIVERSE),
        "symbols_scanned": len(results),
        "errors": errors,
        "picks": chosen,
        "watchlist": ranked,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(chosen)} picks from {len(results)} valid symbols.")

if __name__ == "__main__":
    main()
