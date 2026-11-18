import re
from datetime import timedelta
from .models import parse, utcnow
from .location import locate
from .filters import fake_country, ai_slop, excluded_topic

def duration(value):
    match = re.fullmatch(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', value)
    if not match:
        return 0
    d, h, m, s = [int(x or 0) for x in match.groups()]
    return d * 86400 + h * 3600 + m * 60 + s

def precheck(channel, cfg):
    stats = channel.get('statistics', {})
    if stats.get('hiddenSubscriberCount') or 'subscriberCount' not in stats:
        return 'review', 'Subscriber count unavailable'
    if not cfg['min_subscribers'] <= int(stats['subscriberCount']) <= cfg['max_subscribers']:
        return 'rejected', 'Subscriber count outside configured range'
    country = channel['snippet'].get('country', '')
    if country and country not in cfg.get('countries', ['US']):
        return 'rejected', 'Channel country metadata is not ' + '/'.join(cfg.get('countries', ['US']))
    return '', ''

def evaluate(channel, videos, complete, cfg, niches, confirmed=False):
    cutoff = utcnow() - timedelta(days=cfg['activity_days'])
    longs = [v for v in videos if v['seconds'] > cfg['long_video_min_seconds_exclusive']]
    sample = longs[:cfg['video_sample_size']]
    active = [v for v in longs if parse(v['published']) >= cutoff]
    hits = sum(v['views'] >= cfg['min_video_views'] for v in sample)
    reasons, failures = [], []
    if hits < cfg['min_videos_above_threshold']:
        (failures if complete else reasons).append('Fewer than two sampled long videos meet view threshold')
    if len(active) < cfg['min_long_uploads']:
        (failures if complete else reasons).append('Insufficient long uploads in activity window')
    # Country: banned regions and other countries are rejected outright (never reviewed). A channel with no country
    # field and no clear signal follows "unknown_country_policy": accept (default), review or reject.
    # Floor: no sampled long video may sit under min_every_video_views. Videos newer than floor_min_age_days are skipped,
    # because a video posted yesterday has not had time to collect views. A floor miss cannot be undone by more data.
    floor = cfg.get('min_every_video_views', 0)
    if floor:
        old_enough = utcnow() - timedelta(days=cfg.get('floor_min_age_days', 7))
        judged = [v for v in sample[:cfg.get('floor_sample_size', len(sample))] if parse(v['published']) <= old_enough]
        low = [v for v in judged if v['views'] < floor]
        if low:
            failures.append(f'{len(low)} of {len(judged)} sampled long videos have under {floor:,} views')
    where, note = locate(channel, videos, cfg)
    location_note = ''
    # Evidence filters: fake country, AI-generated channels, unwanted topics. Rejected outright, never reviewed.
    for verdict, why in (fake_country(channel, videos, cfg), ai_slop(channel, videos, sample, cfg), excluded_topic(channel, sample, cfg)):
        if verdict == 'reject':
            failures.append(why)
        elif verdict == 'review':
            reasons.append(why)
    if where == 'reject':
        failures.append(note)
    elif where == 'unknown':
        policy = cfg.get('unknown_country_policy', 'accept')
        label = '/'.join(cfg.get('countries', ['US']))
        if policy == 'reject':
            failures.append(label + ' location not established')
        elif policy == 'review':
            reasons.append(label + ' location not established: no country on the channel and no clear signals in its text')
        else:
            location_note = 'Country not set on channel; no sign of another country (accepted by policy). '
    text = ' '.join([channel['snippet']['title'], channel['snippet'].get('description', '')]
                    + [v['title'] for v in sample]).lower()
    scored = [(sum(text.count(s.lower()) for s in n['signals']), n['name']) for n in niches]
    best = max(scored, default=(0, ''))
    niche = best[1] if best[0] else ''  # no niche only means "All Leads without a niche tab"; it never blocks a qualified lead
    if cfg['require_talking_head_confirmation'] and not confirmed:
        reasons.append('Talking head format requires visual confirmation')
    # An incomplete upload scan can only matter when the criteria above are not met yet; if they are met, more data cannot undo it.
    in_window = [v for v in videos if parse(v['published']) >= cutoff]
    status = 'rejected' if failures else ('review' if reasons else 'qualified')
    return dict(status=status, reason='; '.join(failures or reasons), niche=niche,
        sample=sample, active=active, videos_above=hits, videos_checked=len(sample),
        average_views=round(sum(v['views'] for v in sample) / len(sample)) if sample else '',
        last_upload=longs[0]['published'] if longs else '',
        uploads_in_window=len(in_window), shorts_in_window=len(in_window) - len(active), location_note=location_note)
