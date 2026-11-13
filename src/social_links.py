"""Canonical public profile URLs only, never platform navigation links."""
from urllib.parse import urlsplit, parse_qs, urlencode
import re


def canonical_profile(url):
    try:
        if any(c in url for c in '[]<>\\'):
            return ''
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            return ''
        host = parts.hostname.lower().removeprefix('www.').removeprefix('m.')
        path = [v for v in parts.path.split('/') if v]
        if not path:
            return ''
        first = path[0].lower()
        if host == 'facebook.com':
            banned = {'login','recover','reg','privacy','watch','lite','about','help','policies','ad_campaign',
                'careers','share','sharer.php','dialog','plugins','groups','events','photo','photos','reel','reels',
                'story.php','permalink.php','checkpoint','settings','marketplace','gaming','notifications'}
            if first in banned:
                return ''
            if first == 'profile.php':
                ident = parse_qs(parts.query).get('id', [''])[0]
                return 'https://www.facebook.com/profile.php?' + urlencode({'id':ident}) if ident.isdigit() else ''
            if first == 'pages':
                if len(path) == 3 and path[-1].isdigit():
                    return 'https://www.facebook.com/' + path[-1]
                return ''
            if len(path) > 1 or not re.fullmatch(r'[A-Za-z0-9._-]+', path[0]):
                return ''
            return 'https://www.facebook.com/' + path[0]
        if host == 'instagram.com':
            if len(path) != 1 or first in {'p','reel','reels','stories','explore','accounts','direct','about','legal'}:
                return ''
            return 'https://www.instagram.com/' + path[0] if re.fullmatch(r'[A-Za-z0-9._]+',path[0]) else ''
        if host == 'linkedin.com':
            if len(path) == 2 and first in {'in','company','school'}:
                return 'https://www.linkedin.com/' + '/'.join(path)
            return ''
        if host in {'twitter.com','x.com'}:
            if len(path) != 1 or first in {'home','search','intent','share','i','login','signup','settings','explore'}:
                return ''
            return 'https://x.com/' + path[0] if re.fullmatch(r'[A-Za-z0-9_]+',path[0]) else ''
    except (ValueError, TypeError):
        pass
    return ''
