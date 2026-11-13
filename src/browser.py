"""Standard headless Chromium rendering of public pages, without stealth or login."""
import re
from urllib.parse import urlsplit

CHALLENGE = re.compile(r'verify you are human|complete the captcha|log in to continue|checking your browser|just a moment', re.I)
# Facebook is allowed: a public page shows its Contact info email to a plain logged-out browser (verified 4 of 5 pages).
# Login, checkpoint and challenge pages are still refused below.
EXCLUDED = {'youtube.com', 'youtu.be', 'instagram.com', 'linkedin.com'}


def render_public(url, cfg):
    from playwright.sync_api import sync_playwright
    from .contacts import safe_public_url, host
    domain = host(url)
    if not safe_public_url(url) or any(domain == d or domain.endswith('.' + d) for d in EXCLUDED):
        raise ValueError('Browser rendering is limited to public websites')
    limit = cfg.get('browser_timeout_seconds', 15) * 1000
    maximum_requests = cfg.get('browser_max_requests_per_page', 30)
    counts = {'allowed': 0, 'blocked': 0}
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        try:
            context = browser.new_context(service_workers='block', accept_downloads=False)
            # Validate each resource, navigation and redirect. Block unnecessary heavy resources.
            def guard(route):
                request = route.request
                if (counts['allowed'] >= maximum_requests or request.method not in ('GET', 'HEAD')
                        or request.resource_type in ('image', 'media', 'font')
                        or not safe_public_url(request.url)):
                    counts['blocked'] += 1
                    route.abort()
                else:
                    counts['allowed'] += 1
                    route.continue_()
            context.route('**/*', guard)
            context.route_web_socket('**/*', lambda socket: socket.close())
            page = context.new_page()
            page.set_default_timeout(limit)
            response = page.goto(url, wait_until='domcontentloaded', timeout=limit)
            if response is None or response.status >= 400:
                raise ValueError('Public page unavailable')
            page.wait_for_timeout(cfg.get('browser_wait_ms', 1000))
            text = page.locator('body').inner_text(timeout=limit)
            if CHALLENGE.search(text[:20000]) or re.search(r'/login|/checkpoint|/challenge', urlsplit(page.url).path, re.I):
                raise ValueError('Public page requires human access')
            # Ordinary HTML disclosures only; no arbitrary buttons, forms or protected email reveals.
            for summary in page.locator('details:not([open]) > summary').all()[:3]:
                if summary.is_visible():
                    summary.click(timeout=1000)
            document = page.content()
            if len(document.encode('utf-8')) > 500000:
                # Big app pages (Facebook is ~1 MB of script): keep only the visible text and contact links.
                import html as _html
                contact_links = page.eval_on_selector_all('a[href^="mailto:"], a[href^="tel:"]', 'nodes => nodes.map(n => n.href)')
                document = ('<html><body>' + _html.escape(text[:100000])
                            + ''.join('<a href="' + _html.escape(h) + '">c</a>' for h in contact_links[:20]) + '</body></html>')
            return page.url, document, counts['allowed']
        finally:
            browser.close()
