import json
from pathlib import Path
import sys


def main():
    source,target=map(Path,sys.argv[1:3])
    try:
        payload=json.loads(source.read_text(encoding='utf-8'))
        if payload['task']=='youtube_panel':
            from .youtube_panel import fetch_channel
            result=fetch_channel(payload['channel_id'],payload.get('cfg',{}))
        elif payload['task']=='public_page':
            from .browser import render_public
            url,html,requests=render_public(payload['url'],payload['cfg'])
            result=dict(status='ok',url=url,html=html,requests=requests)
        else:
            raise ValueError('Unknown browser task')
    except Exception as exc:
        result={'status':'error','reason':type(exc).__name__ + (': ' + str(exc)[:80] if isinstance(exc, ValueError) else '')}
    target.write_text(json.dumps(result),encoding='utf-8')

if __name__=='__main__':
    main()
