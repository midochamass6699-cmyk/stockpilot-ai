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

    // Show the shared visit number on the five homepage editions only.
    if (["/", "/fr", "/es", "/de", "/us"].includes(pagePath)) {
      const counterMarkup = '<span id="tf-visitor-counter" aria-live="polite">YOU ARE VISITOR NUMBER …</span>';
      const toggleAt = html.indexOf('<button class="nav-toggle"');
      if (toggleAt >= 0) {
        const menuCloseAt = html.lastIndexOf('</div>', toggleAt);
        if (menuCloseAt >= 0) html = html.slice(0, menuCloseAt) + counterMarkup + html.slice(menuCloseAt);
      }
      const counterStyle = '<style id="tf-visitor-counter-style">#tf-visitor-counter{display:inline-flex;align-items:center;justify-content:center;align-self:flex-end;margin:2px 0 0 auto;padding:5px 10px;border:1px solid #ffd629;border-radius:999px;background:#101010;color:#ffd629;font:800 10px/1.2 Arial,sans-serif;letter-spacing:.035em;white-space:nowrap}@media(max-width:760px){#tf-visitor-counter{align-self:center;margin:8px auto 0;font-size:10px}}</style>';
      html = html.replace("</head>", counterStyle + "</head>");
      const counterScript = '<script id="tf-visitor-counter-script">(function(){var el=document.getElementById("tf-visitor-counter");if(!el)return;fetch("/api/visitor-number",{cache:"no-store",credentials:"same-origin"}).then(function(r){if(!r.ok)throw new Error("counter unavailable");return r.json()}).then(function(data){if(Number.isFinite(Number(data.visitorNumber)))el.textContent="YOU ARE VISITOR NUMBER "+Number(data.visitorNumber).toLocaleString("en-CA")}).catch(function(){el.hidden=true})})();</script>';
      html = html.replace("</body>", counterScript + "</body>");
    }

    const headers = new Headers(response.headers);
    headers.delete("content-length");
    headers.delete("content-encoding");
    headers.delete("etag");
    return new Response(html, { status: response.status, statusText: response.statusText, headers });
  }
};