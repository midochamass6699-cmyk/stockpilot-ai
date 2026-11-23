#!/usr/bin/env python3
"""Refresh cached financial-news headlines from GDELT DOC 2.0.

Stores article metadata only. Every category is restricted to English-language
coverage. Failed requests preserve that category's last successful cache.
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
    "markets": [
        '("stock market" OR stocks OR "Federal Reserve" OR Nasdaq OR NYSE OR TSX OR "interest rates") sourcelang:english',
    ],
    "penny": [
        '("small cap stocks" OR "penny stocks" OR microcap OR "small-cap stocks") sourcelang:english',
        '("small cap" OR microcap OR "penny stock") sourcelang:english',
    ],
    "crypto": [
        '(bitcoin OR ethereum OR cryptocurrency OR crypto OR "digital assets") sourcelang:english',
        '(bitcoin OR ethereum OR cryptocurrency) sourcelang:english',
    ],
}

def load_previous():
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def is_english(value):
    value = str(value or "").strip().lower()
    return value in ("english", "eng", "en")

def fetch_articles(query):
    params = urlencode({
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 50,
        "timespan": "24h",
        "sort": "DateDesc",
    })
    req = Request(
        API + "?" + params,
        headers={
            "User-Agent": "StockPilotAI-News/1.1 (headline links; https://www.technofront.org/)",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        content_type = response.headers.get("Content-Type", "").lower()
        if response.status != 200:
            raise RuntimeError("GDELT HTTP status " + str(response.status))
    if "json" not in content_type and not body.lstrip().startswith("{"):
        raise RuntimeError("GDELT returned a non-JSON response (possibly rate-limited): " + body[:180])
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GDELT returned invalid JSON: " + body[:180]) from exc
    rows = payload.get("articles", []) if isinstance(payload, dict) else []
    clean, seen_urls, seen_titles = [], set(), set()
    for row in rows:
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        language = row.get("language") or ""
        if not title or not is_english(language):
            continue
        if not url.startswith(("https://", "http://")) or url in seen_urls:
            continue
        normalized_title = " ".join(title.lower().split())
        if normalized_title in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(normalized_title)
        clean.append({
            "title": title[:300],
            "url": url,
            "source": str(row.get("domain") or row.get("source") or "Original publisher")[:120],
            "published": str(row.get("seendate") or ""),
            "language": "English",
        })
        if len(clean) >= 12:
            break
    return clean

def fetch_category(queries):
    last_error = None
    for query_index, query in enumerate(queries):
        for attempt in range(3):
            try:
                articles = fetch_articles(query)
                if articles:
                    return articles
                last_error = RuntimeError("No English articles matched this query")
                break
            except (HTTPError, URLError, TimeoutError, RuntimeError, OSError, ValueError) as exc:
                last_error = exc
                print("GDELT request attempt", attempt + 1, "failed:", str(exc)[:240])
                if attempt < 2:
                    time.sleep(8 * (attempt + 1))
        if query_index < len(queries) - 1:
            time.sleep(8)
    raise RuntimeError(str(last_error or "No matching English articles"))

def main():
    previous = load_previous()
    old_sections = previous.get("sections", {}) if isinstance(previous.get("sections"), dict) else {}
    sections = dict(old_sections)
    updated = []
    for index, (key, queries) in enumerate(QUERIES.items()):
        if index:
            time.sleep(8)  # GDELT asks clients to leave at least five seconds between requests.
        try:
            articles = fetch_category(queries)
            sections[key] = articles
            updated.append(key)
            print("Updated", key, "with", len(articles), "English headlines")
        except Exception as exc:
            print("Keeping cached", key, "headlines:", str(exc)[:300])
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
