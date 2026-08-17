import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright

from shared import run_firefox_smoke_suite, run_main, wait_for_ws_server

WS_URL = "ws://localhost:7861/camoufox"


def main() -> None:
    with sync_playwright() as p:
        browser = wait_for_ws_server(p, WS_URL, timeout=40)
        context = browser.new_context()
        context.set_default_timeout(15000)
        run_firefox_smoke_suite(context, extended=True)

        context.set_default_timeout(30000)
        page = context.new_page()
        page.goto("https://x.com/googledevs", wait_until="domcontentloaded")
        print(f'заголовок страницы: "{page.title()}"')
        page.close()

        context.close()
        browser.close()


if __name__ == "__main__":
    run_main(main)