"""Name and email-guess helpers. Names are inferred from the channel title only when a known first name is present."""
import re

FIRST = set('''aaron adam adrian alan albert alex alexander alexis alice alicia allen amanda amber amy andrea andrew andy angela anna anthony ashley austin barbara ben benjamin beth betty billy bob bobby brad bradley brandon brenda brian brittany bruce bryan caleb cameron carl carlos carol caroline catherine charles charlie chase chelsea cheryl chris christian christina christine christopher cindy claire clark cody colin connor corey courtney craig crystal dale dan daniel danielle danny darren dave david dawn dean debbie deborah dennis derek diana diane dominic don donald donna doug douglas drew dustin dylan earl ed eddie edward elaine elizabeth ellen emily emma eric erica erik erin ethan eugene evan frank fred gabriel gary gavin gene george gerald gina glenn gloria gordon grace grant greg gregory hannah harold harry heather heidi helen henry holly howard ian isaac jack jacob jake james jamie jane janet jason jay jeff jeffrey jennifer jenny jeremy jerry jesse jessica jill jim jimmy joan joe joel john johnny jon jonathan jordan joseph josh joshua joy juan judy julia julie justin karen kate katherine kathy katie keith kelly ken kenneth kevin kim kirk kris kristen kyle larry laura lauren lee leo leonard linda lindsay lisa logan lori louis lucas luke lynn marc marcus margaret maria marie mark martin mary mason matt matthew megan melissa michael michelle mike mitchell molly monica nancy nate nathan neil nicholas nick nicole noah norman olivia oscar pamela patricia patrick paul peter philip phil rachel ralph randy ray raymond rebecca richard rick ricky rob robert robin rod roger ron ronald rose roy russell ruth ryan sam samantha samuel sandra sara sarah scott sean seth shane sharon shawn sheila shirley simon stacy stephanie stephen steve steven stuart susan tammy tara ted terry theresa thomas tim timothy tina todd tom tommy tony tracy travis trevor tyler valerie vanessa victor victoria vincent walter wayne wendy wesley whitney william willie zach zachary dre jason jen jess jon rj tj aj cj'''.split())
TITLES = {'dr', 'doctor', 'mr', 'mrs', 'ms', 'prof', 'professor', 'coach', 'pastor', 'rev'}
BRAND = {'tv', 'show', 'news', 'media', 'studio', 'studios', 'official', 'channel', 'tips', 'health', 'travel', 'with',
    'the', 'of', 'and', 'by', 'club', 'academy', 'labs', 'lab', 'group', 'team', 'co', 'inc', 'llc', 'podcast', 'tech',
    'reviews', 'review', 'daily', 'live', 'network', 'productions', 'production', 'films', 'vlog', 'vlogs'}
ROLE_LOCALS = {'info', 'contact', 'hello', 'hi', 'support', 'sales', 'press', 'media', 'team', 'admin', 'office',
    'business', 'booking', 'bookings', 'partnerships', 'help', 'editorial', 'advertising', 'inquiries', 'enquiries'}
FREE_MAIL = {'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'aol.com', 'proton.me', 'protonmail.com'}
JUNK_EMAIL_DOMAINS = {'facebook.com', 'fb.com', 'instagram.com', 'github.com', 'google.com', 'youtube.com', 'sentry.io',
    'wixpress.com', 'twitter.com', 'x.com', 'tiktok.com', 'ncbi.nlm.nih.gov', 'nih.gov', 'doi.org', 'w3.org', 'schema.org'}
TITLE_WORDS = re.compile(r'\b(founder|co-?founder|ceo|chief [a-z ]+officer|owner|president|director|head of [a-z ]+|manager|'
                         r'producer|editor|partner|host|managing [a-z]+|vp|vice president|coo|cmo)\b', re.I)


def infer_person(channel_title):
    """Return (first_name, full_name) from a channel title, or ('', '') when no real first name is present."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", channel_title)]
    for i, word in enumerate(words):
        if word.lower() in TITLES or word.lower() in BRAND:
            continue
        if word.lower() in FIRST:
            first = word.capitalize()
            nxt = words[i + 1] if i + 1 < len(words) else ''
            if nxt and nxt[0].isupper() and nxt.lower() not in BRAND | TITLES and nxt.lower() not in FIRST and len(nxt) > 1:
                return first, f'{first} {nxt.capitalize() if nxt.isupper() else nxt}'
            return first, first
    return '', ''


def domain_matches_name(domain, title):
    """True when a site's name label resembles the channel title, e.g. daveasprey.com for 'Dave Asprey'."""
    label = domain.lower().removeprefix('www.').split('.')[0]
    collapsed = re.sub(r'[^a-z0-9]', '', title.lower())
    return len(label) >= 4 and (label in collapsed or collapsed in label)


def email_allowed(email, source_host, trusted_domains):
    """Reject emails that merely belong to the platform or reference site we crawled (policy@github.com)."""
    domain = email.lower().rsplit('@', 1)[-1]
    if any(domain == d or domain.endswith('.' + d) for d in JUNK_EMAIL_DOMAINS):
        return False
    if source_host in ('facebook.com', 'm.facebook.com') or domain in FREE_MAIL:
        return True
    return any(domain == d or domain.endswith('.' + d) for d in {source_host} | set(trusted_domains))


def guess_email(first_name, domain):
    """Single first-name pattern, e.g. dave@daveasprey.com. Always unverified."""
    return f'{first_name.lower()}@{domain}' if first_name and domain else ''


def people_from_text(chunks, source):
    """Name + title pairs from a team page. 'Name, Title' in one chunk or name chunk followed by title chunk."""
    found, seen = [], set()
    for i, chunk in enumerate(chunks):
        text = ' '.join(chunk.split())
        if not text or len(text) > 90:
            continue
        pair = re.match(r"^([A-Z][a-z'\-]+ (?:[A-Z]\.? )?[A-Z][a-zA-Z'\-]+)\s*[,\-–—|]\s*(.+)$", text)
        name, title = (pair.group(1), pair.group(2)) if pair else (None, None)
        if not name and i + 1 < len(chunks):
            following = ' '.join(chunks[i + 1].split())
            if re.fullmatch(r"[A-Z][a-z'\-]+ (?:[A-Z]\.? )?[A-Z][a-zA-Z'\-]+", text) and len(following) < 60:
                name, title = text, following
        if name and title and TITLE_WORDS.search(title) and name.split()[0].lower() in FIRST and name not in seen:
            seen.add(name)
            found.append(dict(full_name=name, first_name=name.split()[0], designation=title.strip(), source=source))
    return found
