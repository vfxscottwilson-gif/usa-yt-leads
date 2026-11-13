import time

class BudgetStop(Exception):
    pass

class YouTubeError(Exception):
    pass

class YouTube:
    def __init__(self, key, cfg, metrics, session=None):
        self.key, self.cfg, self.metrics = key, cfg, metrics
        if session is None:
            import requests
            session = requests.Session()
        self.session = session

    def get(self, endpoint, **params):
        search = endpoint == 'search'
        tries = 2 if search else 3   # every search attempt, failed or not, costs 1 of the 100 daily searches
        for attempt in range(tries):
            if self.metrics['search_calls'] >= self.cfg['max_searches'] and search:
                raise BudgetStop('Search budget reached')
            if not search and self.metrics['other_api_calls'] >= self.cfg['other_api_units_budget']:
                raise BudgetStop('Inspection budget reached')
            self.metrics['search_calls' if search else 'other_api_calls'] += 1
            import requests
            try:
                response = self.session.get('https://www.googleapis.com/youtube/v3/' + endpoint,
                        params={**params, 'key': self.key}, timeout=25)
                data = response.json()
            except (requests.RequestException, ValueError):
                self.metrics['failed_requests'] += 1
                if attempt == tries - 1:
                    raise YouTubeError('YouTube network or response failure (' + endpoint + ', HTTP ' + str(getattr(locals().get('response'), 'status_code', '?')) + ')') from None
            else:
                if response.ok:
                    return data
                reasons = [e.get('reason', '') for e in data.get('error', {}).get('errors', [])]
                self.metrics['failed_requests'] += 1
                if any(r in ('quotaExceeded', 'dailyLimitExceeded') for r in reasons):
                    raise BudgetStop('Provider quota reached')
                if response.status_code not in (429, 500, 502, 503, 504):
                    raise YouTubeError(f'YouTube HTTP {response.status_code} {",".join(reasons)}; check key and enabled API')
                if attempt == tries - 1:
                    raise YouTubeError(f'YouTube temporarily unavailable (HTTP {response.status_code} {",".join(reasons)})')
            self.metrics['retries'] += 1
            time.sleep(2 ** attempt)

    def channels(self, ids):
        if not ids:
            return {}
        data = self.get('channels', part='snippet,statistics,contentDetails', id=','.join(ids), maxResults=50)
        return {c['id']: c for c in data.get('items', [])}

    def resolve_handle(self, handle):
        # forHandle costs 1 quota unit; a failure just means the related channel is skipped.
        try:
            items = self.get('channels', part='id', forHandle=handle).get('items', [])
        except (YouTubeError, BudgetStop):  # never lose the current lead over an optional lookup
            return ''
        return items[0]['id'] if items else ''

    def featured(self, channel_id):
        # Channels a creator features on their page are often same-niche peers. 1 quota unit, no search needed.
        try:
            data = self.get('channelSections', part='contentDetails', channelId=channel_id)
        except (YouTubeError, BudgetStop):
            return []
        return [c for s in data.get('items', []) for c in s.get('contentDetails', {}).get('channels', [])]

    def videos(self, playlist):
        from .qualification import duration
        videos, token = [], None
        complete = False
        for _ in range(self.cfg['max_upload_pages']):
            params = dict(part='contentDetails', playlistId=playlist, maxResults=50)
            if token:
                params['pageToken'] = token
            page = self.get('playlistItems', **params)
            ids = [x['contentDetails']['videoId'] for x in page.get('items', [])]
            if ids:
                data = self.get('videos', part='snippet,statistics,contentDetails', id=','.join(ids))
                for item in data.get('items', []):
                    # Ongoing streams have no stable duration and are not upload evidence.
                    if item['snippet'].get('liveBroadcastContent') in ('live', 'upcoming'):
                        continue
                    videos.append(dict(id=item['id'], title=item['snippet']['title'],
                        description=item['snippet'].get('description', ''),
                        published=item['snippet']['publishedAt'],
                        language=item['snippet'].get('defaultAudioLanguage') or item['snippet'].get('defaultLanguage', ''),
                        seconds=duration(item['contentDetails'].get('duration', '')),
                        views=int(item.get('statistics', {}).get('viewCount', 0))))
            token = page.get('nextPageToken')
            longs = [v for v in videos if v['seconds'] > self.cfg['long_video_min_seconds_exclusive']]
            # Need BOTH the view sample and complete activity coverage through the cutoff.
            from .models import utcnow, parse
            from datetime import timedelta
            cutoff = utcnow() - timedelta(days=self.cfg['activity_days'])
            covered = any(parse(v['published']) < cutoff for v in videos)
            if not token or (len(longs) >= self.cfg['video_sample_size'] and covered):
                complete = True
                break
        videos.sort(key=lambda v: v['published'], reverse=True)
        return videos, complete
