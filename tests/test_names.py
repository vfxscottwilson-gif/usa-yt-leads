import unittest
from src.names import infer_person, email_allowed, guess_email, domain_matches_name, people_from_text

class NameTests(unittest.TestCase):
    def test_title_names(self):
        self.assertEqual(infer_person('Travel with Dave'), ('Dave', 'Dave'))
        self.assertEqual(infer_person('Dr. Robert Cywes'), ('Robert', 'Robert Cywes'))
        self.assertEqual(infer_person('Dave Asprey'), ('Dave', 'Dave Asprey'))
        self.assertEqual(infer_person('DRM News'), ('', ''))
        self.assertEqual(infer_person('Precision Signal'), ('', ''))

    def test_email_domain_rules(self):
        self.assertFalse(email_allowed('policy@github.com', 'github.com', set()))
        self.assertFalse(email_allowed('pmc-phe@ncbi.nlm.nih.gov', 'nacproplus.com', set()))
        self.assertTrue(email_allowed('info@drm.news', 'drm.news', set()))
        self.assertTrue(email_allowed('someone@gmail.com', 'creator.org', set()))
        self.assertTrue(email_allowed('support@bulletproofmedia.com', 'facebook.com', set()))
        self.assertFalse(email_allowed('x@other.com', 'creator.org', set()))

    def test_guess_and_domain(self):
        self.assertEqual(guess_email('Dave', 'daveasprey.com'), 'dave@daveasprey.com')
        self.assertEqual(guess_email('', 'daveasprey.com'), '')
        self.assertTrue(domain_matches_name('daveasprey.com', 'Dave Asprey'))
        self.assertFalse(domain_matches_name('github.com', 'Dave Asprey'))

    def test_team_page_people(self):
        chunks = ['Our Team', 'Sarah Miller', 'Founder & CEO', 'Mark Lee, Head of Marketing', 'Random Words']
        people = people_from_text(chunks, 'https://x.org/team')
        self.assertEqual([(p['full_name'], p['designation']) for p in people],
            [('Sarah Miller', 'Founder & CEO'), ('Mark Lee', 'Head of Marketing')])

if __name__ == '__main__':
    unittest.main()


class RowTests(unittest.TestCase):
    def test_row_has_inferred_name_guess_and_clean_phone(self):
        from src.pipeline import build_rows
        from src.config import load
        from src.models import utcnow
        cfg, _ = load()
        channel = {'id': 'UCx', 'snippet': {'title': 'Dave Asprey'}, 'statistics': {'subscriberCount': '330000'}}
        ev = dict(niche='Health', videos_checked=20, videos_above=5, average_views=9000, active=[1, 2, 3],
                  last_upload='2026-11-01', reason='')
        research = dict(contacts={}, links={}, phones=['212 555 0123'], team_pages=[], people=[], guess_domain='daveasprey.com')
        row = build_rows(channel, ev, research, cfg, 'run1', utcnow())[0]
        self.assertEqual((row['First Name'], row['Full Name'], row['Guessed Email']), ('Dave', 'Dave Asprey', 'dave@daveasprey.com'))
        self.assertEqual(row['Phone Number'], '212 555 0123')


class BlockedSiteTests(unittest.TestCase):
    def test_403_site_is_read_through_browser_and_name_matched_site_is_trusted(self):
        from collections import Counter
        from unittest import mock
        from src.config import load
        from src.contacts import Research, Page
        cfg, _ = load()
        cfg['browser_enabled'] = True
        research = Research(cfg, Counter())
        resp = mock.MagicMock(ok=False, is_redirect=False, status_code=403, headers={})
        resp.__enter__.return_value = resp

        def render(url, page):
            page.feed('<p>Call 888-732-1625</p><a href="mailto:subs@theabsolutesound.com">EMAIL</a>')
        research.render_fallback = render
        with mock.patch('src.contacts.safe_public_url', return_value=True), mock.patch('requests.get', return_value=resp):
            url, page = research.fetch('https://theabsolutesound.com/contact/')
        self.assertIn('subs@theabsolutesound.com', page.mail)
        research.fetch = lambda u: (u, page)
        channel = {'id': 'UCx', 'snippet': {'title': 'THE ABSOLUTE SOUND', 'description': 'More at https://theabsolutesound.com'}}
        result = research.collect(channel, [])
        self.assertEqual(result['phones'], ['888 732 1625'])
        self.assertTrue(result['contacts']['subs@theabsolutesound.com']['supported'])


class PanelLinkTests(unittest.TestCase):
    def test_panel_links_are_sorted_into_columns(self):
        from collections import Counter
        from src.config import load
        from src.contacts import Research, Page
        cfg, _ = load()
        research = Research(cfg, Counter())
        research.channel_panel = lambda cid: {'status': 'ok', 'emails': [], 'links': [
            'https://open.spotify.com/show/abc', 'https://calendly.com/me/30min', 'https://tkopod.co/ytp-cjk',
            'https://www.instagram.com/koerner']}
        research.fetch = lambda u: (u, None)
        result = research.collect({'id': 'UCx', 'snippet': {'title': 'Chris Koerner', 'description': ''}}, [])
        self.assertEqual(result['links']['Website'], 'https://tkopod.co/ytp-cjk')
        self.assertEqual(result['links']['Instagram'], 'https://www.instagram.com/koerner')


class OldCodeFeatureTests(unittest.TestCase):
    def test_instagram_handle_written_as_text(self):
        from collections import Counter
        from src.config import load
        from src.contacts import Research
        cfg, _ = load()
        research = Research(cfg, Counter())
        research.channel_panel = lambda cid: {}
        research.fetch = lambda u: (u, None)
        result = research.collect({'id': 'UCx', 'snippet': {'title': 'X', 'description': 'Business: IG: @dave.asprey.'}}, [])
        self.assertEqual(result['links']['Instagram'], 'https://www.instagram.com/dave.asprey')

    def test_featured_channels_parsed(self):
        from collections import Counter
        from src.youtube import YouTube
        api = YouTube('k', {}, Counter())
        api.get = lambda *a, **k: {'items': [{'contentDetails': {'channels': ['UCa', 'UCb']}}, {'contentDetails': {}}]}
        self.assertEqual(api.featured('UCx'), ['UCa', 'UCb'])
