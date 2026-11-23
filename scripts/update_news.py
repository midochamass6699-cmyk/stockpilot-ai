#!/usr/bin/env python3
"""Refresh cached market-news headlines from the GDELT DOC 2.0 API.

Only article metadata (headline, publisher/domain, timestamp and original URL)
is stored. If an individual request fails or returns no usable articles, the
last successful category is retained so the public site does not go blank.
"""
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "news.json")
API = "https://api.gdeltproject.org/api/v2/doc/doc"
QUERIES = {
    "markets": '("stock market" OR stocks OR "Federal Reserve" OR Nasdaq OR NYSE OR TSX OR "interest rates")',
    "penny": '("small cap stocks" OR "penny stocks" OR microcap OR "small-cap")',
    "crypto": '(cryptocurrency OR bitcoin OR ethereum OR "digital assets" OR crypto)',
}

def load_previous():
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def fetch_articles(query):
    params = urlencode({
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 30,
        "timespan": "24h",
        "sort": "DateDesc",
    })
    req = Request(API + "?" + params, headers={"User-Agent": "StockPilotAI-News/1.0 (headline links; contact via technofront.org)"})
    with urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError("GDELT HTTP status " + str(response.status))
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("articles", []) if isinstance(payload, dict) else []
    clean, seen = [], set()
    for row in rows:
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        clean.append({
            "title": title[:300],
            "url": url,
            "source": str(row.get("domain") or row.get("source") or "Original publisher")[:120],
            "published": str(row.get("seendate") or ""),
            "language": str(row.get("language") or ""),
        })
        if len(clean) >= 12:
            break
    if not clean:
        raise RuntimeError("GDELT returned no usable article records")
    return clean

def main():
    previous = load_previous()
    old_sections = previous.get("sections", {}) if isinstance(previous.get("sections"), dict) else {}
    sections = dict(old_sections)
    updated = []
    for index, (key, query) in enumerate(QUERIES.items()):
        if index:
            time.sleep(6)  # Respect GDELT's published guidance to space requests.
        try:
            sections[key] = fetch_articles(query)
            updated.append(key)
            print("Updated", key, "with", len(sections[key]), "headlines")
        except Exception as exc:
            print("Keeping cached", key, "headlines:", str(exc))
    payload = {
        "provider": "GDELT Project",
        "attribution": "News metadata supplied by the GDELT Project. Headlines link to their original publishers.",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "updated_sections": updated,
        "sections": sections,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix="news-", suffix=".json", dir=os.path.dirname(OUT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp_path, OUT)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

if __name__ == "__main__":
    main()
