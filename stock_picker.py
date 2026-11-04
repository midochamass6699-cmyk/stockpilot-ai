
import os
import json
import time
import requests
from datetime import datetime, timezone

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")

STOCKS = [
    ("MSFT", "Microsoft", "US", "Technology"),
    ("NVDA", "Nvidia", "US", "Technology"),
    ("AMZN", "Amazon", "US", "Consumer"),
    ("GOOGL", "Alphabet", "US", "Technology"),
    ("META", "Meta", "US", "Technology"),
    ("AVGO", "Broadcom", "US", "Technology"),
    ("JPM", "JPMorgan Chase", "US", "Financials"),
    ("COST", "Costco", "US", "Consumer"),
    ("LLY", "Eli Lilly", "US", "Healthcare"),
    ("KO", "Coca-Cola", "US", "Consumer"),
    ("SHOP.TRT", "Shopify", "Canada", "Technology"),
    ("RY.TRT", "Royal Bank", "Canada", "Financials"),
    ("TD.TRT", "TD Bank", "Canada", "Financials"),
    ("CNR.TRT", "Canadian National Railway", "Canada", "Industrials"),
    ("ENB.TRT", "Enbridge", "Canada", "Energy"),
    ("CNQ.TRT", "Canadian Natural Resources", "Canada", "Energy"),
    ("CSU.TRT", "Constellation Software", "Canada", "Technology"),
    ("BNS.TRT", "Bank of Nova Scotia", "Canada", "Financials"),
]

def get_stock_data(symbol):
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": API_KEY
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    result = response.json()

    series = result.get("Time Series (Daily)")
    if not series:
        print(f"No daily data for {symbol}: {result.get('Note') or result.get('Error Message') or 'unavailable'}")
        return None

    dates = sorted(series.keys(), reverse=True)
    prices = [float(series[d]["4. close"]) for d in dates]
    volumes = [int(series[d]["5. volume"]) for d in dates]

    if len(prices) < 100:
        return None

    current = prices[0]
    ma50 = sum(prices[:50]) / 50
    high100 = max(prices[:100])

    return_20 = (current / prices[20] - 1) * 100
    return_50 = (current / prices[50] - 1) * 100
    distance_high = (current / high100 - 1) * 100

    gains = []
    losses = []
    for i in range(14):
        change = prices[i] - prices[i + 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    rsi = 100 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))

    average_volume = sum(volumes[1:21]) / 20
    volume_ratio = volumes[0] / average_volume if average_volume else 0

    momentum = max(0, min(100, 50 + return_20 * 2 + return_50))
    trend = 100 if current > ma50 else 30
    pullback = max(0, min(100, 100 + distance_high * 2))
    volume_score = max(0, min(100, volume_ratio * 50))
    rsi_score = max(0, 100 - abs(rsi - 60) * 2)

    score = (
        momentum * 0.30 +
        trend * 0.20 +
        pullback * 0.25 +
        volume_score * 0.15 +
        rsi_score * 0.10
    )

    return {
        "price": round(current, 2),
        "price_date": dates[0],
        "score": round(score, 1),
        "return_20d": round(return_20, 2),
        "return_50d": round(return_50, 2),
        "rsi": round(rsi, 1),
        "volume_ratio": round(volume_ratio, 2),
        "above_50day_average": current > ma50
    }

def main():
    if not API_KEY:
        raise RuntimeError("Missing ALPHAVANTAGE_API_KEY secret.")

    candidates = []

    for index, (symbol, company, market, sector) in enumerate(STOCKS):
        print(f"Checking {symbol} ({index + 1}/{len(STOCKS)})")

        try:
            data = get_stock_data(symbol)
            if data:
                candidates.append({
                    "ticker": symbol,
                    "company": company,
                    "market": market,
                    "sector": sector,
                    **data,
                    "reason": (
                        "Positive trend and momentum with recent price and volume indicators."
                        if data["above_50day_average"]
                        else "Potential recovery candidate; price is below its 50-day average."
                    ),
                    "risk": "Price momentum can reverse. Review company fundamentals and recent news."
                })
        except Exception as error:
            print(f"Error for {symbol}: {error}")

        if index < len(STOCKS) - 1:
            time.sleep(12.5)

    candidates.sort(key=lambda item: item["score"], reverse=True)

    picks = []
    sectors = set()
    markets = {}

    for stock in candidates:
        if stock["sector"] in sectors:
            continue
        if markets.get(stock["market"], 0) >= 2:
            continue

        picks.append(stock)
        sectors.add(stock["sector"])
        markets[stock["market"]] = markets.get(stock["market"], 0) + 1

        if len(picks) == 3:
            break

    if len(picks) < 3:
        raise RuntimeError(
            f"Only {len(picks)} valid diversified picks found. "
            "No incomplete list will be published."
        )

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "picks": picks
    }

    os.makedirs("docs/data", exist_ok=True)

    with open("docs/data/picks.json", "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print("Successfully generated three stock picks.")

if __name__ == "__main__":
    main()
