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
    // The homepage HTML contains the single centered counter badge.
    // Do not inject a second counter beside the language selector.
    return response;
  }
};
