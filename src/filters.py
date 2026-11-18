"""Three extra channel filters, all based on evidence in the channel itself (never on a person's name or looks):

1. fake_country(): a channel that says it is in the target country but whose own text, links, phone numbers, language or
   posting hours show another country (typically India, Pakistan, Bangladesh).
2. ai_slop(): channels that mostly publish AI-generated videos (YouTube's own "altered or synthetic content" flag, an
   AI disclosure in the text, very high upload volume, one repeated title template). Rejected whatever their views.
3. excluded_topic(): topics the agency does not want at all (sports news and betting, by default).

Every function returns (verdict, note): verdict is 'reject', 'review' or 'ok'. Scores: a strong signal is worth 3, a weak
one 1; 3 or more rejects, exactly 2 goes to review. Settings live in settings.json ("foreign_signals", "ai_slop",
"excluded_topics"); the defaults below apply when a setting is missing.
"""
import re
from collections import Counter
from datetime import timedelta
from .models import parse, utcnow

REJECT_AT, REVIEW_AT = 3, 2

# ---------- 1. fake country -------------------------------------------------------------------------------------------
SCRIPT_RANGES = {
    'Devanagari': 'ऀ-ॿ', 'Bengali': 'ঀ-৿', 'Gurmukhi': '਀-੿', 'Gujarati': '઀-૿',
    'Tamil': '஀-௿', 'Telugu': 'ఀ-౿', 'Kannada': 'ಀ-೿', 'Malayalam': 'ഀ-ൿ',
    'Sinhala': '඀-෿', 'Arabic or Urdu': '؀-ۿ',
}
SCRIPT_RE = {name: re.compile('[' + rng + ']') for name, rng in SCRIPT_RANGES.items()}
PHONE_RE = re.compile(r'(?<!\d)(?:\+|00)\s?(?:91|92|880|94|977)[\s\-.]?\(?\d{2,}')
WHATSAPP_RE = re.compile(r'wa\.me/(?:91|92|880|94|977)\d')
TLD_RE = re.compile(r'[a-z0-9\-]\.(?:co\.in|in|com\.pk|pk|com\.bd|bd|lk|np)(?![a-z0-9])')
# Roman-script Hindi/Urdu ("Hinglish"): at least two different words are needed
HINGLISH = ('kaise', 'kya hai', 'nahi', 'bhai', 'yaar', 'ke liye', 'karna', 'paise', 'kamao', 'sikhe', 'sabse', 'bohot',
            'zaroor', 'hindi', 'urdu', 'tamil', 'telugu', 'punjabi')
CURRENCY = ('₹', 'inr', 'lakh', 'lakhs', 'crore', 'crores', 'paytm', 'upi')
SOUTH_ASIA_PLACES = ('india', 'pakistan', 'bangladesh', 'sri lanka', 'nepal', 'mumbai', 'delhi', 'new delhi', 'bangalore',
                     'bengaluru', 'hyderabad', 'chennai', 'kolkata', 'pune', 'ahmedabad', 'jaipur', 'lucknow', 'noida',
                     'gurgaon', 'gurugram', 'karachi', 'lahore', 'islamabad', 'rawalpindi', 'peshawar', 'faisalabad',
                     'multan', 'dhaka', 'chittagong', 'colombo', 'kathmandu')
BASED_IN_RE = re.compile(r'\b(?:based in|located in|from|live in|living in|born in|operating from)\s+(?:the\s+)?([a-z .]{3,30})')
SOUTH_ASIAN_LANGS = {'hi', 'ur', 'bn', 'ta', 'te', 'ml', 'kn', 'mr', 'gu', 'pa', 'si', 'ne'}


def _words(text, words):
    return {w for w in words if re.search(r'(?<![\w])' + re.escape(w) + r'(?![\w])', text)}


def fake_country(channel, videos, cfg):
    settings = cfg.get('foreign_signals', {})
    if settings.get('enabled', True) is False or 'RU' in set(cfg.get('countries', [])):
        return 'ok', ''
    snippet = channel['snippet']
    own_text = (snippet.get('title', '') + ' ' + snippet.get('description', '')).lower()
    recent = videos[:12]
    video_text = ' '.join(v.get('title', '') + ' ' + v.get('description', '') for v in recent).lower()
    everything = own_text + ' ' + video_text
    strong, weak = [], []

    scripts = [n for n, rx in SCRIPT_RE.items() if rx.search(own_text) or sum(bool(rx.search(v.get('title', ''))) for v in recent) >= 2]
    if scripts:
        strong.append('writing in ' + '/'.join(sorted(scripts)) + ' script')
    if PHONE_RE.search(everything) or WHATSAPP_RE.search(everything):
        strong.append('South Asian phone number')
    langs = {str(snippet.get('defaultLanguage', '')).lower().split('-')[0]} | {str(v.get('language', '')).lower().split('-')[0] for v in recent}
    if langs & SOUTH_ASIAN_LANGS:
        strong.append('video or channel language ' + '/'.join(sorted(langs & SOUTH_ASIAN_LANGS)))
    hits = _words(everything, HINGLISH)
    if len(hits) >= 2:
        strong.append('Hindi or Urdu words in Roman letters')
    elif hits:
        weak.append('one Hindi or Urdu word')
    if TLD_RE.search(everything):
        weak.append('web or email address ending in .in/.pk/.bd')
        if TLD_RE.search(own_text):
            strong.append('channel text has a .in/.pk/.bd address')
    places = _words(own_text, SOUTH_ASIA_PLACES)
    claimed = [m.group(1) for m in BASED_IN_RE.finditer(own_text)]
    if any(any(p in c for p in SOUTH_ASIA_PLACES) for c in claimed):
        strong.append('channel says it is based in South Asia')
    elif len(places) >= 2:
        strong.append('several South Asian places in the channel text')
    elif places:
        weak.append('a South Asian place name in the channel text')
    if _words(everything, CURRENCY):
        weak.append('Indian currency or payment words')
    window = settings.get('upload_hours_utc')
    if window is not None and len(recent) >= 8:
        lo, hi = window
        inside = sum(lo <= parse(v['published']).hour <= hi for v in recent if v.get('published'))
        if inside / len(recent) >= 0.8:
            weak.append('nearly every upload is posted during South Asian daytime')
    score = 3 * len(strong) + len(weak)
    note = '; '.join(strong + weak)
    if score >= REJECT_AT:
        return 'reject', 'Location signals point outside the target country (' + note + ')'
    if score >= REVIEW_AT:
        return 'review', 'Mixed location signals (' + note + ')'
    return 'ok', ''


# ---------- 2. AI slop --------------------------------------------------------------------------------------------------
DISCLOSURE_RE = re.compile(
    r'(?:this (?:video|channel|content) (?:was|is|has been) (?:created|made|generated|produced|narrated) (?:with|using|by) (?:an? )?(?:ai|artificial intelligence))'
    r'|(?:(?:ai|artificial intelligence)[- ](?:generated|created|produced|made|narrated) (?:voice|voiceover|narration|images?|visuals?|footage|content|video|script))'
    r'|(?:(?:voice(?:over)?|narration|script|images?|visuals?) (?:is|are|was|were) (?:generated|created|made|produced) (?:with|using|by) (?:an? )?ai)'
    r'|(?:text[- ]to[- ]speech (?:voice|narration))|(?:(?:synthetic|cloned|robotic) voice)|(?:\bfaceless (?:channel|youtube|videos?)\b)'
    r'|(?:\bautomated (?:youtube )?channel\b)|(?:\bai (?:avatar|presenter|anchor|host)\b)', re.I)
AI_TOOLS = ('elevenlabs', 'invideo', 'pictory', 'fliki', 'heygen', 'synthesia', 'midjourney', 'veo 3', 'sora', 'kling', 'runway ml')


def ai_slop(channel, videos, sample, cfg):
    settings = cfg.get('ai_slop', {})
    if settings.get('enabled', True) is False:
        return 'ok', ''
    strong, weak = [], []
    checked = sample or videos[:10]
    flagged = [v for v in checked if v.get('synthetic')]
    share = settings.get('synthetic_share', 0.3)
    if len(flagged) >= 2 and len(flagged) / max(1, len(checked)) >= share:
        strong.append(f'YouTube marks {len(flagged)} of {len(checked)} sampled videos as AI-generated or altered')
    snippet = channel['snippet']
    texts = [snippet.get('description', '')] + [v.get('description', '') for v in videos[:12]]
    disclosed = sum(bool(DISCLOSURE_RE.search(t)) for t in texts)
    if DISCLOSURE_RE.search(snippet.get('description', '')) or disclosed >= 2:
        strong.append('the text says the videos are AI-generated, AI-narrated or faceless')
    blob = ' '.join(texts).lower()
    tools = _words(blob, AI_TOOLS)
    if tools and (strong or disclosed):
        weak.append('AI video tools named (' + ', '.join(sorted(tools)) + ')')
    week = utcnow() - timedelta(days=7)
    longs_week = [v for v in videos if v.get('published') and parse(v['published']) >= week]
    if len(longs_week) >= settings.get('max_uploads_per_week', 14):
        weak.append(f'{len(longs_week)} uploads in 7 days')
        if len(longs_week) >= 2 * settings.get('max_uploads_per_week', 14):
            weak.append('more than double the normal upload volume')
    titles = [re.sub(r'[^a-z0-9 ]', '', v['title'].lower()).split() for v in checked if v.get('title')]
    if len(titles) >= 6:
        prefixes = Counter(' '.join(t[:3]) for t in titles if len(t) >= 3)
        if prefixes and prefixes.most_common(1)[0][1] / len(titles) >= settings.get('title_template_share', 0.5):
            weak.append('most titles start with the same words')
    score = 3 * len(strong) + len(weak)
    note = '; '.join(strong + weak)
    if score >= REJECT_AT:
        return 'reject', 'Looks like an AI-generated channel (' + note + ')'
    return 'ok', ''


# ---------- 3. excluded topics ---------------------------------------------------------------------------------------
def excluded_topic(channel, sample, cfg):
    snippet = channel['snippet']
    text = ' '.join([snippet.get('title', ''), snippet.get('description', '')] + [v.get('title', '') for v in sample]).lower()
    for topic in cfg.get('excluded_topics', []):
        hits = _words(text, [s.lower() for s in topic['signals']])
        if len(hits) >= topic.get('min_hits', 3):
            return 'reject', 'Excluded topic: ' + topic['name']
    return 'ok', ''
