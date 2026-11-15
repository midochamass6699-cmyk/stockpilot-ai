/**
 * StockPilot AI country edition router
 *
 * Cloudflare Worker route: technofront.org/*
 * Optional second route: www.technofront.org/*
 *
 * US visitors opening the homepage are sent to /us/.
 * Canadian visitors remain on /.
 * A manual Canada/US choice is remembered in a cookie.
 * Other countries remain on the default homepage.
 * Deep links and assets are never redirected.
 */
const COOKIE_NAME = "sp_country_choice";

function readCookie(header, name) {
  if (!header) return "";
  const prefix = name + "=";
  const entry = header.split(";").map(part => part.trim()).find(part => part.startsWith(prefix));
  if (!entry) return "";
  try {
    return decodeURIComponent(entry.slice(prefix.length));
  } catch {
    return "";
  }
}

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (url.hostname !== "technofront.org" && url.hostname !== "www.technofront.org") {
      return fetch(request);
    }

    // Only route the homepage; leave all deep links and assets untouched.
    if (url.pathname !== "/" && url.pathname !== "/index.html") {
      return fetch(request);
    }

    // A visitor's manual choice takes priority over IP-country detection.
    const savedChoice = readCookie(request.headers.get("Cookie"), COOKIE_NAME);
    let edition = "";

    if (savedChoice === "ca" || savedChoice === "us") {
      edition = savedChoice;
    } else {
      const detectedCountry = request.cf && request.cf.country;
      if (detectedCountry === "US") edition = "us";
      if (detectedCountry === "CA") edition = "ca";
    }

    // Visitors outside Canada and the United States use the default edition.
    if (!edition) return fetch(request);

    const destination = edition === "us" ? "/us/" : "/";
    if (url.pathname === destination) return fetch(request);

    url.pathname = destination;
    return Response.redirect(url.toString(), 302);
  }
};
