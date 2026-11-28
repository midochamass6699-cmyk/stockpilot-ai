# Final Cloudflare activation — StockPilot AI country router

The website-side changes and Worker code are already committed.

## The only remaining task

1. Open Cloudflare and select the `technofront.org` website.
2. Go to **Workers & Pages** and create a Worker named `stockpilot-country-router`.
3. Open the Worker editor and replace the sample code with the complete contents of this file:
   [cloudflare/country-router.js](./country-router.js)
4. Click **Deploy**.
5. Open the Worker **Settings → Domains & Routes** and add this route:
   `technofront.org/*`
6. Save the route.

If your visitors also use `www.technofront.org`, add a second route:
`www.technofront.org/*`

## Expected behaviour after activation

- A visitor from the United States who opens the homepage is redirected to `/us/`.
- A visitor from Quebec is redirected to `/fr/`.
- A visitor from the rest of Canada stays on `/`.
- Choosing **CANADA** or **UNITED STATES** in the site's edition selector saves that choice for 180 days and takes priority over automatic country detection.
- Visitors from other countries stay on the default homepage.
- Existing article pages, language pages, scripts, images and other deep links are not redirected.

The Worker uses a temporary HTTP 302 redirect. This is intentional so the routing can be changed later without a permanent browser or search-engine redirect being cached.

## Important

Do not create or share an API token for this setup. The final activation is done from the Cloudflare dashboard. The Worker is not active until its route has been added and saved.
