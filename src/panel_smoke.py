"""Real DOM fixtures verify public panel extraction and challenge detection."""
from playwright.sync_api import sync_playwright
from .youtube_panel import collect_panel


def main():
    with sync_playwright() as driver:
        browser=driver.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            page.set_content('<ytd-about-channel-renderer style="display:block">Description Links More info <span>public@creator.example</span><a href="https://instagram.com/creator">Instagram</a><span style="display:none">hidden@creator.example</span></ytd-about-channel-renderer>')
            result=collect_panel(page)
            assert result['status']=='ok',result
            assert result['emails']==['public@creator.example'],result
            assert result['links']==['https://instagram.com/creator'],result
            page.set_content('<p>Verify you are human</p>')
            assert collect_panel(page)['status']=='blocked'
            page.set_content('<yt-description-preview-view-model><button onclick="document.getElementById(\'panel\').style.display=\'block\'">More</button></yt-description-preview-view-model><ytd-about-channel-renderer id="panel" style="display:none">Description Links visible@creator.example</ytd-about-channel-renderer>')
            assert collect_panel(page)['emails']==['visible@creator.example']
            print('Real DOM panel, More interaction, hidden-text exclusion and block detection passed.')
        finally:
            browser.close()

if __name__=='__main__':main()
