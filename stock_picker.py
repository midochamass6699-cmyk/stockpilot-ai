
#!/usr/bin/env python3
"""
StockPilot AI - Daily Stock Picks

Selects:
- 3 most actively traded US stocks above $10
- 3 most actively traded US stocks between $0.10 and $10

Uses Alpha Vantage TOP_GAINERS_LOSERS.
This is a volume-ranking screen, not investment advice.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
OUTPUT = Path(os.environ.get("PICKS_OUTPUT", "docs/data/picks.json"))

FEED_URL = "https://www.alphavantage.co/query"

PENNY_MIN_PRICE = 0.10
PENNY_MAX_PRICE = 10.00

MAIN_MIN_PRICE = 10.00
PICKS_PER_CATEGORY = 3


def write_output(data):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )


def error_output(message):
    now = datetime.now(timezone.utc).isoformat()

    write_output({
        "status": "error",
        "updated_at": now,
        "data_source": "Alpha Vantage",
        "data_note": "No verified market data received. No sample stocks displayed.",
        "main": [],
        "penny": [],
        "picks": [],
        "errors": [str(message)]
    })

    print("DATA ERROR:", message)


def to_float(value):
    if value is None:
        raise ValueError("Missing numeric value")

    return float(
        str(value).replace(",", "").replace("%", "").strip()
    )


def fetch_most_active():

    if not API_KEY:
        raise RuntimeError(
            "Missing GitHub secret ALPHAVANTAGE_API_KEY"
        )

    params = urlencode({
        "function": "TOP_GAINERS_LOSERS",
        "apikey": API_KEY
    })

    request = Request(
        FEED_URL + "?" + params,
        headers={
            "User-Agent": "StockPilotDailyPicks/1.0"
        }
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )

    except HTTPError as exc:
        raise RuntimeError(
            f"Alpha Vantage HTTP error: {exc.code}"
        )

    except URLError as exc:
        raise RuntimeError(
            f"Could not connect to Alpha Vantage: {exc.reason}"
        )

    # Alpha Vantage may return an API error instead of stock data.
    if "most_actively_traded" not in payload:

        message = (
            payload.get("Note")
            or payload.get("Information")
            or payload.get("Error Message")
            or "The API did not return most_actively_traded."
        )

        raise RuntimeError(message)

    rows = payload["most_actively_traded"]

    if not isinstance(rows, list) or not rows:
        raise RuntimeError(
            "Alpha Vantage returned an empty most_actively_traded list."
        )

    return rows


def normalize_rows(rows, snapshot_time):

    normalized = []

    for row in rows:

        try:
            ticker = str(row["ticker"]).strip().upper()

            price = to_float(row["price"])

            volume = int(
                float(str(row["volume"]).replace(",", ""))
            )

            change_pct = to_float(
                row.get("change_percentage", 0)
            )

            if not ticker:
                continue

            if price <= 0 or volume <= 0:
                continue

            normalized.append({
                "ticker": ticker,
                "company": ticker,
                "exchange": "US market",
                "market": "US",
                "price": round(price, 4),
                "change_percent": round(change_pct, 2),
                "volume": volume,
                "price_date": snapshot_time,
                "reason": (
                    "Selected based on reported trading volume "
                    "among stocks returned by Alpha Vantage."
                ),
                "risk": (
                    "Market risk applies. Trading volume does not "
                    "predict future performance."
                )
            })

        except (KeyError, ValueError, TypeError) as exc:
            print("Skipping invalid stock row:", exc)
            continue

    return normalized


def build_picks():

    now = datetime.now(timezone.utc)
    snapshot_time = now.strftime("%Y-%m-%d")

    print("Fetching Alpha Vantage market data...")

    rows = fetch_most_active()

    stocks = normalize_rows(rows, snapshot_time)

    if not stocks:
        raise RuntimeError(
            "No valid stock records were found in the API response."
        )

    # Main stocks: strictly above $10.
    main_stocks = [
        stock for stock in stocks
        if stock["price"] > MAIN_MIN_PRICE
    ]

    # Penny stocks: $0.10 through $10 inclusive.
    penny_stocks = [
        stock for stock in stocks
        if PENNY_MIN_PRICE <= stock["price"] <= PENNY_MAX_PRICE
    ]

    # Highest reported volume first.
    main_stocks.sort(
        key=lambda stock: stock["volume"],
        reverse=True
    )

    penny_stocks.sort(
        key=lambda stock: stock["volume"],
        reverse=True
    )

    main_stocks = main_stocks[:PICKS_PER_CATEGORY]
    penny_stocks = penny_stocks[:PICKS_PER_CATEGORY]

    combined = main_stocks + penny_stocks

    if not combined:
        raise RuntimeError(
            "The API returned stocks, but none matched the price filters."
        )

    output = {
        "status": "ok",
        "updated_at": now.isoformat(),
        "snapshot_time": snapshot_time,
        "data_source": "Alpha Vantage TOP_GAINERS_LOSERS",
        "data_note": (
            "Ranked by reported trading volume among stocks "
            "included in Alpha Vantage's most_actively_traded feed. "
            "The feed may not represent every US-listed stock."
        ),
        "main": main_stocks,
        "penny": penny_stocks,
        "picks": combined,
        "errors": []
    }

    write_output(output)

    print("SUCCESS: Stock picks updated.")
    print("Main stocks:", len(main_stocks))
    print("Penny stocks:", len(penny_stocks))

    for stock in combined:
        print(
            stock["ticker"],
            "Price:", stock["price"],
            "Volume:", stock["volume"]
        )


if __name__ == "__main__":

    try:
        build_picks()

    except Exception as exc:
        error_output(exc)
        raise
