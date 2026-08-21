import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import BrowserContext, sync_playwright

from shared import run_chromium_smoke_suite, run_main, wait_for_cdp_server

CDP_URL = "http://localhost:9222"


def run_yandex_search_scenario(context: BrowserContext, query: str) -> None:
    page = context.new_page()
    try:
        page.goto(
            f'https://yandex.com/search?text={quote(query.replace(" ", "+"), safe="+")}&lr=84',
            wait_until="domcontentloaded",
            timeout=90000,
        )
        print(f'итоговый URL: "{page.url}"')
        page.screenshot(path="clearcote_screen.jpeg", full_page=True, type="jpeg", quality=50)
    finally:
        page.close()


def main(query: str = "bufo bufo care") -> None:
    wait_for_cdp_server(CDP_URL, timeout=40)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        context.set_default_timeout(15000)
        run_chromium_smoke_suite(context, expected_extensions_count=0)

        context.set_default_timeout(60000)
        run_yandex_search_scenario(context, query)

        context.close()
        browser.close()


if __name__ == "__main__":
    run_main(main)