"""Decide where a channel is based, and keep banned countries out completely.

Order of trust: YouTube's own country field, then the channel's text (place names, web address endings, video language,
writing script), then, only for banned regions, the creator's name. Banned channels are rejected: they never reach
All Leads or Needs Review.
"""
import re

# tld = web/email address endings, words = place names. Add or override countries in settings.json under "country_hints".
HINTS = {
    'GB': dict(tld=['uk'], words=['united kingdom', 'u.k.', 'uk', 'england', 'scotland', 'wales', 'northern ireland', 'british',
                                  'london', 'manchester', 'birmingham', 'glasgow', 'liverpool', 'leeds', 'edinburgh', 'bristol']),
    'US': dict(tld=['us'], words=['united states', 'texas', 'california', 'new york', 'florida', 'los angeles', 'chicago',
                                  'miami', 'las vegas', 'atlanta', 'seattle', 'denver', 'usa']),
    'CA': dict(tld=['ca'], words=['canada', 'canadian', 'toronto', 'vancouver', 'montreal', 'calgary', 'ontario', 'alberta', 'ottawa']),
    'AU': dict(tld=['au'], words=['australia', 'australian', 'sydney', 'melbourne', 'brisbane', 'perth', 'adelaide', 'queensland']),
    'NZ': dict(tld=['nz'], words=['new zealand', 'auckland', 'wellington', 'christchurch']),
    'IE': dict(tld=['ie'], words=['ireland', 'irish', 'dublin', 'cork', 'galway']),
    'SG': dict(tld=['sg'], words=['singapore', 'singaporean']),
    'MT': dict(tld=['mt'], words=['malta', 'maltese', 'valletta']),
    'ZA': dict(tld=['za'], words=['south africa', 'johannesburg', 'cape town', 'durban', 'pretoria']),
    'AE': dict(tld=['ae'], words=['dubai', 'abu dhabi', 'uae', 'united arab emirates']),
    'DE': dict(tld=['de'], words=['germany', 'deutschland', 'berlin', 'munich', 'hamburg', 'frankfurt']),
    'RU': dict(tld=['ru'], words=['россия', 'москва', 'санкт-петербург', 'russia', 'moscow']),
    # banned by default (see "banned_countries" in settings.json)
    'IN': dict(tld=['in'], words=['india', 'indian', 'mumbai', 'delhi', 'bangalore', 'bengaluru', 'hyderabad', 'chennai', 'kolkata',
                                  'pune', 'ahmedabad', 'jaipur', 'lucknow', 'noida', 'gurgaon', 'gurugram']),
    'PK': dict(tld=['pk'], words=['pakistan', 'pakistani', 'karachi', 'lahore', 'islamabad', 'rawalpindi', 'peshawar', 'faisalabad',
                                  'multan', 'quetta']),
    'BD': dict(tld=['bd'], words=['bangladesh', 'bangladeshi', 'dhaka', 'chittagong', 'sylhet']),
    'NG': dict(tld=['ng'], words=['nigeria', 'nigerian', 'lagos', 'abuja']),
    'PH': dict(tld=['ph'], words=['philippines', 'filipino', 'manila', 'cebu']),
}
# YouTube video/channel languages typical of the banned regions (Hindi, Urdu, Bengali, Tamil, Telugu, Malayalam, Kannada, Marathi, Gujarati, Punjabi)
BANNED_LANGUAGES = {'hi', 'ur', 'bn', 'ta', 'te', 'ml', 'kn', 'mr', 'gu', 'pa'}
OTHER_LANGUAGE_REGIONS = {'IN', 'PK', 'BD', 'NG', 'PH', 'KE', 'LK'}
CYRILLIC = re.compile(r'[а-яёА-ЯЁ]')
# Common South Asian given names and family names. Used ONLY when the channel has no country and no sign of a target country.
SOUTH_ASIAN_NAMES = set('''
singh kumar sharma gupta verma yadav khan ahmed ahmad hussain hossain rahman begum akhtar iqbal sheikh shaikh malik chaudhry
chowdhury patel shah reddy naidu nair iyer iyengar pillai menon joshi mehta desai banerjee chatterjee mukherjee bhatt bhatia
kapoor chopra agarwal aggarwal jain mishra pandey tiwari dubey saxena srivastava thakur rathore chauhan rajput siddiqui ansari
qureshi mirza baig butt cheema gill sandhu dhillon grewal sidhu bajwa awan rana raja
rahul amit ankit rohit vikram priya pooja neha sachin ravi sunil anil ajay vijay suresh ramesh mahesh deepak manish nikhil akash
aakash arjun kapil sanjay sandeep rajesh rajat varun vivek abhishek shubham gaurav mohit tushar harsh yash ritesh muhammad
mohammad mohammed muhammed imran usman bilal hamza faisal zubair tariq irfan asif kamran shahid sajid waqar arif naveen
praveen karthik sundar lakshmi anjali shreya divya kavita sunita rekha simran harpreet gurpreet jaspreet manpreet tanveer
saleem salman shoaib junaid hassan hasan hussein farhan zeeshan adnan nadeem rizwan shehzad shahzad babar waseem
'''.split())


def _matches(code, text, hints):
    spec = hints.get(code)
    if not spec:
        return False
    if any(re.search(r'\.' + re.escape(t) + r'(?:[/\s"\'>)\],]|$)', text) for t in spec.get('tld', [])):
        return True
    return any(re.search(r'(?<![\w])' + re.escape(w) + r'(?![\w])', text) for w in spec.get('words', []))


def _name_looks_banned(title):
    tokens = re.findall(r"[a-z]+", title.lower())
    return any(t in SOUTH_ASIAN_NAMES for t in tokens)


def locate(channel, videos, cfg):
    """Returns (verdict, note): 'accept' | 'reject' | 'unknown'."""
    targets = set(cfg.get('countries', ['US']))
    banned = set(cfg.get('banned_countries', ['IN', 'PK', 'BD'])) - targets
    snippet = channel['snippet']
    country = str(snippet.get('country', '')).upper()
    if country:
        if country in banned:
            return 'reject', f'Banned country ({country})'
        return ('accept', 'country set on channel') if country in targets else ('reject', f'Channel country is {country}')
    hints = {**HINTS, **cfg.get('country_hints', {})}
    text = ' '.join([snippet.get('title', ''), snippet.get('description', '')]
                    + [v.get('title', '') + ' ' + v.get('description', '') for v in videos[:10]]).lower()
    languages = {str(snippet.get('defaultLanguage', '')).lower().split('-')[0]} | {str(v.get('language', '')).lower().split('-')[0] for v in videos}
    regions = {str(v.get('language', '')).split('-')[-1].upper() for v in videos if '-' in str(v.get('language', ''))}
    regions |= {str(snippet.get('defaultLanguage', '')).split('-')[-1].upper()} if '-' in str(snippet.get('defaultLanguage', '')) else set()

    # 1) strong signs of a banned or other non-target region win over everything else
    negative = [c for c in hints if c not in targets and (_matches(c, text, hints) or (c in regions and c in OTHER_LANGUAGE_REGIONS))]
    if languages & BANNED_LANGUAGES:
        negative.append('banned-language')
    banned_hit = [c for c in negative if c in banned or c == 'banned-language']
    if banned_hit:
        return 'reject', 'Signals point to a banned region (' + '/'.join(sorted(set(banned_hit))) + ')'
    positive = [c for c in targets if _matches(c, text, hints) or c in regions]
    if cfg.get('require_script') == 'cyrillic' or 'RU' in targets:
        if CYRILLIC.search(text) or 'ru' in languages:
            positive.append('script')
        elif cfg.get('require_script') == 'cyrillic':
            return 'reject', 'No Russian-language text found'
    if negative and not positive:
        return 'reject', 'Location signals point to ' + '/'.join(sorted(negative)) + ', not ' + '/'.join(sorted(targets))
    if positive and not negative:
        return 'accept', 'location inferred from channel text or language'
    # 2) the creator's name is only used to keep banned regions out, never to let anyone in
    if not positive and _name_looks_banned(snippet.get('title', '')):
        return 'reject', 'Channel name looks South Asian and no country is set'
    return 'unknown', ''
