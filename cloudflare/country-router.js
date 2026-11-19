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
      let edition = "";
      if (savedChoice === "ca" || savedChoice === "us") {
        edition = savedChoice;
      } else {
        const detectedCountry = request.cf && request.cf.country;
        if (detectedCountry === "US") edition = "us";
        if (detectedCountry === "CA") edition = "ca";
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

    const pagePath = url.pathname.replace(/index\.html$/i, "").replace(/\/$/, "") || "/";
    if (!["/", "/fr", "/es", "/de", "/us"].includes(pagePath)) return response;

    let html = await response.text();
    const desktopMarkup = '<span id="tf-visitor-counter" aria-live="polite">YOU ARE VISITOR NUMBER …</span>';
    const mobileMarkup = '<span id="tf-visitor-counter-mobile" aria-live="polite">YOU ARE VISITOR NUMBER …</span>';

    // Place one copy beside the language links and one beside the mobile menu toggle.
    const langClose = '</div>\n</div>\n<button class="nav-toggle"';
    if (html.includes(langClose)) {
      html = html.replace(langClose, '</div>\n' + desktopMarkup + '\n</div>\n' + mobileMarkup + '\n<button class="nav-toggle"');
    } else {
      html = html.replace('<button class="nav-toggle"', mobileMarkup + '<button class="nav-toggle"');
    }

    const style = '<style id="tf-visitor-counter-style">#tf-visitor-counter{display:inline-flex;align-items:center;justify-content:center;margin:2px 0 0 auto;padding:5px 10px;border:1px solid #ffd629;border-radius:999px;background:#101010;color:#ffd629;font:800 10px/1.2 Arial,sans-serif;letter-spacing:.035em;white-space:nowrap}#tf-visitor-counter-mobile{display:none}@media(max-width:760px){#tf-visitor-counter{display:none!important}#tf-visitor-counter-mobile{display:inline-flex;align-items:center;justify-content:center;position:absolute;right:60px;top:50%;transform:translateY(-50%);max-width:calc(100% - 150px);overflow:hidden;text-overflow:ellipsis;padding:5px 7px;border:1px solid #ffd629;border-radius:999px;background:#101010;color:#ffd629;font:800 9px/1.2 Arial,sans-serif;white-space:nowrap}.topbar .nav{position:relative}}</style>';
    html = html.replace("</head>", style + "</head>");

    const script = '<script id="tf-visitor-counter-script">(function(){var els=[document.getElementById("tf-visitor-counter"),document.getElementById("tf-visitor-counter-mobile")].filter(Boolean);if(!els.length)return;fetch("/api/visitor-number",{cache:"no-store",credentials:"same-origin"}).then(function(r){if(!r.ok)throw new Error("counter unavailable");return r.json()}).then(function(data){if(Number.isFinite(Number(data.visitorNumber))){var label="YOU ARE VISITOR NUMBER "+Number(data.visitorNumber).toLocaleString("en-CA");els.forEach(function(el){el.textContent=label})}}).catch(function(){els.forEach(function(el){el.hidden=true})})})();</script>';
    html = html.replace("</body>", script + "</body>");

    const headers = new Headers(response.headers);
    headers.delete("content-length");
    headers.delete("content-encoding");
    headers.delete("etag");
    return new Response(html, { status: response.status, statusText: response.statusText, headers });
  }
};
