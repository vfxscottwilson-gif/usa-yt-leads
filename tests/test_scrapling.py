import unittest
from collections import Counter
from unittest.mock import patch
from src.contacts import Research, Page, people_from_structured
from src.extractors.scrapling_html import extract

class ScraplingTests(unittest.TestCase):
    def test_extracts_microdata_without_guessing(self):
        result = extract('''<section itemscope itemtype="https://schema.org/Person">
          <span itemprop="name">Jane Rivera</span><span itemprop="givenName">Jane</span>
          <span itemprop="jobTitle">Founder</span>
          <meta itemprop="email" content="jane@creator.org">
          <meta itemprop="telephone" content="+12125550123">
        </section>''')
        self.assertEqual(result['emails'], ['jane@creator.org'])
        self.assertEqual(result['phones'], ['+12125550123'])
        person = people_from_structured(result['people'], 'https://creator.org/team')[0]
        self.assertEqual(person['full_name'], 'Jane Rivera')
        self.assertEqual(person['designation'], 'Founder')

    def test_name_and_role_in_different_people_not_joined(self):
        result = extract('''<div itemscope itemtype="https://schema.org/Person"><span itemprop="name">Jane</span></div>
          <div itemscope itemtype="https://schema.org/Person"><span itemprop="jobTitle">CEO</span></div>''')
        self.assertEqual(result['people'], [])

    def test_explicitly_hidden_metadata_ignored(self):
        result = extract('<div hidden><meta itemprop="email" content="hidden@creator.org"></div>')
        self.assertEqual(result['emails'], [])

    def test_research_uses_real_scrapling_and_counts_it(self):
        research = Research({'html_extractor':'scrapling'}, Counter())
        page = Page()
        research.enrich_page(page, '<meta itemprop="email" content="hello@creator.org">')
        self.assertEqual(page.mail, ['hello@creator.org'])
        self.assertEqual(research.metrics['scrapling_pages'], 1)
        self.assertEqual(research.metrics['website_requests'], 0)

    def test_extractor_failure_preserves_existing_contacts(self):
        research = Research({'html_extractor':'scrapling'}, Counter())
        page = Page()
        page.mail = ['existing@creator.org']
        with patch('src.extractors.scrapling_html.extract', side_effect=ValueError('bad HTML')):
            research.enrich_page(page, '<bad>')
        self.assertEqual(page.mail, ['existing@creator.org'])
        self.assertEqual(research.metrics['scrapling_failures'], 1)

    def test_builtin_mode_does_not_invoke_scrapling(self):
        research = Research({'html_extractor':'builtin'}, Counter())
        with patch('src.extractors.scrapling_html.extract') as parser:
            research.enrich_page(Page(), '<p>Hi</p>')
            parser.assert_not_called()
