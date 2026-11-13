"""Lead score (0-100), tier, pitch line and editing price, built only from public facts. Edit the numbers freely."""
import re
import statistics

MONETIZATION = {
    'sponsor': r'sponsor|paid promotion|#ad\b',
    'affiliate/code': r'affiliate|discount code|use code|promo code',
    'patreon/membership': r'patreon|membership|buymeacoffee',
    'course/coaching': r'\bcourse\b|coaching|masterclass|mentorship|workshop|cohort',
    'booking/calls': r'calendly|book a call|apply now|application|strategy call|work with me',
    'platform': r'skool\.com|kajabi|teachable|thinkific|stan\.store|gumroad|podia|circle\.so',
    'product/software': r'free trial|\bsaas\b|my software|my app\b|our app\b|get started free',
    'merch/shop': r'merch|\bshop\b|\bstore\b',
    'newsletter': r'newsletter',
}
SELLS = {'course/coaching': 'your program', 'booking/calls': 'your calls', 'platform': 'your offer',
         'product/software': 'your product'}
EDITOR_CREDIT = re.compile(r'edited by|editor\s*:|video editor|editing by|editing\s*:', re.I)
SWEET_MIN, SWEET_MAX = 5_000, 60_000   # median views that score the full 5 points
TIER_A, TIER_B = 65, 45
# median views of recent long videos -> minimum price (USD) to edit one long video
PRICE_BANDS = [(0, 150), (10_000, 250), (25_000, 350), (50_000, 500), (100_000, 700), (250_000, 1000)]
PRICE_LENGTH = [(0, 1.0), (10 * 60, 1.2), (20 * 60, 1.4), (40 * 60, 1.7)]   # video length -> multiplier
PRICE_SELLS_OFFER = 1.15
PRICE_RANGE_TOP = 1.6


def assess(channel, evaluation, research):
    """Sheet cells for Score, Tier, Pitch Angle and Suggested Editing Quote ({} when data is missing)."""
    sample, active = evaluation.get('sample') or [], evaluation.get('active') or []
    subs = int(channel.get('statistics', {}).get('subscriberCount', 0) or 0)
    if not sample or not subs:
        return {}
    med_views = statistics.median(v['views'] for v in sample)
    ratio = med_views / subs
    blob = channel['snippet'].get('description', '') + '\n' + '\n'.join(v.get('description', '') for v in sample[:10])
    signals = [name for name, pattern in MONETIZATION.items() if re.search(pattern, blob, re.I)]
    has_editor = bool(EDITOR_CREDIT.search(blob))
    uploads = evaluation.get('uploads_in_window', len(active))
    shorts = evaluation.get('shorts_in_window', 0)
    links = research.get('links', {})
    has_email = any(c.get('email') for c in research.get('contacts', {}).values())

    sweet = 1.0 if SWEET_MIN <= med_views <= SWEET_MAX else (
        med_views / SWEET_MIN if med_views < SWEET_MIN else max(0.0, 1 - (med_views - SWEET_MAX) / (SWEET_MAX * 1.5)))
    score = round(min(uploads, 8) / 8 * 15                      # steady editing workload
                  + min(ratio / 0.25, 1) * 15                   # views per subscriber = real audience
                  + min(len(signals), 4) / 4 * 25               # they already earn money
                  + (0 if has_editor else min(len(active), 3) / 3 * 15)
                  + (15 if has_email else 7 if links.get('Instagram') else 4 if links.get('Website') else 0)
                  + sweet * 5
                  + (10 if evaluation.get('niche') else 4), 1)

    sells = [s for s in SELLS if s in signals]
    seconds = statistics.median(v['seconds'] for v in active) if active else 600
    mult = max(m for s, m in PRICE_LENGTH if seconds >= s) * (PRICE_SELLS_OFFER if sells else 1)
    low = int(round(max(p for v, p in PRICE_BANDS if med_views >= v) * mult / 25) * 25)
    high = int(round(low * PRICE_RANGE_TOP / 25) * 25)

    title = sample[0]['title']
    title = title if len(title) <= 55 else title[:52].rstrip() + '...'
    if ratio < 0.04:
        hook = f'Your recent videos average {ratio:.0%} of your {subs:,} subs; tighter hooks and pacing could win those viewers back.'
    elif shorts == 0 and len(active) >= 2:
        hook = 'You post no Shorts; I can cut each long video into 3-5 Shorts that feed your channel.'
    else:
        hook = f'Strong output ({uploads} uploads in the activity window); I can take editing off your plate.'
    close = (f' Edits built to turn viewers into buyers of {SELLS[sells[0]]}.' if sells
             else f" {evaluation.get('niche') or 'Your'} viewers buy from creators they trust; editing builds that.")
    return {'Score': score, 'Tier': 'A' if score >= TIER_A else 'B' if score >= TIER_B else 'C',
            'Pitch Angle': f'Saw "{title}". {hook}{close}' + (' NOTE: editor credit found, may already have an editor.' if has_editor else ''),
            'Suggested Editing Quote': f'${low:,} - ${high:,}'}
