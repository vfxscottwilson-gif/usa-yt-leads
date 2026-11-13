"""Verify actual Scrapling DynamicFetcher and panel extraction against a local fixture."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from scrapling.fetchers import DynamicFetcher
from .youtube_panel import collect_panel

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'<yt-description-preview-view-model><button onclick="document.getElementById(\'p\').style.display=\'block\'">More</button></yt-description-preview-view-model><ytd-about-channel-renderer id="p" style="display:none">Description Links <span>dynamic@creator.example</span></ytd-about-channel-renderer>'
        self.send_response(200)
        self.send_header('Content-Type','text/html')
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*args):pass


def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    result={}
    try:
        DynamicFetcher.fetch('http://127.0.0.1:'+str(server.server_port),headless=True,
            network_idle=False, timeout=10000, google_search=False, disable_resources=True,
            useragent='YTLeadResearch/1.0 (public channel contact research)',
            additional_args={'service_workers':'block','accept_downloads':False},
            page_action=lambda page:result.update(collect_panel(page)),selector_config={'adaptive':False})
        assert result.get('emails')==['dynamic@creator.example'],result
        print('Actual Scrapling DynamicFetcher launched Chromium, opened More, extracted visible email.')
    finally:
        server.shutdown();server.server_close()

if __name__=='__main__':main()
