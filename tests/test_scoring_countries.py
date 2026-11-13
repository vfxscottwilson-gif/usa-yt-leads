import unittest
from collections import Counter
from src.scoring import assess
from src.qualification import precheck
from src.discovery import discover
from src.models import utcnow
from datetime import timedelta


def video(views=30000, seconds=900):
    return dict(id='v', title='How I Built My Coaching Business', description='Join my coaching program', views=views,
                seconds=seconds, published=utcnow().isoformat())


class ScoringTests(unittest.TestCase):
    def test_score_tier_pitch_and_price(self):
        channel = {'snippet': {'title': 'Dave', 'description': 'Book a call'}, 'statistics': {'subscriberCount': '100000'}}
        evaluation = dict(sample=[video()] * 4, active=[video()] * 4, niche='Coaching', uploads_in_window=4, shorts_in_window=0)
        cells = assess(channel, evaluation, dict(contacts={'a@b.com': {'email': 'a@b.com'}}, links={}))
        self.assertTrue(0 < cells['Score'] <= 100)
        self.assertIn(cells['Tier'], 'ABC')
        self.assertIn('Saw "How I Built My Coaching Business"', cells['Pitch Angle'])
        self.assertEqual(cells['Suggested Editing Quote'], '$475 - $750')

    def test_missing_data_adds_nothing(self):
        self.assertEqual(assess({'snippet': {}, 'statistics': {}}, {}, {}), {})


class CountryTests(unittest.TestCase):
    def channel(self, country):
        return {'snippet': {'country': country}, 'statistics': {'subscriberCount': '100000'}}

    def test_country_filter_follows_settings(self):
        cfg = dict(min_subscribers=50000, max_subscribers=1000000, countries=['AU', 'NZ'])
        self.assertEqual(precheck(self.channel('AU'), cfg)[0], '')
        self.assertEqual(precheck(self.channel('US'), cfg)[0], 'rejected')

    def test_search_uses_each_configured_country(self):
        regions = []

        class Api:
            def get(self, endpoint, **params):
                regions.append(params['regionCode'])
                return {'items': []}
        cfg = dict(countries=['AU', 'NZ'], max_seed_channels_per_run=0, max_searches=95, pagination_search_fraction=0,
                   query_cooldown_days=7)
        niches = [dict(name='N', queries=['q'], signals=[])]
        discover(Api(), cfg, niches, {}, {}, Counter(), utcnow() + timedelta(minutes=5))
        self.assertEqual(set(regions), {'AU', 'NZ'})


if __name__ == '__main__':
    unittest.main()


class SearchProtectionTests(unittest.TestCase):
    def test_failing_searches_stop_after_the_limit(self):
        from src.youtube import YouTubeError
        calls = []

        class Api:
            def get(self, endpoint, **params):
                calls.append(1)
                raise YouTubeError('YouTube temporarily unavailable (HTTP 503 backendError)')
        cfg = dict(countries=['US'], max_seed_channels_per_run=0, max_searches=95, pagination_search_fraction=0,
                   query_cooldown_days=7, max_search_failures=8)
        niches = [dict(name='N', queries=['q%d' % i for i in range(20)], signals=[])]
        metrics = Counter()
        discover(Api(), cfg, niches, {}, {}, metrics, utcnow() + timedelta(minutes=5))
        self.assertEqual(len(calls), 8)
        self.assertEqual(metrics['search_failures'], 8)
