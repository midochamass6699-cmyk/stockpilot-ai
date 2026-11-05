
#!/usr/bin/env python3
"""
Generate 3 main stock picks + 3 penny stock picks.
Data: Alpha Vantage daily OHLCV.
Maximum: 25 API requests per daily run.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
OUTPUT = Path(os.environ.get("PICKS_OUTPUT", "docs/data/picks.json"))

# 18 established stocks
MAIN_UNIVERSE = [
    ("MSFT", "Microsoft", "US", "Technology"),
    ("NVDA", "NVIDIA", "US", "Semiconductors"),
    ("AMZN", "Amazon", "US", "Consumer"),
    ("GOOGL", "Alphabet", "US", "Technology"),
    ("META", "Meta Platforms", "US", "Technology"),
    ("AVGO", "Broadcom", "US", "Semiconductors"),
    ("JPM", "JPMorgan Chase", "US", "Financials"),
    ("COST", "Costco", "US", "Consumer"),
    ("LLY", "Eli Lilly", "US", "Healthcare"),
    ("KO", "Coca-Cola", "US", "Consumer"),
    ("SHOP.TRT", "Shopify", "Canada", "Technology"),
    ("RY.TRT", "Royal Bank of Canada", "Canada", "Financials"),
    ("TD.TRT", "Toronto-Dominion Bank", "Canada", "Financials"),
    ("CNR.TRT", "Canadian National Railway", "Canada", "Industrials"),
    ("ENB.TRT", "Enbridge", "Canada", "Energy"),
    ("CNQ.TRT", "Canadian Natural Resources", "Canada", "Energy"),
    ("CSU.TRT", "Constellation Software", "Canada", "Technology"),
    ("BNS.TRT", "Bank of Nova Scotia", "Canada", "Financials"),
]

# 7 speculative penny-stock candidates
PENNY_UNIVERSE = [
    ("SNDL", "SNDL Inc.", "US", "Cannabis"),
    ("ACB", "Aurora Cannabis", "US", "Cannabis"),
    ("TLRY", "Tilray Brands", "US", "Cannabis"),
    ("BITF", "Bitfarms", "US", "Technology"),
    ("HUT", "Hut 8", "US", "Technology"),
    ("OPEN", "Opendoor Technologies", "US", "Real Estate"),
    ("LUMN", "Lumen Technologies", "US", "Telecommunications"),
]

PENNY_MAX_PRICE = 5.00
REQUEST_DELAY = 12.5


def fetch_daily(symbol):
    params = urlencode({
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": API_KEY,
    })

    url = "https://www.alphavantage.co/query?" + params
    request = Request(
        url,
        headers={"User-Agent": "3DailyStockPicks/1.0"}
    )

    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))

    key = "Time Series (Daily)"

    if key not in payload:
        message = (
            payload.get("Note")
            or payload.get("Information")
            or payload.get("Error Message")
            or "No daily data returned"
        )
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

    rows.sort(key=lambda row: row["date"])

    if len(rows) < 55:
        raise RuntimeError(f"{symbol}: insufficient price history")

    return rows


def pct_change(new, old):
    return ((new / old) - 1) * 100 if old else 0


def calculate_rsi(closes, period=14):
    changes = [
        closes[i] - closes[i - 1]
        for i in range(1, len(closes))
    ]

    recent = changes[-period:]

    gains = sum(x for x in recent if x > 0) / period
    losses = -sum(x for x in recent if x < 0) / period

    if losses == 0:
        return 100 if gains else 50

    rs = gains / losses

    return 100 - (100 / (1 + rs))


def analyze(meta):
    symbol, company, market, sector = meta

    rows = fetch_daily(symbol)

    closes = [r["close"] for r in rows]
    volumes = [r["volume"] for r in rows]

    last = closes[-1]
    previous = closes[-2]

    ma50 = sum(closes[-50:]) / 50

    ret20 = pct_change(last, closes[-21])
    ret50 = pct_change(last, closes[-51])

    daily_change = pct_change(last, previous)

    rsi14 = calculate_rsi(closes)

    avg_vol20 = sum(volumes[-20:]) / 20

    volume_ratio = (
        volumes[-1] / avg_vol20
        if avg_vol20 else 1
    )

    high100 = max(r["high"] for r in rows[-100:])

    drawdown = pct_change(last, high100)

    # Research score
    trend = max(
        0,
        min(
            100,
            50 + ret20 * 2 + ret50 * 0.8
            + (8 if last > ma50 else -12)
        )
    )

    pullback = max(0, min(100, 75 + drawdown * 2))

    participation = max(
        0,
        min(100, 50 + (volume_ratio - 1) * 20)
    )

    rsi_score = max(0, 100 - abs(rsi14 - 58) * 2.2)

    score = round(
        trend * 0.50
        + pullback * 0.25
        + participation * 0.15
        + rsi_score * 0.10,
        1
    )

    reasons = []

    if last > ma50:
        reasons.append("Price above 50-day average")

    if ret20 > 0:
        reasons.append(f"Positive 20-day momentum ({ret20:.1f}%)")

    if 40 <= rsi14 <= 68:
        reasons.append(f"Balanced RSI ({rsi14:.1f})")

    if volume_ratio >= 1.15:
        reasons.append("Above-average trading volume")

    if not reasons:
        reasons.append("Competitive technical research score")

    risks = []

    if last < ma50:
        risks.append("Below 50-day average")

    if rsi14 >= 70:
        risks.append("Potentially overbought")

    elif rsi14 < 35:
        risks.append("Weak momentum")

    if ret20 < -5:
        risks.append("Negative 20-day momentum")

    if not risks:
        risks.append("Market and company-specific risks remain")

    return {
        "ticker": symbol,
        "company": company,
        "exchange": "TSX" if market == "Canada" else "US",
        "market": market,
        "sector": sector,
        "currency": "CAD" if market == "Canada" else "USD",
        "price": round(last, 2),
        "price_date": rows[-1]["date"],
        "change_percent": round(daily_change, 2),
        "quote_time": rows[-1]["date"] + " (daily close)",
        "score": score,
        "return_20d": round(ret20, 2),
        "return_50d": round(ret50, 2),
        "rsi": round(rsi14, 1),
        "volume_ratio": round(volume_ratio, 2),
        "above_50day_average": last > ma50,
        "reason": "; ".join(reasons) + ".",
        "risk": "; ".join(risks) + ".",
    }


def choose_main(ranked):
    chosen = []
    market_count = {}
    sector_count = {}

    for stock in ranked:
        market = stock["market"]
        sector = stock["sector"]

        if market_count.get(market, 0) >= 2:
            continue

        if sector_count.get(sector, 0) >= 1:
            continue

        chosen.append(stock)
        market_count[market] = market_count.get(market, 0) + 1
        sector_count[sector] = sector_count.get(sector, 0) + 1

        if len(chosen) == 3:
            break

    for stock in ranked:
        if len(chosen) == 3:
            break

        if stock not in chosen:
            chosen.append(stock)

    return chosen


def scan_universe(universe, label):
    results = []
    errors = []

    for index, meta in enumerate(universe):
        try:
            stock = analyze(meta)
            results.append(stock)
            print(f"OK {label}: {meta[0]} score={stock['score']}")

        except Exception as exc:
            errors.append(str(exc))
            print(f"SKIP {meta[0]}: {exc}", file=sys.stderr)

        if index < len(universe) - 1:
            time.sleep(REQUEST_DELAY)

    return results, errors


def main():
    if not API_KEY:
        sys.exit("ERROR: Missing ALPHAVANTAGE_API_KEY")

    print("Scanning main stocks...")

    main_results, main_errors = scan_universe(
        MAIN_UNIVERSE, "MAIN"
    )

    print("Scanning penny stocks...")

    penny_results, penny_errors = scan_universe(
        PENNY_UNIVERSE, "PENNY"
    )

    if len(main_results) < 3:
        sys.exit("ERROR: Fewer than 3 valid main stocks.")

    # Main stocks: highest research score
    main_ranked = sorted(
        main_results,
        key=lambda x: x["score"],
        reverse=True
    )

    main_picks = choose_main(main_ranked)

    # Penny stocks: under $5 in their trading currency
    penny_eligible = [
        stock for stock in penny_results
        if 0 < stock["price"] <= PENNY_MAX_PRICE
    ]

    penny_ranked = sorted(
        penny_eligible,
        key=lambda x: x["score"],
        reverse=True
    )

    penny_picks = penny_ranked[:3]

    # Do not invent stocks if fewer than three qualify.
    for stock in penny_picks:
        stock["risk"] = "HIGH RISK — speculative stock. " + stock["risk"]

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "Alpha Vantage TIME_SERIES_DAILY",
        "data_note": (
            "Daily end-of-day prices, not real-time quotes. "
            "Penny stocks are filtered at a maximum price of $5 "
            "in their respective trading currency."
        ),
        "strategy": (
            "50% trend/momentum, 25% pullback context, "
            "15% volume, 10% RSI."
        ),
        "main": main_picks,
        "penny": penny_picks,
        "penny_candidates_scanned": len(penny_results),
        "penny_candidates_eligible": len(penny_eligible),
        "picks": main_picks,
        "watchlist": main_ranked,
        "errors": main_errors + penny_errors,
        "penny_errors": penny_errors,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    print("\nSUCCESS")
    print(f"Main picks: {len(main_picks)}/3")
    print(f"Penny picks: {len(penny_picks)}/3")
    print(f"Output: {OUTPUT}")

    if len(penny_picks) < 3:
        print(
            "WARNING: Fewer than 3 penny stocks qualified. "
            "No artificial picks were added."
        )


if __name__ == "__main__":
    main()
