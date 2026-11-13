"""Real Chromium + JavaScript + Scrapling smoke test; no external requests."""
from playwright.sync_api import sync_playwright
from .extractors.scrapling_html import extract


def main():
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content("""<div id="root"></div><script>
            setTimeout(() => {document.getElementById('root').innerHTML =
            '<span itemprop="email">fixture@creator.example</span>';}, 50);
            </script>""")
            page.wait_for_selector('[itemprop="email"]')
            result = extract(page.content())
            assert result['emails'] == ['fixture@creator.example'], result
            print('Real Chromium JavaScript rendering and Scrapling extraction passed. No live contacts collected.')
        finally:
            browser.close()

if __name__ == '__main__':
    main()
