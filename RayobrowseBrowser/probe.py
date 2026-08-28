# ./RayobrowseBrowser/probe.py
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright
from shared.capabilities import run_chromium_smoke_suite
from shared.utils import run_main, wait_for_cdp_server

CDP_URL = "http://localhost:9222"


def main() -> None:
    print(f"Ожидание запуска Rayobrowse CDP на {CDP_URL}...", flush=True)
    wait_for_cdp_server(CDP_URL, timeout=90)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        context.set_default_timeout(15000)

        # run_chromium_smoke_suite(context, expected_extensions_count=5)

        page = context.new_page()
        try:
            page.goto("https://google.com", wait_until="domcontentloaded", timeout=15000)
            print(f'Заголовок страницы: "{page.title()}"', flush=True)
            assert page.title()
        finally:
            page.close()

        context.close()
        browser.close()
        print("✅ PROBE УСПЕШНО ЗАВЕРШЕН", flush=True)


if __name__ == "__main__":
    run_main(main)