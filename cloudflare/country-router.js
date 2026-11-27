/**
 * StockPilot AI country edition router + shared visitor counter.
 *
 * Cloudflare Worker route: technofront.org/*
 * D1 binding required on THIS Worker: VISITOR_DB
 */
const COOKIE_NAME = "sp_country_choice";

function readCookie(header, name) {
  if (!header) return "";
  const prefix = name + "=";
  const entry = header.split(";").map(part => part.trim()).find(part => part.startsWith(prefix));
  if (!entry) return "";
  try { return decodeURIComponent(entry.slice(prefix.length)); }
  catch { return ""; }
}

function json(data, status = 200) {
  return Response.json(data, {
    status,
    headers: { "Cache-Control": "no-store, no-cache, must-revalidate", "X-Content-Type-Options": "nosniff" }
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // The country-router Worker receives this route before the Pages project.
    // Serve the counter here so /api/visitor-number is not sent to the static origin.
    if (url.pathname === "/api/visitor-number") {
      if (request.method !== "GET") {
        return new Response("Method not allowed", { status: 405, headers: { "Allow": "GET" } });
      }
      if (!env.VISITOR_DB) return json({ error: "Visitor counter database binding is missing on the country-router Worker." }, 503);
      try {
        const row = await env.VISITOR_DB
          .prepare("UPDATE visitor_counter SET value = value + 1 WHERE id = 1 RETURNING value")
          .first();
        if (!row) return json({ error: "Visitor counter table is not initialized." }, 503);
        return json({ visitorNumber: row.value });
      } catch {
        return json({ error: "Visitor counter database error." }, 503);
      }
    }

    if (url.hostname !== "technofront.org" && url.hostname !== "www.technofront.org") {
      return fetch(request);
    }

    // Normalize language homepages to their trailing-slash canonical URLs.
    // Keep the query string and use a permanent redirect for search engines.
    if (url.pathname === "/fr" || url.pathname === "/es") {
      url.pathname += "/";
      return Response.redirect(url.toString(), 301);
    }

    // Only route the Canadian/US root homepage by visitor country.
    if (url.pathname === "/" || url.pathname === "/index.html") {
      const savedChoice = readCookie(request.headers.get("Cookie"), COOKIE_NAME);
      const detectedCountry = request.cf && request.cf.country;
      let edition = "";

      // Country detection takes priority for Canada and the United States.
      // A saved manual choice is only a fallback for visitors elsewhere.
      if (detectedCountry === "US") {
        edition = "us";
      } else if (detectedCountry === "CA") {
        edition = "ca";
      } else if (savedChoice === "ca" || savedChoice === "us") {
        edition = savedChoice;
      }

      if (edition) {
        const destination = edition === "us" ? "/us/" : "/";
        if (url.pathname !== destination) {
          url.pathname = destination;
          return Response.redirect(url.toString(), 302);
        }
      }
    }

    const response = await fetch(request);
    const contentType = response.headers.get("content-type") || "";
    if (!response.ok || !contentType.includes("text/html")) return response;
    let html = await response.text();

    // Apply one shared visual theme to every public HTML page.
    // Preview mockups are intentionally excluded; page copy, layout and scripts remain untouched.
    if (!/^\/(?:design-preview|preview|preview-phone)(?:\.html)?\/?$/i.test(url.pathname) && !url.pathname.startsWith("/app/") && !html.includes("technofront-theme.css")) {
      html = html.replace(/<\/head>/i, '<link rel="stylesheet" href="/assets/technofront-theme.css?v=20261126">\n</head>');
    }

    const pagePath = url.pathname.replace(/index\.html$/i, "").replace(/\/$/, "") || "/";

    // Add Statcounter to every HTML page served by this domain.
    // Keep existing page-level copies, and avoid adding a duplicate tracker.
    if (!html.includes("sc_project=13368384")) {
      const statcounterCode = `<!-- Default Statcounter code for technofront https://technofront.org -->
<script type="text/javascript">
var sc_project=13368384;
var sc_invisible=1;
var sc_security="58d29d99";
</script>
<script type="text/javascript"
src="https://secure.statcounter.com/counter/counter.js" async></script>
<noscript><div class="statcounter"><a title="Web Analytics"
href="https://statcounter.com/" target="_blank"><img class="statcounter"
src="https://c.statcounter.com/13368384/0/58d29d99/1/" alt="Web Analytics"
referrerPolicy="no-referrer-when-downgrade"></a></div></noscript>
<!-- End of Statcounter Code -->`;
      html = html.replace(/<\/body>/i, statcounterCode + "\n</body>");
    }

    // Populate the existing visitor counter only on the language homepages.
    // Do not create a second counter beside the language selector.
    if (["/", "/fr", "/es", "/de", "/us"].includes(pagePath)) {
      const visitorCounterScript = '<script id="tf-visitor-counter-script">(function(){var el=document.getElementById("tf-visitor-counter");if(!el)return;fetch("/api/visitor-number",{cache:"no-store",credentials:"same-origin"}).then(function(r){if(!r.ok)throw new Error("counter unavailable");return r.json()}).then(function(data){var n=Number(data&&data.visitorNumber);if(Number.isSafeInteger(n)&&n>0){el.textContent="YOU ARE VISITOR NUMBER "+n.toLocaleString("en-CA")}else{throw new Error("invalid counter value")}}).catch(function(){el.textContent="VISITOR COUNT UNAVAILABLE"})})();</script>';
      html = html.replace("</body>", visitorCounterScript + "</body>");
    }

    const headers = new Headers(response.headers);
    headers.delete("content-length");
    headers.delete("content-encoding");
    headers.delete("etag");
    return new Response(html, { status: response.status, statusText: response.statusText, headers });
  }
};
