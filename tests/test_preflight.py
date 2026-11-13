import json
import os
import unittest
from unittest.mock import patch
from src.preflight import validate_secrets, SetupError

class PreflightTests(unittest.TestCase):
    def test_missing_secret_names_are_clear(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SetupError, 'YOUTUBE_API_KEY'):
                validate_secrets()

    def test_oauth_json_rejected(self):
        with patch.dict(os.environ, {'YOUTUBE_API_KEY':'hidden','GOOGLE_SHEET_ID':'sheet',
                'GOOGLE_SERVICE_ACCOUNT_JSON':'{"installed":{}}'}, clear=True):
            with self.assertRaisesRegex(SetupError,'Service Account'):
                validate_secrets()

    def test_full_url_normalized_without_printing_secrets(self):
        credentials={'type':'service_account','client_email':'robot@example.org',
                     'private_key':'PRIVATE_TEST_VALUE','token_uri':'uri','project_id':'project'}
        with patch.dict(os.environ, {'YOUTUBE_API_KEY':'SECRET_TEST_VALUE',
                'GOOGLE_SHEET_ID':'https://docs.google.com/spreadsheets/d/abc_123/edit#gid=0',
                'GOOGLE_SERVICE_ACCOUNT_JSON':json.dumps(credentials)},clear=True):
            with patch('builtins.print') as output:
                validate_secrets()
            self.assertEqual(os.environ['GOOGLE_SHEET_ID'],'abc_123')
            self.assertNotIn('SECRET_TEST_VALUE',str(output.call_args_list))
            self.assertNotIn('PRIVATE_TEST_VALUE',str(output.call_args_list))
