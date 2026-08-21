import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright

from shared import run_common_capabilities, run_main, wait_for_cdp_server

CDP_URL = "http://localhost:9222"


def main() -> None:
    print(f"Ожидание запуска Clearcote CDP на {CDP_URL}...", flush=True)
    wait_for_cdp_server(CDP_URL, timeout=40)

    with sync_playwright() as p:
        print("Подключение к Clearcote через CDP (Probe)...", flush=True)
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        context.set_default_timeout(15000)

        # Прогрев возможностей браузера для регистрации SlimToolkit всех динамических библиотек
        run_common_capabilities(context)

        try:
            page = context.new_page()
            page.goto("https://ya.ru", wait_until="domcontentloaded", timeout=30000)
            print(f'Probe URL: "{page.url}", Title: "{page.title()}"', flush=True)
            page.close()
        except Exception as e:
            print(f"[WARN] Probe navigation warning: {e}", flush=True)

        context.close()
        browser.close()


if __name__ == "__main__":
    run_main(main)