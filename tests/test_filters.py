import unittest
from datetime import timedelta
from src.filters import fake_country, ai_slop, excluded_topic
from src.location import locate
from src.config import load
from src.qualification import evaluate
from src.models import utcnow, iso

US = {'countries': ['US'], 'banned_countries': ['IN', 'PK', 'BD'], 'foreign_signals': {'upload_hours_utc': [2, 10]}}


def channel(description='', title='Some Creator', country='US', language=None):
    snippet = {'title': title, 'description': description}
    if country:
        snippet['country'] = country
    if language:
        snippet['defaultLanguage'] = language
    return {'id': 'UCx', 'snippet': snippet, 'statistics': {'subscriberCount': '100000'}}


def video(title='A video', description='', days_ago=10, hour=15, views=50000, language='', synthetic=False):
    when = (utcnow() - timedelta(days=days_ago)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return dict(id='v' + title, title=title, description=description, views=views, seconds=900, language=language,
                published=iso(when), synthetic=synthetic)


class FakeCountryTests(unittest.TestCase):
    def test_us_channel_that_is_really_south_asian_is_rejected(self):
        # says US, but: Hindi video language + an Indian phone number + a .in address
        ch = channel('Business tips. WhatsApp +91 98765 43210 or mail hello@shop.co.in')
        self.assertEqual(fake_country(ch, [video(language='hi')], US)[0], 'reject')

    def test_indic_script_in_titles_is_rejected(self):
        vids = [video('पैसे कैसे कमाए'), video('बिज़नेस आइडिया'), video('normal title')]
        self.assertEqual(fake_country(channel('Money tips'), vids, US)[0], 'reject')

    def test_hinglish_needs_two_words(self):
        vids = [video('bhai ye kaise karna hai')]
        self.assertEqual(fake_country(channel('tips'), vids, US)[0], 'reject')
        self.assertNotEqual(fake_country(channel('tips'), [video('my bhai visited')], US)[0], 'reject')

    def test_based_in_south_asia_is_rejected(self):
        self.assertEqual(fake_country(channel('We are based in Lahore and ship worldwide'), [], US)[0], 'reject')

    def test_real_us_channels_pass(self):
        ch = channel('Austin Texas based tech reviewer. Business inquiries: me@example.com')
        self.assertEqual(fake_country(ch, [video(hour=17) for _ in range(10)], US)[0], 'ok')
        # a single travel mention is not enough
        self.assertEqual(fake_country(channel('We filmed a trip to Delhi last year'), [], US)[0], 'ok')
        # nothing is decided from the creator's name
        self.assertEqual(fake_country(channel('Tech tips', title='Rahul Sharma Tech'), [video(hour=16)], US)[0], 'ok')
        self.assertEqual(locate(channel('Business tips', title='Rahul Sharma', country=None), [], US)[0], 'unknown')

    def test_posting_hours_alone_only_send_to_review_at_most(self):
        vids = [video(f't{i}', hour=5) for i in range(10)]
        self.assertEqual(fake_country(channel('Tech tips'), vids, US)[0], 'ok')   # one weak signal is ignored
        self.assertEqual(fake_country(channel('Tech tips. Visit karachi.pk'), vids, US)[0] in ('review', 'reject'), True)

    def test_require_country_field(self):
        cfg = {**US, 'require_country_field': True}
        self.assertEqual(locate(channel(country=None, description='Austin Texas tips'), [], cfg)[0], 'reject')
        self.assertEqual(locate(channel(country='US'), [], cfg)[0], 'accept')


class AiSlopTests(unittest.TestCase):
    def test_synthetic_flag_majority_is_rejected(self):
        vids = [video(f'v{i}', synthetic=i < 5) for i in range(10)]
        self.assertEqual(ai_slop(channel(), vids, vids, {})[0], 'reject')

    def test_one_flagged_video_is_not_enough(self):
        vids = [video(f'v{i}', synthetic=i == 0) for i in range(10)]
        self.assertEqual(ai_slop(channel(), vids, vids, {})[0], 'ok')

    def test_disclosure_in_channel_text_is_rejected(self):
        ch = channel('All narration is AI-generated voice and the visuals are AI generated images.')
        self.assertEqual(ai_slop(ch, [video()], [video()], {})[0], 'reject')

    def test_ai_tutorial_channel_is_not_slop(self):
        ch = channel('I review AI tools like ElevenLabs and Midjourney every week.')
        self.assertEqual(ai_slop(ch, [video(f'ai {i}') for i in range(8)], [], {})[0], 'ok')

    def test_upload_flood_with_one_template_is_rejected(self):
        vids = [video(f'Top 10 facts about thing number {i}', days_ago=i % 6) for i in range(40)]
        self.assertEqual(ai_slop(channel(), vids, vids[:10], {})[0], 'reject')

    def test_normal_creator_passes(self):
        vids = [video(f'Different title {i} about {w}', days_ago=7 * i + 1) for i, w in enumerate('cars phones laptops cameras audio tv'.split())]
        self.assertEqual(ai_slop(channel('Honest reviews.'), vids, vids, {})[0], 'ok')


class TopicTests(unittest.TestCase):
    CFG = {'excluded_topics': [{'name': 'Sports News And Betting', 'min_hits': 3,
                                'signals': ['nfl', 'trade rumors', 'injury update', 'patriots', 'prizepicks']}]}

    def test_team_news_channel_is_excluded(self):
        sample = [video('Patriots trade rumors: NFL week 12'), video('Injury update on the QB')]
        self.assertEqual(excluded_topic(channel('Patriots News & Rumors', 'Patriots Today'), sample, self.CFG)[0], 'reject')

    def test_gear_review_with_one_sports_word_is_kept(self):
        self.assertEqual(excluded_topic(channel('Golf club reviews. Not about the NFL.'), [video('Driver review')], self.CFG)[0], 'ok')


class EvaluateFloorTests(unittest.TestCase):
    def setUp(self):
        self.cfg, _ = load()
        self.cfg.update(countries=['US'], unknown_country_policy='accept', min_every_video_views=5000, floor_sample_size=8)
        self.cfg.pop('require_country_field', None)
        self.cfg['excluded_topics'] = []
        self.niches = [dict(name='Real Estate', signals=['real estate'], queries=['q'], topics=[])]

    def vids(self, views):
        return [video(f'Real estate advice {w}', days_ago=3 + 4 * i, views=v) for i, (v, w) in enumerate(zip(views, 'one two three four five six'.split()))]

    def test_every_video_over_the_floor_qualifies(self):
        r = evaluate(channel('Real estate advice'), self.vids([30000, 25000, 9000, 8000, 7000, 6000]), True, self.cfg, self.niches)
        self.assertEqual(r['status'], 'qualified')

    def test_one_video_under_the_floor_is_rejected(self):
        r = evaluate(channel('Real estate advice'), self.vids([30000, 25000, 900, 8000, 7000, 6000]), True, self.cfg, self.niches)
        self.assertEqual(r['status'], 'rejected')
        self.assertIn('under 5,000 views', r['reason'])

    def test_a_video_posted_yesterday_is_not_judged(self):
        vids = self.vids([30000, 25000, 9000, 8000, 7000, 6000])
        vids.insert(0, video('Real estate fresh upload', days_ago=1, views=120))
        self.assertEqual(evaluate(channel('Real estate advice'), vids, True, self.cfg, self.niches)['status'], 'qualified')


if __name__ == '__main__':
    unittest.main()
