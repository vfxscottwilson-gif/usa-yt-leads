import unittest
from unittest.mock import patch
from collections import Counter
from src.contacts import Research, Page

class BrowserFallbackTests(unittest.TestCase):
    def test_public_render_results_merge_without_losing_contacts(self):
        r = Research({}, Counter())
        page = Page()
        page.mail = ['old@creator.org']
        with patch('src.contacts.run_browser_task', return_value=dict(status='ok',url='https://creator.org/contact',html='<a href="mailto:new@creator.org">Email</a>',requests=3)):
            r.render_fallback('https://creator.org/contact', page)
        self.assertIn('old@creator.org', page.mail)
        self.assertIn('new@creator.org', page.mail)
        self.assertEqual(r.metrics['browser_successes'], 1)

    def test_failed_render_preserves_static_results(self):
        r = Research({}, Counter())
        page = Page()
        page.mail = ['old@creator.org']
        with patch('src.contacts.run_browser_task', side_effect=ValueError('challenge')):
            r.render_fallback('https://creator.org/contact', page)
        self.assertEqual(page.mail, ['old@creator.org'])
        self.assertEqual(r.metrics['browser_failures'], 1)

    def test_social_domains_not_rendered(self):
        r = Research({}, Counter())
        with patch('src.contacts.run_browser_task') as render:
            r.render_fallback('https://www.youtube.com/about', Page())
            r.render_fallback('https://www.instagram.com/someone', Page())
            r.render_fallback('https://www.linkedin.com/in/someone', Page())
            render.assert_not_called()

    def test_browser_budget_and_provenance(self):
        r = Research({'browser_max_pages_per_run':1}, Counter())
        page = Page()
        with patch('src.contacts.run_browser_task', return_value=dict(status='ok',url='https://other.org',html='<a href="mailto:other@other.org">Email</a>',requests=1)) as render:
            r.render_fallback('https://creator.org', page)
            r.render_fallback('https://creator.org', page)
        self.assertEqual(render.call_count, 1)
        self.assertEqual(page.mail, [])
        self.assertEqual(r.metrics['browser_failures'], 1)
