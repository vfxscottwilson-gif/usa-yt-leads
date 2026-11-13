import unittest
from src.location import locate
from src.config import load
from src.qualification import evaluate
from src.models import utcnow

CFG = {'countries': ['GB'], 'banned_countries': ['IN', 'PK', 'BD']}


def channel(description='', title='Some Creator', country=None, language=None):
    snippet = {'title': title, 'description': description}
    if country:
        snippet['country'] = country
    if language:
        snippet['defaultLanguage'] = language
    return {'id': 'UCx', 'snippet': snippet, 'statistics': {'subscriberCount': '100000'}}


def video(language='', title='A video'):
    return dict(id='v', title=title, description='', views=50000, seconds=900, language=language, published=utcnow().isoformat())


class LocateTests(unittest.TestCase):
    def test_country_field_decides_first(self):
        self.assertEqual(locate(channel(country='GB', title='Rahul Sharma'), [], CFG)[0], 'accept')   # name ignored when the country is set
        self.assertEqual(locate(channel(country='IN'), [], CFG)[0], 'reject')
        self.assertEqual(locate(channel(country='US'), [], CFG)[0], 'reject')

    def test_banned_regions_are_rejected_without_country_field(self):
        self.assertEqual(locate(channel('Made in Karachi'), [], CFG)[0], 'reject')
        self.assertEqual(locate(channel('mail me at x@shop.co.in'), [], CFG)[0], 'reject')
        self.assertEqual(locate(channel('hello'), [video('hi')], CFG)[0], 'reject')          # Hindi videos
        self.assertEqual(locate(channel('hello'), [video('en-IN')], CFG)[0], 'reject')
        self.assertEqual(locate(channel('Dhaka tips and London visits'), [], CFG)[0], 'reject')  # banned wins over target

    def test_south_asian_name_is_rejected_only_with_no_target_signal(self):
        self.assertEqual(locate(channel('Business tips', title='Rahul Sharma'), [], CFG)[0], 'reject')
        self.assertEqual(locate(channel('Based in London', title='Rahul Sharma'), [], CFG)[0], 'accept')

    def test_target_signals_and_unknown(self):
        self.assertEqual(locate(channel('Manchester based, site shop.co.uk'), [], CFG)[0], 'accept')
        self.assertEqual(locate(channel('Business tips for everyone'), [], CFG)[0], 'unknown')

    def test_russian_script(self):
        ru = {'countries': ['RU'], 'banned_countries': ['IN', 'PK', 'BD']}
        self.assertEqual(locate(channel('Бизнес и инвестиции'), [], ru)[0], 'accept')
        self.assertEqual(locate(channel('Business only'), [], {**ru, 'require_script': 'cyrillic'})[0], 'reject')


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.cfg, _ = load()
        self.cfg['countries'] = ['GB']
        self.cfg.pop('require_script', None)   # these tests are about English channels whatever package this is
        self.cfg['unknown_country_policy'] = 'accept'
        self.niches = [dict(name='Real Estate', signals=['real estate'], queries=['q'], topics=[])]
        self.vids = [video() for _ in range(4)]

    def test_blank_country_with_no_signals_is_accepted_by_default_not_reviewed(self):
        r = evaluate(channel('Real estate advice'), self.vids, True, self.cfg, self.niches)
        self.assertEqual(r['status'], 'qualified')
        self.assertIn('Country not set', r['location_note'])

    def test_policy_can_be_review_or_reject(self):
        self.cfg['unknown_country_policy'] = 'review'
        self.assertEqual(evaluate(channel('Real estate advice'), self.vids, True, self.cfg, self.niches)['status'], 'review')
        self.cfg['unknown_country_policy'] = 'reject'
        self.assertEqual(evaluate(channel('Real estate advice'), self.vids, True, self.cfg, self.niches)['status'], 'rejected')

    def test_banned_channel_is_rejected_not_reviewed(self):
        r = evaluate(channel('Real estate advice from Lahore'), self.vids, True, self.cfg, self.niches)
        self.assertEqual(r['status'], 'rejected')

    def test_missing_niche_and_incomplete_scan_do_not_cause_review_when_criteria_are_met(self):
        r = evaluate(channel('Advice from London'), self.vids, False, self.cfg, [])
        self.assertEqual(r['status'], 'qualified')


if __name__ == '__main__':
    unittest.main()
