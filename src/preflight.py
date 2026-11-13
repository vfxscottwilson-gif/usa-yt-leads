import json
import os
import re

class SetupError(Exception):
    pass

def validate_secrets():
    required = ('YOUTUBE_API_KEY','GOOGLE_SERVICE_ACCOUNT_JSON','GOOGLE_SHEET_ID')
    missing = [name for name in required if not os.environ.get(name, '').strip()]
    if missing:
        raise SetupError('Missing repository Actions secret: ' + ', '.join(missing) + '. Use Settings > Secrets and variables > Actions > Secrets.')
    for name in required:
        os.environ[name] = os.environ[name].strip()
    try:
        credentials = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
    except ValueError:
        raise SetupError('GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON. Paste the entire downloaded JSON object, not its filename or only its private key.') from None
    if not isinstance(credentials, dict) or credentials.get('type') != 'service_account':
        raise SetupError('Use a Service Account JSON key, not an OAuth client JSON or API key.')
    fields = ('client_email','private_key','token_uri','project_id')
    if any(not credentials.get(field) for field in fields):
        raise SetupError('Service account JSON is incomplete. Replace the secret with the complete downloaded file.')
    value = os.environ['GOOGLE_SHEET_ID']
    match = re.search(r'/spreadsheets/d/([A-Za-z0-9_-]+)', value)
    if match:
        value = match.group(1)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise SetupError('GOOGLE_SHEET_ID must be the spreadsheet ID or its full Google Sheets URL.')
    os.environ['GOOGLE_SHEET_ID'] = value
    print(f"Secret key belongs to service account {credentials['client_email']} in project {credentials['project_id']}; sheet ID ends ...{value[-6:]}. Share the sheet with that exact email.")
    print('Secret presence and JSON format checks passed. Values are hidden; live access is checked during collection.')
    return credentials

if __name__ == '__main__':
    try:
        validate_secrets()
    except SetupError as exc:
        from pathlib import Path
        output = Path(__file__).resolve().parents[1] / 'output'
        output.mkdir(exist_ok=True)
        (output / 'preflight_error.json').write_text(json.dumps({'status':'Failed','message':str(exc)}), encoding='utf-8')
        print(str(exc))
        raise SystemExit(1)
