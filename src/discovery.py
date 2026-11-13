import csv
import hashlib
from datetime import timedelta
from .config import ROOT
from .models import iso, parse, utcnow
from .youtube import BudgetStop, YouTubeError

def discover(api, cfg, niches, searches, channels, metrics, deadline):
    candidates = {}
    seed_path = ROOT / 'config/seeds.csv'
    with seed_path.open(encoding='utf-8-sig', newline='') as handle:
        for row in list(csv.DictReader(handle))[:cfg['max_seed_channels_per_run']]:
            cid = row.get('Channel ID', '').strip()
            if cid.startswith('UC') and len(cid) == 24:
                candidates[cid] = row.get('Niche', '')
    tasks = []
    for niche in niches:
        for query, country in [(q, c) for q in niche['queries'] for c in cfg['countries']]:
            for length in ('medium', 'long'):
                for order in ('relevance', 'date', 'viewCount'):
                    for lower, upper in ((0,7),(7,14),(14,21),(21,30)):
                        key = hashlib.sha256(f'{query}|{country}|{length}|{order}|{lower}|{upper}'.encode()).hexdigest()[:24]
                        old = searches.get(key, {})
                        tasks.append((old.get('checked', ''), key, niche['name'], query, length, order, lower, upper, country))
    # Stable oldest-first rotation; never deliberately discard expanded niches.
    tasks.sort()
    pagination_limit = int(cfg['max_searches'] * cfg['pagination_search_fraction'])
    for checked, key, niche, query, length, order, lower, upper, country in tasks:
        if utcnow() >= deadline:
            break
        if checked and utcnow() - parse(checked) < timedelta(days=cfg['query_cooldown_days']):
            continue
        params = dict(part='snippet', type='video', q=query, regionCode=country,
            relevanceLanguage=cfg.get('search_language', 'en'), videoDuration=length, maxResults=50,
            order=order,
            publishedAfter=(utcnow() - timedelta(days=upper)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            publishedBefore=(utcnow() - timedelta(days=lower)).strftime('%Y-%m-%dT%H:%M:%SZ'))
        try:
            data = api.get('search', **params)
        except BudgetStop:
            break
        except YouTubeError as exc:
            metrics['search_failures'] += 1
            if metrics['search_failures'] <= 3:
                print('YouTube search failed: ' + str(exc), flush=True)   # shows the real reason in the log
            if metrics['search_failures'] >= cfg.get('max_search_failures', 8):
                print('Too many failed searches; stopping search for this run to protect the 100 daily searches.', flush=True)
                break
            continue
        found = [x['snippet']['channelId'] for x in data.get('items', [])]
        metrics['results_received'] += len(found)
        fresh = set(found) - set(channels) - set(candidates)
        for cid in found:
            candidates.setdefault(cid, niche)
        searches[key] = dict(checked=iso(), query=query, niche=niche,
            unique_new=len(fresh), results=len(found), duration=length, order=order,
            lower_days=lower, upper_days=upper)
        # Only test depth when the first page actually exposes unseen channels.
        if pagination_limit and len(fresh) >= 10 and data.get('nextPageToken') and utcnow() < deadline:
            try:
                page = api.get('search', **params, pageToken=data['nextPageToken'])
            except BudgetStop:
                break
            except YouTubeError:
                metrics['search_failures'] += 1
                continue
            pagination_limit -= 1
            for item in page.get('items', []):
                candidates.setdefault(item['snippet']['channelId'], niche)
            metrics['results_received'] += len(page.get('items', []))
    metrics['unique_channels_found'] = len(candidates)
    return candidates
