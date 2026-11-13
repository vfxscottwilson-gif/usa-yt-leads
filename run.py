import argparse
import json
import os
from pathlib import Path
from src.pipeline import run
from src.sheets import SheetsError
from src.preflight import SetupError, validate_secrets

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='USA YT Leads')
    parser.add_argument('--check-config',action='store_true')
    args = parser.parse_args()
    try:
        if not args.check_config:
            validate_secrets()
        raise SystemExit(run(check_only=args.check_config))
    except Exception as exc:
        message = str(exc) if isinstance(exc,(SheetsError,SetupError)) else 'Unexpected failure; inspect the safe stack location below.'
        for name in ('YOUTUBE_API_KEY','GOOGLE_SERVICE_ACCOUNT_JSON','GOOGLE_SHEET_ID'):
            value=os.environ.get(name,'')
            if value: message=message.replace(value,'[REDACTED]')
        import traceback
        frames=[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(exc.__traceback__)]
        detail={'status':'Failed','type':type(exc).__name__,'message':message,'locations':frames}
        output=Path(__file__).parent/'output'
        output.mkdir(exist_ok=True)
        (output/'startup_error.json').write_text(json.dumps(detail,indent=2),encoding='utf-8')
        print('Run failed ('+type(exc).__name__+'): '+message)
        print('Safe stack locations: '+json.dumps(frames))
        raise SystemExit(1)
