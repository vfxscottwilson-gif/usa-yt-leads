"""Evidence-backed owner name and email typing. Nothing here guesses.

Owner name: accepted only from the creator's own pages (website, link-in-bio, channel/video descriptions) or when the
same name appears on two independent public sources. Every name keeps its source URL and the exact evidence snippet.
Email: every found address is typed Personal / Own Domain / Generic / Other Domain and sorted best-first.
YouTube 'View email address' needs a CAPTCHA: it is never clicked here, only its presence is recorded.
Optional hooks (SEARCH_API_KEY, HUNTER_API_KEY) are OFF unless enabled in settings AND the key is in the environment.
"""
import os
import re
from urllib.parse import urlsplit, quote
from .names import FIRST, BRAND, TITLES, ROLE_LOCALS, FREE_MAIL, domain_matches_name

PERSONAL_DOMAINS = set(FREE_MAIL) | {'googlemail.com', 'live.com', 'msn.com', 'ymail.com', 'me.com', 'mac.com',
    'pm.me', 'proton.com', 'gmx.com', 'gmx.net', 'mail.com', 'yahoo.co.uk', 'yahoo.ca', 'yahoo.com.au', 'hotmail.co.uk',
    'outlook.co.uk', 'fastmail.com', 'hey.com', 'zoho.com', 'yandex.com', 'mail.ru'}
GENERIC_LOCALS = set(ROLE_LOCALS) | {'contact', 'hello', 'sales', 'press', 'business', 'team', 'admin', 'info', 'support',
    'enquiry', 'inquiry', 'mail', 'email', 'general', 'service', 'services', 'marketing', 'pr', 'collab', 'collabs',
    'collaborations', 'sponsor', 'sponsors', 'sponsorship', 'sponsorships', 'ads', 'creators', 'management', 'booking',
    'businessinquiries', 'businessinquiry', 'businessenquiries', 'contactus', 'webmaster', 'feedback', 'hi', 'hey'}
EMAIL_RANK = {'Personal': 0, 'Own Domain': 1, 'Other Domain': 2, 'Generic': 3}

# ---------------------------------------------------------------- emails


def is_generic_local(local):
    local = local.lower()
    if local in GENERIC_LOCALS:
        return True
    return bool(re.split(r'[._\-+]', local)[0] in GENERIC_LOCALS and re.search(r'[._\-+]', local))


def classify_email(email, own_domains=(), channel_title=''):
    """'Personal', 'Own Domain', 'Generic' or 'Other Domain' (a named mailbox on a domain that is not the creator's)."""
    email = (email or '').lower().strip()
    if '@' not in email:
        return ''
    local, domain = email.rsplit('@', 1)
    if is_generic_local(local):
        return 'Generic'
    if domain in PERSONAL_DOMAINS:
        return 'Personal'
    own = {d.lower().removeprefix('www.') for d in own_domains if d}
    if any(domain == d or domain.endswith('.' + d) for d in own) or (
            not own and channel_title and domain_matches_name(domain, channel_title)):
        return 'Own Domain'
    return 'Other Domain'


def sort_contacts(contacts, own_domains=(), channel_title=''):
    """Stable sort: Personal, Own Domain, Other Domain, Generic; published-and-supported first inside each type."""
    def key(contact):
        kind = classify_email(contact.get('email', ''), own_domains, channel_title)
        return (EMAIL_RANK.get(kind, 4), 0 if contact.get('supported') else 1)
    return sorted(contacts, key=key)


# ---------------------------------------------------------------- owner name

NAME = r"[A-Z][a-z'’\-]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-]+)?"
ROLE = r"(?:co-?founder|founder|owner|creator|ceo|host|president)"
# (rank, needs_known_first_name, regex, role_group_or_None). Lower rank = stronger evidence.
PATTERNS = [
    (2, False, re.compile(r"(?i:\b(?:founder|co-?founder|owner|ceo|president)(?:\s*(?:&|and)\s*\w+)?\s*[:\-–—|])\s*(" + NAME + ")"), 'Founder'),
    (2, False, re.compile(r"(?i:\b(?:founded|owned|created|run|started)\s+by)\s+(" + NAME + ")"), 'Founder'),
    (3, False, re.compile(r"(?i:\bmy name(?:['’]s| is))\s+(" + NAME + ")"), ''),
    (3, False, re.compile(r"(?i:\bI['’]?m|\bI am)\s+(" + NAME + r")\s*[,–—\-]?\s*(?i:(?:the|a|an|and|your|its|this)\s+)*(?i:" + ROLE + ")"), 'Founder'),
    (4, True, re.compile(r"(?i:\b(?:hi|hello|hey)\b)[,!.]?\s+(?:(?i:there)[,!.]?\s+)?(?i:I['’]?m|I am)\s+(" + NAME + ")"), ''),
    (4, True, re.compile(r"(?:^|[.!?]\s+)(?i:I['’]?m|I am)\s+(" + NAME + ")"), ''),
]
FOUNDER_JOB = re.compile(r'founder|owner|\bceo\b|chief executive|president|creator', re.I)
# A page block that looks like a customer quote, review, comment or guest: a name there is NOT the site owner.
TESTIMONIAL = re.compile(r"testimonial|what (?:our |my )?(?:clients|customers|people|students|members|viewers|users|fans) "
    r"(?:are )?(?:say|saying)|(?:client|customer|student|member|viewer|user|patient) (?:review|stories|story|feedback|reviews)|"
    r"success stor|\bcomments?\b|\bwrote\b:?|\bsays\b:|\bsaid\b:|reviewed by|verified (?:buyer|purchase)|guest|interview with|"
    r"\bwith special\b|featuring", re.I)
NOT_NAME = {'the', 'this', 'that', 'back', 'here', 'there', 'excited', 'happy', 'new', 'welcome', 'just', 'very', 'not',
    'now', 'also', 'so', 'sorry', 'proud', 'thrilled', 'glad', 'looking', 'going', 'ready', 'sure', 'still', 'always',
    'team', 'channel', 'media', 'studio', 'studios', 'productions', 'official', 'inc', 'llc', 'ltd', 'company', 'group',
    'support', 'contact', 'about', 'home', 'hello', 'founder', 'owner', 'ceo', 'president', 'creator', 'host', 'youtube',
    'google', 'facebook', 'instagram', 'twitter', 'linkedin', 'tiktok', 'amazon', 'subscribe', 'follow', 'join', 'read',
    'learn', 'click', 'view', 'see', 'get', 'free', 'best', 'top', 'my', 'our', 'your', 'you', 'we', 'it', 'an', 'in',
    'of', 'at', 'on', 'for', 'and', 'with', 'from', 'to', 'by', 'tutorials', 'tutorial', 'tech', 'reviews', 'review',
    'privacy', 'policy', 'terms', 'services', 'service', 'solutions', 'consulting', 'marketing', 'agency'}


def valid_name(name):
    """2-3 alphabetic words, none a brand/stop/role word."""
    tokens = [t for t in re.split(r'\s+', (name or '').strip()) if t]
    if not 2 <= len(tokens) <= 3:
        return False
    for t in tokens:
        bare = t.rstrip('.').lower()
        if len(bare) == 1 and t.endswith('.'):
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z'’\-]+", t) or bare in NOT_NAME or bare in BRAND or bare in TITLES:
            return False
    return True


def name_key(name):
    tokens = [t.rstrip('.').lower() for t in name.split() if len(t.rstrip('.')) > 1]
    return ' '.join(tokens[:1] + tokens[-1:]) if len(tokens) >= 2 else ' '.join(tokens)


def family(url):
    """Registered-ish domain, so two pages of one site (or two youtube.com pages) count as ONE source."""
    host = (urlsplit(url).hostname or '').lower().removeprefix('www.')
    parts = host.split('.')
    if len(parts) >= 3 and parts[-2] in ('co', 'com', 'org', 'net', 'ac') and len(parts[-1]) == 2:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def _snippet(text, match, width=110):
    return ' '.join(text[max(0, match.start() - width):match.end() + width].split())[:260]


def _candidate(name, rank, source, evidence, kind, role=''):
    return dict(name=' '.join(name.split()), rank=rank, source=source, evidence=evidence, kind=kind, role=role)


def names_from_text(chunks, source, kind):
    """First-person / labelled owner statements in text chunks. A chunk near testimonial-style text is ignored."""
    found = []
    clean = [' '.join(str(c).split()) for c in chunks]
    for i, chunk in enumerate(clean):
        if not chunk or len(chunk) > 600:
            continue
        near = ' '.join(clean[max(0, i - 3):i + 4])
        for rank, needs_first, regex, role in PATTERNS:
            for match in regex.finditer(chunk):
                name = match.group(1)
                if not valid_name(name):
                    # trim a trailing stop/brand word: "Frank Joseph Welcome" -> "Frank Joseph"
                    tokens = name.split()
                    while len(tokens) > 2 and not valid_name(' '.join(tokens)):
                        tokens.pop()
                    name = ' '.join(tokens)
                    if not valid_name(name):
                        continue
                if needs_first and name.split()[0].lower() not in FIRST:
                    continue
                before = chunk[:match.start(1)]
                if re.search(r'[“"‘]\s*[^”"’]*$', before) or TESTIMONIAL.search(near):
                    continue  # inside a quotation, or surrounded by testimonial / comment / guest wording
                if any(f['name'] == name and f['evidence'] == _snippet(chunk, match) and f['rank'] <= rank for f in found):
                    continue   # a stronger pattern already matched this same sentence
                found = [f for f in found if not (f['name'] == name and f['evidence'] == _snippet(chunk, match))]
                found.append(_candidate(name, rank, source, _snippet(chunk, match), kind, role))
    return found


def names_from_structured(data, source, kind, _parent=''):
    """JSON-LD: Organization founder/owner, Person with a founder-type jobTitle, mainEntity Person of an About/Profile page."""
    found = []
    if isinstance(data, list):
        for value in data:
            found.extend(names_from_structured(value, source, kind, _parent))
    elif isinstance(data, dict):
        kinds = data.get('@type', '')
        kinds = kinds if isinstance(kinds, list) else [kinds]
        def person_names(value):
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, dict) and item.get('name') and (not item.get('@type') or 'Person' in str(item.get('@type'))):
                    yield str(item['name']), item.get('jobTitle', '')
                elif isinstance(item, str):
                    yield item, ''
        if any(k in ('Organization', 'LocalBusiness', 'Corporation', 'WebSite', 'Brand') for k in kinds):
            for field in ('founder', 'founders', 'owner'):
                for name, job in person_names(data.get(field, [])):
                    if valid_name(name):
                        found.append(_candidate(name, 1, source, f'JSON-LD {kinds[0]} {field}: {name}', kind,
                                                'Founder' if field != 'owner' else 'Owner'))
        if 'Person' in kinds and data.get('name') and valid_name(str(data['name'])):
            job = data.get('jobTitle', '')
            job = ', '.join(map(str, job)) if isinstance(job, list) else str(job)
            if FOUNDER_JOB.search(job):
                found.append(_candidate(str(data['name']), 1, source, f'JSON-LD Person {data["name"]}, {job}', kind, job))
            elif _parent in ('AboutPage', 'ProfilePage'):
                found.append(_candidate(str(data['name']), 2, source, f'JSON-LD Person {data["name"]} (main entity of {_parent})', kind, ''))
        parent = next((k for k in kinds if k in ('AboutPage', 'ProfilePage')), '')
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                found.extend(names_from_structured(value, source, kind, parent if key == 'mainEntity' else ''))
    return found


def names_from_meta(authors, source, kind):
    found = []
    for author in authors:
        author = ' '.join(str(author).split())
        if valid_name(author) and author.split()[0].lower() in FIRST:
            found.append(_candidate(author, 5, source, f'<meta name="author" content="{author}">', kind, ''))
    return found


def page_kind(source, trusted_domains, bio_domains):
    host = (urlsplit(source).hostname or '').lower().removeprefix('www.')
    if host in trusted_domains:
        return 'own_site'
    if host in bio_domains:
        return 'bio_page'
    if host.endswith('facebook.com'):
        return 'social_bio'
    return ''


def candidates_from_page(page, source, kind):
    """Owner-name candidates from one fetched page (kind from page_kind; '' = ignore the page)."""
    if not kind:
        return []
    found = names_from_text(page.text, source, kind)
    if kind in ('own_site', 'bio_page'):
        for data in page.structured:
            found.extend(names_from_structured(data, source, kind))
        found.extend(names_from_meta(getattr(page, 'meta', []), source, kind))
    return found


def candidates_from_descriptions(blobs):
    """blobs = [(text, source_url)]: the channel description first, then recent video descriptions (all written by the creator)."""
    found = []
    for text, source in blobs:
        found.extend(names_from_text(str(text).splitlines(), source, 'description'))
    return found


OWN_KINDS = {'own_site', 'bio_page', 'description', 'panel'}


def pick_owner(candidates):
    """One owner or None. Own page => accepted; otherwise the same name must come from two independent source families."""
    groups = {}
    for c in candidates:
        if valid_name(c['name']):
            groups.setdefault(name_key(c['name']), []).append(c)
    best = None
    for key, items in groups.items():
        families = {family(c['source']) for c in items}
        own = [c for c in items if c['kind'] in OWN_KINDS]
        if not own and len(families) < 2:
            continue
        lead = min(own or items, key=lambda c: (c['rank'], -len(c['name'])))
        score = (0 if own else 1, lead['rank'], -len(families))
        if best is None or score < best[0]:
            best = (score, lead, len(families))
    if not best:
        return None
    lead = best[1]
    note = lead['evidence'] + ('' if lead['kind'] in OWN_KINDS else f' (same name on {best[2]} independent sources)')
    return dict(full_name=lead['name'], first_name=lead['name'].split()[0], source=lead['source'], evidence=note,
                designation=lead.get('role', ''))


def owner_from_people(people):
    """Existing team-page / JSON-LD people from the creator's own site, only when the listed title says founder/owner."""
    for p in people or []:
        if p.get('source') and p.get('full_name') and FOUNDER_JOB.search(p.get('designation', '')) and valid_name(p['full_name']):
            return dict(full_name=p['full_name'], first_name=p.get('first_name') or p['full_name'].split()[0],
                        source=p['source'], evidence=f"{p['full_name']}, {p.get('designation', '')} (listed on the creator's own site)",
                        designation=p.get('designation', ''))
    return None


# ---------------------------------------------------------------- YouTube business email button (never clicked)

def button_state(panel):
    """'Button Present' / 'No Button' / 'Not Checked' from the About panel result. Detection only, never a click."""
    state = (panel or {}).get('email_button', '')
    return state if state in ('Button Present', 'No Button') else 'Not Checked'


def manual_check(state, contacts, own_domains=(), channel_title=''):
    """Flag leads a human should open once: a protected YouTube email exists and no personal email is known."""
    has_personal = any(classify_email(c.get('email', ''), own_domains, channel_title) == 'Personal' for c in contacts)
    return 'Yes' if state == 'Button Present' and not has_personal else ''


# ---------------------------------------------------------------- optional hooks (off by default, keys from env only)

def search_enabled(cfg):
    return bool(cfg.get('search_api_enabled')) and bool(os.environ.get('SEARCH_API_KEY'))


def hunter_enabled(cfg):
    return bool(cfg.get('hunter_enabled')) and bool(os.environ.get('HUNTER_API_KEY'))


def search_urls(channel_title, cfg, requests_module=None):
    """Result URLs from an OFFICIAL search API (Brave Search API). Google result pages are never scraped."""
    if not search_enabled(cfg):
        return []
    requests = requests_module
    if requests is None:
        import requests
    try:
        response = requests.get('https://api.search.brave.com/res/v1/web/search',
            params={'q': f'{channel_title} owner name email', 'count': int(cfg.get('search_api_results', 5))},
            headers={'X-Subscription-Token': os.environ['SEARCH_API_KEY'], 'Accept': 'application/json'}, timeout=10)
        if not response.ok:
            return []
        return [r['url'] for r in response.json().get('web', {}).get('results', []) if r.get('url')][:int(cfg.get('search_api_results', 5))]
    except Exception:
        return []


def hunter_lookup(domain, full_name, cfg, requests_module=None):
    """One email for a proven owner name on the creator's own domain, or None. Unverified results are marked as such."""
    if not hunter_enabled(cfg) or not domain or not valid_name(full_name):
        return None
    requests = requests_module
    if requests is None:
        import requests
    tokens = full_name.split()
    try:
        response = requests.get('https://api.hunter.io/v2/email-finder',
            params={'domain': domain, 'first_name': tokens[0], 'last_name': tokens[-1]},
            headers={'X-API-KEY': os.environ['HUNTER_API_KEY']}, timeout=10)
        if not response.ok:
            return None
        data = response.json().get('data') or {}
        email = data.get('email')
        if not email or not email.lower().endswith('@' + domain.lower()):
            return None
        verified = (data.get('verification') or {}).get('status') == 'valid'
        return dict(email=email.lower(), verified=verified, score=data.get('score'))
    except Exception:
        return None


def finalize(research, result, channel, panel, trusted_domains, sites):
    """Called once at the end of Research.collect: owner, own domains, YouTube button state, optional hooks."""
    cfg = research.cfg
    title = channel['snippet'].get('title', '')
    own = {d for d in trusted_domains if d}
    own |= {(urlsplit(u).hostname or '').lower().removeprefix('www.') for u in sites
            if domain_matches_name((urlsplit(u).hostname or '').removeprefix('www.'), title)}
    website = result.get('links', {}).get('Website', '')
    if website:
        own.add((urlsplit(website).hostname or '').lower().removeprefix('www.'))
    result['own_domains'] = sorted(own)
    result['youtube_business_email'] = button_state(panel)
    candidates = list(result.get('owner_candidates', []))
    if search_enabled(cfg):
        for url in search_urls(title, cfg)[:int(cfg.get('search_api_results', 5))]:
            fetched, page = research.fetch(url)
            if page is not None:
                kind = 'own_site' if family(fetched) in {family('https://' + d) for d in own} else 'third_party'
                candidates += names_from_text(page.text, fetched, kind)
    result['owner'] = pick_owner(candidates)
    if result['owner'] is None:
        result['owner'] = owner_from_people(result.get('people'))
    if result['owner'] and own and hunter_enabled(cfg):
        domain = sorted(own)[0]
        found = hunter_lookup(domain, result['owner']['full_name'], cfg)
        if found:
            research.add(result, found['email'], 'https://api.hunter.io/v2/email-finder?domain=' + quote(domain),
                         found['verified'], 'Hunter email finder for proven owner name '
                         + ('(verified)' if found['verified'] else '(not verified)'))
    return result
