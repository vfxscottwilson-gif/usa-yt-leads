"""Read visible public channel About/More details. Never reveal protected email fields."""
import re
from urllib.parse import urlsplit, parse_qs

EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
BLOCK = re.compile(r'verify (?:you are|that you.re) human|unusual traffic|complete the captcha|not a robot|sign in to confirm|automated queries', re.I)


def blocked_reason(page):
    if re.search(r'/sorry/|/challenge|accounts\.google\.com|consent\.youtube\.com',page.url,re.I):
        return 'Login consent or automated challenge page'
    if BLOCK.search(page.locator('body').inner_text(timeout=2000)[:40000]):
        return 'Automated challenge or login confirmation visible'
    for frame in page.locator('iframe[src*="recaptcha"], iframe[src*="hcaptcha"]').all():
        if frame.is_visible():
            return 'Visible CAPTCHA'
    return ''


def collect_panel(page):
    reason = blocked_reason(page)
    if reason:
        return {'status':'blocked','reason':reason,'emails':[],'links':[]}
    try:  # the page action fires right after DOM load, before YouTube has drawn the channel header
        page.wait_for_selector('ytd-about-channel-renderer, yt-description-preview-view-model, #channel-header-container', timeout=6000)
    except Exception:
        pass
    panel_selectors = ['ytd-about-channel-renderer', 'ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-about"]', 'tp-yt-paper-dialog']
    def panel():
        for selector in panel_selectors:
            for item in page.locator(selector).all():
                if item.is_visible() and (selector == 'ytd-about-channel-renderer' or re.search(r'description|more info|links|about',item.inner_text(timeout=1000),re.I)):
                    return item
        return None
    scope = panel()
    if scope is None:
        for selector in ['yt-description-preview-view-model button', '#channel-header-container #description-container', 'yt-description-preview-view-model']:
            item = page.locator(selector).first
            if item.count() and item.is_visible():
                try:
                    item.click(timeout=2000)
                    page.wait_for_timeout(400)
                except Exception:
                    continue
                if blocked_reason(page):
                    return {'status':'blocked','reason':'Challenge appeared while opening About','emails':[],'links':[]}
                scope = panel()
                if scope is not None:
                    break
    if scope is None:
        return {'status':'panel_missing','reason':'Public About panel not found within selector budget','emails':[],'links':[]}
    text = scope.evaluate("""root => {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const parts = []; let n;
        while (n = walker.nextNode()) {
            const e = n.parentElement;
            if (e && e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden'
                && !e.closest('script,style,[hidden],[aria-hidden="true"]')) parts.push(n.textContent);
        }
        return parts.join('\\n');
    }""")
    if BLOCK.search(text):
        return {'status':'blocked','reason':'Challenge in About panel','emails':[],'links':[]}
    links = scope.locator('a[href]').evaluate_all("nodes => nodes.filter(n => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden').map(n => n.href)")
    normalized = []
    for url in links:
        parts = urlsplit(url)
        if parts.hostname in ('www.youtube.com','youtube.com') and parts.path == '/redirect':
            url = parse_qs(parts.query).get('q',[url])[0]
        if url.startswith(('https://','http://')) and url not in normalized:
            normalized.append(url)
    protected = bool(re.search(r'view email address|sign in to (?:view|see).*email',text,re.I))
    return {'status':'partial' if protected else 'ok',
        'reason':'Protected email control left untouched' if protected else 'Visible public About details collected',
        'emails':sorted(set(EMAIL.findall(text))), 'links':normalized[:40]}


def fetch_channel(channel_id, cfg):
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',channel_id):
        raise ValueError('Invalid Channel ID')
    from scrapling.fetchers import DynamicFetcher
    result = {}
    def action(page):
        try:
            page.set_default_timeout(2000)
            result.update(collect_panel(page))
        except Exception as exc:
            result.update(status='error',reason=type(exc).__name__,emails=[],links=[])
    response = DynamicFetcher.fetch('https://www.youtube.com/channel/'+channel_id+'/about',
        headless=True, network_idle=False, load_dom=True, timeout=15000, wait=0,
        disable_resources=True, google_search=False, page_action=action,
        useragent='YTLeadResearch/1.0 (public channel contact research)',
        additional_args={'service_workers':'block','accept_downloads':False,'locale':'en-US'},
        selector_config={'adaptive':False})
    if not result:
        result = {'status':'error','reason':'No panel callback result','emails':[],'links':[]}
    return result
