import unittest
from collections import Counter
from src.contacts import clean_url, host, record_link, Research, Page, normalize_phone
from src.config import load


class ContactRegressionTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        patcher = patch('src.contacts.run_browser_task', return_value={'status':'panel_missing','reason':'Test fixture'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_malformed_description_does_not_abort_collection(self):
        cfg, _ = load()
        research = Research(cfg, Counter())
        research.fetch = lambda url: (url, Page())
        channel = {'id': 'UCtest', 'snippet': {'description':
            'https://[broken Contact email: contact@creator.org'}}
        result = research.collect(channel, [])
        self.assertIn('contact@creator.org', result['contacts'])
        self.assertNotIn('All Discovered Links', result['links'])

    def test_invalid_ports_and_brackets_are_skipped(self):
        for url in ['https://[broken', 'https://site.org:bad/path',
                    'https://user:password@site.org', 'javascript:alert(1)']:
            self.assertEqual(clean_url(url), '')
            self.assertEqual(host(url), '')
            result = {'links': {}}
            record_link(result, url, 'source')
            self.assertEqual(result['links'], {})
        self.assertEqual(clean_url('/team', 'https://creator.org'), 'https://creator.org/team')

    def test_public_facebook_email_keeps_source_and_is_accepted(self):
        cfg, _ = load()
        research = Research(cfg, Counter())
        page = Page()
        page.feed('<a href="mailto:support@creator.org">Contact</a>')
        research.fetch = lambda url: (url, page)
        channel = {'id': 'UCtest', 'snippet': {'description': 'https://facebook.com/creator'}}
        result = research.collect(channel, [])
        contact = result['contacts']['support@creator.org']
        self.assertEqual(contact['source'], 'https://www.facebook.com/creator')
        self.assertTrue(contact['supported'])

    def test_reference_site_not_mistaken_for_creator_website(self):
        cfg, _ = load()
        research = Research(cfg, Counter())
        calls = []
        def fetch(url):
            calls.append(url)
            return url, Page()
        research.fetch = fetch
        channel = {'id': 'UCtest', 'snippet': {'description':
            'Research https://doi.org/10/example Code https://github.com/example'}}
        result = research.collect(channel, [])
        self.assertEqual(calls, [])
        self.assertNotIn('Website', result['links'])
        self.assertNotIn('All Discovered Links', result['links'])

    def test_broken_page_link_does_not_lose_good_contact(self):
        cfg, _ = load()
        cfg['verified_creator_domains'] = {'UCtest': ['creator.org']}
        research = Research(cfg, Counter())
        page = Page()
        page.feed('<a href="https://[bad">Bad</a><a href="mailto:hello@creator.org">Contact</a>')
        research.fetch = lambda url: (url, page)
        result = research.collect({'id': 'UCtest', 'snippet': {'description': 'https://creator.org'}}, [])
        self.assertTrue(result['contacts']['hello@creator.org']['supported'])

    def test_us_phone_format_does_not_damage_other_country_codes(self):
        self.assertEqual(normalize_phone('+1 (212) 555-0123'), '212 555 0123')
        self.assertEqual(normalize_phone('+44 20 1234 5678'), '44 20 1234 5678')  # a leading + would become a Sheets formula

if __name__ == '__main__':
    unittest.main()
