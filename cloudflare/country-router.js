/**
 * StockPilot AI country edition router.
 * Deploy as a Cloudflare Worker and attach route: technofront.org/*
 * Only the site root is redirected. Deep links remain untouched.
 */
const COOKIE = "sp_country_choice";
const MAX_AGE = 60 * 60 * 24 * 180;

function readCookie(header, name) {
  const item = (header || "").split(";").map(v => v.trim()).find(v => v.startsWith(name + "="));
  return item ? decodeURIComponent(item.slice(name.length + 1)) : "";
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.hostname !== "technofront.org" && url.hostname !== "www.technofront.org") {
      return fetch(request);
    }

    // Respect explicit deep links and assets; only route the homepage.
    if (url.pathname !== "/" && url.pathname !== "/index.html") {
      return fetch(request);
    }

    const saved = readCookie(request.headers.get("Cookie"), COOKIE);
    const country = saved === "ca" || saved === "us"
      ? saved
      : (request.cf && request.cf.country === "US" ? "us"
        : request.cf && request.cf.country === "CA" ? "ca" : "");

    if (!country) return fetch(request);

    const target = country === "us" ? "/us/" : "/";
    if ((country === "us" && url.pathname === "/us/") || url.pathname === target) {
      return fetch(request);
    }

    // Avoid redirect loops and preserve query parameters.
    url.pathname = target;
    return Response.redirect(url.toString(), 302);
  }
};
