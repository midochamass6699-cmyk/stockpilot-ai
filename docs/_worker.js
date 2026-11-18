export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Shared visit counter. One increment per homepage load, including repeat visits.
    if (url.pathname === "/api/visitor-number") {
      if (request.method !== "GET") {
        return new Response("Method not allowed", { status: 405, headers: { "Allow": "GET" } });
      }
      if (!env.VISITOR_DB) {
        return Response.json({ error: "Visitor counter is not configured yet." }, {
          status: 503,
          headers: { "Cache-Control": "no-store" }
        });
      }
      try {
        const row = await env.VISITOR_DB
          .prepare("UPDATE visitor_counter SET value = value + 1 WHERE id = 1 RETURNING value")
          .first();
        if (!row) {
          return Response.json({ error: "Visitor counter has not been initialized." }, {
            status: 503,
            headers: { "Cache-Control": "no-store" }
          });
        }
        return Response.json({ visitorNumber: row.value }, {
          headers: {
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Access-Control-Allow-Origin": url.origin,
            "X-Content-Type-Options": "nosniff"
          }
        });
      } catch {
        return Response.json({ error: "Visitor counter temporarily unavailable." }, {
          status: 503,
          headers: { "Cache-Control": "no-store" }
        });
      }
    }

    const response = await env.ASSETS.fetch(request);
    const contentType = response.headers.get("content-type") || "";
    if (!response.ok || !contentType.includes("text/html")) return response;
    let html = await response.text();

    // Remove analytics and advertising tags from static HTML. The consent
    // manager loads them only after the visitor opts in.
    html = html.replace(/<script\\b[^>]*src=["'][^"']*googletagmanager\\.com\\/gtag\\/js[^"']*["'][^>]*>\\s*<\\/script>/gi, "");
    html = html.replace(/<script\\b[^>]*src=["'][^"']*googletagmanager\\.com\\/gtm\\.js[^"']*["'][^>]*>\\s*<\\/script>/gi, "");
    html = html.replace(/<script\\b[^>]*>[\\s\\S]*?googletagmanager\\.com\\/gtm\\.js[\\s\\S]*?<\\/script>/gi, "");
    html = html.replace(/<noscript\\b[^>]*>\\s*<iframe[^>]*googletagmanager\\.com\\/ns\\.html[\\s\\S]*?<\\/noscript>/gi, "");
    html = html.replace(/<script\\b[^>]*>[\\s\\S]*?gtag\\(['"]config['"],\\s*['"]G-VL62LP5NZ9['"][\\s\\S]*?<\\/script>/gi, "");
    html = html.replace(/<script\\b[^>]*>[\\s\\S]*?function\\s+gtag\\s*\\(\\)\\s*\\{[\\s\\S]*?<\\/script>/gi, "");
    html = html.replace(/<script\\b[^>]*src=["'][^"']*pagead\\.googlesyndication\\.com\\/pagead\\/js\\/adsbygoogle\\.js[^"']*["'][^>]*>\\s*<\\/script>/gi, "");
    html = html.replace(/<script\\b[^>]*>[\\s\\S]*?impactcdn\\.com[\\s\\S]*?<\\/script>/gi, "");

    if (!html.includes("/assets/privacy-consent.js")) {
      html = html.replace(/<\\/head>/i, '<script defer src="/assets/privacy-consent.js"></script>\\n</head>');
    }
    const pagePath = url.pathname.replace(/index\\.html$/i, "").replace(/\\/$/, "") || "/";
    if (["/", "/fr", "/es", "/de", "/us"].includes(pagePath) && !/\\bdata-site-advertising=/i.test(html.slice(0, html.indexOf(">") + 1))) {
      html = html.replace(/<html\\b/i, '<html data-site-advertising="true"');
    }
    if (["/", "/de", "/us"].includes(pagePath)) {
      html = html.replace(/<html\\b/i, '<html data-site-impact="true"');
    }
    const headers = new Headers(response.headers);
    headers.delete("content-length");
    headers.delete("content-encoding");
    headers.delete("etag");
    return new Response(html, { status: response.status, statusText: response.statusText, headers });
  }
};