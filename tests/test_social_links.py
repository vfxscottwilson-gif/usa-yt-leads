import unittest
from src.social_links import canonical_profile
from src.contacts import record_link,normalize_phone

class SocialLinksTests(unittest.TestCase):
    def test_footer_links_rejected(self):
        for path in ['login/','recover/initiate/','privacy/policy/','help/123','watch/','reg/','ad_campaign/landing.php','pages/create']:
            self.assertEqual(canonical_profile('https://www.facebook.com/'+path),'')

    def test_profiles_canonicalized_and_deduplicated(self):
        result={'links':{}}
        for value in ['https://m.facebook.com/official.natethelawyer?ref=footer','https://www.facebook.com/official.natethelawyer/']:
            record_link(result,value,'source')
        self.assertEqual(result['links']['Facebook'],'https://www.facebook.com/official.natethelawyer')
        self.assertNotIn('All Discovered Links',result['links'])
        self.assertEqual(canonical_profile('https://instagram.com/bagfuel/?hl=en'),'https://www.instagram.com/bagfuel')
        self.assertEqual(canonical_profile('https://www.facebook.com/profile.php?id=123&ref=test'),'https://www.facebook.com/profile.php?id=123')

    def test_us_phone_spacing(self):
        for value in ['+1 (408) 877-1505','4088771505','1 408 877 1505']:
            self.assertEqual(normalize_phone(value),'408 877 1505')


class ProfileLinkFixTests(unittest.TestCase):
    def test_linkedin_variants_accepted_and_trimmed(self):
        cases = {
            'https://uk.linkedin.com/in/jane-doe': 'https://www.linkedin.com/in/jane-doe',
            'https://ca.linkedin.com/in/jane-doe/': 'https://www.linkedin.com/in/jane-doe',
            'https://de.linkedin.com/company/acme': 'https://www.linkedin.com/company/acme',
            'https://www.linkedin.com/in/jane-doe/details/experience/': 'https://www.linkedin.com/in/jane-doe',
            'https://www.linkedin.com/company/acme/about/?viewAsMember=true': 'https://www.linkedin.com/company/acme',
            'https://www.linkedin.com/showcase/acme-labs/': 'https://www.linkedin.com/showcase/acme-labs',
            'https://www.linkedin.com/school/mit/': 'https://www.linkedin.com/school/mit',
            'https://www.linkedin.com/pub/jane-doe/1/2/3': 'https://www.linkedin.com/pub/jane-doe/1/2/3',
        }
        for given, expected in cases.items():
            self.assertEqual(canonical_profile(given), expected, given)

    def test_linkedin_non_profiles_dropped(self):
        for url in ['https://www.linkedin.com/', 'https://www.linkedin.com/feed/', 'https://www.linkedin.com/login',
                    'https://www.linkedin.com/in/', 'https://lnkd.in/abc123']:
            self.assertEqual(canonical_profile(url), '', url)

    def test_facebook_variants_accepted(self):
        cases = {
            'https://web.facebook.com/acme': 'https://www.facebook.com/acme',
            'https://m.facebook.com/acme/about': 'https://www.facebook.com/acme',
            'https://www.facebook.com/acme/posts/': 'https://www.facebook.com/acme',
            'https://www.facebook.com/acme/photos?ref=x': 'https://www.facebook.com/acme',
            'https://fb.com/acme': 'https://www.facebook.com/acme',
            'https://fb.me/acme': 'https://www.facebook.com/acme',
            'https://www.facebook.com/people/Jane-Doe/100012345678901/': 'https://www.facebook.com/people/Jane-Doe/100012345678901',
            'https://www.facebook.com/profile.php?id=123&ref=x': 'https://www.facebook.com/profile.php?id=123',
        }
        for given, expected in cases.items():
            self.assertEqual(canonical_profile(given), expected, given)

    def test_facebook_non_profiles_still_dropped(self):
        for url in ['https://www.facebook.com/login', 'https://www.facebook.com/sharer.php?u=x', 'https://www.facebook.com/groups/abc',
                    'https://www.facebook.com/events/123', 'https://www.facebook.com/share/abc', 'https://www.facebook.com/people/Jane/notdigits',
                    'https://www.facebook.com/acme/whatever', 'https://web.facebook.com/dialog/share']:
            self.assertEqual(canonical_profile(url), '', url)

    def test_lnkd_in_only_in_all_discovered_links(self):
        result = {'links': {}}
        record_link(result, 'https://lnkd.in/abc123', 'src')
        self.assertEqual(result['links'], {'All Discovered Links': 'https://lnkd.in/abc123'})
        record_link(result, 'https://lnkd.in/abc123', 'src')
        self.assertEqual(result['links']['All Discovered Links'], 'https://lnkd.in/abc123')

    def test_record_link_fills_columns_for_regional_hosts(self):
        result = {'links': {}}
        record_link(result, 'https://uk.linkedin.com/in/jane-doe/details/experience/', 's')
        record_link(result, 'https://web.facebook.com/acme/about', 's')
        self.assertEqual(result['links']['LinkedIn'], 'https://www.linkedin.com/in/jane-doe')
        self.assertEqual(result['links']['Personal LinkedIn'], 'https://www.linkedin.com/in/jane-doe')
        self.assertEqual(result['links']['Facebook'], 'https://www.facebook.com/acme')

    def test_social_gap_note(self):
        from src.enrich import social_gap_note
        self.assertIn('blocked', social_gap_note({'panel_status': 'blocked', 'links': {}}))
        self.assertEqual(social_gap_note({'panel_status': 'ok', 'links': {}}), '')
        self.assertEqual(social_gap_note({'panel_status': 'blocked', 'links': {'LinkedIn': 'x', 'Facebook': 'y'}}), '')
