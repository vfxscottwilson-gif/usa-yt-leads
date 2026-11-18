import unittest
from collections import Counter
from unittest import mock
from src import enrich
from src.contacts import Page, Research
from src.config import load
from src.models import utcnow, HEADERS

OWN = 'https://creator.example/about'


def names(chunks, kind='own_site', source=OWN):
    return [c['name'] for c in enrich.names_from_text(chunks, source, kind)]


class OwnerNameTests(unittest.TestCase):
    def test_hi_im_accepted_with_evidence(self):
        found = enrich.names_from_text(["Hi, I'm Frank Joseph and I make home lab videos."], OWN, 'own_site')
        self.assertEqual(found[0]['name'], 'Frank Joseph')
        self.assertIn("I'm Frank Joseph", found[0]['evidence'])
        self.assertEqual(found[0]['source'], OWN)

    def test_other_strong_patterns(self):
        self.assertEqual(names(['My name is Sarah Miller.']), ['Sarah Miller'])
        self.assertEqual(names(["I'm Mark Lee, the founder of Lee Labs"]), ['Mark Lee'])
        self.assertEqual(names(['Founder: Sarah Miller']), ['Sarah Miller'])
        self.assertEqual(names(['Owner & Founder. Frank Joseph is a corporate IT professional']), [])  # no label colon: not a pattern
        self.assertEqual(names(['Founded by Dana Whitfield in 2019']), ['Dana Whitfield'])

    def test_testimonial_and_quote_rejected(self):
        self.assertEqual(names(['What our customers say', "Hi, I'm Jane Doe and this course changed my life."]), [])
        self.assertEqual(names(['Testimonials', 'My name is Tom Baker and I love it']), [])
        self.assertEqual(names(['He said: "Hi, I\'m John Smith, nice to meet you"']), [])
        self.assertEqual(names(['Comments', "Hi, I'm Karen Wells, great video!"]), [])

    def test_commenter_and_junk_rejected(self):
        self.assertEqual(names(["I'm Very Excited to share this"]), [])
        self.assertEqual(names(["Hi, I'm Back Again"]), [])
        self.assertEqual(names(["I'm Subscribe Now"]), [])

    def test_weak_pattern_needs_known_first_name(self):
        self.assertEqual(names(["Hi, I'm Zyxwq Plomb"]), [])
        self.assertEqual(names(['My name is Zyxwq Plomb']), ['Zyxwq Plomb'])  # explicit statement, strong pattern

    def test_json_ld_founder_and_person(self):
        data = {'@type': 'Organization', 'name': 'WunderTech', 'founder': {'@type': 'Person', 'name': 'Frank Joseph'}}
        found = enrich.names_from_structured(data, OWN, 'own_site')
        self.assertEqual([c['name'] for c in found], ['Frank Joseph'])
        person = {'@type': 'Person', 'name': 'Ann Lee', 'jobTitle': 'Founder'}
        self.assertEqual([c['name'] for c in enrich.names_from_structured([person], OWN, 'own_site')], ['Ann Lee'])
        plain = {'@type': 'Person', 'name': 'Ann Lee', 'jobTitle': 'Intern'}
        self.assertEqual(enrich.names_from_structured(plain, OWN, 'own_site'), [])

    def test_meta_author_needs_two_words_and_known_first(self):
        self.assertEqual(len(enrich.names_from_meta(['Frank Joseph'], OWN, 'own_site')), 1)
        self.assertEqual(enrich.names_from_meta(['WunderTech'], OWN, 'own_site'), [])
        self.assertEqual(enrich.names_from_meta(['Staff Writer'], OWN, 'own_site'), [])

    def test_own_page_accepted_third_party_needs_two_sources(self):
        mine = enrich.names_from_text(["Hi, I'm Frank Joseph"], OWN, 'own_site')
        self.assertEqual(enrich.pick_owner(mine)['full_name'], 'Frank Joseph')
        third = enrich.names_from_text(["Hi, I'm Frank Joseph"], 'https://facebook.com/x', 'social_bio')
        self.assertIsNone(enrich.pick_owner(third))
        two = third + enrich.names_from_text(['My name is Frank Joseph'], 'https://blog.other/me', 'third_party')
        owner = enrich.pick_owner(two)
        self.assertEqual(owner['full_name'], 'Frank Joseph')
        self.assertIn('2 independent sources', owner['evidence'])
        # two pages of one site are ONE source
        same = enrich.names_from_text(["Hi, I'm Frank Joseph"], 'https://a.other/1', 'third_party') + \
            enrich.names_from_text(["Hi, I'm Frank Joseph"], 'https://a.other/2', 'third_party')
        self.assertIsNone(enrich.pick_owner(same))

    def test_description_is_own_and_single_owner_returned(self):
        found = enrich.candidates_from_descriptions([("Welcome!\nHi, I'm Frank Joseph.\nMy name is Sarah Miller, the founder", 'https://www.youtube.com/channel/UCx')])
        owner = enrich.pick_owner(found)
        self.assertIn(owner['full_name'], ('Frank Joseph', 'Sarah Miller'))
        self.assertEqual(owner['source'], 'https://www.youtube.com/channel/UCx')

    def test_page_candidates_ignore_unrelated_hosts(self):
        page = Page()
        page.feed("<html><head><meta name='author' content='Frank Joseph'></head><body><p>Hi, I'm Frank Joseph</p></body></html>")
        self.assertEqual(enrich.candidates_from_page(page, 'https://random.example', ''), [])
        got = enrich.candidates_from_page(page, OWN, 'own_site')
        self.assertTrue(got and all(c['name'] == 'Frank Joseph' for c in got))


class EmailTests(unittest.TestCase):
    def test_types(self):
        own = ['wundertech.net']
        self.assertEqual(enrich.classify_email('someone@gmail.com', own), 'Personal')
        self.assertEqual(enrich.classify_email('a@proton.me', own), 'Personal')
        self.assertEqual(enrich.classify_email('frank@wundertech.net', own), 'Own Domain')
        self.assertEqual(enrich.classify_email('support@wundertech.net', own), 'Generic')
        self.assertEqual(enrich.classify_email('business-inquiries@wundertech.net', own), 'Generic')
        self.assertEqual(enrich.classify_email('info@gmail.com', own), 'Generic')
        self.assertEqual(enrich.classify_email('x@agency.com', own), 'Other Domain')
        self.assertEqual(enrich.classify_email('', own), '')

    def test_order_personal_and_named_own_first(self):
        contacts = [dict(email='support@wundertech.net', supported=True), dict(email='x@agency.com', supported=True),
                    dict(email='frank@wundertech.net', supported=True), dict(email='f@gmail.com', supported=False),
                    dict(email='g@gmail.com', supported=True)]
        ordered = [c['email'] for c in enrich.sort_contacts(contacts, ['wundertech.net'])]
        self.assertEqual(ordered, ['g@gmail.com', 'f@gmail.com', 'frank@wundertech.net', 'x@agency.com', 'support@wundertech.net'])

    def test_manual_check_and_button(self):
        self.assertEqual(enrich.button_state({'email_button': 'Button Present'}), 'Button Present')
        self.assertEqual(enrich.button_state({'status': 'blocked'}), 'Not Checked')
        self.assertEqual(enrich.button_state({}), 'Not Checked')
        mail = [dict(email='info@x.com')]
        self.assertEqual(enrich.manual_check('Button Present', mail, ['x.com']), 'Yes')
        self.assertEqual(enrich.manual_check('Button Present', mail + [dict(email='a@gmail.com')], ['x.com']), '')
        self.assertEqual(enrich.manual_check('No Button', mail, ['x.com']), '')
        self.assertEqual(enrich.manual_check('Not Checked', [], []), '')


def make_channel():
    return {'id': 'UCx', 'snippet': {'title': 'Dave Asprey'}, 'statistics': {'subscriberCount': '330000'}}


EV = dict(niche='Health', videos_checked=20, videos_above=5, average_views=9000, active=[1, 2, 3], last_upload='2026-11-01', reason='')


class RowBehaviourTests(unittest.TestCase):
    def rows(self, research, cfg=None):
        from src.pipeline import build_rows
        loaded, _ = load()
        loaded.update(cfg or {})
        base = dict(contacts={}, links={}, phones=[], team_pages=[], people=[])
        base.update(research)
        return build_rows(make_channel(), EV, base, loaded, 'run1', utcnow())

    def test_no_guess_and_no_title_inference_by_default(self):
        row = self.rows(dict(guess_domain='daveasprey.com'))[0]
        self.assertEqual(row['Guessed Email'], '')
        self.assertEqual(row['First Name'], 'Team')
        self.assertEqual(row['Full Name'], 'Team')   # unchanged placeholder when no owner is proven
        self.assertEqual(row['Owner Name'], '')
        self.assertNotIn('Inferred', row['Evidence Note'])

    def test_flags_off_by_default(self):
        cfg, _ = load()
        self.assertFalse(cfg['guess_email'])
        self.assertFalse(cfg['infer_name_from_title'])
        self.assertFalse(cfg['search_api_enabled'])
        self.assertFalse(cfg['hunter_enabled'])

    def test_proven_owner_fills_columns(self):
        owner = dict(full_name='Frank Joseph', first_name='Frank', source=OWN, evidence="Hi, I'm Frank Joseph", designation='')
        research = dict(owner=owner, own_domains=['creator.example'], youtube_business_email='Button Present',
            contacts={'info@creator.example': dict(email='info@creator.example', source=OWN, supported=True, evidence='e'),
                      'frank@creator.example': dict(email='frank@creator.example', source=OWN, supported=True, evidence='e')})
        rows = self.rows(research)
        self.assertEqual([r['Email'] for r in rows], ['frank@creator.example', 'info@creator.example'])
        self.assertEqual([r['Email Type'] for r in rows], ['Own Domain', 'Generic'])
        first = rows[0]
        self.assertEqual((first['Full Name'], first['First Name'], first['Owner Name']), ('Frank Joseph', 'Frank', 'Frank Joseph'))
        self.assertEqual((first['Owner Name Source'], first['Owner Name Evidence']), (OWN, "Hi, I'm Frank Joseph"))
        self.assertEqual(first['Email Source'], OWN)
        self.assertEqual((first['YouTube Business Email'], first['Manual Check']), ('Button Present', 'Yes'))

    def test_legacy_flags_still_work_when_turned_on(self):
        row = self.rows(dict(guess_domain='daveasprey.com'), dict(infer_name_from_title=True, guess_email=True))[0]
        self.assertEqual(row['Guessed Email'], 'dave@daveasprey.com')

    def test_new_headers(self):
        for h in ['Owner Name', 'Owner Name Source', 'Owner Name Evidence', 'Email Type', 'Email Source',
                  'YouTube Business Email', 'Manual Check']:
            self.assertIn(h, HEADERS)
        self.assertEqual(len(HEADERS), len(set(HEADERS)))
        self.assertTrue(all('-' not in h and '_' not in h for h in HEADERS))


class HookTests(unittest.TestCase):
    def test_hooks_off_without_flag_or_key(self):
        with mock.patch.dict('os.environ', {'SEARCH_API_KEY': 'k', 'HUNTER_API_KEY': 'k'}):
            self.assertFalse(enrich.search_enabled({}))
            self.assertFalse(enrich.hunter_enabled({}))
            self.assertEqual(enrich.search_urls('x', {}), [])
        with mock.patch.dict('os.environ', {}, clear=True):
            self.assertFalse(enrich.search_enabled({'search_api_enabled': True}))
            self.assertIsNone(enrich.hunter_lookup('a.com', 'Frank Joseph', {'hunter_enabled': True}))

    def test_search_and_hunter_use_env_key_and_official_hosts(self):
        calls = []
        class R:
            ok = True
            def __init__(self, data): self.data = data
            def json(self): return self.data
        class Req:
            @staticmethod
            def get(url, **kw):
                calls.append((url, kw))
                if 'brave' in url:
                    return R({'web': {'results': [{'url': 'https://creator.example/about'}]}})
                return R({'data': {'email': 'frank@creator.example', 'score': 90, 'verification': {'status': 'valid'}}})
        cfg = dict(search_api_enabled=True, hunter_enabled=True)
        with mock.patch.dict('os.environ', {'SEARCH_API_KEY': 'sk', 'HUNTER_API_KEY': 'hk'}):
            self.assertEqual(enrich.search_urls('Chan', cfg, Req), ['https://creator.example/about'])
            self.assertEqual(enrich.hunter_lookup('creator.example', 'Frank Joseph', cfg, Req)['email'], 'frank@creator.example')
            self.assertIsNone(enrich.hunter_lookup('other.com', 'Frank Joseph', cfg, Req))   # address on a different domain refused
        self.assertTrue(all('google.' not in u for u, _ in calls))
        self.assertNotIn('sk', ' '.join(u for u, _ in calls))   # key goes in a header, never the URL

    def test_collect_attaches_owner_and_never_clicks(self):
        cfg, _ = load()
        research = Research(cfg, Counter())
        research.channel_panel = lambda cid: {'status': 'partial', 'emails': [], 'links': ['https://creator.example'], 'email_button': 'Button Present'}
        page = Page()
        page.feed("<html><body><p>Hi, I'm Frank Joseph</p><a href='mailto:frank@creator.example'>mail</a></body></html>")
        research.fetch = lambda url: (url, page)
        result = research.collect({'id': 'UCtest', 'snippet': {'title': 'Chan', 'description': ''}}, [])
        self.assertEqual(result['owner']['full_name'], 'Frank Joseph')
        self.assertEqual(result['youtube_business_email'], 'Button Present')
        self.assertIn('creator.example', result['own_domains'])

    def test_panel_never_clicks_email_button(self):
        import inspect
        from src import youtube_panel
        source = inspect.getsource(youtube_panel)
        self.assertNotRegex(source, r"(?i)view email address.{0,80}click|click.{0,80}view email address")
        self.assertIn("'email_button'", source)


if __name__ == '__main__':
    unittest.main()
