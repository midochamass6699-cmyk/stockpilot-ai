#!/usr/bin/env python3
"""
Build daily stock lists from Alpha Vantage's US Most Actively Traded feed.

This is a volume-ranking screen, not a prediction or buy recommendation.
One API request per run. Output: docs/data/picks.json
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
OUTPUT = Path(os.environ.get("PICKS_OUTPUT", "docs/data/picks.json"))
PENNY_MIN_PRICE = 0.10
PENNY_MAX_PRICE = 10.00
FEED_URL = "https://www.alphavantage.co/query"


def write_output(data):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2), encoding="utf-8")


def error_output(message):
    now = datetime.now(timezone.utc).isoformat()
    write_output({
        "status": "error",
        "updated_at": now,
        "data_source": "Alpha Vantage TOP_GAINERS_LOSERS",
        "data_note": "No verified market data was received. No sample stocks are shown.",
        "main": [],
        "penny": [],
        "picks": [],
        "errors": [str(message)],
    })
    print("DATA ERROR:", message)
    print("Wrote empty lists so old/example picks are not presented as current data.")


def to_float(value):
    if value is None:
        raise ValueError("missing numeric value")
    return float(str(value).replace(",", "").replace("%", "").strip())


def fetch_most_active():
    if not API_KEY:
        raise RuntimeError("Missing GitHub secret ALPHAVANTAGE_API_KEY")

    params = urlencode({
        "function": "TOP_GAINERS_LOSERS",
        "apikey": API_KEY,
    })
    request = Request(
        FEED_URL + "?" + params,
        headers={"User-Agent": "StockPilotDailyPicks/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "most_actively_traded" not in payload:
        message = (
            payload.get("Note")
            or payload.get("Information")
            or payload.get("Error Message")
            or "Alpha Vantage did not return most_actively_traded."
        )
        raise RuntimeError(message)

    rows = payload["most_actively_traded"]
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("The most_actively_traded list is empty.")

    return payload, rows


def normalize_rows(rows, snapshot_time):
    normalized = []
    for row in rows:
        try:
            ticker = str(row["ticker"]).strip().upper()
            price = to_float(row["price"])
            volume = int(float(str(row["volume"]).replace(",", "")))
            change_pct = to_float(row.get("change_percentage", 0))
            if not ticker or price <= 0 or volume < 0:
                continue

            normalized.append({
                "ticker": ticker,
                "company": ticker,  # Feed supplies symbols, not verified company names.
                "exchange": "US market",
                "market": "US",
