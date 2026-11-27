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
    html = html.replace(/<script\b[^>]*src=["'][^"']*googletagmanager\.com\/gtag\/js[^"']*["'][^>]*>\s*<\/script>/gi, "");
    html = html.replace(/<script\b[^>]*src=["'][^"']*googletagmanager\.com\/gtm\.js[^"']*["'][^>]*>\s*<\/script>/gi, "");
    html = html.replace(/<script\b[^>]*>[\s\S]*?googletagmanager\.com\/gtm\.js[\s\S]*?<\/script>/gi, "");
    html = html.replace(/<noscript\b[^>]*>\s*<iframe[^>]*googletagmanager\.com\/ns\.html[\s\S]*?<\/noscript>/gi, "");
    html = html.replace(/<script\b[^>]*>[\s\S]*?gtag\(['"]config['"],\s*['"]G-VL62LP5NZ9['"][\s\S]*?<\/script>/gi, "");
    html = html.replace(/<script\b[^>]*>[\s\S]*?function\s+gtag\s*\(\)\s*\{[\s\S]*?<\/script>/gi, "");
    html = html.replace(/<script\b[^>]*src=["'][^"']*pagead\.googlesyndication\.com\/pagead\/js\/adsbygoogle\.js[^"']*["'][^>]*>\s*<\/script>/gi, "");
    html = html.replace(/<script\b[^>]*>[\s\S]*?impactcdn\.com[\s\S]*?<\/script>/gi, "");

    if (!html.includes("/assets/privacy-consent.js")) {
      html = html.replace(/<\/head>/i, '<script defer src="/assets/privacy-consent.js"></script>\n</head>');
    }
    // Add the shared Technofront visual theme to site pages without changing page content.
    // Preview-only mockups and the installable PWA keep their dedicated presentation.
    if (!/^\/(?:design-preview|preview|preview-phone)(?:\.html)?\/?$/i.test(url.pathname) && !url.pathname.startsWith("/app/") && !html.includes("technofront-theme.css")) {
      html = html.replace(/<\/head>/i, '<link rel="stylesheet" href="/assets/technofront-theme.css?v=20261126">\\n</head>');
    }

    const pagePath = url.pathname.replace(/index\.html$/i, "").replace(/\/$/, "") || "/";
    if (["/", "/fr", "/es", "/de", "/us"].includes(pagePath) && !/\bdata-site-advertising=/i.test(html.slice(0, html.indexOf(">") + 1))) {
      html = html.replace(/<html\b/i, '<html data-site-advertising="true"');
    }
    if (["/", "/de", "/us"].includes(pagePath)) {
      html = html.replace(/<html\b/i, '<html data-site-impact="true"');
    }

    // Add Statcounter to every HTML page served by this Pages Worker.
    // Existing page-level copies are left untouched to prevent duplicate tracking.
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

    // The homepage HTML owns the single centered visitor counter.
    // Avoid injecting a second header/mobile counter.
    const headers = new Headers(response.headers);
    headers.delete("content-length");
    headers.delete("content-encoding");
    headers.delete("etag");
    return new Response(html, { status: response.status, statusText: response.statusText, headers });
  }
};