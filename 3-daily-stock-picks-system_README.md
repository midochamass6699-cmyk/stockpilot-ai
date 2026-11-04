# 3 Daily Stock Picks — free automated prototype

This project creates a daily, rules-based shortlist of three US and Canadian stocks and publishes it to a static landing page.

## What it does
- Screens a curated starter universe of 18 tickers (10 US, 8 TSX).
- Downloads daily end-of-day OHLCV history from Alpha Vantage.
- Scores each symbol using:
  - 50% trend and momentum (20/50-session returns and 50-session moving average)
  - 25% recent pullback context (distance from the 100-session high; **not** intrinsic value)
  - 15% volume participation
  - 10% RSI balance
- Publishes the top three candidates with a reason and risk note.
- Runs on GitHub Actions on weekdays at 5:30 p.m. Toronto time, and can also be run manually.

## Important limitations
- The free Alpha Vantage service currently advertises 25 API requests/day. This workflow requests up to 18 symbols once per weekday, with a delay between calls. A free key is required.
- Data is end-of-day, not real-time. The daily endpoint's default compact response provides the recent 100 data points.
- The requested “value” component is **not true fundamental valuation**. This free prototype uses recent pullback context as an entry-context proxy. It does not score P/E, P/B, free cash flow, debt, intrinsic value, or company quality.
- This is a screening experiment, not investment advice or a prediction. Backtest and paper-trade before relying on it.
- API coverage and ticker symbol validity can change. If a symbol is unsupported, the script skips it and reports the error in `picks.json`.

## Setup (no paid tools required)

1. Create a free account and API key at https://www.alphavantage.co/support/#api-key
2. Create a free GitHub account at https://github.com/
3. Create a new **public** GitHub repository named `3-daily-stock-picks` (GitHub Pages is free for public repositories).
4. Upload the contents of this folder to the repository, keeping the `.github/workflows` folder.
5. In the repository, open **Settings → Secrets and variables → Actions → New repository secret**:
   - Name: `ALPHAVANTAGE_API_KEY`
   - Value: your Alpha Vantage API key
6. Open **Settings → Pages** and set **Deploy from a branch**, branch `main`, folder `/docs`, then Save.
7. Open **Actions → Update daily stock picks → Run workflow** to make the first run. The scheduled workflow will run on weekdays afterward.
8. Your page will be published at `https://YOUR-GITHUB-USERNAME.github.io/3-daily-stock-picks/` after Pages finishes deploying.

## Test locally (optional)
```bash
export ALPHAVANTAGE_API_KEY="your_key_here"
python stock_picker.py
```
Then serve the `docs` folder with any local static web server.

## Change the monitored stocks
Edit `UNIVERSE` in `stock_picker.py`. Keep the number of symbols below your provider's daily request limit. Alpha Vantage's Toronto Stock Exchange example uses the `.TRT` suffix (for example `SHOP.TRT`).
