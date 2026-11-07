#!/usr/bin/env python3
"""
StockPilot daily momentum screener.

Keeps the existing GitHub Pages contract:
  output: docs/data/picks.json
  keys: status, updated_at, data_source, main, penny, picks, watchlist, errors

Data provider: Alpha Vantage TIME_SERIES_DAILY.
The script scans a fixed, disclosed US + Canadian candidate universe.
It does not claim to scan every listed security in either market.
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

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
OUTPUT = Path(os.environ.get("PICKS_OUTPUT", "docs/data/picks.json"))

# Keep this at or below the provider's available daily request allowance.
# One daily time-series request is made per symbol.
MAIN_UNIVERSE = [
    ("MSFT", "Microsoft", "US", "Technology", "NASDAQ", "USD"),
    ("NVDA", "NVIDIA", "US", "Semiconductors", "NASDAQ", "USD"),
    ("AMZN", "Amazon", "US", "Consumer Discretionary", "NASDAQ", "USD"),
    ("GOOGL", "Alphabet", "US", "Communication Services", "NASDAQ", "USD"),
    ("META", "Meta Platforms", "US", "Communication Services", "NASDAQ", "USD"),
    ("AVGO", "Broadcom", "US", "Semiconductors", "NASDAQ", "USD"),
    ("JPM", "JPMorgan Chase", "US", "Financials", "NYSE", "USD"),
    ("COST", "Costco", "US", "Consumer Staples", "NASDAQ", "USD"),
    ("LLY", "Eli Lilly", "US", "Healthcare", "NYSE", "USD"),
    ("KO", "Coca-Cola", "US", "Consumer Staples", "NYSE", "USD"),
    ("SHOP.TRT", "Shopify", "Canada", "Technology", "TSX", "CAD"),
    ("RY.TRT", "Royal Bank of Canada", "Canada", "Financials", "TSX", "CAD"),
    ("TD.TRT", "Toronto-Dominion Bank", "Canada", "Financials", "TSX", "CAD"),
    ("CNR.TRT", "Canadian National Railway", "Canada", "Industrials", "TSX", "CAD"),
    ("ENB.TRT", "Enbridge", "Canada", "Energy", "TSX", "CAD"),
]

PENNY_UNIVERSE = [
    ("SNDL", "SNDL Inc.", "US", "Cannabis", "NASDAQ", "USD"),
    ("ACB", "Aurora Cannabis", "US", "Cannabis", "NASDAQ", "USD"),
    ("TLRY", "Tilray Brands", "US", "Cannabis", "NASDAQ", "USD"),
    ("BITF", "Bitfarms", "US", "Technology", "NASDAQ", "USD"),
    ("OPEN", "Opendoor Technologies", "US", "Real Estate", "NASDAQ", "USD"),
    ("HIVE.TRT", "HIVE Digital Technologies", "Canada", "Technology", "TSX", "CAD"),
    ("BITF.TRT", "Bitfarms", "Canada", "Technology", "TSX", "CAD"),
    ("BTE.TRT", "Baytex Energy", "Canada", "Energy", "TSX", "CAD"),
    ("AC.TRT", "Air Canada", "Canada", "Industrials", "TSX", "CAD"),
    ("TVE.TRT", "Tamarack Valley Energy", "Canada", "Energy", "TSX", "CAD"),
]

PENNY_MAX_PRICE = float(os.environ.get("PENNY_MAX_PRICE", "10.00"))
PENNY_MIN_PRICE = 0.05
MAIN_MIN_AVG_DOLLAR_VOLUME = 1_000_000
PENNY_MIN_AVG_DOLLAR_VOLUME = 100_000
REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY_SECONDS", "12.5"))
MIN_HISTORY = 55


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def pct_change(new, old):
    return ((new / old) - 1.0) * 100.0 if old else 0.0


def fetch_daily(symbol):
    params = urlencode({
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": API_KEY,
    })
    url = "https://www.alphavantage.co/query?" + params
    request = Request(url, headers={"User-Agent": "StockPilotMomentum/2.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    key = "Time Series (Daily)"
    if key not in payload:
        message = (
            payload.get("Note")
            or payload.get("Information")
            or payload.get("Error Message")
            or "No daily data returned"
        )
