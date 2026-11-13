"""Bounded public-page research. No CAPTCHA, login, mailbox guessing or SMTP probing."""
import html
import json
import ipaddress
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, unquote
from .social_links import canonical_profile
from .names import email_allowed, domain_matches_name, people_from_text
from .task_runner import run_browser_task

EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
URL = re.compile(r'https?://[^\s<>\"\)]+')
CONTACT = re.compile(r'contact|inquir|business|email|e-mail|reach|partnership|booking', re.I)
SPONSOR = re.compile(r'sponsor|affiliate|discount code|promo code', re.I)
SOCIALS = {'instagram.com': 'Instagram', 'facebook.com': 'Facebook', 'linkedin.com': 'LinkedIn'}
# Links in the About panel that are not the creator's website: meeting booking and podcast-listening apps.
NOT_WEBSITE = re.compile(r'calendly\.com|cal\.com|savvycal|tidycal|zoom\.us|acuityscheduling|meetings\.hubspot|youcanbook|chilipiper|setmore|podcasts\.apple|music\.apple|spotify\.com|overcast\.fm|pocketcasts|castbox|iheart\.com|audible\.com|amazon\.|amzn\.', re.I)
SKIP = {'youtube.com', 'youtu.be', 'google.com', 'amazon.com', 'amzn.to', 'bit.ly',
        'twitter.com', 'x.com', 'tiktok.com', 'discord.gg'}
BIO = {'linktr.ee', 'beacons.ai', 'stan.store', 'bio.link'}

def clean_url(url, base=''):
    """Reject malformed external input before it reaches URL parsing or requests."""
    try:
        value = html.unescape(str(url)).strip().rstrip('.,;')
        value = urljoin(base, value) if base else value
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or not parts.hostname:
            return ''
        if parts.username or parts.password or parts.port not in (None, 80, 443):
            return ''
        if any(c.isspace() for c in value):
            return ''
        return value
    except (ValueError, TypeError):
        return ''


def host(url):
    value = clean_url(url)
    return (urlsplit(value).hostname or '').lower().removeprefix('www.') if value else ''


def is_domain(url, domains):
    domain = host(url)
    return any(domain == d or domain.endswith('.' + d) for d in domains)


REFERENCE_DOMAINS = {'github.com', 'doi.org', 'nih.gov', 'pubmed.ncbi.nlm.nih.gov'}


def normalize_phone(value):
    value = value.strip()
    digits = re.sub(r'\D', '', value)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10 and (not value.startswith('+') or value.startswith('+1')):
        return f'{digits[:3]} {digits[3:6]} {digits[6:]}'
    return value.lstrip('+=-@ ')  # a leading + or = would make Google Sheets read the cell as a formula


PHONE = re.compile(r'(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)')
YT_CHANNEL = re.compile(r'https?://(?:www\.|m\.)?youtube\.com/(channel/UC[\w-]{22}|@[\w.\-]+)', re.I)


def record_link(result, url, source):
    url = canonical_profile(clean_url(url))
    if not url:
        return
    parts = urlsplit(url)
    def add(column):
        existing = result['links'].get(column, '').splitlines()
        existing = [v for v in existing if v]
        if url not in existing:
            result['links'][column] = '\n'.join(existing + [url])
    domain = host(url)
    if domain == 'linkedin.com':
        add('LinkedIn')
        if parts.path.startswith('/in/'):
            add('Personal LinkedIn')
        elif parts.path.startswith('/company/'):
            add('Company LinkedIn')
    elif domain in ('twitter.com', 'x.com'):
        add('Twitter And X')
    else:
        for network, column in SOCIALS.items():
            if domain == network:
                add(column)
    # Provenance retained internally; do not fill user-facing cells with every crawled URL.
    result.setdefault('_link_evidence', {})[url] = source


def safe_public_url(url):
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
            return False
        if parts.port not in (None, 80, 443):
            return False
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(x[4][0]).is_global for x in addresses)
    except (ValueError, OSError):
        return False

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text, self.links, self.mail, self.phones = [], [], [], []
        self.hidden = 0
        self.structured = []
        self.ld_buffer = None

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        values = dict(attrs)
        if tag == 'script' and values.get('type','').lower() == 'application/ld+json':
            self.ld_buffer = ''
        target = values.get('href', '')
        if tag == 'a' and target:
            self.links.append(target)
            if target.lower().startswith('mailto:'):
                self.mail.extend(EMAIL.findall(unquote(target.split('?', 1)[0])))
            if target.lower().startswith('tel:'):
                self.phones.append(unquote(target[4:]).strip())

    def handle_endtag(self, tag):
        if tag == 'script' and self.ld_buffer is not None:
            try:
                self.structured.append(json.loads(self.ld_buffer))
            except ValueError:
                pass
            self.ld_buffer = None
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.ld_buffer is not None:
            self.ld_buffer += data
        if not self.hidden:
            self.text.append(data)

def people_from_structured(data, source):
    """Only explicit named organizational roles, not author-name guesses."""
    found = []
    if isinstance(data,list):
        for value in data:
            found.extend(people_from_structured(value,source))
    elif isinstance(data,dict):
        kind = data.get('@type','')
        kinds = kind if isinstance(kind,list) else [kind]
        if 'Organization' in kinds:
            for field, role in [('founder','Founder'),('employee','')]:
                persons = data.get(field,[])
                for person in persons if isinstance(persons,list) else [persons]:
                    if isinstance(person,dict) and person.get('name'):
                        designation = person.get('jobTitle') or role
                        if designation:
                            found.append(dict(full_name=person['name'],first_name=person.get('givenName',''),
                                designation=designation,source=source))
        if 'Person' in kinds and data.get('name') and data.get('jobTitle'):
            if re.search(r'founder|chief executive|\bceo\b|manager|team lead',str(data['jobTitle']),re.I):
                found.append(dict(full_name=data['name'],first_name=data.get('givenName',''),
                    designation=data['jobTitle'],source=source))
        for key,value in data.items():
            if key not in ('founder','employee') and isinstance(value,(list,dict)):
                found.extend(people_from_structured(value,source))
    return found

class Research:
    def __init__(self, cfg, metrics):
        self.cfg, self.metrics = cfg, metrics
        self.lock = threading.Lock()
        self.browser_slots = threading.BoundedSemaphore(cfg.get("browser_workers", 1))

    def fetch(self, url):
        import requests
        if self.cfg.get('browser_enabled', False) and is_domain(url, {'facebook.com'}):
            # A plain HTTP request never contains the page's email; the rendered page does.
            page = Page()
            self.render_fallback(url, page, wait=True)
            return url, (page if page.text or page.mail else None)
        # Validate every redirect, use normal certificate verification, cap response size.
        for _ in range(4):
            if not safe_public_url(url):
                return url, None
            with self.lock:
                if self.metrics['website_requests'] >= self.cfg['website_max_pages_per_run']:
                    return url, None
                self.metrics['website_requests'] += 1
            try:
                with requests.get(url, timeout=self.cfg['website_timeout_seconds'],
                        allow_redirects=False, stream=True,
                        headers={'User-Agent': 'YTLeadResearch/1.0 (public business contact research)'}) as response:
                    if response.is_redirect:
                        url = clean_url(response.headers.get('Location', ''), url)
                        continue
                    if not response.ok or 'text/html' not in response.headers.get('Content-Type', ''):
                        raise ValueError('Not an accessible HTML page')
                    body = bytearray()
                    for chunk in response.iter_content(16384):
                        body.extend(chunk)
                        if len(body) >= 500000:
                            break
                    decoded = body.decode(response.encoding or 'utf-8', errors='replace')
                    if re.search(r'verify you are human|complete the captcha|checkpoint/|log in to continue', decoded, re.I):
                        raise ValueError('Page requires human access')
                    page = Page()
                    page.feed(decoded)
                    self.enrich_page(page, decoded)
                    if (self.cfg.get('browser_enabled', False) and '<script' in decoded.lower()
                            and not page.mail and not EMAIL.search(' '.join(page.text))):
                        self.render_fallback(url, page)
                    return url, page
            except (requests.RequestException, ValueError) as exc:
                # Many sites answer a plain script with 403 yet serve a normal browser. Retry once in the
                # bounded real-browser renderer (it still refuses CAPTCHA / login / challenge pages).
                if self.cfg.get('browser_enabled', False) and 'human access' not in str(exc):
                    fallback = Page()
                    self.render_fallback(url, fallback)
                    if fallback.text or fallback.links or fallback.mail:
                        return url, fallback
                break
        with self.lock:
            self.metrics['website_failures'] += 1
        return url, None

    def render_fallback(self, url, original, wait=False):
        from .browser import EXCLUDED
        if is_domain(url, EXCLUDED):
            return
        # Do not queue another browser when the bounded renderer is already busy.
        if not self.browser_slots.acquire(blocking=wait):
            with self.lock:
                self.metrics['browser_deferred'] += 1
            return
        try:
            with self.lock:
                if self.metrics['browser_pages'] >= self.cfg.get('browser_max_pages_per_run', 20):
                    return
                self.metrics['browser_pages'] += 1
            try:
                outcome = run_browser_task('public_page', {'url':url, 'cfg':self.cfg}, self.cfg.get('browser_hard_timeout_seconds',30))
                if outcome['status'] != 'ok':
                    print('Public browser task: ' + outcome['status'] + ' - ' + str(outcome.get('reason', ''))[:150] + '; continuing', flush=True)
                    raise ValueError('Browser task failed')
                final_url, document, requests = outcome['url'], outcome['html'], outcome['requests']
                # Keep provenance correct: do not merge redirected content under the old URL.
                if host(final_url) != host(url) or (not is_domain(url, {'facebook.com'})
                        and clean_url(final_url).rstrip('/') != clean_url(url).rstrip('/')):
                    raise ValueError('Rendered page navigated away from original source')
                rendered = Page()
                rendered.feed(document)
                self.enrich_page(rendered, document)
                for field in ('text', 'links', 'mail', 'phones', 'structured'):
                    getattr(original, field).extend(getattr(rendered, field))
                with self.lock:
                    self.metrics['browser_requests'] += requests
                    self.metrics['browser_successes'] += 1
            except Exception:
                with self.lock:
                    self.metrics['browser_failures'] += 1
        finally:
            self.browser_slots.release()

    def enrich_page(self, page, document):
        if self.cfg.get('html_extractor', 'scrapling') != 'scrapling':
            return
        try:
            from .extractors.scrapling_html import extract
            extra = extract(document)
        except Exception:
            # Preserve the original parser's contacts if a page breaks the optional enrichment.
            with self.lock:
                self.metrics['scrapling_failures'] += 1
            return
        page.links = list(dict.fromkeys(page.links + extra['links']))
        for value in extra['emails']:
            page.mail.extend(EMAIL.findall(unquote(value)))
        page.phones.extend(value.removeprefix('tel:') for value in extra['phones'])
        page.structured.extend(extra['people'])
        with self.lock:
            self.metrics['scrapling_pages'] += 1

    def channel_panel(self, channel_id):
        if not self.cfg.get('youtube_panel_enabled', False):
            return {}
        with self.lock:
            if self.metrics['youtube_panel_pages'] >= self.cfg.get('youtube_panel_max_per_run',20):
                return {'status':'budget','reason':'Panel browser budget reached'}
            self.metrics['youtube_panel_pages'] += 1
        try:
            outcome = run_browser_task('youtube_panel', {'channel_id':channel_id, 'cfg':{}},
                self.cfg.get('browser_hard_timeout_seconds',30))
        except Exception as exc:
            outcome = {'status':'error','reason':type(exc).__name__}
        status = outcome.get('status','error')
        with self.lock:
            self.metrics['youtube_panel_' + status] += 1
        print(f'YouTube About {channel_id}: {status} - {outcome.get("reason", "")}; continuing', flush=True)
        return outcome

    def collect(self, channel, videos):
        cfg = self.cfg
        result = dict(contacts={}, links={}, phones=[], failure=False, team_pages=[], people=[], related=[])
        panel = self.channel_panel(channel['id'])
        result['research_notes'] = 'YouTube About: ' + panel.get('status','disabled') + '. ' + panel.get('reason','')
        description = channel['snippet'].get('description', '')
        channel_url = 'https://www.youtube.com/channel/' + channel['id']
        blobs = [(description, channel_url)] + [(v['description'], 'https://www.youtube.com/watch?v=' + v['id'])
                                                   for v in videos[:20]]
        for text, source in blobs:
            for match in EMAIL.finditer(html.unescape(text)):
                context = text[max(0, match.start()-120):match.end()+120]
                supported = bool(CONTACT.search(context)) and not SPONSOR.search(context)
                self.add(result, match.group(), source, supported,
                         'Published in channel or video description; ' +
                         ('explicit contact context' if supported else 'ownership or contact purpose requires review'))
        for text, source in blobs[:1]:
            result['phones'] += PHONE.findall(text)
            # "IG: @handle" written as text in the channel description, not as a link
            for handle in re.findall(r'\b(?:ig|insta|instagram)\s*[:\-–]?\s*@([A-Za-z0-9_.]{2,30})', text, re.I):
                record_link(result, 'https://www.instagram.com/' + handle.rstrip('.'), source)
        # Other YouTube channels the creator links from their own channel description belong to the same person.
        for text, _ in blobs[:1]:
            result['related'] += [m.group(1) for m in YT_CHANNEL.finditer(text)]
        # Links in the channel description are starting evidence, not proof that all belong to the creator.
        urls = list(dict.fromkeys(clean_url(u) for text, _ in blobs for u in URL.findall(text)))
        urls = [u for u in urls if u]
        for email in panel.get('emails', []):
            self.add(result, email, channel_url + '/about', True, 'Visible email published in channel About panel')
        trusted_panel = set()
        for link in panel.get('links', []):
            if clean_url(link):
                urls.append(clean_url(link))
                record_link(result, link, channel_url + '/about')
                # Any ordinary website linked in the creator's own About panel is theirs (first one fills Website).
                if (not is_domain(link, SKIP | set(SOCIALS) | REFERENCE_DOMAINS) and not NOT_WEBSITE.search(link)
                        and not SPONSOR.search(link)):
                    trusted_panel.add(host(link))
                    result['links'].setdefault('Website', clean_url(link))
        for text, source in blobs:
            for match in URL.finditer(text):
                context = text[max(0,match.start()-100):match.end()+50]
                if not SPONSOR.search(context) and (source == channel_url or re.search(r'follow me|follow us|my (?:social|instagram|facebook|linkedin)|our (?:social|instagram|facebook|linkedin)', context, re.I)):
                    record_link(result, match.group(), source)
        for entry in cfg.get('channel_links', {}).get(channel['id'], []):
            if entry.get('url') and entry.get('source'):
                record_link(result, entry['url'], entry['source'])
                if clean_url(entry['url']):
                    urls.append(clean_url(entry['url']))
        trusted_domains = set(cfg.get('verified_creator_domains', {}).get(channel['id'], [])) | trusted_panel
        for text, _ in blobs:
            for match in URL.finditer(text):
                context = text[max(0,match.start()-100):match.end()+50]
                if re.search(r'\b(?:my|our) (?:official )?(?:website|site|company|business)\b',context,re.I) and not SPONSOR.search(context):
                    trusted_domains.add(host(match.group().rstrip('.,;')))
        title = channel['snippet'].get('title', '')
        for u in urls:  # a site named like the channel (theabsolutesound.com / The Absolute Sound) is the creator's own
            h = host(u)
            if h and not is_domain(u, SKIP | set(SOCIALS) | BIO | REFERENCE_DOMAINS) and domain_matches_name(h, title):
                trusted_domains.add(h)
        urls.sort(key=lambda u: host(u) not in trusted_domains)
        sites = [u for u in urls if not is_domain(u, SKIP | set(SOCIALS))
                 and (host(u) in trusted_domains or not is_domain(u, REFERENCE_DOMAINS))]
        sites = sites[:2]
        pages = []
        # Public Facebook HTML only; no cookies, login or challenge solving.
        facebook = result['links'].get('Facebook', '').splitlines()
        for site in sites:
            if host(site) in BIO:
                pages.append(site)
            else:
                if host(site) in trusted_domains:
                    result['links'].setdefault('Website', site)
                root = urlsplit(site)._replace(path='', query='', fragment='').geturl()
                pages += [site] + [root + p for p in cfg['contact_pages']]
        grouped = {}
        for page_url in dict.fromkeys(pages):
            grouped.setdefault(host(page_url), []).append(page_url)
        pages = [group[index] for index in range(max(map(len,grouped.values()),default=0))
                 for group in grouped.values() if index < len(group)]
        if cfg.get('collect_public_facebook', True):
            pages = facebook[:1] + pages
        pages = pages[:cfg['website_max_pages_per_channel']]
        deadline = time.monotonic() + cfg['website_max_seconds_per_channel']
        visited, blocked = set(), set()
        with ThreadPoolExecutor(max_workers=cfg['website_workers']) as pool:
            while pages and time.monotonic() < deadline and len(visited) < cfg['website_max_pages_per_channel']:
                batch, pages = pages[:cfg['website_workers']], pages[cfg['website_workers']:]
                batch = [u for u in batch if u not in visited]
                visited.update(batch)
                for original, (source, page) in zip(batch, pool.map(self.fetch, batch)):
                    if host(original) in trusted_domains:  # a creator's short link (tkopod.co/..) lands on another host
                        trusted_domains.add(host(source))
                    if page is None:
                        result['failure'] = True
                        # an exhausted page budget is not the site's fault; only real failures are reported
                        if (not is_domain(source, {'facebook.com'})
                                and self.metrics['website_requests'] < cfg['website_max_pages_per_run']):
                            blocked.add(host(source))
                        continue
                    text = ' '.join(page.text)
                    for data in page.structured:
                        if host(source) in trusted_domains:
                            result['people'].extend(people_from_structured(data,source))
                    # A page reached via a channel link supports publication, not personal inbox ownership.
                    if host(source) in trusted_domains or is_domain(source, {'facebook.com'}):
                        result['related'] += [m.group(1) for l in page.links for m in YT_CHANNEL.finditer(clean_url(l, source))]
                    if host(source) in trusted_domains:
                        result['people'].extend(people_from_text(page.text, source))
                        result['phones'] += PHONE.findall(text)
                    for email in set(page.mail + EMAIL.findall(text)):
                        if not email_allowed(email, host(source), trusted_domains):
                            continue
                        context = next((text[max(0,m.start()-100):m.end()+100]
                                        for m in EMAIL.finditer(text) if m.group().lower() == email.lower()), '')
                        supported = ((host(source) in trusted_domains and (email in page.mail or bool(CONTACT.search(context))))
                                     or is_domain(source, {'facebook.com'})) and not SPONSOR.search(context)
                        self.add(result, email, source, supported,
                            'Published on a page reached from the channel description; '
                            'publication does not establish a named inbox owner')
                    if host(source) in trusted_domains:
                        result['phones'] += page.phones
                    for link in page.links:
                        absolute = clean_url(link, source)
                        if not absolute:
                            continue
                        if host(source) in trusted_domains and canonical_profile(absolute):
                            record_link(result, absolute, source)
                        if (cfg.get('collect_public_facebook', True) and host(source) in trusted_domains
                                and is_domain(absolute, {'facebook.com'}) and absolute not in visited):
                            pages.insert(0, absolute)
                        for domain, column in SOCIALS.items():
                            if host(source) in trusted_domains and host(absolute) == domain:
                                record_link(result, absolute, source)
                        if host(absolute) == host(source) and re.search(r'/(team|our-team|about|contact)(/|$)', urlsplit(absolute).path):
                            if absolute not in visited:
                                pages.insert(0, absolute)
                            if 'team' in absolute:
                                result['team_pages'].append(absolute)
                        if host(source) in BIO and host(absolute) not in SKIP | set(SOCIALS) | BIO:
                            if absolute.startswith('https://') and absolute not in visited:
                                pages.insert(0, absolute)
                    pages = list(dict.fromkeys(pages))[:max(0, cfg['website_max_pages_per_channel'] - len(visited))]
        if blocked:  # tell the user which sites the automation could not read, instead of leaving silent blanks
            result['research_notes'] += ' Could not read (blocked or unavailable to automation, check by hand): ' + ', '.join(sorted(blocked)) + '.'
        result['phones'] = list(dict.fromkeys(normalize_phone(v) for v in result['phones'] if v.strip()))
        result['related'] = list(dict.fromkeys(result['related']))[:5]
        # Guess domain: the creator's own site only (stated as 'my website', or its name matches the channel).
        result['guess_domain'] = next((d for d in list(trusted_domains) + [host(u) for u in sites]
                                       if d and (d in trusted_domains or domain_matches_name(d, title))), '')
        return result

    @staticmethod
    def add(result, email, source, supported, note):
        email = email.lower().strip().rstrip('.')
        if any(x in email for x in ('example.com', 'sentry.io', 'noreply@', 'no-reply@')):
            return
        previous = result['contacts'].get(email)
        if not previous or (supported and not previous['supported']):
            result['contacts'][email] = dict(email=email, source=source, supported=bool(supported), evidence=note)
