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
