"""Isolate browser tasks so a deadline can terminate their process tree."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


def run_browser_task(task, payload, timeout=30):
    with tempfile.TemporaryDirectory(prefix='yt_browser_') as folder:
        source, target = Path(folder)/'input.json', Path(folder)/'output.json'
        source.write_text(json.dumps({'task':task, **payload}), encoding='utf-8')
        env = {k:v for k,v in os.environ.items() if k not in
               {'YOUTUBE_API_KEY','GOOGLE_SERVICE_ACCOUNT_JSON','GOOGLE_SHEET_ID'}}
        options = {'start_new_session':True} if os.name != 'nt' else {
            'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
        process = subprocess.Popen([sys.executable,'-m','src.browser_worker',str(source),str(target)],
            cwd=Path(__file__).resolve().parents[1], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                import psutil
                try:
                    parent = psutil.Process(process.pid)
                    children = parent.children(recursive=True)
                    for child in reversed(children):
                        try: child.kill()
                        except psutil.NoSuchProcess: pass
                    process.kill()
                    psutil.wait_procs(children, timeout=3)
                except psutil.NoSuchProcess:
                    pass
            else:
                try:
                    os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=5)
            return {'status':'timeout','reason':f'Hard deadline of {timeout} seconds reached'}
        if not target.exists():
            return {'status':'error','reason':'Browser worker exited without a result'}
        try:
            return json.loads(target.read_text(encoding='utf-8'))
        except (ValueError,OSError):
            return {'status':'error','reason':'Invalid browser worker output'}
