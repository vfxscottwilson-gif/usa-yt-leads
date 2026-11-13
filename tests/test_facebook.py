import unittest
from collections import Counter
from src.config import load
from src.contacts import Research


class FacebookTests(unittest.TestCase):
    def test_facebook_page_is_read_through_browser_and_email_accepted(self):
        cfg, _ = load()
        cfg['browser_enabled'] = True
        research = Research(cfg, Counter())

        def render(url, page, wait=False):
            self.assertTrue(wait)
            page.feed('<div>Contact info</div><div>support@creator.com</div>')
        research.render_fallback = render
        research.channel_panel = lambda cid: {}
        channel = {'id': 'UCx', 'snippet': {'title': 'Creator', 'description': 'https://www.facebook.com/creator'}}
        result = research.collect(channel, [])
        self.assertTrue(result['contacts']['support@creator.com']['supported'])
        self.assertEqual(result['contacts']['support@creator.com']['source'], 'https://www.facebook.com/creator')


if __name__ == '__main__':
    unittest.main()
