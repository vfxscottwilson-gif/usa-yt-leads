import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]

def time_zone(name):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == 'Asia/Karachi':
            return timezone(timedelta(hours=5),name='PKT')
        raise ValueError('Install tzdata for the configured timezone') from None

def load():
    # This loader has no third party dependency and never prints secrets.
    path = ROOT / '.env'
    if path.exists() and os.environ.get("GITHUB_ACTIONS") != "true":
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('\"').strip("'"))
    cfg = json.loads((ROOT / 'config/settings.json').read_text(encoding='utf-8'))
    niches = json.loads((ROOT / 'config/niches.json').read_text(encoding='utf-8'))
    cfg.setdefault('countries', ['US'])
    cfg.setdefault('banned_countries', ['IN', 'PK', 'BD'])
    # YouTube calls the United Kingdom GB. Accept UK as a friendly alias so a typo cannot silently break the search.
    cfg['countries'] = ['GB' if str(c).strip().upper() == 'UK' else str(c).strip().upper() for c in cfg['countries']]
    if not cfg['countries'] or not all(isinstance(c, str) and len(c) == 2 and c.isupper() for c in cfg['countries']):
        raise ValueError('countries must be a list of 2-letter codes such as ["US", "AU", "NZ"]')
    if not 0 < cfg['min_subscribers'] <= cfg['max_subscribers']:
        raise ValueError('Subscriber limits are invalid')
    for key in ['activity_days', 'min_long_uploads', 'video_sample_size', 'min_video_views',
                'min_videos_above_threshold', 'max_upload_pages', 'max_searches',
                'max_channels_per_run', 'checkpoint_channels', 'website_workers',
                'max_formula_rows']:
        if not isinstance(cfg[key], int) or cfg[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if cfg['min_videos_above_threshold'] > cfg['video_sample_size']:
        raise ValueError('Video threshold exceeds sample size')
    if cfg['max_searches'] > 100:
        raise ValueError('max_searches must not exceed the documented default of 100')
    for key in ['pagination_search_fraction', 'recheck_fraction']:
        if not 0 <= cfg[key] <= 1:
            raise ValueError(f'{key} must be between 0 and 1')
    if not cfg['recheck_delays_days'] or min(cfg['recheck_delays_days']) < 1:
        raise ValueError('Recheck delays must be positive')
    if cfg.get('html_extractor', 'scrapling') not in ('scrapling', 'builtin'):
        raise ValueError('html_extractor must be scrapling or builtin')
    for key in ('browser_workers', 'browser_max_pages_per_run', 'browser_max_requests_per_page', 'browser_timeout_seconds', 'browser_hard_timeout_seconds', 'youtube_panel_max_per_run'):
        if not isinstance(cfg.get(key, 1), int) or cfg.get(key, 1) < 1:
            raise ValueError(key + ' must be a positive integer')
    if not isinstance(cfg.get('browser_enabled', False), bool):
        raise ValueError('browser_enabled must be a boolean')
    if not 0 <= cfg.get('browser_wait_ms', 1000) <= 5000:
        raise ValueError('browser_wait_ms must be between 0 and 5000')
    time_zone(cfg['timezone'])
    names = [n['name'] for n in niches]
    reserved = {'Dashboard', 'Daily Report', 'All Leads', 'Needs Review', 'Settings',
                'Channel Memory', 'Search Memory'}
    if len(names) != len(set(names)) or any(n in reserved or len(n) > 90 or
            any(c in n for c in '-[]:*?/\\') for n in names):
        raise ValueError('Niche tab names must be unique, valid, and contain no dashes')
    if not niches or any(not n['queries'] or not n['signals'] for n in niches):
        raise ValueError('Every niche needs queries and signals')
    return cfg, niches
