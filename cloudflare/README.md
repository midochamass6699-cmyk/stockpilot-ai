# StockPilot AI SEC Financial Report API

This Worker provides a small server-side bridge between the GitHub Pages site and the U.S. SEC's public EDGAR APIs.

## What it does

- Searches the SEC company ticker directory by company name or ticker.
- Retrieves the selected company's SEC submissions and Company Facts.
- Returns up to three annual reporting periods for supported US-GAAP financial measures.
- Links to recent original SEC filings.
- Does not provide stock quotes, predictions, trading signals, or investment recommendations.

Coverage is not universal. It is limited to companies in the SEC ticker directory with supported annual US-GAAP facts. Missing figures are returned as missing, never estimated.

## Deploy in Cloudflare

1. Sign in to the Cloudflare dashboard and open **Workers & Pages**.
2. Choose **Create application** → **Create Worker**.
3. Name it `stockpilot-sec-api`.
4. Open the Worker editor, replace the starter code with the complete contents of `cloudflare/financial-report-worker.js`, and deploy.
5. In the Worker settings, open **Variables and Secrets** and add a text variable named `SEC_USER_AGENT`. Set its value to:
   `StockPilotAI/1.0 (contact: YOUR_EMAIL_ADDRESS)`
   Replace the placeholder with a monitored contact email address. The SEC asks automated clients to identify themselves with a User-Agent contact.
6. Open **Settings** → **Domains & Routes** → **Add** → **Custom Domain**. Enter `api.technofront.org` and follow Cloudflare's prompts. The zone for technofront.org must be active in this Cloudflare account.
7. Test these URLs in a browser:
   - `https://api.technofront.org/api/health`
   - `https://api.technofront.org/api/search?q=Microsoft`
   The second should return a JSON list including Microsoft and its SEC CIK.

## Website connection

The English and French pages call `https://api.technofront.org`. The custom domain must be active before company search will work.

## API endpoints

- `GET /api/health`
- `GET /api/search?q=Microsoft`
- `GET /api/company?cik=0000789019`

Only GET requests are supported. CORS is restricted to the StockPilot AI website origins.

## Data and limitations

The Worker uses:
- `https://www.sec.gov/files/company_tickers.json`
- `https://data.sec.gov/submissions/CIK##########.json`
- `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

The first report version uses annual 10-K, 20-F and 40-F filings and USD-denominated US-GAAP facts. It does not fetch real-time or delayed stock prices. Some companies, foreign accounting standards and individual metrics may not be represented. Always inspect the linked original filings.

## Local configuration

If the Worker is deployed under a different custom domain, change the `API_BASE` constant in both report-generator pages to that exact HTTPS origin.
