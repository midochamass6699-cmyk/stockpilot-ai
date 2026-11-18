export default {
  async fetch(request, env) {
    const response = await env.ASSETS.fetch(request);
    const contentType = response.headers.get("content-type") || "";
    if (!response.ok || !contentType.includes("text/html")) return response;
    const url = new URL(request.url);
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
    if (["/", "/fr/", "/es/", "/de/", "/us/"].includes(url.pathname)) {
      html = html.replace(/<html\b/i, '<html data-site-advertising="true"');
    }
    const headers = new Headers(response.headers);
    headers.delete("content-length"); headers.delete("content-encoding"); headers.delete("etag");
    headers.set("cache-control", "public, max-age=0, must-revalidate");
    return new Response(html, { status: response.status, statusText: response.statusText, headers });
  }
};