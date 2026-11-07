        "sector": meta["sector"],
        "currency": meta["currency"],
        "quote_time": m["price_date"] + " (daily close)",
        "reason": "; ".join(reasons or ["highest momentum score in the screened candidate pool"]) + ".",
        "risk": "; ".join(risks) + ".",
        **m,
    }


def eligible(stock, penny=False):
    if stock["return_20d"] <= 0 or not stock["above_20day_average"]:
        return False
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
    print("StockPilot Free Momentum v3 — public US + Canada candidate screeners")
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
            "Momentum score 0–100: 10% 5-day return, 30% 20-day return, 25% 50-day return, "
            "20% relative volume, 15% trend alignment; deductions for elevated RSI and volatility. "
            "Requires positive 20-day momentum and price above the 20-day average."
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
